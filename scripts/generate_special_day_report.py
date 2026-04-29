"""
VÉLØ Special Day Report Generator

Usage:
    python scripts/generate_special_day_report.py --date 2026-04-28

Outputs:
    docs/evidence/special_days/VELO_SPECIAL_DAY_YYYY-MM-DD.md
    data/evidence_vault/special_days/velo_special_day_YYYY-MM-DD.json

Rules: No model changes. No router changes. No staking. Documentation only.
"""

import argparse
import json
import os
import re
import sys
import glob
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

STRIKE_BASELINE = 0.20
FRAME_BASELINE = 0.70
RUN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# Candidate lane thresholds (mirrors design_velo_candidate_lanes.py)
LANE_CONDITIONS = [
    {
        "lane_id": "MARKET_DECEPTION_HIGH",
        "badge": "🔥 MDS_HIGH",
        "tier": "elite",
        "evidence": "n=31 | SR 54.8% | Frame 96.8%",
    },
    {
        "lane_id": "VP30_TIER_A",
        "badge": "✅ VP30_TIER_A",
        "tier": "proven",
        "evidence": "n=162 | SR 40.1% | Frame 77.2%",
    },
    {
        "lane_id": "IMPROVEMENT_SCORE_HIGH",
        "badge": "📈 IMPROVE_HIGH",
        "tier": "proven",
        "evidence": "n=62 | SR 43.5% | Frame 82.3%",
    },
    {
        "lane_id": "PLACE_PROB_HIGH",
        "badge": "🟡 PLACE_HIGH",
        "tier": "watchlist",
        "evidence": "n=392 | SR 31.6% | Frame 66.8%",
    },
    {
        "lane_id": "B_TIER_LOW_VP_SUPPRESS",
        "badge": "⚠️ B_LOW_VP",
        "tier": "suppress",
        "evidence": "n=272 | SR 16.9% | Frame 44.1%",
    },
]


def get_sb():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def load_sigma_for_date(sb, date: str) -> pd.DataFrame:
    r = sb.table("sigma_audits").select(
        "id,race_id,verdict_id,date,track,off_time,outcome,miss_reason,"
        "confidence_level,decision_tier,actual_winner_sp,actual_winner_name"
    ).eq("date", date).execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        return df
    df["actual_winner_sp"] = pd.to_numeric(df["actual_winner_sp"], errors="coerce")
    return df


