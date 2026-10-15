"""Command-line entry point for reproducible, non-interactive executions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import default_config
from .optimization import GAConfig, OptimizationConstraints, optimize_staffing
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
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Ejecuta el algoritmo genético sobre la capacidad indicada.",
    )
    parser.add_argument(
        "--population",
        type=int,
        default=24,
        help="Tamaño de población cuando se usa --optimize.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=20,
        help="Máximo de generaciones cuando se usa --optimize.",
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=3,
        help="Réplicas por candidato con semillas comunes.",
    )
    parser.add_argument(
        "--algorithm-seed",
        type=int,
        default=9101,
        help="Semilla de selección, cruce y mutación.",
    )
    parser.add_argument(
        "--min-capacity",
        type=int,
        default=1,
        help="Mínimo permitido por bloque.",
    )
    parser.add_argument(
        "--max-capacity",
        type=int,
        default=8,
        help="Máximo permitido por bloque.",
    )
    parser.add_argument(
        "--max-step-change",
        type=int,
        default=3,
        help="Cambio máximo entre bloques consecutivos.",
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
    if args.optimize:
        constraints = OptimizationConstraints(
            blocks=len(config.capacity_schedule),
            total_capacity_units=sum(config.capacity_schedule),
            min_capacity=args.min_capacity,
            max_capacity=args.max_capacity,
            max_step_change=args.max_step_change,
        )
        ga_config = GAConfig(
            population_size=args.population,
            generations=args.generations,
            evaluation_replicates=args.replicates,
            algorithm_seed=args.algorithm_seed,
        )
        optimization = optimize_staffing(config, constraints, ga_config)
        payload = optimization.to_dict()
        summary_payload = {
            "baseline_schedule": payload["baseline"]["schedule"],
            "best_schedule": payload["best"]["schedule"],
            "baseline_objective": payload["baseline"]["objective"],
            "best_objective": payload["best"]["objective"],
            "relative_improvement": payload["relative_improvement"],
            "feasible": payload["best"]["feasible"],
            "evaluated_schedules": payload["evaluated_schedules"],
        }
        print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    else:
        result = simulate(config)
        payload = result.to_dict(include_patients=not args.summary_only)
        print(json.dumps(result.metrics, ensure_ascii=False, indent=2))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Resultado guardado en: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
