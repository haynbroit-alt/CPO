"""Tests for the POST /ask conversational endpoint."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import ExecutionResult


@pytest.fixture(autouse=True)
def _patch_ask_execute():
    mock_result = ExecutionResult(stdout="42\n", stderr="", exit_code=0, runtime_ms=7.0)
    with patch("app.executor.docker.from_env"), \
         patch("app.main.execute", return_value=mock_result):
        yield mock_result


@pytest.fixture()
def client(tmp_path):
    import app.storage as storage_module
    key_file = str(tmp_path / "key.pem")
    ledger_file = tmp_path / "ledger.jsonl"

    with patch("app.main._PRIVATE_KEY", __import__("app.crypto", fromlist=["load_private_key"]).load_private_key(key_file)), \
         patch.object(storage_module, "_ledger", ledger_file):
        from app.main import app as fastapi_app
        import app.main as main_module
        import app.crypto as crypto_module
        priv = crypto_module.load_private_key(key_file)
        main_module._PRIVATE_KEY = priv
        main_module._PUB_BYTES = crypto_module.public_key_bytes(priv)
        main_module.NODE_ID = crypto_module.node_id(main_module._PUB_BYTES)
        yield TestClient(fastapi_app)


@pytest.fixture()
def mock_brain():
    with patch("app.main.generate_code", return_value="print(6 * 7)") as m:
        yield m


def test_ask_basic(client, mock_brain):
    r = client.post("/ask", json={"question": "What is 6 times 7?"})
    assert r.status_code == 201
    data = r.json()
    assert data["answer"] == "42"
    assert data["code"] == "print(6 * 7)"
    assert "proof_hash" in data
    assert "signature" in data
    assert data["exit_code"] == 0
    assert data["world"] == "llm"


def test_ask_custom_world(client, mock_brain):
    r = client.post("/ask", json={"question": "Factor x^2-1", "world": "symbolic"})
    assert r.status_code == 201
    assert r.json()["world"] == "symbolic"
    mock_brain.assert_called_once_with("Factor x^2-1", "symbolic")


def test_ask_invalid_world(client, mock_brain):
    r = client.post("/ask", json={"question": "test", "world": "quantum"})
    assert r.status_code == 422


def test_ask_brain_error(client):
    with patch("app.main.generate_code", side_effect=Exception("API unreachable")):
        r = client.post("/ask", json={"question": "anything"})
    assert r.status_code == 502
    assert "Brain error" in r.json()["detail"]


def test_ask_empty_code(client):
    with patch("app.main.generate_code", return_value="   "):
        r = client.post("/ask", json={"question": "blank"})
    assert r.status_code == 502
    assert "empty" in r.json()["detail"]


def test_ask_stored_in_ledger(client, mock_brain):
    client.post("/ask", json={"question": "What is 6 times 7?"})
    ledger_r = client.get("/ledger")
    assert ledger_r.status_code == 200
    records = ledger_r.json()
    assert len(records) == 1
    assert records[0]["claim"] == "What is 6 times 7?"
