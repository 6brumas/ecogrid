from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex
from physical.device_model import IoTDevice


def _compute_status(node: Node, unsupplied_ids: Set[str]) -> str:
    """
    Calcula o status lógico de um nó para exibição na árvore de UI.
    """
    if node.node_type == NodeType.CONSUMER_POINT and node.id in unsupplied_ids:
        return "UNSUPPLIED"

    if node.capacity is None or node.current_load is None:
        return "NORMAL"

    try:
        capacity = float(node.capacity)
        load = float(node.current_load)
        if capacity <= 0.0:
            return "NORMAL"
        ratio = load / capacity
    except (TypeError, ValueError, ZeroDivisionError):
        return "NORMAL"

    if ratio < 0.8:
        return "NORMAL"
    if ratio <= 1.0:
        return "WARNING"
    return "OVERLOADED"


def _translate_node_type(node_type: NodeType) -> str:
    """
    Traduz o tipo de nó para Português do Brasil.
    GENERATION_PLANT -> "Usina Geradora"
    TRANSMISSION_SUBSTATION -> "Subestação de Transmissão"
    DISTRIBUTION_SUBSTATION -> "Subestação de Distribuição"
    CONSUMER_POINT -> "Consumidor"
    """
    mapping = {
        NodeType.GENERATION_PLANT: "Usina Geradora",
        NodeType.TRANSMISSION_SUBSTATION: "Subestação de Transmissão",
        NodeType.DISTRIBUTION_SUBSTATION: "Subestação de Distribuição",
        NodeType.CONSUMER_POINT: "Consumidor",
    }
    return mapping.get(node_type, node_type.name)


def _determine_network_type(capacity: Optional[float]) -> str:
    """
    Determina o tipo de rede com base na capacidade (regra de negócio).
    Se capacidade <= 13.0 -> "Monofásica"
    Se capacidade > 13.0 -> "Trifásica"
    Caso None -> "Desconhecido" (ou padrão)
    """
    if capacity is None:
        return "Desconhecido"

    # Tolerância de ponto flutuante, considerando 13.0 exato
    if capacity <= 13.001:
        return "Monofásica"
    return "Trifásica"


def _round_val(val: Optional[float]) -> Optional[float]:
    """Arredonda para 3 casas decimais."""
    if val is None:
        return None
    return round(val, 3)


def _build_tree_entry(
    node: Node,
    parent_id: Optional[str],
    unsupplied_ids: Set[str],
) -> Dict:
    """
    Constrói a entrada plana (flat) de um nó na árvore de UI.
    Aplica traduções e arredondamentos.
    """
    # Tradução do tipo de nó
    node_type_translated = _translate_node_type(node.node_type)

    # Determinação do tipo de rede (apenas se fizer sentido, mas a regra diz para injetar)
    # A regra de negócio se aplica principalmente a Consumidores, mas injetamos em todos se tiver capacidade
    network_type = _determine_network_type(node.capacity)

    return {
        "id": node.id,
        "parent_id": parent_id,
        "node_type": node_type_translated,
        "position_x": _round_val(node.position_x),
        "position_y": _round_val(node.position_y),
        "cluster_id": node.cluster_id,
        "nominal_voltage": _round_val(node.nominal_voltage),
        "capacity": _round_val(node.capacity),
        "current_load": _round_val(node.current_load),
        "status": _compute_status(node, unsupplied_ids),
        "network_type": network_type,
    }


def _serialize_devices(
    devices_by_node: Dict[str, List[IoTDevice]],
) -> Dict[str, List[Dict]]:
    """
    Serializa os dispositivos IoT para formato JSON.
    """
    serialized: Dict[str, List[Dict]] = {}
    for node_id, devices in devices_by_node.items():
        if not devices:
            continue

        serialized[node_id] = []
        for dev in devices:
            serialized[node_id].append({
                "id": dev.id,
                "name": dev.name,
                "device_type": dev.device_type.name,
                "avg_power": _round_val(dev.avg_power),
                "current_power": _round_val(dev.current_power),
            })
    return serialized


def build_full_ui_snapshot(
    graph: PowerGridGraph,
    index: BPlusIndex,
    unsupplied_ids: Set[str],
    devices_by_node: Optional[Dict[str, List[IoTDevice]]] = None,
    logs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Gera o snapshot completo da árvore lógica para o front-end.
    """
    tree_entries: List[Dict] = []

    # Percorre a árvore lógica em pré-ordem usando o índice B+.
    for node_id in index.iter_preorder():
        node: Optional[Node] = graph.get_node(node_id)
        if node is None:
            continue

        parent_id = index.get_parent(node_id)
        entry = _build_tree_entry(
            node=node,
            parent_id=parent_id,
            unsupplied_ids=unsupplied_ids,
        )
        tree_entries.append(entry)

    devices_data = {}
    if devices_by_node:
        devices_data = _serialize_devices(devices_by_node)

    return {
        "tree": tree_entries,
        "devices": devices_data,
        "logs": logs or [],
    }


__all__ = [
    "build_full_ui_snapshot",
]
