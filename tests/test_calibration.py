"""Tests for the NHAMCS calibration pipeline.

Most tests use a small synthetic fixed-width file built with the same layout
mechanism as the official one, so they run without the raw NHAMCS download. The
versioned processed files are checked for schema and probability constraints,
and an integration test runs against the official file when it is present.
"""

from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ed_simulation.calibration import (
    OUTPUT_FILES,
    REQUIRED_VARIABLES,
    SOURCE_CATEGORIES,
    build_calibration_tables,
    build_metadata,
    calibrated_inputs,
    clean_visits,
    load_calibrated_config,
    parse_infix_dictionary,
    read_public_use_file,
    survey_mean,
    validate_public_use_file,
    weighted_quantile,
    write_processed_outputs,
)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

# Width of each synthetic field; positions are assigned consecutively.
WIDTHS = {
    "VMONTH": 2,
    "ARRTIME": 4,
    "WAITTIME": 4,
    "LOV": 4,
    "IMMEDR": 2,
    "LWBS": 1,
    "LBTC": 1,
    "LEFTAMA": 1,
    "BOARDED": 4,
    "HOSPCODE": 3,
    "CSTRATM": 8,
    "CPSUM": 6,
    "PATWT": 11,
    "EDWT": 9,
    "YEAR": 4,
}


def _dictionary_text() -> str:
    lines = ["infix dictionary {"]
    position = 1
    for name in REQUIRED_VARIABLES:
        width = WIDTHS[name]
        span = f"{position}-{position + width - 1}" if width > 1 else str(position)
        lines.append(f"  int {name} {span}")
        position += width
    lines.append("}")
    return "\n".join(lines) + "\n"


def _record(values: dict[str, object]) -> str:
    return "".join(str(values[name]).rjust(WIDTHS[name]) for name in REQUIRED_VARIABLES)


def _base_values(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "VMONTH": 1,
        "ARRTIME": "0930",
        "WAITTIME": 10,
        "LOV": 100,
        "IMMEDR": 3,
        "LWBS": 0,
        "LBTC": 0,
        "LEFTAMA": 0,
        "BOARDED": -7,
        "HOSPCODE": 1,
        "CSTRATM": 1,
        "CPSUM": 1,
        "PATWT": "100.00000",
        "EDWT": ".",
        "YEAR": 2022,
    }
    values.update(changes)
    return values


def _fixture_records() -> list[dict[str, object]]:
    """Two EDs, two strata, special codes in every relevant variable."""

    return [
        _base_values(ARRTIME="0005", WAITTIME=5, IMMEDR=1, EDWT="2.00000", CPSUM=1),
        _base_values(ARRTIME="0130", WAITTIME=20, IMMEDR=2, CPSUM=1),
        _base_values(ARRTIME="1015", WAITTIME=90, IMMEDR=3, CPSUM=2, PATWT="300.00000"),
        _base_values(ARRTIME="-9", WAITTIME=-9, IMMEDR=-8, CPSUM=2),
        _base_values(
            ARRTIME="1500",
            WAITTIME=-7,
            IMMEDR=4,
            LWBS=1,
            HOSPCODE=2,
            CSTRATM=2,
            CPSUM=3,
            EDWT="4.00000",
        ),
        _base_values(
            ARRTIME="2359",
            WAITTIME=30,
            LOV=400,
            BOARDED=200,
            IMMEDR=5,
            HOSPCODE=2,
            CSTRATM=2,
            CPSUM=4,
        ),
        _base_values(ARRTIME="1200", WAITTIME=45, IMMEDR=0, HOSPCODE=2, CSTRATM=2, CPSUM=4),
        _base_values(ARRTIME="1800", WAITTIME=61, IMMEDR=7, HOSPCODE=2, CSTRATM=2, CPSUM=3),
    ]


@pytest.fixture()
def fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    dictionary = tmp_path / "dict.dct"
    dictionary.write_text(_dictionary_text(), encoding="latin-1")
    data = tmp_path / "data.txt"
    data.write_text("\r\n".join(_record(r) for r in _fixture_records()) + "\r\n")
    return data, dictionary


