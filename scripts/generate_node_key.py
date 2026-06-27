"""Generate a new Ed25519 node key and print the base64-encoded PEM.

Usage:
    python scripts/generate_node_key.py

Then set the output as NODE_PRIVATE_KEY_B64 in your environment:
    - Render: Dashboard → Environment → Secret Files / Env Vars
    - Kubernetes: kubectl create secret generic proof-node --from-literal=NODE_PRIVATE_KEY_B64=<value>
    - Local dev: add to .env file
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.crypto import generate_key_b64

if __name__ == "__main__":
    key = generate_key_b64()
    print("Generated Ed25519 node key (base64-encoded PEM):\n")
    print(key)
    print("\nSet this as NODE_PRIVATE_KEY_B64 in your deployment environment.")
    print("Keep it secret — it is your node's signing identity.")
