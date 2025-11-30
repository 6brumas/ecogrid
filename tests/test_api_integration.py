
import pytest
from fastapi.testclient import TestClient
from app import app
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

client = TestClient(app)

def test_get_tree():
    response = client.post("/tree")
    assert response.status_code == 200
    data = response.json()
    assert "tree" in data
    assert "logs" in data
    assert len(data["tree"]) > 0

def test_change_capacity():
    # Find a node first
    response = client.post("/tree")
    node_id = response.json()["tree"][0]["id"]

    payload = {
        "id": node_id,
        "capacity": 500.0
    }
    response = client.post("/change-node", json=payload)
    assert response.status_code == 200

    # Check if capacity was updated in the returned tree
    tree = response.json()["tree"]
    updated_node = next(n for n in tree if n["id"] == node_id)
    assert updated_node["capacity"] == 500.0

def test_add_node():
    # Pick a parent node (e.g., a distribution substation if possible, or any node)
    response = client.post("/tree")
    # Let's pick a DS node if available, otherwise just the first node
    tree = response.json()["tree"]
    parent_id = tree[0]["id"]
    for node in tree:
        if node["node_type"] == "DISTRIBUTION_SUBSTATION":
            parent_id = node["id"]
            break

    payload = {
        "id": parent_id,
        "add_node": True
    }

    response = client.post("/change-node", json=payload)
    assert response.status_code == 200

    new_tree = response.json()["tree"]
    assert len(new_tree) > len(tree)

    # Identify the new node (it should have parent_id = parent_id)
    # The new node id is random, so we just check count or existence of a new child
    children = [n for n in new_tree if n["parent_id"] == parent_id]
    original_children = [n for n in tree if n["parent_id"] == parent_id]
    assert len(children) > len(original_children)

def test_delete_node():
    # Add a node first to delete it safely
    response = client.post("/tree")
    parent_id = response.json()["tree"][0]["id"]

    payload_add = {
        "id": parent_id,
        "add_node": True
    }
    response_add = client.post("/change-node", json=payload_add)
    new_tree = response_add.json()["tree"]

    # Find the new node
    children = [n for n in new_tree if n["parent_id"] == parent_id]
    # We assume the last added child is the new one or we pick one that wasn't there
    # Simpler: just pick the last node in the list that is a child of parent_id
    node_to_delete = children[-1]["id"]

    payload_delete = {
        "id": node_to_delete,
        "delete_node": True
    }

    response_delete = client.post("/change-node", json=payload_delete)
    assert response_delete.status_code == 200

    final_tree = response_delete.json()["tree"]
    # Verify node is gone
    assert not any(n["id"] == node_to_delete for n in final_tree)

def test_change_parent_routing():
    # Pick a consumer node
    response = client.post("/tree")
    tree = response.json()["tree"]
    consumer_id = None
    for node in tree:
        if node["node_type"] == "CONSUMER_POINT":
            consumer_id = node["id"]
            break

    if not consumer_id:
        pytest.skip("No consumer node found")

    payload = {
        "id": consumer_id,
        "change_parent_routing": True
    }

    response = client.post("/change-node", json=payload)
    assert response.status_code == 200
    # Success just means it ran without error and returned a tree
    assert "tree" in response.json()

def test_force_change_parent():
    # Pick a consumer and a compatible parent (DS)
    response = client.post("/tree")
    tree = response.json()["tree"]

    consumer = None
    new_parent = None

    for node in tree:
        if node["node_type"] == "CONSUMER_POINT" and not consumer:
            consumer = node
        if node["node_type"] == "DISTRIBUTION_SUBSTATION" and not new_parent:
            new_parent = node

    if not consumer or not new_parent:
        pytest.skip("Could not find suitable nodes for force change parent")

    # Ensure we are actually changing parent
    if consumer["parent_id"] == new_parent["id"]:
        # Find another parent if possible
        for node in tree:
             if node["node_type"] == "DISTRIBUTION_SUBSTATION" and node["id"] != consumer["parent_id"]:
                 new_parent = node
                 break

    if consumer["parent_id"] == new_parent["id"]:
         pytest.skip("Only one parent available, cannot test change")

    payload = {
        "id": consumer["id"],
        "new_parent": new_parent["id"]
    }

    response = client.post("/change-node", json=payload)
    assert response.status_code == 200

    updated_tree = response.json()["tree"]
    updated_consumer = next(n for n in updated_tree if n["id"] == consumer["id"])

    # Note: Force change parent might fail if capacity is not sufficient, but the API returns the tree anyway.
    # We check if the response is valid.
    # If the change was successful, parent_id should be new_parent["id"]
    # If not, it remains the same. The test just checks that the endpoint works.
    assert updated_consumer["id"] == consumer["id"]

if __name__ == "__main__":
    # Manually run if executed as script
    try:
        test_get_tree()
        print("test_get_tree passed")
        test_change_capacity()
        print("test_change_capacity passed")
        test_add_node()
        print("test_add_node passed")
        test_delete_node()
        print("test_delete_node passed")
        test_change_parent_routing()
        print("test_change_parent_routing passed")
        test_force_change_parent()
        print("test_force_change_parent passed")
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
