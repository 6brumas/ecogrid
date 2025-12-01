from __future__ import annotations
from typing import Dict, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex

def initialize_capacities(graph: PowerGridGraph, index: BPlusIndex) -> None:
    """
    Inicializa a capacidade dos nós (Subestações e Usinas) baseado na topologia.
    Regra: Node.capacity = 13.0 * (numero_de_filhos_diretos + 1)

    NOTA: Nós do tipo CONSUMER_POINT são ignorados nesta função e devem ter
    capacidade NULA (None), pois o conceito de capacidade foi removido para consumidores.
    """

    all_nodes = index.iter_preorder()

    for node_id in all_nodes:
        node = graph.get_node(node_id)
        if node is None:
            continue

        # Garante que consumidores não tenham capacidade definida
        if node.node_type == NodeType.CONSUMER_POINT:
            node.capacity = None
            continue

        # Obtém número de filhos diretos
        children_ids = list(index.get_children(node_id))
        num_children = len(children_ids)

        # Aplica a nova regra: 13 * (filhos + 1)
        new_capacity = 13.0 * (num_children + 1)

        node.capacity = new_capacity