def load_verdicts_for_date(sb, date: str) -> pd.DataFrame:
    """Load velo_verdicts for races on a given date via generated_at filter."""
    r = sb.table("velo_verdicts").select(
        "id,race_id,velo_prime_prob,decision_tier,confidence_level_effective,"
        "race_archetype,improvement_score,market_deception_score,place_prob,"
        "rpdc_release_score,g_shadow_multiplier,g_shadow_mode,generated_at"
    ).gte("generated_at", f"{date}T00:00:00").lt("generated_at", f"{date}T23:59:59").execute()
    df = pd.DataFrame(r.data)
    if df.empty:
        # Fallback: try verdict JSON file
        return pd.DataFrame()
    for col in ["velo_prime_prob", "improvement_score", "market_deception_score",
                "place_prob", "rpdc_release_score", "g_shadow_multiplier"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_verdict_json_for_date(date: str) -> pd.DataFrame:
    date_str = date.replace("-", "_")
    paths = glob.glob(str(ROOT / "data" / f"velo_prime_verdicts_{date_str}.json"))
    if not paths:
        return pd.DataFrame()
    with open(paths[0]) as f:
        verdicts = json.load(f)
    rows = []
    for v in verdicts:
        top = v.get("top") or {}
        rows.append({
            "verdict_race_id": v.get("race_id"),
            "course": v.get("course"),
            "off_time": v.get("off_time"),
            "tier_json": v.get("tier"),
            "vp_json": top.get("velo_prime_prob"),
            "conf_json": top.get("confidence_level"),
            "horse_json": top.get("horse"),
            "archetype_json": v.get("race_archetype"),
            "mds_json": top.get("market_deception_score"),
            "improvement_score_json": top.get("improvement_score"),
            "place_prob_json": top.get("place_prob"),
            "g_shadow_mode_json": top.get("g_shadow_mode", False),
            "cash_run_flag_json": top.get("cash_run_flag", False),
        })
    df = pd.DataFrame(rows)
    for col in ["vp_json", "mds_json", "improvement_score_json", "place_prob_json"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_learned_patterns_for_date(sb, date: str) -> pd.DataFrame:
    r = sb.table("learned_patterns").select("*").gte(
        "created_at", f"{date}T00:00:00"
    ).lt("created_at", f"{date}T23:59:59").execute()
    return pd.DataFrame(r.data)


def load_router_ledger() -> pd.DataFrame:
    p = ROOT / "data" / "router_shadow_audit_ledger.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def pct(n, d, decimals=1):
    return 0.0 if d == 0 else round(n / d * 100, decimals)


def band_stats(df, label, vp_col="vp"):
    n = len(df)
    wins = (df["outcome"] == "WIN").sum()
    placed = df["outcome"].isin(["WIN", "PLACED"]).sum()
    return {
        "label": label, "n": int(n), "wins": int(wins), "placed": int(placed),
        "strike_rate": pct(wins, n), "frame_rate": pct(placed, n),
        "avg_vp": round(float(df[vp_col].mean()), 3) if vp_col in df and n > 0 and df[vp_col].notna().any() else None,
    }


def compare_to_global(sr: float, fr: float) -> str:
    if sr > STRIKE_BASELINE * 100 + 3:
        sr_word = "ABOVE"
    elif sr < STRIKE_BASELINE * 100 - 3:
        sr_word = "BELOW"
    else:
        sr_word = "AT"
    if fr >= FRAME_BASELINE * 100:
        fr_word = "AT OR ABOVE"
    else:
        fr_word = "BELOW"
    return f"SR {sr_word} baseline ({STRIKE_BASELINE*100:.0f}%) | Frame {fr_word} target ({FRAME_BASELINE*100:.0f}%)"


def generate_report(date: str) -> dict:
    print(f"Generating Special Day Report for {date}...")
    sb = get_sb()

    sigma = load_sigma_for_date(sb, date)
    if sigma.empty:
        print(f"  No sigma_audit rows found for {date}. Cannot generate report.")
        sys.exit(1)

    vj = load_verdict_json_for_date(date)
    patterns = load_learned_patterns_for_date(sb, date)
    ledger = load_router_ledger()

    print(f"  Sigma rows: {len(sigma)} | JSON verdicts: {len(vj)} | Patterns: {len(patterns)}")

    # Merge VP from JSON where available
    merged = sigma.copy()
    merged["vp"] = np.nan
    if not vj.empty:
        def norm(c):
            return re.sub(r"\s+", " ", str(c or "").lower().strip().split("(")[0].strip())
        vj["course_norm"] = vj["course"].apply(norm)
        merged["track_norm"] = merged["track"].apply(norm)
        lookup = vj.set_index(["course_norm", "off_time"])
        for idx, row in merged.iterrows():
            key = (row["track_norm"], row["off_time"])
            if key in lookup.index:
                v = lookup.loc[key]
                if isinstance(v, pd.DataFrame):
                    v = v.iloc[0]
                merged.at[idx, "vp"] = v.get("vp_json")

    non_x = merged[merged["decision_tier"] != "X"].copy()
    x_rows = merged[merged["decision_tier"] == "X"]

    n = len(non_x)
    wins = (non_x["outcome"] == "WIN").sum()
    placed = non_x["outcome"].isin(["WIN", "PLACED"]).sum()
    misses = (non_x["outcome"] == "MISS").sum()
    sr = pct(wins, n)
    fr = pct(placed, n)

    # VP bands
    vp_bands = []
    for lo, hi, label in [
        (0.0, 0.20, "VP<0.20"), (0.20, 0.30, "VP 0.20-0.30"),
        (0.30, 0.40, "VP 0.30-0.40"), (0.40, 1.01, "VP>=0.40"),
    ]:
        sub = non_x[(non_x["vp"] >= lo) & (non_x["vp"] < hi)]
        if len(sub) > 0:
            vp_bands.append(band_stats(sub, label))
    vp_30 = band_stats(non_x[non_x["vp"] >= 0.30], "VP>=0.30")
    vp_30_a = band_stats(non_x[(non_x["vp"] >= 0.30) & (non_x["decision_tier"] == "A")],
                         "VP>=0.30 + Tier A")

    # Tier stats
    tier_stats = {}
    for tier in ["A", "B", "C", "D", "X"]:
        sub = merged[merged["decision_tier"] == tier]
        if len(sub) > 0:
            tier_stats[tier] = band_stats(sub, f"Tier {tier}")

    # Sidecar highlights from JSON
    sidecar_highlights = []
    if not vj.empty:
        mds_high = vj[vj["mds_json"] > 0.5]
        imp_high = vj[vj["improvement_score_json"] > 0.40]
        pp_high = vj[vj["place_prob_json"] > 0.80]
        if len(mds_high) > 0:
            sidecar_highlights.append(f"MDS>0.5: {len(mds_high)} races fired")
        if len(imp_high) > 0:
            sidecar_highlights.append(f"Improvement>0.40: {len(imp_high)} races fired")
        if len(pp_high) > 0:
            sidecar_highlights.append(f"Place prob>0.80: {len(pp_high)} races fired")

    # Miss classes
    miss_rows = non_x[non_x["outcome"] == "MISS"]
    miss_classes = miss_rows["miss_reason"].value_counts().to_dict() if len(miss_rows) > 0 else {}
    mid_price_misses = miss_rows[
        (miss_rows["actual_winner_sp"] >= 3.0) & (miss_rows["actual_winner_sp"] <= 8.5)
    ]
    short_fav_misses = miss_rows[miss_rows["actual_winner_sp"] < 3.0]

    # Course notes
    course_results = {}
    for track, g in non_x.groupby("track"):
        w = (g["outcome"] == "WIN").sum()
        f = g["outcome"].isin(["WIN", "PLACED"]).sum()
        course_results[track] = {"n": len(g), "wins": int(w), "frame": int(f),
                                 "sr": pct(w, len(g)), "fr": pct(f, len(g))}

    # Router ledger state
    router_state = {}
    if not ledger.empty:
        for lane in ledger["lane"].unique():
            latest = ledger[ledger["lane"] == lane].iloc[-1]
            router_state[lane] = {
                "n": int(latest.get("n", 0)),
                "roi": float(latest.get("roi", 0)),
                "status": latest.get("status", "?"),
            }

    # Determine day contribution to router
    router_contribution = "NEUTRAL — no qualifying results added to innovation protocol from this date"

    # Pattern summary
    pattern_summary = []
    if not patterns.empty:
        for _, p in patterns.iterrows():
            desc = p.get("description", "") or ""
            pattern_summary.append(desc[:80])

    # Audit conclusion
    if sr > STRIKE_BASELINE * 100 + 5:
        conclusion_sr = "SR above baseline — strong day for winner conversion."
    elif sr < STRIKE_BASELINE * 100 - 5:
        conclusion_sr = "SR below baseline — weak winner conversion day."
    else:
        conclusion_sr = "SR at baseline — normal day for winner conversion."

    if fr >= 70:
        conclusion_fr = f"Frame rate {fr}% meets target — contender detection working."
    elif fr >= 55:
        conclusion_fr = f"Frame rate {fr}% below 70% target — partial contender detection."
    else:
        conclusion_fr = f"Frame rate {fr}% well below target — weak contender day."

    mid_pct = pct(len(mid_price_misses), len(miss_rows)) if len(miss_rows) > 0 else 0
    conclusion_miss = f"Primary miss class: mid-priced winners ({mid_pct}% of misses in SP 3–8.5 zone)."

    audit_conclusion = f"{conclusion_sr} {conclusion_fr} {conclusion_miss}"

    # Research tags
    research_tags = []
    if len(mid_price_misses) >= 3:
        research_tags.append("MID_PRICE_WINNER_MISS_CLASS")
    if vp_30.get("frame_rate", 0) >= 75:
        research_tags.append("VP30_FRAME_STRENGTH")
    if vp_30.get("strike_rate", 0) >= 30:
        research_tags.append("VP30_SR_STRONG")
    if tier_stats.get("A", {}).get("strike_rate", 0) >= 40:
        research_tags.append("TIER_A_STRONG")
    if tier_stats.get("B", {}).get("strike_rate", 0) < 15:
        research_tags.append("TIER_B_DRAG_CONFIRMED")
    if len(short_fav_misses) >= 2:
        research_tags.append("SHORT_FAV_OVERRIDE_NEEDED")

    # ── Signal attribution analysis ───────────────────────────────────────────
    # Evaluate candidate lane conditions against each race using verdict JSON data.
    # This shows which lanes would have fired and surfaces operator visibility gaps.

    race_attributions = []
    lane_day_counts = {lc["lane_id"]: {"fired": 0, "wins": 0, "frames": 0} for lc in LANE_CONDITIONS}
    lane_day_counts["MID_PRICE_WINNER_FORENSICS"] = {"fired": 0, "wins": 0, "frames": 0}

    if not vj.empty:
        vj_lookup = vj.set_index(["course_norm", "off_time"]) if "course_norm" in vj.columns else pd.DataFrame()

        for idx, row in merged.iterrows():
            if row["decision_tier"] == "X":
                continue
            key = (row.get("track_norm"), row.get("off_time"))
            vj_row = None
            if not vj_lookup.empty and key in vj_lookup.index:
                v = vj_lookup.loc[key]
                vj_row = v.iloc[0] if isinstance(v, pd.DataFrame) else v

            vp = row.get("vp") or (float(vj_row.get("vp_json", 0) or 0) if vj_row is not None else 0)
            tier = row.get("decision_tier", "")
            mds = float(vj_row.get("mds_json", 0) or 0) if vj_row is not None else 0
            improve = float(vj_row.get("improvement_score_json", 0) or 0) if vj_row is not None else 0
            place_p = float(vj_row.get("place_prob_json", 0) or 0) if vj_row is not None else 0
            outcome = row.get("outcome", "")
            winner_sp = row.get("actual_winner_sp")
            won = outcome == "WIN"
            framed = outcome in ("WIN", "PLACED")

            fired_lanes = []

            if mds > 0.50:
                fired_lanes.append("MARKET_DECEPTION_HIGH")
                lane_day_counts["MARKET_DECEPTION_HIGH"]["fired"] += 1
                if won:
                    lane_day_counts["MARKET_DECEPTION_HIGH"]["wins"] += 1
                if framed:
                    lane_day_counts["MARKET_DECEPTION_HIGH"]["frames"] += 1

            if vp >= 0.30 and tier == "A":
                fired_lanes.append("VP30_TIER_A")
                lane_day_counts["VP30_TIER_A"]["fired"] += 1
                if won:
                    lane_day_counts["VP30_TIER_A"]["wins"] += 1
                if framed:
                    lane_day_counts["VP30_TIER_A"]["frames"] += 1

            if improve > 0.40:
                fired_lanes.append("IMPROVEMENT_SCORE_HIGH")
                lane_day_counts["IMPROVEMENT_SCORE_HIGH"]["fired"] += 1
                if won:
                    lane_day_counts["IMPROVEMENT_SCORE_HIGH"]["wins"] += 1
                if framed:
                    lane_day_counts["IMPROVEMENT_SCORE_HIGH"]["frames"] += 1

            if place_p > 0.80:
                fired_lanes.append("PLACE_PROB_HIGH")
                lane_day_counts["PLACE_PROB_HIGH"]["fired"] += 1
                if won:
                    lane_day_counts["PLACE_PROB_HIGH"]["wins"] += 1
                if framed:
                    lane_day_counts["PLACE_PROB_HIGH"]["frames"] += 1

            if tier == "B" and vp < 0.30:
                fired_lanes.append("B_TIER_LOW_VP_SUPPRESS")
                lane_day_counts["B_TIER_LOW_VP_SUPPRESS"]["fired"] += 1
                if won:
                    lane_day_counts["B_TIER_LOW_VP_SUPPRESS"]["wins"] += 1
                if framed:
                    lane_day_counts["B_TIER_LOW_VP_SUPPRESS"]["frames"] += 1

            if outcome == "MISS" and winner_sp is not None and 3.0 <= float(winner_sp) <= 8.5:
                fired_lanes.append("MID_PRICE_WINNER_FORENSICS")
                lane_day_counts["MID_PRICE_WINNER_FORENSICS"]["fired"] += 1

            if fired_lanes:
                race_attributions.append({
                    "race_id": row.get("race_id"),
                    "track": row.get("track"),
                    "off_time": row.get("off_time"),
                    "outcome": outcome,
                    "vp": round(float(vp), 3) if vp else None,
                    "tier": tier,
                    "mds": round(mds, 3) if mds else None,
                    "improve": round(improve, 3) if improve else None,
                    "place_prob": round(place_p, 3) if place_p else None,
                    "winner_sp": float(winner_sp) if winner_sp is not None else None,
                    "lanes_fired": fired_lanes,
                    "elite_lanes": [l for l in fired_lanes if l in ("MARKET_DECEPTION_HIGH", "VP30_TIER_A", "IMPROVEMENT_SCORE_HIGH")],
                    "suppress_warning": "B_TIER_LOW_VP_SUPPRESS" in fired_lanes,
                })

    # Strongest signal of the day
    strongest_signal = None
    if lane_day_counts["MARKET_DECEPTION_HIGH"]["fired"] > 0:
        c = lane_day_counts["MARKET_DECEPTION_HIGH"]
        sr_d = pct(c["wins"], c["fired"])
        strongest_signal = {
            "lane_id": "MARKET_DECEPTION_HIGH",
            "fired": c["fired"],
            "wins": c["wins"],
            "frames": c["frames"],
            "day_sr": sr_d,
            "day_frame": pct(c["frames"], c["fired"]),
            "note": "Elite signal. Historical SR=54.8% at n=31.",
        }
    elif lane_day_counts["IMPROVEMENT_SCORE_HIGH"]["fired"] > 0:
        c = lane_day_counts["IMPROVEMENT_SCORE_HIGH"]
        strongest_signal = {
            "lane_id": "IMPROVEMENT_SCORE_HIGH",
            "fired": c["fired"],
            "wins": c["wins"],
            "frames": c["frames"],
            "day_sr": pct(c["wins"], c["fired"]),
            "day_frame": pct(c["frames"], c["fired"]),
            "note": "Proven signal. Historical SR=43.5% at n=62.",
        }
    elif lane_day_counts["VP30_TIER_A"]["fired"] > 0:
        c = lane_day_counts["VP30_TIER_A"]
        strongest_signal = {
            "lane_id": "VP30_TIER_A",
            "fired": c["fired"],
            "wins": c["wins"],
            "frames": c["frames"],
            "day_sr": pct(c["wins"], c["fired"]),
            "day_frame": pct(c["frames"], c["fired"]),
            "note": "Proven primary gate. Historical SR=40.1% at n=162.",
        }

    # Operator visibility gaps
    visibility_gaps = []
    elite_races_invisible = [
        r for r in race_attributions if r["elite_lanes"]
    ]
    if elite_races_invisible:
        visibility_gaps.append({
            "gap": "ELITE_SIGNAL_NOT_SURFACED",
            "count": len(elite_races_invisible),
            "description": (
                f"{len(elite_races_invisible)} races fired elite candidate lane signals "
                "(MDS_HIGH / VP30_TIER_A / IMPROVE_HIGH) that were not visible in the "
                "standard Telegram output."
            ),
            "fix": "Add VÉLØ SIGNAL STACK panel to Telegram output (see design doc).",
        })
    suppress_invisible = [r for r in race_attributions if r["suppress_warning"]]
    if suppress_invisible:
        visibility_gaps.append({
            "gap": "SUPPRESS_WARNING_NOT_SURFACED",
            "count": len(suppress_invisible),
            "description": (
                f"{len(suppress_invisible)} races were in the Tier B VP<0.30 suppress zone "
                "but no warning appeared in Telegram output."
            ),
            "fix": "Add suppress warnings to VÉLØ SIGNAL STACK panel.",
        })

    # Elite day flag
    elite_signals_today = (
        lane_day_counts["MARKET_DECEPTION_HIGH"]["fired"] > 0 or
        lane_day_counts["VP30_TIER_A"]["fired"] >= 2 or
        lane_day_counts["IMPROVEMENT_SCORE_HIGH"]["fired"] >= 2
    )
    elite_day_flag = {
        "is_elite_day": elite_signals_today,
        "reason": (
            "MDS_HIGH fired" if lane_day_counts["MARKET_DECEPTION_HIGH"]["fired"] > 0
            else f"VP30_TIER_A fired {lane_day_counts['VP30_TIER_A']['fired']}x" if elite_signals_today
            else "No elite signal threshold met today"
        ),
        "dashboard_watch_recommended": elite_signals_today,
        "dashboard_watch_reason": (
            "Elite signal fired today — add to daily dashboard accumulation tracker."
            if elite_signals_today
            else "Standard day — no dashboard promotion recommended."
        ),
    }

    result = {
        "date": date,
        "generated_at": RUN_TS,
        "A_date": date,
        "B_total_verdicts": len(merged),
        "C_matched_outcomes": n,
        "D_excluded_x_tier": int(len(x_rows)),
        "E_strike_rate": sr,
        "F_frame_rate": fr,
        "G_baseline_comparison": compare_to_global(sr, fr),
        "H_vp_band_performance": vp_bands,
        "I_tier_performance": tier_stats,
        "J_vp30_performance": vp_30,
        "K_vp30_tier_a_performance": vp_30_a,
        "L_sidecar_highlights": sidecar_highlights,
        "M_miss_class_breakdown": {k: int(v) for k, v in miss_classes.items()},
        "N_mid_price_misses": {
            "count": int(len(mid_price_misses)),
            "pct_of_misses": mid_pct,
            "winner_sps": sorted(mid_price_misses["actual_winner_sp"].dropna().round(2).tolist()),
        },
        "O_short_fav_misses": {
            "count": int(len(short_fav_misses)),
            "winner_sps": sorted(short_fav_misses["actual_winner_sp"].dropna().round(2).tolist()),
        },
        "P_course_notes": course_results,
        "Q_learned_patterns": {
            "count": len(patterns),
            "patterns": pattern_summary,
        },
        "R_router_evidence": router_state,
        "S_router_contribution": router_contribution,
        "T_audit_conclusion": audit_conclusion,
        "U_research_tags": research_tags,
        "V_signal_attribution": {
            "race_attributions": race_attributions,
            "lane_day_counts": lane_day_counts,
            "strongest_signal": strongest_signal,
            "total_attribution_races": len(race_attributions),
        },
        "W_elite_day_flag": elite_day_flag,
        "X_operator_visibility_gaps": visibility_gaps,
        "Y_telegram_panel_needed": len(visibility_gaps) > 0,
    }
    return result


def write_markdown(result: dict, date: str) -> str:
    sr = result["E_strike_rate"]
    fr = result["F_frame_rate"]
    vp30 = result["J_vp30_performance"]
    vp30a = result["K_vp30_tier_a_performance"]

    lines = [
        f"# VÉLØ Special Day Report — {date}",
        "",
        f"**{vp30.get('frame_rate', 0):.1f}% VP≥0.30 frame | {sr}% overall SR | {fr}% overall frame**",
        "",
        f"*Generated: {result['generated_at']}*",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Value | Context |",
        f"|---|---|---|",
        f"| Total verdicts | {result['B_total_verdicts']} | — |",
        f"| Matched outcomes | {result['C_matched_outcomes']} | non-X tier |",
        f"| X-tier excluded | {result['D_excluded_x_tier']} | correct behaviour |",
        f"| Strike rate | **{sr}%** | baseline 20% |",
        f"| Frame rate | **{fr}%** | target 70% |",
        f"| Baseline | {result['G_baseline_comparison']} | — |",
        "",
        "---",
        "",
        "## VP Band Performance",
        "",
        "| Band | n | Wins | SR | Frame |",
        "|---|---|---|---|---|",
    ]
    for b in result["H_vp_band_performance"]:
        lines.append(f"| {b['label']} | {b['n']} | {b['wins']} | {b['strike_rate']}% | {b['frame_rate']}% |")
    lines += [
        f"| **VP≥0.30 combined** | **{vp30['n']}** | **{vp30['wins']}** | **{vp30['strike_rate']}%** | **{vp30['frame_rate']}%** |",
        f"| **VP≥0.30 + Tier A** | **{vp30a['n']}** | **{vp30a['wins']}** | **{vp30a['strike_rate']}%** | **{vp30a['frame_rate']}%** |",
        "",
        "---",
        "",
        "## Tier Performance",
        "",
        "| Tier | n | Wins | SR | Frame |",
        "|---|---|---|---|---|",
    ]
    for tier_label, t in result["I_tier_performance"].items():
        lines.append(f"| {t['label']} | {t['n']} | {t['wins']} | {t['strike_rate']}% | {t['frame_rate']}% |")
    lines += [
        "",
        "---",
        "",
        "## Sidecar Highlights",
        "",
    ]
    if result["L_sidecar_highlights"]:
        for s in result["L_sidecar_highlights"]:
            lines.append(f"- {s}")
    else:
        lines.append("No notable sidecar signals today.")
    lines += [
        "",
        "---",
        "",
        "## Miss Class Breakdown",
        "",
        "| Miss Class | Count |",
        "|---|---|",
    ]
    for k, v in sorted(result["M_miss_class_breakdown"].items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} |")
    mid = result["N_mid_price_misses"]
    short = result["O_short_fav_misses"]
    lines += [
        "",
        f"**Mid-price misses (SP 3.0–8.5):** {mid['count']} ({mid['pct_of_misses']}% of all misses)",
        f"Winner SPs: {mid['winner_sps']}",
        "",
        f"**Short-favourite misses (SP <3.0):** {short['count']}",
        f"Winner SPs: {short['winner_sps']}",
        "",
        "---",
        "",
        "## Course Notes",
        "",
        "| Course | n | Wins | SR | Frame |",
        "|---|---|---|---|---|",
    ]
    for course, c in sorted(result["P_course_notes"].items(), key=lambda x: -x[1]["n"]):
        lines.append(f"| {course} | {c['n']} | {c['wins']} | {c['sr']}% | {c['fr']}% |")
    lines += [
        "",
        "---",
        "",
        "## Learned Patterns",
        "",
        f"Patterns saved: {result['Q_learned_patterns']['count']}",
        "",
    ]
    for p in result["Q_learned_patterns"]["patterns"][:10]:
        lines.append(f"- {p}")
    lines += [
        "",
        "---",
        "",
        "## Router Evidence Contribution",
        "",
    ]
    if result["R_router_evidence"]:
        lines += ["| Lane | n | ROI | Status |", "|---|---|---|---|"]
        for lane, lr in result["R_router_evidence"].items():
            lines.append(f"| {lane} | {lr['n']} | {lr['roi']:+.1f}% | {lr['status']} |")
    lines += [
        "",
        f"**Day contribution:** {result['S_router_contribution']}",
        "",
        "---",
        "",
        "## Audit Conclusion",
        "",
        result["T_audit_conclusion"],
        "",
        "---",
        "",
        "## Research Tags",
        "",
    ]
    for tag in result["U_research_tags"]:
        lines.append(f"- `{tag}`")
    # Signal Attribution
    attr = result.get("V_signal_attribution", {})
    elite_flag = result.get("W_elite_day_flag", {})
    vis_gaps = result.get("X_operator_visibility_gaps", [])
    lane_counts = attr.get("lane_day_counts", {})
    strongest = attr.get("strongest_signal")

    lines += [
        "",
        "---",
        "",
        "## Signal Attribution Analysis",
        "",
        "Candidate lane conditions evaluated against today's races.",
        "Shadow evidence only — no execution decisions.",
        "",
        "### Lane Firing Summary",
        "",
        "| Lane | Fired | Wins | Frames | Day SR | Day Frame |",
        "|---|---|---|---|---|---|",
    ]
    lane_display = [
        ("MARKET_DECEPTION_HIGH", "🔥 MDS_HIGH"),
        ("VP30_TIER_A", "✅ VP30_TIER_A"),
        ("IMPROVEMENT_SCORE_HIGH", "📈 IMPROVE_HIGH"),
        ("PLACE_PROB_HIGH", "🟡 PLACE_HIGH"),
        ("B_TIER_LOW_VP_SUPPRESS", "⚠️ B_LOW_VP"),
        ("MID_PRICE_WINNER_FORENSICS", "🔬 MID_PRICE_FORENSICS"),
    ]
    for lid, display in lane_display:
        c = lane_counts.get(lid, {})
        n_ = c.get("fired", 0)
        w_ = c.get("wins", 0)
        f_ = c.get("frames", 0)
        sr_ = f"{pct(w_, n_):.0f}%" if n_ > 0 else "—"
        fr_ = f"{pct(f_, n_):.0f}%" if n_ > 0 else "—"
        lines.append(f"| {display} | {n_} | {w_} | {f_} | {sr_} | {fr_} |")

    if strongest:
        lines += [
            "",
            f"**Strongest signal today:** {strongest['lane_id']} — fired {strongest['fired']}x, "
            f"day SR {strongest['day_sr']}%, {strongest['note']}",
        ]
    else:
        lines += ["", "No elite signals fired today."]

    # Race-level attributions (top 10 only for readability)
    race_attrs = attr.get("race_attributions", [])
    if race_attrs:
        lines += [
            "",
            "### Race-Level Attribution (signal races only)",
            "",
            "| Time | Course | Outcome | VP | Tier | Lanes Fired |",
            "|---|---|---|---|---|---|",
        ]
        for r in sorted(race_attrs, key=lambda x: x.get("off_time", ""))[:15]:
            badges = " ".join(r.get("lanes_fired", []))
            lines.append(
                f"| {r.get('off_time','?')} | {r.get('track','?')} | {r.get('outcome','?')} "
                f"| {r.get('vp','?')} | {r.get('tier','?')} | {badges} |"
            )
        if len(race_attrs) > 15:
            lines.append(f"*... +{len(race_attrs)-15} more races in JSON*")

    # Elite day flag
    lines += [
        "",
        "---",
        "",
        "## Elite Day Flag",
        "",
        f"**Elite day:** {'✅ YES' if elite_flag.get('is_elite_day') else '❌ No'}",
        f"**Reason:** {elite_flag.get('reason', '—')}",
        f"**Dashboard watch recommended:** {'✅ YES' if elite_flag.get('dashboard_watch_recommended') else 'No'}",
        f"**Note:** {elite_flag.get('dashboard_watch_reason', '—')}",
    ]

    # Operator visibility gaps
    lines += [
        "",
        "---",
        "",
        "## Operator Visibility Gaps",
        "",
    ]
    if vis_gaps:
        for g in vis_gaps:
            lines += [
                f"**{g['gap']}** ({g['count']} races)",
                "",
                f"*{g['description']}*",
                "",
                f"Fix: {g['fix']}",
                "",
            ]
        lines.append("> **Telegram Signal Attribution Panel required.** See `docs/evidence/VELO_TELEGRAM_SIGNAL_ATTRIBUTION_PANEL_V1.md`")
    else:
        lines.append("No operator visibility gaps identified today.")

    lines += [
        "",
        "---",
        f"*VÉLØ Special Day Report — {date} | {result['generated_at']}*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    date = args.date

    result = generate_report(date)

    # Write JSON
    json_path = ROOT / "data" / "evidence_vault" / "special_days" / f"velo_special_day_{date}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Write Markdown
    md_content = write_markdown(result, date)
    md_path = ROOT / "docs" / "evidence" / "special_days" / f"VELO_SPECIAL_DAY_{date}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(md_path, "w") as f:
        f.write(md_content)

    print(f"\nOutputs:")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    print(f"\nSR={result['E_strike_rate']}% | Frame={result['F_frame_rate']}%")
    print(f"VP≥0.30: SR={result['J_vp30_performance']['strike_rate']}% Frame={result['J_vp30_performance']['frame_rate']}%")
    print(f"Tags: {result['U_research_tags']}")


if __name__ == "__main__":
    main()
