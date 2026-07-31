"""
Построитель графов на networkx + отрисовка matplotlib.
"""

import networkx as nx
import matplotlib.pyplot as plt
from typing import Optional
from dataclasses import dataclass


@dataclass
class GraphConfig:
    """Настройки отрисовки графа."""
    figsize: tuple = (14, 10)
    node_size_base: int = 300
    node_size_multiplier: float = 1.5
    edge_alpha: float = 0.3
    edge_width_base: float = 0.5
    edge_width_multiplier: float = 2.0
    font_size: int = 7
    title: str = "Wallet Cluster Graph"
    show_labels: bool = True


class WalletGraph:
    """Граф связей кошельков."""

    def __init__(self):
        self.graph = nx.Graph()
        self._address_to_id: dict[str, str] = {}

    def add_wallet(self, address: str, balance_usd: float = 0, label: str = None, 
                   risk_level: str = "unknown", cluster_id: int = None):
        """
        Добавить кошелёк как узел.
        
        Args:
            address: адрес кошелька
            balance_usd: баланс в USD (влияет на размер узла)
            label: подпись узла (если None — первые 8 символов адреса)
            risk_level: уровень риска: green, yellow, red, unknown
            cluster_id: ID кластера
        """
        node_id = address
        self.graph.add_node(
            node_id,
            balance=balance_usd,
            label=label or address[:8] + "...",
            risk_level=risk_level,
            cluster_id=cluster_id,
        )

    def add_link(self, address_a: str, address_b: str, weight: float = 1.0, 
                 common_tx: int = 0):
        """
        Добавить связь между кошельками.
        
        Args:
            address_a, address_b: адреса кошельков
            weight: сила связи (чем больше, тем жирнее ребро)
            common_tx: количество общих транзакций
        """
        # Если узлов ещё нет — создаём
        if address_a not in self.graph:
            self.add_wallet(address_a)
        if address_b not in self.graph:
            self.add_wallet(address_b)

        self.graph.add_edge(address_a, address_b, weight=weight, common_tx=common_tx)

    def find_clusters(self, min_weight: float = 3.0) -> list[set[str]]:
        """
        Найти кластеры (группы связанных кошельков).
        Использует связные компоненты, фильтрует по минимальному весу.
        
        Returns:
            Список кластеров, каждый кластер — множество адресов
        """
        # Создаём копию графа, оставляя только сильные связи
        filtered = nx.Graph()
        for u, v, data in self.graph.edges(data=True):
            if data.get("weight", 0) >= min_weight:
                filtered.add_edge(u, v, **data)

        # Копируем узлы
        for node, data in self.graph.nodes(data=True):
            filtered.add_node(node, **data)

        # Находим связные компоненты
        clusters = list(nx.connected_components(filtered))
        return clusters

    def render(self, output_path: str = None, config: GraphConfig = None) -> str:
        """
        Отрисовать граф и сохранить в PNG.
        
        Args:
            output_path: путь для сохранения (если None — в DATA_DIR)
            config: настройки отрисовки
            
        Returns:
            Путь к сохранённому файлу
        """
        if config is None:
            config = GraphConfig()
        
        if output_path is None:
            from ..config import settings
            output_path = str(settings.DATA_DIR / "cluster_graph.png")

        G = self.graph

        # Цвета по уровню риска
        risk_colors = {
            "red": "#FF4444",
            "yellow": "#FFBB33",
            "green": "#00C851",
            "unknown": "#999999",
        }
        node_colors = [
            risk_colors.get(G.nodes[n].get("risk_level", "unknown"), "#999999")
            for n in G.nodes
        ]

        # Размер узла = баланс
        balances = [G.nodes[n].get("balance", 0) for n in G.nodes]
        max_balance = max(balances) if balances and max(balances) > 0 else 1
        node_sizes = [
            config.node_size_base + (b / max_balance) * config.node_size_base * config.node_size_multiplier
            for b in balances
        ]

        # Толщина рёбер = вес связи
        edge_weights = [G.edges[e].get("weight", 0.5) for e in G.edges]
        max_weight = max(edge_weights) if edge_weights and max(edge_weights) > 0 else 1
        edge_widths = [
            config.edge_width_base + (w / max_weight) * config.edge_width_multiplier
            for w in edge_weights
        ]

        # Отрисовка
        fig, ax = plt.subplots(figsize=config.figsize)
        pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)

        nx.draw_networkx_edges(G, pos, alpha=config.edge_alpha, width=edge_widths,
                               edge_color="#888888", ax=ax)
        nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors,
                               alpha=0.9, ax=ax)

        if config.show_labels:
            labels = {n: G.nodes[n].get("label", n[:8]) for n in G.nodes}
            nx.draw_networkx_labels(G, pos, labels, font_size=config.font_size,
                                    font_color="#333333", ax=ax)

        ax.set_title(config.title, fontsize=14, fontweight="bold")
        ax.axis("off")

        # Легенда
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#FF4444", label="High Risk"),
            Patch(facecolor="#FFBB33", label="Medium Risk"),
            Patch(facecolor="#00C851", label="Low Risk"),
            Patch(facecolor="#999999", label="Unknown"),
        ]
        ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()

        return output_path

    def stats(self) -> dict:
        """Статистика графа."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "density": nx.density(self.graph),
            "clusters_found": len(self.find_clusters()),
        }