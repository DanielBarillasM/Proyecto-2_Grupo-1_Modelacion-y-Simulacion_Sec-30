"""Run the frozen schedule experiment without re-optimizing the candidate."""

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
    generate_evidence_bundle,
    load_frozen_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta base y candidata congelada con tres niveles de demanda, "
            "semillas pareadas y validación NHAMCS."
        )
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=ROOT / "evidence" / "final" / "frozen_candidate.json",
        help="JSON de candidata congelada.",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=ROOT / "data" / "processed",
        help="Directorio con tablas NHAMCS procesadas.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "evidence" / "final",
        help="Directorio para CSV, figuras y manifiesto.",
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=30,
        help="Réplicas independientes por condición (mínimo final: 30).",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=DEFAULT_EVALUATION_SEED_START,
        help="Primera semilla del conjunto final independiente.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Usa dos réplicas y evidence/smoke para una comprobación rápida.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke:
        args.replicates = 2
        if args.output_dir == ROOT / "evidence" / "final":
            args.output_dir = ROOT / "evidence" / "smoke"
    if not args.smoke and args.replicates < 30:
        raise SystemExit("la ejecución final requiere al menos 30 réplicas")
    candidate = load_frozen_candidate(args.candidate)
    paths = generate_evidence_bundle(
        args.processed_dir,
        args.output_dir,
        candidate,
        replicates=args.replicates,
        evaluation_seed_start=args.seed_start,
        git_commit=_git_commit(),
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
