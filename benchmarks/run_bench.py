"""
Proof Protocol — benchmark runner.

Usage:
    BASE_URL=https://your-app.onrender.com python benchmarks/run_bench.py

Outputs:
    benchmarks/results_latency.csv
    benchmarks/results_determinism.csv
"""

import csv
import os
import statistics
import sys
import time

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
N_TRIALS = int(os.getenv("N_TRIALS", "20"))
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# One representative snippet per world — keep them deterministic by default.
# The stochastic snippets have two versions: without seed and with seed.
DETERMINISTIC_SNIPPETS: dict[str, str] = {
    "llm": "print(sum(range(100)))",
    "symbolic": (
        "import sympy as sp\n"
        "x = sp.Symbol('x')\n"
        "print(str(sp.integrate(x**2, x)))\n"
    ),
    "formal": (
        "import z3\n"
        "s = z3.Solver()\n"
        "x = z3.Int('x')\n"
        "s.add(x > 2, x < 10)\n"
        "print('sat' if s.check() == z3.sat else 'unsat')\n"
    ),
    "bayesian": (
        "import random\n"
        "random.seed(42)\n"
        "samples = [random.gauss(0, 1) for _ in range(1000)]\n"
        "print(f'{sum(samples)/len(samples):.4f}')\n"
    ),
    "evolutionary": (
        "import random\n"
        "random.seed(0)\n"
        "pop = [random.random() for _ in range(50)]\n"
        "for _ in range(10):\n"
        "    pop = sorted(pop)[:25] + [random.random() for _ in range(25)]\n"
        "print(f'{min(pop):.4f}')\n"
    ),
    "multimodal": (
        "from PIL import Image\n"
        "img = Image.new('RGB', (128, 128), color=(73, 109, 137))\n"
        "thumb = img.resize((64, 64))\n"
        "print(thumb.size)\n"
    ),
    "neuro": (
        "import random\n"
        "random.seed(7)\n"
        "a = [random.random() for _ in range(100)]\n"
        "b = [random.random() for _ in range(100)]\n"
        "print(f'{sum(x*y for x,y in zip(a,b)):.4f}')\n"
    ),
}

# Stochastic snippets WITHOUT seed (for determinism rate experiment)
STOCHASTIC_SNIPPETS: dict[str, str] = {
    "bayesian": (
        "import random\n"
        "samples = [random.gauss(0, 1) for _ in range(1000)]\n"
        "print(f'{sum(samples)/len(samples):.4f}')\n"
    ),
    "evolutionary": (
        "import random\n"
        "pop = [random.random() for _ in range(50)]\n"
        "for _ in range(10):\n"
        "    pop = sorted(pop)[:25] + [random.random() for _ in range(25)]\n"
        "print(f'{min(pop):.4f}')\n"
    ),
    "neuro": (
        "import random\n"
        "a = [random.random() for _ in range(100)]\n"
        "b = [random.random() for _ in range(100)]\n"
        "print(f'{sum(x*y for x,y in zip(a,b)):.4f}')\n"
    ),
}


def prove(world: str, code: str) -> tuple[dict, float]:
    t0 = time.monotonic()
    resp = requests.post(
        f"{BASE_URL}/prove",
        json={"world": world, "claim": f"Benchmark for {world}", "code": code},
        timeout=TIMEOUT,
    )
    elapsed_ms = (time.monotonic() - t0) * 1000
    resp.raise_for_status()
    return resp.json(), elapsed_ms


def verify(hash_: str) -> tuple[dict, float]:
    t0 = time.monotonic()
    resp = requests.get(f"{BASE_URL}/verify/{hash_}", timeout=TIMEOUT)
    elapsed_ms = (time.monotonic() - t0) * 1000
    resp.raise_for_status()
    return resp.json(), elapsed_ms


