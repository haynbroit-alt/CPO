"""Integration tests for the FastAPI endpoints using a mocked executor."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import ExecutionResult


@pytest.fixture(autouse=True)
def _patch_docker(tmp_path):
    """Avoid real Docker calls in unit tests."""
    mock_result = ExecutionResult(stdout="2\n", stderr="", exit_code=0, runtime_ms=5.0)
    with patch("app.executor.docker.from_env"), \
         patch("app.executor.execute", return_value=mock_result):
        yield mock_result


@pytest.fixture()
def client(tmp_path):
    import app.storage as storage_module
    from pathlib import Path
    key_file = str(tmp_path / "key.pem")
    ledger_file = tmp_path / "ledger.jsonl"

    with patch("app.main._PRIVATE_KEY", __import__("app.crypto", fromlist=["load_private_key"]).load_private_key(key_file)), \
         patch.object(storage_module, "_ledger", ledger_file):
        from app.main import app as fastapi_app
        # Re-init node keys after patching
        import app.main as main_module
        import app.crypto as crypto_module
        priv = crypto_module.load_private_key(key_file)
        main_module._PRIVATE_KEY = priv
        main_module._PUB_BYTES = crypto_module.public_key_bytes(priv)
        main_module.NODE_ID = crypto_module.node_id(main_module._PUB_BYTES)
        yield TestClient(fastapi_app)


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "node_id" in data
    assert "llm" in data["worlds"]


def test_prove_default_world(client):
    payload = {"claim": "1+1=2", "code": "print(1+1)"}
    r = client.post("/prove", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "accepted"
    assert data["world"] == "llm"
    assert "content_hash" in data
    assert "signature" in data


def test_prove_symbolic_world(client):
    payload = {
        "claim": "x**2 - 1 == (x-1)(x+1)",
        "code": "from sympy import symbols, factor; x = symbols('x'); print(factor(x**2-1))",
        "world": "symbolic",
    }
    r = client.post("/prove", json=payload)
    assert r.status_code == 201
    assert r.json()["world"] == "symbolic"


def test_prove_invalid_world(client):
    payload = {"claim": "test", "code": "pass", "world": "quantum"}
    r = client.post("/prove", json=payload)
    assert r.status_code == 422


def test_get_cpo_not_found(client):
    r = client.get("/cpo/nonexistent-id")
    assert r.status_code == 404


def test_ledger_empty(client):
    r = client.get("/ledger")
    assert r.status_code == 200
    assert r.json() == []
