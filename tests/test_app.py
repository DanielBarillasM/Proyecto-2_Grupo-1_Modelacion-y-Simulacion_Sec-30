"""Streamlit AppTest coverage for navigation, forms and evidence states."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ed_simulation.ui import scenario
from ed_simulation.ui.data import load_evidence_bundle
from ed_simulation.ui.scenario import parse_capacity_schedule


ROOT = Path(__file__).resolve().parents[1]


def run_page(relative_path: str) -> AppTest:
    return AppTest.from_file(
        str(ROOT / relative_path), default_timeout=15
    ).run()


@pytest.mark.parametrize(
    "relative_path",
    (
        "app.py",
        "app_pages/summary.py",
        "app_pages/model.py",
        "app_pages/laboratory.py",
        "app_pages/optimization.py",
        "app_pages/evidence.py",
    ),
)
def test_every_page_loads_without_exception(relative_path: str) -> None:
    app = run_page(relative_path)

    assert not app.exception


def test_laboratory_does_not_execute_before_submit(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("la simulación no debe ejecutarse al cargar")

    monkeypatch.setattr(scenario, "run_calibrated_scenario", fail_if_called)
    app = run_page("app_pages/laboratory.py")

    assert not app.exception
    assert app.session_state["laboratory_result"] is None
    assert any("no calcula nada" in item.value for item in app.info)


def test_laboratory_reports_invalid_capacity() -> None:
    app = run_page("app_pages/laboratory.py")
    app.text_input[0].set_value("3,4")
    app.button[0].click()
    app.run()

    assert not app.exception
    assert any("exactamente seis bloques" in item.value for item in app.error)


def test_laboratory_runs_short_scenario_on_submit() -> None:
    app = run_page("app_pages/laboratory.py")
    app.text_input[0].set_value("3,3,4,4,5,4")
    app.button[0].click()
    app.run(timeout=15)

    assert not app.exception
    assert app.success
    assert app.session_state["laboratory_result"] is not None
    assert {metric.label for metric in app.metric} >= {
        "Espera media",
        "Percentil 90",
        "Utilización",
    }


def test_missing_evidence_has_actionable_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ED_SIM_PROJECT_ROOT", str(tmp_path))
    load_evidence_bundle.clear()
    app = run_page("app_pages/evidence.py")
    load_evidence_bundle.clear()

    assert not app.exception
    assert any("generate_evidence.py" in item.value for item in app.error)


def test_model_displays_provenance_labels() -> None:
    app = run_page("app_pages/model.py")
    table = app.dataframe[0].value

    assert "Procedencia" in table.columns
    assert "Derivado de datos públicos" in set(table["Procedencia"])
    assert "Supuesto estimado" in set(table["Procedencia"])


def test_capacity_parser_rejects_ambiguous_values() -> None:
    assert parse_capacity_schedule("3,3,4,4,5,4") == (3, 3, 4, 4, 5, 4)
    with pytest.raises(ValueError, match="seis bloques"):
        parse_capacity_schedule("3,4")
    with pytest.raises(ValueError, match="enteros"):
        parse_capacity_schedule("3,3,cuatro,4,5,4")


def test_deprecated_layout_argument_is_absent() -> None:
    paths = [ROOT / "app.py", *sorted((ROOT / "app_pages").glob("*.py"))]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "use_container_width" not in text
    assert "st.radio(" not in text
