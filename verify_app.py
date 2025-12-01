
import sys
import os

# Add the current directory to sys.path so we can import app
sys.path.append(os.getcwd())

# Mock FastAPI and other dependencies if necessary, but we want to check imports
try:
    from app import app, sim_sobrecarga, sim_falha_no, sim_pico_consumo, change_node
    print("Successfully imported app and simulation functions.")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

# Check if functions are callable
if not callable(sim_sobrecarga):
    print("sim_sobrecarga is not callable")
    sys.exit(1)

if not callable(sim_falha_no):
    print("sim_falha_no is not callable")
    sys.exit(1)

if not callable(sim_pico_consumo):
    print("sim_pico_consumo is not callable")
    sys.exit(1)

print("Verification script passed.")
