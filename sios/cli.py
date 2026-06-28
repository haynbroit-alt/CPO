"""SIOS CLI — detect hidden financial losses in under 2 minutes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
except ImportError:
    print("Run: pip install typer")
    sys.exit(1)

from sios.pipeline import run_file

app = typer.Typer(
    name="sios",
    help="SIOS — find hidden financial losses in your data. Proved, not predicted.",
    add_completion=False,
)

_FINDING_LABELS = {
    "duplicate_payment":     "Duplicate payment",
    "unused_subscription":   "Unused subscription",
    "cost_anomaly":          "Cost anomaly",
    "cloud_waste":           "Cloud waste",
    "tax_credit":            "Tax credit opportunity",
    "public_grant":          "Public grant",
}


def _label(finding_type: str) -> str:
    return _FINDING_LABELS.get(finding_type, finding_type.replace("_", " ").title())


@app.command()
def run(
    file: Path = typer.Argument(..., help="CSV or JSON file to audit"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Only print estimated savings"),
) -> None:
    """Run a full financial audit on a CSV or JSON file."""
    if not file.exists():
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(1)

    typer.echo(f"\nAnalyzing {file.name} ...", err=True)

    try:
        result = run_file(file)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    if not result.findings:
        typer.echo("\nNo findings. Your data looks clean.")
        raise typer.Exit(0)

    if not quiet:
        typer.echo(f"\n{'─' * 52}")
        typer.echo(f"  SIOS Audit — {file.name}")
        typer.echo(f"  {result.dataset_rows} transactions analyzed")
        typer.echo(f"{'─' * 52}")

        for f in sorted(result.findings, key=lambda x: x.estimated_amount or 0, reverse=True):
            label = _label(f.type.value)
            amount = f"  {f.estimated_amount:,.0f} {f.currency}" if f.estimated_amount else ""
            conf = f"(conf: {f.confidence:.0%})"
            typer.echo(f"\n  [{label}]{amount}")
            typer.echo(f"  {f.title}  {conf}")
            if f.description:
                typer.echo(f"  {f.description[:120]}")

        typer.echo(f"\n{'─' * 52}")
        typer.echo(
            f"  Estimated recoverable: "
            f"{result.estimated_savings:,.0f} {result.currency}"
        )
        typer.echo(f"  Findings: {len(result.findings)}")
        typer.echo(f"{'─' * 52}\n")
    else:
        typer.echo(f"{result.estimated_savings:.2f} {result.currency}")

    if output:
        out = Path(output)
        out.write_text(json.dumps(result.to_dict(), indent=2))
        typer.echo(f"Results saved to {output}", err=True)


@app.command()
def detect(
    file: Path = typer.Argument(..., help="CSV or JSON file to analyze"),
    fmt: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
) -> None:
    """Detect financial anomalies and print results."""
    try:
        result = run_file(file)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    if fmt == "json":
        typer.echo(json.dumps(result.to_dict(), indent=2))
    elif fmt == "csv":
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["type", "title", "estimated_amount", "currency", "confidence"])
        for f in result.findings:
            w.writerow([f.type.value, f.title, f.estimated_amount, f.currency, f.confidence])
        typer.echo(buf.getvalue().strip())
    else:
        if not result.findings:
            typer.echo("No findings.")
            return
        for f in result.findings:
            typer.echo(
                f"  {_label(f.type.value):<28} "
                f"{f.estimated_amount or 0:>8,.0f} {f.currency}  "
                f"conf={f.confidence:.0%}"
            )
        typer.echo(f"\n  Total: {result.estimated_savings:,.0f} {result.currency}")


@app.command()
def prove(
    file: Path = typer.Argument(..., help="CSV or JSON file to audit and prove"),
    node: str = typer.Option(
        "http://localhost:8000", "--node", "-n",
        help="Proof Protocol node URL"
    ),
) -> None:
    """Run audit and generate verifiable CPO proofs for each finding."""
    try:
        import requests
    except ImportError:
        typer.echo("Run: pip install requests", err=True)
        raise typer.Exit(1)

    result = run_file(file)
    if not result.findings:
        typer.echo("No findings to prove.")
        return

    typer.echo(f"\nGenerating proofs via {node} ...\n")
    for f in result.findings:
        code = (
            f"# SIOS proof: {f.type.value}\n"
            f"finding = {{'type': {f.type.value!r}, 'amount': {f.estimated_amount}, "
            f"'confidence': {f.confidence}}}\n"
            f"print(finding)\n"
        )
        try:
            resp = requests.post(
                f"{node}/prove",
                json={"world": "llm", "claim": f"[sios] {f.title}", "code": code},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            typer.echo(f"  {f.title[:45]:<45}  CPO: {data.get('cpo_id', '?')[:12]}...")
        except Exception as exc:
            typer.echo(f"  {f.title[:45]:<45}  ERROR: {exc}")

    typer.echo(f"\n{len(result.findings)} proofs generated.\n")


@app.command()
def export(
    file: Path = typer.Argument(..., help="CSV or JSON file to audit"),
    fmt: str = typer.Option("json", "--format", "-f", help="Export format: json, csv"),
    out: Path = typer.Option(
        Path("sios_report.json"), "--out", "-o", help="Output file path"
    ),
) -> None:
    """Export audit results to a file."""
    result = run_file(file)
    data = result.to_dict()

    if fmt == "csv":
        import csv, io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["type", "title", "estimated_amount", "currency", "confidence"])
        w.writeheader()
        w.writerows(data["findings"])
        out.with_suffix(".csv").write_text(buf.getvalue())
        typer.echo(f"Exported {len(data['findings'])} findings to {out.with_suffix('.csv')}")
    else:
        out.write_text(json.dumps(data, indent=2))
        typer.echo(f"Exported {len(data['findings'])} findings to {out}")


@app.command()
def aws(
    days: int = typer.Option(90, "--days", "-d", help="Look-back window in days"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="AWS profile (~/.aws/credentials)"),
    region: str = typer.Option("us-east-1", "--region", "-r", help="AWS region"),
    save: Optional[Path] = typer.Option(None, "--save", "-s", help="Save raw transactions to CSV"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save findings to JSON file"),
) -> None:
    """Pull AWS Cost Explorer data and detect cloud waste + anomalies."""
    try:
        from sios.connectors.aws import AWSConnector
    except ImportError:
        typer.echo("AWS connector requires boto3. Run: pip install sios[aws]", err=True)
        raise typer.Exit(1)

    typer.echo(f"\nConnecting to AWS Cost Explorer (last {days} days) ...", err=True)
    try:
        connector = AWSConnector(profile=profile, region=region)
        transactions = connector.fetch(days=days)
    except Exception as exc:
        typer.echo(f"AWS error: {exc}", err=True)
        raise typer.Exit(1)

    if not transactions:
        typer.echo("No cost data found.")
        raise typer.Exit(0)

    typer.echo(f"  {len(transactions)} cost records fetched", err=True)

    if save:
        _save_transactions_csv(transactions, save)

    from sios.value_engine.engine import ValueEngine
    findings = ValueEngine().run(transactions)
    _print_findings(findings, source="AWS Cost Explorer")

    if output:
        from sios.pipeline import AuditResult
        result = AuditResult(
            findings=findings,
            estimated_savings=sum(f.estimated_amount for f in findings if f.estimated_amount),
            currency=findings[0].currency if findings else "USD",
            dataset_rows=len(transactions),
        )
        Path(output).write_text(json.dumps(result.to_dict(), indent=2))
        typer.echo(f"Saved to {output}", err=True)


@app.command()
def stripe(
    days: int = typer.Option(90, "--days", "-d", help="Look-back window in days"),
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="Stripe secret key (or STRIPE_API_KEY env)"),
    include_subs: bool = typer.Option(True, "--subscriptions/--no-subscriptions", help="Include active subscriptions"),
    save: Optional[Path] = typer.Option(None, "--save", "-s", help="Save raw transactions to CSV"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save findings to JSON file"),
) -> None:
    """Pull Stripe charges and detect duplicate billing + anomalies."""
    try:
        from sios.connectors.stripe import StripeConnector
    except ImportError:
        typer.echo("Stripe connector requires stripe. Run: pip install sios[stripe]", err=True)
        raise typer.Exit(1)

    typer.echo(f"\nConnecting to Stripe (last {days} days) ...", err=True)
    try:
        connector = StripeConnector(api_key=api_key)
        transactions = connector.fetch(days=days)
        if include_subs:
            transactions += connector.fetch_subscriptions()
    except Exception as exc:
        typer.echo(f"Stripe error: {exc}", err=True)
        raise typer.Exit(1)

    if not transactions:
        typer.echo("No charges found.")
        raise typer.Exit(0)

    typer.echo(f"  {len(transactions)} records fetched", err=True)

    if save:
        _save_transactions_csv(transactions, save)

    from sios.value_engine.engine import ValueEngine
    findings = ValueEngine().run(transactions)
    _print_findings(findings, source="Stripe")

    if output:
        from sios.pipeline import AuditResult
        result = AuditResult(
            findings=findings,
            estimated_savings=sum(f.estimated_amount for f in findings if f.estimated_amount),
            currency=findings[0].currency if findings else "EUR",
            dataset_rows=len(transactions),
        )
        Path(output).write_text(json.dumps(result.to_dict(), indent=2))
        typer.echo(f"Saved to {output}", err=True)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _print_findings(findings, source: str = "") -> None:
    if not findings:
        typer.echo(f"\nNo findings detected in {source}.")
        return

    total = sum(f.estimated_amount for f in findings if f.estimated_amount)
    currency = findings[0].currency if findings else "EUR"

    typer.echo(f"\n{'─' * 52}")
    if source:
        typer.echo(f"  SIOS Audit — {source}")
    typer.echo(f"{'─' * 52}")

    for f in sorted(findings, key=lambda x: x.estimated_amount or 0, reverse=True):
        amount = f"  {f.estimated_amount:,.0f} {f.currency}" if f.estimated_amount else ""
        typer.echo(f"\n  [{_label(f.type.value)}]{amount}  (conf: {f.confidence:.0%})")
        typer.echo(f"  {f.title}")

    typer.echo(f"\n{'─' * 52}")
    typer.echo(f"  Estimated recoverable: {total:,.0f} {currency}")
    typer.echo(f"  Findings: {len(findings)}")
    typer.echo(f"{'─' * 52}\n")


def _save_transactions_csv(transactions, path: Path) -> None:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "amount", "currency", "vendor", "description", "category", "source_id"])
    for t in transactions:
        w.writerow([
            t.date.date() if hasattr(t.date, "date") else t.date,
            t.amount, t.currency, t.vendor, t.description,
            t.category or "", t.source_id or "",
        ])
    path.write_text(buf.getvalue())
    typer.echo(f"Saved {len(transactions)} transactions to {path}", err=True)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
