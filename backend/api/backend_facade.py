from __future__ import annotations

from typing import Dict, List, MutableMapping, Sequence, Optional
from pathlib import Path

from core.graph_core import PowerGridGraph
from core.models import Node, Edge, NodeType
from logic.bplus_index import BPlusIndex
from logic.logical_graph_service import LogicalGraphService
from physical.device_model import DeviceType, IoTDevice
from physical.device_simulation import DeviceSimulationState, build_device_simulation_state

# Import modules for initialization
from io_utils.loader import load_graph_from_files
from logic.graph_initialization import build_logical_state
from logic.capacity_analysis import initialize_capacities

# Import existing functional API to delegate calls
from api import logical_backend_api as api_impl


class PowerGridBackend:
    """
    Fachada (Facade) Stateful para o backend de simulação de rede elétrica.

    Esta classe encapsula o estado da aplicação (grafo físico, índice lógico,
    serviço de domínio) e oferece uma interface simplificada para consumidores
    (CLI, Web API, Testes), eliminando a necessidade de microgerenciamento
    de dependências e inicialização.

    Responsabilidades:
        - Carregar e persistir o estado do grafo (`PowerGridGraph`).
        - Manter a integridade do índice lógico (`BPlusIndex`).
        - Orquestrar operações de domínio via `LogicalGraphService`.
        - Prover métodos de alto nível que ocultam a complexidade interna.
    """

    def __init__(
        self,
        nodes_path: str = "out/nodes",
        edges_path: str = "out/edges",
    ) -> None:
        """
        Inicializa o backend, carregando dados e construindo o estado lógico.

        O processo de inicialização inclui:
            1. Leitura dos arquivos CSV de nós e arestas.
            2. Construção do grafo físico.
            3. Hidratação da árvore lógica (B+) a partir da topologia.

        Parâmetros:
            nodes_path: Caminho para o arquivo CSV de nós.
            edges_path: Caminho para o arquivo CSV de arestas.
        """
        self._nodes_path = nodes_path
        self._edges_path = edges_path

        # 1. Carrega grafo físico
        self.graph: PowerGridGraph = load_graph_from_files(
            nodes_path=self._nodes_path,
            edges_path=self._edges_path,
        )

        # 2. Constrói estado lógico (inclui hidratação via service.hydrate_from_physical)
        # build_logical_state já retorna (graph, index, service) populados.
        _, self.index, self.service = build_logical_state(self.graph)

        # 2.5. Inicializa capacidades baseado na topologia
        initialize_capacities(self.graph, self.index)

        # 3. Inicializa dispositivos
        self._init_default_devices()

    def _init_default_devices(self) -> None:
        """
        Inicializa o estado de simulação de dispositivos com valores padrão
        para todos os consumidores do grafo.
        """
        node_device_types = {}
        for node in self.graph.nodes.values():
            if node.node_type == NodeType.CONSUMER_POINT:
                # Default configuration: 1 TV, 1 Fridge
                node_device_types[node.id] = [DeviceType.TV, DeviceType.FRIDGE]

        self.device_state = build_device_simulation_state(
            graph=self.graph,
            node_device_types=node_device_types
        )

        # Propaga a carga inicial dos dispositivos para a rede
        for consumer_id in node_device_types.keys():
             self.service.update_load_after_device_change(
                consumer_id=consumer_id,
                node_devices=self.device_state.devices_by_node
             )

    # ------------------------------------------------------------------
    # Métodos de Leitura / Snapshot
    # ------------------------------------------------------------------

    def get_tree_snapshot(self) -> Dict[str, List[Dict]]:
        """
        Retorna o snapshot atual da árvore lógica para UI.
        Delegado para `logical_backend_api.api_get_tree_snapshot`.
        """
        return api_impl.api_get_tree_snapshot(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
        )

    # ------------------------------------------------------------------
    # Métodos de Modificação Estrutural
    # ------------------------------------------------------------------

    def add_node_with_routing(
        self,
        node: Node,
        edges: Sequence[Edge],
    ) -> Dict[str, List[Dict]]:
        """
        Adiciona um nó e conecta-o logicamente via roteamento.
        """
        return api_impl.api_add_node_with_routing(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node=node,
            edges=edges,
        )

    def remove_node(
        self,
        node_id: str,
        remove_from_graph: bool = True,
    ) -> Dict[str, List[Dict]]:
        """
        Remove um nó da lógica (e opcionalmente do físico).
        """
        return api_impl.api_remove_node(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            remove_from_graph=remove_from_graph,
        )

    def change_parent_with_routing(
        self,
        node_id: str,
    ) -> Dict[str, List[Dict]]:
        """
        Recalcula o pai lógico de um nó via roteamento.
        """
        return api_impl.api_change_parent_with_routing(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
        )

    def force_change_parent(
        self,
        node_id: str,
        forced_parent_id: str,
    ) -> Dict[str, List[Dict]]:
        """
        Força a troca de pai para um nó específico.
        """
        return api_impl.api_force_change_parent(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            forced_parent_id=forced_parent_id,
        )

    # ------------------------------------------------------------------
    # Métodos de Ajuste de Parâmetros e Carga
    # ------------------------------------------------------------------

    def set_node_capacity(
        self,
        node_id: str,
        new_capacity: float,
    ) -> Dict[str, List[Dict]]:
        """
        Define a capacidade máxima de um nó.
        """
        return api_impl.api_set_node_capacity(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            new_capacity=new_capacity,
        )

    def force_overload(
        self,
        node_id: str,
        overload_percentage: float,
    ) -> Dict[str, List[Dict]]:
        """
        Força sobrecarga em um nó reduzindo sua capacidade.
        """
        return api_impl.api_force_overload(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            overload_percentage=overload_percentage,
        )

    def set_device_average_load(
        self,
        consumer_id: str,
        device_id: str,
        new_avg_power: float,
        adjust_current_to_average: bool = True,
    ) -> Dict[str, List[Dict]]:
        """
        Atualiza a potência média de um dispositivo IoT.
        """
        return api_impl.api_set_device_average_load(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            consumer_id=consumer_id,
            device_id=device_id,
            new_avg_power=new_avg_power,
            adjust_current_to_average=adjust_current_to_average,
        )

    def add_device(
        self,
        node_id: str,
        device_type: DeviceType,
        name: str = "Novo Dispositivo",
        avg_power: Optional[float] = None,
    ) -> Dict[str, List[Dict]]:
        """
        Adiciona um dispositivo a um nó consumidor.
        """
        return api_impl.api_add_device(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            device_type=device_type,
            name=name,
            avg_power=avg_power,
        )

    def remove_device(
        self,
        node_id: str,
        device_id: str,
    ) -> Dict[str, List[Dict]]:
        """
        Remove um dispositivo de um nó consumidor.
        """
        return api_impl.api_remove_device(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            device_id=device_id,
        )
