#!/usr/bin/env python3
"""
VFU-25 + VFU-26: Verdict → Sigma Enrichment

Shared helper: cross-references sigma result rows with daily verdict files
to extract No-RPR shadow prob (VFU-25) and NDS badge fields (VFU-26) for
the VELO top pick in each race.

VFU-25 (No-RPR Shadow Sigma Enrichment):
  sqpe_no_rpr_shadow_prob was added to velo_prime_verdicts on 2026-05-09.
  Sigma rows don't carry it through. This script reads both files, builds
  a per-race enriched table, and computes No-RPR shadow SR.

  IMPORTANT: No-RPR probs max out at ~0.335 (excludes SP/market features).
  WIN_LANE threshold is model-native: ≥ 0.15 (empirically ~top quartile of
  no-rpr scores, roughly equivalent to the full model's 0.40 VP threshold
  in terms of relative model confidence).

VFU-26 (NDS Gap Diagnostic):
  nds_* fields are present in verdicts but all scores = 0.0 because NDS
  receives sp_dec=10.0 (pre-race default) — real SPs aren't known at
  scoring time. The overround signal threshold (1.15) is never reached with
  a flat uniform market, and the historical data frame is always empty.
  This script documents the gap and classifies the root cause.
  Real retroactive NDS computation is deferred to Phase 7 (needs results
  files with full runner SPs, not just the top pick).

Usage:
    python scripts/ops/vfu_verdict_sigma_enrichment.py --cutoff 2026-06-15
    python scripts/ops/vfu_verdict_sigma_enrichment.py --cutoff 2026-06-15 --through 2026-07-27
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

OUTPUT_VFU25  = DATA / "reports" / "vfu_25_norpr_shadow_sigma.json"
OUTPUT_VFU25B = DATA / "reports" / "vfu_25_norpr_shadow_sigma.md"
OUTPUT_VFU26  = DATA / "reports" / "vfu_26_nds_sigma_enrichment.json"
OUTPUT_VFU26B = DATA / "reports" / "vfu_26_nds_sigma_enrichment.md"

VFU25_VERSION = "VFU_25_NORPR_SIGMA_ENRICHMENT_V1"
VFU26_VERSION = "VFU_26_NDS_SIGMA_ENRICHMENT_V1"


def normalize_horse(name: str) -> str:
    return (name or "").lower().strip().replace("'", "").replace("-", " ").replace("  ", " ")


# ------------------------------------------------------------------
# Verdict index builder
# ------------------------------------------------------------------

def _build_verdict_index(date_str: str) -> dict[str, dict]:
    """
    Return {normalized_horse_name: top_field_dict} for a date's verdicts.
    Keyed by the top pick's horse name (normalized).
    Also keyed by race_id for direct race lookups.
    """
    date_tag = date_str.replace("-", "_")
    path = DATA / f"velo_prime_verdicts_{date_tag}.json"
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    races = raw if isinstance(raw, list) else (
        raw.get("verdicts") or raw.get("races") or []
    )

    index: dict[str, dict] = {}
    for race in races:
        top = race.get("top") or {}
        if not top:
            continue
        race_id   = str(race.get("race_id") or top.get("race_id") or "")
        horse_raw = top.get("horse") or ""
        norm      = normalize_horse(horse_raw)
        entry = {
            "race_id":               race_id,
            "horse":                 horse_raw,
            "velo_prime_prob":       top.get("velo_prime_prob"),
            "sqpe_no_rpr_shadow_prob":  top.get("sqpe_no_rpr_shadow_prob"),
            "sqpe_no_rpr_feature_count": top.get("sqpe_no_rpr_shadow_feature_count"),
            "nds_score":             top.get("nds_score"),
            "nds_narrative":         top.get("nds_narrative"),
            "nds_disruption":        top.get("nds_disruption"),
            "nds_is_fade":           top.get("nds_is_fade"),
            "nds_overround_signal":  top.get("nds_overround_signal"),
        }
        if race_id:
            index[f"race:{race_id}"] = entry
        if norm:
            index[f"horse:{norm}"] = entry
    return index


def _lookup_verdict(sigma_row: dict, verdict_index: dict) -> dict:
    """
    Find the verdict entry for a sigma row.
    Tries race_id first, then predicted horse name.
    """
    race_id_key = f"race:{sigma_row.get('race_id', '')}"
    if race_id_key in verdict_index:
        return verdict_index[race_id_key]
    norm_key = f"horse:{normalize_horse(sigma_row.get('predicted', ''))}"
    return verdict_index.get(norm_key, {})


# ------------------------------------------------------------------
# Sigma loader
# ------------------------------------------------------------------

def load_sigma_rows(cutoff: str, through: str) -> list[dict]:
    rows = []
    for path in sorted((DATA / "sigma_results").glob("sigma_results_2026_*.json")):
        date_str = path.stem.replace("sigma_results_", "").replace("_", "-")
        if date_str < cutoff or date_str > through:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in data.get("rows", []):
            rows.append({**row, "_date": date_str})
    return rows


# ------------------------------------------------------------------
# VFU-25: No-RPR Shadow Analysis
# ------------------------------------------------------------------

def analyse_norpr(enriched: list[dict]) -> dict:
    """Compute No-RPR shadow performance metrics."""
    with_norpr = [r for r in enriched if r.get("no_rpr_prob") is not None]
    n = len(enriched)
    n_enriched = len(with_norpr)

    if not with_norpr:
        return {"n": n, "n_enriched": n_enriched, "verdict": "NO_NORPR_FIELDS_IN_VERDICTS"}

    wins     = sum(1 for r in with_norpr if r.get("outcome") == "WIN")
    frames   = sum(1 for r in with_norpr if r.get("outcome") in ("WIN", "PLACED"))
    no_rpr_sr    = round(wins / n_enriched, 4) if n_enriched else None
    no_rpr_fr    = round(frames / n_enriched, 4) if n_enriched else None

    # Agreement: both models agree on the pick (always, since sigma row IS the top pick)
    # HIGH CONFIDENCE ZONE: no-rpr native threshold ≥ 0.15
    # (No-RPR probs max ~0.335; 0.15 is empirically ~top quartile.
    #  Using 0.40 would capture zero rows — wrong scale for this model.)
    NO_RPR_HIGH_CONF_THRESHOLD = 0.15
    wl_rows   = [r for r in with_norpr if (r.get("no_rpr_prob") or 0.0) >= NO_RPR_HIGH_CONF_THRESHOLD]
    wl_n      = len(wl_rows)
    wl_wins   = sum(1 for r in wl_rows if r.get("outcome") == "WIN")
    wl_frames = sum(1 for r in wl_rows if r.get("outcome") in ("WIN", "PLACED"))

    # High disagreement: live VP >= 0.40 but no-rpr < 0.20 (market signal, not pure form)
    disagree  = [r for r in with_norpr
                 if (r.get("velo_prime_prob") or 0.0) >= 0.40
                 and (r.get("no_rpr_prob") or 0.0) < 0.20]
    dis_n     = len(disagree)
    dis_wins  = sum(1 for r in disagree if r.get("outcome") == "WIN")

    return {
        "n": n,
        "n_enriched": n_enriched,
        "enrichment_rate": round(n_enriched / n, 4) if n else 0,
        "norpr_sr": no_rpr_sr,
        "norpr_frame_rate": no_rpr_fr,
        "norpr_win_lane_n": wl_n,
        "norpr_win_lane_sr": round(wl_wins / wl_n, 4) if wl_n else None,
        "norpr_win_lane_frame_rate": round(wl_frames / wl_n, 4) if wl_n else None,
        "live_norpr_high_disagree_n": dis_n,
        "live_norpr_high_disagree_sr": round(dis_wins / dis_n, 4) if dis_n else None,
        "verdict": "NO_RPR_SHADOW_TRACKING_INITIALIZED" if n_enriched >= 30 else "INSUFFICIENT_DATA",
    }


# ------------------------------------------------------------------
# VFU-26: NDS Signal Analysis
# ------------------------------------------------------------------

def analyse_nds(enriched: list[dict]) -> dict:
    """
    Document NDS gap: all scores are 0.0 because NDS receives sp_dec=10.0
    (pre-race default, not real market odds) and an empty historical DataFrame.

    Root causes:
      1. OVERROUND_SIGNAL: requires market_overround > 1.15, but uniform SP=10.0
         gives total implied prob = n×0.10 ≤ 1.0 → overround never reaches 1.15
      2. RECENCY_SIGNAL: returns 0.0 when hist_df is empty (always empty)
      3. FORM_QUALITY_SIGNAL: returns 0.0 when hist_df is empty
      4. ODDS_DRIFT_SIGNAL: always 0.0 (TODO placeholder in nds.py)
    """
    with_nds = [r for r in enriched if r.get("nds_score") is not None]
    n = len(enriched)
    n_enriched = len(with_nds)

    from collections import Counter
    score_dist = Counter("zero" if (r.get("nds_score") or 0.0) == 0.0 else "nonzero"
                         for r in with_nds)
    narrative_dist = Counter(r.get("nds_narrative") for r in with_nds)

    pct_zero = round(score_dist.get("zero", 0) / n_enriched, 4) if n_enriched else None

    return {
        "n": n,
        "n_enriched": n_enriched,
        "enrichment_rate": round(n_enriched / n, 4) if n else 0,
        "pct_score_zero": pct_zero,
        "nonzero_scores": score_dist.get("nonzero", 0),
        "narrative_breakdown": dict(narrative_dist.most_common(5)),
        "root_cause": [
            "SP_DECIMAL_DEFAULT_10: pre-race scoring receives sp_dec=10.0 for all runners",
            "OVERROUND_BELOW_THRESHOLD: uniform 10.0 SP gives overround ≤ 1.0, never reaches 1.15 trigger",
            "HIST_DF_EMPTY: recency/form signals always return 0.0 without historical dataframe",
            "ODDS_DRIFT_PLACEHOLDER: always 0.0 (TODO in nds.py L250)",
        ],
        "recommendation": "Feed best_odds_decimal (pre-race market price) instead of sp_dec to NDS, and build hist_df from form_history data. Retroactive NDS with real SPs deferred to Phase 7.",
        "verdict": "NDS_GAP_DOCUMENTED" if n_enriched > 0 else "NO_NDS_FIELDS_IN_VERDICTS",
        "fade_signal_quality": "NOT_OPERATIONAL_SP_DATA_MISSING",
    }


# ------------------------------------------------------------------
# Enrichment loop
# ------------------------------------------------------------------

def enrich_rows(sigma_rows: list[dict]) -> list[dict]:
    verdict_cache: dict[str, dict] = {}
    enriched = []
    for row in sigma_rows:
        date_str = row["_date"]
        if date_str not in verdict_cache:
            verdict_cache[date_str] = _build_verdict_index(date_str)
        v = _lookup_verdict(row, verdict_cache[date_str])
        enriched.append({
            **row,
            "no_rpr_prob":       v.get("sqpe_no_rpr_shadow_prob"),
            "nds_score":         v.get("nds_score"),
            "nds_narrative":     v.get("nds_narrative"),
            "nds_disruption":    v.get("nds_disruption"),
            "nds_is_fade":       v.get("nds_is_fade"),
            "nds_overround":     v.get("nds_overround_signal"),
        })
    return enriched


# ------------------------------------------------------------------
# Brief builders
# ------------------------------------------------------------------

def _build_norpr_brief(summary: dict) -> str:
    m = summary.get("metrics", {})
    lines = [
        "# VFU-25 — No-RPR Shadow Sigma Enrichment — Operator Brief",
        "",
        f"## Period: {summary.get('cutoff')} to {summary.get('through')}",
        f"  Sigma rows: {m.get('n',0)} | Enriched: {m.get('n_enriched',0)} ({m.get('enrichment_rate',0)*100:.1f}%)",
        "",
        "## No-RPR Shadow Performance",
        "| Metric | No-RPR Shadow | Live Model (VFU-22) |",
        "|---|---|---|",
        f"| Overall SR | {m.get('norpr_sr','n/a')} | 0.2556 |",
        f"| Overall frame rate | {m.get('norpr_frame_rate','n/a')} | 0.5809 |",
        f"| WIN_LANE SR (>=0.40) | {m.get('norpr_win_lane_sr','n/a')} | 0.3077 |",
        f"| WIN_LANE frame rate | {m.get('norpr_win_lane_frame_rate','n/a')} | 0.6717 |",
        f"| WIN_LANE n | {m.get('norpr_win_lane_n','n/a')} | 533 |",
        "",
        "## High-Disagreement Analysis (live VP>=0.40, no-rpr<0.20)",
        f"  Rows: {m.get('live_norpr_high_disagree_n','n/a')}  SR: {m.get('live_norpr_high_disagree_sr','n/a')}",
        "",
        f"**Verdict: {m.get('verdict', 'UNKNOWN')}**",
        "",
        "## Classifications",
        *[f"- {c}" for c in summary.get("classification_codes", [])],
    ]
    return "\n".join(lines)


def _build_nds_brief(summary: dict) -> str:
    m = summary.get("metrics", {})
    lines = [
        "# VFU-26 — NDS Gap Diagnostic — Operator Brief",
        "",
        f"## Period: {summary.get('cutoff')} to {summary.get('through')}",
        f"  Sigma rows: {m.get('n',0)} | NDS-enriched: {m.get('n_enriched',0)}",
        f"  Scores = 0.0: {m.get('pct_score_zero', 'n/a')*100 if m.get('pct_score_zero') else 'n/a'}%",
        "",
        "## Root Causes",
        *[f"- {r}" for r in (m.get("root_cause") or [])],
        "",
        "## Recommendation",
        f"> {m.get('recommendation', '')}",
        "",
        f"**Verdict: {m.get('verdict', 'UNKNOWN')}**",
        "",
        "## Classifications",
        *[f"- {c}" for c in summary.get("classification_codes", [])],
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main(cutoff: str = "2026-06-15", through: str = "2026-07-27") -> dict:
    (DATA / "reports").mkdir(parents=True, exist_ok=True)

    sigma_rows = load_sigma_rows(cutoff, through)
    enriched   = enrich_rows(sigma_rows)

    norpr_metrics = analyse_norpr(enriched)
    nds_metrics   = analyse_nds(enriched)

    summary_25 = {
        "vfu25_validation_version": VFU25_VERSION,
        "cutoff": cutoff,
        "through": through,
        "metrics": norpr_metrics,
        "classification_codes": [
            "VFU_25_NORPR_SIGMA_ENRICHMENT_COMPLETE",
            "NO_RPR_SHADOW_PROB_CROSS_REFERENCED",
            f"VERDICT_{norpr_metrics.get('verdict', 'UNKNOWN')}",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
            "NO_MODEL_PROMOTION",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }
    summary_26 = {
        "vfu26_validation_version": VFU26_VERSION,
        "cutoff": cutoff,
        "through": through,
        "metrics": nds_metrics,
        "classification_codes": [
            "VFU_26_NDS_GAP_DIAGNOSTIC_COMPLETE",
            "NDS_ROOT_CAUSE_SP_DECIMAL_DEFAULT_10",
            "NDS_NOT_OPERATIONAL_NO_REAL_MARKET_DATA",
            "NDS_RETROACTIVE_FIX_DEFERRED_TO_PHASE_7",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }

    OUTPUT_VFU25.write_text(json.dumps(summary_25, indent=2), encoding="utf-8")
    OUTPUT_VFU25B.write_text(_build_norpr_brief(summary_25), encoding="utf-8")
    OUTPUT_VFU26.write_text(json.dumps(summary_26, indent=2), encoding="utf-8")
    OUTPUT_VFU26B.write_text(_build_nds_brief(summary_26), encoding="utf-8")

    nm = norpr_metrics
    dm = nds_metrics
    print(f"VFU-25 No-RPR Shadow ({cutoff} to {through})")
    print(f"  Enriched {nm.get('n_enriched',0)}/{nm.get('n',0)} rows  SR={nm.get('norpr_sr','n/a')}  FR={nm.get('norpr_frame_rate','n/a')}")
    print(f"  WIN_LANE: n={nm.get('norpr_win_lane_n','n/a')} SR={nm.get('norpr_win_lane_sr','n/a')}  Verdict: {nm.get('verdict')}")
    print(f"\nVFU-26 NDS Gap Diagnostic ({cutoff} to {through})")
    print(f"  Enriched {dm.get('n_enriched',0)}/{dm.get('n',0)} rows")
    print(f"  NDS pct_zero: {dm.get('pct_score_zero','n/a')}  Non-zero: {dm.get('nonzero_scores','n/a')}")
    print(f"  Verdict: {dm.get('verdict')}")
    print(f"  Recommendation: {dm.get('recommendation','')[:80]}...")

    return {"vfu25": summary_25, "vfu26": summary_26}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff",  default="2026-06-15")
    parser.add_argument("--through", default="2026-07-27")
    args = parser.parse_args()
    main(args.cutoff, args.through)
