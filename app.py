"""Streamlit interface for the emergency-department simulation.

The interface intentionally delegates all model logic to ``ed_simulation``. This
keeps the visual layer replaceable and prevents interactive controls from creating
a second, inconsistent implementation of the mathematics.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Support ``streamlit run app.py`` even before an editable installation. Clean
# environments should still follow the documented ``pip install -e .`` workflow.
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from ed_simulation import default_config, simulate
from ed_simulation.optimization import (
    GAConfig,
    OptimizationConstraints,
    optimize_staffing,
)


BLOCK_LABELS = (
    "00:00-04:00",
    "04:00-08:00",
    "08:00-12:00",
    "12:00-16:00",
    "16:00-20:00",
    "20:00-24:00",
)


def main() -> None:
    """Render navigation, configuration, and the selected project view."""

    st.set_page_config(
        page_title="Flujo de emergencias",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _apply_styles()

    with st.sidebar:
        st.markdown("## Flujo de emergencias")
        st.caption("Simulación y asignación de recursos")
        page = st.radio(
            "Sección",
            ("Problema", "Modelo", "Simulación", "Optimización"),
            label_visibility="collapsed",
        )
        st.divider()
        st.caption(
            "Proyecto 2 · CC3074 · Los parámetros actuales son estimados y no "
            "constituyen validación clínica."
        )

    if page == "Problema":
        _problem_page()
    elif page == "Modelo":
        _model_page()
    elif page == "Simulación":
        _simulation_page()
    else:
        _optimization_page()


def _problem_page() -> None:
    """Explain the decision problem before exposing controls."""

    st.markdown(
        """
        <section class="hero">
          <p class="section-mark">Proyecto 2 · Parte 1</p>
          <h1>La demanda cambia cada hora. La capacidad también debería hacerlo.</h1>
          <p class="hero-copy">
            Este modelo evalúa si redistribuir los mismos recursos de atención
            reduce la espera sin aumentar las horas disponibles.
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns((1.3, 1), gap="large")
    with left:
        st.markdown("### Decisión que se estudia")
        st.write(
            "Se divide el día en seis bloques de cuatro horas. Cada bloque recibe "
            "un número entero de equipos de atención. El escenario mejorado debe "
            "conservar el mismo total diario del escenario base."
        )
        st.markdown("### Pregunta de investigación")
        st.info(
            "¿Cuánto puede reducirse el tiempo de espera al redistribuir una "
            "cantidad fija de equipos entre los bloques del día?"
        )
    with right:
        st.markdown("### Qué se mide")
        st.markdown(
            """
            - Espera media, mediana y percentil 90.
            - Pacientes con espera mayor a 60 minutos.
            - Longitud de la cola.
            - Utilización y pacientes pendientes al cierre.
            """
        )
        st.markdown("### Referencia")
        st.write(
            "La calibración final utilizará NHAMCS 2022. Esta versión funcional "
            "usa un perfil estimado, marcado como tal en datos y resultados."
        )

    st.markdown("### Flujo operativo")
    st.markdown(
        """
        <div class="patient-flow" role="list" aria-label="Flujo de pacientes">
          <div role="listitem"><strong>Llegada</strong><span>Tasa por hora</span></div>
          <i aria-hidden="true"></i>
          <div role="listitem"><strong>Triaje</strong><span>Prioridad 1 a 5</span></div>
          <i aria-hidden="true"></i>
          <div role="listitem"><strong>Espera</strong><span>Cola prioritaria</span></div>
          <i aria-hidden="true"></i>
          <div role="listitem"><strong>Atención</strong><span>Capacidad limitada</span></div>
          <i aria-hidden="true"></i>
          <div role="listitem"><strong>Salida</strong><span>Métricas registradas</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _model_page() -> None:
    """Present model equations, state, assumptions, and source categories."""

    st.markdown('<p class="section-mark">Proyecto 2 · Parte 3</p>', unsafe_allow_html=True)
    st.title("Modelo de eventos discretos")
    st.write(
        "El reloj avanza de un evento al siguiente. Los pacientes compiten por "
        "equipos de atención y la prioridad clínica ordena la cola."
    )

    model_tab, variables_tab, limits_tab = st.tabs(
        ("Dinámica", "Variables", "Supuestos")
    )
    with model_tab:
        st.markdown("#### Llegadas por hora")
        st.latex(r"T_h=-\frac{\ln(U)}{\lambda_h},\quad U\sim\mathrm{Uniforme}(0,1)")
        st.markdown("#### Duración por nivel de triaje")
        st.latex(r"S_k\sim\mathrm{Lognormal}(\ln(m_k),\sigma)")
        st.markdown("#### Comparación posterior")
        st.latex(r"J(x)=0.7\,\overline{W}(x)+0.3\,Q_{0.90}(W(x))")
    with variables_tab:
        st.dataframe(
            pd.DataFrame(
                [
                    ("Tasa de llegada", "pacientes/hora", "Entrada estimada"),
                    ("Nivel de triaje", "1 a 5", "Entrada aleatoria"),
                    ("Capacidad", "equipos", "Decisión"),
                    ("Espera", "minutos", "Salida principal"),
                    ("Utilización", "proporción", "Salida secundaria"),
                ],
                columns=("Variable", "Unidad", "Papel"),
            ),
            hide_index=True,
            use_container_width=True,
        )
    with limits_tab:
        st.markdown(
            """
            - El recurso es un equipo compuesto, no una persona específica.
            - La prioridad no interrumpe una atención iniciada.
            - Los parámetros actuales son estimados.
            - El primer día sirve como calentamiento y no se reporta.
            - Los pacientes pendientes al final se muestran como censurados.
            """
        )


def _simulation_page() -> None:
    """Collect explicit parameters and run the baseline scenario on demand."""

    st.markdown('<p class="section-mark">Proyecto 2 · Parte 3</p>', unsafe_allow_html=True)
    st.title("Ejecutar escenario base")
    st.write(
        "Ajusta la demanda y la capacidad. La ejecución ocurre únicamente al "
        "presionar el botón; la semilla permite repetir exactamente el resultado."
    )

    with st.expander("Parámetros de la simulación", expanded=True):
        top_left, top_right = st.columns(2)
        with top_left:
            seed = st.number_input(
                "Semilla",
                min_value=0,
                max_value=2_147_483_647,
                value=2026,
                step=1,
            )
        with top_right:
            demand_multiplier = st.slider(
                "Multiplicador de demanda",
                min_value=0.50,
                max_value=1.50,
                value=1.00,
                step=0.05,
                help="1.00 conserva el perfil estimado; 1.20 aumenta todas las tasas 20 %.",
            )

        st.markdown("#### Equipos por bloque")
        capacity_columns = st.columns(6)
        default_capacity = (3, 3, 4, 4, 5, 4)
        capacity: list[int] = []
        for index, column in enumerate(capacity_columns):
            with column:
                capacity.append(
                    int(
                        st.number_input(
                            BLOCK_LABELS[index],
                            min_value=1,
                            max_value=10,
                            value=default_capacity[index],
                            step=1,
                            key=f"capacity_{index}",
                        )
                    )
                )

        st.caption(
            f"Capacidad configurada: {sum(capacity) * 4} horas-equipo por día."
        )

    if st.button("Ejecutar simulación base", type="primary", use_container_width=True):
        base = default_config()
        rates = tuple(rate * demand_multiplier for rate in base.arrival_rates)
        config = default_config(
            seed=int(seed),
            arrival_rates=rates,
            capacity_schedule=tuple(capacity),
        )
        with st.spinner("Procesando llegadas, prioridades y recursos..."):
            st.session_state["baseline_result"] = simulate(config)

    result = st.session_state.get("baseline_result")
    if result is None:
        st.markdown(
            """
            <div class="empty-state">
              <strong>Aún no hay una ejecución.</strong>
              <span>Configura el escenario y selecciona “Ejecutar simulación base”.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    _render_result(result)


def _render_result(result) -> None:
    """Render metrics and diagnostic plots for a completed simulation."""

    metrics = result.metrics
    st.success(
        f"Ejecución completada con semilla {result.config.seed}. "
        "Los resultados corresponden al segundo día simulado."
    )

    metric_columns = st.columns(5)
    values = (
        ("Espera media", f"{metrics['mean_wait_minutes']:.1f} min"),
        ("Percentil 90", f"{metrics['p90_wait_minutes']:.1f} min"),
        ("Cola máxima", f"{metrics['maximum_queue']} pacientes"),
        ("Utilización", f"{100 * metrics['resource_utilization']:.1f} %"),
        ("Pendientes", f"{metrics['in_system_at_end']} pacientes"),
    )
    for column, (label, value) in zip(metric_columns, values, strict=True):
        column.metric(label, value)

    timeline, distribution = st.columns((1.35, 1), gap="large")
    with timeline:
        st.plotly_chart(
            _timeline_figure(result),
            use_container_width=True,
            config={"displaylogo": False},
        )
    with distribution:
        st.plotly_chart(
            _wait_figure(result),
            use_container_width=True,
            config={"displaylogo": False},
        )

    with st.expander("Inspeccionar métricas y pacientes"):
        metrics_frame = pd.DataFrame(
            {"Métrica": metrics.keys(), "Valor": metrics.values()}
        )
        st.dataframe(metrics_frame, hide_index=True, use_container_width=True)
        patient_frame = pd.DataFrame(patient.to_dict() for patient in result.patients)
        st.dataframe(patient_frame.head(200), hide_index=True, use_container_width=True)
        st.caption("La tabla muestra como máximo los primeros 200 pacientes medidos.")


def _optimization_page() -> None:
    """Configure and execute the constrained genetic algorithm on demand."""

    st.markdown('<p class="section-mark">Proyecto 2 · Parte 4</p>', unsafe_allow_html=True)
    st.title("Redistribuir sin aumentar recursos")
    st.write(
        "El algoritmo genético modifica la asignación por bloque, pero conserva "
        "el total diario. Todos los candidatos usan las mismas semillas para que "
        "la comparación no dependa de una demanda favorable."
    )

    with st.expander("Escenario y restricciones", expanded=True):
        baseline_columns = st.columns(6)
        default_capacity = (3, 3, 4, 4, 5, 4)
        baseline: list[int] = []
        for index, column in enumerate(baseline_columns):
            with column:
                baseline.append(
                    int(
                        st.number_input(
                            BLOCK_LABELS[index],
                            min_value=1,
                            max_value=10,
                            value=default_capacity[index],
                            step=1,
                            key=f"opt_capacity_{index}",
                        )
                    )
                )
        constraint_columns = st.columns(3)
        with constraint_columns[0]:
            min_capacity = int(
                st.number_input("Mínimo por bloque", 1, 5, 1, key="opt_min")
            )
        with constraint_columns[1]:
            max_capacity = int(
                st.number_input("Máximo por bloque", 2, 10, 8, key="opt_max")
            )
        with constraint_columns[2]:
            max_step = int(
                st.number_input("Cambio máximo consecutivo", 0, 8, 3, key="opt_step")
            )
        st.caption(
            f"Presupuesto fijo: {sum(baseline)} unidades de bloque, equivalentes "
            f"a {sum(baseline) * 4} horas-equipo por día."
        )

    with st.expander("Parámetros del algoritmo"):
        algorithm_columns = st.columns(4)
        with algorithm_columns[0]:
            population = int(
                st.number_input("Población", 8, 60, 16, step=4, key="ga_population")
            )
        with algorithm_columns[1]:
            generations = int(
                st.number_input("Generaciones", 2, 60, 10, key="ga_generations")
            )
        with algorithm_columns[2]:
            replicates = int(
                st.number_input("Réplicas por candidato", 1, 10, 2, key="ga_replicates")
            )
        with algorithm_columns[3]:
            algorithm_seed = int(
                st.number_input(
                    "Semilla del algoritmo",
                    0,
                    2_147_483_647,
                    9101,
                    key="ga_seed",
                )
            )

    st.markdown(
        """
        <div class="method-note">
          <strong>Objetivo de búsqueda</strong>
          <span>70 % espera media + 30 % percentil 90 + penalización por pacientes sin iniciar atención.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Buscar asignación mejorada", type="primary", use_container_width=True):
        try:
            base_config = default_config(capacity_schedule=tuple(baseline))
            constraints = OptimizationConstraints(
                blocks=6,
                total_capacity_units=sum(baseline),
                min_capacity=min_capacity,
                max_capacity=max_capacity,
                max_step_change=max_step,
            )
            ga_config = GAConfig(
                population_size=population,
                generations=generations,
                elitism=min(2, population - 1),
                tournament_size=min(3, population),
                patience=max(2, min(8, generations)),
                evaluation_replicates=replicates,
                algorithm_seed=algorithm_seed,
            )
            with st.spinner("Evaluando asignaciones con simulaciones comunes..."):
                st.session_state["optimization_result"] = optimize_staffing(
                    base_config,
                    constraints,
                    ga_config,
                )
        except ValueError as error:
            st.error(f"No se puede iniciar la búsqueda: {error}")

    optimization = st.session_state.get("optimization_result")
    if optimization is None:
        st.markdown(
            """
            <div class="empty-state">
              <strong>Aún no hay una búsqueda.</strong>
              <span>Revisa las restricciones y selecciona “Buscar asignación mejorada”.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    _render_optimization(optimization)


def _render_optimization(result) -> None:
    """Show feasibility, comparison, and convergence without overstating results."""

    baseline = result.baseline
    best = result.best
    if best.feasible:
        st.success(
            "La asignación candidata satisface presupuesto, límites y cambios "
            "máximos entre bloques."
        )
    else:
        st.error("La solución candidata no es factible y no debe utilizarse.")

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "Objetivo base",
        f"{baseline.objective:.1f} min",
    )
    metric_columns[1].metric(
        "Objetivo candidato",
        f"{best.objective:.1f} min",
        delta=f"{-result.absolute_improvement_minutes:.1f} min",
        delta_color="inverse",
    )
    metric_columns[2].metric(
        "Mejora simulada",
        f"{100 * result.relative_improvement:.1f} %",
    )
    metric_columns[3].metric(
        "Asignaciones evaluadas",
        str(result.evaluated_schedules),
    )

    comparison, convergence = st.columns((1.1, 1), gap="large")
    with comparison:
        st.plotly_chart(
            _schedule_comparison_figure(result),
            use_container_width=True,
            config={"displaylogo": False},
        )
    with convergence:
        st.plotly_chart(
            _convergence_figure(result),
            use_container_width=True,
            config={"displaylogo": False},
        )

    table = pd.DataFrame(
        {
            "Indicador": (
                "Asignación",
                "Espera media (min)",
                "Percentil 90 (min)",
                "Proporción censurada",
                "Cola media",
                "Utilización",
            ),
            "Base": (
                str(list(baseline.schedule)),
                baseline.mean_wait_minutes,
                baseline.p90_wait_minutes,
                baseline.censored_share,
                baseline.mean_queue,
                baseline.resource_utilization,
            ),
            "Candidata": (
                str(list(best.schedule)),
                best.mean_wait_minutes,
                best.p90_wait_minutes,
                best.censored_share,
                best.mean_queue,
                best.resource_utilization,
            ),
        }
    )
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.warning(
        "Esta es una mejora simulada con parámetros estimados. No demuestra una "
        "mejora observada en un hospital real; esa afirmación requiere las Partes 5 y 6."
    )


def _schedule_comparison_figure(result) -> go.Figure:
    """Compare integer allocations block by block."""

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=BLOCK_LABELS,
            y=result.baseline.schedule,
            name="Base",
            marker_color="#6B8E86",
        )
    )
    figure.add_trace(
        go.Bar(
            x=BLOCK_LABELS,
            y=result.best.schedule,
            name="Candidata",
            marker_color="#C94F4F",
        )
    )
    figure.update_layout(
        title="Asignación por bloque",
        barmode="group",
        xaxis_title="Horario",
        yaxis_title="Equipos",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#F7FBFC",
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        legend={"orientation": "h", "y": -0.28},
    )
    figure.update_yaxes(dtick=1, gridcolor="#D9E8EA")
    return figure


