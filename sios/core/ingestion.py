"""SIOS Core — source adapters that produce CanonicalTransaction objects."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from .models import CanonicalTransaction, TransactionType


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_date(raw: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_amount(raw: str | float) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = str(raw).replace(",", ".").replace(" ", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    return float(cleaned)


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def from_csv(
    content: str | bytes,
    source: str = "csv",
    column_map: Dict[str, str] | None = None,
) -> List[CanonicalTransaction]:
    """Parse a CSV file into CanonicalTransactions.

    ``column_map`` maps canonical field names to actual CSV column headers:
    ``{"date": "Date", "amount": "Montant", "description": "Libellé", ...}``
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    default_map = {
        "date": "date",
        "amount": "amount",
        "description": "description",
        "vendor": "vendor",
        "currency": "currency",
        "source_id": "id",
    }
    if column_map:
        default_map.update(column_map)

    reader = csv.DictReader(io.StringIO(content))
    txns: List[CanonicalTransaction] = []
    for row in reader:
        row_lower = {k.lower().strip(): v for k, v in row.items()}

        def get(field: str) -> str:
            col = default_map.get(field, field).lower()
            return row_lower.get(col, row_lower.get(field, "")).strip()

        try:
            amount_raw = get("amount") or get("montant") or get("debit") or "0"
            txns.append(CanonicalTransaction(
                source=source,
                source_id=get("source_id") or get("id") or None,
                amount=_parse_amount(amount_raw),
                currency=get("currency") or "EUR",
                date=_parse_date(get("date") or get("Date")),
                description=get("description") or get("libellé") or "",
                vendor=get("vendor") or get("fournisseur") or "",
                metadata=dict(row),
            ))
        except Exception:
            continue  # skip malformed rows

    return txns


def from_json(
    content: str | bytes,
    source: str = "json",
    column_map: Dict[str, str] | None = None,
) -> List[CanonicalTransaction]:
    """Parse a JSON array of transaction objects."""
    if isinstance(content, bytes):
        content = content.decode()
    records = json.loads(content)
    if isinstance(records, dict):
        for key in ("data", "transactions", "items", "results"):
            if key in records:
                records = records[key]
                break

    txns: List[CanonicalTransaction] = []
    for rec in records:
        try:
            cm = column_map or {}
            txns.append(CanonicalTransaction(
                source=source,
                source_id=str(rec.get(cm.get("id", "id"), "")),
                amount=_parse_amount(rec.get(cm.get("amount", "amount"), 0)),
                currency=rec.get(cm.get("currency", "currency"), "EUR"),
                date=_parse_date(str(rec.get(cm.get("date", "date"), ""))),
                description=str(rec.get(cm.get("description", "description"), "")),
                vendor=str(rec.get(cm.get("vendor", "vendor"), "")),
                metadata=rec,
            ))
        except Exception:
            continue

    return txns


def from_stripe_events(events: List[Dict[str, Any]]) -> List[CanonicalTransaction]:
    """Convert Stripe charge/invoice events to CanonicalTransactions."""
    txns: List[CanonicalTransaction] = []
    for ev in events:
        obj = ev.get("data", {}).get("object", ev)
        try:
            amount = obj.get("amount", obj.get("amount_paid", 0)) / 100.0
            created = obj.get("created", 0)
            date = datetime.fromtimestamp(created, tz=timezone.utc)
            description = obj.get("description") or obj.get("statement_descriptor") or ""
            txns.append(CanonicalTransaction(
                source="stripe",
                source_id=obj.get("id"),
                amount=amount,
                currency=(obj.get("currency") or "EUR").upper(),
                date=date,
                description=description,
                vendor="stripe",
                transaction_type=TransactionType.DEBIT if amount > 0 else TransactionType.CREDIT,
                metadata=obj,
            ))
        except Exception:
            continue
    return txns
