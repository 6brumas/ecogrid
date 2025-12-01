from __future__ import annotations
from typing import Dict, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex

def initialize_capacities(graph: PowerGridGraph, index: BPlusIndex) -> None:
    """
    Inicializa a capacidade dos nós (Subestações e Usinas) baseado na topologia.
    Regra: Node.capacity = max(1.0, len(unique_consumers_in_subtree) * 1.5)

    NOTA: Nós do tipo CONSUMER_POINT são ignorados nesta função, pois sua capacidade
    é definida por regras específicas de negócio (13kW/25kW) com base nos dispositivos instalados.
    """

    # Map node_id -> Set of consumer_ids
    consumers_in_subtree: Dict[str, Set[str]] = {}

    # Bottom-up traversal: reverse of preorder
    # This ensures children are processed before parents
    nodes_ordered = list(index.iter_preorder())
    nodes_bottom_up = reversed(nodes_ordered)

    for node_id in nodes_bottom_up:
        node = graph.get_node(node_id)
        if node is None:
            continue

        unique_consumers: Set[str] = set()

        if node.node_type == NodeType.CONSUMER_POINT:
            unique_consumers.add(node_id)

        # Add children's consumers
        children_ids = index.get_children(node_id)
        for child_id in children_ids:
            if child_id in consumers_in_subtree:
                unique_consumers.update(consumers_in_subtree[child_id])

        consumers_in_subtree[node_id] = unique_consumers

        # Calculate capacity ONLY for non-consumers
        if node.node_type != NodeType.CONSUMER_POINT:
            count = len(unique_consumers)
            # Factor 1.5x for emergency buffer
            new_capacity = max(1.0, float(count) * 1.5)
            node.capacity = new_capacity