def _convergence_figure(result) -> go.Figure:
    """Expose the optimization history instead of showing only the winner."""

    frame = pd.DataFrame(
        {
            "generation": [record.generation for record in result.history],
            "best": [record.best_objective for record in result.history],
            "mean": [record.population_mean_objective for record in result.history],
        }
    )
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=frame["generation"],
            y=frame["mean"],
            name="Media de población",
            line={"color": "#91B7BC", "width": 2},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=frame["generation"],
            y=frame["best"],
            name="Mejor factible",
            line={"color": "#0B3C49", "width": 3},
        )
    )
    figure.update_layout(
        title="Convergencia de la búsqueda",
        xaxis_title="Generación",
        yaxis_title="Objetivo (min)",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#F7FBFC",
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        legend={"orientation": "h", "y": -0.28},
    )
    figure.update_xaxes(dtick=1, gridcolor="#D9E8EA")
    figure.update_yaxes(gridcolor="#D9E8EA")
    return figure


def _timeline_figure(result) -> go.Figure:
    """Compare realized arrivals with scheduled capacity through the day."""

    capacities = [
        result.config.capacity_schedule[hour // result.config.block_hours]
        for hour in range(24)
    ]
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=list(range(24)),
            y=result.hourly_arrivals,
            name="Llegadas realizadas",
            marker_color="#146B78",
            hovertemplate="Hora %{x}:00<br>%{y} pacientes<extra></extra>",
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=list(range(24)),
            y=capacities,
            name="Equipos disponibles",
            mode="lines",
            line={"color": "#C94F4F", "width": 3, "shape": "hv"},
            hovertemplate="Hora %{x}:00<br>%{y} equipos<extra></extra>",
        ),
        secondary_y=True,
    )
    figure.update_layout(
        title="Ritmo diario: demanda y capacidad",
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        legend={"orientation": "h", "y": -0.2},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#F7FBFC",
        hovermode="x unified",
    )
    figure.update_xaxes(title="Hora", dtick=2, gridcolor="#D9E8EA")
    figure.update_yaxes(
        title="Pacientes por hora", gridcolor="#D9E8EA", secondary_y=False
    )
    figure.update_yaxes(title="Equipos", rangemode="tozero", secondary_y=True)
    return figure


