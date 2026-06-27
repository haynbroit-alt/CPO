import json
from typing import Any


def canonicalize(obj: Any) -> str:
    """Deterministic JSON serialization (RFC 8785-style)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
