"""SIOS Cashflow — pay-per-audit web product.

Flow: upload CSV → Stripe checkout → webhook → job queue → worker → PDF → email.

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
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sios.pipeline import run_file
from sios.store import SqliteStore

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent.parent / "static"
_REPORTS_DIR = Path(os.getenv("SIOS_REPORTS_DIR", "reports"))
_PRICE_CENTS = int(os.getenv("AUDIT_PRICE_CENTS", "4900"))
_BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

_JOB_MAX_ATTEMPTS = 3
_JOB_STALE_SECONDS = 300   # jobs stuck in "running" > 5 min → reset to pending


# ── Data models ────────────────────────────────────────────────────────────────

class AuditSession(BaseModel):
    id: str
    csv_b64: str
    filename: str = "upload.csv"
    email: str = ""
    paid: bool = False
    stripe_session_id: str = ""
    created_at: str = ""
    completed: bool = False
    result_json: str = ""  # cached result — avoids re-running detection


class RawStripeEvent(BaseModel):
    """Durable record of every incoming Stripe event."""
    event_id: str
    event_type: str
    payload: str   # raw JSON blob
    received_at: str


class ProcessedEvent(BaseModel):
    """Idempotency guard — one record per processed Stripe event_id."""
    event_id: str
    processed_at: str


class AuditJob(BaseModel):
    """Retryable job in the SQLite-backed queue."""
    job_id: str
    session_id: str
    status: str = "pending"    # pending | running | done | failed
    attempts: int = 0
    last_error: str = ""
    updated_at: str = ""


# ── Stores ─────────────────────────────────────────────────────────────────────

_sessions: SqliteStore[AuditSession] = SqliteStore("cashflow_sessions", AuditSession)
_raw_events: SqliteStore[RawStripeEvent] = SqliteStore("stripe_events", RawStripeEvent)
_processed_events: SqliteStore[ProcessedEvent] = SqliteStore("processed_events", ProcessedEvent)
_jobs: SqliteStore[AuditJob] = SqliteStore("audit_jobs", AuditJob)


# ── Job queue helpers ──────────────────────────────────────────────────────────

def _enqueue(session_id: str) -> str:
    job = AuditJob(
        job_id=str(uuid.uuid4()),
        session_id=session_id,
        updated_at=_now(),
    )
    _jobs.set(job.job_id, job)
    logger.info("Job enqueued: %s → session %s", job.job_id, session_id)
    return job.job_id


def _pick_pending_job() -> Optional[AuditJob]:
    """Return one pending job, or None if the queue is empty."""
    for job in _jobs.values():
        if job.status == "pending":
            job.status = "running"
            job.updated_at = _now()
            _jobs.set(job.job_id, job)
            return job
    return None


def _recover_stale_jobs() -> None:
    """Reset jobs stuck in 'running' (process died mid-execution) to 'pending'."""
    now = time.time()
    for job in _jobs.values():
        if job.status != "running":
            continue
        try:
            updated = datetime.fromisoformat(job.updated_at).timestamp()
        except Exception:
            updated = 0
        if now - updated > _JOB_STALE_SECONDS:
            logger.warning("Resetting stale job: %s (session %s)", job.job_id, job.session_id)
            job.status = "pending"
            job.updated_at = _now()
            _jobs.set(job.job_id, job)


def _run_job(job: AuditJob) -> None:
    """Execute one audit job. On failure, retry up to max attempts."""
    job.attempts += 1
    job.updated_at = _now()
    _jobs.set(job.job_id, job)

    try:
        _execute_audit(job.session_id)
        job.status = "done"
        logger.info("Job done: %s (session %s)", job.job_id, job.session_id)
    except Exception as exc:
        job.last_error = str(exc)
        if job.attempts >= _JOB_MAX_ATTEMPTS:
            job.status = "failed"
            logger.error("Job failed permanently: %s — %s", job.job_id, exc)
        else:
            job.status = "pending"  # will be retried
            logger.warning("Job attempt %d/%d failed, will retry: %s — %s",
                           job.attempts, _JOB_MAX_ATTEMPTS, job.job_id, exc)
    finally:
        job.updated_at = _now()
        _jobs.set(job.job_id, job)


# ── Worker thread ──────────────────────────────────────────────────────────────

def _worker_loop() -> None:
    """Persistent worker — picks up jobs, retries failures, recovers stale jobs."""
    logger.info("Audit worker started")
    while True:
        try:
            _recover_stale_jobs()
            job = _pick_pending_job()
            if job:
                _run_job(job)
            else:
                time.sleep(2)
        except Exception as exc:
            logger.error("Worker loop error: %s", exc)
            time.sleep(5)


# ── Audit execution ────────────────────────────────────────────────────────────

def _execute_audit(session_id: str) -> None:
    """Detect → CPO → PDF → email. Stores result in session. Idempotent."""
    sess = _sessions.get(session_id)
    if not sess:
        raise ValueError(f"Session not found: {session_id}")
    if sess.completed:
        return  # already done

    csv_bytes = base64.b64decode(sess.csv_b64)
    suffix = ".json" if sess.filename.lower().endswith(".json") else ".csv"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(csv_bytes)
        tmp_path = f.name

    try:
        result = run_file(tmp_path)
    finally:
        os.unlink(tmp_path)

    cpo_payload = json.dumps(
        [{"type": f.type.value, "amount": f.estimated_amount, "confidence": f.confidence}
         for f in result.findings],
        sort_keys=True,
    ).encode()
    cpo = hashlib.sha256(cpo_payload).hexdigest()

    report_path = ""
    try:
        from sios.cashflow.pdf import create_report
        report_path = create_report(result, cpo, session_id, str(_REPORTS_DIR))
    except Exception as exc:
        logger.error("PDF generation failed for %s: %s", session_id, exc)

    if sess.email and report_path:
        try:
            from sios.cashflow.email_sender import send_report
            send_report(sess.email, report_path, result.estimated_savings, result.currency)
        except Exception as exc:
            logger.error("Email delivery failed for %s: %s", session_id, exc)

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

    response = {
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

    # Re-fetch and persist (session may have been updated concurrently)
    sess = _sessions.get(session_id) or sess
    sess.completed = True
    sess.result_json = json.dumps(response)
    _sessions.set(session_id, sess)

    logger.info("Audit complete: %s — %d findings, %.0f %s",
                session_id, len(result.findings), result.estimated_savings, result.currency)


# ── App lifecycle ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    t = threading.Thread(target=_worker_loop, daemon=True, name="audit-worker")
    t.start()
    logger.info("SIOS Cashflow started — worker thread running")
    yield


app = FastAPI(title="SIOS Cashflow", docs_url=None, redoc_url=None, lifespan=_lifespan)

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    page = _STATIC_DIR / "index.html"
    return HTMLResponse(page.read_text() if page.exists() else _fallback_landing())


@app.get("/results/{session_id}", response_class=HTMLResponse)
def results_page(session_id: str) -> HTMLResponse:
    page = _STATIC_DIR / "results.html"
    if page.exists():
        return HTMLResponse(page.read_text().replace("{{SESSION_ID}}", session_id))
    return HTMLResponse(_fallback_results(session_id))


# ── Upload ─────────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload(file: UploadFile, email: str = Form("")) -> dict:
    if not file.filename or not file.filename.lower().endswith((".csv", ".json")):
        raise HTTPException(400, "Only .csv and .json files are accepted")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10 MB)")

    session_id = str(uuid.uuid4())
    _sessions.set(session_id, AuditSession(
        id=session_id,
        csv_b64=base64.b64encode(content).decode(),
        filename=file.filename or "upload.csv",
        email=email.strip(),
        created_at=_now(),
    ))
    logger.info("Session created: %s (%d bytes)", session_id, len(content))
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
        sess.paid = True
        _sessions.set(session_id, sess)
        _enqueue(session_id)
        logger.warning("Dev mode: payment skipped, job enqueued for %s", session_id)
        return {"url": f"{_BASE_URL}/results/{session_id}", "dev_mode": True}

    try:
        import stripe
        stripe.api_key = stripe_key
        cs = stripe.checkout.Session.create(
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
        sess.stripe_session_id = cs.id
        _sessions.set(session_id, sess)
        return {"url": cs.url}
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

    # 1. Verify signature
    try:
        import stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        event = (
            stripe.Webhook.construct_event(payload, sig, secret)
            if secret else json.loads(payload)
        )
    except Exception as exc:
        logger.warning("Webhook signature failed: %s", exc)
        raise HTTPException(400, f"Webhook error: {exc}")

    event_id = event.get("id", "")
    event_type = event.get("type", "")

    # 2. Store raw event (durable audit trail)
    if event_id:
        _raw_events.set(event_id, RawStripeEvent(
            event_id=event_id,
            event_type=event_type,
            payload=payload.decode("utf-8", errors="replace"),
            received_at=_now(),
        ))

    # 3. Idempotency check
    if event_id and _processed_events.get(event_id):
        logger.info("Duplicate webhook ignored: %s", event_id)
        return {"status": "ok", "duplicate": True}

    # 4. ACK path — minimal logic, enqueue work
    if event_type == "checkout.session.completed":
        obj = event["data"]["object"]
        session_id = obj.get("metadata", {}).get("session_id", "")
        if session_id:
            sess = _sessions.get(session_id)
            if sess and not sess.paid:
                sess.paid = True
                _sessions.set(session_id, sess)
                _enqueue(session_id)
                logger.info("Payment confirmed, job enqueued: %s (event %s)", session_id, event_id)

    # 5. Mark event processed
    if event_id:
        _processed_events.set(event_id, ProcessedEvent(
            event_id=event_id,
            processed_at=_now(),
        ))

    return {"status": "ok"}


# ── Run / poll ─────────────────────────────────────────────────────────────────

@app.get("/run/{session_id}")
def run(session_id: str) -> dict:
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")

    if sess.completed and sess.result_json:
        return json.loads(sess.result_json)

    if not sess.paid:
        if not _verify_stripe_payment(sess):
            raise HTTPException(402, "Payment required")
        sess.paid = True
        _sessions.set(session_id, sess)
        _enqueue(session_id)

    # Job in queue (or already picked up by worker)
    return {"status": "processing", "session_id": session_id}


# ── Invoice status (recovery) ──────────────────────────────────────────────────

@app.get("/invoice/status")
def invoice_status(session_id: str) -> dict:
    """Recovery endpoint — returns status + download link without re-running."""
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    if not sess.paid:
        return {"status": "unpaid", "session_id": session_id}
    if not sess.completed:
        return {"status": "processing", "session_id": session_id}
    data = json.loads(sess.result_json)
    return {
        "status": "completed",
        "session_id": session_id,
        "findings_count": data.get("findings_count", 0),
        "total_detected": data.get("total_detected", 0),
        "currency": data.get("currency", "EUR"),
        "cpo": data.get("cpo", ""),
        "report_available": data.get("report_available", False),
        "download_url": data.get("download_url"),
    }


# ── Download ───────────────────────────────────────────────────────────────────

@app.get("/download/{session_id}")
def download_report(session_id: str) -> FileResponse:
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    if not sess.paid:
        raise HTTPException(402, "Payment required")
    report = _REPORTS_DIR / f"{session_id}.pdf"
    if not report.exists():
        raise HTTPException(404, "Report not yet generated — check /invoice/status")
    return FileResponse(
        str(report),
        media_type="application/pdf",
        filename=f"sios_audit_{sess.filename.removesuffix('.csv').removesuffix('.json')}.pdf",
    )


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    pending = sum(1 for j in _jobs.values() if j.status == "pending")
    running = sum(1 for j in _jobs.values() if j.status == "running")
    return {
        "status": "ok",
        "product": "SIOS Cashflow",
        "price_eur": _PRICE_CENTS / 100,
        "stripe": bool(os.getenv("STRIPE_SECRET_KEY")),
        "email": bool(os.getenv("RESEND_API_KEY") or os.getenv("SMTP_HOST")),
        "queue": {"pending": pending, "running": running},
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _verify_stripe_payment(sess: AuditSession) -> bool:
    if not sess.stripe_session_id:
        return False
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not stripe_key:
        return False
    try:
        import stripe
        stripe.api_key = stripe_key
        cs = stripe.checkout.Session.retrieve(sess.stripe_session_id)
        return cs.payment_status == "paid"
    except Exception as exc:
        logger.error("Stripe verification failed: %s", exc)
        return False


def _fallback_landing() -> str:
    return (
        "<!DOCTYPE html><html><head><title>SIOS Audit</title></head>"
        "<body><p>Static files not found.</p></body></html>"
    )


def _fallback_results(session_id: str) -> str:
    return (
        f"<!DOCTYPE html><html><head><title>SIOS Audit</title></head><body>"
        f"<script>fetch('/run/{session_id}')"
        f".then(r=>r.json()).then(d=>document.body.innerHTML='<pre>'+JSON.stringify(d,null,2)+'</pre>');"
        f"</script></body></html>"
    )
