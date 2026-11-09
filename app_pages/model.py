"""Model, assumptions and provenance page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app_pages._bootstrap import bootstrap

bootstrap()

from ed_simulation.ui.data import (
    load_calibration_metadata,
    load_evidence_bundle,
    source_label,
)


st.title("Modelo de eventos discretos")
st.write(
    "Los pacientes llegan con una tasa dependiente de la hora, reciben una "
    "prioridad clínica y esperan por un equipo de atención no expropiativo."
)

st.subheader("Flujo del sistema")
flow = st.columns(5)
for column, icon, title, detail in zip(
    flow,
    (
        ":material/login:",
        ":material/medical_services:",
        ":material/hourglass_top:",
        ":material/groups:",
        ":material/logout:",
    ),
    ("Llegada", "Triaje", "Cola", "Atención", "Salida"),
    ("Tasa por hora", "Prioridad 1–5", "Orden clínico", "Capacidad variable", "Métricas"),
    strict=True,
):
    with column.container(border=True):
        st.markdown(f"### {icon} {title}")
        st.caption(detail)

metadata = load_calibration_metadata()
bundle = load_evidence_bundle()
candidate = bundle.candidate if bundle.available else {}

left, right = st.columns((1.2, 1), gap="large")
with left:
    st.subheader("Variables y procedencia")
    inputs = metadata["model_inputs"]
    table = pd.DataFrame(
        [
            ("Perfil horario", "pacientes/hora", source_label(inputs["arrival_rates"]["source_category"])),
            ("Triaje", "proporción", source_label(inputs["triage_probabilities"]["source_category"])),
            ("Tiempo de servicio", "minutos", source_label(inputs["service_medians_minutes"]["source_category"])),
            ("Capacidad", "equipos", source_label(inputs["capacity_schedule"]["source_category"])),
            ("Espera y cola", "minutos / pacientes", source_label("synthetic_simulation")),
        ],
        columns=("Variable", "Unidad", "Procedencia"),
    )
    st.dataframe(table, hide_index=True, width="stretch", key="model_variables_table")
with right:
    st.subheader("Reglas centrales")
    with st.container(border=True):
        st.latex(r"T_h=-\frac{\ln(U)}{\lambda_h}")
        st.caption("Llegadas: Poisson por tramos horarios.")
    with st.container(border=True):
        st.latex(r"S_k\sim\mathrm{Lognormal}(\ln(m_k),\sigma)")
        st.caption("Servicio: supuesto positivo por nivel de triaje.")

st.subheader("Medición y límites")
assumptions, scope = st.columns(2, gap="large")
with assumptions.container(border=True):
    st.markdown("#### Verificación implementada")
    st.markdown(
        """
        - Un día de calentamiento conserva la cola física inicial.
        - Al corte se detienen llegadas y se drena la cohorte medida.
        - El drenaje no entra en cola ni utilización de la ventana.
        - La utilización usa capacidad efectiva y queda acotada por 1.
        """
    )
with scope.container(border=True):
    st.markdown("#### Alcance")
    st.markdown(
        """
        - NHAMCS representa departamentos de Estados Unidos, no Guatemala.
        - El tiempo de servicio sigue siendo un supuesto estimado.
        - La cola es no expropiativa y usa un equipo compuesto.
        - No se modelan abandono, múltiples etapas ni resultados clínicos.
        """
    )

if candidate:
    st.caption(
        "Candidata factible: "
        + str(candidate["candidate_schedule"])
        + ". Fuente: "
        + source_label("synthetic_simulation")
        + "."
    )
