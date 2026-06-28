"""AWS Cost Explorer connector.

Pulls daily spend per AWS service and converts it to CanonicalTransactions
so the SIOS Value Engine can detect waste, anomalies, and over-spend.

Requirements::

    pip install sios[aws]
    # or: pip install boto3

Credentials are resolved by the standard boto3 chain:
    1. AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars
    2. ~/.aws/credentials profile
    3. IAM instance profile (EC2 / ECS / Lambda)

Minimum IAM permissions required::

    ce:GetCostAndUsage
    ce:GetDimensionValues
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sios.core.models import CanonicalTransaction, TransactionType

logger = logging.getLogger(__name__)

# AWS Cost Explorer only operates in us-east-1 regardless of resource region
_CE_REGION = "us-east-1"

# Services commonly associated with waste / optimisation opportunities
_WASTE_SERVICES = frozenset(
    {
        "Amazon Elastic Compute Cloud - Compute",
        "Amazon Elastic Container Service",
        "Amazon Relational Database Service",
        "Amazon Redshift",
        "Amazon OpenSearch Service",
        "Amazon ElastiCache",
    }
)


class AWSConnector:
    """Pull AWS spend from Cost Explorer and convert to CanonicalTransactions.

    Example::

        from sios.connectors.aws import AWSConnector
        from sios import SIOS

        connector = AWSConnector()                  # uses default boto3 credentials
        transactions = connector.fetch(days=90)

        from sios.pipeline import run_file
        from sios.value_engine.engine import ValueEngine
        findings = ValueEngine().run(transactions)
    """

    def __init__(
        self,
        profile: Optional[str] = None,
        region: str = "us-east-1",
        currency: str = "USD",
    ) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for the AWS connector. "
                "Install it with: pip install sios[aws]"
            ) from exc

        session = boto3.Session(profile_name=profile, region_name=region)
        self._ce = session.client("ce", region_name=_CE_REGION)
        self._currency = currency
        logger.info("AWSConnector initialised (profile=%s)", profile or "default")

    def fetch(
        self,
        days: int = 90,
        granularity: str = "DAILY",
        min_amount: float = 0.01,
    ) -> List[CanonicalTransaction]:
        """Fetch AWS costs grouped by service for the last ``days`` days.

        Args:
            days:        Look-back window in days (max 400 for DAILY).
            granularity: "DAILY" or "MONTHLY".
            min_amount:  Skip rows below this amount (USD cents noise).

        Returns:
            List of CanonicalTransaction objects ready for the Value Engine.
        """
        end = date.today()
        start = end - timedelta(days=days)

        logger.info("Fetching AWS costs from %s to %s (%s)", start, end, granularity)

        try:
            response = self._ce.get_cost_and_usage(
                TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
                Granularity=granularity,
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
                Metrics=["UnblendedCost"],
            )
        except Exception as exc:
            logger.error("Cost Explorer API call failed: %s", exc)
            raise

        transactions: List[CanonicalTransaction] = []
        for period in response.get("ResultsByTime", []):
            period_start = datetime.fromisoformat(
                period["TimePeriod"]["Start"]
            ).replace(tzinfo=timezone.utc)

            for group in period.get("Groups", []):
                service = group["Keys"][0]
                metric = group["Metrics"]["UnblendedCost"]
                amount = float(metric["Amount"])
                unit = metric.get("Unit", self._currency)

                if amount < min_amount:
                    continue

                txn_type = (
                    TransactionType.SUBSCRIPTION
                    if "Support" in service or "Reserved" in service
                    else TransactionType.DEBIT
                )

                transactions.append(
                    CanonicalTransaction(
                        source="aws",
                        source_id=f"aws-{service.replace(' ', '_')}-{period['TimePeriod']['Start']}",
                        amount=round(amount, 4),
                        currency=unit,
                        date=period_start,
                        description=f"AWS {service}",
                        vendor="AWS",
                        category="cloud",
                        transaction_type=txn_type,
                        metadata={
                            "service": service,
                            "granularity": granularity,
                            "is_waste_candidate": service in _WASTE_SERVICES,
                        },
                    )
                )

        logger.info("Fetched %d AWS cost records", len(transactions))
        return transactions

    def services(self) -> List[str]:
        """Return distinct AWS service names from the last 30 days."""
        end = date.today()
        start = end - timedelta(days=30)
        resp = self._ce.get_dimension_values(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Dimension="SERVICE",
        )
        return [item["Value"] for item in resp.get("DimensionValues", [])]

    def monthly_summary(self, months: int = 3) -> Dict[str, float]:
        """Return total spend per month (useful for trend display)."""
        end = date.today()
        start = end - timedelta(days=months * 31)
        resp = self._ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        return {
            p["TimePeriod"]["Start"]: float(
                p["Total"]["UnblendedCost"]["Amount"]
            )
            for p in resp.get("ResultsByTime", [])
        }
