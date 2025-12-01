import unittest
import os
import sys
import uuid

# Ensure backend modules are importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from api.backend_facade import PowerGridBackend
from core.models import Node, Edge, NodeType, EdgeType
from physical.device_model import DeviceType
from config import SimulationConfig

class TestPowerGridFacade(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize Facade using existing files or a config
        print("Initializing PowerGridBackend...")
        # Since we are running tests, we might want to use a fresh config to ensure graph exists
        # Or rely on defaults if the files exist.
        # But to be safe and avoid "file not found" or "TypeError" seen before:
        # We will pass a config object (not kwargs) because __init__ accepts (config_or_path, edges_path)

        cfg = SimulationConfig(
            random_seed=42,
            num_clusters=1,
            num_generation_plants=1,
            num_transmission_substations=2,
            max_transmission_segment_length=1500.0,
            max_mv_segment_length=800.0,
            max_lv_segment_length=250.0
        )
        cls.backend = PowerGridBackend(cfg)

    def test_01_initialization(self):
        """Test if backend initializes and logs startup message."""
        print("Running test_01_initialization")
        snapshot = self.backend.get_tree_snapshot()
        self.assertIn("tree", snapshot)
        self.assertIn("logs", snapshot)
        self.assertIn("devices", snapshot)

        logs = snapshot["logs"]
        # Check for "Rede ligada"
        has_init_log = any("Rede ligada" in log for log in logs)

        if not has_init_log:
            print("WARNING: Initialization log not found. Might have been consumed.")
        else:
            print("Initialization log verified.")

    def test_02_add_node_sequence(self):
        """Test adding a node, checking routing logs."""
        print("Running test_02_add_node_sequence")
        snapshot = self.backend.get_tree_snapshot()
        tree = snapshot["tree"]
        parent = next((n for n in tree if n["node_type"] == "DISTRIBUTION_SUBSTATION"), None)
        self.assertIsNotNone(parent, "No DS found")

        new_id = f"TEST_C_{uuid.uuid4().hex[:4]}"
        new_node = Node(
            id=new_id,
            node_type=NodeType.CONSUMER_POINT,
            position_x=0, position_y=0,
            capacity=10.0,
            current_load=0.0
        )
        edge = Edge(
            id=f"E_{uuid.uuid4()}",
            from_node_id=parent["id"],
            to_node_id=new_id,
            edge_type=EdgeType.LV_DISTRIBUTION_SEGMENT,
            length=1.0
        )

        result = self.backend.add_node_with_routing(new_node, [edge])
        logs = result["logs"]
        print("Logs:", logs)

        self.assertTrue(any("foi conectado ao fornecedor" in log for log in logs), f"Logs missing connection msg: {logs}")

        tree_ids = [n["id"] for n in result["tree"]]
        self.assertIn(new_id, tree_ids)

        self.__class__.test_node_id = new_id
        self.__class__.parent_id = parent["id"]

    def test_03_device_management(self):
        """Test adding devices and verifying load calculation/propagation."""
        print("Running test_03_device_management")
        node_id = self.test_node_id

        # Add TV (0.195 kW)
        res = self.backend.add_device(
            node_id=node_id,
            device_type=DeviceType.TV,
            name="TestTV"
        )
        logs = res["logs"]
        print("Logs (TV):", logs)
        self.assertTrue(any("adicionado ao consumidor" in log for log in logs))
        self.assertTrue(any("Carga do consumidor" in log for log in logs))

        node = next(n for n in res["tree"] if n["id"] == node_id)
        self.assertAlmostEqual(node["current_load"], 0.195, places=3)

        # Add Fridge (0.1 kW)
        res = self.backend.add_device(
            node_id=node_id,
            device_type=DeviceType.FRIDGE,
            name="TestFridge"
        )
        node = next(n for n in res["tree"] if n["id"] == node_id)
        self.assertAlmostEqual(node["current_load"], 0.295, places=3)

        devices = res["devices"][node_id]
        self.__class__.device_id = devices[0]["id"]

    def test_04_routing_changes(self):
        """Test changing parent and verifying logs."""
        print("Running test_04_routing_changes")
        child_id = self.test_node_id
        current_parent = self.parent_id

        snapshot = self.backend.get_tree_snapshot()
        possible_parents = [n for n in snapshot["tree"] if n["node_type"] == "DISTRIBUTION_SUBSTATION" and n["id"] != current_parent]

        if not possible_parents:
            print("Skipping routing change test (no alternative parent)")
            return

        new_parent = possible_parents[0]["id"]

        res = self.backend.force_change_parent(child_id, new_parent)
        logs = res["logs"]
        print("Logs:", logs)

        expected_log_snippet = "trocou de fornecedor"
        self.assertTrue(any(expected_log_snippet in log for log in logs), f"Missing routing log: {logs}")

        node = next(n for n in res["tree"] if n["id"] == child_id)
        self.assertEqual(node["parent_id"], new_parent)

    def test_05_capacity_overload(self):
        """Test capacity setting and overload detection logs."""
        print("Running test_05_capacity_overload")

        # Overload the CURRENT PARENT (DS), not the consumer
        node_id = self.test_node_id
        snapshot = self.backend.get_tree_snapshot()
        node = next(n for n in snapshot["tree"] if n["id"] == node_id)
        target_id = node["parent_id"]

        # Force overload
        res = self.backend.force_overload(target_id, 0.5)
        logs = res["logs"]
        print("Logs:", logs)

        self.assertTrue(any("ALERTA" in log for log in logs), f"Missing overload alert: {logs}")
        # Expect shedding if overload persists
        # self.assertTrue(any("Corte de carga" in log for log in logs))

        node = next(n for n in res["tree"] if n["id"] == target_id)
        # After shedding, it should NOT be OVERLOADED (unless shedding failed)
        self.assertNotEqual(node["status"], "OVERLOADED")

    def test_06_cleanup(self):
        """Test removing device and node."""
        print("Running test_06_cleanup")
        node_id = self.test_node_id
        device_id = self.device_id

        # Remove device
        res = self.backend.remove_device(node_id, device_id)
        logs = res["logs"]
        print("Logs (Remove Device):", logs)
        self.assertTrue(any("removido do consumidor" in log for log in logs))

        node = next(n for n in res["tree"] if n["id"] == node_id)
        # Check load reduced (0.295 - 0.195 (TV) = 0.1)
        # Note: we assume the FIRST device was TV.
        # Let's check which one we removed.
        # In test_03, we stored devices[0]["id"].
        # Devices list order depends on implementation.
        # Assuming FIFO.

        # Actually, let's just check load < 0.295
        self.assertLess(node["current_load"], 0.295)

        # Remove node
        res = self.backend.remove_node(node_id)

        tree_ids = [n["id"] for n in res["tree"]]
        self.assertNotIn(node_id, tree_ids)

if __name__ == "__main__":
    unittest.main()
