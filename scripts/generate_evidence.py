"""Freeze a calibrated candidate, then generate the final evidence bundle."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ed_simulation.evidence import (  # noqa: E402
    DEFAULT_EVALUATION_SEED_START,
    freeze_candidate,
    generate_evidence_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Optimiza con semillas de selección, congela la candidata y la "
            "evalúa con un conjunto independiente."
        )
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=ROOT / "data" / "processed",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "evidence" / "final",
    )
    parser.add_argument("--replicates", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_EVALUATION_SEED_START)
    parser.add_argument("--smoke", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke:
        args.replicates = 2
        if args.output_dir == ROOT / "evidence" / "final":
            args.output_dir = ROOT / "evidence" / "smoke"
    elif args.replicates < 30:
        raise SystemExit("la ejecución final requiere al menos 30 réplicas")

    candidate = freeze_candidate(
        args.processed_dir,
        population_size=8 if args.smoke else 24,
        generations=3 if args.smoke else 20,
        optimization_replicates=2 if args.smoke else 10,
        evaluation_seed_start=args.seed_start,
    )
    paths = generate_evidence_bundle(
        args.processed_dir,
        args.output_dir,
        candidate,
        replicates=args.replicates,
        evaluation_seed_start=args.seed_start,
        git_commit=_git_commit(),
    )
    print(
        "Candidata congelada:",
        candidate["candidate_schedule"],
        "| base:",
        candidate["baseline_schedule"],
    )
    print(f"Condiciones: 6; réplicas por condición: {args.replicates}")
    for name, path in sorted(paths.items()):
        print(f"{name}: {path}")
    return 0


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
