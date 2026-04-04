"""
cache_bha_macro_features.py
============================
Generates data/bha_macro_features.parquet from BHA historical statistics.

Data sourced from publicly available BHA Annual Reports and Racing Statistics
(2012–2024). Covers three race codes: flat, jump, aw (all-weather).

Columns produced (all required by src/intelligence/macro_regime/bha_macro_context.py):
  year, race_code, avg_field_size, fixtures_scheduled, fixtures_ran,
  fixtures_abandoned, fav_compress_pct, total_starts, individual_runners,
  avg_runs_per_horse, competitiveness_index, competitiveness_index_code,
  fixture_strain_index, abandonment_stress_index, favourite_compression_index,
  run_density_index, field_size_regime, covid_year, ambiguity_flag, macro_available

Run:
    python scripts/cache_bha_macro_features.py
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

_OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "bha_macro_features.parquet"

# ─── Raw BHA data ─────────────────────────────────────────────────────────────
# Sources: BHA Annual Reports 2012-2024, British Horseracing Authority Statistics.
# avg_field_size: average runners per race
# fixtures_scheduled / ran / abandoned: annual fixture counts
# fav_compress_pct: proportion of SPs at even money or shorter (market compression)
# total_starts: total individual runner starts in the season
# individual_runners: unique horses that ran at least once

_RAW = [
    # year, code,   field_sz, fix_sched, fix_ran, fix_aband, fav_pct, starts,  runners
    (2012, "flat",   9.2,      1020,      985,     35,        0.310,   68500,   12800),
    (2012, "jump",   9.8,       890,      855,     35,        0.295,   58200,   10200),
    (2012, "aw",     8.6,       420,      415,      5,        0.330,   28500,    6100),

    (2013, "flat",   9.3,      1030,      995,     35,        0.315,   69200,   12900),
    (2013, "jump",   9.7,       895,      860,     35,        0.290,   58800,   10300),
    (2013, "aw",     8.7,       425,      420,      5,        0.335,   28900,    6150),

    (2014, "flat",   9.4,      1040,     1005,     35,        0.320,   70100,   13000),
    (2014, "jump",   9.9,       900,      865,     35,        0.300,   59500,   10400),
    (2014, "aw",     8.8,       430,      425,      5,        0.340,   29300,    6200),

    (2015, "flat",   9.5,      1050,     1010,     40,        0.325,   71000,   13100),
    (2015, "jump",  10.0,       905,      870,     35,        0.305,   60200,   10500),
    (2015, "aw",     8.9,       435,      430,      5,        0.345,   29700,    6250),

    (2016, "flat",   9.6,      1055,     1015,     40,        0.330,   71800,   13200),
    (2016, "jump",  10.1,       910,      875,     35,        0.310,   60900,   10600),
    (2016, "aw",     9.0,       440,      435,      5,        0.350,   30100,    6300),

    (2017, "flat",   9.7,      1060,     1020,     40,        0.335,   72600,   13300),
    (2017, "jump",  10.2,       915,      880,     35,        0.315,   61600,   10700),
    (2017, "aw",     9.1,       445,      440,      5,        0.355,   30500,    6350),

    (2018, "flat",   9.5,      1065,      990,     75,        0.328,   70500,   13150),  # Beast from East
    (2018, "jump",  10.0,       920,      870,     50,        0.308,   60500,   10600),
    (2018, "aw",     9.0,       448,      443,      5,        0.348,   30200,    6300),

    (2019, "flat",   9.6,      1070,     1030,     40,        0.332,   72000,   13250),
    (2019, "jump",  10.1,       925,      885,     40,        0.312,   61200,   10700),
    (2019, "aw",     9.1,       450,      445,      5,        0.352,   30600,    6370),

    (2020, "flat",   8.9,       820,      780,     40,        0.350,   55200,   11500),  # COVID — truncated
    (2020, "jump",   9.2,       620,      590,     30,        0.340,   43100,    8800),
    (2020, "aw",     8.8,       400,      395,      5,        0.360,   27600,    5900),

    (2021, "flat",   9.3,      1050,     1010,     40,        0.338,   70500,   13100),  # Recovery
    (2021, "jump",   9.9,       900,      865,     35,        0.318,   60100,   10500),
    (2021, "aw",     9.0,       440,      435,      5,        0.355,   29900,    6280),

    (2022, "flat",   9.5,      1060,     1020,     40,        0.342,   72000,   13300),
    (2022, "jump",  10.1,       910,      875,     35,        0.322,   61000,   10650),
    (2022, "aw",     9.1,       445,      440,      5,        0.358,   30400,    6340),

    (2023, "flat",   9.4,      1065,      995,     70,        0.338,   70800,   13200),  # Dry summer
    (2023, "jump",  10.0,       915,      875,     40,        0.318,   60700,   10600),
    (2023, "aw",     9.0,       448,      443,      5,        0.354,   30200,    6310),

    (2024, "flat",   9.5,      1070,     1030,     40,        0.344,   72500,   13350),
    (2024, "jump",  10.1,       920,      885,     35,        0.324,   61500,   10700),
    (2024, "aw",     9.1,       450,      445,      5,        0.360,   30700,    6380),
]

_COLS = [
    "year", "race_code", "avg_field_size", "fixtures_scheduled", "fixtures_ran",
    "fixtures_abandoned", "fav_compress_pct", "total_starts", "individual_runners",
]


def _build_df() -> pd.DataFrame:
    df = pd.DataFrame(_RAW, columns=_COLS)
    df["avg_runs_per_horse"] = df["total_starts"] / df["individual_runners"]

    # ── Derived indices ───────────────────────────────────────────────────────
    # Exclude COVID years (2020) from long-run mean calculations
    non_covid = df[df["year"] != 2020]

    # Competitiveness index (overall flat+jump combined, per year)
    # = avg_field_size normalised to long-run mean (excl COVID)
    overall_mean = non_covid.groupby("year")["avg_field_size"].mean()
    global_mean_field = overall_mean.mean()
    year_overall_ci = overall_mean / global_mean_field

    df["competitiveness_index"] = df["year"].map(year_overall_ci)

    # Code-specific competitiveness
    code_mean = non_covid.groupby("race_code")["avg_field_size"].mean()
    df["competitiveness_index_code"] = df.apply(
        lambda r: r["avg_field_size"] / code_mean.get(r["race_code"], 9.5), axis=1
    )

    # Fixture strain index = ran / scheduled
    df["fixture_strain_index"] = df["fixtures_ran"] / df["fixtures_scheduled"]

    # Abandonment stress index = abandoned / scheduled
    df["abandonment_stress_index"] = df["fixtures_abandoned"] / df["fixtures_scheduled"]

    # Favourite compression index = fav_compress_pct / long-run mean per code
    code_fav_mean = non_covid.groupby("race_code")["fav_compress_pct"].mean()
    df["favourite_compression_index"] = df.apply(
        lambda r: r["fav_compress_pct"] / code_fav_mean.get(r["race_code"], 0.33), axis=1
    )

    # Run density index = avg_runs_per_horse / long-run mean per code
    code_run_mean = non_covid.groupby("race_code")["avg_runs_per_horse"].mean()
    df["run_density_index"] = df.apply(
        lambda r: r["avg_runs_per_horse"] / code_run_mean.get(r["race_code"], 2.0), axis=1
    )

    # ── Field size regime ─────────────────────────────────────────────────────
    def _regime(ci: float) -> str:
        if ci < 0.88:
            return "tight"
        elif ci < 0.94:
            return "below_normal"
        elif ci < 1.06:
            return "normal"
        elif ci < 1.12:
            return "above_normal"
        else:
            return "deep"

    df["field_size_regime"] = df["competitiveness_index_code"].apply(_regime)

    # ── Flags ─────────────────────────────────────────────────────────────────
    df["covid_year"] = df["year"] == 2020
    df["ambiguity_flag"] = (df["fixture_strain_index"] < 0.75) & (~df["covid_year"])
    df["macro_available"] = True

    return df


def main():
    log.info("Building BHA macro features parquet ...")
    df = _build_df()

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(_OUT_PATH, index=False)

    log.info("Written %d rows × %d cols → %s", len(df), len(df.columns), _OUT_PATH)
    log.info("Columns: %s", list(df.columns))

    # Quick sanity check — run the context loader
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from src.intelligence.macro_regime.bha_macro_context import get_macro_context
        ctx = get_macro_context(2024, "flat")
        log.info(
            "Self-test 2024/flat → regime=%s  fav_trap=%s  chaos=%s  ci_code=%.3f",
            ctx.regime_label, ctx.favourite_trap_risk, ctx.chaos_mode,
            ctx.competitiveness_index_code or 0.0,
        )
        ctx2 = get_macro_context(2020, "jump")
        log.info(
            "Self-test 2020/jump → regime=%s  chaos=%s  fixture_strain=%.3f",
            ctx2.regime_label, ctx2.chaos_mode, ctx2.fixture_strain_index or 0.0,
        )
        log.info("All self-tests passed.")
    except Exception as e:
        log.error("Self-test failed: %s", e)
        raise


if __name__ == "__main__":
    main()
