"""Frozen candidate and explicit short optimization demonstration."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app_pages._bootstrap import bootstrap

bootstrap()

from ed_simulation.calibration import load_calibrated_config
from ed_simulation.optimization import GAConfig, OptimizationConstraints, optimize_staffing
from ed_simulation.ui.charts import convergence_figure, schedule_figure
from ed_simulation.ui.data import load_evidence_bundle, project_root, source_label
from ed_simulation.ui.state import initialize_session_state


initialize_session_state()
st.title("Optimización restringida")
st.write(
    "La vista principal consume la candidata congelada. La búsqueda en vivo es "
    "una demostración corta y solo se ejecuta al enviar su formulario."
)

bundle = load_evidence_bundle()
if not bundle.available:
    st.error(bundle.error, icon=":material/error:")
    st.stop()

candidate = bundle.candidate
base_schedule = tuple(candidate["baseline_schedule"])
candidate_schedule = tuple(candidate["candidate_schedule"])
optimization = candidate["optimization"]

st.subheader("Candidata precomputada")
cards = st.columns(4)
cards[0].metric("Presupuesto diario", f"{sum(base_schedule) * 4} h-equipo")
cards[1].metric("Objetivo base", f"{optimization['baseline']['objective']:.1f} min")
cards[2].metric("Objetivo candidato", f"{optimization['best']['objective']:.1f} min")
cards[3].metric("Mejora de selección", f"{100 * optimization['relative_improvement']:.1f} %")

left, right = st.columns((1.35, 1), gap="large")
with left:
    st.plotly_chart(
        schedule_figure(base_schedule, candidate_schedule),
        width="stretch",
        config={"displaylogo": False},
        key="frozen_schedule_chart",
    )
with right:
    with st.container(border=True):
        st.markdown("#### Restricciones comprobadas")
        st.write("✓ Seis bloques enteros")
        st.write("✓ Suma fija de 23 unidades")
        st.write("✓ Entre 1 y 8 equipos por bloque")
        st.write("✓ Cambio máximo de 3, incluido cierre diario")
        st.caption("Fuente: " + source_label("synthetic_simulation") + ".")
    st.download_button(
        "Descargar candidata congelada",
        data=(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        file_name="frozen_candidate.json",
        mime="application/json",
        icon=":material/download:",
        width="stretch",
    )

with st.expander("Demostración corta de búsqueda", expanded=False):
    st.caption(
        "Esta ejecución usa parámetros reducidos para la exposición. No reemplaza "
        "la candidata congelada ni las 180 ejecuciones finales."
    )
    with st.form("optimization_demo_form", border=True):
        columns = st.columns(4)
        population = int(columns[0].number_input("Población", 8, 24, 8, step=4))
        generations = int(columns[1].number_input("Generaciones", 2, 10, 3))
        replicates = int(columns[2].number_input("Réplicas/candidata", 1, 3, 1))
        algorithm_seed = int(columns[3].number_input("Semilla del algoritmo", 0, 2_147_483_647, 9101))
        run_demo = st.form_submit_button(
            "Ejecutar demostración",
            type="primary",
            icon=":material/play_arrow:",
            width="stretch",
        )

if run_demo:
    try:
        base_config = load_calibrated_config(
            project_root() / "data" / "processed",
            capacity_schedule=base_schedule,
            seed=10_000,
        )
        constraints = OptimizationConstraints(
            blocks=6,
            total_capacity_units=sum(base_schedule),
            min_capacity=1,
            max_capacity=8,
            max_step_change=3,
        )
        settings = GAConfig(
            population_size=population,
            generations=generations,
            elitism=1,
            tournament_size=2,
            patience=generations,
            evaluation_replicates=replicates,
            evaluation_seed_start=10_000,
            algorithm_seed=algorithm_seed,
        )
        with st.spinner("Evaluando candidatas de demostración..."):
            st.session_state["optimization_result"] = optimize_staffing(
                base_config, constraints, settings
            )
        st.session_state["optimization_error"] = None
    except ValueError as error:
        st.session_state["optimization_result"] = None
        st.session_state["optimization_error"] = str(error)

if st.session_state["optimization_error"]:
    st.error("No se pudo ejecutar la demostración: " + st.session_state["optimization_error"])

demo = st.session_state["optimization_result"]
if demo is not None:
    st.success(
        f"Demostración completada: {demo.evaluated_schedules} horarios evaluados."
    )
    st.plotly_chart(
        convergence_figure(demo),
        width="stretch",
        config={"displaylogo": False},
        key="optimization_demo_convergence",
    )
    table = pd.DataFrame(
        {
            "Escenario": ["Base", "Mejor de la demo"],
            "Horario": [str(list(demo.baseline.schedule)), str(list(demo.best.schedule))],
            "Objetivo (min)": [demo.baseline.objective, demo.best.objective],
            "Factible": [demo.baseline.feasible, demo.best.feasible],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch", key="optimization_demo_table")

st.warning(
    "La mejora es simulada. La búsqueda no demuestra que un hospital real haya "
    "cambiado su desempeño.",
    icon=":material/warning:",
)