@pytest.fixture()
def fixture_frame(fixture_files: tuple[Path, Path]) -> pd.DataFrame:
    return read_public_use_file(*fixture_files)


# --------------------------------------------------------------------------- #
# Reading and validation
# --------------------------------------------------------------------------- #


def test_parse_infix_dictionary_positions() -> None:
    specs = parse_infix_dictionary("infix dictionary {\n  str ARRTIME 4-7\n  byte VDAYR 3\n}")
    assert (specs["ARRTIME"].start, specs["ARRTIME"].end) == (4, 7)
    assert (specs["VDAYR"].start, specs["VDAYR"].end) == (3, 3)


def test_parse_infix_dictionary_rejects_empty() -> None:
    with pytest.raises(ValueError):
        parse_infix_dictionary("not a dictionary")


def test_read_plain_and_zip_are_identical(fixture_files, tmp_path: Path) -> None:
    data, dictionary = fixture_files
    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.write(data, arcname="ed2022")
    pd.testing.assert_frame_equal(
        read_public_use_file(data, dictionary),
        read_public_use_file(archive, dictionary),
    )


def test_read_rejects_wrong_record_length(fixture_files) -> None:
    data, dictionary = fixture_files
    data.write_text(data.read_text() + "short line\n")
    with pytest.raises(ValueError, match="longitud"):
        read_public_use_file(data, dictionary)


def test_stata_missing_marker_becomes_nan(fixture_frame: pd.DataFrame) -> None:
    assert fixture_frame["EDWT"].notna().sum() == 2
    assert fixture_frame["EDWT"].max() == 4.0


def test_validation_detects_wrong_file(fixture_frame: pd.DataFrame) -> None:
    total = float(fixture_frame["PATWT"].sum())
    checks = validate_public_use_file(
        fixture_frame, expected_records=8, expected_total_weight=total
    )
    assert checks["hospitals_with_edwt"] == 2
    with pytest.raises(ValueError, match="registros"):
        validate_public_use_file(fixture_frame, expected_total_weight=total)
    with pytest.raises(ValueError, match="PATWT"):
        validate_public_use_file(
            fixture_frame, expected_records=8, expected_total_weight=total + 100
        )
    wrong_year = fixture_frame.assign(YEAR=2021)
    with pytest.raises(ValueError, match="2022"):
        validate_public_use_file(wrong_year, expected_records=8, expected_total_weight=total)


# --------------------------------------------------------------------------- #
# Special codes and cleaning
# --------------------------------------------------------------------------- #


def test_special_codes_are_missing_not_numbers(fixture_frame: pd.DataFrame) -> None:
    visits = clean_visits(fixture_frame)
    assert visits["arrival_hour"].isna().sum() == 1
    assert visits["wait_minutes"].isna().sum() == 2  # -9 and -7
    assert visits["triage_level"].isna().sum() == 3  # -8, 0 and 7
    assert (visits["wait_minutes"].dropna() >= 0).all()
    assert set(visits["triage_level"].dropna()) <= {1, 2, 3, 4, 5}


def test_arrival_hour_and_block(fixture_frame: pd.DataFrame) -> None:
    visits = clean_visits(fixture_frame)
    assert visits["arrival_hour"].tolist()[:3] == [0, 1, 10]
    assert visits.loc[5, "arrival_hour"] == 23
    assert visits.loc[5, "arrival_block"] == 5


def test_service_proxy_subtracts_boarding_and_excludes_left_early(
    fixture_frame: pd.DataFrame,
) -> None:
    visits = clean_visits(fixture_frame)
    assert visits.loc[5, "service_proxy_minutes"] == 400 - 30 - 200
    assert visits.loc[0, "service_proxy_minutes"] == 100 - 5
    assert math.isnan(visits.loc[4, "service_proxy_minutes"])  # LWBS
    assert math.isnan(visits.loc[3, "service_proxy_minutes"])  # blank wait


