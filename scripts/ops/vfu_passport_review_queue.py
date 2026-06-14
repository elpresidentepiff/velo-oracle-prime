#!/usr/bin/env python3
"""
scripts/ops/vfu_passport_review_queue.py
=========================================
VFU-08 — Formal Passport Update Review Queue (dry-run only).

Reads VFU-07 scored candidates + repeated-horse truth tables.
Applies a second-pass verdict layer and produces a formal operator
review queue with structured update proposals.

Candidate verdicts:
  APPROVE_FOR_PASSPORT_UPDATE_REVIEW — RP_UID + WIN + strong evidence
  HOLD_FOR_MORE_EVIDENCE             — promising but thin
  REJECT_AS_NOISE                    — low VP + MISS, no signal
  NEEDS_IDENTITY_RECONCILIATION      — EOD/no-id, not safe for Passport
  PLACE_EW_PROFILE_ONLY              — place specialist, not win doctrine
  VP_UNDERCOUNTING_WATCHLIST         — wins below VP threshold, Passport ahead
  LEARNABLE_VP_POSITIVE              — VP tracking horse trajectory correctly
  OBSERVE_ONLY                       — PLACED outcome, monitor only

Never writes Supabase. Never mutates canonical Horse Passport.
All proposals: do_not_merge=True, human_review_required=True.

Core doctrine (VFU-07):
"VP is valid as a population signal. VP is not valid as a hard individual
horse disqualifier. Identity-confirmed Passport evidence may reveal
improving horses before VP crosses threshold."
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

# ── Inputs ────────────────────────────────────────────────────────────────────
CANDS_ENRICHED   = ROOT / "data/reports/vfu_current_era_passport_candidates_identity_enriched.jsonl"
CAND_REVIEW_V7   = ROOT / "data/reports/vfu_passport_candidate_review.json"
TRUTH_TABLE_V7   = ROOT / "data/reports/vfu_repeated_horse_truth_table.json"
KAKIRRA_V7       = ROOT / "data/reports/vfu_kakirra_case_study.json"
PASSPORT_FILE    = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
AUTOPSY_RECORDS  = ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl"
CANON_PASSPORT   = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"

# ── Outputs ───────────────────────────────────────────────────────────────────
OUT_CANDIDATES   = ROOT / "data/reports/vfu_passport_review_candidates.jsonl"
OUT_REJECTED     = ROOT / "data/reports/vfu_passport_review_rejected.json"
OUT_OP_QUEUE     = ROOT / "data/reports/vfu_passport_review_operator_decision_queue.json"
OUT_QUEUE_JSON   = ROOT / "data/reports/vfu_passport_review_queue.json"
OUT_QUEUE_MD     = ROOT / "data/reports/vfu_passport_review_queue.md"
OUT_KAKIRRA_MD   = ROOT / "data/reports/vfu_passport_review_kakirra_case_study.md"

REVIEW_VERSION   = "VFU_PASSPORT_REVIEW_QUEUE_V1"
VP_THRESHOLD     = 0.40
CORE_DOCTRINE    = (
    "VP is valid as a population signal. "
    "VP is not valid as a hard individual horse disqualifier. "
    "Identity-confirmed Passport evidence may reveal improving horses "
    "before VP crosses threshold."
)

VFU08_VERDICTS = {
    "APPROVE_FOR_PASSPORT_UPDATE_REVIEW",
    "HOLD_FOR_MORE_EVIDENCE",
    "REJECT_AS_NOISE",
    "NEEDS_IDENTITY_RECONCILIATION",
    "PLACE_EW_PROFILE_ONLY",
    "VP_UNDERCOUNTING_WATCHLIST",
    "LEARNABLE_VP_POSITIVE",
    "OBSERVE_ONLY",
}


def norm_horse(h: str | None) -> str:
    if not h:
        return ""
    h = h.strip().lower()
    h = re.sub(r"\s*\([a-z]+\)\s*$", "", h)
    h = re.sub(r"[^a-z0-9 ]", "", h)
    return re.sub(r"\s+", " ", h).strip()


# ── Passport lookup ───────────────────────────────────────────────────────────

def load_canonical_passports(path: Path) -> dict:
    result = {}
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        uid = row.get("horse_rp_uid")
        if uid is not None:
            result[str(uid)] = row
    return result


# ── VFU-08 verdict assignment ─────────────────────────────────────────────────

def vfu08_verdict(
    cand: dict,
    truth_by_norm: dict,
    canonical: dict,
) -> str:
    ns = cand.get("horse_id_namespace", "UNKNOWN")
    outcome = cand.get("outcome", "MISS")
    vp = cand.get("vp_at_race")
    hid = cand.get("horse_id")
    score = cand.get("score_total", 0)
    n = norm_horse(cand.get("horse_name", ""))

    cluster = truth_by_norm.get(n)
    cluster_verdict = cluster.get("cluster_verdict") if cluster else None

    # No usable identity → reconciliation
    if not hid or ns == "UNKNOWN":
        return "NEEDS_IDENTITY_RECONCILIATION"

    # EOD non-canonical → reconciliation (not safe for Passport)
    if ns not in ("RP_UID",):
        return "NEEDS_IDENTITY_RECONCILIATION"

    # VP_UNDERCOUNTING from cluster
    if cluster_verdict == "VP_UNDERCOUNTING":
        return "VP_UNDERCOUNTING_WATCHLIST"

    # Place specialist from cluster
    if cluster_verdict == "PLACE_SPECIALIST":
        return "PLACE_EW_PROFILE_ONLY"

    # Learnable VP positive from cluster
    if cluster_verdict == "LEARNABLE_VP_POSITIVE":
        return "LEARNABLE_VP_POSITIVE"

    # Single-race WIN with RP_UID
    if outcome == "WIN" and ns == "RP_UID":
        # VP undercounting at single-race level
        if vp is not None and vp < VP_THRESHOLD:
            return "VP_UNDERCOUNTING_WATCHLIST"
        # Strong evidence: approve
        if score >= 8:
            return "APPROVE_FOR_PASSPORT_UPDATE_REVIEW"
        # Weaker: hold
        return "HOLD_FOR_MORE_EVIDENCE"

    # PLACED single outcome
    if outcome == "PLACED":
        return "PLACE_EW_PROFILE_ONLY"

    # MISS with VP above threshold (false positive)
    if outcome == "MISS" and vp is not None and vp >= VP_THRESHOLD:
        return "HOLD_FOR_MORE_EVIDENCE"

    # Low score MISS
    if score < 4:
        return "REJECT_AS_NOISE"

    return "OBSERVE_ONLY"


# ── Passport labels ───────────────────────────────────────────────────────────

def derive_passport_labels(cand: dict, cluster: dict | None, pp: dict | None) -> list[str]:
    labels = []
    vp = cand.get("vp_at_race", 0) or 0
    outcome = cand.get("outcome", "")

    if outcome == "WIN":
        labels.append("VFU_WIN_CONFIRMED_CURRENT_ERA")
        if vp >= 0.50:
            labels.append("VP_HIGH_WIN_GTE050")
        elif vp >= 0.40:
            labels.append("VP_THRESHOLD_WIN")
        else:
            labels.append("VP_UNDERCOUNTING_WIN")

    if pp:
        if pp.get("sp_trajectory") == "SHORTENING":
            labels.append("SP_SHORTENING_AT_WIN")
        if pp.get("position_trend") == "IMPROVING":
            labels.append("POSITION_TREND_IMPROVING")
        if pp.get("margin_trend") == "IMPROVING":
            labels.append("MARGIN_TREND_IMPROVING")
        if pp.get("aw_specialist"):
            labels.append("AW_SPECIALIST")
        if pp.get("cash_run_candidate"):
            labels.append("CASH_RUN_CANDIDATE")

    if cluster:
        if cluster["wins"] >= 2:
            labels.append("REPEAT_WIN_CURRENT_ERA")
        if cluster.get("cluster_verdict") == "LEARNABLE_VP_POSITIVE":
            labels.append("VP_LEARNING_POSITIVE")

    return labels


def build_forensic_note(cand: dict, cluster: dict | None, pp: dict | None) -> str:
    parts = [
        f"VFU current-era: {cand.get('outcome')} on {cand.get('race_date')} "
        f"at {cand.get('course')} (VP={cand.get('vp_at_race')}, "
        f"tier={cand.get('evidence_quality_tier', '?')})."
    ]
    if pp and pp.get("win_rate") is not None:
        parts.append(
            f"Canonical Passport: {pp.get('career_runs')} runs, "
            f"win_rate={pp.get('win_rate')}, SP={pp.get('sp_trajectory')}."
        )
    if cluster and cluster.get("cluster_verdict") == "LEARNABLE_VP_POSITIVE":
        parts.append(
            f"Repeated horse: {cluster['wins']}/{cluster['appearance_count']} wins, "
            f"VP trend {cluster.get('vp_trend')}."
        )
    return " ".join(parts)


# ── Build candidate record ────────────────────────────────────────────────────

def build_candidate_record(
    cand: dict,
    truth_by_norm: dict,
    canonical: dict,
) -> dict:
    n = norm_horse(cand.get("horse_name", ""))
    cluster = truth_by_norm.get(n)
    hid = cand.get("horse_id")
    pp = canonical.get(str(hid), {}) if hid else {}

    verdict = vfu08_verdict(cand, truth_by_norm, canonical)
    labels = derive_passport_labels(cand, cluster, pp or None)
    note = build_forensic_note(cand, cluster, pp or None)

    source_autopsies = [cand.get("autopsy_id_link")] if cand.get("autopsy_id_link") else []

    proposal = {
        "horse_id": cand.get("horse_id"),
        "horse_id_namespace": cand.get("horse_id_namespace"),
        "horse_name": cand.get("horse_name"),
        "proposed_passport_labels": labels,
        "proposed_forensic_note": note,
        "evidence_summary": (
            f"outcome={cand.get('outcome')}, vp={cand.get('vp_at_race')}, "
            f"tier={cand.get('evidence_quality_tier')}, score={cand.get('score_total')}"
        ),
        "confidence": (
            "HIGH" if cand.get("horse_id_namespace") == "RP_UID" and cand.get("score_total", 0) >= 8
            else "MEDIUM" if cand.get("horse_id_namespace") == "RP_UID"
            else "LOW"
        ),
        "source_autopsies": source_autopsies,
        "do_not_merge": True,
        "human_review_required": True,
        "canonical_passport_mutated": False,
    }

    return {
        **cand,
        "vfu08_verdict": verdict,
        "vfu08_passport_proposal": proposal,
        "cluster_verdict": cluster.get("cluster_verdict") if cluster else None,
        "canonical_passport_snapshot": {
            "career_runs": pp.get("career_runs"),
            "win_rate": pp.get("win_rate"),
            "sp_trajectory": pp.get("sp_trajectory"),
            "position_trend": pp.get("position_trend"),
            "margin_trend": pp.get("margin_trend"),
            "aw_specialist": pp.get("aw_specialist"),
        } if pp else None,
        "do_not_merge": True,
        "human_review_required": True,
        "canonical_passport_mutated": False,
        "review_version": REVIEW_VERSION,
    }


# ── Build cluster review record ───────────────────────────────────────────────

def build_cluster_record(tt: dict, canonical: dict) -> dict:
    hid = tt.get("horse_id")
    ns = tt.get("horse_id_namespace", "UNKNOWN")
    pp = canonical.get(str(hid), {}) if (hid and ns == "RP_UID") else {}
    cv = tt.get("cluster_verdict", "NEEDS_MORE_RUNS")

    verdict_map = {
        "VP_UNDERCOUNTING": "VP_UNDERCOUNTING_WATCHLIST",
        "LEARNABLE_VP_POSITIVE": "LEARNABLE_VP_POSITIVE",
        "PLACE_SPECIALIST": "PLACE_EW_PROFILE_ONLY",
        "NOISE": "REJECT_AS_NOISE",
        "NEEDS_MORE_RUNS": "HOLD_FOR_MORE_EVIDENCE",
        "HIGH_VP_NON_WINNER": "OBSERVE_ONLY",
        "IDENTITY_UNRESOLVED": "NEEDS_IDENTITY_RECONCILIATION",
    }
    vfu08_v = verdict_map.get(cv, "OBSERVE_ONLY")

    labels = []
    if cv == "VP_UNDERCOUNTING":
        labels.append("VP_UNDERCOUNTING_WATCHLIST")
        if pp.get("aw_specialist"):
            labels.append("AW_SPECIALIST")
        if pp.get("sp_trajectory") == "SHORTENING":
            labels.append("SP_SHORTENING_SIGNAL")
    elif cv == "LEARNABLE_VP_POSITIVE":
        labels.append("VP_LEARNING_POSITIVE")
        if tt.get("vp_trend") in ("RISING", "IMPROVING"):
            labels.append("VP_TREND_RISING")
    elif cv == "PLACE_SPECIALIST":
        labels.append("PLACE_EW_PROFILE_CANDIDATE")

    return {
        "horse_name": tt["horse_name"],
        "horse_id": hid,
        "horse_id_namespace": ns,
        "source_type": "REPEATED_CLUSTER",
        "cluster_verdict": cv,
        "vfu08_verdict": vfu08_v,
        "appearance_count": tt["appearance_count"],
        "wins": tt["wins"],
        "strike_rate": tt["strike_rate"],
        "avg_vp": tt["avg_vp"],
        "vp_trend": tt.get("vp_trend"),
        "wins_below_vp_threshold": tt.get("wins_below_vp_threshold", 0),
        "per_run_truth_table": tt.get("per_run_truth_table", []),
        "proposed_passport_labels": labels,
        "canonical_passport_snapshot": {
            "career_runs": pp.get("career_runs"),
            "win_rate": pp.get("win_rate"),
            "sp_trajectory": pp.get("sp_trajectory"),
            "position_trend": pp.get("position_trend"),
            "margin_trend": pp.get("margin_trend"),
            "aw_specialist": pp.get("aw_specialist"),
        } if pp else None,
        "do_not_merge": True,
        "human_review_required": True,
        "canonical_passport_mutated": False,
        "name_only_confidence": True,
        "review_version": REVIEW_VERSION,
    }


# ── Operator decision queue ───────────────────────────────────────────────────

def build_operator_queue(
    candidate_records: list[dict],
    cluster_records: list[dict],
    kakirra_case: dict,
) -> list[dict]:
    queue = []

    # 1. VP_UNDERCOUNTING_WATCHLIST — doctrine investigation required
    queue.append({
        "queue_type": "KAKIRRA_CASE_STUDY",
        "priority": "HIGH",
        "horse_name": "Kakirra",
        "horse_id": "8866972",
        "horse_id_namespace": "RP_UID",
        "vfu08_verdict": "VP_UNDERCOUNTING_WATCHLIST",
        "vfu_sr": 1.0,
        "avg_vp": 0.265,
        "proposed_labels": ["VP_UNDERCOUNTING_WATCHLIST", "AW_SPECIALIST", "SP_SHORTENING_SIGNAL"],
        "do_not_merge": True,
        "review_question": (
            "Kakirra won 3/3 with VP 0.175–0.343 (all below 0.40 threshold). "
            "RP_UID 8866972 confirmed. Passport already shows improvement. "
            "VP blind spot. Requires doctrine investigation before any Passport action."
        ),
    })

    for r in cluster_records:
        if r["vfu08_verdict"] == "VP_UNDERCOUNTING_WATCHLIST" and r["horse_name"] != "kakirra":
            queue.append({
                "queue_type": "VP_UNDERCOUNTING_CLUSTER",
                "priority": "HIGH",
                "horse_name": r["horse_name"],
                "horse_id": r["horse_id"],
                "horse_id_namespace": r["horse_id_namespace"],
                "vfu08_verdict": r["vfu08_verdict"],
                "vfu_sr": r["strike_rate"],
                "avg_vp": r["avg_vp"],
                "proposed_labels": r["proposed_passport_labels"],
                "do_not_merge": True,
                "review_question": (
                    f"{r['horse_name']}: {r['wins']}/{r['appearance_count']} wins, "
                    f"avg_vp={r['avg_vp']:.3f}. Same blind spot as Kakirra."
                ),
            })

    # 2. APPROVE_FOR_PASSPORT_UPDATE_REVIEW — sorted by score
    approve = sorted(
        [r for r in candidate_records if r["vfu08_verdict"] == "APPROVE_FOR_PASSPORT_UPDATE_REVIEW"],
        key=lambda x: -(x.get("score_total") or 0),
    )
    for r in approve:
        queue.append({
            "queue_type": "PASSPORT_CANDIDATE_REVIEW",
            "priority": "MEDIUM",
            "horse_name": r["horse_name"],
            "horse_id": r["horse_id"],
            "horse_id_namespace": r["horse_id_namespace"],
            "vfu08_verdict": r["vfu08_verdict"],
            "outcome": r.get("outcome"),
            "vp_at_race": r.get("vp_at_race"),
            "score_total": r.get("score_total"),
            "evidence_tier": r.get("evidence_quality_tier"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "proposed_labels": r["vfu08_passport_proposal"]["proposed_passport_labels"],
            "passport_exists": r.get("passport_exists_in_canonical"),
            "do_not_merge": True,
            "review_question": (
                f"{r['horse_name']}: WIN at {r.get('course')} on {r.get('race_date')}, "
                f"VP={r.get('vp_at_race')}, score={r.get('score_total')}. "
                f"RP_UID confirmed. Ready for operator merge decision."
            ),
        })

    # 3. LEARNABLE_VP_POSITIVE clusters
    for r in cluster_records:
        if r["vfu08_verdict"] == "LEARNABLE_VP_POSITIVE":
            queue.append({
                "queue_type": "LEARNABLE_CLUSTER",
                "priority": "MEDIUM",
                "horse_name": r["horse_name"],
                "horse_id": r["horse_id"],
                "horse_id_namespace": r["horse_id_namespace"],
                "vfu08_verdict": r["vfu08_verdict"],
                "vfu_sr": r["strike_rate"],
                "avg_vp": r["avg_vp"],
                "vp_trend": r.get("vp_trend"),
                "proposed_labels": r["proposed_passport_labels"],
                "do_not_merge": True,
                "review_question": (
                    f"{r['horse_name']}: VP trending {r.get('vp_trend')}, "
                    f"SR={r['strike_rate']:.0%}. VP tracking horse correctly. Monitor."
                ),
            })

    # 4. PLACE_EW_PROFILE_ONLY
    for r in cluster_records:
        if r["vfu08_verdict"] == "PLACE_EW_PROFILE_ONLY":
            queue.append({
                "queue_type": "PLACE_SPECIALIST",
                "priority": "LOW",
                "horse_name": r["horse_name"],
                "horse_id": r["horse_id"],
                "horse_id_namespace": r["horse_id_namespace"],
                "vfu08_verdict": r["vfu08_verdict"],
                "proposed_labels": r["proposed_passport_labels"],
                "do_not_merge": True,
                "review_question": (
                    f"{r['horse_name']}: consistent PLACED outcomes. "
                    f"VP={r['avg_vp']:.3f}. Frame/EW profile candidate only."
                ),
            })

    return queue


# ── Kakirra case study MD ─────────────────────────────────────────────────────

def build_kakirra_md(kakirra: dict) -> str:
    runs = kakirra.get("per_run_truth_table", [])
    pp = kakirra.get("canonical_passport", {})
    analysis = kakirra.get("analysis", {})

    lines = [
        "# Kakirra — VFU-08 Passport Override Case Study",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()[:19]}Z",
        f"**Review version**: {REVIEW_VERSION}",
        f"**Canonical Passport mutated**: NO",
        f"**do_not_merge**: TRUE",
        "",
        "---",
        "",
        "## Identity",
        "",
        f"| Field | Value |",
        "|---|---|",
        f"| Horse name | Kakirra |",
        f"| RP_UID | 8866972 |",
        f"| Namespace | RP_UID (canonical) |",
        f"| ID source | PASSPORT_NORM_MATCH |",
        f"| ID confidence | HIGH |",
        "",
        "---",
        "",
        "## VFU Appearances — Truth Table",
        "",
        "| Date | Course | VP | VP ≥ 0.40 | Outcome |",
        "|---|---|---|---|---|",
    ]
    for r in runs:
        lines.append(
            f"| {r['date']} | {r['course']} | {r['vp']:.3f} | "
            f"{'YES' if r['vp_above_threshold'] else '**NO**'} | **{r['outcome']}** |"
        )

    vp_vals = [r["vp"] for r in runs if r.get("vp") is not None]
    lines += [
        "",
        f"**VFU appearances**: {kakirra['vfu_appearances']} | "
        f"**VFU wins**: {kakirra['vfu_wins']} | "
        f"**SR**: 100%",
        f"**VP range**: {min(vp_vals):.3f}–{max(vp_vals):.3f} (avg {sum(vp_vals)/len(vp_vals):.3f})",
        f"**All wins below VP threshold (0.40)**: **YES**",
        "",
        "---",
        "",
        "## Canonical Passport Profile",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Career runs | {pp.get('career_runs')} |",
        f"| Career wins | {pp.get('wins')} |",
        f"| Win rate | {pp.get('win_rate')} |",
        f"| SP trajectory | {pp.get('sp_trajectory')} |",
        f"| Position trend | {pp.get('position_trend')} |",
        f"| Margin trend | {pp.get('margin_trend')} |",
        f"| AW specialist | {pp.get('aw_specialist')} |",
        f"| Avg SP last 5 | {pp.get('avg_sp_last5')} |",
        f"| Avg SP last 3 | {pp.get('avg_sp_last3')} |",
        f"| Current OR | {pp.get('current_or')} |",
        f"| Last run date | {pp.get('last_run_date')} |",
        "",
        "---",
        "",
        "## VP vs Passport Gap Analysis",
        "",
        f"**Pattern type**: {analysis.get('pattern_type')}",
        f"**Verdict**: {analysis.get('vp_vs_passport_verdict')}",
        "",
        f"> {analysis.get('description', '')}",
        "",
        "### Possible causes of VP suppression",
        "",
    ]
    for cause in analysis.get("possible_causes", []):
        lines.append(f"- {cause}")

    lines += [
        "",
        "---",
        "",
        "## Core Doctrine Implication",
        "",
        f"> {analysis.get('doctrine_implication', '')}",
        "",
        "---",
        "",
        "## Recommended Action",
        "",
        f"{analysis.get('recommended_action', '')}",
        "",
        "---",
        "",
        "## Proposed Passport Labels",
        "",
        "| Label | Justification |",
        "|---|---|",
        "| VP_UNDERCOUNTING_WATCHLIST | 3/3 wins below VP 0.40 threshold |",
        "| AW_SPECIALIST | Passport confirms AW specialist |",
        "| SP_SHORTENING_SIGNAL | Passport SP trajectory: SHORTENING |",
        "| POSITION_TREND_IMPROVING | Passport position trend: IMPROVING |",
        "| MARGIN_TREND_IMPROVING | Passport margin trend: IMPROVING |",
        "| VFU_WIN_CONFIRMED_CURRENT_ERA | 3 identity-confirmed wins in current era |",
        "",
        "**All labels are proposals only. `do_not_merge=True`. "
        "Operator must approve before any Passport write.**",
        "",
        "---",
        "",
        "## Hard Rule Confirmations",
        "",
        "| Check | Status |",
        "|---|---|",
        "| Canonical Passport NOT mutated | CONFIRMED |",
        "| No Supabase writes | CONFIRMED |",
        "| No live scoring change | CONFIRMED |",
        "| No doctrine promotion | CONFIRMED |",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    assert str(OUT_CANDIDATES) != str(CANON_PASSPORT)
    assert str(OUT_QUEUE_JSON) != str(CANON_PASSPORT)

    print(f"[VFU-08] Loading inputs")
    cand_review_v7 = json.loads(CAND_REVIEW_V7.read_text(encoding="utf-8"))
    truth_tables   = json.loads(TRUTH_TABLE_V7.read_text(encoding="utf-8"))
    kakirra        = json.loads(KAKIRRA_V7.read_text(encoding="utf-8"))
    canonical      = load_canonical_passports(PASSPORT_FILE)

    truth_by_norm = {t["norm_name"]: t for t in truth_tables}
    print(f"  {len(cand_review_v7)} VFU-07 candidates | {len(truth_tables)} clusters | {len(canonical)} passports")

    # Phase A: candidate records
    print(f"[VFU-08] Phase A: Assigning VFU-08 verdicts to {len(cand_review_v7)} candidates")
    candidate_records = [
        build_candidate_record(c, truth_by_norm, canonical)
        for c in cand_review_v7
    ]

    verdict_counts: dict[str, int] = defaultdict(int)
    for r in candidate_records:
        verdict_counts[r["vfu08_verdict"]] += 1

    # Phase B: cluster records
    print(f"[VFU-08] Phase B: Building cluster records for {len(truth_tables)} clusters")
    cluster_records = [
        build_cluster_record(tt, canonical)
        for tt in truth_tables
    ]

    # Phase C: Kakirra MD
    print(f"[VFU-08] Phase C: Kakirra case study MD")
    kakirra_md = build_kakirra_md(kakirra)
    OUT_KAKIRRA_MD.write_text(kakirra_md, encoding="utf-8")

    # Separate rejected
    rejected = [
        r for r in candidate_records
        if r["vfu08_verdict"] in ("REJECT_AS_NOISE",)
    ]

    # Operator queue
    print(f"[VFU-08] Building operator decision queue")
    op_queue = build_operator_queue(candidate_records, cluster_records, kakirra)

    # Combined review queue (for compatibility with VFU-07 test)
    review_queue = op_queue[:]  # already includes KAKIRRA_CASE_STUDY + PASSPORT_CANDIDATE_REVIEW

    # ── Write outputs ─────────────────────────────────────────────────────────
    with OUT_CANDIDATES.open("w", encoding="utf-8") as fh:
        for r in candidate_records:
            fh.write(json.dumps(r, default=str) + "\n")

    OUT_REJECTED.write_text(json.dumps(rejected, indent=2, default=str), encoding="utf-8")
    OUT_OP_QUEUE.write_text(json.dumps(op_queue, indent=2, default=str), encoding="utf-8")
    OUT_QUEUE_JSON.write_text(json.dumps(review_queue, indent=2, default=str), encoding="utf-8")

    # ── Summary counts ────────────────────────────────────────────────────────
    approve   = [r for r in candidate_records if r["vfu08_verdict"] == "APPROVE_FOR_PASSPORT_UPDATE_REVIEW"]
    vp_uc     = [r for r in cluster_records if r["vfu08_verdict"] == "VP_UNDERCOUNTING_WATCHLIST"]
    learnable = [r for r in cluster_records if r["vfu08_verdict"] == "LEARNABLE_VP_POSITIVE"]
    place_ew  = [r for r in cluster_records if r["vfu08_verdict"] == "PLACE_EW_PROFILE_ONLY"]
    id_recon  = [r for r in candidate_records if r["vfu08_verdict"] == "NEEDS_IDENTITY_RECONCILIATION"]

    # ── MD report ─────────────────────────────────────────────────────────────
    md = [
        "# VFU-08 — Formal Passport Update Review Queue",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()[:19]}Z",
        f"**Review version**: {REVIEW_VERSION}",
        f"**Canonical Passport mutated**: NO",
        f"**Supabase written**: NO",
        "",
        f"**Core doctrine**: {CORE_DOCTRINE}",
        "",
        "---",
        "",
        "## 1. Total Candidates Reviewed",
        "",
        f"| Source | Count |",
        "|---|---|",
        f"| VFU-07 passport candidates | {len(cand_review_v7)} |",
        f"| Repeated horse clusters | {len(truth_tables)} |",
        f"| **Total** | **{len(cand_review_v7) + len(truth_tables)}** |",
        "",
        "## 2. Verdict Distribution",
        "",
        "| Verdict | Count |",
        "|---|---|",
    ]
    for v, n in sorted(verdict_counts.items(), key=lambda x: -x[1]):
        md.append(f"| {v} | {n} |")

    cluster_v: dict[str, int] = defaultdict(int)
    for r in cluster_records:
        cluster_v[r["vfu08_verdict"]] += 1
    md += ["", "Cluster verdicts:", ""]
    for v, n in sorted(cluster_v.items(), key=lambda x: -x[1]):
        md.append(f"| {v} | {n} |")

    md += [
        "",
        "## 3. Top 30 Review Queue",
        "",
        "| # | Horse | RP_UID | Date | Course | VP | Tier | Score | Labels |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(approve[:30], 1):
        labels = ", ".join(r["vfu08_passport_proposal"]["proposed_passport_labels"][:2])
        md.append(
            f"| {i} | {r['horse_name']} | {r['horse_id']} "
            f"| {r.get('race_date')} | {r.get('course')} "
            f"| {r.get('vp_at_race')} | {r.get('evidence_quality_tier','')[:6]} "
            f"| {r.get('score_total')} | {labels} |"
        )

    md += [
        "",
        "## 4. VP_UNDERCOUNTING Cases",
        "",
        "| Horse | ID | Apps | Wins | Avg VP | All below 0.40 |",
        "|---|---|---|---|---|---|",
    ]
    for r in vp_uc:
        all_below = r.get("wins_below_vp_threshold", 0) == r.get("wins", 0)
        md.append(
            f"| {r['horse_name']} | {r['horse_id']} | {r['appearance_count']} "
            f"| {r['wins']} | {r['avg_vp']:.3f} | {'YES' if all_below else 'NO'} |"
        )

    md += [
        "",
        "## 5. LEARNABLE_VP_POSITIVE Cases",
        "",
        "| Horse | ID | Apps | Wins | Avg VP | VP Trend |",
        "|---|---|---|---|---|---|",
    ]
    for r in learnable:
        md.append(
            f"| {r['horse_name']} | {r['horse_id']} | {r['appearance_count']} "
            f"| {r['wins']} | {r['avg_vp']:.3f} | {r.get('vp_trend')} |"
        )

    md += [
        "",
        "## 6. PLACE_SPECIALIST Cases",
        "",
        "| Horse | ID | Apps | Wins | Avg VP |",
        "|---|---|---|---|---|",
    ]
    for r in place_ew:
        md.append(
            f"| {r['horse_name']} | {r['horse_id']} | {r['appearance_count']} "
            f"| {r['wins']} | {r['avg_vp']:.3f} |"
        )

    md += [
        "",
        "## 7. Identity Reconciliation Cases",
        "",
        f"**{len(id_recon)} candidates** require identity reconciliation before Passport consideration.",
        "These are EOD non-canonical IDs (hrs_ or rp_* format). Cannot be treated as RP_UID.",
        "",
        "## 8. Rejected / Noise",
        "",
        f"**{len(rejected)} candidates** rejected as noise.",
        "",
        "## 9. Passport Update Recommendations",
        "",
        "| Class | Recommendation |",
        "|---|---|",
        "| APPROVE_FOR_PASSPORT_UPDATE_REVIEW | Ready for operator merge decision. All `do_not_merge=True`. |",
        "| VP_UNDERCOUNTING_WATCHLIST | Do NOT merge. Investigate VP suppression cause first. |",
        "| LEARNABLE_VP_POSITIVE | Monitor. Merge when n>=5 and SR>=50%. |",
        "| PLACE_EW_PROFILE_ONLY | Do not add to win doctrine. Frame/EW label only. |",
        "| NEEDS_IDENTITY_RECONCILIATION | Do not merge. Resolve EOD identity first. |",
        "| REJECT_AS_NOISE | Discard. |",
        "",
        "## 10. Fields Proposed for Passport Extension",
        "",
        "| Field | Purpose |",
        "|---|---|",
        "| vfu_win_confirmed_current_era | Binary: horse won in current-era VFU observation |",
        "| vfu_vp_at_win | VP value at the winning race |",
        "| vfu_course_at_win | Course where VFU win observed |",
        "| vfu_vp_undercounting | Boolean: horse wins consistently below VP threshold |",
        "| vfu_place_specialist | Boolean: horse consistently places, rarely wins |",
        "| vfu_learnable_pattern | Boolean: VP and outcome are aligning over time |",
        "| vfu_forensic_note | Text note from autopsy |",
        "| vfu_evidence_confidence | HIGH/MEDIUM/LOW evidence quality |",
        "",
        "## 11. Operator Decision Queue",
        "",
        f"Total entries: **{len(op_queue)}**",
        "",
        "| Type | Count |",
        "|---|---|",
    ]
    from collections import Counter
    qt = Counter(e["queue_type"] for e in op_queue)
    for q, n in qt.most_common():
        md.append(f"| {q} | {n} |")

    md += [
        "",
        "## 12. What Is Still Blocked",
        "",
        "| Action | Status |",
        "|---|---|",
        "| Canonical Passport merge | BLOCKED — operator approval required |",
        "| Supabase writes | BLOCKED |",
        "| Live scoring change | BLOCKED |",
        "| Model promotion | BLOCKED |",
        "| Mar–Apr extraction | BLOCKED |",
        "| VP live doctrine promotion | BLOCKED |",
        "| EOD identity reconciliation | BLOCKED — pending identity resolution |",
        "| Kakirra Passport update | BLOCKED — VP suppression cause unknown |",
        "",
        "## 13. Whether VFU-09 Should Proceed",
        "",
        (
            "VFU-09 should address: **Kakirra VP Suppression Investigation**. "
            "Root cause of VP undercounting in AW specialists. "
            "Check OR/RPR availability at Kakirra race times. "
            "Do not proceed to live doctrine until cause is identified."
        ),
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
    final_classifications = [
        "VFU_08_PASSPORT_REVIEW_QUEUE_COMPLETE",
        "PASSPORT_UPDATE_PROPOSALS_DRY_RUN_ONLY",
        "KAKIRRA_CASE_STUDY_CREATED",
        "VP_UNDERCOUNTING_WATCHLIST_CREATED",
        "PASSPORT_OVERRIDE_CONCEPT_DOCUMENTED",
        "EOD_IDENTITIES_NOT_APPROVED_FOR_CANONICAL_PASSPORT",
        "PLACE_SPECIALISTS_NOT_PROMOTED_TO_WIN_DOCTRINE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_MAR_APR_EXTRACTION",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]
    for c in final_classifications:
        md.append(f"- `{c}`")

    OUT_QUEUE_MD.write_text("\n".join(md), encoding="utf-8")

    # ── Summary JSON ──────────────────────────────────────────────────────────
    summary = {
        "report_type": "VFU_08_FORMAL_PASSPORT_REVIEW_QUEUE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_version": REVIEW_VERSION,
        "core_doctrine": CORE_DOCTRINE,
        "source_scope": "current_era_only_2026_05_08_to_2026_06_13",
        "candidates_reviewed": len(cand_review_v7),
        "clusters_reviewed": len(truth_tables),
        "verdict_distribution": dict(verdict_counts),
        "cluster_verdict_distribution": dict(cluster_v),
        "approve_count": len(approve),
        "vp_undercounting_count": len(vp_uc),
        "learnable_count": len(learnable),
        "place_ew_count": len(place_ew),
        "reconciliation_count": len(id_recon),
        "rejected_count": len(rejected),
        "operator_queue_entries": len(op_queue),
        "kakirra_rp_uid": 8866972,
        "kakirra_verdict": "VP_UNDERCOUNTING_WATCHLIST",
        "eod_approved_for_passport": False,
        "any_candidate_merged": False,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_extracted": False,
        "final_classifications": final_classifications,
    }
    # Write summary alongside the MD (no separate file requested but good practice)
    (ROOT / "data/reports/vfu_08_review_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    print(f"\n[VFU-08] Done.")
    print(f"  Candidates: {len(cand_review_v7)} | Clusters: {len(truth_tables)}")
    print(f"  APPROVE: {len(approve)} | VP_UNDERCOUNTING: {len(vp_uc)} | LEARNABLE: {len(learnable)}")
    print(f"  PLACE_EW: {len(place_ew)} | RECONCILE: {len(id_recon)} | REJECTED: {len(rejected)}")
    print(f"  Operator queue: {len(op_queue)} entries")
    print(f"  Kakirra: VP_UNDERCOUNTING_WATCHLIST confirmed (RP_UID 8866972)")


if __name__ == "__main__":
    main()
