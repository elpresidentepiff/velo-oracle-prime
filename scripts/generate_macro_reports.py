"""
Phase D Reports: Structural Trend Report + Macro Volatility Report + Doctrine Linkage Report
Reads from data/bha_macro_features.parquet and data/bha_industry_stats.json
Outputs: reports/ directory
"""
import json
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

df = pd.read_parquet(DATA / "bha_macro_features.parquet")
with open(DATA / "bha_industry_stats.json", encoding="utf-8") as f:
    bha = json.load(f)

# ─── 1. Structural Trend Report ────────────────────────────────────────────────

def structural_trend_report():
    lines = [
        "=" * 70,
        "VELO STRUCTURAL TREND REPORT — BHA Data Pack 2012-2024",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 70,
        "",
        "1. FIELD SIZE TRENDS (flat turf, jump, all-weather)",
        "-" * 50,
    ]

    flat_rows  = df[df["race_code"] == "flat"][["year", "avg_field_size", "competitiveness_index_code"]].dropna()
    jump_rows  = df[df["race_code"] == "jump"][["year", "avg_field_size", "competitiveness_index_code"]].dropna()
    aw_rows    = df[df["race_code"] == "aw"][["year", "avg_field_size", "competitiveness_index_code"]].dropna()

    lines.append(f"{'Year':<6} {'Flat':>6} {'Jump':>6} {'AW':>6} {'CI_flat':>8} {'CI_jump':>8}")
    lines.append("-" * 46)
    for y in range(2012, 2025):
        fr = flat_rows[flat_rows["year"] == y]
        jr = jump_rows[jump_rows["year"] == y]
        ar = aw_rows[aw_rows["year"] == y]
        f_fs  = f"{fr['avg_field_size'].values[0]:>6.2f}"  if len(fr) else "   n/a"
        j_fs  = f"{jr['avg_field_size'].values[0]:>6.2f}"  if len(jr) else "   n/a"
        a_fs  = f"{ar['avg_field_size'].values[0]:>6.2f}"  if len(ar) else "   n/a"
        f_ci  = f"{fr['competitiveness_index_code'].values[0]:>8.4f}" if len(fr) else "    n/a "
        j_ci  = f"{jr['competitiveness_index_code'].values[0]:>8.4f}" if len(jr) else "    n/a "
        covid = " [COVID]" if y == 2020 else ""
        lines.append(f"{y:<6} {f_fs} {j_fs} {a_fs} {f_ci} {j_ci}{covid}")

    # Long-run means
    non_covid = df[df["covid_year"] == 0]
    f_mean = non_covid[non_covid["race_code"] == "flat"]["avg_field_size"].mean()
    j_mean = non_covid[non_covid["race_code"] == "jump"]["avg_field_size"].mean()
    a_mean = non_covid[non_covid["race_code"] == "aw"]["avg_field_size"].mean()
    lines += ["", f"Long-run means (excl COVID): flat={f_mean:.2f}  jump={j_mean:.2f}  aw={a_mean:.2f}"]

    # Trend: 2022 was worst for jump (7.73 — field collapse)
    j_min = non_covid[non_covid["race_code"] == "jump"]["avg_field_size"].min()
    j_min_yr = non_covid[non_covid["race_code"] == "jump"].loc[
        non_covid[non_covid["race_code"] == "jump"]["avg_field_size"].idxmin(), "year"
    ]
    lines.append(f"Jump field size nadir: {j_min:.2f} in {int(j_min_yr)} — structural concern for jump betting")

    lines += [
        "",
        "2. FAVOURITE COMPRESSION INDEX (% SP favs at even money or shorter)",
        "-" * 50,
    ]

    fav_df = df[df["race_code"] == "flat"][["year", "fav_compress_pct", "favourite_compression_index"]].dropna()
    lines.append(f"{'Year':<6} {'Odds-on/evs %':>14} {'Compression Index':>18} {'Regime Signal'}")
    lines.append("-" * 55)
    for _, row in fav_df.iterrows():
        y = int(row["year"])
        pct = row["fav_compress_pct"]
        ci  = row["favourite_compression_index"]
        signal = "HIGH TRAP RISK" if ci > 1.20 else ("ELEVATED" if ci > 1.08 else ("LOW TRAP" if ci < 0.85 else "normal"))
        covid = " [COVID]" if y == 2020 else ""
        lines.append(f"{y:<6} {pct:>14.1f} {ci:>18.4f} {signal}{covid}")

    lines += [
        "",
        "3. ABANDONMENT STRESS",
        "-" * 50,
    ]

    aband_data = bha["abandonments"]["data"]
    sched_data = {r["year"]: r["total"] for r in bha["fixtures_scheduled"]["data"]}
    lines.append(f"{'Year':<6} {'Abandoned':>10} {'Scheduled':>10} {'Rate %':>8} {'Stress Idx':>11}")
    lines.append("-" * 48)
    for r in aband_data:
        y = r["year"]
        tot = r.get("total")
        s = sched_data.get(y)
        rate = round(tot/s*100, 2) if tot and s else None
        stress = df[(df["year"] == y) & (df["race_code"] == "flat")]["abandonment_stress_index"]
        si = f"{stress.values[0]:>11.4f}" if len(stress) > 0 and not pd.isna(stress.values[0]) else "        n/a"
        af = " [AMBIGUOUS]" if r.get("ambiguity_flag") else ""
        lines.append(f"{y:<6} {str(tot):>10} {str(s):>10} {str(rate):>8} {si}{af}")

    lines += ["", "Worst year: 2019/2023 (~6.0% rate) — not structural chaos, normal weather variation"]

    lines += [
        "",
        "4. REGIME SUMMARY BY YEAR",
        "-" * 50,
    ]
    flat_df = df[df["race_code"] == "flat"].sort_values("year")
    lines.append(f"{'Year':<6} {'CI':>6} {'FavTrap':>10} {'AbStress':>10} {'Regime'}")
    lines.append("-" * 50)
    for _, row in flat_df.iterrows():
        from src.intelligence.macro_regime.bha_macro_context import get_macro_context
        ctx = get_macro_context(int(row["year"]), "flat")
        ci = f"{ctx.competitiveness_index_code:.4f}" if ctx.competitiveness_index_code else "  n/a"
        lines.append(f"{int(row['year']):<6} {ci:>6} {ctx.favourite_trap_risk:>10} "
                     f"{str(round(ctx.abandonment_stress_index, 3) if ctx.abandonment_stress_index else 'n/a'):>10} "
                     f"{ctx.regime_label}")

    return "\n".join(lines)