def test_undocumented_negative_code_fails(fixture_frame: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="no documentados"):
        clean_visits(fixture_frame.assign(LOV=-3))


def test_invalid_military_time_fails(fixture_frame: pd.DataFrame) -> None:
    broken = fixture_frame.copy()
    broken.loc[0, "ARRTIME"] = 1275
    with pytest.raises(ValueError, match="HHMM"):
        clean_visits(broken)


# --------------------------------------------------------------------------- #
# Estimators
# --------------------------------------------------------------------------- #


def test_weighted_quantile_inverted_cdf() -> None:
    assert weighted_quantile([1, 2, 3], [1, 1, 1], 0.5) == 2
    assert weighted_quantile([1, 2, 3], [1, 1, 8], 0.5) == 3
    assert weighted_quantile([5, 1], [1, 1], 0.0) == 1
    assert weighted_quantile([5, 1], [1, 1], 1.0) == 5
    assert math.isnan(weighted_quantile([], [], 0.5))
    with pytest.raises(ValueError):
        weighted_quantile([1], [1], 1.5)


def test_survey_mean_matches_classical_standard_error() -> None:
    values = pd.Series([2.0, 4.0, 9.0, 1.0, 7.0])
    one = pd.Series(1.0, index=values.index)
    result = survey_mean(values, one, one, pd.Series(range(5)))
    assert result.estimate == pytest.approx(values.mean())
    assert result.standard_error == pytest.approx(values.std(ddof=1) / math.sqrt(5))


def test_survey_mean_uses_weights_and_domain() -> None:
    values = pd.Series([10.0, 20.0, np.nan, 40.0])
    weights = pd.Series([1.0, 3.0, 5.0, 1.0])
    domain = pd.Series([True, True, True, False])
    result = survey_mean(values, weights, pd.Series(1, index=values.index), pd.Series(range(4)), domain)
    assert result.estimate == pytest.approx((10 + 60) / 4)
    assert result.n_unweighted == 2


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #


def test_profiles_from_fixture(fixture_frame: pd.DataFrame) -> None:
    tables = build_calibration_tables(fixture_frame)
    hourly, triage = tables["hourly_profile"], tables["triage_profile"]
    assert list(hourly["hour"]) == list(range(24))
    assert hourly["share"].sum() == pytest.approx(1.0, abs=1e-5)
    assert hourly["n_unweighted"].sum() == 7
    assert triage["share"].sum() == pytest.approx(1.0, abs=1e-5)
    # Weighted: level 3 has PATWT 300 among triaged weights 100+100+300+100+100 = 700.
    assert triage.set_index("triage_level").loc[3, "share"] == pytest.approx(3 / 7, abs=1e-6)

    volume = tables["reference_volume"].set_index("statistic")
    total = float(fixture_frame["PATWT"].sum())
    assert volume.loc["mean_per_ed", "annual_visits"] == pytest.approx(total / 6.0, abs=0.01)
    assert volume.loc["mean_per_ed", "daily_visits"] == pytest.approx(total / 6.0 / 365, rel=1e-4)

    metrics = tables["reference_metrics"]
    overall = metrics[(metrics.group_type == "overall")].set_index("metric")["value"]
    expected = np.average([5, 20, 90, 30, 45, 61], weights=[100, 100, 300, 100, 100, 100])
    assert overall["mean_wait_minutes"] == pytest.approx(round(expected, 4))
    assert overall["share_wait_over_60"] == pytest.approx(round(400 / 800, 4))


def test_outputs_are_deterministic(fixture_frame: pd.DataFrame, tmp_path: Path) -> None:
    checks = {"records": len(fixture_frame)}
    contents = []
    for run in ("a", "b"):
        tables = build_calibration_tables(fixture_frame)
        metadata = build_metadata(fixture_frame, checks, [])
        paths = write_processed_outputs(tables, metadata, tmp_path / run)
        contents.append({path.name: path.read_bytes() for path in paths})
    assert contents[0] == contents[1]


