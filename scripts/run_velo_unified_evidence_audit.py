"""
VÉLØ Unified Evidence Audit V1

Reconciles all evidence streams across the full live operating period:
  - sigma_audits (Supabase)
  - velo_verdicts (Supabase, VP + sidecar scores)
  - verdict JSON files (full per-race detail)
  - innovation protocol CSV (router lane data)
  - router shadow audit ledger
  - learned_patterns (Supabase)

Produces:
  data/velo_unified_evidence_audit_v1.json
  data/velo_unified_evidence_audit_v1.md
  data/velo_unified_evidence_audit_v1_metrics.csv

Rules: NO model changes. NO router changes. NO staking. Audit only.
"""

import json
import glob
import os
import sys
import re
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

# ─── Supabase ────────────────────────────────────────────────────────────────
def get_sb():
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def pull_sigma_audits(sb) -> pd.DataFrame:
    rows = []
    offset = 0
    while True:
        r = sb.table("sigma_audits").select(
            "id,race_id,verdict_id,date,track,off_time,outcome,miss_reason,"
            "confidence_level,decision_tier,actual_winner_sp,verdict_score,"
            "top_pick_position,actual_winner_name"
        ).range(offset, offset + 999).execute()
        rows.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000
    df = pd.DataFrame(rows)
    df["actual_winner_sp"] = pd.to_numeric(df["actual_winner_sp"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    # Exclude proof_run and tier rows we cannot classify
    df = df[df["decision_tier"] != "proof_run"]
    return df


def pull_velo_verdicts(sb) -> pd.DataFrame:
    rows = []
    offset = 0
    while True:
        r = sb.table("velo_verdicts").select(
            "id,race_id,velo_prime_prob,decision_tier,confidence_level_effective,"
            "race_archetype,archetype_suppression,macro_chaos_mode,"
            "assigned_product,execution_allowed,predicted_field_size,"
            "improvement_score,market_deception_score,place_prob,"
            "rpdc_release_score,rpdc_cash_window_flag,rpdc_tag_count,"
            "top_horse_readiness_state,top_horse_release_state,"
            "g_shadow_mode,g_shadow_multiplier,generated_at"
        ).range(offset, offset + 999).execute()
        rows.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000
    df = pd.DataFrame(rows)
    df["velo_prime_prob"] = pd.to_numeric(df["velo_prime_prob"], errors="coerce")
    df["improvement_score"] = pd.to_numeric(df["improvement_score"], errors="coerce")
    df["market_deception_score"] = pd.to_numeric(df["market_deception_score"], errors="coerce")
    df["place_prob"] = pd.to_numeric(df["place_prob"], errors="coerce")
    df["rpdc_release_score"] = pd.to_numeric(df["rpdc_release_score"], errors="coerce")
    df["g_shadow_multiplier"] = pd.to_numeric(df["g_shadow_multiplier"], errors="coerce")
    # date from generated_at
    df["generated_date"] = df["generated_at"].str[:10]
    return df


def pull_learned_patterns(sb) -> pd.DataFrame:
    r = sb.table("learned_patterns").select("*").execute()
    df = pd.DataFrame(r.data)
    if not df.empty:
        df["date"] = df["created_at"].str[:10]
    return df


# ─── Verdict JSON files ───────────────────────────────────────────────────────
def load_verdict_jsons() -> pd.DataFrame:
    """Load all daily verdict JSON files into a flat DataFrame."""
    rows = []
    for path in sorted(glob.glob(str(ROOT / "data" / "velo_prime_verdicts_*.json"))):
        # Extract date from filename
        m = re.search(r"(\d{4}_\d{2}_\d{2})", path)
        if not m:
            continue
        file_date = m.group(1).replace("_", "-")
        with open(path) as f:
            verdicts = json.load(f)
        for v in verdicts:
            top = v.get("top") or {}
            rows.append({
                "file_date": file_date,
                "verdict_race_id": v.get("race_id"),
                "course": v.get("course"),
                "off_time": v.get("off_time"),
                "tier_json": v.get("tier"),
                "vp_json": top.get("velo_prime_prob"),
                "conf_json": top.get("confidence_level"),
                "horse_json": top.get("horse"),
                "archetype_json": v.get("race_archetype"),
                "macro_chaos_json": top.get("macro_chaos_mode", False),
                "g_shadow_mode_json": top.get("g_shadow_mode", False),
                "g_shadow_multiplier_json": top.get("g_shadow_multiplier"),
                "cash_run_flag_json": top.get("cash_run_flag", False),
                "setup_run_flag_json": top.get("setup_run_flag", False),
                "place_prob_json": top.get("place_prob"),
                "mds_json": top.get("market_deception_score"),
                "improvement_score_json": top.get("improvement_score"),
                "release_day_prob_json": top.get("release_day_prob"),
            })
    df = pd.DataFrame(rows)
    df["vp_json"] = pd.to_numeric(df["vp_json"], errors="coerce")
    df["place_prob_json"] = pd.to_numeric(df["place_prob_json"], errors="coerce")
    df["mds_json"] = pd.to_numeric(df["mds_json"], errors="coerce")
    df["improvement_score_json"] = pd.to_numeric(df["improvement_score_json"], errors="coerce")
    df["release_day_prob_json"] = pd.to_numeric(df["release_day_prob_json"], errors="coerce")
    df["g_shadow_multiplier_json"] = pd.to_numeric(df["g_shadow_multiplier_json"], errors="coerce")
    return df


# ─── Router data ─────────────────────────────────────────────────────────────
def load_router_data() -> dict:
    ip_path = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
    ledger_path = ROOT / "data" / "router_shadow_audit_ledger.csv"
    latest_path = ROOT / "data" / "router_shadow_audit_latest.csv"
    ip_df = pd.read_csv(ip_path) if ip_path.exists() else pd.DataFrame()
    ledger_df = pd.read_csv(ledger_path) if ledger_path.exists() else pd.DataFrame()
    latest_df = pd.read_csv(latest_path) if latest_path.exists() else pd.DataFrame()
    return {"ip": ip_df, "ledger": ledger_df, "latest": latest_df}


# ─── Core metrics ─────────────────────────────────────────────────────────────
def pct(n, d, decimals=1):
    if d == 0:
        return 0.0
    return round(n / d * 100, decimals)


def band_stats(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    wins = (df["outcome"] == "WIN").sum()
    placed = df["outcome"].isin(["WIN", "PLACED"]).sum()
    misses = (df["outcome"] == "MISS").sum()
    win_sps = df[df["outcome"] == "WIN"]["actual_winner_sp"].dropna()
    miss_sps = df[df["outcome"] == "MISS"]["actual_winner_sp"].dropna()
    avg_vp = df["velo_prime_prob"].mean() if "velo_prime_prob" in df.columns else None
    return {
        "label": label,
        "n": int(n),
        "wins": int(wins),
        "placed": int(placed),
        "misses": int(misses),
        "strike_rate": pct(wins, n),
        "frame_rate": pct(placed, n),
        "avg_vp": round(float(avg_vp), 3) if avg_vp is not None and not np.isnan(avg_vp) else None,
        "avg_winner_sp": round(float(win_sps.mean()), 2) if len(win_sps) else None,
        "avg_miss_sp": round(float(miss_sps.mean()), 2) if len(miss_sps) else None,
        "miss_sp_dist": sorted(miss_sps.round(2).tolist()) if len(miss_sps) else [],
    }


def daily_stats(df: pd.DataFrame) -> list[dict]:
    days = []
    for date, g in df.groupby("date"):
        n = len(g)
        wins = (g["outcome"] == "WIN").sum()
        placed = g["outcome"].isin(["WIN", "PLACED"]).sum()
        sr = pct(wins, n)
        fr = pct(placed, n)
        if sr > STRIKE_BASELINE * 100 + 2:
            vs_baseline = "ABOVE"
        elif sr < STRIKE_BASELINE * 100 - 2:
            vs_baseline = "BELOW"
        else:
            vs_baseline = "AT"
        days.append({
            "date": date, "n": int(n), "wins": int(wins),
            "strike_rate": sr, "frame_rate": fr, "vs_baseline": vs_baseline,
        })
    return sorted(days, key=lambda x: x["date"])


def sidecar_analysis(merged: pd.DataFrame, signal_col: str, threshold=None,
                     label: str = "") -> dict:
    """Measure lift of a sidecar signal over the global baseline."""
    col_data = merged[signal_col].dropna() if signal_col in merged.columns else pd.Series()
    if len(col_data) == 0:
        return {"label": label, "verdict": "BROKEN_OR_UNWIRED", "n": 0}
    if threshold is not None:
        active = merged[merged[signal_col] >= threshold]
    else:
        # Boolean field
        try:
            active = merged[merged[signal_col].astype(bool)]
        except Exception:
            active = merged[merged[signal_col] == True]
    inactive = merged[~merged.index.isin(active.index)]
    n_active = len(active)
    if n_active < 5:
        return {"label": label, "verdict": "INSUFFICIENT_SAMPLE", "n": n_active}
    global_sr = pct((merged["outcome"] == "WIN").sum(), len(merged))
    active_sr = pct((active["outcome"] == "WIN").sum(), n_active)
    active_fr = pct(active["outcome"].isin(["WIN", "PLACED"]).sum(), n_active)
    lift_sr = round(active_sr - global_sr, 1)
    return {
        "label": label,
        "n": n_active,
        "strike_rate": active_sr,
        "frame_rate": active_fr,
        "global_baseline_sr": global_sr,
        "lift_sr": lift_sr,
        "verdict": "KEEP" if lift_sr > 3 else ("WATCHLIST" if lift_sr > 0 else "SUPPRESS"),
    }


# ─── Modification timeline ───────────────────────────────────────────────────
MODIFICATION_TIMELINE = [
    {
        "date": "2026-03-16",
        "commit": "phase-d-velo-prime-ensemble",
        "feature": "VeloPrimeEnsemble — SQPE v17 + 7 specialists",
        "description": "Core ensemble rebuilt. velo_prime_prob introduced.",
    },
    {
        "date": "2026-03-26",
        "commit": "spotlight-layer",
        "feature": "Spotlight NLP layer + horse_comments flags",
        "description": "NLP flags from Racing Post horse comments ingested.",
    },
    {
        "date": "2026-03-28",
        "commit": "playbook-g-v2",
        "feature": "Playbook G v2 — shadow tracking + doctrine features",
        "description": "Sentient loop upgraded. g_shadow_mode introduced.",
    },
    {
        "date": "2026-04-10",
        "commit": "archetype-layer",
        "feature": "Race archetype classification",
        "description": "Structure / Compression / Chaos archetype routing.",
    },
    {
        "date": "2026-04-16",
        "commit": "rpdc-layer",
        "feature": "RPDC evidence layer — trainer/headgear/class tags",
        "description": "180-day truth query results. MARK_READY, suppressor/amplifier tags.",
    },
    {
        "date": "2026-04-27",
        "commit": "67820ae",
        "feature": "Execution Router v1 — SP gate tightened to 2–4s",
        "description": "candidate_route() SP gate changed from ≤7.0 to 2.0–4.0.",
    },
    {
        "date": "2026-04-28",
        "commit": "06ba74b",
        "feature": "Router Evidence Engine hardened",
        "description": "Immutable snapshots + append ledger + lane state tracking.",
    },
]


# ─── Signal ranking ───────────────────────────────────────────────────────────
def rank_signal(sr: float, fr: float, n: int, baseline_sr: float,
                min_n: int = 30) -> str:
    if n < 10:
        return "INSUFFICIENT_SAMPLE"
    if n < min_n:
        if sr > baseline_sr * 100 + 5 and fr > FRAME_BASELINE * 100 - 5:
            return "WATCHLIST_SIGNAL"
        return "INSUFFICIENT_SAMPLE"
    lift = sr - baseline_sr * 100
    if lift > 8 and fr > FRAME_BASELINE * 100 and n >= 50:
        return "PROVEN_SIGNAL"
    if lift > 5 and fr > FRAME_BASELINE * 100 - 5:
        return "PROMISING_SIGNAL"
    if lift > 2:
        return "WATCHLIST_SIGNAL"
    if lift > -2:
        return "NOISY_SIGNAL"
    return "SUPPRESS_SIGNAL"


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("VÉLØ Unified Evidence Audit V1")
    print(f"Run: {RUN_TS}")
    print("=" * 60)

    sb = get_sb()

    print("\n[1/7] Loading sigma_audits...")
    sigma = pull_sigma_audits(sb)
    print(f"  sigma rows: {len(sigma)} | dates: {sigma['date'].nunique()}")

    print("[2/7] Loading velo_verdicts...")
    verdicts = pull_velo_verdicts(sb)
    print(f"  verdict rows: {len(verdicts)}")

    print("[3/7] Loading verdict JSON files...")
    vj = load_verdict_jsons()
    print(f"  JSON verdict rows: {len(vj)} | dates: {vj['file_date'].nunique()}")

    print("[4/7] Loading router data...")
    router = load_router_data()
    ip = router["ip"]
    ledger = router["ledger"]
    print(f"  IP rows: {len(ip)} | ledger rows: {len(ledger)}")

    print("[5/7] Loading learned patterns...")
    lp = pull_learned_patterns(sb)
    print(f"  learned patterns: {len(lp)}")

    print("[6/7] Joining sigma → verdicts...")
    # Join sigma_audits to velo_verdicts via race_id (best available join)
    # velo_verdicts may have multiple rows per race_id; take the latest generated
    vv_deduped = (
        verdicts.sort_values("generated_at", ascending=False)
        .drop_duplicates(subset="race_id", keep="first")
    )
    merged = sigma.merge(
        vv_deduped[[
            "race_id", "velo_prime_prob", "confidence_level_effective",
            "race_archetype", "archetype_suppression", "macro_chaos_mode",
            "improvement_score", "market_deception_score", "place_prob",
            "rpdc_release_score", "rpdc_cash_window_flag", "rpdc_tag_count",
            "g_shadow_mode", "g_shadow_multiplier", "assigned_product",
        ]],
        on="race_id",
        how="left",
    )
    # Also join JSON verdict data for fields not in Supabase
    # Normalise course name for join
    def norm_course(c):
        return re.sub(r"\s+", " ", str(c or "").lower().strip().split("(")[0].strip())

    vj["course_norm"] = vj["course"].apply(norm_course)
    merged["track_norm"] = merged["track"].apply(norm_course)

    # Try to add VP from JSON where Supabase VP is missing
    vj_lookup = vj.set_index(["file_date", "course_norm", "off_time"])[
        ["vp_json", "conf_json", "archetype_json", "cash_run_flag_json",
         "setup_run_flag_json", "place_prob_json", "mds_json",
         "improvement_score_json", "release_day_prob_json",
         "g_shadow_mode_json", "g_shadow_multiplier_json"]
    ].to_dict(orient="index")

    # Enrich rows where VP is missing
    for idx, row in merged[merged["velo_prime_prob"].isna()].iterrows():
        key = (row["date"], row["track_norm"], row["off_time"])
        if key in vj_lookup:
            merged.at[idx, "velo_prime_prob"] = vj_lookup[key]["vp_json"]
            if pd.isna(merged.at[idx, "confidence_level_effective"]):
                merged.at[idx, "confidence_level_effective"] = vj_lookup[key]["conf_json"]

    vp_coverage = merged["velo_prime_prob"].notna().sum()
    print(f"  Joined rows: {len(merged)} | VP coverage: {vp_coverage}/{len(merged)}")

    print("[7/7] Running analysis...\n")

    # ── A–K: Global stats ──────────────────────────────────────────────────────
    total_days = sigma["date"].nunique()
    total_verdicts_db = len(verdicts)
    total_matched = len(sigma)
    excluded = sigma[sigma["decision_tier"] == "X"]
    unmatched_note = "X-tier rows included in DB but excluded from SR/frame calculations"

    non_x = sigma[sigma["decision_tier"] != "X"]
    global_n = len(non_x)
    global_wins = (non_x["outcome"] == "WIN").sum()
    global_placed = non_x["outcome"].isin(["WIN", "PLACED"]).sum()
    global_sr = pct(global_wins, global_n)
    global_fr = pct(global_placed, global_n)

    days_list = daily_stats(non_x)
    above = sum(1 for d in days_list if d["vs_baseline"] == "ABOVE")
    at = sum(1 for d in days_list if d["vs_baseline"] == "AT")
    below = sum(1 for d in days_list if d["vs_baseline"] == "BELOW")

    print(f"GLOBAL: n={global_n}, SR={global_sr}%, Frame={global_fr}%")
    print(f"Days: {total_days} | Above baseline: {above} | At: {at} | Below: {below}")

    # ── VP Band analysis ───────────────────────────────────────────────────────
    m_non_x = merged[merged["decision_tier"] != "X"].copy()
    m_non_x["vp"] = m_non_x["velo_prime_prob"]

    vp_bands = []
    for lo, hi, label in [
        (0.0,  0.20, "VP<0.20"),
        (0.20, 0.30, "VP 0.20-0.30"),
        (0.30, 0.40, "VP 0.30-0.40"),
        (0.40, 1.01, "VP>=0.40"),
    ]:
        sub = m_non_x[(m_non_x["vp"] >= lo) & (m_non_x["vp"] < hi)]
        if len(sub) > 0:
            vp_bands.append(band_stats(sub, label))

    vp_30_plus = m_non_x[m_non_x["vp"] >= 0.30]
    vp_30_combined = band_stats(vp_30_plus, "VP>=0.30 combined")
    vp_30_a = m_non_x[(m_non_x["vp"] >= 0.30) & (m_non_x["decision_tier"] == "A")]
    vp_30_tier_a = band_stats(vp_30_a, "VP>=0.30 + Tier A")

    # ── Tier analysis ──────────────────────────────────────────────────────────
    tier_stats = []
    for tier in ["A", "B", "C", "D", "X"]:
        sub = merged[merged["decision_tier"] == tier].copy()
        if len(sub) == 0:
            continue
        sub["vp"] = sub["velo_prime_prob"]
        ts = band_stats(sub, f"Tier {tier}")
        ts["miss_breakdown"] = sub["miss_reason"].value_counts().head(5).to_dict()
        tier_stats.append(ts)

    # B-tier drag test
    b_high_vp = m_non_x[(m_non_x["decision_tier"] == "B") & (m_non_x["vp"] >= 0.30)]
    b_low_vp = m_non_x[(m_non_x["decision_tier"] == "B") & (m_non_x["vp"] < 0.30)]
    b_high = band_stats(b_high_vp, "Tier B VP>=0.30")
    b_low = band_stats(b_low_vp, "Tier B VP<0.30")

    # ── Suppression test ───────────────────────────────────────────────────────
    baseline_pool = m_non_x.copy()
    suppressed_pool = m_non_x[~((m_non_x["decision_tier"] == "B") & (m_non_x["vp"] < 0.30))]
    sup_n = len(suppressed_pool)
    sup_wins = (suppressed_pool["outcome"] == "WIN").sum()
    sup_placed = suppressed_pool["outcome"].isin(["WIN", "PLACED"]).sum()
    suppression_test = {
        "original_n": global_n,
        "suppressed_n": int(sup_n),
        "rows_removed": int(global_n - sup_n),
        "pct_coverage_lost": round((global_n - sup_n) / global_n * 100, 1),
        "original_sr": global_sr,
        "suppressed_sr": pct(sup_wins, sup_n),
        "original_fr": global_fr,
        "suppressed_fr": pct(sup_placed, sup_n),
    }

    # ── Miss class analysis ────────────────────────────────────────────────────
    miss_rows = non_x[non_x["outcome"] == "MISS"]
    miss_classes = miss_rows["miss_reason"].value_counts().to_dict()
    sp_zone_misses = miss_rows[
        (miss_rows["actual_winner_sp"] >= 3.0) & (miss_rows["actual_winner_sp"] <= 8.5)
    ]
    southwell_misses = miss_rows[
        miss_rows["track"].str.contains("Southwell|Chelmsford|Wolverhampton|Lingfield", case=False, na=False)
    ]
    high_vp_misses = merged[
        (merged["decision_tier"] != "X") &
        (merged["outcome"] == "MISS") &
        (merged["velo_prime_prob"] >= 0.40)
    ]

    # ── Sidecar analysis ───────────────────────────────────────────────────────
    sidecars = []
    global_sr_pct = global_sr  # already a percentage

    # G Shadow (multiplier > 1.0)
    mg = merged[merged["decision_tier"] != "X"].copy()
    mg["g_shadow_active"] = (mg["g_shadow_multiplier"].fillna(0) > 1.0)
    sidecars.append(sidecar_analysis(mg, "g_shadow_active", label="G Shadow (multiplier>1.0)"))

    # RPDC release score active
    mg["rpdc_active"] = (mg["rpdc_release_score"].fillna(0) > 0.5)
    sidecars.append(sidecar_analysis(mg, "rpdc_active", label="RPDC release score>0.5"))

    # RPDC cash window flag
    mg["rpdc_cash"] = mg["rpdc_cash_window_flag"].fillna(False).astype(bool)
    sidecars.append(sidecar_analysis(mg, "rpdc_cash", label="RPDC cash window flag"))

    # Place prob high
    mg["place_prob_high"] = (mg["place_prob"].fillna(0) > 0.80)
    sidecars.append(sidecar_analysis(mg, "place_prob_high", label="Place prob>0.80"))

    # MDS (market deception) high — in A/B means decoy risk
    mg["mds_high"] = (mg["market_deception_score"].fillna(0) > 0.5)
    sidecars.append(sidecar_analysis(mg, "mds_high", label="Market deception score>0.5"))

    # Improvement score active
    mg["imp_active"] = (mg["improvement_score"].fillna(0) > 0.4)
    sidecars.append(sidecar_analysis(mg, "imp_active", label="Improvement score>0.40"))

    # Macro chaos — expected to suppress
    mg["macro_chaos"] = mg["macro_chaos_mode"].fillna(False).astype(bool)
    sc = sidecar_analysis(mg, "macro_chaos", label="Macro chaos mode")
    sc["expected"] = "suppress (chaos should reduce SR)"
    sidecars.append(sc)

    # Archetype = Structure
    mg["arch_structure"] = (mg["race_archetype"] == "Structure")
    sidecars.append(sidecar_analysis(mg, "arch_structure", label="Archetype=Structure"))

    # Archetype = Compression
    mg["arch_compression"] = (mg["race_archetype"] == "Compression")
    sidecars.append(sidecar_analysis(mg, "arch_compression", label="Archetype=Compression"))

    # ── Router lane truth (from innovation protocol) ───────────────────────────
    router_lanes = []
    if not ledger.empty:
        # Get latest row per lane from ledger
        for lane_name in ledger["lane"].unique():
            lane_rows = ledger[ledger["lane"] == lane_name].sort_values("run_ts").iloc[-1]
            router_lanes.append({
                "lane": lane_name,
                "n": int(lane_rows.get("n", 0)),
                "wins": int(lane_rows.get("wins", 0)),
                "strike_rate": float(lane_rows.get("strike_rate", 0)),
                "frame_rate": float(lane_rows.get("frame_rate", 0)),
                "roi": float(lane_rows.get("roi", 0)),
                "status": lane_rows.get("status", "?"),
                "freeze_flag": lane_rows.get("freeze_flag", False),
                "threshold_message": lane_rows.get("threshold_message", ""),
            })

    # ── Pattern-learning analysis ──────────────────────────────────────────────
    lp_analysis = {}
    if not lp.empty:
        lp["type"] = lp.get("pattern_type", lp.get("description", "")).apply(
            lambda x: "PRIME_HIT" if "PRIME hit" in str(x) else str(x)[:40]
        )
        lp["vp_from_desc"] = lp.get("description", "").str.extract(r"prob=([\d.]+)").astype(float)
        vp_vals = lp["vp_from_desc"].dropna()
        lp_analysis = {
            "total": len(lp),
            "prime_hits": int((lp["type"] == "PRIME_HIT").sum()),
            "dates_covered": int(lp["date"].nunique()),
            "avg_vp_at_hit": round(float(vp_vals.mean()), 3) if len(vp_vals) else None,
            "vp_band_dist": {
                "vp<0.20": int((vp_vals < 0.20).sum()),
                "vp 0.20-0.30": int(((vp_vals >= 0.20) & (vp_vals < 0.30)).sum()),
                "vp 0.30-0.40": int(((vp_vals >= 0.30) & (vp_vals < 0.40)).sum()),
                "vp>=0.40": int((vp_vals >= 0.40).sum()),
            },
        }

    # ── Modification impact ────────────────────────────────────────────────────
    # Split sigma into pre/post key modification dates
    mod_impact = []
    mods = sorted(MODIFICATION_TIMELINE, key=lambda x: x["date"])
    for i, mod in enumerate(mods):
        cut = mod["date"]
        pre = non_x[non_x["date"] < cut]
        post = non_x[non_x["date"] >= cut]
        if i + 1 < len(mods):
            next_cut = mods[i + 1]["date"]
            post = post[post["date"] < next_cut]
        if len(pre) < 5 or len(post) < 5:
            continue
        pre_sr = pct((pre["outcome"] == "WIN").sum(), len(pre))
        post_sr = pct((post["outcome"] == "WIN").sum(), len(post))
        pre_fr = pct(pre["outcome"].isin(["WIN", "PLACED"]).sum(), len(pre))
        post_fr = pct(post["outcome"].isin(["WIN", "PLACED"]).sum(), len(post))
        mod_impact.append({
            "date": cut,
            "feature": mod["feature"],
            "pre_n": int(len(pre)),
            "post_n": int(len(post)),
            "pre_sr": pre_sr,
            "post_sr": post_sr,
            "sr_delta": round(post_sr - pre_sr, 1),
            "pre_fr": pre_fr,
            "post_fr": post_fr,
            "fr_delta": round(post_fr - pre_fr, 1),
        })

    # ── Final signal ranking ───────────────────────────────────────────────────
    signal_rankings = []
    def add_ranking(label, sr, fr, n):
        r = rank_signal(sr, fr, n, STRIKE_BASELINE)
        signal_rankings.append({"signal": label, "n": n, "sr": sr, "fr": fr, "rank": r})

    add_ranking("VP>=0.30", vp_30_combined["strike_rate"], vp_30_combined["frame_rate"], vp_30_combined["n"])
    add_ranking("VP>=0.30 + Tier A", vp_30_tier_a["strike_rate"], vp_30_tier_a["frame_rate"], vp_30_tier_a["n"])
    add_ranking("Tier A (all VP)", next((t["strike_rate"] for t in tier_stats if t["label"] == "Tier A"), 0),
                next((t["frame_rate"] for t in tier_stats if t["label"] == "Tier A"), 0),
                next((t["n"] for t in tier_stats if t["label"] == "Tier A"), 0))
    add_ranking("Tier B (all VP)", next((t["strike_rate"] for t in tier_stats if t["label"] == "Tier B"), 0),
                next((t["frame_rate"] for t in tier_stats if t["label"] == "Tier B"), 0),
                next((t["n"] for t in tier_stats if t["label"] == "Tier B"), 0))
    add_ranking("Tier B VP<0.30", b_low["strike_rate"], b_low["frame_rate"], b_low["n"])
    add_ranking("Tier B VP>=0.30", b_high["strike_rate"], b_high["frame_rate"], b_high["n"])
    for lane in router_lanes:
        add_ranking(lane["lane"], lane["strike_rate"] * 100 if lane["strike_rate"] < 1 else lane["strike_rate"],
                    lane["frame_rate"] * 100 if lane["frame_rate"] < 1 else lane["frame_rate"], lane["n"])
    for sc in sidecars:
        if sc.get("n", 0) >= 5 and "strike_rate" in sc:
            add_ranking(f"Sidecar:{sc['label']}", sc["strike_rate"], sc.get("frame_rate", 0), sc["n"])

    # ── Assemble final result ──────────────────────────────────────────────────
    result = {
        "run_ts": RUN_TS,
        "summary": {
            "A_total_race_days": total_days,
            "B_total_verdicts_in_db": total_verdicts_db,
            "C_total_matched_outcomes": total_matched,
            "D_excluded_x_tier": int(len(excluded)),
            "D_unmatched_note": unmatched_note,
            "E_global_strike_rate": global_sr,
            "F_global_frame_rate": global_fr,
            "G_days_list": days_list,
            "H_baseline": f"SR={STRIKE_BASELINE*100}% | Frame={FRAME_BASELINE*100}%",
            "I_days_below_baseline": below,
            "J_days_at_baseline": at,
            "K_days_above_baseline": above,
        },
        "vp_band_analysis": {
            "bands": vp_bands,
            "vp_30_combined": vp_30_combined,
            "vp_30_tier_a": vp_30_tier_a,
            "vp_30_outperforms_baseline": vp_30_combined["strike_rate"] > STRIKE_BASELINE * 100,
            "vp_30_plus_tier_a_outperforms_vp_30": vp_30_tier_a["strike_rate"] > vp_30_combined["strike_rate"],
            "vp_20_30_dilution": b_low["strike_rate"] < global_sr,
        },
        "tier_analysis": {
            "tiers": tier_stats,
            "b_high_vp": b_high,
            "b_low_vp": b_low,
            "suppression_test": suppression_test,
        },
        "router_lanes": router_lanes,
        "sidecar_analysis": sidecars,
        "miss_class_analysis": {
            "all_miss_classes": {k: int(v) for k, v in miss_classes.items()},
            "total_misses": int(len(miss_rows)),
            "sp_3_8_misses": int(len(sp_zone_misses)),
            "sp_3_8_pct_of_misses": pct(len(sp_zone_misses), len(miss_rows)),
            "aw_southwell_misses": int(len(southwell_misses)),
            "high_vp_misses_n": int(len(high_vp_misses)),
            "high_vp_miss_sps": sorted(high_vp_misses["actual_winner_sp"].dropna().round(2).tolist()),
        },
        "learned_patterns": lp_analysis,
        "modification_impact": mod_impact,
        "signal_rankings": sorted(signal_rankings, key=lambda x: (
            {"PROVEN_SIGNAL": 0, "PROMISING_SIGNAL": 1, "WATCHLIST_SIGNAL": 2,
             "NOISY_SIGNAL": 3, "SUPPRESS_SIGNAL": 4, "INSUFFICIENT_SAMPLE": 5}.get(x["rank"], 6)
        )),
    }

    # ── Final conclusions ──────────────────────────────────────────────────────
    proven = [s for s in signal_rankings if s["rank"] in ("PROVEN_SIGNAL", "PROMISING_SIGNAL")]
    suppression_gain = suppression_test["suppressed_sr"] - suppression_test["original_sr"]
    b_drag_confirmed = suppression_gain > 2.0

    result["conclusions"] = {
        "A_what_is_working": [s["signal"] for s in signal_rankings
                              if s["rank"] in ("PROVEN_SIGNAL", "PROMISING_SIGNAL")],
        "B_what_is_not_working": [s["signal"] for s in signal_rankings
                                  if s["rank"] in ("SUPPRESS_SIGNAL",)],
        "C_promising_under_sampled": [s["signal"] for s in signal_rankings
                                      if s["rank"] == "WATCHLIST_SIGNAL"],
        "D_suppress_candidates": [s["signal"] for s in signal_rankings
                                  if s["rank"] == "SUPPRESS_SIGNAL"],
        "E_shadow_only": ["V1_BASE", "V2_CLASS4_ONLY", "V6_GOLD_SEAM", "Playbook G V3 core"],
        "F_candidate_lane_deserving": [s["signal"] for s in signal_rankings
                                       if s["rank"] == "PROMISING_SIGNAL"],
        "G_needs_more_data": [s["signal"] for s in signal_rankings
                              if s["rank"] == "INSUFFICIENT_SAMPLE"],
        "H_modification_direction": "See modification_impact for per-change metrics",
        "I_frame_rate_attribution": (
            "Frame detection appears structural (VP>=0.30 band performs consistently). "
            "Cannot attribute to a single modification without pre-ensemble baseline. "
            "Post-ensemble (Mar 16+) data is primary evidence corpus."
        ),
        "J_next_protocol": (
            "1. Continue evidence accumulation for V2/V6 router lanes. "
            "2. Track VP>=0.30+TierA as shadow candidate lane (do not stake). "
            f"3. {'Confirm B-tier VP<0.30 suppression — gain would be ' + str(round(suppression_gain, 1)) + '%' if b_drag_confirmed else 'B-tier drag not yet large enough to confirm suppression'}. "
            "4. Build audit dossier from this output. "
            "5. Next promotion review when V2 reaches n=30."
        ),
    }

    # ── Write outputs ──────────────────────────────────────────────────────────
    out_json = ROOT / "data" / "velo_unified_evidence_audit_v1.json"
    out_md = ROOT / "data" / "velo_unified_evidence_audit_v1.md"
    out_csv = ROOT / "data" / "velo_unified_evidence_audit_v1_metrics.csv"

    with open(out_json, "w") as f:
        json.dump(result, f, indent=2, default=str)

    # CSV metrics
    csv_rows = []
    for b in vp_bands + [vp_30_combined, vp_30_tier_a]:
        csv_rows.append({"type": "VP_BAND", **{k: v for k, v in b.items() if not isinstance(v, list)}})
    for t in tier_stats:
        csv_rows.append({"type": "TIER", **{k: v for k, v in t.items() if not isinstance(v, (list, dict))}})
    for s in signal_rankings:
        csv_rows.append({"type": "SIGNAL_RANK", **s})
    pd.DataFrame(csv_rows).to_csv(out_csv, index=False)

    # Markdown report
    lines = [
        f"# VÉLØ Unified Evidence Audit V1",
        f"**Run:** {RUN_TS}",
        "",
        "---",
        "",
        "## Global Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Race days audited | {total_days} |",
        f"| Total verdicts in DB | {total_verdicts_db} |",
        f"| Total sigma_audit rows | {total_matched} |",
        f"| X-tier excluded | {len(excluded)} |",
        f"| Global strike rate (non-X) | **{global_sr}%** (baseline {STRIKE_BASELINE*100:.0f}%) |",
        f"| Global frame rate (non-X) | **{global_fr}%** (baseline {FRAME_BASELINE*100:.0f}%) |",
        f"| Days above baseline | {above} |",
        f"| Days at baseline | {at} |",
        f"| Days below baseline | {below} |",
        "",
        "---",
        "",
        "## VP Band Truth",
        "",
        "| Band | n | Wins | SR | Frame | Avg VP |",
        "|---|---|---|---|---|---|",
    ]
    for b in vp_bands + [vp_30_combined, vp_30_tier_a]:
        lines.append(
            f"| {b['label']} | {b['n']} | {b['wins']} | {b['strike_rate']}% | "
            f"{b['frame_rate']}% | {b.get('avg_vp') or '—'} |"
        )
    lines += [
        "",
        f"**VP ≥ 0.30 outperforms baseline:** {'YES' if result['vp_band_analysis']['vp_30_outperforms_baseline'] else 'NO'}",
        f"**VP ≥ 0.30 + Tier A outperforms VP ≥ 0.30 alone:** {'YES' if result['vp_band_analysis']['vp_30_plus_tier_a_outperforms_vp_30'] else 'NO'}",
        "",
        "---",
        "",
        "## Tier Truth",
        "",
        "| Tier | n | Wins | SR | Frame | Avg VP |",
        "|---|---|---|---|---|---|",
    ]
    for t in tier_stats:
        lines.append(
            f"| {t['label']} | {t['n']} | {t['wins']} | {t['strike_rate']}% | "
            f"{t['frame_rate']}% | {t.get('avg_vp') or '—'} |"
        )
    lines += [
        "",
        "### B-Tier Suppression Test",
        "",
        f"| | Original | Suppressed (excl B VP<0.30) |",
        f"|---|---|---|",
        f"| n | {suppression_test['original_n']} | {suppression_test['suppressed_n']} |",
        f"| Rows removed | — | {suppression_test['rows_removed']} ({suppression_test['pct_coverage_lost']}% coverage lost) |",
        f"| Strike rate | {suppression_test['original_sr']}% | {suppression_test['suppressed_sr']}% |",
        f"| Frame rate | {suppression_test['original_fr']}% | {suppression_test['suppressed_fr']}% |",
        "",
        "---",
        "",
        "## Router Lane Truth",
        "",
        "| Lane | n | SR | Frame | ROI | Status |",
        "|---|---|---|---|---|---|",
    ]
    for lane in router_lanes:
        sr_disp = f"{lane['strike_rate']:.1f}%" if lane["strike_rate"] > 1 else f"{lane['strike_rate']*100:.1f}%"
        fr_disp = f"{lane['frame_rate']:.1f}%" if lane["frame_rate"] > 1 else f"{lane['frame_rate']*100:.1f}%"
        roi_disp = f"{lane['roi']:+.1f}%" if lane["roi"] > 1 or lane["roi"] < -1 else f"{lane['roi']*100:+.1f}%"
        lines.append(f"| {lane['lane']} | {lane['n']} | {sr_disp} | {fr_disp} | {roi_disp} | {lane['status']} |")

    lines += [
        "",
        "---",
        "",
        "## Sidecar / Shadow Signal Truth",
        "",
        "| Signal | n | SR | Frame | Lift vs Global | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for sc in sidecars:
        if "strike_rate" not in sc:
            lines.append(f"| {sc['label']} | {sc.get('n',0)} | — | — | — | {sc['verdict']} |")
        else:
            lines.append(
                f"| {sc['label']} | {sc['n']} | {sc['strike_rate']}% | "
                f"{sc.get('frame_rate',0)}% | {sc.get('lift_sr',0):+.1f}% | {sc['verdict']} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Miss Class Truth",
        "",
        f"Total misses: {result['miss_class_analysis']['total_misses']}",
        "",
        "| Miss class | Count |",
        "|---|---|",
    ]
    for k, v in sorted(result["miss_class_analysis"]["all_miss_classes"].items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        f"**SP 3.0–8.5 zone misses:** {result['miss_class_analysis']['sp_3_8_misses']} "
        f"({result['miss_class_analysis']['sp_3_8_pct_of_misses']}% of all misses)",
        f"**High VP (≥0.40) misses:** {result['miss_class_analysis']['high_vp_misses_n']}",
        f"**AW/Southwell card misses:** {result['miss_class_analysis']['aw_southwell_misses']}",
        "",
        "---",
        "",
        "## Signal Rankings",
        "",
        "| Signal | n | SR | Frame | Rank |",
        "|---|---|---|---|---|",
    ]
    for s in result["signal_rankings"]:
        lines.append(f"| {s['signal']} | {s['n']} | {s['sr']}% | {s['fr']}% | **{s['rank']}** |")

    lines += [
        "",
        "---",
        "",
        "## Conclusions",
        "",
        f"**A. What is working:** {', '.join(result['conclusions']['A_what_is_working']) or 'None confirmed'}",
        f"**B. What is not working:** {', '.join(result['conclusions']['B_what_is_not_working']) or 'None confirmed'}",
        f"**C. Promising (under-sampled):** {', '.join(result['conclusions']['C_promising_under_sampled']) or 'None'}",
        f"**D. Suppress candidates:** {', '.join(result['conclusions']['D_suppress_candidates']) or 'None'}",
        f"**E. Shadow-only:** {', '.join(result['conclusions']['E_shadow_only'])}",
        f"**F. Candidate lanes:** {', '.join(result['conclusions']['F_candidate_lane_deserving']) or 'None promoted yet'}",
        f"**G. Needs more data:** {', '.join(result['conclusions']['G_needs_more_data'][:5]) or 'None'}...",
        f"**H. Modifications:** {result['conclusions']['H_modification_direction']}",
        f"**I. Frame attribution:** {result['conclusions']['I_frame_rate_attribution']}",
        "",
        f"**J. Next protocol:**",
        f"{result['conclusions']['J_next_protocol']}",
        "",
        "---",
        f"*Generated by scripts/run_velo_unified_evidence_audit.py — {RUN_TS}*",
    ]

    with open(out_md, "w") as f:
        f.write("\n".join(lines))

    print(f"\nOutputs written:")
    print(f"  JSON:   {out_json}")
    print(f"  MD:     {out_md}")
    print(f"  CSV:    {out_csv}")
    print(f"\nAudit complete — {RUN_TS}")
    return result


if __name__ == "__main__":
    main()
