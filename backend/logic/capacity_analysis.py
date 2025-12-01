from __future__ import annotations
from typing import Dict, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex

def initialize_capacities(graph: PowerGridGraph, index: BPlusIndex) -> None:
    """
    Inicializa a capacidade dos nós (Subestações e Usinas) baseado na topologia.
    Regra: Node.capacity = 8.0 * (numero_de_filhos_diretos + 1)

    NOTA: Nós do tipo CONSUMER_POINT são ignorados nesta função, pois sua capacidade
    é definida por regras específicas de negócio (13kW/25kW) com base nos dispositivos instalados.
    """

    # Iteramos sobre todos os nós no índice
    # A classe BPlusIndex expõe _parent que contém todas as chaves (nós registrados).
    # Vamos acessar as chaves de _parent via um método auxiliar se possível, ou iterar sobre as chaves.
    # Como _parent é interno, o correto seria usar um método público.
    # O método iter_preorder() retorna todos os nós da árvore.

    all_nodes = index.iter_preorder()

    for node_id in all_nodes:
        node = graph.get_node(node_id)
        if node is None:
            continue

        # Pula consumidores (já definidos na inicialização de dispositivos)
        if node.node_type == NodeType.CONSUMER_POINT:
            continue

        # Obtém número de filhos diretos
        children_ids = list(index.get_children(node_id))
        num_children = len(children_ids)

        # Aplica a nova regra: 8 * (filhos + 1)
        new_capacity = 8.0 * (num_children + 1)

        node.capacity = new_capacity
