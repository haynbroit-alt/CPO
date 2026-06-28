"""Send audit report by email.

Supports two backends, selected by env var:
  - RESEND_API_KEY  → resend.dev (recommended, zero config)
  - SMTP_HOST       → standard SMTP

If neither is configured, logs a warning and skips delivery (dev mode).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def send_report(to_email: str, report_path: str, estimated_savings: float, currency: str = "EUR") -> bool:
    """Send the PDF report to the user. Returns True if sent, False if skipped."""
    if not to_email:
        return False

    resend_key = os.getenv("RESEND_API_KEY")
    smtp_host = os.getenv("SMTP_HOST")

    if resend_key:
        return _send_resend(to_email, report_path, estimated_savings, currency, resend_key)
    elif smtp_host:
        return _send_smtp(to_email, report_path, estimated_savings, currency)
    else:
        logger.warning(
            "Email delivery skipped — set RESEND_API_KEY or SMTP_HOST to enable. "
            "Report saved at: %s", report_path
        )
        return False


def _send_resend(
    to_email: str,
    report_path: str,
    estimated_savings: float,
    currency: str,
    api_key: str,
) -> bool:
    try:
        import resend  # type: ignore[import]
    except ImportError:
        logger.warning("resend not installed. Run: pip install resend")
        return False

    resend.api_key = api_key
    pdf_bytes = Path(report_path).read_bytes()

    from_addr = os.getenv("RESEND_FROM", "SIOS Audit <audit@resend.dev>")

    try:
        resend.Emails.send({
            "from": from_addr,
            "to": [to_email],
            "subject": f"Your SIOS Audit Report — {estimated_savings:,.0f} {currency} detected",
            "html": _email_html(estimated_savings, currency),
            "attachments": [{"filename": "sios_audit_report.pdf", "content": list(pdf_bytes)}],
        })
        logger.info("Report sent via Resend to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Resend delivery failed: %s", exc)
        return False


def _send_smtp(
    to_email: str,
    report_path: str,
    estimated_savings: float,
    currency: str,
) -> bool:
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    host = os.getenv("SMTP_HOST", "localhost")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", user or "audit@sios.app")

    msg = MIMEMultipart()
    msg["Subject"] = f"Your SIOS Audit Report — {estimated_savings:,.0f} {currency} detected"
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.attach(MIMEText(_email_html(estimated_savings, currency), "html"))

    with open(report_path, "rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="pdf")
        attachment.add_header("Content-Disposition", "attachment", filename="sios_audit_report.pdf")
        msg.attach(attachment)

    try:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            if port != 25:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        logger.info("Report sent via SMTP to %s", to_email)
        return True
    except Exception as exc:
        logger.error("SMTP delivery failed: %s", exc)
        return False


def _email_html(estimated_savings: float, currency: str) -> str:
    return f"""
<html><body style="font-family:system-ui;max-width:600px;margin:40px auto;color:#1a1a1a">
<h2>Your SIOS Audit Report</h2>
<p>Your financial audit is complete.</p>
<div style="background:#f5f5f5;padding:20px;border-radius:8px;margin:20px 0">
  <b style="font-size:20px">{estimated_savings:,.0f} {currency} detected</b><br>
  <span style="color:#555">in potential recoverable losses</span>
</div>
<p>Find your detailed report attached as a PDF.
Each finding includes an estimated recovery amount, confidence score, and recommended actions.</p>
<p style="color:#888;font-size:12px">
Every result is backed by a cryptographic proof (CPO) — reproducible and verifiable.<br>
SIOS — Financial Audit Engine
</p>
</body></html>
"""
