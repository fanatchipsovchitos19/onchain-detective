"""
Кластеризатор кошельков.
Находит скрытые связи между адресами через общие транзакции и временные корреляции.
"""

from collections import defaultdict
from typing import Optional
from datetime import datetime, timedelta

from ..providers.base import BaseProvider, Transaction
from ..providers.etherscan import EtherscanProvider
from ..config import settings
from .graph_builder import WalletGraph
from .db import get_session, Wallet, wallet_links


class WalletClusterer:
    """Алгоритм кластеризации кошельков."""

    def __init__(self, provider: BaseProvider):
        """
        Args:
            provider: провайдер данных (EtherscanProvider и т.д.)
        """
        self.provider = provider
        self.graph = WalletGraph()
        self._known_exchange_addresses = self._load_exchange_addresses()

    def _load_exchange_addresses(self) -> set[str]:
        """
        Загружает известные адреса бирж и роутеров DEX.
        Их исключаем из кластеризации — это шум.
        """
        # Базовый список (можно расширять)
        return {
            # Binance
            "0x28c6c06298d514db089934071355e5743bf21d60".lower(),
            "0x21a31ee1afc51d94c2efccaa2092ad1028285549".lower(),
            # Uniswap V2 Router
            "0x7a250d5630b4cf539739df2c5dacb4c659f2488d".lower(),
            # Uniswap V3 Router
            "0xe592427a0aece92de3edee1f18e0157c05861564".lower(),
            # 1inch Router
            "0x1111111254eeb25477b68fb85ed929f73a960582".lower(),
            # MEV Bot (известный)
            "0x0000000000007f150bd6f54c40a34d7c3d5e9f56".lower(),
        }

    def _is_noise(self, address: str) -> bool:
        """Проверяет, является ли адрес шумом (биржа, роутер, MEV-бот)."""
        addr_lower = address.lower()
        if addr_lower in self._known_exchange_addresses:
            return True
        # Если адрес — контракт и это не кошелёк пользователя
        # (упрощённо: контракты часто имеют длинный bytecode)
        return False

    def analyze_wallet(self, target_address: str, depth: int = 2, 
                       max_wallets: int = None) -> WalletGraph:
        """
        Анализирует кошелёк и строит граф связей.
        
        Args:
            target_address: целевой адрес для анализа
            depth: глубина рекурсивного анализа (1 = только прямые связи,
                   2 = связи связей)
            max_wallets: максимальное количество кошельков для анализа
                        (по умолчанию из settings)
            
        Returns:
            WalletGraph с построенными связями
        """
        if max_wallets is None:
            max_wallets = settings.MAX_WALLETS_TO_ANALYZE

        print(f"[Clusterer] Анализирую {target_address[:10]}... (depth={depth}, max_wallets={max_wallets})")

        # Этап 1: собираем прямые транзакции цели
        target_txs = self.provider.get_transactions(target_address)
        print(f"[Clusterer] Найдено {len(target_txs)} транзакций для целевого адреса")

        # Этап 2: извлекаем контрагентов (с кем взаимодействовал)
        counterparties = defaultdict(lambda: {"tx_count": 0, "total_value": 0.0, "timestamps": []})

        for tx in target_txs:
            other = tx.to_address if tx.from_address.lower() == target_address.lower() else tx.from_address
            if self._is_noise(other):
                continue
            counterparties[other]["tx_count"] += 1
            counterparties[other]["total_value"] += tx.value
            counterparties[other]["timestamps"].append(tx.timestamp)

        print(f"[Clusterer] Найдено {len(counterparties)} контрагентов (после фильтрации шума)")

        # Этап 3: ограничиваем количество (сортируем по сумме взаимодействий)
        sorted_counterparties = sorted(
            counterparties.items(),
            key=lambda x: x[1]["total_value"],
            reverse=True
        )[:max_wallets]

        # Добавляем целевой адрес в граф
        self.graph.add_wallet(target_address, label=target_address[:10], risk_level="unknown")

        # Этап 4: для каждого контрагента строим связи
        analyzed = {target_address.lower()}
        queue = [(addr, data, 1) for addr, data in sorted_counterparties]  # (адрес, данные, текущая глубина)

        for addr, data, current_depth in queue:
            addr_lower = addr.lower()
            if addr_lower in analyzed:
                continue
            analyzed.add(addr_lower)

            # Добавляем узел контрагента
            self.graph.add_wallet(addr, label=addr[:10], risk_level="unknown")

            # Добавляем связь с целевым
            weight = data["tx_count"] * (1 + data["total_value"])
            self.graph.add_link(target_address, addr, weight=weight, common_tx=data["tx_count"])

            # Если глубина позволяет — копаем дальше
            if current_depth < depth:
                try:
                    sub_txs = self.provider.get_transactions(addr)[:100]  # ограничиваем
                    sub_counterparties = defaultdict(int)

                    for tx in sub_txs:
                        other = tx.to_address if tx.from_address.lower() == addr_lower else tx.from_address
                        if not self._is_noise(other) and other.lower() not in analyzed:
                            sub_counterparties[other] += 1

                    # Добавляем только значимые связи (>2 общих транзакций)
                    for sub_addr, count in sub_counterparties.items():
                        if count >= 2:
                            self.graph.add_wallet(sub_addr, label=sub_addr[:10], risk_level="unknown")
                            self.graph.add_link(addr, sub_addr, weight=count * 2, common_tx=count)

                except Exception as e:
                    print(f"[Clusterer] Ошибка при анализе {addr[:10]}: {e}")
                    continue

        print(f"[Clusterer] Граф построен: {self.graph.stats()}")
        return self.graph

    def find_insider_clusters(self, min_cluster_size: int = 3) -> list[set[str]]:
        """
        Находит подозрительные кластеры (инсайдерские кольца).
        
        Args:
            min_cluster_size: минимальный размер кластера для отнесения к подозрительному
            
        Returns:
            Список подозрительных кластеров
        """
        all_clusters = self.graph.find_clusters(min_weight=3.0)
        suspicious = []

        for cluster in all_clusters:
            if len(cluster) >= min_cluster_size:
                suspicious.append(cluster)

                # Помечаем узлы как красные (высокий риск)
                for addr in cluster:
                    if addr in self.graph.graph:
                        self.graph.graph.nodes[addr]["risk_level"] = "red"

        print(f"[Clusterer] Найдено {len(suspicious)} подозрительных кластеров "
              f"(из {len(all_clusters)} всего)")
        return suspicious

    def export_report(self) -> dict:
        """
        Экспортирует результаты кластеризации в словарь для AI-интерпретатора.
        """
        clusters = self.find_insider_clusters()
        return {
            "target_address": None,  # будет заполнено в модуле AI
            "total_wallets_analyzed": self.graph.graph.number_of_nodes(),
            "total_connections": self.graph.graph.number_of_edges(),
            "suspicious_clusters": len(clusters),
            "cluster_details": [
                {
                    "size": len(c),
                    "addresses": list(c)[:20],  # максимум 20 адресов
                }
                for c in clusters
            ],
            "graph_stats": self.graph.stats(),
        }