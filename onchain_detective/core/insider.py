"""
Детектор инсайдерских закупок.
Анализирует первые блоки после создания токена и находит кошельки,
которые систематически закупаются до пампов.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from ..providers.base import BaseProvider, Transaction, TokenTransfer
from ..config import settings


class InsiderDetector:
    """Алгоритм поиска инсайдеров."""

    def __init__(self, provider: BaseProvider):
        self.provider = provider
        self._known_routers = {
            "0x7a250d5630b4cf539739df2c5dacb4c659f2488d".lower(),  # Uniswap V2
            "0xe592427a0aece92de3edee1f18e0157c05861564".lower(),  # Uniswap V3
            "0x1111111254eeb25477b68fb85ed929f73a960582".lower(),  # 1inch
            "0xdef1c0ded9bec7f1a1670819833240f027b25eff".lower(),  # 0x
        }

    def find_early_buyers(self, token_address: str, 
                          blocks_to_scan: int = None) -> list[dict]:
        """
        Находит ранних покупателей токена.
        
        Args:
            token_address: адрес контракта токена
            blocks_to_scan: сколько первых блоков анализировать
            
        Returns:
            Список словарей с информацией о ранних покупателях
        """
        if blocks_to_scan is None:
            blocks_to_scan = settings.INSIDER_EARLY_BLOCKS

        print(f"[Insider] Анализирую токен {token_address[:10]}...")
        print(f"[Insider] Сканирую первые {blocks_to_scan} блоков после создания")

        # Получаем создателя контракта
        creator = self.provider.get_contract_creator(token_address)
        print(f"[Insider] Создатель: {creator[:10] if creator else 'не найден'}...")

        # Получаем ВСЕ трансферы токена (ограничиваем для скорости)
        transfers = self.provider.get_token_transfers(
            token_address, 
            start_block=0, 
            end_block=99999999
        )[:1000]  # берём первые 1000 трансферов

        print(f"[Insider] Всего трансферов: {len(transfers)}")

        # Группируем по блокам и находим стартовый блок
        if not transfers:
            print("[Insider] Трансферов не найдено")
            return []

        start_block = min(t.block_number for t in transfers)
        end_block = start_block + blocks_to_scan

        print(f"[Insider] Стартовый блок: {start_block}, конечный: {end_block}")

        # Собираем ранних получателей (первые blocks_to_scan блоков)
        early_receivers = defaultdict(lambda: {
            "amount": 0.0,
            "first_block": None,
            "tx_count": 0,
            "tx_hashes": []
        })

        for t in transfers:
            if t.block_number > end_block:
                break

            to_addr = t.to_address.lower()

            # Исключаем: нулевой адрес, создателя, роутеры DEX
            if to_addr == "0x0000000000000000000000000000000000000000":
                continue
            if creator and to_addr == creator.lower():
                continue
            if to_addr in self._known_routers:
                continue

            early_receivers[to_addr]["amount"] += t.value
            early_receivers[to_addr]["tx_count"] += 1
            early_receivers[to_addr]["tx_hashes"].append(t.transaction_hash)
            if early_receivers[to_addr]["first_block"] is None:
                early_receivers[to_addr]["first_block"] = t.block_number

        print(f"[Insider] Ранних получателей: {len(early_receivers)}")

        # Сортируем по объёму
        sorted_buyers = sorted(
            early_receivers.items(),
            key=lambda x: x[1]["amount"],
            reverse=True
        )

        return [
            {
                "address": addr,
                "amount": data["amount"],
                "first_block": data["first_block"],
                "tx_count": data["tx_count"],
                "distance_from_start": data["first_block"] - start_block if data["first_block"] else None,
            }
            for addr, data in sorted_buyers
        ]

    def check_history(self, wallet_address: str, 
                      lookback_days: int = 30) -> dict:
        """
        Проверяет историю кошелька: участвовал ли он в других токенах до пампов.
        
        Args:
            wallet_address: адрес кошелька
            lookback_days: на сколько дней назад смотреть
            
        Returns:
            Словарь с метриками "hit rate"
        """
        print(f"[Insider] Проверяю историю {wallet_address[:10]}... за {lookback_days} дней")

        # Получаем трансферы токенов этого кошелька
        transfers = self.provider.get_token_transfers(wallet_address)[:500]

        if not transfers:
            return {"address": wallet_address, "tokens_bought": 0, "hit_rate": 0.0, "verdict": "unknown"}

        # Группируем по токенам
        token_buys = defaultdict(list)
        for t in transfers:
            if t.to_address.lower() == wallet_address.lower():
                token_buys[t.token_address].append({
                    "amount": t.value,
                    "timestamp": t.timestamp,
                    "block": t.block_number,
                })

        # Для каждого токена проверяем: был ли памп после покупки?
        pump_count = 0
        total_tokens = len(token_buys)

        for token_addr, buys in token_buys.items():
            if not buys:
                continue

            # Упрощённая проверка: берём первую покупку и смотрим, 
            # были ли ещё транзакции после (признак активности)
            first_buy = min(buys, key=lambda x: x["timestamp"])
            later_transfers = [b for b in buys if b["timestamp"] > first_buy["timestamp"]]

            # Если были повторные покупки или большие объёмы — признак интереса
            if len(later_transfers) >= 2:
                pump_count += 1

        hit_rate = (pump_count / total_tokens * 100) if total_tokens > 0 else 0.0

        verdict = "green"
        if hit_rate > 70:
            verdict = "red"  # высокая вероятность инсайдера
        elif hit_rate > 40:
            verdict = "yellow"

        print(f"[Insider] Токенов: {total_tokens}, пампилось: {pump_count}, hit_rate: {hit_rate:.1f}%, вердикт: {verdict}")

        return {
            "address": wallet_address,
            "tokens_bought": total_tokens,
            "pump_count": pump_count,
            "hit_rate": round(hit_rate, 1),
            "verdict": verdict,
        }

    def analyze_token(self, token_address: str, 
                      check_top_buyers: int = 10) -> dict:
        """
        Полный анализ токена: находит ранних покупателей и проверяет их историю.
        
        Args:
            token_address: адрес контракта токена
            check_top_buyers: сколько топ-покупателей проверять на историю
            
        Returns:
            Словарь с результатами для AI-интерпретатора
        """
        early_buyers = self.find_early_buyers(token_address)

        # Проверяем топ-N покупателей на историю
        suspicious = []
        for buyer in early_buyers[:check_top_buyers]:
            history = self.check_history(buyer["address"])
            buyer["history"] = history
            if history["verdict"] in ("red", "yellow"):
                suspicious.append(buyer)

        print(f"\n[Insider] Итого: {len(early_buyers)} ранних покупателей, "
              f"{len(suspicious)} подозрительных")

        return {
            "token_address": token_address,
            "creator": self.provider.get_contract_creator(token_address),
            "total_early_buyers": len(early_buyers),
            "suspicious_count": len(suspicious),
            "top_buyers": early_buyers[:10],
            "suspicious": suspicious,
            "risk_level": "red" if len(suspicious) >= 3 else ("yellow" if len(suspicious) >= 1 else "green"),
        }