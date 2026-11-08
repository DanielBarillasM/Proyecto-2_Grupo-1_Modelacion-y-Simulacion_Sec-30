"""Reproducible calibration of model inputs from the NHAMCS 2022 ED public file.

The module separates four steps so that each one can be audited and tested:

1. ``read_public_use_file`` reads the official fixed-width file using the column
   positions published in the official Stata ``infix`` dictionary.
2. ``validate_public_use_file`` rejects files that do not match the 2022
   documentation (record count, survey year and total visit weight).
3. ``clean_visits`` converts documented special codes (``-9`` blank, ``-8``
   unknown, ``-7`` not applicable, triage ``0``/``7`` = no nursing triage) into
   missing values. A special code is never interpreted as a clinical quantity.
4. The ``*_profile`` / ``*_metrics`` functions produce small aggregated tables with
   units, unweighted sample sizes, ``PATWT``-weighted estimates and a provenance
   label (``observed_public``, ``derived_from_public``, ``estimated_assumption`` or
   ``synthetic_simulation``).

Standard errors use Taylor linearization with the masked design variables
``CSTRATM`` (stratum) and ``CPSUM`` (cluster), as recommended by the NHAMCS
documentation for variance estimation with ultimate cluster designs. Confidence
intervals use a normal approximation.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from .config import SimulationConfig, default_config

# --------------------------------------------------------------------------- #
# Source description
# --------------------------------------------------------------------------- #

SURVEY_YEAR = 2022
EXPECTED_RECORDS = 16_025
# Documentation, Section I: "the user can obtain the estimated total of
# 155,397,747 ED visits made in the United States".
EXPECTED_TOTAL_WEIGHT = 155_397_747.0
TOTAL_WEIGHT_TOLERANCE = 5.0
DAYS_PER_YEAR = 365
Z_95 = 1.959963984540054
MIN_RELIABLE_RECORDS = 30
MAX_RELIABLE_RSE = 0.30

SOURCE_CATEGORIES = (
    "observed_public",
    "derived_from_public",
    "estimated_assumption",
    "synthetic_simulation",
)

_FTP = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS"


@dataclass(frozen=True)
class SourceFile:
    """One official file with the checksum used to detect wrong downloads."""

    key: str
    url: str
    filename: str
    sha256: str
    size_bytes: int
    description: str
    required: bool = True


NHAMCS_2022_FILES: tuple[SourceFile, ...] = (
    SourceFile(
        key="data",
        url=f"{_FTP}/Datasets/NHAMCS/ed2022.zip",
        filename="ed2022.zip",
        sha256="a513693ed05b98bf94d2ff48b50de85afe48dd63cd7d43fb0930f914b18a9f25",
        size_bytes=1_666_841,
        description="NHAMCS 2022 ED public use micro-data file (fixed-width ASCII, zipped)",
    ),
    SourceFile(
        key="dictionary",
        url=f"{_FTP}/dataset_documentation/NHAMCS/stata/eddict2022.dct",
        filename="eddict2022.dct",
        sha256="00f8bf6cf09bfa3f216ee560a68d4309573c6b7ea931fa022a5bbbcae260014f",
        size_bytes=21_447,
        description="Official Stata infix dictionary with column positions",
    ),
    SourceFile(
        key="documentation",
        url=f"{_FTP}/dataset_documentation/NHAMCS/doc22-ed-508.pdf",
        filename="doc22-ed-508.pdf",
        sha256="2f79b33f790eb26e7d737ddb49169af66df047503f07e3ba2da07e92f6661490",
        size_bytes=2_646_922,
        description="2022 NHAMCS ED public use file documentation (codebook)",
        required=False,
    ),
)

# Variables read from the public file. Positions come from the dictionary.
REQUIRED_VARIABLES: tuple[str, ...] = (
    "VMONTH",
    "ARRTIME",
    "WAITTIME",
    "LOV",
    "IMMEDR",
    "LWBS",
    "LBTC",
    "LEFTAMA",
    "BOARDED",
    "HOSPCODE",
    "CSTRATM",
    "CPSUM",
    "PATWT",
    "EDWT",
    "YEAR",
)

# Special codes taken from the 2022 codebook (Section II.A).
SPECIAL_CODES: dict[str, dict[int, str]] = {
    "ARRTIME": {-9: "blank"},
    "WAITTIME": {-9: "blank", -7: "not_applicable_not_seen_by_provider"},
    "LOV": {-9: "blank"},
    "IMMEDR": {
        -9: "blank",
        -8: "unknown",
        0: "no_triage_reported_in_esa_that_triages",
        7: "esa_does_not_conduct_nursing_triage",
    },
    "BOARDED": {-9: "missing", -7: "not_applicable"},
}

TRIAGE_LABELS: dict[int, str] = {
    1: "Immediate",
    2: "Emergent",
    3: "Urgent",
    4: "Semi-urgent",
    5: "Nonurgent",
}

# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FieldSpec:
    """Column position of one variable (1-based, inclusive, as in the codebook)."""

    name: str
    storage: str
    start: int
    end: int


_INFIX_LINE = re.compile(r"^\s*(\w+)\s+(\w+)\s+(\d+)(?:-(\d+))?\s*$")


def parse_infix_dictionary(text: str) -> dict[str, FieldSpec]:
    """Parse a Stata ``infix dictionary`` into column specifications."""

    specs: dict[str, FieldSpec] = {}
    for line in text.splitlines():
        match = _INFIX_LINE.match(line)
        if not match:
            continue
        storage, name, start, end = match.groups()
        start_pos = int(start)
        end_pos = int(end) if end else start_pos
        if end_pos < start_pos:
            raise ValueError(f"posición inválida para {name}: {start_pos}-{end_pos}")
        specs[name] = FieldSpec(name, storage, start_pos, end_pos)
    if not specs:
        raise ValueError("el diccionario no contiene variables con posiciones")
    return specs


def _read_text_member(path: Path) -> str:
    """Return the fixed-width text, reading the single member of a zip if needed."""

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) != 1:
                raise ValueError(
                    f"se esperaba un único archivo dentro de {path.name}, "
                    f"se encontraron {len(members)}"
                )
            raw = archive.read(members[0])
    else:
        raw = path.read_bytes()
    return raw.decode("latin-1")


def read_public_use_file(
    data_path: Path | str,
    dictionary_path: Path | str,
    variables: Iterable[str] = REQUIRED_VARIABLES,
) -> pd.DataFrame:
    """Read selected variables from the official fixed-width file.

    Every record must have exactly the length implied by the dictionary; a
    different length indicates a wrong year, a truncated download or a different
    layout. Values are returned as numeric raw codes (special codes included).
    """

    specs = parse_infix_dictionary(Path(dictionary_path).read_text(encoding="latin-1"))
    variables = tuple(variables)
    missing = [name for name in variables if name not in specs]
    if missing:
        raise ValueError(f"el diccionario no define las variables: {missing}")
    record_length = max(spec.end for spec in specs.values())

    lines = _read_text_member(Path(data_path)).splitlines()
    lines = [line for line in lines if line.strip()]
    bad = [index for index, line in enumerate(lines) if len(line) != record_length]
    if bad:
        raise ValueError(
            f"{len(bad)} registros no tienen longitud {record_length}; "
            "el archivo no coincide con el diccionario"
        )

    selected = [specs[name] for name in variables]
    frame = pd.read_fwf(
        io.StringIO("\n".join(lines)),
        colspecs=[(spec.start - 1, spec.end) for spec in selected],
        names=[spec.name for spec in selected],
        dtype=str,
        header=None,
    )
    for column in frame.columns:
        text = frame[column].str.strip()
        # A lone "." is the Stata/SAS missing marker (e.g. EDWT outside the first
        # record of each ED). It is converted to NaN, never to zero.
        frame[column] = pd.to_numeric(text.where(text != "."), errors="raise")
    return frame


def validate_public_use_file(
    frame: pd.DataFrame,
    *,
    expected_records: int = EXPECTED_RECORDS,
    expected_total_weight: float = EXPECTED_TOTAL_WEIGHT,
    weight_tolerance: float = TOTAL_WEIGHT_TOLERANCE,
    survey_year: int = SURVEY_YEAR,
) -> dict[str, Any]:
    """Check the file against the documentation and return the checks performed."""

    checks = {
        "records": int(len(frame)),
        "expected_records": expected_records,
        "years": sorted(int(year) for year in frame["YEAR"].dropna().unique()),
        "total_patwt": round(float(frame["PATWT"].sum()), 5),
        "expected_total_patwt": expected_total_weight,
        "hospitals": int(frame["HOSPCODE"].nunique()),
        "hospitals_with_edwt": int((frame["EDWT"].fillna(0) > 0).sum()),
    }
    if checks["records"] != expected_records:
        raise ValueError(
            f"se esperaban {expected_records} registros y se leyeron {checks['records']}"
        )
    if checks["years"] != [survey_year]:
        raise ValueError(f"el archivo no corresponde a {survey_year}: {checks['years']}")
    if abs(checks["total_patwt"] - expected_total_weight) > weight_tolerance:
        raise ValueError(
            "la suma de PATWT no coincide con el total documentado "
            f"({checks['total_patwt']} frente a {expected_total_weight})"
        )
    if (frame["PATWT"] <= 0).any():
        raise ValueError("PATWT debe ser positivo en todos los registros")
    return checks


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #


def _without_special(series: pd.Series, variable: str) -> pd.Series:
    """Replace documented special codes by NaN and reject undocumented negatives."""

    codes = SPECIAL_CODES.get(variable, {})
    cleaned = series.astype(float).where(~series.isin(list(codes)))
    unexpected = cleaned[cleaned < 0]
    if not unexpected.empty:
        raise ValueError(
            f"{variable} contiene valores negativos no documentados: "
            f"{sorted(unexpected.unique().tolist())[:5]}"
        )
    return cleaned


def clean_visits(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert raw codes into analysis variables with explicit units.

    Returned columns
    ----------------
    arrival_hour : float (0-23) or NaN
    arrival_block : float (0-5) or NaN, four-hour blocks used by the model
    wait_minutes : float or NaN; WAITTIME to first physician/APRN/PA contact
    lov_minutes : float or NaN; length of visit
    triage_level : float (1-5) or NaN; IMMEDR levels without triage codes
    boarded_minutes : float or NaN
    service_proxy_minutes : float or NaN; see ``service_proxy_profile``
    weight, stratum, psu, hospital, edwt
    """

    arrtime = _without_special(frame["ARRTIME"], "ARRTIME")
    hours = np.floor(arrtime / 100)
    minutes = arrtime - hours * 100
    invalid_time = arrtime.notna() & ((hours > 23) | (minutes > 59))
    if invalid_time.any():
        raise ValueError(f"{int(invalid_time.sum())} valores de ARRTIME no son HHMM")

    triage = _without_special(frame["IMMEDR"], "IMMEDR")
    if not triage.dropna().isin(list(TRIAGE_LABELS)).all():
        raise ValueError("IMMEDR contiene niveles no documentados")

    wait = _without_special(frame["WAITTIME"], "WAITTIME")
    lov = _without_special(frame["LOV"], "LOV")
    boarded = _without_special(frame["BOARDED"], "BOARDED")
    left_early = (
        frame["LWBS"].eq(1) | frame["LBTC"].eq(1) | frame["LEFTAMA"].eq(1)
    )

    # Post-contact time: what remains of the visit after first provider contact,
    # minus documented boarding. It still includes tests, results and internal
    # waits, so it is an upper bound for the time one care team is occupied.
    proxy = lov - wait - boarded.fillna(0.0)
    proxy = proxy.where(wait.notna() & lov.notna() & ~left_early & (proxy > 0))

    return pd.DataFrame(
        {
            "arrival_hour": hours,
            "arrival_block": np.floor(hours / 4),
            "wait_minutes": wait,
            "lov_minutes": lov,
            "triage_level": triage,
            "boarded_minutes": boarded,
            "service_proxy_minutes": proxy,
            "left_before_complete": left_early,
            "weight": frame["PATWT"].astype(float),
            "stratum": frame["CSTRATM"],
            "psu": frame["CPSUM"],
            "hospital": frame["HOSPCODE"],
            "edwt": frame["EDWT"].astype(float),
        }
    )


