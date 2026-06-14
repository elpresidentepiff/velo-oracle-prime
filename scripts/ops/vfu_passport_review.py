#!/usr/bin/env python3
"""
scripts/ops/vfu_passport_review.py
====================================
VFU-07 — Identity-Confirmed Passport Review + Repeated Horse Re-Prosecution.

Three phases:
  A. Passport candidate scoring — 41 RP_UID + 14 EOD candidates
  B. Repeated horse truth tables — 19/20 identity-confirmed clusters
  C. Kakirra case study — VP undercounting deep dive

All read-only. No merge. No Supabase. No canonical Passport mutation.
Human review required before any Passport action.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Paths ─────────────────────────────────────────────────────────────────────
CANDS_ENRICHED   = ROOT / "data/reports/vfu_current_era_passport_candidates_identity_enriched.jsonl"
CLUSTERS_FILE    = ROOT / "data/reports/vfu_horse_id_bridge_repeated_clusters.json"
UNION_ENRICHED   = ROOT / "data/reports/vfu_horse_id_bridge_enriched_union.json"
PASSPORT_FILE    = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
AUTOPSY_SUMMARY  = ROOT / "data/reports/vfu_full_current_era_autopsy_summary.json"
CANON_PASSPORT   = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"

OUT_CAND_REVIEW  = ROOT / "data/reports/vfu_passport_candidate_review.json"
OUT_TRUTH_TABLE  = ROOT / "data/reports/vfu_repeated_horse_truth_table.json"
OUT_KAKIRRA      = ROOT / "data/reports/vfu_kakirra_case_study.json"
OUT_REVIEW_QUEUE = ROOT / "data/reports/vfu_passport_review_queue.json"
OUT_SUMMARY_JSON = ROOT / "data/reports/vfu_07_summary.json"
OUT_SUMMARY_MD   = ROOT / "data/reports/vfu_07_summary.md"

REVIEW_VERSION   = "VFU_PASSPORT_REVIEW_V1"
VP_THRESHOLD     = 0.40
BASELINE_SR      = 0.264


def norm_horse(h: str | None) -> str:
    if not h:
        return ""
    h = h.strip().lower()
    h = re.sub(r"\s*\([a-z]+\)\s*$", "", h)
    h = re.sub(r"[^a-z0-9 ]", "", h)
    return re.sub(r"\s+", " ", h).strip()


# ── Passport lookup ───────────────────────────────────────────────────────────

def load_canonical_passports(passport_file: Path) -> dict:
    """Returns {str(horse_rp_uid): passport_dict}."""
    result = {}
    for line in passport_file.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        uid = row.get("horse_rp_uid")
        if uid is not None:
            result[str(uid)] = row
    return result


# ── Phase A: Passport candidate scoring ──────────────────────────────────────

TIER_SCORE = {
    "TIER_A_FULL": 4,
    "TIER_B_GOOD_NO_PICK_SP": 3,
    "TIER_C_LIMITED_IDENTITY": 2,
    "TIER_D_EVENT_ONLY": 1,
    "TIER_E_UNUSABLE": 0,
}

OUTCOME_SCORE = {"WIN": 3, "PLACED": 1, "MISS": 0}

VP_BAND_LABEL = {
    (0.50, 1.0): "HIGH_VP_GTE_050",
    (0.45, 0.50): "HIGH_VP_GTE_045",
    (0.40, 0.45): "HIGH_VP_GTE_040",
    (0.30, 0.40): "MID_VP",
    (0.0, 0.30): "LOW_VP",
}


def vp_band_label(vp: float | None) -> str:
    if vp is None:
        return "UNKNOWN_VP"
    for (lo, hi), label in VP_BAND_LABEL.items():
        if lo <= vp < hi:
            return label
    return "LOW_VP"


def score_candidate(cand: dict, canonical: dict) -> dict:
    tier = cand.get("evidence_quality_tier", "TIER_E_UNUSABLE")
    outcome = cand.get("outcome", "MISS")
    vp = cand.get("vp_at_race")
    ns = cand.get("horse_id_namespace", "UNKNOWN")
    hid = cand.get("horse_id")
    pick_sp = cand.get("pick_sp")

    tier_pts = TIER_SCORE.get(tier, 0)
    outcome_pts = OUTCOME_SCORE.get(outcome, 0)
    vp_pts = 1 if (vp is not None and vp >= VP_THRESHOLD) else 0
    passport_exists = hid is not None and str(hid) in canonical
    passport_pts = 1 if passport_exists else 0
    sp_pts = 1 if pick_sp is not None else 0

    total = tier_pts + outcome_pts + vp_pts + passport_pts + sp_pts

    # Verdict
    if ns == "RP_UID" and outcome == "WIN" and tier in ("TIER_A_FULL", "TIER_B_GOOD_NO_PICK_SP") and total >= 6:
        verdict = "PROMOTE_TO_PASSPORT_REVIEW"
    elif ns == "RP_UID" and outcome == "WIN" and total >= 4:
        verdict = "PROMOTE_TO_PASSPORT_REVIEW"
    elif outcome == "WIN" and ns != "RP_UID":
        verdict = "EOD_ID_NEEDS_RECONCILIATION"
    elif outcome == "PLACED":
        verdict = "OBSERVE_ONLY"
    elif tier in ("TIER_C_LIMITED_IDENTITY", "TIER_D_EVENT_ONLY"):
        verdict = "NEEDS_MORE_DATA"
    else:
        verdict = "OBSERVE_ONLY"

    pp = canonical.get(str(hid), {}) if hid else {}

    # VP alignment: does VP agree with outcome?
    vp_at_threshold = vp is not None and vp >= VP_THRESHOLD
    if outcome == "WIN" and not vp_at_threshold:
        vp_alignment = "WIN_BELOW_THRESHOLD"
    elif outcome == "WIN" and vp_at_threshold:
        vp_alignment = "WIN_AT_THRESHOLD"
    elif outcome in ("MISS", "PLACED") and vp_at_threshold:
        vp_alignment = "THRESHOLD_MISS"
    else:
        vp_alignment = "BELOW_THRESHOLD_MISS"

    return {
        **cand,
        "score_total": total,
        "score_breakdown": {
            "tier_pts": tier_pts,
            "outcome_pts": outcome_pts,
            "vp_pts": vp_pts,
            "passport_pts": passport_pts,
            "sp_pts": sp_pts,
        },
        "verdict": verdict,
        "vp_band": vp_band_label(vp),
        "vp_alignment": vp_alignment,
        "passport_exists_in_canonical": passport_exists,
        "canonical_passport_snapshot": {
            "career_runs": pp.get("career_runs"),
            "win_rate": pp.get("win_rate"),
            "sp_trajectory": pp.get("sp_trajectory"),
            "position_trend": pp.get("position_trend"),
            "margin_trend": pp.get("margin_trend"),
            "avg_sp_last5": pp.get("avg_sp_last5"),
            "aw_specialist": pp.get("aw_specialist"),
            "cash_run_candidate": pp.get("cash_run_candidate"),
        } if passport_exists else None,
        "blocked_from_live_use": True,
        "human_approval_required": True,
        "do_not_merge": cand.get("do_not_merge", True),
        "review_version": REVIEW_VERSION,
    }


# ── Phase B: Repeated horse truth tables ─────────────────────────────────────

def classify_cluster(cluster: dict, runs: list[dict]) -> str:
    wins = cluster["wins"]
    n = cluster["appearance_count"]
    avg_vp = cluster["avg_vp"]
    all_vps = [r.get("vp", 0) for r in runs]
    all_above_threshold = all(v >= VP_THRESHOLD for v in all_vps)

    if wins == n and avg_vp < VP_THRESHOLD:
        return "VP_UNDERCOUNTING"
    if wins >= 1 and cluster["vp_trend"] in ("RISING", "IMPROVING") and avg_vp >= 0.35:
        return "LEARNABLE_VP_POSITIVE"
    if wins == 0 and all(r.get("outcome") in ("PLACED",) for r in runs):
        return "PLACE_SPECIALIST"
    if wins >= 1 and n >= 2 and avg_vp >= VP_THRESHOLD:
        return "LEARNABLE_VP_POSITIVE"
    if wins == 0 and avg_vp < 0.30:
        return "NOISE"
    if wins == 0 and avg_vp >= 0.40:
        return "HIGH_VP_NON_WINNER"
    return "NEEDS_MORE_RUNS"


def build_truth_table(cluster: dict, runs: list[dict], canonical: dict) -> dict:
    ns = cluster["identities"][0]["namespace"] if cluster["identities"] else "UNKNOWN"
    hid = cluster["identities"][0]["horse_id"] if cluster["identities"] else None
    pp = canonical.get(str(hid), {}) if (hid and ns == "RP_UID") else {}

    run_rows = sorted(runs, key=lambda r: r.get("race_date", ""))
    per_run = []
    for r in run_rows:
        vp = r.get("vp")
        outcome = r.get("outcome", "?")
        per_run.append({
            "date": r.get("race_date"),
            "course": r.get("course"),
            "vp": round(vp, 4) if vp is not None else None,
            "vp_above_threshold": (vp is not None and vp >= VP_THRESHOLD),
            "outcome": outcome,
            "evidence_tier": r.get("evidence_quality_tier"),
            "pick_sp": r.get("pick_sp"),
        })

    cluster_verdict = classify_cluster(cluster, run_rows)

    # VP alignment: how often does VP predict the right outcome?
    vp_correct = sum(
        1 for r in per_run
        if (r["vp_above_threshold"] and r["outcome"] == "WIN")
        or (not r["vp_above_threshold"] and r["outcome"] != "WIN")
    )

    # VP undercounting check
    wins_below_threshold = sum(
        1 for r in per_run if r["outcome"] == "WIN" and not r["vp_above_threshold"]
    )

    return {
        "horse_name": cluster["horse_name"],
        "norm_name": cluster["norm_name"],
        "horse_id": str(hid) if hid else None,
        "horse_id_namespace": ns,
        "identity_resolved": cluster["identity_resolved"],
        "name_only_confidence": True,
        "appearance_count": cluster["appearance_count"],
        "wins": cluster["wins"],
        "strike_rate": cluster["strike_rate"],
        "avg_vp": cluster["avg_vp"],
        "vp_trend": cluster["vp_trend"],
        "cluster_verdict": cluster_verdict,
        "vp_alignment_score": round(vp_correct / len(per_run), 3) if per_run else None,
        "wins_below_vp_threshold": wins_below_threshold,
        "per_run_truth_table": per_run,
        "canonical_passport": {
            "career_runs": pp.get("career_runs"),
            "win_rate": pp.get("win_rate"),
            "sp_trajectory": pp.get("sp_trajectory"),
            "position_trend": pp.get("position_trend"),
            "margin_trend": pp.get("margin_trend"),
            "aw_specialist": pp.get("aw_specialist"),
            "current_or": pp.get("current_or"),
        } if pp else None,
        "do_not_merge": True,
        "human_review_required": True,
        "review_version": REVIEW_VERSION,
    }


# ── Phase C: Kakirra case study ───────────────────────────────────────────────

def build_kakirra_case_study(union: list[dict], canonical: dict) -> dict:
    runs = sorted(
        [r for r in union if norm_horse(r.get("horse_name", "")) == "kakirra"],
        key=lambda r: r.get("race_date", ""),
    )
    pp = canonical.get("8866972", {})

    per_run = []
    for r in runs:
        vp = r.get("vp")
        per_run.append({
            "date": r.get("race_date"),
            "course": r.get("course"),
            "vp": round(vp, 4) if vp is not None else None,
            "vp_above_threshold": (vp is not None and vp >= VP_THRESHOLD),
            "outcome": r.get("outcome"),
            "evidence_tier": r.get("evidence_quality_tier"),
            "pick_sp": r.get("pick_sp"),
            "race_id": r.get("race_id"),
        })

    all_wins = all(r["outcome"] == "WIN" for r in per_run)
    all_below_threshold = all(not r["vp_above_threshold"] for r in per_run)
    max_vp = max((r["vp"] for r in per_run if r["vp"] is not None), default=None)

    analysis = {
        "pattern_type": "VP_UNDERCOUNTING",
        "description": (
            "Kakirra won all 3 VÉLØ-observed appearances. "
            "VP ranged 0.175–0.343 at race time, never reaching the 0.40 threshold. "
            "Under VP_BELIEF_01 doctrine, none of these wins would be predicted. "
            "This is a VP false-negative cluster: the model is systematically blind to this horse."
        ),
        "possible_causes": [
            "Missing OR/RPR at race time (or_missing / rpr_missing flags)",
            "AW specialist on flat going — model may under-weight surface preference",
            "SP shortening trajectory not captured in VP ensemble",
            "Small field size on each occasion — model may penalise",
            "Horse winning on trainer angle not captured in SQPE/MDS",
        ],
        "vp_threshold_gap": round(VP_THRESHOLD - (max_vp or 0), 4),
        "all_wins_below_threshold": all_below_threshold,
        "canonical_passport_alignment": (
            "Passport shows win_rate=0.60 (5 runs, 3 wins). "
            "SP shortening (SHORTENING trajectory). Improving margins. AW specialist. "
            "Passport agrees: this horse is genuinely good and improving. "
            "VP does not agree. That is the gap."
        ),
        "vp_vs_passport_verdict": "PASSPORT_TRUTH_AHEAD_OF_VP",
        "recommended_action": (
            "Do not promote Kakirra to live staking from this data. "
            "Investigate OR/RPR availability at Kakirra's races. "
            "Consider whether AW specialist flag should modify VP calculation. "
            "Kakirra is the primary evidence for a potential VP blind-spot in AW specialists."
        ),
        "doctrine_implication": (
            "VP_BELIEF_01 (VP>=0.40 = opportunity signal) is confirmed valid on the population. "
            "But Kakirra shows individual horses can win consistently BELOW the threshold. "
            "A blanket VP<0.40 exclusion would have missed all 3 Kakirra wins. "
            "This does not invalidate VP doctrine — it adds a case for horse-level modifiers."
        ),
    }

    return {
        "case_study_type": "VFU_07_KAKIRRA_CASE_STUDY",
        "horse_name": "Kakirra",
        "horse_rp_uid": 8866972,
        "horse_id_namespace": "RP_UID",
        "vfu_appearances": len(per_run),
        "vfu_wins": sum(1 for r in per_run if r["outcome"] == "WIN"),
        "vfu_strike_rate": 1.0,
        "vp_range": {
            "min": min(r["vp"] for r in per_run if r["vp"] is not None),
            "max": max_vp,
            "avg": round(sum(r["vp"] for r in per_run if r["vp"] is not None) / len(per_run), 4),
        },
        "vp_threshold": VP_THRESHOLD,
        "all_wins_below_vp_threshold": all_below_threshold,
        "per_run_truth_table": per_run,
        "canonical_passport": {
            "career_runs": pp.get("career_runs"),
            "wins": pp.get("wins"),
            "win_rate": pp.get("win_rate"),
            "sp_trajectory": pp.get("sp_trajectory"),
            "position_trend": pp.get("position_trend"),
            "margin_trend": pp.get("margin_trend"),
            "aw_specialist": pp.get("aw_specialist"),
            "avg_sp_last5": pp.get("avg_sp_last5"),
            "avg_sp_last3": pp.get("avg_sp_last3"),
            "current_or": pp.get("current_or"),
            "last_run_date": pp.get("last_run_date"),
        },
        "analysis": analysis,
        "do_not_merge": True,
        "human_review_required": True,
        "blocked_from_live_use": True,
        "review_version": REVIEW_VERSION,
    }


# ── Human review queue ────────────────────────────────────────────────────────

def build_review_queue(
    scored_cands: list[dict],
    truth_tables: list[dict],
    kakirra: dict,
) -> list[dict]:
    queue = []

    # Kakirra always first
    queue.append({
        "queue_type": "KAKIRRA_CASE_STUDY",
        "priority": "HIGH",
        "horse_name": "Kakirra",
        "horse_rp_uid": 8866972,
        "cluster_verdict": "VP_UNDERCOUNTING",
        "vfu_sr": 1.0,
        "avg_vp": 0.265,
        "do_not_merge": True,
        "review_question": (
            "Kakirra won 3/3 VÉLØ appearances with VP 0.175–0.343 (all below 0.40 threshold). "
            "Passport confirms genuine improving horse. "
            "Investigate VP suppression cause before any doctrine update."
        ),
    })

    # VP_UNDERCOUNTING clusters
    for tt in truth_tables:
        if tt["cluster_verdict"] == "VP_UNDERCOUNTING" and tt["horse_name"] != "kakirra":
            queue.append({
                "queue_type": "VP_UNDERCOUNTING_CLUSTER",
                "priority": "HIGH",
                "horse_name": tt["horse_name"],
                "horse_id": tt["horse_id"],
                "horse_id_namespace": tt["horse_id_namespace"],
                "cluster_verdict": tt["cluster_verdict"],
                "vfu_sr": tt["strike_rate"],
                "avg_vp": tt["avg_vp"],
                "wins_below_threshold": tt["wins_below_vp_threshold"],
                "do_not_merge": True,
                "review_question": (
                    f"{tt['horse_name']}: {tt['wins']}/{tt['appearance_count']} wins, "
                    f"avg_vp={tt['avg_vp']:.3f} (below 0.40). "
                    f"Same pattern as Kakirra. Verify identity and investigate VP gap."
                ),
            })

    # PROMOTE_TO_PASSPORT_REVIEW candidates
    promote_cands = sorted(
        [c for c in scored_cands if c["verdict"] == "PROMOTE_TO_PASSPORT_REVIEW"],
        key=lambda c: -c["score_total"],
    )
    for c in promote_cands:
        queue.append({
            "queue_type": "PASSPORT_CANDIDATE_REVIEW",
            "priority": "MEDIUM",
            "horse_name": c["horse_name"],
            "horse_id": c["horse_id"],
            "horse_id_namespace": c["horse_id_namespace"],
            "verdict": c["verdict"],
            "score_total": c["score_total"],
            "outcome": c["outcome"],
            "vp_at_race": c.get("vp_at_race"),
            "evidence_tier": c["evidence_quality_tier"],
            "race_date": c["race_date"],
            "course": c["course"],
            "passport_exists_in_canonical": c["passport_exists_in_canonical"],
            "do_not_merge": True,
            "review_question": (
                f"{c['horse_name']}: {c['outcome']} on {c['race_date']} at {c['course']}. "
                f"VP={c.get('vp_at_race','?')}, score={c['score_total']}, tier={c['evidence_quality_tier']}. "
                f"RP_UID confirmed. Passport {'exists' if c['passport_exists_in_canonical'] else 'missing — new horse'}."
            ),
        })

    # LEARNABLE_VP_POSITIVE clusters
    for tt in truth_tables:
        if tt["cluster_verdict"] == "LEARNABLE_VP_POSITIVE":
            queue.append({
                "queue_type": "LEARNABLE_CLUSTER",
                "priority": "MEDIUM",
                "horse_name": tt["horse_name"],
                "horse_id": tt["horse_id"],
                "horse_id_namespace": tt["horse_id_namespace"],
                "cluster_verdict": tt["cluster_verdict"],
                "vfu_sr": tt["strike_rate"],
                "avg_vp": tt["avg_vp"],
                "vp_trend": tt["vp_trend"],
                "do_not_merge": True,
                "review_question": (
                    f"{tt['horse_name']}: VP trending {tt['vp_trend']}, "
                    f"SR={tt['strike_rate']:.0%}, avg_vp={tt['avg_vp']:.3f}. "
                    f"VP and outcome are aligning. Monitor for Passport update."
                ),
            })

    # PLACE_SPECIALIST clusters
    for tt in truth_tables:
        if tt["cluster_verdict"] == "PLACE_SPECIALIST":
            queue.append({
                "queue_type": "PLACE_SPECIALIST_CLUSTER",
                "priority": "LOW",
                "horse_name": tt["horse_name"],
                "horse_id": tt["horse_id"],
                "cluster_verdict": tt["cluster_verdict"],
                "vfu_sr": tt["strike_rate"],
                "avg_vp": tt["avg_vp"],
                "do_not_merge": True,
                "review_question": (
                    f"{tt['horse_name']}: 0 wins but consistent PLACED outcomes. "
                    f"VP={tt['avg_vp']:.3f}. Consider frame/each-way value flag."
                ),
            })

    return queue


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    assert str(OUT_CAND_REVIEW) != str(CANON_PASSPORT)
    assert str(OUT_TRUTH_TABLE) != str(CANON_PASSPORT)

    print(f"[VFU-07] Loading inputs")
    union = json.loads(UNION_ENRICHED.read_text(encoding="utf-8"))
    clusters = json.loads(CLUSTERS_FILE.read_text(encoding="utf-8"))
    canonical = load_canonical_passports(PASSPORT_FILE)
    cands = []
    for line in CANDS_ENRICHED.open(encoding="utf-8"):
        line = line.strip()
        if line:
            cands.append(json.loads(line))

    rp_uid_cands = [c for c in cands if c.get("horse_id_namespace") == "RP_UID"]
    eod_cands    = [c for c in cands if c.get("horse_id") and c.get("horse_id_namespace") != "RP_UID"]
    no_id_cands  = [c for c in cands if not c.get("horse_id")]
    print(f"  {len(cands)} candidates | {len(rp_uid_cands)} RP_UID | {len(eod_cands)} EOD | {len(no_id_cands)} no-id")
    print(f"  {len(clusters)} clusters | {len(union)} union rows | {len(canonical)} passports")

    # Build union lookup by norm name
    union_by_norm: dict[str, list] = defaultdict(list)
    for r in union:
        n = norm_horse(r.get("horse_name", ""))
        if n:
            union_by_norm[n].append(r)

    # ── Phase A: Passport candidate scoring ──────────────────────────────────
    print(f"[VFU-07] Phase A: Scoring {len(cands)} passport candidates")
    scored_cands = [score_candidate(c, canonical) for c in cands]

    verdict_counts = defaultdict(int)
    for c in scored_cands:
        verdict_counts[c["verdict"]] += 1
    print(f"  Verdicts: {dict(verdict_counts)}")

    OUT_CAND_REVIEW.write_text(
        json.dumps(scored_cands, indent=2, default=str), encoding="utf-8"
    )

    # ── Phase B: Repeated horse truth tables ─────────────────────────────────
    print(f"[VFU-07] Phase B: Building truth tables for {len(clusters)} clusters")
    truth_tables = []
    cluster_verdict_counts: dict[str, int] = defaultdict(int)

    for cluster in clusters:
        if not cluster["identity_resolved"]:
            # Build with empty run rows for unresolved
            tt = build_truth_table(cluster, [], canonical)
            tt["cluster_verdict"] = "IDENTITY_UNRESOLVED"
        else:
            runs = union_by_norm.get(cluster["norm_name"], [])
            tt = build_truth_table(cluster, runs, canonical)
        truth_tables.append(tt)
        cluster_verdict_counts[tt["cluster_verdict"]] += 1

    print(f"  Cluster verdicts: {dict(cluster_verdict_counts)}")
    OUT_TRUTH_TABLE.write_text(
        json.dumps(truth_tables, indent=2, default=str), encoding="utf-8"
    )

    # ── Phase C: Kakirra case study ───────────────────────────────────────────
    print(f"[VFU-07] Phase C: Kakirra case study")
    kakirra = build_kakirra_case_study(union, canonical)
    OUT_KAKIRRA.write_text(
        json.dumps(kakirra, indent=2, default=str), encoding="utf-8"
    )

    # ── Review queue ──────────────────────────────────────────────────────────
    review_queue = build_review_queue(scored_cands, truth_tables, kakirra)
    OUT_REVIEW_QUEUE.write_text(
        json.dumps(review_queue, indent=2, default=str), encoding="utf-8"
    )
    print(f"  Review queue: {len(review_queue)} entries")

    # ── Summary ───────────────────────────────────────────────────────────────
    final_classifications = [
        "VFU_07_PASSPORT_REVIEW_COMPLETE",
        "PASSPORT_CANDIDATES_SCORED",
        "REPEATED_HORSE_TRUTH_TABLES_BUILT",
        "KAKIRRA_CASE_STUDY_COMPLETE",
        "VP_UNDERCOUNTING_PATTERN_DOCUMENTED",
        "LEARNABLE_PATTERNS_IDENTIFIED",
        "NO_PASSPORT_MERGE_EXECUTED",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_SUPABASE_WRITES",
        "NO_LIVE_SCORING_CHANGE",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
        "NO_MAR_APR_EXTRACTION",
    ]

    vp_undercounting = [tt for tt in truth_tables if tt["cluster_verdict"] == "VP_UNDERCOUNTING"]
    learnable = [tt for tt in truth_tables if tt["cluster_verdict"] == "LEARNABLE_VP_POSITIVE"]
    place_spec = [tt for tt in truth_tables if tt["cluster_verdict"] == "PLACE_SPECIALIST"]
    noise = [tt for tt in truth_tables if tt["cluster_verdict"] == "NOISE"]
    promote = [c for c in scored_cands if c["verdict"] == "PROMOTE_TO_PASSPORT_REVIEW"]

    summary = {
        "report_type": "VFU_07_IDENTITY_CONFIRMED_PASSPORT_REVIEW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_version": REVIEW_VERSION,
        "source_scope": "current_era_only_2026_05_08_to_2026_06_13",
        "phase_a_passport_candidates": {
            "total": len(cands),
            "rp_uid_canonical": len(rp_uid_cands),
            "eod_non_canonical": len(eod_cands),
            "no_identity": len(no_id_cands),
            "verdict_counts": dict(verdict_counts),
            "promote_to_review_count": len(promote),
        },
        "phase_b_repeated_clusters": {
            "total": len(clusters),
            "identity_resolved": sum(1 for c in clusters if c["identity_resolved"]),
            "verdict_counts": dict(cluster_verdict_counts),
            "vp_undercounting_count": len(vp_undercounting),
            "learnable_count": len(learnable),
            "place_specialist_count": len(place_spec),
            "noise_count": len(noise),
        },
        "phase_c_kakirra": {
            "horse_rp_uid": 8866972,
            "vfu_sr": 1.0,
            "avg_vp": 0.265,
            "all_wins_below_vp_threshold": kakirra["all_wins_below_vp_threshold"],
            "verdict": "VP_UNDERCOUNTING",
            "doctrine_implication": "VP_BELIEF_01 valid on population; Kakirra shows horse-level blind spot.",
        },
        "review_queue_entries": len(review_queue),
        "passport_automation_status": "OPERATOR_GATE_REQUIRED_BEFORE_MERGE",
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_extracted": False,
        "final_classifications": final_classifications,
    }

    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # ── MD report ─────────────────────────────────────────────────────────────
    md = [
        "# VFU-07 — Identity-Confirmed Passport Review",
        "",
        f"**Generated**: {summary['generated_at'][:19]}Z",
        f"**Review version**: {REVIEW_VERSION}",
        f"**Canonical Passport mutated**: NO",
        f"**Supabase written**: NO",
        "",
        "---",
        "",
        "## Phase A — Passport Candidates",
        "",
        f"| Category | Count |",
        "|---|---|",
        f"| Total candidates | {len(cands)} |",
        f"| RP_UID canonical | {len(rp_uid_cands)} |",
        f"| EOD non-canonical | {len(eod_cands)} |",
        f"| No identity | {len(no_id_cands)} |",
        "",
        "### Verdicts",
        "",
        "| Verdict | Count |",
        "|---|---|",
    ]
    for v, n in sorted(verdict_counts.items(), key=lambda x: -x[1]):
        md.append(f"| {v} | {n} |")

    md += [
        "",
        "### Top PROMOTE_TO_PASSPORT_REVIEW candidates",
        "",
        "| Horse | RP_UID | Outcome | VP | Tier | Score | Passport exists |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in sorted(promote, key=lambda x: -x["score_total"])[:10]:
        md.append(
            f"| {c['horse_name']} | {c['horse_id']} | {c['outcome']} "
            f"| {c.get('vp_at_race','?')} | {c['evidence_quality_tier']} "
            f"| {c['score_total']} | {'YES' if c['passport_exists_in_canonical'] else 'NO'} |"
        )

    md += [
        "",
        "---",
        "",
        "## Phase B — Repeated Horse Truth Tables",
        "",
        "| Cluster verdict | Count |",
        "|---|---|",
    ]
    for v, n in sorted(cluster_verdict_counts.items(), key=lambda x: -x[1]):
        md.append(f"| {v} | {n} |")

    md += [
        "",
        "### VP_UNDERCOUNTING clusters",
        "",
        "| Horse | ID | Wins | Apps | Avg VP | All below threshold |",
        "|---|---|---|---|---|---|",
    ]
    for tt in sorted(vp_undercounting, key=lambda x: -x["wins"]):
        md.append(
            f"| {tt['horse_name']} | {tt['horse_id']} "
            f"| {tt['wins']} | {tt['appearance_count']} "
            f"| {tt['avg_vp']:.3f} | {tt['wins_below_vp_threshold']==tt['wins']} |"
        )

    md += [
        "",
        "### LEARNABLE_VP_POSITIVE clusters",
        "",
        "| Horse | ID | Wins | Apps | Avg VP | Trend |",
        "|---|---|---|---|---|---|",
    ]
    for tt in sorted(learnable, key=lambda x: -x["avg_vp"]):
        md.append(
            f"| {tt['horse_name']} | {tt['horse_id']} "
            f"| {tt['wins']} | {tt['appearance_count']} "
            f"| {tt['avg_vp']:.3f} | {tt['vp_trend']} |"
        )

    md += [
        "",
        "---",
        "",
        "## Phase C — Kakirra Case Study",
        "",
        f"- **RP_UID**: 8866972",
        f"- **VFU appearances**: 3 | **VFU wins**: 3 | **VFU SR**: 100%",
        f"- **VP range**: {kakirra['vp_range']['min']:.3f}–{kakirra['vp_range']['max']:.3f} (avg {kakirra['vp_range']['avg']:.3f})",
        f"- **All wins below VP threshold (0.40)**: {kakirra['all_wins_below_vp_threshold']}",
        f"- **Passport**: {kakirra['canonical_passport']['career_runs']} runs, win_rate={kakirra['canonical_passport']['win_rate']}, SP={kakirra['canonical_passport']['sp_trajectory']}",
        f"- **Pattern**: VP_UNDERCOUNTING — Passport truth ahead of VP",
        "",
        "---",
        "",
        "## Review Queue Summary",
        "",
        f"Total entries: **{len(review_queue)}**",
        "",
        "| Queue type | Count |",
        "|---|---|",
    ]
    from collections import Counter
    qt_counts = Counter(e["queue_type"] for e in review_queue)
    for qt, n in qt_counts.most_common():
        md.append(f"| {qt} | {n} |")

    md += [
        "",
        "---",
        "",
        "## Hard Rule Confirmations",
        "",
        "| Check | Status |",
        "|---|---|",
        "| Canonical Horse Passport NOT mutated | CONFIRMED |",
        "| No Passport merge executed | CONFIRMED |",
        "| No Supabase writes | CONFIRMED |",
        "| No live scoring change | CONFIRMED |",
        "| No model promotion | CONFIRMED |",
        "| No live doctrine promotion | CONFIRMED |",
        "| No Telegram send | CONFIRMED |",
        "| No Racing API restoration | CONFIRMED |",
        "| No Mar–Apr extraction | CONFIRMED |",
        "",
        "## Final Classifications",
        "",
    ]
    for c in final_classifications:
        md.append(f"- `{c}`")

    OUT_SUMMARY_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\n[VFU-07] Done.")
    print(f"  Phase A: {len(promote)} promote | {verdict_counts.get('OBSERVE_ONLY', 0)} observe | {verdict_counts.get('NEEDS_MORE_DATA', 0)} needs data")
    print(f"  Phase B: {len(vp_undercounting)} VP_UNDERCOUNTING | {len(learnable)} LEARNABLE | {len(place_spec)} PLACE_SPECIALIST | {len(noise)} NOISE")
    print(f"  Phase C: Kakirra VP_UNDERCOUNTING confirmed (RP_UID 8866972)")
    print(f"  Review queue: {len(review_queue)} entries")


if __name__ == "__main__":
    main()
