"""
BHA Macro Context - Phase B
Provides structural racing context from the BHA Data Pack (2012-2024),
with explicit 2025 proxy support when the parquet has not yet been extended.

Usage at inference time:
    from src.intelligence.macro_regime.bha_macro_context import get_macro_context
    ctx = get_macro_context(year=2024, race_code="flat")

This module is STRUCTURAL CONTEXT only. Per D004 (decisions.md):
  BHA stats are NOT runner-level features.
  They inform regime classification, confidence calibration,
  favourite trap logic, and chaos mode. Joined at race/year/code level.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "bha_macro_features.parquet"
BASE_CONTEXT_VERSION = "BHA_MACRO_2012_2024_V1"
PROXY_CONTEXT_VERSION_2025 = "2025_PROXY_V1"
PROXY_SOURCE_2025 = "2024_baseline_extended"
_VALID_CODES = {"flat", "jump", "aw"}


@dataclass
class MacroContext:
    """Structural macro context for a given year + race_code."""

    year: int
    race_code: str  # "flat", "jump", "aw"

    # Raw structural metrics
    avg_field_size: Optional[float] = None
    fixtures_scheduled: Optional[int] = None
    fixtures_ran: Optional[int] = None
    fixtures_abandoned: Optional[int] = None
    fav_compress_pct: Optional[float] = None
    total_starts: Optional[int] = None
    individual_runners: Optional[int] = None
    avg_runs_per_horse: Optional[float] = None

    # Derived macro indices
    competitiveness_index: Optional[float] = None
    competitiveness_index_code: Optional[float] = None
    fixture_strain_index: Optional[float] = None
    abandonment_stress_index: Optional[float] = None
    favourite_compression_index: Optional[float] = None
    run_density_index: Optional[float] = None

    # Categorical regime
    field_size_regime: str = "unknown"

    # Flags / provenance
    covid_year: bool = False
    ambiguity_flag: bool = False
    macro_available: bool = True
    macro_context_version: str = BASE_CONTEXT_VERSION
    macro_year_source: str = "race_date"
    macro_year_fallback: bool = False
    macro_proxy_source: Optional[str] = None
    macro_proxy_approved: Optional[bool] = None

    # Derived classifications
    chaos_mode: bool = False
    low_field_warning: bool = False
    favourite_trap_risk: str = "normal"
    regime_label: str = "normal"

    def classify(self) -> "MacroContext":
        structural_collapse = (
            self.fixture_strain_index is not None
            and self.fixture_strain_index < 0.72
        )
        self.chaos_mode = bool(self.covid_year or structural_collapse)

        self.low_field_warning = bool(
            self.competitiveness_index_code is not None
            and self.competitiveness_index_code < 0.94
        )

        if self.favourite_compression_index is None:
            self.favourite_trap_risk = "unknown"
        elif self.favourite_compression_index > 1.20:
            self.favourite_trap_risk = "high"
        elif self.favourite_compression_index > 1.08:
            self.favourite_trap_risk = "elevated"
        elif self.favourite_compression_index < 0.85:
            self.favourite_trap_risk = "low"
        else:
            self.favourite_trap_risk = "normal"

        if self.chaos_mode:
            self.regime_label = "chaos"
        elif self.low_field_warning:
            self.regime_label = "thin_market"
        elif self.favourite_trap_risk in ("elevated", "high"):
            self.regime_label = "compressed_market"
        else:
            self.regime_label = "normal"

        return self

    def to_feature_dict(self) -> dict:
        return {
            "macro_competitiveness_index": self.competitiveness_index,
            "macro_competitiveness_index_code": self.competitiveness_index_code,
            "macro_fixture_strain_index": self.fixture_strain_index,
            "macro_abandonment_stress_index": self.abandonment_stress_index,
            "macro_favourite_compression_index": self.favourite_compression_index,
            "macro_run_density_index": self.run_density_index,
            "macro_avg_field_size": self.avg_field_size,
            "macro_covid_year": int(self.covid_year),
            "macro_chaos_mode": int(self.chaos_mode),
            "macro_low_field_warning": int(self.low_field_warning),
            "macro_field_size_regime": self.field_size_regime,
            "macro_favourite_trap_risk": self.favourite_trap_risk,
            "macro_regime_label": self.regime_label,
            "macro_context_version": self.macro_context_version,
            "macro_year_used": self.year,
            "macro_year_source": self.macro_year_source,
            "macro_year_fallback": self.macro_year_fallback,
            "macro_proxy_source": self.macro_proxy_source,
            "macro_proxy_approved": self.macro_proxy_approved,
        }


@lru_cache(maxsize=1)
def _load_macro_df() -> pd.DataFrame:
    if not _DATA_PATH.exists():
        logger.warning(
            "BHA macro features parquet not found at %s. "
            "Using fallback neutral regime - regime corrections are DISABLED.",
            _DATA_PATH,
        )
        return pd.DataFrame(
            {
                "year": [2024, 2024, 2024],
                "race_code": ["flat", "jump", "aw"],
                "avg_field_size": [10.0, 10.0, 10.0],
                "fixtures_scheduled": [1000, 1000, 1000],
                "fixtures_ran": [950, 950, 950],
                "fixtures_abandoned": [50, 50, 50],
                "fav_compress_pct": [0.35, 0.35, 0.35],
                "total_starts": [10000, 10000, 10000],
                "individual_runners": [5000, 5000, 5000],
                "avg_runs_per_horse": [2.0, 2.0, 2.0],
                "competitiveness_index": [1.0, 1.0, 1.0],
                "competitiveness_index_code": [1.0, 1.0, 1.0],
                "fixture_strain_index": [0.95, 0.95, 0.95],
                "abandonment_stress_index": [0.05, 0.05, 0.05],
                "favourite_compression_index": [1.0, 1.0, 1.0],
                "run_density_index": [1.0, 1.0, 1.0],
                "field_size_regime": ["normal", "normal", "normal"],
                "covid_year": [False, False, False],
                "ambiguity_flag": [False, False, False],
                "macro_available": [False, False, False],
            }
        )
    return pd.read_parquet(_DATA_PATH)


def _value(row_obj, column: str):
    value = row_obj.get(column)
    if value is None:
        return None
    try:
        import math

        return None if math.isnan(float(value)) else float(value)
    except (TypeError, ValueError):
        return value


def _context_from_row(
    row_obj,
    *,
    effective_year: int,
    race_code: str,
    macro_context_version: str,
    macro_year_fallback: bool,
    macro_proxy_source: Optional[str] = None,
    macro_proxy_approved: Optional[bool] = None,
) -> MacroContext:
    return MacroContext(
        year=int(effective_year),
        race_code=race_code,
        avg_field_size=_value(row_obj, "avg_field_size"),
        fixtures_scheduled=_value(row_obj, "fixtures_scheduled"),
        fixtures_ran=_value(row_obj, "fixtures_ran"),
        fixtures_abandoned=_value(row_obj, "fixtures_abandoned"),
        fav_compress_pct=_value(row_obj, "fav_compress_pct"),
        total_starts=_value(row_obj, "total_starts"),
        individual_runners=_value(row_obj, "individual_runners"),
        avg_runs_per_horse=_value(row_obj, "avg_runs_per_horse"),
        competitiveness_index=_value(row_obj, "competitiveness_index"),
        competitiveness_index_code=_value(row_obj, "competitiveness_index_code"),
        fixture_strain_index=_value(row_obj, "fixture_strain_index"),
        abandonment_stress_index=_value(row_obj, "abandonment_stress_index"),
        favourite_compression_index=_value(row_obj, "favourite_compression_index"),
        run_density_index=_value(row_obj, "run_density_index"),
        field_size_regime=str(row_obj.get("field_size_regime", "unknown")),
        covid_year=bool(row_obj.get("covid_year", 0)),
        ambiguity_flag=bool(row_obj.get("ambiguity_flag", 0)),
        macro_available=bool(row_obj.get("macro_available", True)),
        macro_context_version=macro_context_version,
        macro_year_source="race_date",
        macro_year_fallback=macro_year_fallback,
        macro_proxy_source=macro_proxy_source,
        macro_proxy_approved=macro_proxy_approved,
    ).classify()


def get_macro_context(year: int, race_code: str) -> MacroContext:
    """
    Look up structural macro context for a given year and race_code.

    2025 is handled as an explicit proxy regime sourced from the 2024 baseline.
    Other out-of-range years retain the original clamped-boundary behavior.
    """
    code = str(race_code or "").lower().strip()
    if code not in _VALID_CODES:
        warnings.warn(f"Unknown race_code '{race_code}' - defaulting to 'flat'", stacklevel=2)
        code = "flat"

    df = _load_macro_df()
    min_year = int(df["year"].min())
    max_year = int(df["year"].max())

    if year == max_year + 1:
        proxy_row = df[(df["year"] == max_year) & (df["race_code"] == code)]
        if proxy_row.empty:
            warnings.warn(
                f"No proxy macro data found for year={year}, code={code}; returning empty proxy context",
                stacklevel=2,
            )
            return MacroContext(
                year=year,
                race_code=code,
                macro_context_version=PROXY_CONTEXT_VERSION_2025,
                macro_year_source="race_date",
                macro_year_fallback=False,
                macro_proxy_source=PROXY_SOURCE_2025,
                macro_proxy_approved=True,
            ).classify()
        warnings.warn(
            f"Year {year} outside BHA data range ({min_year}-{max_year}) - "
            f"using explicit {PROXY_CONTEXT_VERSION_2025} from {PROXY_SOURCE_2025}",
            stacklevel=2,
        )
        return _context_from_row(
            proxy_row.iloc[0],
            effective_year=year,
            race_code=code,
            macro_context_version=PROXY_CONTEXT_VERSION_2025,
            macro_year_fallback=False,
            macro_proxy_source=PROXY_SOURCE_2025,
            macro_proxy_approved=True,
        )

    clamped_year = max(min_year, min(max_year, year))
    if clamped_year != year:
        warnings.warn(
            f"Year {year} outside BHA data range ({min_year}-{max_year}) - using {clamped_year}",
            stacklevel=2,
        )

    row = df[(df["year"] == clamped_year) & (df["race_code"] == code)]
    if row.empty:
        warnings.warn(f"No macro data found for year={clamped_year}, code={code}", stacklevel=2)
        return MacroContext(year=year, race_code=code).classify()

    return _context_from_row(
        row.iloc[0],
        effective_year=clamped_year,
        race_code=code,
        macro_context_version=BASE_CONTEXT_VERSION,
        macro_year_fallback=False,
    )


def get_macro_context_for_race(date_str: str, race_code: str) -> MacroContext:
    """Convenience wrapper: accepts a date string and extracts the year automatically."""
    try:
        year = int(str(date_str)[:4])
    except (ValueError, TypeError):
        warnings.warn(f"Cannot parse year from '{date_str}' - using 2024", stacklevel=2)
        year = 2024
    return get_macro_context(year=year, race_code=race_code)


if __name__ == "__main__":
    for year_value, code_value in [(2019, "flat"), (2020, "jump"), (2022, "aw"), (2024, "flat"), (2025, "flat")]:
        ctx = get_macro_context(year_value, code_value)
        feature_dict = ctx.to_feature_dict()
        print(f"\n{year_value} {code_value}:")
        print(f"  field_size={ctx.avg_field_size} ci_code={ctx.competitiveness_index_code}")
        print(f"  fav_trap={ctx.favourite_trap_risk} regime={ctx.regime_label} chaos={ctx.chaos_mode}")
        print(f"  macro_context_version={ctx.macro_context_version} proxy_source={ctx.macro_proxy_source}")
        print(f"  feature_dict keys: {list(feature_dict.keys())}")