# ─── 2. Macro Volatility Report ─────────────────────────────────────────────────

def macro_volatility_report():
    lines = [
        "=" * 70,
        "VELO MACRO VOLATILITY REPORT",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 70,
        "",
        "Volatility = standard deviation of each index across non-COVID years.",
        "High volatility = index is noisy year-to-year. Low = stable baseline.",
        "",
    ]

    non_covid = df[df["covid_year"] == 0]
    flat_nc = non_covid[non_covid["race_code"] == "flat"]
    jump_nc = non_covid[non_covid["race_code"] == "jump"]

    metrics = [
        ("competitiveness_index_code (flat)", flat_nc["competitiveness_index_code"]),
        ("competitiveness_index_code (jump)", jump_nc["competitiveness_index_code"]),
        ("favourite_compression_index", flat_nc["favourite_compression_index"]),
        ("abandonment_stress_index", flat_nc["abandonment_stress_index"].dropna()),
        ("fixture_strain_index", flat_nc["fixture_strain_index"].dropna()),
        ("run_density_index", flat_nc["run_density_index"].dropna()),
    ]

    lines.append(f"{'Metric':<40} {'Mean':>8} {'Std':>8} {'CV%':>8} {'Stability'}")
    lines.append("-" * 72)
    for name, s in metrics:
        s = s.dropna()
        if len(s) == 0:
            continue
        mean = s.mean()
        std  = s.std()
        cv   = (std / mean * 100) if mean != 0 else 0
        stability = "STABLE" if cv < 4 else ("MODERATE" if cv < 8 else "VOLATILE")
        lines.append(f"{name:<40} {mean:>8.4f} {std:>8.4f} {cv:>7.1f}% {stability}")

    lines += ["", "Key finding: favourite_compression_index has highest volatility — market efficiency varies year-to-year."]
    return "\n".join(lines)


# ─── 3. Doctrine Linkage Report ─────────────────────────────────────────────────

def doctrine_linkage_report():
    lines = [
        "=" * 70,
        "VELO DOCTRINE LINKAGE REPORT",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 70,
        "",
        "How macro indices connect to VELO_PRIME_prob and betting doctrine:",
        "",
        "INDEX                        -> DOCTRINE APPLICATION",
        "-" * 70,
        "competitiveness_index_code   -> Low CI: thin market, increase uncertainty band",
        "                               High CI: competitive race, standard confidence",
        "favourite_compression_index  -> >1.20: HIGH fav trap — penalise favourite prob by 5pp",
        "                               >1.08: ELEVATED — flag, reduce fav confidence",
        "                               <0.85: LOW — market spreading bets, less compression",
        "abandonment_stress_index     -> >0.95: near-chaos season (structural disruption risk)",
        "                               Note: 2024 data ambiguous (PDF column misalignment)",
        "fixture_strain_index         -> <0.72: chaos_mode=True (season not running normally)",
        "                               Normal range: 0.94-0.98",
        "run_density_index            -> Low: fewer runs per horse, less form data reliability",
        "                               High: form signals more reliable (more data per horse)",
        "covid_year                   -> Always chaos_mode=True for 2020",
        "",
        "REGIME LABELS:",
        "  chaos         — COVID or structural season collapse. Flatten all probabilities 80%.",
        "  compressed_market — fav trap elevated/high. Apply penalty to favourites.",
        "  thin_market   — low field sizes. Spread uncertainty by 10%.",
        "  normal        — baseline regime. No macro adjustments.",
        "",
        "CURRENT YEAR (2024) ASSESSMENT:",
    ]

    from src.intelligence.macro_regime.bha_macro_context import get_macro_context
    for code in ["flat", "jump", "aw"]:
        ctx = get_macro_context(2024, code)
        lines.append(f"  2024 {code:4}: regime={ctx.regime_label:<18} "
                     f"fav_trap={ctx.favourite_trap_risk:<10} "
                     f"ci={ctx.competitiveness_index_code or 'n/a'}")
    lines += [
        "",
        "  Note: 2024 abandonment data ambiguous (source PDF column misalignment).",
        "  abandonment_stress_index for 2024 = NaN. Regime classification uses other indices.",
    ]
    return "\n".join(lines)


# ─── Run all reports ──────────────────────────────────────────────────────────

sys.path.insert(0, str(ROOT))

for name, fn in [
    ("structural_trend_report.txt", structural_trend_report),
    ("macro_volatility_report.txt", macro_volatility_report),
    ("doctrine_linkage_report.txt", doctrine_linkage_report),
]:
    content = fn()
    path = REPORTS / name
    path.write_text(content, encoding="utf-8")
    print(f"Written: reports/{name}")
    print()
    print(content[:600])
    print("...")
    print()
