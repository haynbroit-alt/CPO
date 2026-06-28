"""Stripe connector — pull charges and subscriptions as CanonicalTransactions.

Requirements::

    pip install sios[stripe]
    # or: pip install stripe

Credentials::

    export STRIPE_API_KEY=sk_live_...
    # or pass api_key= to StripeConnector()

What it detects when fed to the Value Engine:
    - Duplicate charges (same amount + customer, close dates)
    - Subscription anomalies (sudden price changes)
    - Refund signals (high refund rate = product/billing issue)
    - Failed charge patterns (retry storms)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sios.core.models import CanonicalTransaction, TransactionType

logger = logging.getLogger(__name__)


class StripeConnector:
    """Fetch Stripe charges and convert them to CanonicalTransactions.

    Example::

        from sios.connectors.stripe import StripeConnector
        from sios.value_engine.engine import ValueEngine

        connector = StripeConnector(api_key="sk_live_...")
        transactions = connector.fetch(days=90)

        findings = ValueEngine().run(transactions)
        for f in findings:
            print(f.type.value, f.title, f.estimated_amount)
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        try:
            import stripe as _stripe
            self._stripe = _stripe
        except ImportError as exc:
            raise ImportError(
                "stripe is required for the Stripe connector. "
                "Install it with: pip install sios[stripe]"
            ) from exc

        resolved_key = api_key or os.environ.get("STRIPE_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Stripe API key required. Pass api_key= or set STRIPE_API_KEY env var."
            )
        self._client = self._stripe.StripeClient(resolved_key)
        logger.info("StripeConnector initialised")

    # ── Charges ───────────────────────────────────────────────────────────────

    def fetch(
        self,
        days: int = 90,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> List[CanonicalTransaction]:
        """Fetch Stripe charges as CanonicalTransactions.

        Args:
            days:   Look-back window in days.
            limit:  Max number of charges per page (Stripe max = 100).
            status: Filter by charge status: "succeeded", "failed", "pending".

        Returns:
            List of CanonicalTransaction objects.
        """
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)
        params: Dict = {
            "created": {"gte": int(since.timestamp())},
            "limit": min(limit, 100),
            "expand": ["data.customer"],
        }
        if status:
            params["status"] = status

        transactions: List[CanonicalTransaction] = []
        try:
            charges = self._client.charges.list(params=params)
            for charge in charges.auto_paging_iter():
                txn = self._charge_to_transaction(charge)
                if txn:
                    transactions.append(txn)
        except self._stripe.StripeError as exc:
            logger.error("Stripe API error: %s", exc)
            raise

        logger.info("Fetched %d Stripe charges (last %d days)", len(transactions), days)
        return transactions

    # ── Subscriptions ─────────────────────────────────────────────────────────

    def fetch_subscriptions(
        self,
        status: str = "active",
        limit: int = 100,
    ) -> List[CanonicalTransaction]:
        """Fetch active subscriptions as recurring CanonicalTransactions.

        Useful for detecting subscription drift (price changes, unused plans).
        """
        transactions: List[CanonicalTransaction] = []
        try:
            subs = self._client.subscriptions.list(
                params={"status": status, "limit": min(limit, 100)}
            )
            for sub in subs.auto_paging_iter():
                for item in sub.get("items", {}).get("data", []):
                    plan = item.get("plan") or item.get("price", {})
                    amount = (plan.get("amount") or 0) / 100.0
                    currency = (plan.get("currency") or "usd").upper()
                    interval = plan.get("interval", "month")

                    transactions.append(
                        CanonicalTransaction(
                            source="stripe_subscription",
                            source_id=sub["id"],
                            amount=amount,
                            currency=currency,
                            date=datetime.fromtimestamp(
                                sub["current_period_start"], tz=timezone.utc
                            ),
                            description=f"Stripe subscription — {plan.get('nickname') or plan.get('id', 'unknown')}",
                            vendor="Stripe",
                            category="subscription",
                            transaction_type=TransactionType.SUBSCRIPTION,
                            metadata={
                                "subscription_id": sub["id"],
                                "interval": interval,
                                "status": sub.get("status"),
                                "customer": sub.get("customer"),
                            },
                        )
                    )
        except self._stripe.StripeError as exc:
            logger.error("Stripe subscription fetch error: %s", exc)
            raise

        logger.info("Fetched %d active Stripe subscriptions", len(transactions))
        return transactions

    # ── Internal ──────────────────────────────────────────────────────────────

    def _charge_to_transaction(self, charge) -> Optional[CanonicalTransaction]:
        if charge.get("amount") is None:
            return None

        amount = charge["amount"] / 100.0  # Stripe amounts are in cents
        currency = (charge.get("currency") or "usd").upper()
        created = datetime.fromtimestamp(charge["created"], tz=timezone.utc)

        customer = charge.get("customer")
        customer_email = ""
        if isinstance(customer, dict):
            customer_email = customer.get("email", "")
        elif isinstance(customer, str):
            customer_email = customer  # ID only

        status = charge.get("status", "")
        txn_type = (
            TransactionType.REFUND
            if charge.get("refunded")
            else TransactionType.DEBIT
        )

        description = (
            charge.get("description")
            or charge.get("statement_descriptor")
            or f"Stripe charge {charge['id']}"
        )

        return CanonicalTransaction(
            source="stripe",
            source_id=charge["id"],
            amount=amount,
            currency=currency,
            date=created,
            description=description,
            vendor=charge.get("statement_descriptor") or "Stripe",
            category="payment",
            transaction_type=txn_type,
            metadata={
                "charge_id": charge["id"],
                "status": status,
                "customer_email": customer_email,
                "payment_method": charge.get("payment_method_details", {}).get("type"),
                "failure_code": charge.get("failure_code"),
            },
        )
