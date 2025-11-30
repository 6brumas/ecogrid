
import unittest
import os
import sys
import time
from unittest.mock import patch

# Ensure backend modules are importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from api.backend_facade import PowerGridBackend
from core.models import Node, NodeType

class TestSimulationNoise(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("Initializing PowerGridBackend for noise test...")
        cls.backend = PowerGridBackend(nodes_path="backend/out/nodes", edges_path="backend/out/edges")

    def test_capacity_factor(self):
        """Verify capacity is 1.5x consumers."""
        snap = self.backend.get_tree_snapshot()

        # Check a consumer node (should have 1 unique consumer in subtree: itself)
        consumer = next((n for n in snap["tree"] if n["node_type"] == "CONSUMER_POINT"), None)
        if consumer:
            print(f"Consumer {consumer['id']} Capacity: {consumer['capacity']}")
            self.assertEqual(consumer["capacity"], 1.5)

        # Check a DS
        # We don't know exactly how many consumers, but capacity should be 1.5 * Integer
        ds = next((n for n in snap["tree"] if n["node_type"] == "DISTRIBUTION_SUBSTATION"), None)
        if ds:
            print(f"DS {ds['id']} Capacity: {ds['capacity']}")
            self.assertTrue(ds['capacity'] % 1.5 == 0.0 or ds['capacity'] == 1.0)
            # Note: max(1.0, count*1.5). If count=0, cap=1.0. If count > 0, multiple of 1.5.

    @patch('backend.api.backend_facade.time')
    def test_noise_fluctuation(self, mock_time):
        """Verify device power changes with time."""
        snap = self.backend.get_tree_snapshot()
        consumer = next((n for n in snap["tree"] if n["node_type"] == "CONSUMER_POINT"), None)
        if not consumer:
            self.skipTest("No consumer found")

        consumer_id = consumer["id"]

        # Time 0
        mock_time.time.return_value = 0.0
        snap1 = self.backend.get_tree_snapshot()
        devices1 = snap1["devices"][consumer_id]

        # Time 100 (diff block from 0 if block=60)
        mock_time.time.return_value = 100.0
        snap2 = self.backend.get_tree_snapshot()
        devices2 = snap2["devices"][consumer_id]

        # Check all devices. At least one should change (e.g. Fridge with Flat profile)
        changed = False
        for d1, d2 in zip(devices1, devices2):
            print(f"Device {d1['name']}: t=0 power={d1['current_power']}, t=100 power={d2['current_power']}")
            if d1['current_power'] != d2['current_power']:
                changed = True

        self.assertTrue(changed, "Devices power did not change with time/noise")

        # Verify node propagation
        # Node current_load should equal sum of devices (approx if only one device)
        node_load = next(n for n in snap2["tree"] if n["id"] == consumer_id)["current_load"]
        print(f"Node Load at t=100: {node_load}")

        # Sum devices
        dev_sum = sum(d["current_power"] for d in snap2["devices"][consumer_id] if d["current_power"] is not None)
        self.assertAlmostEqual(node_load, dev_sum, places=4)

if __name__ == "__main__":
    unittest.main()
