from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import json
import uuid

# importa todas as funções que serão consumidas do backend
from backend.api.logical_backend_api import (
    api_get_tree_snapshot,
    api_add_node_with_routing,
    api_remove_node,
    api_change_parent_with_routing,
    api_force_change_parent,
    api_set_node_capacity,
    api_set_device_average_load,
    api_force_overload,
)

from backend.api.backend_facade import PowerGridBackend
from backend.core.models import Node, Edge, NodeType, EdgeType

# Initialize BackendFacade
# This handles loading graph from files and setting up index/service
backend = PowerGridBackend(nodes_path="backend/out/nodes", edges_path="backend/out/edges")

# Expose internal components for compatibility with existing API calls
graph = backend.graph
index = backend.index
service = backend.service

# configuração do FastAPI
app = FastAPI()

# configuração dos diretórios de arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def sim_sobrecarga(id_no: str):
    """Simula uma sobrecarga em um nó."""
    # Simula sobrecarga de 20%
    return api_force_overload(graph, index, service, id_no, 0.2)

def sim_falha_no(id_no: str):
    """Simula falha em um nó removendo-o do grafo."""
    return api_remove_node(graph, index, service, id_no, remove_from_graph=True)

def sim_pico_consumo(id_no: str):
    """Simula pico de consumo.

    Como não temos acesso fácil aos devices para aumentar a carga real,
    vamos simular um pico forçando uma sobrecarga maior (50%).
    Isso deve disparar alertas de overload.
    """
    return api_force_overload(graph, index, service, id_no, 0.5)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    '''função que renderiza o template HTML principal'''
    # adicionando a URL base no contexto para uso no JS
    base_url = f"http://{request.url.netloc}"
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "base_url": base_url}
    )

@app.post("/tree")
async def get_tree():
    """função que retorna a árvore completa inicial."""
    arvore = api_get_tree_snapshot(graph, index, service)
    return JSONResponse(arvore)

# rota para o WebSocket de simulação
@app.websocket("/simulation")
async def simulation_socket(ws: WebSocket):
    """função que mantém streaming da árvore simulada até o cliente encerrar."""
    await ws.accept()

    try:
        # recebe parâmetros iniciais
        data = await ws.receive_text()
        data = json.loads(data)

        id_no = data.get("id")
        tipo = data.get("simulation_type")

        if not id_no or not tipo:
            await ws.send_text(json.dumps({"error": "Parâmetros insuficientes"}))
            return

        # loop que envia a nova árvore a cada segundo
        while True:
            if tipo == "overload":
                arvore = sim_sobrecarga(id_no)

            elif tipo == "node-failure":
                arvore = sim_falha_no(id_no)

            elif tipo == "consumption-peak":
                arvore = sim_pico_consumo(id_no)

            else:
                arvore = {"error": "Tipo de simulação inválido"}
            
            await ws.send_json(arvore)
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("Simulação encerrada — WebSocket desconectado.")
    except Exception as e:
        print(f"Erro na simulação: {e}")
        try:
            await ws.send_json({"error": str(e)})
        except:
            pass
    finally:
        # garante que a conexão será fechada se houver um erro antes do loop
        if ws.client_state.name == 'CONNECTED':
             await ws.close()

# rota para alterar atributos de um nó específico
@app.post("/change-node")
async def change_node(data: dict):
    """função que altera atributos de um nó específico."""
    id_no = data.get("id")
    if not id_no:
        return JSONResponse({"error": "ID do nó não fornecido"}, status_code=400)

    nova_arvore = None

    if "capacity_kw" in data:
        nova_arvore = api_set_node_capacity(graph, index, service, id_no, data["capacity_kw"])

    # elif "current_load_kw" in data:
    #     nova_arvore = alterar_carga_no(id_no, data["current_load_kw"])

    elif data.get("add_node") is True:
        # Logic to add a new node connected to id_no (parent)
        # We create a new CONSUMER_POINT by default
        new_node_id = str(uuid.uuid4())[:8]
        # We need a position. Let's take parent position and offset slightly.
        parent_node = graph.get_node(id_no)
        pos_x = 0.0
        pos_y = 0.0
        if parent_node:
            pos_x = parent_node.position_x + 10 # arbitrary offset
            pos_y = parent_node.position_y + 10

        new_node = Node(
            id=new_node_id,
            node_type=NodeType.CONSUMER_POINT,
            position_x=pos_x,
            position_y=pos_y,
            nominal_voltage=127.0, # default
            capacity=50.0, # default
            current_load=0.0
        )

        # Create edge connecting parent to new node
        new_edge = Edge(
            id=f"edge_{id_no}_{new_node_id}",
            edge_type=EdgeType.LV_DISTRIBUTION_SEGMENT, # Assuming LV for consumer
            from_node_id=id_no,
            to_node_id=new_node_id,
            length=10.0 # arbitrary
        )

        nova_arvore = api_add_node_with_routing(graph, index, service, new_node, [new_edge])

    elif data.get("delete_node") is True:
        nova_arvore = api_remove_node(graph, index, service, id_no)

    elif data.get("change_parent_routing") is True:
        nova_arvore = api_change_parent_with_routing(graph, index, service, id_no)

    elif "new_parent" in data:
        nova_arvore = api_force_change_parent(graph, index, service, id_no, data["new_parent"])

    else:
        return JSONResponse({"error": "Nenhuma ação válida fornecida"}, status_code=400)

    if nova_arvore and "error" in nova_arvore:
         return JSONResponse(nova_arvore, status_code=400)

    return JSONResponse(nova_arvore)
