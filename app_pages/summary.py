"""Executive summary page backed only by frozen evidence."""

from __future__ import annotations

import streamlit as st

from app_pages._bootstrap import bootstrap

bootstrap()

from ed_simulation.ui.charts import condition_wait_figure
from ed_simulation.ui.data import load_evidence_bundle, source_label


st.title("Redistribuir capacidad sin aumentar recursos")
st.write(
    "El modelo evalúa si mover equipos entre seis bloques horarios reduce la "
    "espera, manteniendo 23 unidades de bloque y 92 horas-equipo por día."
)
st.warning(
    "Los resultados describen una mejora simulada para un departamento de "
    "referencia estadounidense; no una mejora observada en un hospital real.",
    icon=":material/warning:",
)

bundle = load_evidence_bundle()
if not bundle.available:
    st.error(bundle.error, icon=":material/error:")
    st.stop()

paired = bundle.paired_summary
nominal = paired[
    (paired["metric"] == "mean_wait_minutes")
    & (paired["demand_multiplier"].round(2) == 1.0)
].iloc[0]
candidate = bundle.candidate

metric_columns = st.columns(4)
metric_columns[0].metric("Reducción nominal", f"{nominal['mean_improvement_base_minus_candidate']:.1f} min")
metric_columns[1].metric("Cambio sobre la base", f"{nominal['aggregate_improvement_percent']:.1f} %")
metric_columns[2].metric("Réplicas por condición", str(int(nominal["n_pairs"])))
metric_columns[3].metric("Condiciones evaluadas", str(len(bundle.manifest["conditions"])))

left, right = st.columns((1.55, 1), gap="large")
with left:
    st.plotly_chart(
        condition_wait_figure(bundle.summary),
        width="stretch",
        config={"displaylogo": False, "responsive": True},
        key="summary_wait_chart",
    )
    st.caption(
        "Barras: media de espera. Líneas: intervalo del 95 %. Fuente: "
        + source_label("synthetic_simulation")
        + "."
    )
with right:
    with st.container(border=True):
        st.subheader("Horario congelado")
        st.write("Base: `" + " · ".join(map(str, candidate["baseline_schedule"])) + "`")
        st.write("Candidata: `" + " · ".join(map(str, candidate["candidate_schedule"])) + "`")
        st.caption("Bloques: 00–04 · 04–08 · 08–12 · 12–16 · 16–20 · 20–24")
    with st.container(border=True):
        st.subheader("Lectura responsable")
        st.write(
            "La candidata reduce la espera media bajo demanda nominal y alta. "
            "Al 80 % de demanda, el intervalo pareado incluye cero; el efecto "
            "no es consistente."
        )

st.subheader("Recorrido recomendado para la demostración")
steps = st.columns(4)
for column, icon, title, text in zip(
    steps,
    (":material/account_tree:", ":material/science:", ":material/tune:", ":material/analytics:"),
    ("Comprender", "Ejecutar", "Comparar", "Validar"),
    (
        "Revisar supuestos y procedencia.",
        "Correr un escenario corto bajo demanda.",
        "Ver el horario base y la candidata.",
        "Explorar variabilidad y NHAMCS.",
    ),
    strict=True,
):
    with column.container(border=True):
        st.markdown(f"### {icon} {title}")
        st.write(text)
