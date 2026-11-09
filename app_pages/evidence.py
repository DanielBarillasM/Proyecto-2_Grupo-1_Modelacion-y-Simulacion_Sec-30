"""Read-only exploration of frozen experiments and NHAMCS validation."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app_pages._bootstrap import bootstrap

bootstrap()

from ed_simulation.ui.charts import condition_wait_figure, validation_figure
from ed_simulation.ui.data import load_evidence_bundle, source_label


st.title("Evidencia experimental")
st.write(
    "Esta página lee resultados precomputados; abrirla no repite optimización ni "
    "las 180 simulaciones finales."
)

bundle = load_evidence_bundle()
if not bundle.available:
    st.error(bundle.error, icon=":material/error:")
    st.stop()

manifest = bundle.manifest
cards = st.columns(4)
cards[0].metric("Condiciones", str(len(manifest["conditions"])))
cards[1].metric("Ejecuciones", str(len(bundle.runs)))
cards[2].metric("Semillas finales", str(len(manifest["seeds"]["evaluation"])))
cards[3].metric("Presupuesto", "92 horas-equipo/día")

comparison_tab, variability_tab, validation_tab, downloads_tab = st.tabs(
    ("Comparación", "Variabilidad", "Validación", "Descargas")
)
with comparison_tab:
    st.plotly_chart(
        condition_wait_figure(bundle.summary),
        width="stretch",
        config={"displaylogo": False},
        key="evidence_condition_chart",
    )
    table = bundle.summary[
        bundle.summary["metric"].isin(
            ["mean_wait_minutes", "p90_wait_minutes", "mean_queue"]
        )
    ][
        [
            "condition_id",
            "metric",
            "unit",
            "n",
            "mean",
            "std",
            "ci95_low",
            "ci95_high",
        ]
    ].copy()
    st.dataframe(table, hide_index=True, width="stretch", key="evidence_summary_table")
    st.caption("Procedencia: " + source_label("synthetic_simulation") + ".")

with variability_tab:
    paired = bundle.paired_summary[
        bundle.paired_summary["metric"] == "mean_wait_minutes"
    ][
        [
            "demand_multiplier",
            "n_pairs",
            "base_mean",
            "candidate_mean",
            "mean_improvement_base_minus_candidate",
            "ci95_low",
            "ci95_high",
            "positive_pairs",
        ]
    ].copy()
    paired.columns = (
        "Demanda",
        "Pares",
        "Base (min)",
        "Candidata (min)",
        "Reducción (min)",
        "IC 95 % inferior",
        "IC 95 % superior",
        "Pares favorables",
    )
    paired["Demanda"] = (100 * paired["Demanda"]).round().astype(int).astype(str) + " %"
    st.subheader("Diferencias pareadas de espera media")
    st.dataframe(paired, hide_index=True, width="stretch", key="paired_effects_table")
    st.info(
        "Al 80 % de demanda el intervalo incluye cero; el beneficio no es "
        "consistente. Bajo demanda nominal y alta, la reducción media es positiva.",
        icon=":material/insights:",
    )

with validation_tab:
    st.plotly_chart(
        validation_figure(bundle.validation),
        width="stretch",
        config={"displaylogo": False},
        key="validation_reference_chart",
    )
    validation = bundle.validation[
        [
            "metric",
            "unit",
            "reference_value",
            "base_simulation_mean",
            "candidate_simulation_mean",
            "base_absolute_error",
            "improvement_percent",
        ]
    ].copy()
    st.dataframe(validation, hide_index=True, width="stretch", key="validation_table")
    st.caption(
        "Referencia: "
        + source_label("derived_from_public")
        + ". Base y candidata: "
        + source_label("synthetic_simulation")
        + "."
    )
    st.warning(
        "La candidata queda más cerca de NHAMCS en estas métricas, pero no fue "
        "una intervención observada ni una validación clínica externa.",
        icon=":material/warning:",
    )

with downloads_tab:
    st.subheader("Archivos reproducibles")
    evidence_dir = bundle.root / "evidence" / "final"
    for filename, label, mime in (
        ("runs.csv", "Descargar ejecuciones", "text/csv"),
        ("summary.csv", "Descargar resumen", "text/csv"),
        ("paired_summary.csv", "Descargar efectos pareados", "text/csv"),
        ("validation_comparison.csv", "Descargar validación", "text/csv"),
    ):
        st.download_button(
            label,
            data=(evidence_dir / filename).read_bytes(),
            file_name=filename,
            mime=mime,
            icon=":material/download:",
            width="stretch",
            key=f"download_{filename}",
        )
    st.download_button(
        "Descargar manifiesto",
        data=(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        file_name="manifest.json",
        mime="application/json",
        icon=":material/download:",
        width="stretch",
    )

st.caption(
    "Cada cifra se regenera con `python scripts/generate_evidence.py`; la interfaz "
    "no modifica los archivos de evidencia."
)
