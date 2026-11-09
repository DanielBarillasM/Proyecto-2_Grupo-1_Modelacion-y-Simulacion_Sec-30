"""Genera las tablas, macros y figuras del informe a partir de ``evidence/final/``.

Regla editorial del proyecto: ninguna cifra del informe se copia a mano.
Todo número que aparece en ``report/`` proviene de este script, que solo lee
los CSV/JSON congelados de ``evidence/final/``.

Salidas (todas relativas a la raíz del repositorio):

- ``report/generated/macros.tex``      macros ``\\newcommand`` con cifras clave
- ``report/generated/tab_*.tex``       tablas listas para ``\\input``
- ``report/figures/*.pdf``             figuras SVG de la evidencia convertidas a PDF

Uso::

    python scripts/build_report_assets.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PROCESSED = ROOT / "data" / "processed"
EVIDENCE = ROOT / "evidence" / "final"
GENERATED = ROOT / "report" / "generated"
FIGURES = ROOT / "report" / "figures"

DEMAND_LABEL = {0.8: "Bajo (0.80)", 1.0: "Nominal (1.00)", 1.2: "Alto (1.20)"}
DEMAND_KEY = {0.8: "Low", 1.0: "Nom", 1.2: "High"}
BLOCKS = ["00--04", "04--08", "08--12", "12--16", "16--20", "20--24"]


# ----------------------------------------------------------------- utilidades
def f2(x: float) -> str:
    """Formatea con dos decimales y signo menos tipográfico."""
    return f"{x:.2f}".replace("-", "$-$")


def f1(x: float) -> str:
    return f"{x:.1f}".replace("-", "$-$")


def f3(x: float) -> str:
    return f"{x:.3f}".replace("-", "$-$")


def ci(low: float, high: float, digits: int = 2) -> str:
    fmt = {1: f1, 2: f2, 3: f3}[digits]
    return f"[{fmt(low)}, {fmt(high)}]"


def write(name: str, text: str) -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / name).write_text(text, encoding="utf-8")


def tabular(header: list[str], rows: list[list[str]], spec: str) -> str:
    lines = [rf"\begin{{tabular}}{{{spec}}}", r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    for r in rows:
        lines.append(r"\midrule" if r == ["MIDRULE"] else " & ".join(r) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- carga
def load() -> dict:
    return {
        "summary": pd.read_csv(EVIDENCE / "summary.csv"),
        "paired": pd.read_csv(EVIDENCE / "paired_summary.csv"),
        "validation": pd.read_csv(EVIDENCE / "validation_comparison.csv"),
        "runs": pd.read_csv(EVIDENCE / "runs.csv"),
        "manifest": json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8")),
        "frozen": json.loads((EVIDENCE / "frozen_candidate.json").read_text(encoding="utf-8")),
    }


def paired_row(paired: pd.DataFrame, demand: float, metric: str) -> pd.Series:
    sel = paired[(paired.demand_multiplier == demand) & (paired.metric == metric)]
    assert len(sel) == 1, (demand, metric)
    return sel.iloc[0]


def summary_row(summary: pd.DataFrame, schedule: str, demand: float, metric: str) -> pd.Series:
    sel = summary[
        (summary.schedule_id == schedule) & (summary.demand_multiplier == demand) & (summary.metric == metric)
    ]
    assert len(sel) == 1, (schedule, demand, metric)
    return sel.iloc[0]


# ------------------------------------------------------------------ tablas
def table_schedules(d: dict) -> None:
    base = d["manifest"]["schedules"]["base"]
    cand = d["manifest"]["schedules"]["candidate"]
    rows = [
        ["Base"] + [str(v) for v in base] + [str(sum(base))],
        ["Candidata congelada"] + [str(v) for v in cand] + [str(sum(cand))],
    ]
    write("tab_schedules.tex", tabular(["Horario"] + BLOCKS + ["Total"], rows, "lrrrrrrr"))


def table_paired_mean_wait(d: dict) -> None:
    rows = []
    for demand in (0.8, 1.0, 1.2):
        p = paired_row(d["paired"], demand, "mean_wait_minutes")
        rows.append(
            [
                DEMAND_LABEL[demand],
                f2(p.base_mean),
                f2(p.candidate_mean),
                f2(p.mean_improvement_base_minus_candidate),
                f1(p.aggregate_improvement_percent),
                ci(p.ci95_low, p.ci95_high),
                f"{int(p.positive_pairs)}/{int(p.n_pairs)}",
            ]
        )
    header = [
        "Demanda",
        "Base (min)",
        "Candidata (min)",
        "Reducción (min)",
        "Reducción (\\%)",
        "IC 95\\,\\% pareado (min)",
        "Pares favorables",
    ]
    write("tab_paired_mean_wait.tex", tabular(header, rows, "lrrrrrr"))


METRIC_NAMES = {
    "mean_wait_minutes": ("Espera media", "min", 2),
    "median_wait_minutes": ("Mediana de espera", "min", 2),
    "p90_wait_minutes": ("Percentil 90 de espera", "min", 2),
    "share_wait_over_60": ("Proporción con espera $>$ 60 min", "prop.", 3),
    "mean_queue": ("Cola media", "pacientes", 2),
    "maximum_queue": ("Cola máxima", "pacientes", 2),
}


def table_nominal(d: dict) -> None:
    rows = []
    for metric, (label, unit, digits) in METRIC_NAMES.items():
        p = paired_row(d["paired"], 1.0, metric)
        fmt = {2: f2, 3: f3}[digits]
        rows.append(
            [
                label,
                unit,
                fmt(p.base_mean),
                fmt(p.candidate_mean),
                fmt(-p.mean_improvement_base_minus_candidate),
                f1(-p.aggregate_improvement_percent),
                ci(p.ci95_low, p.ci95_high, digits),
            ]
        )
    ub = summary_row(d["summary"], "base", 1.0, "resource_utilization")
    uc = summary_row(d["summary"], "candidate", 1.0, "resource_utilization")
    rows.append(
        [
            "Utilización efectiva",
            "prop.",
            f3(ub["mean"]),
            f3(uc["mean"]),
            f3(uc["mean"] - ub["mean"]),
            f1(100 * (uc["mean"] - ub["mean"]) / ub["mean"]),
            "---",
        ]
    )
    header = [
        "Métrica",
        "Unidad",
        "Base",
        "Candidata",
        "Cambio",
        "Cambio (\\%)",
        "IC 95\\,\\% de la reducción",
    ]
    write("tab_nominal.tex", tabular(header, rows, "llrrrrr"))


def table_secondary_by_demand(d: dict) -> None:
    rows = []
    for metric in ("p90_wait_minutes", "share_wait_over_60", "mean_queue"):
        label, unit, digits = METRIC_NAMES[metric]
        fmt = {2: f2, 3: f3}[digits]
        for demand in (0.8, 1.0, 1.2):
            p = paired_row(d["paired"], demand, metric)
            rows.append(
                [
                    label if demand == 0.8 else "",
                    DEMAND_LABEL[demand],
                    fmt(p.base_mean),
                    fmt(p.candidate_mean),
                    fmt(p.mean_improvement_base_minus_candidate),
                    ci(p.ci95_low, p.ci95_high, digits),
                ]
            )
        if metric != "mean_queue":
            rows.append(["MIDRULE"])
    body = tabular(
        ["Métrica", "Demanda", "Base", "Candidata", "Reducción", "IC 95\\,\\% pareado"],
        rows,
        "llrrrr",
    )
    write("tab_secondary_by_demand.tex", body)


def table_validation(d: dict) -> None:
    labels = {
        "mean_wait_minutes": ("Espera media", "min"),
        "median_wait_minutes": ("Mediana", "min"),
        "p90_wait_minutes": ("Percentil 90", "min"),
        "share_wait_over_60": ("Proporción $>$ 60 min", "prop."),
    }
    rows = []
    for _, r in d["validation"].iterrows():
        label, unit = labels[r.metric]
        digits = 3 if r.metric == "share_wait_over_60" else 2
        fmt = {2: f2, 3: f3}[digits]
        ref = fmt(r.reference_value)
        if pd.notna(r.reference_ci95_low):
            ref += f" {ci(r.reference_ci95_low, r.reference_ci95_high, digits)}"
        rows.append(
            [
                label,
                unit,
                ref,
                fmt(r.base_simulation_mean),
                fmt(r.candidate_simulation_mean),
                fmt(r.base_absolute_error),
                fmt(r.candidate_absolute_error),
            ]
        )
    header = [
        "Métrica",
        "Unidad",
        "NHAMCS 2022 (IC 95\\,\\%)",
        "Sim. base",
        "Sim. candidata",
        "Error abs. base",
        "Error abs. candidata",
    ]
    write("tab_validation.tex", tabular(header, rows, "llrrrrr"))


def table_conditions(d: dict) -> None:
    rows = []
    for demand in (0.8, 1.0, 1.2):
        for schedule, name in (("base", "Base"), ("candidate", "Candidata")):
            s = summary_row(d["summary"], schedule, demand, "mean_wait_minutes")
            dr = summary_row(d["summary"], schedule, demand, "drain_minutes")
            ut = summary_row(d["summary"], schedule, demand, "resource_utilization")
            rows.append(
                [
                    DEMAND_LABEL[demand] if schedule == "base" else "",
                    name,
                    str(int(s.n)),
                    f2(s["mean"]),
                    f2(s["std"]),
                    ci(s.ci95_low, s.ci95_high),
                    f1(dr["mean"]),
                    f3(ut["mean"]),
                ]
            )
    header = [
        "Demanda",
        "Horario",
        "$n$",
        "Espera media (min)",
        "Desv. est. (min)",
        "IC 95\\,\\% (min)",
        "Drenaje (min)",
        "Utilización",
    ]
    write("tab_conditions.tex", tabular(header, rows, "llrrrrrr"))


def table_ga(d: dict) -> None:
    ga = d["manifest"]["genetic_algorithm"]
    opt = d["frozen"]["optimization"]
    rows = [
        ["Población", str(ga["population_size"])],
        ["Generaciones máximas", str(ga["generations"])],
        ["Probabilidad de cruce", str(ga["crossover_probability"])],
        ["Probabilidad de mutación", str(ga["mutation_probability"])],
        ["Élites", str(ga["elitism"])],
        ["Tamaño de torneo", str(ga["tournament_size"])],
        ["Paciencia (generaciones)", str(ga["patience"])],
        ["Réplicas por candidata", str(ga["evaluation_replicates"])],
        ["Semilla del algoritmo", str(ga["algorithm_seed"])],
        ["Horarios evaluados", str(opt["evaluated_schedules"])],
        ["Detención temprana", "sí" if opt["stopped_early"] else "no"],
    ]
    write("tab_ga.tex", tabular(["Parámetro", "Valor"], rows, "lr"))



def table_blocks(d: dict) -> None:
    """Llegadas esperadas por bloque (demanda nominal) junto con ambos horarios."""
    hourly = pd.read_csv(PROCESSED / "nhamcs_2022_hourly_profile.csv")
    volume = pd.read_csv(PROCESSED / "nhamcs_2022_reference_volume.csv").set_index("statistic")
    daily = float(volume.loc["median_ed", "daily_visits"])
    base = d["manifest"]["schedules"]["base"]
    cand = d["manifest"]["schedules"]["candidate"]
    hourly["block"] = hourly["hour"] // 4
    share = hourly.groupby("block")["share"].sum()
    rows = []
    for b, label in enumerate(BLOCKS):
        rows.append(
            [
                label,
                f1(100 * share[b]),
                f1(daily * share[b]),
                str(base[b]),
                str(cand[b]),
            ]
        )
    header = [
        "Bloque (h)",
        "Llegadas (\\% del día)",
        "Llegadas esperadas (pac./bloque)",
        "Base (equipos)",
        "Candidata (equipos)",
    ]
    write("tab_blocks.tex", tabular(header, rows, "lrrrr"))
    write_macro_lines(
        [("DailyVolume", f2(daily)), ("DailyVolumeRound", f"{daily:.0f}")]
    )


def table_triage() -> None:
    """Probabilidades de triaje derivadas y medianas de servicio supuestas."""
    from ed_simulation.config import SimulationConfig

    cfg = SimulationConfig()
    tri = pd.read_csv(PROCESSED / "nhamcs_2022_triage_profile.csv")
    proxy = pd.read_csv(PROCESSED / "nhamcs_2022_service_proxy.csv").set_index("triage_level")
    rows = []
    for _, r in tri.iterrows():
        k = int(r.triage_level)
        rows.append(
            [
                f"{k} ({r.label})",
                f1(100 * r.share),
                str(int(r.n_unweighted)),
                f"{cfg.service_medians_minutes[k - 1]:.0f}",
                f"{proxy.loc[k, 'median_minutes']:.0f}",
            ]
        )
    header = [
        "Triaje",
        "Probabilidad (\\%)",
        "$n$ sin ponderar",
        "Mediana de servicio supuesta (min)",
        "Proxy \\texttt{LOV} (mediana, min)",
    ]
    write("tab_triage.tex", tabular(header, rows, "lrrrr"))
    write_macro_lines([("ServiceSigma", f"{cfg.service_sigma:.2f}")])


_EXTRA_MACROS: list[tuple[str, str]] = []


def write_macro_lines(pairs: list[tuple[str, str]]) -> None:
    _EXTRA_MACROS.extend(pairs)


# ------------------------------------------------------------------ macros
def macros(d: dict) -> None:
    lines = ["% Generado por scripts/build_report_assets.py. No editar a mano."]

    def add(name: str, value: str) -> None:
        lines.append(rf"\newcommand{{\{name}}}{{{value}}}")

    runs = d["runs"]
    add("NReps", str(int(runs.groupby("condition_id").size().min())))
    add("NRuns", str(len(runs)))
    add("NConditions", str(runs.condition_id.nunique()))
    seeds = d["manifest"]["seeds"]
    add("OptSeedFirst", str(min(seeds["optimization"])))
    add("OptSeedLast", str(max(seeds["optimization"])))
    add("EvalSeedFirst", str(min(seeds["evaluation"])))
    add("EvalSeedLast", str(max(seeds["evaluation"])))
    add("AlgSeed", str(seeds["algorithm"]))
    add("GitCommit", d["manifest"]["git_commit_of_generator"][:7])
    add("PythonVersion", d["manifest"]["python"])
    add("AllDrained", "sí" if int(runs.drain_complete.min()) == 1 else "no")
    add("MaxNotStarted", str(int(runs.not_started_at_end.max())))

    for demand, key in DEMAND_KEY.items():
        p = paired_row(d["paired"], demand, "mean_wait_minutes")
        add(f"WaitBase{key}", f2(p.base_mean))
        add(f"WaitCand{key}", f2(p.candidate_mean))
        add(f"Red{key}", f2(p.mean_improvement_base_minus_candidate))
        add(f"RedPct{key}", f1(p.aggregate_improvement_percent))
        add(f"RedCILow{key}", f2(p.ci95_low))
        add(f"RedCIHigh{key}", f2(p.ci95_high))
        add(f"PairsPos{key}", str(int(p.positive_pairs)))
        dr_b = summary_row(d["summary"], "base", demand, "drain_minutes")
        dr_c = summary_row(d["summary"], "candidate", demand, "drain_minutes")
        add(f"DrainBase{key}", f1(dr_b["mean"]))
        add(f"DrainCand{key}", f1(dr_c["mean"]))

    for metric, tag in (
        ("median_wait_minutes", "Median"),
        ("p90_wait_minutes", "Pninety"),
        ("share_wait_over_60", "Share"),
        ("mean_queue", "Queue"),
    ):
        p = paired_row(d["paired"], 1.0, metric)
        digits = f3 if metric == "share_wait_over_60" else f2
        add(f"NomBase{tag}", digits(p.base_mean))
        add(f"NomCand{tag}", digits(p.candidate_mean))
        add(f"NomRed{tag}", digits(p.mean_improvement_base_minus_candidate))
        add(f"NomRedPct{tag}", f1(p.aggregate_improvement_percent))

    # Variación entre días simulados (desviación estándar marginal, demanda nominal).
    sb = summary_row(d["summary"], "base", 1.0, "mean_wait_minutes")
    sc = summary_row(d["summary"], "candidate", 1.0, "mean_wait_minutes")
    add("StdBaseNom", f2(sb["std"]))
    add("StdCandNom", f2(sc["std"]))
    add("MargBaseLow", f2(sb.ci95_low))
    add("MargBaseHigh", f2(sb.ci95_high))
    add("MargCandLow", f2(sc.ci95_low))
    add("MargCandHigh", f2(sc.ci95_high))

    v = d["validation"].set_index("metric")
    add("RefMeanWait", f2(v.loc["mean_wait_minutes", "reference_value"]))
    add("RefMedianWait", f2(v.loc["median_wait_minutes", "reference_value"]))
    add("RefPninetyWait", f2(v.loc["p90_wait_minutes", "reference_value"]))
    add("RefShare", f3(v.loc["share_wait_over_60", "reference_value"]))
    add("RefMeanCILow", f2(v.loc["mean_wait_minutes", "reference_ci95_low"]))
    add("RefMeanCIHigh", f2(v.loc["mean_wait_minutes", "reference_ci95_high"]))
    add("RefN", f"{int(v.loc['mean_wait_minutes', 'reference_n_unweighted']):,}".replace(",", r"\,"))
    add("MedianCandErr", f2(v.loc["median_wait_minutes", "candidate_absolute_error"]))
    add("PninetyCandErr", f2(v.loc["p90_wait_minutes", "candidate_absolute_error"]))
    diag = d["manifest"]["validation_diagnostics"]
    add("MaeBase", f2(diag["base_mae_minutes"]))
    add("MaeCand", f2(diag["candidate_mae_minutes"]))
    add("MaePropBase", f3(diag["base_mae_proportion_points"]))
    add("MaePropCand", f3(diag["candidate_mae_proportion_points"]))

    # Generalización: objetivo en semillas de optimización frente a evaluación.
    opt = d["frozen"]["optimization"]
    add("OptBaseWait", f2(opt["baseline"]["mean_wait_minutes"]))
    add("OptCandWait", f2(opt["best"]["mean_wait_minutes"]))
    add("OptObjBase", f2(opt["baseline"]["objective"]))
    add("OptObjCand", f2(opt["best"]["objective"]))
    add("OptRelPct", f1(100 * opt["relative_improvement"]))
    add("OptEvaluated", str(opt["evaluated_schedules"]))
    add("OptGenerations", str(len(opt["history"])))

    for name, value in _EXTRA_MACROS:
        add(name, value)
    write("macros.tex", "\n".join(lines) + "\n")


# ----------------------------------------------------------------- figuras
def figures() -> None:
    try:
        import cairosvg
    except ImportError:  # pragma: no cover - depende del entorno
        print("AVISO: cairosvg no está instalado; no se convirtieron las figuras SVG a PDF.")
        print("       Instale con: python -m pip install cairosvg")
        return
    FIGURES.mkdir(parents=True, exist_ok=True)
    for svg in sorted((EVIDENCE / "figures").glob("*.svg")):
        target = FIGURES / f"{svg.stem}.pdf"
        cairosvg.svg2pdf(url=str(svg), write_to=str(target))
        print(f"figura: {target.relative_to(ROOT)}")


def main() -> None:
    d = load()
    table_schedules(d)
    table_paired_mean_wait(d)
    table_nominal(d)
    table_secondary_by_demand(d)
    table_validation(d)
    table_conditions(d)
    table_ga(d)
    table_blocks(d)
    table_triage()
    macros(d)
    figures()
    print(f"tablas y macros escritos en {GENERATED.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
