import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import app.storage as storage_module


@pytest.fixture(autouse=True)
def tmp_ledger(tmp_path):
    ledger = tmp_path / "test_ledger.jsonl"
    with patch.object(storage_module, "_ledger", ledger):
        yield ledger


def test_append_and_retrieve():
    storage_module.append({"cpo_id": "abc", "content_hash": "deadbeef"})
    records = storage_module.all_cpos()
    assert len(records) == 1
    assert records[0]["cpo_id"] == "abc"


def test_find_by_hash():
    storage_module.append({"cpo_id": "x1", "content_hash": "aaa"})
    storage_module.append({"cpo_id": "x2", "content_hash": "bbb"})
    assert storage_module.find_by_hash("aaa")["cpo_id"] == "x1"
    assert storage_module.find_by_hash("zzz") is None


def test_find_by_id():
    storage_module.append({"cpo_id": "id-1", "content_hash": "h1"})
    assert storage_module.find_by_id("id-1") is not None
    assert storage_module.find_by_id("no-such") is None


def test_empty_ledger_returns_empty_list():
    assert storage_module.all_cpos() == []
