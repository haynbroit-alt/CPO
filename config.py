import os

# Consensus
QUORUM_THRESHOLD = float(os.getenv("QUORUM_THRESHOLD", "0.66"))
STABILITY_WINDOW_SEC = int(os.getenv("STABILITY_WINDOW_SEC", "30"))

# Sandbox
EXECUTION_TIMEOUT = int(os.getenv("EXECUTION_TIMEOUT", "10"))

# Docker images per world
WORLD_IMAGES = {
    "llm":           os.getenv("IMAGE_LLM",           "proof-protocol/sandbox:latest"),
    "symbolic":      os.getenv("IMAGE_SYMBOLIC",      "proof-protocol/symbolic:latest"),
    "neuro":         os.getenv("IMAGE_NEURO",         "proof-protocol/neuro:latest"),
    "bayesian":      os.getenv("IMAGE_BAYESIAN",      "proof-protocol/bayesian:latest"),
    "evolutionary":  os.getenv("IMAGE_EVOLUTIONARY",  "proof-protocol/evolutionary:latest"),
    "formal":        os.getenv("IMAGE_FORMAL",        "proof-protocol/formal:latest"),
    "multimodal":    os.getenv("IMAGE_MULTIMODAL",    "proof-protocol/multimodal:latest"),
}
DEFAULT_WORLD = "llm"

SUPPORTED_WORLDS = set(WORLD_IMAGES.keys())

# Crypto
PRIVATE_KEY_FILE = os.getenv("PRIVATE_KEY_FILE", "node_key.pem")

# Storage
LEDGER_FILE = os.getenv("LEDGER_FILE", "ledger.jsonl")
