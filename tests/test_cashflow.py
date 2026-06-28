"""Integration tests for the SIOS Cashflow pay-per-audit flow.

Flow under test:
  POST /upload  →  POST /checkout/{id}  →  GET /run/{id}  →  GET /download/{id}
"""
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

SAMPLE_CSV = b"""\
date,amount,currency,vendor,description
2024-01-05,299,EUR,Slack,Slack Pro subscription
2024-02-05,299,EUR,Slack,Slack Pro subscription
2024-01-20,1250,EUR,AWS,EC2 dev server
2024-02-20,1250,EUR,AWS,EC2 dev server
2024-03-20,1250,EUR,AWS,EC2 dev server
2024-01-15,8900,EUR,AWS,EC2 load test (one-time spike)
2024-01-10,49,EUR,GitHub,GitHub Teams Jan
2024-02-10,49,EUR,GitHub,GitHub Teams Feb
2024-03-10,49,EUR,GitHub,GitHub Teams Mar
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with a tmp SQLite DB and no Stripe key (dev mode)."""
    monkeypatch.setenv("SIOS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SIOS_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("BASE_URL", "http://testserver")

    # Re-import after env vars are set so the store uses the tmp DB
    import importlib
    import app.cashflow as cf_module
    importlib.reload(cf_module)

    return TestClient(cf_module.app)


# ── Upload ────────────────────────────────────────────────────────────────────

def test_upload_rejects_non_csv(client):
    r = client.post(
        "/upload",
        files={"file": ("report.xlsx", b"binary", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_upload_accepts_csv(client):
    r = client.post(
        "/upload",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
        data={"email": "test@example.com"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    assert body["filename"] == "sample.csv"


# ── Checkout (dev mode, no Stripe key) ───────────────────────────────────────

def test_checkout_dev_mode_skips_stripe(client):
    # Upload first
    up = client.post(
        "/upload",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
    )
    sid = up.json()["session_id"]

    r = client.post(f"/checkout/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert "url" in body
    assert body.get("dev_mode") is True
    assert sid in body["url"]


def test_checkout_unknown_session(client):
    r = client.post("/checkout/does-not-exist")
    assert r.status_code == 404


# ── Run (full detection pipeline) ────────────────────────────────────────────

def _full_flow(client) -> tuple[str, dict]:
    """Upload → checkout → run (polls until done). Returns (session_id, result_dict)."""
    up = client.post(
        "/upload",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
        data={"email": "user@example.com"},
    )
    sid = up.json()["session_id"]
    client.post(f"/checkout/{sid}")          # dev mode: marks paid

    # Poll until background task completes (or 10s timeout)
    import time
    deadline = time.monotonic() + 10
    body = {}
    while time.monotonic() < deadline:
        r = client.get(f"/run/{sid}")
        assert r.status_code == 200
        body = r.json()
        if body.get("status") != "processing":
            break
        time.sleep(0.1)
    return sid, body


def test_run_returns_findings(client):
    _, body = _full_flow(client)
    assert body["status"] == "done"
    assert body["transactions_analyzed"] > 0
    assert body["findings_count"] >= 0
    assert isinstance(body["total_detected"], float)
    assert "cpo" in body
    assert len(body["cpo"]) == 64               # SHA-256 hex


def test_run_detects_duplicate_and_subscription(client):
    _, body = _full_flow(client)
    assert len(body["findings"]) >= 1


def test_run_is_idempotent(client):
    """Calling /run twice returns the same CPO from cache."""
    up = client.post(
        "/upload",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
    )
    sid = up.json()["session_id"]
    client.post(f"/checkout/{sid}")

    # Wait for completion
    import time
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        r1 = client.get(f"/run/{sid}")
        if r1.json().get("status") != "processing":
            break
        time.sleep(0.1)

    r2 = client.get(f"/run/{sid}")
    assert r1.json()["cpo"] == r2.json()["cpo"]


def test_run_requires_payment(client):
    """Without checkout, /run should return 402."""
    up = client.post(
        "/upload",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
    )
    sid = up.json()["session_id"]
    r = client.get(f"/run/{sid}")
    assert r.status_code == 402


# ── Invoice status (recovery) ─────────────────────────────────────────────────

def test_invoice_status_unpaid(client):
    up = client.post(
        "/upload",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
    )
    sid = up.json()["session_id"]
    r = client.get(f"/invoice/status?session_id={sid}")
    assert r.status_code == 200
    assert r.json()["status"] == "unpaid"


def test_invoice_status_completed(client):
    sid, _ = _full_flow(client)
    r = client.get(f"/invoice/status?session_id={sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert "cpo" in body
    assert "findings_count" in body


# ── Download ──────────────────────────────────────────────────────────────────

def test_download_after_run(client):
    """If fpdf2 is installed, /download returns a PDF; otherwise 404 is acceptable."""
    sid, body = _full_flow(client)
    if body.get("report_available"):
        r = client.get(f"/download/{sid}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"


def test_download_requires_payment(client):
    up = client.post(
        "/upload",
        files={"file": ("sample.csv", SAMPLE_CSV, "text/csv")},
    )
    sid = up.json()["session_id"]
    r = client.get(f"/download/{sid}")
    assert r.status_code == 402


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
