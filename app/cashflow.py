"""SIOS Cashflow — pay-per-audit web product.

Flow: upload CSV → Stripe checkout → /run → findings + CPO → PDF → email delivery.

Environment variables:
    STRIPE_SECRET_KEY       Stripe secret key (sk_live_... or sk_test_...)
    STRIPE_WEBHOOK_SECRET   Stripe webhook signing secret (whsec_...)
    BASE_URL                Public base URL of this app (https://yourapp.com)
    AUDIT_PRICE_CENTS       Price in cents, default 4900 (€49)
    SIOS_REPORTS_DIR        Directory for PDF reports, default ./reports
    RESEND_API_KEY          Resend API key for email delivery (optional)
    SMTP_HOST               SMTP host for email delivery (optional)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sios.pipeline import run_file
from sios.store import SqliteStore

logger = logging.getLogger(__name__)

app = FastAPI(title="SIOS Cashflow", docs_url=None, redoc_url=None)

_STATIC_DIR = Path(__file__).parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_REPORTS_DIR = Path(os.getenv("SIOS_REPORTS_DIR", "reports"))
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_PRICE_CENTS = int(os.getenv("AUDIT_PRICE_CENTS", "4900"))
_BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")


# ── Session model ──────────────────────────────────────────────────────────────

class AuditSession(BaseModel):
    id: str
    csv_b64: str
    filename: str = "upload.csv"
    email: str = ""
    paid: bool = False
    stripe_session_id: str = ""
    created_at: str = ""
    completed: bool = False


_sessions: SqliteStore[AuditSession] = SqliteStore("cashflow_sessions", AuditSession)


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    page = _STATIC_DIR / "index.html"
    if page.exists():
        return HTMLResponse(page.read_text())
    return HTMLResponse(_fallback_landing())


@app.get("/results/{session_id}", response_class=HTMLResponse)
def results_page(session_id: str) -> HTMLResponse:
    page = _STATIC_DIR / "results.html"
    if page.exists():
        html = page.read_text().replace("{{SESSION_ID}}", session_id)
        return HTMLResponse(html)
    return HTMLResponse(_fallback_results(session_id))


# ── Upload ─────────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload(
    file: UploadFile,
    email: str = Form(""),
) -> dict:
    if not file.filename or not file.filename.lower().endswith((".csv", ".json")):
        raise HTTPException(400, "Only .csv and .json files are accepted")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10 MB)")

    import uuid
    session_id = str(uuid.uuid4())
    session = AuditSession(
        id=session_id,
        csv_b64=base64.b64encode(content).decode(),
        filename=file.filename or "upload.csv",
        email=email.strip(),
        paid=False,
        created_at=datetime.now(tz=timezone.utc).isoformat(),
    )
    _sessions.set(session_id, session)
    logger.info("Session created: %s (%s bytes, %s)", session_id, len(content), email or "no email")
    return {"session_id": session_id, "filename": file.filename, "size": len(content)}


# ── Stripe checkout ────────────────────────────────────────────────────────────

@app.post("/checkout/{session_id}")
def checkout(session_id: str) -> dict:
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    if sess.paid:
        return {"url": f"{_BASE_URL}/results/{session_id}"}

    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        # Dev mode: skip payment, mark as paid
        sess.paid = True
        _sessions.set(session_id, sess)
        logger.warning("Dev mode: payment skipped for session %s", session_id)
        return {"url": f"{_BASE_URL}/results/{session_id}", "dev_mode": True}

    try:
        import stripe
        stripe.api_key = stripe_key
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": "SIOS Financial Audit",
                        "description": f"Audit of {sess.filename} — findings + CPO proof + PDF report",
                    },
                    "unit_amount": _PRICE_CENTS,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{_BASE_URL}/results/{session_id}",
            cancel_url=f"{_BASE_URL}/",
            metadata={"session_id": session_id},
            customer_email=sess.email or None,
        )
        sess.stripe_session_id = checkout_session.id
        _sessions.set(session_id, sess)
        logger.info("Stripe checkout created: %s → %s", session_id, checkout_session.id)
        return {"url": checkout_session.url}
    except ImportError:
        raise HTTPException(500, "Stripe not installed — run: pip install sios[stripe]")
    except Exception as exc:
        logger.error("Stripe error: %s", exc)
        raise HTTPException(500, f"Payment error: {exc}")


# ── Stripe webhook ─────────────────────────────────────────────────────────────

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    try:
        import stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        event = (
            stripe.Webhook.construct_event(payload, sig, secret)
            if secret
            else json.loads(payload)
        )
    except Exception as exc:
        raise HTTPException(400, f"Webhook error: {exc}")

    if event.get("type") == "checkout.session.completed":
        obj = event["data"]["object"]
        session_id = obj.get("metadata", {}).get("session_id")
        if session_id:
            sess = _sessions.get(session_id)
            if sess and not sess.paid:
                sess.paid = True
                _sessions.set(session_id, sess)
                logger.info("Payment confirmed via webhook: %s", session_id)

    return {"status": "ok"}


# ── Run audit ─────────────────────────────────────────────────────────────────

@app.get("/run/{session_id}")
def run(session_id: str) -> dict:
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")

    # Verify payment
    if not sess.paid:
        if not _verify_stripe_payment(sess):
            raise HTTPException(402, "Payment required")
        sess.paid = True
        _sessions.set(session_id, sess)

    # Decode CSV
    try:
        csv_bytes = base64.b64decode(sess.csv_b64)
    except Exception:
        raise HTTPException(400, "Invalid session data")

    # Run detection
    suffix = ".json" if sess.filename.lower().endswith(".json") else ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(csv_bytes)
        tmp_path = f.name

    try:
        result = run_file(tmp_path)
    except Exception as exc:
        logger.error("Detection error for session %s: %s", session_id, exc)
        raise HTTPException(422, f"Could not process file: {exc}")
    finally:
        os.unlink(tmp_path)

    # Generate CPO (SHA-256 fingerprint of findings)
    cpo_payload = json.dumps(
        [{"type": f.type.value, "amount": f.estimated_amount, "confidence": f.confidence}
         for f in result.findings],
        sort_keys=True,
    ).encode()
    cpo = hashlib.sha256(cpo_payload).hexdigest()

    # Generate PDF
    report_path = ""
    try:
        from sios.cashflow.pdf import create_report
        report_path = create_report(result, cpo, session_id, str(_REPORTS_DIR))
    except ImportError:
        logger.warning("fpdf2 not installed — PDF skipped. Run: pip install fpdf2")
    except Exception as exc:
        logger.error("PDF generation failed: %s", exc)

    # Send email
    if sess.email and report_path:
        try:
            from sios.cashflow.email_sender import send_report
            send_report(sess.email, report_path, result.estimated_savings, result.currency)
        except Exception as exc:
            logger.error("Email delivery failed: %s", exc)

    # Mark completed
    sess.completed = True
    _sessions.set(session_id, sess)

    findings_out = [
        {
            "type": f.type.value,
            "title": f.title,
            "estimated_amount": f.estimated_amount,
            "currency": f.currency,
            "confidence": round(f.confidence, 2),
            "description": f.description,
            "recommended_actions": f.recommended_actions[:3],
        }
        for f in sorted(result.findings, key=lambda x: x.estimated_amount or 0, reverse=True)
    ]

    return {
        "status": "done",
        "session_id": session_id,
        "total_detected": round(result.estimated_savings, 2),
        "currency": result.currency,
        "findings_count": len(result.findings),
        "transactions_analyzed": result.dataset_rows,
        "findings": findings_out,
        "cpo": cpo,
        "report_available": bool(report_path),
        "download_url": f"/download/{session_id}" if report_path else None,
    }


# ── Download ──────────────────────────────────────────────────────────────────

@app.get("/download/{session_id}")
def download_report(session_id: str) -> FileResponse:
    # Validate session exists and was paid
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    if not sess.paid:
        raise HTTPException(402, "Payment required")

    report = _REPORTS_DIR / f"{session_id}.pdf"
    if not report.exists():
        raise HTTPException(404, "Report not generated yet — call /run/{session_id} first")

    return FileResponse(
        str(report),
        media_type="application/pdf",
        filename=f"sios_audit_{sess.filename.removesuffix('.csv').removesuffix('.json')}.pdf",
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "product": "SIOS Cashflow",
        "price_eur": _PRICE_CENTS / 100,
        "stripe": bool(os.getenv("STRIPE_SECRET_KEY")),
        "email": bool(os.getenv("RESEND_API_KEY") or os.getenv("SMTP_HOST")),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_stripe_payment(sess: AuditSession) -> bool:
    """Check Stripe API directly to confirm payment status."""
    if not sess.stripe_session_id:
        return False
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return False
    try:
        import stripe
        stripe.api_key = stripe_key
        checkout_session = stripe.checkout.Session.retrieve(sess.stripe_session_id)
        return checkout_session.payment_status == "paid"
    except Exception as exc:
        logger.error("Stripe verification failed: %s", exc)
        return False


def _fallback_landing() -> str:
    return """<!DOCTYPE html>
<html>
<head>
  <title>SIOS Audit</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <p>Static files not found. Make sure the <code>static/</code> directory exists.</p>
</body>
</html>"""


def _fallback_results(session_id: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><title>SIOS — Running Audit</title><meta charset="utf-8"></head>
<body>
  <p>Processing audit for session <code>{session_id}</code>...</p>
  <script>
    fetch('/run/{session_id}')
      .then(r => r.json())
      .then(d => document.body.innerHTML = '<pre>' + JSON.stringify(d, null, 2) + '</pre>');
  </script>
</body>
</html>"""
