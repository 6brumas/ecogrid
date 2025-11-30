
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex
from logic.capacity_analysis import initialize_capacities
from logic.load_aggregation import update_load_after_device_change
from physical.device_model import IoTDevice, DeviceType

def test_capacity_analysis():
    graph = PowerGridGraph()
    index = BPlusIndex()

    # Create hierarchy: G -> TS -> DS -> C1, C2
    g = Node(id="G", node_type=NodeType.GENERATION_PLANT, position_x=0, position_y=0, nominal_voltage=100)
    ts = Node(id="TS", node_type=NodeType.TRANSMISSION_SUBSTATION, position_x=0, position_y=0, nominal_voltage=100)
    ds = Node(id="DS", node_type=NodeType.DISTRIBUTION_SUBSTATION, position_x=0, position_y=0, nominal_voltage=100)
    c1 = Node(id="C1", node_type=NodeType.CONSUMER_POINT, position_x=0, position_y=0, nominal_voltage=100)
    c2 = Node(id="C2", node_type=NodeType.CONSUMER_POINT, position_x=0, position_y=0, nominal_voltage=100)

    graph.add_node(g)
    graph.add_node(ts)
    graph.add_node(ds)
    graph.add_node(c1)
    graph.add_node(c2)

    # Build hierarchy manually
    index.add_root("G")
    index.set_parent("TS", "G")
    index.set_parent("DS", "TS")
    index.set_parent("C1", "DS")
    index.set_parent("C2", "DS")

    initialize_capacities(graph, index)

    print(f"C1 Capacity: {c1.capacity}")
    assert c1.capacity == 1.0
    assert c2.capacity == 1.0
    assert ds.capacity == 2.0
    assert ts.capacity == 2.0
    assert g.capacity == 2.0

def test_load_propagation():
    graph = PowerGridGraph()
    index = BPlusIndex()

    # Hierarchy: G -> DS -> C
    g = Node(id="G", node_type=NodeType.GENERATION_PLANT, position_x=0, position_y=0, nominal_voltage=100, capacity=100)
    ds = Node(id="DS", node_type=NodeType.DISTRIBUTION_SUBSTATION, position_x=0, position_y=0, nominal_voltage=100, capacity=100)
    c = Node(id="C", node_type=NodeType.CONSUMER_POINT, position_x=0, position_y=0, nominal_voltage=100, capacity=100)

    graph.add_node(g)
    graph.add_node(ds)
    graph.add_node(c)

    index.add_root("G")
    index.set_parent("DS", "G")
    index.set_parent("C", "DS")

    # Add device to C
    device = IoTDevice(id="D1", name="Dev", device_type=DeviceType.GENERIC, avg_power=10.0, current_power=5.0)
    node_devices = {"C": [device]}

    # Update load
    update_load_after_device_change("C", node_devices, graph, index)

    print(f"C Load: {c.current_load}")
    print(f"DS Load: {ds.current_load}")
    print(f"G Load: {g.current_load}")

    assert c.current_load == 5.0
    assert ds.current_load == 5.0
    assert g.current_load == 5.0

    # Update device power again
    device.current_power = 10.0
    update_load_after_device_change("C", node_devices, graph, index)

    assert c.current_load == 10.0
    assert ds.current_load == 10.0
    assert g.current_load == 10.0

if __name__ == "__main__":
    try:
        test_capacity_analysis()
        print("Capacity Analysis Passed")
        test_load_propagation()
        print("Load Propagation Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
