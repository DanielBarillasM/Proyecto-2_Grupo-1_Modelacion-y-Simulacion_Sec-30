"""Pure Plotly figures shared by Streamlit pages and tests."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


BLOCK_LABELS = ("00–04", "04–08", "08–12", "12–16", "16–20", "20–24")
BASE_COLOR = "#256D85"
CANDIDATE_COLOR = "#0F8B7C"
REFERENCE_COLOR = "#6B7280"


def timeline_figure(result) -> go.Figure:
    """Compare realized hourly arrivals and configured teams."""

    capacities = [
        result.config.capacity_schedule[hour // result.config.block_hours]
        for hour in range(24)
    ]
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_bar(
        x=list(range(24)),
        y=result.hourly_arrivals,
        name="Llegadas",
        marker_color=BASE_COLOR,
        hovertemplate="Hora %{x}:00<br>%{y} pacientes<extra></extra>",
        secondary_y=False,
    )
    figure.add_scatter(
        x=list(range(24)),
        y=capacities,
        name="Equipos",
        mode="lines",
        line={"color": "#B45309", "width": 3, "shape": "hv"},
        hovertemplate="Hora %{x}:00<br>%{y} equipos<extra></extra>",
        secondary_y=True,
    )
    _base_layout(figure, "Llegadas y capacidad durante el día")
    figure.update_xaxes(title="Hora", dtick=2)
    figure.update_yaxes(title="Pacientes por hora", secondary_y=False)
    figure.update_yaxes(title="Equipos", rangemode="tozero", secondary_y=True)
    return figure


def wait_distribution_figure(result) -> go.Figure:
    """Show complete waits after terminal drain."""

    waits = [patient.wait_minutes for patient in result.patients]
    figure = go.Figure(
        go.Histogram(
            x=waits,
            nbinsx=24,
            marker_color=CANDIDATE_COLOR,
            hovertemplate="Espera %{x:.1f} min<br>%{y} pacientes<extra></extra>",
        )
    )
    figure.add_vline(
        x=60,
        line_dash="dash",
        line_color="#B42318",
        annotation_text="60 min",
    )
    _base_layout(figure, "Distribución de espera completa")
    figure.update_xaxes(title="Espera hasta atención (min)")
    figure.update_yaxes(title="Pacientes")
    return figure


def schedule_figure(base: tuple[int, ...], candidate: tuple[int, ...]) -> go.Figure:
    """Compare frozen integer schedules."""

    figure = go.Figure()
    figure.add_bar(x=BLOCK_LABELS, y=base, name="Base", marker_color=BASE_COLOR)
    figure.add_bar(
        x=BLOCK_LABELS,
        y=candidate,
        name="Candidata",
        marker_color=CANDIDATE_COLOR,
    )
    _base_layout(figure, "Equipos por bloque de cuatro horas")
    figure.update_layout(barmode="group")
    figure.update_xaxes(title="Bloque horario")
    figure.update_yaxes(title="Equipos", dtick=1)
    return figure


def convergence_figure(result) -> go.Figure:
    """Render history from an explicitly requested live demonstration."""

    frame = pd.DataFrame(
        {
            "generation": [item.generation for item in result.history],
            "best": [item.best_objective for item in result.history],
            "mean": [item.population_mean_objective for item in result.history],
        }
    )
    figure = go.Figure()
    figure.add_scatter(
        x=frame["generation"],
        y=frame["mean"],
        name="Media de población",
        line={"color": "#88A8B0", "width": 2},
    )
    figure.add_scatter(
        x=frame["generation"],
        y=frame["best"],
        name="Mejor factible",
        line={"color": BASE_COLOR, "width": 3},
    )
    _base_layout(figure, "Convergencia de la demostración")
    figure.update_xaxes(title="Generación", dtick=1)
    figure.update_yaxes(title="Objetivo (min)")
    return figure


def condition_wait_figure(summary: pd.DataFrame) -> go.Figure:
    """Show mean wait and 95 % intervals for all final conditions."""

    data = summary[summary["metric"] == "mean_wait_minutes"].copy()
    data["Demanda"] = (
        (100 * data["demand_multiplier"]).round().astype(int).astype(str) + " %"
    )
    figure = go.Figure()
    for schedule_id, label, color in (
        ("base", "Base", BASE_COLOR),
        ("candidate", "Candidata", CANDIDATE_COLOR),
    ):
        part = data[data["schedule_id"] == schedule_id]
        figure.add_bar(
            x=part["Demanda"],
            y=part["mean"],
            name=label,
            marker_color=color,
            error_y={
                "type": "data",
                "array": part["ci95_high"] - part["mean"],
                "arrayminus": part["mean"] - part["ci95_low"],
            },
            hovertemplate="%{x}<br>%{y:.1f} min<extra>" + label + "</extra>",
        )
    _base_layout(figure, "Espera media por condición")
    figure.update_layout(barmode="group")
    figure.update_xaxes(title="Nivel de demanda")
    figure.update_yaxes(title="Espera media (min)")
    return figure


def validation_figure(validation: pd.DataFrame) -> go.Figure:
    """Compare reference, base and candidate for compatible minute metrics."""

    labels = {
        "mean_wait_minutes": "Media",
        "median_wait_minutes": "Mediana",
        "p90_wait_minutes": "P90",
    }
    data = validation[validation["unit"] == "minutes"].copy()
    data["label"] = data["metric"].map(labels)
    figure = go.Figure()
    for column, name, color in (
        ("reference_value", "Referencia NHAMCS", REFERENCE_COLOR),
        ("base_simulation_mean", "Base simulada", BASE_COLOR),
        ("candidate_simulation_mean", "Candidata simulada", CANDIDATE_COLOR),
    ):
        figure.add_bar(
            x=data["label"], y=data[column], name=name, marker_color=color
        )
    _base_layout(figure, "Referencia y simulaciones en demanda nominal")
    figure.update_layout(barmode="group")
    figure.update_xaxes(title="Métrica")
    figure.update_yaxes(title="Minutos")
    return figure


def _base_layout(figure: go.Figure, title: str) -> None:
    figure.update_layout(
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        legend={"orientation": "h", "y": -0.22},
        hovermode="closest",
    )
    figure.update_xaxes(gridcolor="#E5E7EB")
    figure.update_yaxes(gridcolor="#E5E7EB", rangemode="tozero")
