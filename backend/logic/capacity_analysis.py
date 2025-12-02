from __future__ import annotations
from typing import Dict, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex

def initialize_capacities(graph: PowerGridGraph, index: BPlusIndex) -> None:
    """
    Inicializa a capacidade dos nós (Subestações e Usinas) baseado na topologia.
    Regra: Node.capacity = 13 * max(sum(child_capacities) + child_count, (total_consumers / clusters) + 1)

    NOTA: Nós do tipo CONSUMER_POINT são ignorados nesta função e devem ter
    capacidade NULA (None).
    """

    # 1. Calculate global metrics
    total_consumers = 0
    roots = index.get_roots()

    # Count only Generation Plants as valid roots for clusters?
    # Or any root? Usually clusters implies distinct power sources.
    # Let's count generation plants as clusters.

    num_clusters = 0
    for node_id in graph.nodes:
        node = graph.get_node(node_id)
        if node and node.node_type == NodeType.CONSUMER_POINT:
            total_consumers += 1
        if node and node.node_type == NodeType.GENERATION_PLANT:
             num_clusters += 1

    # Fallback if no clusters (should not happen in valid graph, but safe to handle)
    if num_clusters == 0:
        num_clusters = 1

    avg_consumers_per_cluster = total_consumers / num_clusters

    # Bottom-up traversal is required because capacity depends on children's capacity.
    # index.iter_preorder() is Top-Down.
    # We need to reverse it to process leaves first (consumers) then up to root.

    nodes_ordered = list(index.iter_preorder())
    nodes_bottom_up = reversed(nodes_ordered)

    for node_id in nodes_bottom_up:
        node = graph.get_node(node_id)
        if node is None:
            continue

        # Garante que consumidores não tenham capacidade definida
        if node.node_type == NodeType.CONSUMER_POINT:
            node.capacity = None
            continue

        children_ids = index.get_children(node_id)
        num_children = len(children_ids)

        sum_children_capacity = 0.0
        for child_id in children_ids:
            child = graph.get_node(child_id)
            if child and child.capacity is not None:
                sum_children_capacity += child.capacity

        # Nova regra: 13 * max(sum(child_capacities) + child_count, (total_consumers / clusters) + 1)
        # Note: sum_children_capacity is the sum of capacities of children.
        # num_children is child_count.

        base_term = sum_children_capacity + num_children
        cluster_term = avg_consumers_per_cluster + 1

        new_capacity = 13.0 * max(base_term, cluster_term)

        node.capacity = new_capacity
