from __future__ import annotations

from typing import Dict, List, MutableMapping, Sequence, Optional, Union
from pathlib import Path
import os
import time

from core.graph_core import PowerGridGraph
from core.models import Node, Edge, NodeType
from logic.bplus_index import BPlusIndex
from logic.logical_graph_service import LogicalGraphService
from physical.device_model import DeviceType, IoTDevice
from physical.device_simulation import (
    DeviceSimulationState,
    build_device_simulation_state,
    update_devices_and_nodes_loads
)

# Import modules for initialization
from io_utils.loader import load_graph_from_files
from logic.graph_initialization import build_logical_state
from logic.capacity_analysis import initialize_capacities
from grid_generation import generate_grid_if_needed
from config import SimulationConfig

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
        config_or_path: Union[SimulationConfig, str] = "out/nodes",
        edges_path: str = "out/edges",
    ) -> None:
        """
        Inicializa o backend. Pode receber:
        1. Paths para arquivos existentes (modo produção/default).
        2. Um objeto SimulationConfig (modo teste/geração dinâmica).

        Se um SimulationConfig for passado, o grafo é gerado em memória
        (ou em arquivos temporários) antes de carregar.
        """

        # Check if NOT a string, assuming it is a config object.
        # This avoids issues with isinstance(obj, Class) if Class is imported from different module paths.
        if not isinstance(config_or_path, str):
            # Modo Geração Dinâmica (Testes ou Nova Simulação)
            cfg = config_or_path
            # Gera os arquivos usando o gerador
            generate_grid_if_needed(cfg, force_regenerate=True)

            # Ajuste de path para testes rodando da raiz
            # O gerador salva em "backend/out" se executado da raiz, ou "out" se executado do backend

            # Vamos detectar onde foi salvo
            possible_dirs = ["backend/out", "out"]
            found = False
            for d in possible_dirs:
                if os.path.exists(os.path.join(d, "nodes")):
                    self._nodes_path = os.path.join(d, "nodes")
                    self._edges_path = os.path.join(d, "edges")
                    found = True
                    break

            if not found:
                # Fallback para o default se não encontrado (provavelmente falhará)
                self._nodes_path = "out/nodes"
                self._edges_path = "out/edges"

        else:
            # Modo Arquivo Existente
            self._nodes_path = config_or_path
            self._edges_path = edges_path

        # 1. Carrega grafo físico
        # Verifica se o arquivo existe antes de tentar abrir
        if isinstance(self._nodes_path, str):
            if not os.path.exists(self._nodes_path):
                 # Try appending backend/ prefix if running from root
                 if os.path.exists(os.path.join("backend", self._nodes_path)):
                     self._nodes_path = os.path.join("backend", self._nodes_path)
                     self._edges_path = os.path.join("backend", self._edges_path)

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
        # Atualiza o estado da simulação (ruído) antes de tirar o snapshot
        update_devices_and_nodes_loads(
            graph=self.graph,
            sim_state=self.device_state,
            t_seconds=time.time(),
            service=self.service
        )

        # Tenta reconectar nós sem fornecedor antes de retornar
        self.service.retry_unsupplied_routing()

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
        result = api_impl.api_set_node_capacity(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            new_capacity=new_capacity,
        )
        # Verifica se a mudança causou sobrecarga e trata
        self.service.handle_overload(node_id)
        # O snapshot retornado pela api_impl não incluirá as mudanças de shedding
        # se elas ocorrerem DEPOIS. Deveríamos retornar um novo snapshot?
        # Sim, o handle_overload altera a rede.
        # Mas api_set_node_capacity já retornou o dict.
        # Eu devo chamar get_tree_snapshot novamente ou atualizar?
        # O ideal é que api_set_node_capacity chamasse handle_overload.
        # Mas api_impl é funcional e service é stateful.
        # Eu posso chamar get_tree_snapshot() aqui e retornar.
        return self.get_tree_snapshot()

    def force_overload(
        self,
        node_id: str,
        overload_percentage: float,
    ) -> Dict[str, List[Dict]]:
        """
        Força sobrecarga em um nó reduzindo sua capacidade.
        """
        api_impl.api_force_overload(
            graph=self.graph,
            index=self.index,
            service=self.service,
            sim_state=self.device_state,
            node_id=node_id,
            overload_percentage=overload_percentage,
        )

        # Trata a sobrecarga (shedding)
        self.service.handle_overload(node_id)

        return self.get_tree_snapshot()

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