# --------------------------------------------------------------------------- #
# Versioned processed files
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "key",
    ["hourly_profile", "triage_profile", "reference_volume", "reference_metrics", "service_proxy"],
)
def test_processed_files_have_units_and_provenance(key: str) -> None:
    table = pd.read_csv(PROCESSED / OUTPUT_FILES[key])
    assert "unit" in table.columns and table["unit"].notna().all()
    assert set(table["source_category"]) <= set(SOURCE_CATEGORIES)
    assert (table["n_unweighted"] if "n_unweighted" in table else table["n_eds"]).min() > 0


def test_processed_probabilities_sum_to_one() -> None:
    hourly = pd.read_csv(PROCESSED / OUTPUT_FILES["hourly_profile"])
    triage = pd.read_csv(PROCESSED / OUTPUT_FILES["triage_profile"])
    assert list(hourly["hour"]) == list(range(24))
    assert hourly["share"].between(0, 1).all()
    assert triage["share"].between(0, 1).all()
    assert hourly["share"].sum() == pytest.approx(1.0, abs=1e-4)
    assert triage["share"].sum() == pytest.approx(1.0, abs=1e-4)
    assert (hourly["share_ci95_low"] <= hourly["share"]).all()
    assert (hourly["share"] <= hourly["share_ci95_high"]).all()


def test_reference_metrics_ranges() -> None:
    metrics = pd.read_csv(PROCESSED / OUTPUT_FILES["reference_metrics"])
    minutes = metrics[metrics["unit"] == "minutes"]["value"]
    shares = metrics[metrics["unit"] == "proportion"]["value"]
    assert (minutes >= 0).all()
    assert shares.between(0, 1).all()
    assert {"overall", "triage_level", "arrival_block"} == set(metrics["group_type"])


def test_metadata_documents_outputs_and_limitation() -> None:
    metadata = json.loads((PROCESSED / OUTPUT_FILES["metadata"]).read_text(encoding="utf-8"))
    for key, filename in OUTPUT_FILES.items():
        if key != "metadata":
            assert metadata["outputs"][filename]["source_category"] in SOURCE_CATEGORIES
            assert metadata["outputs"][filename]["unit"]
    assert all(len(entry["sha256"]) == 64 for entry in metadata["source_files"])
    assert "Guatemala" in metadata["scope_limitation"]
    assert metadata["model_inputs"]["service_medians_minutes"]["source_category"] == (
        "estimated_assumption"
    )


def test_calibrated_config_is_valid_and_scales_with_demand() -> None:
    config = load_calibrated_config(PROCESSED)
    inputs = calibrated_inputs(PROCESSED)
    assert sum(config.triage_probabilities) == pytest.approx(1.0, abs=1e-12)
    assert sum(config.arrival_rates) == pytest.approx(inputs["daily_visits"])
    higher = load_calibrated_config(PROCESSED, demand_multiplier=1.2)
    assert sum(higher.arrival_rates) == pytest.approx(1.2 * sum(config.arrival_rates))
    with pytest.raises(ValueError):
        calibrated_inputs(PROCESSED, reference_volume="unknown")
    with pytest.raises(ValueError):
        calibrated_inputs(PROCESSED, demand_multiplier=0)


# --------------------------------------------------------------------------- #
# Official file (only when downloaded)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not (RAW / "ed2022.zip").exists() or not (RAW / "eddict2022.dct").exists(),
    reason="requiere python scripts/download_nhamcs.py",
)
def test_official_file_reproduces_versioned_outputs(tmp_path: Path) -> None:
    frame = read_public_use_file(RAW / "ed2022.zip", RAW / "eddict2022.dct")
    checks = validate_public_use_file(frame)
    assert checks["records"] == 16_025
    tables = build_calibration_tables(frame)
    for key, table in tables.items():
        written = tmp_path / OUTPUT_FILES[key]
        table.to_csv(written, index=False, lineterminator="\n")
        assert written.read_bytes() == (PROCESSED / OUTPUT_FILES[key]).read_bytes()
