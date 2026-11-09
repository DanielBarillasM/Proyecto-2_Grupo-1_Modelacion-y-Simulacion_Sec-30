"""Explicit, on-demand calibrated scenario laboratory."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_pages._bootstrap import bootstrap

bootstrap()

from ed_simulation.ui.charts import timeline_figure, wait_distribution_figure
from ed_simulation.ui.data import project_root, source_label
from ed_simulation.ui.scenario import (
    config_download,
    parse_capacity_schedule,
    result_download,
    run_calibrated_scenario,
)
from ed_simulation.ui.state import initialize_session_state


initialize_session_state()
st.title("Laboratorio de escenarios")
st.write(
    "La simulación se ejecuta únicamente al enviar el formulario. Usa agregados "
    "NHAMCS para llegadas y triaje; servicio y capacidad siguen siendo supuestos."
)
st.info(
    "Configuración corta de demostración: una semilla, un día de calentamiento y "
    "un día medido.",
    icon=":material/bolt:",
)

with st.form("laboratory_form", border=True):
    first, second = st.columns(2)
    seed = first.number_input("Semilla reproducible", min_value=0, value=2026, step=1)
    demand = second.slider(
        "Multiplicador de demanda",
        min_value=0.50,
        max_value=1.50,
        value=1.00,
        step=0.05,
    )
    capacity_text = st.text_input(
        "Capacidad por bloque (seis enteros separados por coma)",
        value="3,3,4,4,5,4",
        help="Bloques: 00–04, 04–08, 08–12, 12–16, 16–20 y 20–24.",
    )
    submitted = st.form_submit_button(
        "Ejecutar escenario",
        type="primary",
        icon=":material/play_arrow:",
        width="stretch",
    )

if submitted:
    try:
        schedule = parse_capacity_schedule(capacity_text)
        with st.spinner("Simulando llegadas, prioridad y capacidad..."):
            st.session_state["laboratory_result"] = run_calibrated_scenario(
                project_root(),
                seed=int(seed),
                demand_multiplier=float(demand),
                capacity_schedule=schedule,
            )
        st.session_state["laboratory_error"] = None
    except (ValueError, OSError) as error:
        st.session_state["laboratory_result"] = None
        st.session_state["laboratory_error"] = str(error)

if st.session_state["laboratory_error"]:
    st.error(
        "No se pudo ejecutar el escenario: " + st.session_state["laboratory_error"],
        icon=":material/error:",
    )

result = st.session_state["laboratory_result"]
if result is None:
    st.info(
        "Aún no hay una ejecución. El formulario no calcula nada hasta presionar “Ejecutar escenario”.",
        icon=":material/pending_actions:",
    )
    st.stop()

metrics = result.metrics
st.success(f"Ejecución completada con semilla {result.config.seed}.")
cards = st.columns(5)
for column, label, value in zip(
    cards,
    ("Espera media", "Percentil 90", "Cola máxima", "Utilización", "Pendientes al corte"),
    (
        f"{metrics['mean_wait_minutes']:.1f} min",
        f"{metrics['p90_wait_minutes']:.1f} min",
        f"{metrics['maximum_queue']} pacientes",
        f"{100 * metrics['resource_utilization']:.1f} %",
        f"{metrics['not_started_at_measurement_end']} pacientes",
    ),
    strict=True,
):
    column.metric(label, value)

left, right = st.columns((1.35, 1), gap="large")
with left:
    st.plotly_chart(
        timeline_figure(result), width="stretch", config={"displaylogo": False}, key="lab_timeline"
    )
with right:
    st.plotly_chart(
        wait_distribution_figure(result), width="stretch", config={"displaylogo": False}, key="lab_waits"
    )
st.caption("Fuente de resultados: " + source_label("synthetic_simulation") + ".")

download_columns = st.columns(2)
download_columns[0].download_button(
    "Descargar configuración",
    data=config_download(
        seed=result.config.seed,
        demand_multiplier=float(demand),
        capacity_schedule=result.config.capacity_schedule,
    ),
    file_name=f"scenario_config_{result.config.seed}.json",
    mime="application/json",
    icon=":material/download:",
    width="stretch",
)
download_columns[1].download_button(
    "Descargar resultado y pacientes",
    data=result_download(result),
    file_name=f"scenario_result_{result.config.seed}.json",
    mime="application/json",
    icon=":material/download:",
    width="stretch",
)

with st.expander("Inspeccionar métricas completas"):
    frame = pd.DataFrame({"Métrica": metrics.keys(), "Valor": metrics.values()})
    st.dataframe(frame, hide_index=True, width="stretch", key="laboratory_metrics_table")
