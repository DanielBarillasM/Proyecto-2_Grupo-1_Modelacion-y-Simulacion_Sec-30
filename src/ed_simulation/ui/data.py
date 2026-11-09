"""Small, bounded loaders for calibration metadata and frozen evidence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


SOURCE_LABELS = {
    "observed_public": "Dato público observado",
    "derived_from_public": "Derivado de datos públicos",
    "estimated_assumption": "Supuesto estimado",
    "synthetic_simulation": "Resultado sintético simulado",
}


@dataclass
class EvidenceBundle:
    """All small files needed by the read-only evidence views."""

    available: bool
    root: Path
    manifest: dict[str, Any]
    candidate: dict[str, Any]
    runs: pd.DataFrame
    summary: pd.DataFrame
    paired_summary: pd.DataFrame
    validation: pd.DataFrame
    error: str | None = None


def project_root() -> Path:
    """Resolve resources independently of the current working directory."""

    override = os.environ.get("ED_SIM_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


@st.cache_data(max_entries=4, show_spinner=False)
def load_evidence_bundle(root: Path | str | None = None) -> EvidenceBundle:
    """Load final evidence, returning an actionable missing-data state."""

    root_path = Path(root).resolve() if root is not None else project_root()
    evidence = root_path / "evidence" / "final"
    files = {
        "manifest": evidence / "manifest.json",
        "candidate": evidence / "frozen_candidate.json",
        "runs": evidence / "runs.csv",
        "summary": evidence / "summary.csv",
        "paired_summary": evidence / "paired_summary.csv",
        "validation": evidence / "validation_comparison.csv",
    }
    missing = [path.name for path in files.values() if not path.exists()]
    if missing:
        return _missing_bundle(
            root_path,
            "Falta evidencia precomputada: "
            + ", ".join(sorted(missing))
            + ". Ejecute `python scripts/generate_evidence.py`.",
        )
    try:
        return EvidenceBundle(
            available=True,
            root=root_path,
            manifest=json.loads(files["manifest"].read_text(encoding="utf-8")),
            candidate=json.loads(files["candidate"].read_text(encoding="utf-8")),
            runs=pd.read_csv(files["runs"]),
            summary=pd.read_csv(files["summary"]),
            paired_summary=pd.read_csv(files["paired_summary"]),
            validation=pd.read_csv(files["validation"]),
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _missing_bundle(root_path, f"La evidencia no puede leerse: {error}")


@st.cache_data(max_entries=2, show_spinner=False)
def load_calibration_metadata(root: Path | str | None = None) -> dict[str, Any]:
    """Load provenance metadata used in the model page."""

    root_path = Path(root).resolve() if root is not None else project_root()
    path = root_path / "data" / "processed" / "calibration_metadata.json"
    return json.loads(path.read_text(encoding="utf-8"))


def source_label(category: str) -> str:
    """Return a provenance label that does not rely on color."""

    return SOURCE_LABELS.get(category, category.replace("_", " ").title())


def _missing_bundle(root: Path, message: str) -> EvidenceBundle:
    return EvidenceBundle(
        available=False,
        root=root,
        manifest={},
        candidate={},
        runs=pd.DataFrame(),
        summary=pd.DataFrame(),
        paired_summary=pd.DataFrame(),
        validation=pd.DataFrame(),
        error=message,
    )
