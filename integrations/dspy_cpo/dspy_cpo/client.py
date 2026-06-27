"""Thin HTTP client for the Proof Protocol node — shared with langchain-cpo."""

from __future__ import annotations

import requests


class CPOClient:
    """HTTP client for a running Proof Protocol node.

    Args:
        base_url: Base URL of the node (e.g. ``https://your-node.onrender.com``).
        timeout: Request timeout in seconds (default 30).
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def prove(self, claim: str, code: str, world: str = "llm") -> dict:
        """Execute *code* in the sandbox and return a signed CPO."""
        resp = requests.post(
            f"{self.base_url}/prove",
            json={"claim": claim, "code": code, "world": world},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def ask(self, question: str, world: str = "llm") -> dict:
        """Generate code from *question* via the LLM brain and return a signed CPO."""
        resp = requests.post(
            f"{self.base_url}/ask",
            json={"question": question, "world": world},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def verify(self, content_hash: str) -> dict:
        """Re-execute a stored CPO and return the verification verdict."""
        resp = requests.get(f"{self.base_url}/verify/{content_hash}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> bool:
        """Return True if the node is reachable and healthy."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            return resp.status_code == 200
        except Exception:
            return False
