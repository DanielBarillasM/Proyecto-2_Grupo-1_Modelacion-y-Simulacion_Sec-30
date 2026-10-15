"""Command-line entry point for reproducible, non-interactive executions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import default_config
from .simulation import simulate


def build_parser() -> argparse.ArgumentParser:
    """Define stable CLI arguments shared by users and automated checks."""

    parser = argparse.ArgumentParser(
        prog="ed-sim",
        description="Ejecuta la simulación base del departamento de emergencias.",
    )
    parser.add_argument("--seed", type=int, default=2026, help="Semilla entera.")
    parser.add_argument(
        "--arrival-multiplier",
        type=float,
        default=1.0,
        help="Multiplicador positivo aplicado a todas las tasas de llegada.",
    )
    parser.add_argument(
        "--capacity",
        type=int,
        nargs=6,
        metavar=("B0", "B1", "B2", "B3", "B4", "B5"),
        default=(3, 3, 4, 4, 5, 4),
        help="Seis capacidades para los bloques de cuatro horas.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Ruta opcional para guardar el resultado completo en JSON.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Omite las trazas de pacientes en el JSON guardado.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the baseline model and optionally persist auditable evidence."""

    args = build_parser().parse_args(argv)
    if args.arrival_multiplier <= 0:
        raise SystemExit("--arrival-multiplier debe ser mayor que cero")

    base = default_config()
    rates = tuple(rate * args.arrival_multiplier for rate in base.arrival_rates)
    config = default_config(
        seed=args.seed,
        arrival_rates=rates,
        capacity_schedule=tuple(args.capacity),
    )
    result = simulate(config)
    summary = json.dumps(result.metrics, ensure_ascii=False, indent=2)
    print(summary)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                result.to_dict(include_patients=not args.summary_only),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Resultado guardado en: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
