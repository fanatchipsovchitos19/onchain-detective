"""
Монитор движения китов.
Отслеживает крупные перемещения ETH на биржи.
"""

import time
from datetime import datetime, timedelta
from typing import Optional

from ..providers.base import BaseProvider
from ..providers.etherscan import EtherscanProvider
from ..config import settings
from ..utils.telegram import TelegramAlerter


class WhaleMonitor:
    """Мониторинг кошельков китов."""

    # Известные адреса бирж
    EXCHANGE_ADDRESSES = {
        "0x28c6c06298d514db089934071355e5743bf21d60".lower(): "Binance",
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549".lower(): "Binance 2",
        "0xdfd5293d8e347dfe59e90efd55b2956a1343963d".lower(): "Coinbase",
        "0x71660c4005ba85c37ccec55d0c4493e66fe775d3".lower(): "Coinbase 2",
        "0x75e89d5979e4f6fba9f97c104c2f0afb3f1dcb88".lower(): "Kraken",
        "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0".lower(): "Kraken 2",
    }

    def __init__(self, provider: BaseProvider, alerter: TelegramAlerter = None):
        self.provider = provider
        self.alerter = alerter or TelegramAlerter()
        self._known_whales: list[str] = []
        self._last_check: dict[str, datetime] = {}

    def load_top_whales(self, count: int = 10) -> list[str]:
        """
        Загружает топ-N адресов по балансу ETH.
        Для продакшена — использовать Arkham API.
        Здесь упрощённо: используем известных китов.
        """
        # Известные киты Ethereum (можно заменить на API)
        known = [
            "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # Vitalik
            "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",  # Binance 7
            "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",  # Arbitrum Bridge
            "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",  # Binance-Peg
        ]
        self._known_whales = known[:count]
        return self._known_whales

    def check_wallet(self, address: str) -> Optional[dict]:
        """
        Проверяет кошелёк на предмет крупных движений.
        
        Returns:
            Словарь с информацией о транзакции или None
        """
        # Получаем последние 10 транзакций
        txs = self.provider.get_transactions(address)[-10:]

        if not txs:
            return None

        # Проверяем последнюю транзакцию
        last_tx = txs[-1]

        # Проверяем, не проверяли ли уже
        tx_time = last_tx.timestamp
        if address in self._last_check:
            if tx_time <= self._last_check[address]:
                return None

        self._last_check[address] = tx_time

        # Фильтр: сумма > $50k
        eth_price = 3000  # упрощённо, можно заменить на API CoinGecko
        value_usd = last_tx.value * eth_price

        if value_usd < 50000:
            return None

        # Определяем действие
        to_addr = last_tx.to_address.lower()
        action = "unknown"
        exchange_name = None

        if to_addr in self.EXCHANGE_ADDRESSES:
            action = "sell"  # перевод на биржу = вероятная продажа
            exchange_name = self.EXCHANGE_ADDRESSES[to_addr]
        elif last_tx.from_address.lower() in self.EXCHANGE_ADDRESSES:
            action = "buy"  # вывод с биржи
            exchange_name = self.EXCHANGE_ADDRESSES.get(last_tx.from_address.lower())
        else:
            action = "transfer"

        return {
            "address": address,
            "action": action,
            "amount_eth": last_tx.value,
            "amount_usd": value_usd,
            "tx_hash": last_tx.hash,
            "exchange": exchange_name,
            "timestamp": tx_time,
        }

    def scan_and_alert(self, ai_analyzer=None) -> list[dict]:
        """
        Сканирует всех китов и отправляет алерты.
        
        Returns:
            Список найденных алертов
        """
        if not self._known_whales:
            self.load_top_whales()

        alerts = []

        for whale in self._known_whales:
            try:
                movement = self.check_wallet(whale)
                if movement:
                    print(f"[Whale] Найдено движение: {movement['address'][:10]}... "
                          f"{movement['action']} ${movement['amount_usd']:,.0f}")

                    # AI-комментарий (если есть анализатор)
                    ai_comment = ""
                    if ai_analyzer:
                        try:
                            prompt = f"Кит {whale[:10]}... переводит ${movement['amount_usd']:,.0f} на {movement.get('exchange', 'неизвестный адрес')}. Это вероятная продажа или покупка? Ответь одной фразой на русском."
                            ai_response = ai_analyzer.client.chat.completions.create(
                                model=ai_analyzer.model,
                                messages=[{"role": "user", "content": prompt}],
                                max_tokens=100,
                            )
                            ai_comment = ai_response.choices[0].message.content.strip()
                        except:
                            pass

                    # Отправляем алерт
                    self.alerter.send_whale_alert(
                        whale_address=whale,
                        action=movement["action"],
                        amount_usd=movement["amount_usd"],
                        tx_hash=movement["tx_hash"],
                        ai_comment=ai_comment,
                    )

                    alerts.append(movement)

            except Exception as e:
                print(f"[Whale] Ошибка проверки {whale[:10]}: {e}")
                continue

        return alerts

    def run_loop(self, interval_minutes: int = 5, ai_analyzer=None):
        """
        Запускает бесконечный цикл мониторинга.
        """
        print(f"[Whale] Запускаю мониторинг (интервал: {interval_minutes} мин)...")
        print(f"[Whale] Китов на отслеживании: {len(self._known_whales)}")

        while True:
            try:
                print(f"\n[Whale] Проверка: {datetime.now().strftime('%H:%M:%S')}")
                alerts = self.scan_and_alert(ai_analyzer)
                print(f"[Whale] Найдено алертов: {len(alerts)}")
            except Exception as e:
                print(f"[Whale] Ошибка в цикле: {e}")

            time.sleep(interval_minutes * 60)