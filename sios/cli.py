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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