def bench_latency() -> list[dict]:
    rows: list[dict] = []
    for world, code in DETERMINISTIC_SNIPPETS.items():
        print(f"  [{world}] latency benchmark ({N_TRIALS} trials)...")
        exec_times: list[float] = []
        verify_times: list[float] = []
        for _ in range(N_TRIALS):
            try:
                data, t_exec = prove(world, code)
                hash_ = data.get("hash") or data.get("cpo", {}).get("h", "")
                _, t_verify = verify(hash_)
                exec_times.append(t_exec)
                verify_times.append(t_verify)
            except Exception as exc:
                print(f"    WARNING: trial failed — {exc}", file=sys.stderr)

        if not exec_times:
            print(f"    SKIP: no successful trials for {world}", file=sys.stderr)
            continue

        rows.append(
            {
                "world": world,
                "n_trials": len(exec_times),
                "exec_median_ms": round(statistics.median(exec_times), 1),
                "exec_iqr_ms": round(
                    statistics.quantiles(exec_times, n=4)[2]
                    - statistics.quantiles(exec_times, n=4)[0],
                    1,
                ),
                "verify_median_ms": round(statistics.median(verify_times), 1),
                "verify_iqr_ms": round(
                    statistics.quantiles(verify_times, n=4)[2]
                    - statistics.quantiles(verify_times, n=4)[0],
                    1,
                ),
                "overhead_pct": round(
                    (statistics.median(verify_times) / statistics.median(exec_times) - 1) * 100,
                    1,
                ),
            }
        )
    return rows


def bench_determinism() -> list[dict]:
    rows: list[dict] = []

    # Deterministic worlds: seeded snippet, all should replay
    for world, code in DETERMINISTIC_SNIPPETS.items():
        if world in STOCHASTIC_SNIPPETS:
            continue
        print(f"  [{world}] determinism (deterministic, no seed needed)...")
        first_stdout: str | None = None
        matches = 0
        for _ in range(N_TRIALS):
            try:
                data, _ = prove(world, code)
                stdout = (data.get("cpo") or data).get("stdout", "").strip()
                if first_stdout is None:
                    first_stdout = stdout
                elif stdout == first_stdout:
                    matches += 1
            except Exception as exc:
                print(f"    WARNING: {exc}", file=sys.stderr)
        rate = round(matches / (N_TRIALS - 1) * 100, 1) if N_TRIALS > 1 else 100.0
        rows.append({"world": world, "type": "deterministic", "without_seed_pct": rate, "with_seed_pct": rate})

    # Stochastic worlds: without seed, then with seed
    for world, code_no_seed in STOCHASTIC_SNIPPETS.items():
        code_with_seed = DETERMINISTIC_SNIPPETS[world]

        for label, code in [("without_seed", code_no_seed), ("with_seed", code_with_seed)]:
            print(f"  [{world}] determinism ({label})...")
            first_stdout = None
            matches = 0
            for _ in range(N_TRIALS):
                try:
                    data, _ = prove(world, code)
                    stdout = (data.get("cpo") or data).get("stdout", "").strip()
                    if first_stdout is None:
                        first_stdout = stdout
                    elif stdout == first_stdout:
                        matches += 1
                except Exception as exc:
                    print(f"    WARNING: {exc}", file=sys.stderr)
            rates = round(matches / (N_TRIALS - 1) * 100, 1) if N_TRIALS > 1 else 100.0
            rows.append({
                "world": world,
                "type": "stochastic",
                label + "_pct": rates,
            })

    return rows


def write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  -> written {path}")


def main() -> None:
    print(f"Proof Protocol benchmark  BASE_URL={BASE_URL}  N_TRIALS={N_TRIALS}\n")

    print("=== Latency ===")
    latency_rows = bench_latency()
    write_csv("benchmarks/results_latency.csv", latency_rows)

    print("\n=== Determinism ===")
    det_rows = bench_determinism()
    write_csv("benchmarks/results_determinism.csv", det_rows)

    print("\nDone.")


if __name__ == "__main__":
    main()
