
from config import SimulationConfig
from core.graph_core import PowerGridGraph
from planning.node_generation import generate_nodes
from planning.transmission_backbone import build_transmission_backbone
from planning.mv_network import build_mv_network
from planning.lv_network import build_lv_network
from io_utils.graph_export import export_graph_to_files

def generate_graph(config: SimulationConfig) -> PowerGridGraph:
    """
    Gera o grafo completo da rede elétrica com base na configuração.
    """
    graph = PowerGridGraph()

    # 1. Gera nós e clusters
    clusters = generate_nodes(config, graph)

    # 2. Constrói redes
    build_transmission_backbone(config, graph)
    build_mv_network(config, graph, clusters)
    build_lv_network(config, graph, clusters)

    return graph

def generate_default_graph(nodes_path: str, edges_path: str) -> None:
    """
    Gera o grafo com configuração padrão e salva nos caminhos especificados.
    """
    print(f"Gerando grafo de rede elétrica em {nodes_path} e {edges_path}...")
    config = SimulationConfig()
    graph = generate_graph(config)
    export_graph_to_files(graph, nodes_path, edges_path)
    print("Grafo gerado com sucesso.")