def missing_value_report(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Count each documented special code, unweighted, for the metadata file."""

    rows = []
    for variable, codes in SPECIAL_CODES.items():
        for code, meaning in codes.items():
            rows.append(
                {
                    "variable": variable,
                    "code": code,
                    "meaning": meaning,
                    "records": int((frame[variable] == code).sum()),
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# Estimators
# --------------------------------------------------------------------------- #


def weighted_quantile(
    values: Iterable[float],
    weights: Iterable[float],
    quantile: float,
) -> float:
    """Inverted weighted CDF: smallest value whose cumulative weight share >= q."""

    if not 0 <= quantile <= 1:
        raise ValueError("quantile debe estar entre 0 y 1")
    x = np.asarray(list(values), dtype=float)
    w = np.asarray(list(weights), dtype=float)
    keep = ~np.isnan(x)
    x, w = x[keep], w[keep]
    if x.size == 0:
        return float("nan")
    if (w < 0).any() or w.sum() <= 0:
        raise ValueError("los pesos deben ser no negativos y sumar más que cero")
    order = np.argsort(x, kind="mergesort")
    x, w = x[order], w[order]
    cumulative = np.cumsum(w) / w.sum()
    index = int(np.searchsorted(cumulative, quantile - 1e-12, side="left"))
    return float(x[min(index, x.size - 1)])


@dataclass(frozen=True)
class SurveyEstimate:
    """Weighted mean (or proportion) with its design-based uncertainty."""

    estimate: float
    standard_error: float
    n_unweighted: int
    weighted_total: float

    @property
    def ci_low(self) -> float:
        return self.estimate - Z_95 * self.standard_error

    @property
    def ci_high(self) -> float:
        return self.estimate + Z_95 * self.standard_error

    @property
    def relative_standard_error(self) -> float:
        if self.estimate == 0:
            return float("inf") if self.standard_error > 0 else 0.0
        return abs(self.standard_error / self.estimate)


def survey_mean(
    values: pd.Series,
    weights: pd.Series,
    strata: pd.Series,
    psu: pd.Series,
    domain: pd.Series | None = None,
) -> SurveyEstimate:
    """Domain mean with Taylor-linearized variance (with-replacement clusters).

    Records outside the domain, or with missing ``values``, contribute zero but
    keep their clusters in the design, which is the correct treatment of domain
    estimation. Strata with a single cluster are centred on the overall mean of
    cluster totals (the conservative "adjust" convention).
    """

    in_domain = values.notna()
    if domain is not None:
        in_domain &= domain.fillna(False).astype(bool)
    w = weights.where(in_domain, 0.0).astype(float)
    y = values.where(in_domain, 0.0).astype(float)
    total_weight = float(w.sum())
    n = int(in_domain.sum())
    if n == 0 or total_weight <= 0:
        return SurveyEstimate(float("nan"), float("nan"), 0, 0.0)

    estimate = float((w * y).sum() / total_weight)
    linearized = w * (y - estimate) / total_weight
    cluster_totals = (
        pd.DataFrame({"stratum": strata, "psu": psu, "z": linearized})
        .groupby(["stratum", "psu"], sort=True)["z"]
        .sum()
    )
    grand_mean = float(cluster_totals.mean())
    variance = 0.0
    for _, totals in cluster_totals.groupby(level="stratum"):
        clusters = len(totals)
        if clusters > 1:
            deviations = totals - totals.mean()
            variance += clusters / (clusters - 1) * float((deviations**2).sum())
        else:
            variance += float(((totals - grand_mean) ** 2).sum())
    return SurveyEstimate(estimate, float(np.sqrt(variance)), n, total_weight)


def _is_reliable(estimate: SurveyEstimate) -> bool:
    """Simplified screen: at least 30 records and relative standard error <= 30 %."""

    return (
        estimate.n_unweighted >= MIN_RELIABLE_RECORDS
        and estimate.relative_standard_error <= MAX_RELIABLE_RSE
    )


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #


def _share_rows(
    visits: pd.DataFrame,
    column: str,
    levels: Iterable[int],
) -> list[dict[str, Any]]:
    """Weighted share of each level among records where ``column`` is valid."""

    valid = visits[column].notna()
    rows = []
    for level in levels:
        indicator = (visits[column] == level).astype(float).where(valid)
        estimate = survey_mean(
            indicator, visits["weight"], visits["stratum"], visits["psu"]
        )
        rows.append(
            {
                "level": level,
                "n_unweighted": int((visits[column] == level).sum()),
                "weighted_visits": round(
                    float(visits.loc[visits[column] == level, "weight"].sum()), 2
                ),
                "share": round(estimate.estimate, 6),
                "share_se": round(estimate.standard_error, 6),
                "share_ci95_low": round(max(0.0, estimate.ci_low), 6),
                "share_ci95_high": round(min(1.0, estimate.ci_high), 6),
                "reliable": _is_reliable(estimate),
            }
        )
    return rows


def hourly_arrival_profile(visits: pd.DataFrame) -> pd.DataFrame:
    """Weighted share of ED visits by arrival hour (records with valid ARRTIME)."""

    table = pd.DataFrame(_share_rows(visits, "arrival_hour", range(24)))
    table = table.rename(columns={"level": "hour"})
    table.insert(1, "unit", "share_of_daily_visits")
    table["source_category"] = "derived_from_public"
    return table


def triage_profile(visits: pd.DataFrame) -> pd.DataFrame:
    """Weighted distribution of IMMEDR levels 1-5 among triaged visits."""

    table = pd.DataFrame(_share_rows(visits, "triage_level", TRIAGE_LABELS))
    table = table.rename(columns={"level": "triage_level"})
    table.insert(1, "label", table["triage_level"].map(TRIAGE_LABELS))
    table.insert(2, "unit", "share_of_triaged_visits")
    table["source_category"] = "derived_from_public"
    return table


def reference_ed_volume(visits: pd.DataFrame) -> pd.DataFrame:
    """Annual and daily visits for a reference emergency department.

    For each sampled ED, ``sum(PATWT) / EDWT`` approximates its annual visits
    because PATWT inflates visits to the national annual total and EDWT inflates
    departments to the national number of EDs. The national ratio of totals gives
    the mean volume per ED; EDWT-weighted quantiles describe a typical ED.
    """

    per_ed = (
        visits.groupby("hospital")
        .agg(patwt=("weight", "sum"), edwt=("edwt", "max"), records=("weight", "size"))
        .query("edwt > 0")
    )
    if per_ed.empty:
        raise ValueError("no hay departamentos con EDWT positivo")
    per_ed["annual_visits"] = per_ed["patwt"] / per_ed["edwt"]
    n_eds = int(len(per_ed))

    rows = [
        (
            "mean_per_ed",
            float(visits["weight"].sum() / per_ed["edwt"].sum()),
            "sum(PATWT) / sum(EDWT)",
        )
    ]
    for label, q in (("p25_ed", 0.25), ("median_ed", 0.50), ("p75_ed", 0.75)):
        rows.append(
            (
                label,
                weighted_quantile(per_ed["annual_visits"], per_ed["edwt"], q),
                f"EDWT-weighted quantile {q:.2f} of sum(PATWT)/EDWT per ED",
            )
        )
    return pd.DataFrame(
        [
            {
                "statistic": name,
                "annual_visits": round(value, 2),
                "daily_visits": round(value / DAYS_PER_YEAR, 4),
                "unit": "visits_per_ed",
                "n_eds": n_eds,
                "method": method,
                "source_category": "derived_from_public",
            }
            for name, value, method in rows
        ]
    )


def reference_wait_metrics(visits: pd.DataFrame) -> pd.DataFrame:
    """Observed WAITTIME distribution reserved for validation (not for fitting).

    Population: visits with a valid WAITTIME (seen by a provider and not blank).
    Groups: all visits, each triage level 1-5 and each four-hour arrival block.
    """

    groups: list[tuple[str, str, pd.Series]] = [
        ("overall", "all", pd.Series(True, index=visits.index))
    ]
    for level, label in TRIAGE_LABELS.items():
        groups.append(("triage_level", str(level), visits["triage_level"] == level))
    for block in range(6):
        groups.append(
            (
                "arrival_block",
                f"{block * 4:02d}-{block * 4 + 4:02d}h",
                visits["arrival_block"] == block,
            )
        )

    rows: list[dict[str, Any]] = []
    wait = visits["wait_minutes"]
    for group_type, group, mask in groups:
        domain = mask & wait.notna()
        n = int(domain.sum())
        mean = survey_mean(wait, visits["weight"], visits["stratum"], visits["psu"], domain)
        over_60 = survey_mean(
            (wait > 60).astype(float).where(wait.notna()),
            visits["weight"],
            visits["stratum"],
            visits["psu"],
            domain,
        )
        subset = visits.loc[domain]
        metrics = [
            ("mean_wait_minutes", "minutes", mean),
            ("share_wait_over_60", "proportion", over_60),
        ]
        for metric, unit, estimate in metrics:
            rows.append(
                {
                    "group_type": group_type,
                    "group": group,
                    "metric": metric,
                    "unit": unit,
                    "value": round(estimate.estimate, 4),
                    "se": round(estimate.standard_error, 4),
                    "ci95_low": round(max(0.0, estimate.ci_low), 4),
                    "ci95_high": round(estimate.ci_high, 4),
                    "n_unweighted": n,
                    "reliable": _is_reliable(estimate),
                }
            )
        for metric, q in (("median_wait_minutes", 0.5), ("p90_wait_minutes", 0.9)):
            rows.append(
                {
                    "group_type": group_type,
                    "group": group,
                    "metric": metric,
                    "unit": "minutes",
                    "value": weighted_quantile(subset["wait_minutes"], subset["weight"], q),
                    "se": np.nan,
                    "ci95_low": np.nan,
                    "ci95_high": np.nan,
                    "n_unweighted": n,
                    "reliable": n >= MIN_RELIABLE_RECORDS,
                }
            )
    table = pd.DataFrame(rows)
    table["source_category"] = "derived_from_public"
    return table


def service_proxy_profile(visits: pd.DataFrame) -> pd.DataFrame:
    """Post-contact visit time by triage level: ``LOV - WAITTIME - BOARDED``.

    Excludes visits that left before completion (LWBS, LBTC, AMA) and
    non-positive values. The result is an upper bound for team occupancy, not a
    direct service time; the lognormal sigma is fitted from the interquartile
    range of log values, ``(ln q75 - ln q25) / 1.349``.
    """

    rows = []
    for level, label in TRIAGE_LABELS.items():
        subset = visits[(visits["triage_level"] == level) & visits["service_proxy_minutes"].notna()]
        values, weights = subset["service_proxy_minutes"], subset["weight"]
        q25 = weighted_quantile(values, weights, 0.25)
        q50 = weighted_quantile(values, weights, 0.50)
        q75 = weighted_quantile(values, weights, 0.75)
        q90 = weighted_quantile(values, weights, 0.90)
        sigma = (np.log(q75) - np.log(q25)) / 1.349 if len(subset) else np.nan
        rows.append(
            {
                "triage_level": level,
                "label": label,
                "unit": "minutes",
                "n_unweighted": int(len(subset)),
                "p25_minutes": q25,
                "median_minutes": q50,
                "p75_minutes": q75,
                "p90_minutes": q90,
                "lognormal_sigma_iqr": round(float(sigma), 4),
                "reliable": len(subset) >= MIN_RELIABLE_RECORDS,
                "interpretation": "upper_bound_of_team_occupancy",
                "source_category": "derived_from_public",
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Pipeline and consumption by the model
# --------------------------------------------------------------------------- #

OUTPUT_FILES = {
    "hourly_profile": "nhamcs_2022_hourly_profile.csv",
    "triage_profile": "nhamcs_2022_triage_profile.csv",
    "reference_volume": "nhamcs_2022_reference_volume.csv",
    "reference_metrics": "nhamcs_2022_reference_metrics.csv",
    "service_proxy": "nhamcs_2022_service_proxy.csv",
    "metadata": "calibration_metadata.json",
}

# The team's choice of reference volume. It is an assumption, documented in
# ``docs/05_data_calibration.md``: the EDWT-weighted median describes a typical
# department, whereas the mean is dominated by very large departments.
DEFAULT_REFERENCE_VOLUME = "median_ed"


def build_calibration_tables(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Clean a validated raw frame and compute every processed table."""

    visits = clean_visits(frame)
    return {
        "hourly_profile": hourly_arrival_profile(visits),
        "triage_profile": triage_profile(visits),
        "reference_volume": reference_ed_volume(visits),
        "reference_metrics": reference_wait_metrics(visits),
        "service_proxy": service_proxy_profile(visits),
    }


def build_metadata(
    frame: pd.DataFrame,
    checks: Mapping[str, Any],
    source_files: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Describe provenance, transformations and labels of the processed outputs."""

    visits = clean_visits(frame)
    return {
        "dataset": "NHAMCS 2022 Emergency Department Public Use File",
        "publisher": "National Center for Health Statistics, CDC",
        "documentation_url": NHAMCS_2022_FILES[2].url,
        "survey_period": "Calendar year 2022; each sampled hospital reports visits during a randomly assigned 4-week reporting period",
        "population": "Visits to emergency departments of noninstitutional general and short-stay hospitals, excluding Federal, military and VA hospitals, in the 50 US states and DC",
        "source_files": list(source_files),
        "validation_checks": dict(checks),
        "sample": {
            "records": int(len(frame)),
            "records_with_valid_arrtime": int(visits["arrival_hour"].notna().sum()),
            "records_with_triage_1_to_5": int(visits["triage_level"].notna().sum()),
            "records_with_valid_waittime": int(visits["wait_minutes"].notna().sum()),
            "records_with_service_proxy": int(visits["service_proxy_minutes"].notna().sum()),
            "design_strata": int(frame["CSTRATM"].nunique()),
            "design_clusters": int(frame[["CSTRATM", "CPSUM"]].drop_duplicates().shape[0]),
        },
        "special_codes": missing_value_report(frame),
        "missing_data_assumption": (
            "Records with special codes are excluded from the estimate that needs "
            "that variable (complete-case within variable). This assumes the "
            "excluded visits resemble the included ones after weighting; IMMEDR "
            "has 27.8 % documented item nonresponse and WAITTIME 14.1 %."
        ),
        "weighting": "All shares, means and quantiles use PATWT; per-ED volumes use EDWT.",
        "variance": (
            "Taylor linearization with CSTRATM and CPSUM (with-replacement "
            "ultimate clusters; singleton strata centred on the overall mean). "
            "95 % intervals use a normal approximation. Quantiles have no SE."
        ),
        "reliability_rule": (
            f"reliable = at least {MIN_RELIABLE_RECORDS} records and relative "
            f"standard error <= {int(MAX_RELIABLE_RSE * 100)} %. This is a "
            "simplified screen, not the complete NCHS 2017 proportion criteria."
        ),
        "outputs": {
            OUTPUT_FILES["hourly_profile"]: {
                "content": "Share of daily visits by arrival hour (ARRTIME)",
                "unit": "proportion; sums to 1",
                "source_category": "derived_from_public",
            },
            OUTPUT_FILES["triage_profile"]: {
                "content": "Share of triaged visits by IMMEDR level 1-5",
                "unit": "proportion; sums to 1",
                "source_category": "derived_from_public",
            },
            OUTPUT_FILES["reference_volume"]: {
                "content": "Annual and daily visits per ED (mean and EDWT-weighted quantiles)",
                "unit": "visits per ED per year / per day",
                "source_category": "derived_from_public",
            },
            OUTPUT_FILES["reference_metrics"]: {
                "content": "WAITTIME mean, median, p90 and share > 60 min, overall, by triage and by 4-hour arrival block",
                "unit": "minutes or proportion",
                "source_category": "derived_from_public",
                "use": "validation target only; must not be used to fit model parameters",
            },
            OUTPUT_FILES["service_proxy"]: {
                "content": "LOV - WAITTIME - BOARDED by triage (post-contact time)",
                "unit": "minutes",
                "source_category": "derived_from_public",
                "use": "upper-bound reference; not adopted as team occupancy",
            },
        },
        "model_inputs": {
            "arrival_rates": {
                "formula": "daily_visits[reference_volume] * hourly_share[h]",
                "reference_volume": DEFAULT_REFERENCE_VOLUME,
                "source_category": "derived_from_public",
                "choice_of_reference_volume": "estimated_assumption",
            },
            "triage_probabilities": {"source_category": "derived_from_public"},
            "service_medians_minutes": {
                "source_category": "estimated_assumption",
                "reason": "LOV includes tests, results, internal waits and boarding; it does not measure the time a single team is occupied.",
            },
            "capacity_schedule": {"source_category": "estimated_assumption"},
        },
        "scope_limitation": (
            "NHAMCS is a national US reference. It does not describe a specific "
            "Guatemalan hospital and cannot show that an intervention was applied "
            "or improved real outcomes."
        ),
    }


def write_processed_outputs(
    tables: Mapping[str, pd.DataFrame],
    metadata: Mapping[str, Any],
    output_dir: Path | str,
) -> list[Path]:
    """Write CSV tables and metadata deterministically (no timestamps)."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for key, table in tables.items():
        path = output_dir / OUTPUT_FILES[key]
        table.to_csv(path, index=False, lineterminator="\n")
        written.append(path)
    metadata_path = output_dir / OUTPUT_FILES["metadata"]
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    written.append(metadata_path)
    return written


def _normalized(values: Iterable[float]) -> tuple[float, ...]:
    array = np.asarray(list(values), dtype=float)
    if (array < 0).any() or array.sum() <= 0:
        raise ValueError("las proporciones deben ser no negativas y sumar más que cero")
    return tuple(float(value) for value in array / array.sum())


def calibrated_inputs(
    processed_dir: Path | str,
    reference_volume: str = DEFAULT_REFERENCE_VOLUME,
    demand_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Return arrival rates and triage probabilities read from processed files.

    Shares are renormalized to remove rounding residue from the CSV files, so
    the configuration validation (sum equal to 1) holds exactly.
    """

    if demand_multiplier <= 0:
        raise ValueError("demand_multiplier debe ser positivo")
    processed_dir = Path(processed_dir)
    hourly = pd.read_csv(processed_dir / OUTPUT_FILES["hourly_profile"]).sort_values("hour")
    triage = pd.read_csv(processed_dir / OUTPUT_FILES["triage_profile"]).sort_values(
        "triage_level"
    )
    volume = pd.read_csv(processed_dir / OUTPUT_FILES["reference_volume"]).set_index(
        "statistic"
    )
    if list(hourly["hour"]) != list(range(24)):
        raise ValueError("el perfil horario debe contener las horas 0 a 23")
    if list(triage["triage_level"]) != list(TRIAGE_LABELS):
        raise ValueError("el perfil de triaje debe contener los niveles 1 a 5")
    if reference_volume not in volume.index:
        raise ValueError(
            f"reference_volume debe ser uno de {sorted(volume.index)}"
        )

    daily_visits = float(volume.loc[reference_volume, "daily_visits"]) * demand_multiplier
    hourly_share = _normalized(hourly["share"])
    return {
        "arrival_rates": tuple(daily_visits * share for share in hourly_share),
        "triage_probabilities": _normalized(triage["share"]),
        "daily_visits": daily_visits,
        "reference_volume": reference_volume,
    }


def load_calibrated_config(
    processed_dir: Path | str,
    reference_volume: str = DEFAULT_REFERENCE_VOLUME,
    demand_multiplier: float = 1.0,
    **overrides: Any,
) -> SimulationConfig:
    """Build a ``SimulationConfig`` with NHAMCS-derived arrivals and triage.

    Service medians, capacity and horizon keep their default (assumed) values
    unless overridden explicitly.
    """

    inputs = calibrated_inputs(processed_dir, reference_volume, demand_multiplier)
    return default_config(
        arrival_rates=inputs["arrival_rates"],
        triage_probabilities=inputs["triage_probabilities"],
        **overrides,
    )
