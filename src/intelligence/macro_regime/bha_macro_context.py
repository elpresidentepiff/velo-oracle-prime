"""
BHA Macro Context — Phase B
Provides structural racing context from the BHA Data Pack (2012-2024).

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
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "bha_macro_features.parquet"

# ─── Data class ────────────────────────────────────────────────────────────────

@dataclass
class MacroContext:
    """Structural macro context for a given year + race_code."""

    year: int
    race_code: str  # 'flat', 'jump', 'aw'

    # Raw structural metrics
    avg_field_size: Optional[float] = None
    fixtures_scheduled: Optional[int] = None
    fixtures_ran: Optional[int] = None
    fixtures_abandoned: Optional[int] = None
    fav_compress_pct: Optional[float] = None  # % SP favs at even money or shorter
    total_starts: Optional[int] = None
    individual_runners: Optional[int] = None
    avg_runs_per_horse: Optional[float] = None

    # Derived macro indices (normalised vs long-run mean, excl COVID)
    competitiveness_index: Optional[float] = None        # overall (flat+jump avg)
    competitiveness_index_code: Optional[float] = None  # code-specific
    fixture_strain_index: Optional[float] = None        # ran/scheduled
    abandonment_stress_index: Optional[float] = None    # abandoned/scheduled, [0,1]
    favourite_compression_index: Optional[float] = None # fav_compress / long-run mean
    run_density_index: Optional[float] = None           # avg_runs / long-run mean

    # Categorical regime
    field_size_regime: str = "unknown"  # tight / below_normal / normal / above_normal / deep

    # Flags
    covid_year: bool = False
    ambiguity_flag: bool = False
    macro_available: bool = True  # False when served from fallback (no real parquet)

    # Derived classifications (set by classify())
    chaos_mode: bool = False
    low_field_warning: bool = False
    favourite_trap_risk: str = "normal"  # low / normal / elevated / high
    regime_label: str = "normal"

    def classify(self) -> "MacroContext":
        """Compute derived classification flags from raw indices."""

        # Chaos mode: COVID truncated season (fixture_strain_index < 0.72 indicates
        # structural season collapse, not just weather abandonments).
        # Standard weather abandon years (2018-2019, 2023) are NOT chaos — they are
        # normal variation. Only use this flag for regime-level season disruption.
        structural_collapse = (
            self.fixture_strain_index is not None and
            self.fixture_strain_index < 0.72
        )
        self.chaos_mode = bool(self.covid_year or structural_collapse)

        # Low-field warning: competitiveness below -1 SD proxy (<0.94)
        self.low_field_warning = bool(
            self.competitiveness_index_code is not None and
            self.competitiveness_index_code < 0.94
        )

        # Favourite trap risk:
        # High compression (lots of short-priced favs) = higher risk of punters over-betting top
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

        # Regime label
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
        """Return a flat dict of macro features for appending to a race-level row."""
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
        }


# ─── Loader (cached) ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_macro_df() -> pd.DataFrame:
    if not _DATA_PATH.exists():
        # Parquet absent — return a single-row DataFrame of neutral/normal values.
        # get_macro_context() will find this row and return a MacroContext classified
        # as regime_label="normal", preventing macro_ctx=None downstream.
        logger.warning(
            "BHA macro features parquet not found at %s. "
            "Using fallback neutral regime — regime corrections are DISABLED. "
            "Run: python scripts/cache_bha_macro_features.py to restore.",
            _DATA_PATH,
        )
        return pd.DataFrame({
            "year": [2024],
            "race_code": ["flat"],
            "avg_field_size": [10.0],
            "fixtures_scheduled": [1000],
            "fixtures_ran": [950],
            "fixtures_abandoned": [50],
            "fav_compress_pct": [0.35],
            "total_starts": [10000],
            "individual_runners": [5000],
            "avg_runs_per_horse": [2.0],
            "competitiveness_index": [1.0],
            "competitiveness_index_code": [1.0],
            "fixture_strain_index": [0.95],
            "abandonment_stress_index": [0.05],
            "favourite_compression_index": [1.0],
            "run_density_index": [1.0],
            "field_size_regime": ["normal"],
            "covid_year": [False],
            "ambiguity_flag": [False],
            "macro_available": [False],
        })
    return pd.read_parquet(_DATA_PATH)


# ─── Public API ────────────────────────────────────────────────────────────────

_VALID_CODES = {"flat", "jump", "aw"}

def get_macro_context(year: int, race_code: str) -> MacroContext:
    """
    Look up structural macro context for a given year and race_code.

    Args:
        year:      Calendar year (2012-2024). Outside range → nearest boundary + warning.
        race_code: 'flat', 'jump', or 'aw'. Unrecognised → defaults to 'flat' + warning.

    Returns:
        MacroContext with all indices populated and classify() already called.
    """
    code = race_code.lower().strip()
    if code not in _VALID_CODES:
        warnings.warn(f"Unknown race_code '{race_code}' — defaulting to 'flat'", stacklevel=2)
        code = "flat"

    df = _load_macro_df()

    # Clamp year to available range
    min_yr, max_yr = int(df["year"].min()), int(df["year"].max())
    clamped = max(min_yr, min(max_yr, year))
    if clamped != year:
        warnings.warn(
            f"Year {year} outside BHA data range ({min_yr}-{max_yr}) — using {clamped}",
            stacklevel=2,
        )

    row = df[(df["year"] == clamped) & (df["race_code"] == code)]

    if row.empty:
        warnings.warn(f"No macro data found for year={clamped}, code={code}", stacklevel=2)
        return MacroContext(year=year, race_code=code).classify()

    r = row.iloc[0]

    def _v(col):
        val = r.get(col)
        if val is None:
            return None
        try:
            import math
            return None if math.isnan(float(val)) else float(val)
        except (TypeError, ValueError):
            return val

    ctx = MacroContext(
        year=int(clamped),
        race_code=code,
        avg_field_size=_v("avg_field_size"),
        fixtures_scheduled=_v("fixtures_scheduled"),
        fixtures_ran=_v("fixtures_ran"),
        fixtures_abandoned=_v("fixtures_abandoned"),
        fav_compress_pct=_v("fav_compress_pct"),
        total_starts=_v("total_starts"),
        individual_runners=_v("individual_runners"),
        avg_runs_per_horse=_v("avg_runs_per_horse"),
        competitiveness_index=_v("competitiveness_index"),
        competitiveness_index_code=_v("competitiveness_index_code"),
        fixture_strain_index=_v("fixture_strain_index"),
        abandonment_stress_index=_v("abandonment_stress_index"),
        favourite_compression_index=_v("favourite_compression_index"),
        run_density_index=_v("run_density_index"),
        field_size_regime=str(r.get("field_size_regime", "unknown")),
        covid_year=bool(r.get("covid_year", 0)),
        ambiguity_flag=bool(r.get("ambiguity_flag", 0)),
        macro_available=bool(r.get("macro_available", True)),
    )

    return ctx.classify()


def get_macro_context_for_race(date_str: str, race_code: str) -> MacroContext:
    """
    Convenience wrapper: accepts a date string (YYYY-MM-DD or YYYY) and race_code.
    Extracts the year automatically.
    """
    try:
        year = int(str(date_str)[:4])
    except (ValueError, TypeError):
        warnings.warn(f"Cannot parse year from '{date_str}' — using 2024", stacklevel=2)
        year = 2024
    return get_macro_context(year=year, race_code=race_code)


# ─── Quick self-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for yr, code in [(2019, "flat"), (2020, "jump"), (2022, "aw"), (2024, "flat")]:
        ctx = get_macro_context(yr, code)
        d = ctx.to_feature_dict()
        print(f"\n{yr} {code}:")
        print(f"  field_size={ctx.avg_field_size}  ci_code={ctx.competitiveness_index_code}")
        print(f"  fav_trap={ctx.favourite_trap_risk}  regime={ctx.regime_label}  chaos={ctx.chaos_mode}")
        print(f"  feature_dict keys: {list(d.keys())}")
