import unittest
import sys
import os
import random

# Ensure backend modules are importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from physical.device_model import DeviceType
from physical.device_catalog import get_device_template
from api.backend_facade import PowerGridBackend
from logic.ui_tree_snapshot import _translate_node_type, _determine_network_type, _round_val
from core.models import Node, NodeType
from config import SimulationConfig

class TestNewRequirements(unittest.TestCase):

    def test_catalog_expansion(self):
        """Verify that all new device types are present and have correct power."""
        # Test a few samples
        tv = get_device_template(DeviceType.TV)
        self.assertAlmostEqual(tv.avg_power, 0.095)
        self.assertEqual(tv.default_name, "TV")

        shower = get_device_template(DeviceType.SHOWER)
        self.assertAlmostEqual(shower.avg_power, 6.500)
        self.assertEqual(shower.default_name, "Chuveiro Elétrico")

        generic = get_device_template(DeviceType.GENERIC)
        self.assertAlmostEqual(generic.avg_power, 0.100)

    def test_initialization_rules(self):
        """Verify random device population and capacity sizing rules."""
        # Setup a minimal config
        cfg = SimulationConfig(
            random_seed=42,
            num_clusters=1,
            num_generation_plants=1,
            num_transmission_substations=1,
            max_transmission_segment_length=1500.0,
            max_mv_segment_length=800.0,
            max_lv_segment_length=250.0
        )
        # We need to ensure we have consumers. Default config usually creates some.
        # But random seed 42 should be deterministic.
        backend = PowerGridBackend(cfg)

        consumers = [n for n in backend.graph.nodes.values() if n.node_type == NodeType.CONSUMER_POINT]
        self.assertTrue(len(consumers) > 0, "No consumers generated")

        for node in consumers:
            # Check devices count
            devices = backend.device_state.devices_by_node.get(node.id, [])
            self.assertTrue(3 <= len(devices) <= 10, f"Consumer {node.id} has {len(devices)} devices, expected 3-10")

            # Check capacity rule
            sum_load = sum([d.avg_power for d in devices])

            # Tolerância para floats
            if sum_load <= 13.0001:
                self.assertEqual(node.capacity, 13.0, f"Node {node.id} load {sum_load} <= 13, expected capacity 13.0")
            else:
                self.assertEqual(node.capacity, 25.0, f"Node {node.id} load {sum_load} > 13, expected capacity 25.0")

    def test_api_localization_and_formatting(self):
        """Verify translation, network type injection and rounding."""
        # Test helper functions directly

        # Translations
        self.assertEqual(_translate_node_type(NodeType.CONSUMER_POINT), "Consumidor")
        self.assertEqual(_translate_node_type(NodeType.GENERATION_PLANT), "Usina Geradora")

        # Network Type
        self.assertEqual(_determine_network_type(13.0), "Monofásica")
        self.assertEqual(_determine_network_type(10.0), "Monofásica")
        self.assertEqual(_determine_network_type(13.1), "Trifásica")
        self.assertEqual(_determine_network_type(25.0), "Trifásica")

        # Rounding
        self.assertEqual(_round_val(1.23456), 1.235)
        self.assertEqual(_round_val(1.2), 1.2)

        # Snapshot Integration
        cfg = SimulationConfig(random_seed=42)
        backend = PowerGridBackend(cfg)
        snapshot = backend.get_tree_snapshot()
        tree = snapshot["tree"]

        # Check one consumer entry
        consumer_entry = next((x for x in tree if x["node_type"] == "Consumidor"), None)
        self.assertIsNotNone(consumer_entry)

        # Verify keys and values
        self.assertIn("network_type", consumer_entry)
        self.assertIn(consumer_entry["network_type"], ["Monofásica", "Trifásica"])

        # Verify rounding in float fields
        self.assertIsInstance(consumer_entry["capacity"], float)
        # Checking if it "looks" rounded is hard with floats, but we used round(val, 3)
        # We can check string representation length or equality

        # Verify capacity matches network type logic in the output
        cap = consumer_entry["capacity"]
        net = consumer_entry["network_type"]
        if cap <= 13.0:
            self.assertEqual(net, "Monofásica")
        else:
            self.assertEqual(net, "Trifásica")

if __name__ == "__main__":
    unittest.main()