def _wait_figure(result) -> go.Figure:
    """Show the skewed waiting-time distribution without hiding outliers."""

    waits = [
        patient.wait_minutes
        for patient in result.patients
        if patient.wait_minutes is not None
    ]
    figure = go.Figure(
        go.Histogram(
            x=waits,
            nbinsx=24,
            marker_color="#6B8E86",
            hovertemplate="Espera %{x:.1f} min<br>%{y} pacientes<extra></extra>",
        )
    )
    figure.add_vline(
        x=60,
        line_dash="dash",
        line_color="#C94F4F",
        annotation_text="60 min",
        annotation_position="top right",
    )
    figure.update_layout(
        title="Distribución de espera",
        xaxis_title="Minutos",
        yaxis_title="Pacientes",
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#F7FBFC",
    )
    figure.update_xaxes(gridcolor="#D9E8EA")
    figure.update_yaxes(gridcolor="#D9E8EA")
    return figure


def _apply_styles() -> None:
    """Apply a restrained clinical-operations visual system."""

    st.markdown(
        """
        <style>
        :root {
          --ink: #16333A;
          --petrol: #0B3C49;
          --surgical: #146B78;
          --mist: #E9F4F5;
          --paper: #F7FBFC;
          --alert: #C94F4F;
        }
        html, body, [class*="st-"] {
          font-family: "Aptos", "Segoe UI", sans-serif;
          color: var(--ink);
        }
        .stApp { background: var(--paper); }
        h1, h2, h3 { color: var(--petrol); letter-spacing: -0.025em; }
        h1 { max-width: 17ch; line-height: 1.02; }
        p, li { line-height: 1.58; }
        .hero {
          border-left: 8px solid var(--surgical);
          padding: 1.2rem 0 1.2rem 1.6rem;
          margin: 0.5rem 0 2rem;
          max-width: 920px;
        }
        .hero h1 { font-size: clamp(2.4rem, 5vw, 4.8rem); margin: 0; }
        .hero-copy { font-size: 1.2rem; max-width: 62ch; margin-top: 1.25rem; }
        .section-mark { color: var(--surgical); font-weight: 650; margin-bottom: 0.35rem; }
        .patient-flow {
          display: grid;
          grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr auto 1fr;
          gap: 0.75rem;
          align-items: center;
          margin: 1rem 0 2rem;
        }
        .patient-flow div {
          min-height: 108px;
          border-top: 4px solid var(--surgical);
          background: white;
          padding: 1rem;
        }
        .patient-flow strong, .patient-flow span { display: block; }
        .patient-flow span { color: #49666D; margin-top: 0.35rem; }
        .patient-flow i { width: 30px; height: 2px; background: #91B7BC; }
        .empty-state {
          border: 1px dashed #91B7BC;
          background: var(--mist);
          padding: 2rem;
          margin-top: 1.5rem;
        }
        .empty-state strong, .empty-state span { display: block; }
        .empty-state span { margin-top: 0.35rem; }
        .method-note {
          border-left: 4px solid var(--alert);
          background: white;
          padding: 1rem 1.2rem;
          margin: 1rem 0;
        }
        .method-note strong, .method-note span { display: block; }
        .method-note span { color: #49666D; margin-top: 0.3rem; }
        .stButton > button[kind="primary"] {
          background: var(--petrol);
          border-color: var(--petrol);
          color: white;
          min-height: 3rem;
        }
        .stButton > button[kind="primary"] p { color: white; }
        [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
          display: none;
        }
        button[aria-label="Collapse sidebar"] [data-testid="stIconMaterial"],
        button[aria-label="Open sidebar"] [data-testid="stIconMaterial"] {
          font-size: 0 !important;
        }
        button[aria-label="Collapse sidebar"] [data-testid="stIconMaterial"]::after {
          content: "‹";
          font-family: "Segoe UI", sans-serif;
          font-size: 1.6rem;
        }
        button[aria-label="Open sidebar"] [data-testid="stIconMaterial"]::after {
          content: "›";
          font-family: "Segoe UI", sans-serif;
          font-size: 1.6rem;
        }
        .stButton > button:focus-visible,
        input:focus-visible {
          outline: 3px solid #E5A6A6 !important;
          outline-offset: 2px;
        }
        @media (max-width: 900px) {
          .patient-flow { grid-template-columns: 1fr; }
          .patient-flow i { width: 2px; height: 18px; margin-left: 1.25rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
