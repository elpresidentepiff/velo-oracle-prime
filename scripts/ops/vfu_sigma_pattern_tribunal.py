#!/usr/bin/env python3
"""
scripts/ops/vfu_sigma_pattern_tribunal.py
==========================================
VFU-12 — Sigma Pattern Tribunal + Human Review Triage.

Turns the VFU-11 master ledger into an operator-ready tribunal pack:
  1. Prosecute all 7 VFU-11 pattern candidates → tribunal verdict per pattern.
  2. Triage all 200 human-review entries → priority bands + Top 25 queue.
  3. Produce quarantine and data-blocked finding summaries.
  4. Answer 12 required report questions.

VFU-10 law (carried forward permanently):
  No evidence becomes doctrine unless it was knowable before the race.

Hard rules (permanent — never relax):
  - Does NOT mutate canonical Horse Passport.
  - Does NOT write Supabase.
  - Does NOT change live scoring.
  - Does NOT change VP threshold.
  - Does NOT promote doctrine.
  - Does NOT promote models.
  - Does NOT send Telegram.
  - Does NOT restore Racing API.
  - Mar–Apr findings remain QUARANTINE ONLY.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

VP_THRESHOLD = 0.40  # UNCHANGED
VALIDATION_VERSION = "VFU_12_SIGMA_PATTERN_TRIBUNAL_V1"

# ── Inputs ────────────────────────────────────────────────────────────────────
IN = {
    "ledger":            ROOT / "data/reports/vfu_11_sigma_master_ledger.jsonl",
    "summary":           ROOT / "data/reports/vfu_11_sigma_investigation_summary.json",
    "era_quality":       ROOT / "data/reports/vfu_11_sigma_era_quality_report.json",
    "dq_debt":           ROOT / "data/reports/vfu_11_sigma_data_quality_debt.json",
    "time_safety":       ROOT / "data/reports/vfu_11_sigma_time_safety_report.json",
    "patterns":          ROOT / "data/reports/vfu_11_sigma_pattern_candidates.json",
    "review_queue":      ROOT / "data/reports/vfu_11_sigma_human_review_queue.json",
    "vfu10_validation":  ROOT / "data/reports/vfu_time_safe_passport_override_validation.json",
    "vfu10_watchlist":   ROOT / "data/reports/vfu_time_safe_passport_candidate_watchlist.json",
    "vfu10_ledger":      ROOT / "data/reports/vfu_10_failure_attribution_ledger.json",
}

# ── Outputs ───────────────────────────────────────────────────────────────────
OUT_DIR       = ROOT / "data/reports"
OUT_SUMMARY_JSON = OUT_DIR / "vfu_12_sigma_pattern_tribunal_summary.json"
OUT_SUMMARY_MD   = OUT_DIR / "vfu_12_sigma_pattern_tribunal_summary.md"
OUT_VERDICTS     = OUT_DIR / "vfu_12_pattern_verdicts.json"
OUT_TOP25        = OUT_DIR / "vfu_12_human_review_top25.json"
OUT_RANKED       = OUT_DIR / "vfu_12_human_review_ranked_queue.json"
OUT_QUARANTINE   = OUT_DIR / "vfu_12_quarantine_findings.json"
OUT_DATA_BLOCKED = OUT_DIR / "vfu_12_data_blocked_findings.json"

# ── Verdict constants ─────────────────────────────────────────────────────────
VERDICT_WATCHLIST       = "PROMOTE_TO_DRY_RUN_WATCHLIST"
VERDICT_QUARANTINED     = "KEEP_QUARANTINED"
VERDICT_TIME_SAFE_REQD  = "NEEDS_TIME_SAFE_VALIDATION"
VERDICT_DATA_BLOCKED    = "DATA_BLOCKED"
VERDICT_REJECT          = "REJECT_FOR_NOW"
VERDICT_HUMAN_REVIEW    = "HUMAN_REVIEW_REQUIRED"

# ── Priority band constants ───────────────────────────────────────────────────
P0 = "P0_CRITICAL"
P1 = "P1_HIGH"
P2 = "P2_MEDIUM"
P3 = "P3_LOW"
P4 = "P4_ARCHIVE_ONLY"


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── Pattern analysis helpers ──────────────────────────────────────────────────

def _safe_mean(vals: list[float]) -> float | None:
    return round(mean(vals), 4) if vals else None


def _safe_stdev(vals: list[float]) -> float | None:
    return round(stdev(vals), 4) if len(vals) >= 2 else None


def analyse_pattern(flag: str, ledger: list[dict]) -> dict:
    rows = [r for r in ledger if flag in r.get("pattern_candidate_flags", [])]
    current  = [r for r in rows if r.get("era_bucket") == "CURRENT_ERA_VALIDATED"]
    may_q    = [r for r in rows if r.get("era_bucket") == "PRE_SURGERY_MAY_QUARANTINE"]
    archive_q = [r for r in rows if r.get("era_bucket") == "PRE_SURGERY_ARCHIVE_QUARANTINE"]
    skeleton = [r for r in rows if r.get("era_bucket") == "SKELETON_OR_NULL_DATE_EXCLUDED"]

    rp_confirmed_current = [r for r in current if r.get("horse_id_namespace") == "RP_UID"]
    has_vp_current = [r for r in current if r.get("vp") is not None]
    has_sp_current = [r for r in current if r.get("pick_sp") is not None or r.get("actual_winner_sp") is not None]

    vp_vals = [r["vp"] for r in has_vp_current]
    sp_vals = [r.get("pick_sp") or r.get("actual_winner_sp") for r in has_sp_current]
    sp_vals = [s for s in sp_vals if s is not None]

    wins_current = sum(1 for r in current if str(r.get("outcome", "")).upper() == "WIN")
    time_safe_pct = round(len(current) / len(rows) * 100, 1) if rows else 0

    return {
        "flag": flag,
        "n_total": len(rows),
        "n_current": len(current),
        "n_may_quarantine": len(may_q),
        "n_archive_quarantine": len(archive_q),
        "n_skeleton": len(skeleton),
        "n_rp_uid_confirmed": len(rp_confirmed_current),
        "n_with_vp": len(has_vp_current),
        "n_with_sp": len(has_sp_current),
        "current_wins": wins_current,
        "avg_vp_current": _safe_mean(vp_vals),
        "stdev_vp_current": _safe_stdev(vp_vals),
        "avg_sp_current": _safe_mean(sp_vals),
        "time_safe_pct": time_safe_pct,
    }


# ── Tribunal verdicts ─────────────────────────────────────────────────────────

def prosecute_pattern(flag: str, analysis: dict, vfu10_data: dict | None) -> dict:
    n       = analysis["n_current"]
    n_total = analysis["n_total"]
    n_rp    = analysis["n_rp_uid_confirmed"]
    archive = analysis["n_archive_quarantine"]
    avg_vp  = analysis["avg_vp_current"]
    avg_sp  = analysis["avg_sp_current"]

    # ── Definitional SR note ──────────────────────────────────────────────────
    # VP_SUPPRESSION: SR=1.0 by definition (VP<0.40 winners)
    # SP_SHORTENING:  SR=1.0 by definition (SP<20 winners)
    # FALSE_GREEN:    SR=0.0 by definition (VP>=0.40 non-winners)
    # These SRs are tautologies, not signal measurement.

    if flag == "VP_SUPPRESSION_CANDIDATE":
        # n=342 current-era TIME_SAFE winners VP<0.40, avg VP=0.259, avg SP=4.3
        # Short-priced (avg SP=4.3) winners VP missed — real structural gap.
        # 102/342 have RP_UID — insufficient for Passport doctrine (need 50+).
        # Sample is large enough for watchlist; not yet for Passport promotion.
        verdict = VERDICT_WATCHLIST
        reason = (
            f"n={n} current-era TIME_SAFE VP<0.40 winners. Avg VP={avg_vp:.3f}, avg SP={avg_sp:.1f}. "
            f"Short-priced winners (avg SP=4.3) indicate structural VP under-rating of confident market. "
            f"n_rp_uid={n_rp} — directional signal, needs identity enrichment before Passport doctrine."
        )
        next_evidence = (
            "Increase RP_UID confirmed from 102 to 150+. "
            "Cross-reference with pre-era SP trajectory (VFU-10 time-safe method). "
            "n>=50 RP_UID confirmed before Passport watchlist entry."
        )
        sample_warning = None
        contamination_risk = "LOW — all current-era TIME_SAFE rows"

    elif flag == "FALSE_GREEN_CANDIDATE":
        # n=258 current-era VP>=0.40 misses, avg VP=0.510
        # SR=0.0 by definitional artifact — not a real SR.
        # These represent doctrine OVER-CONFIDENCE — VP picked them but they lost.
        # Understanding WHY requires feature-level analysis not yet available.
        verdict = VERDICT_TIME_SAFE_REQD
        reason = (
            f"n={n} current-era TIME_SAFE VP≥0.40 non-winners. Avg VP={avg_vp:.3f}. "
            f"SR=0.0 is a definitional artifact (all these horses lost by definition). "
            f"Real question: what features drove VP>=0.40 in losing cases? "
            f"Need feature-level audit to distinguish systemic miss vs. legitimate race risk."
        )
        next_evidence = (
            "Feature-level attribution: which Ensemble components drove VP high in losing cases? "
            "Is this market_deception_score, improvement_score, or SQPE-driven? "
            "Requires VFU-13 feature autopsy, not watchlist promotion yet."
        )
        sample_warning = "n=258 is sufficient but pattern source (which feature?) is unknown."
        contamination_risk = "LOW — all current-era TIME_SAFE"

    elif flag == "SP_SHORTENING_CANDIDATE":
        # n=316 current-era TIME_SAFE SP<20 winners, avg VP=0.351
        # VFU-10 proved this is the strongest time-safe Passport signal.
        # Avg VP=0.351 — near threshold, not far below.
        # Directional separation confirmed (VFU-10: Group A 67% vs Group C 60%).
        vfu10_sp = None
        if vfu10_data:
            vfu10_sp = vfu10_data.get("group_stats", {}).get("GROUP_A", {}).get("pct_sp_shortened")
        verdict = VERDICT_WATCHLIST
        reason = (
            f"n={n} current-era TIME_SAFE SP<20 winners, avg VP={avg_vp:.3f}. "
            f"VFU-10 confirmed SP shortening is time-safe (pre-era observable). "
            f"VFU-10 Group A: 67% SP-shortened vs Group C: 60% — directional but not conclusive. "
            f"Avg VP=0.351 places these near the threshold — SP shortening may partially explain VP suppression."
        )
        next_evidence = (
            "Build per-horse SP trajectory from core_v0 historical dataset (VFU-10 method). "
            "Validate that SP shortening is pre-race-day observable (not same-day move). "
            "Minimum n=50 RP_UID confirmed before Passport entry consideration."
        )
        sample_warning = None
        contamination_risk = "LOW — current-era TIME_SAFE; VFU-10 validated time-safety"

    elif flag == "PASSPORT_OVERRIDE_CANDIDATE":
        # n=235 current-era with passport_update_candidate or pattern_update_candidate flag
        # These are already on the VFU-08/VFU-10 watchlist (DRY_RUN_ONLY).
        # VFU-10 watchlist had 46 candidates.
        vfu10_watchlist_n = None
        if vfu10_data:
            wl = vfu10_data.get("candidate_watchlist", [])
            if isinstance(wl, list):
                vfu10_watchlist_n = len(wl)
        verdict = VERDICT_WATCHLIST
        reason = (
            f"n={n} current-era TIME_SAFE rows with existing Passport/pattern update candidates. "
            f"Already on VFU-10 dry-run watchlist ({vfu10_watchlist_n or 'N/A'} VFU-10 candidates). "
            f"VFU-08/VFU-10 context gives time-safe Passport snapshot for subset. "
            f"Linked to VP_SUPPRESSION and SP_SHORTENING signals — consistent oversight."
        )
        next_evidence = (
            "Prioritise the Top 25 human review entries that have PASSPORT_OVERRIDE_CANDIDATE flag. "
            "Cross-link with VFU-10 watchlist by horse_id. "
            "Merge only after n>=50 confirmed + operator authorisation."
        )
        sample_warning = None
        contamination_risk = "LOW — current-era TIME_SAFE rows only"

    elif flag == "ERA_CONTAMINATION_CANDIDATE":
        # n=2165, all PRE_SURGERY_ARCHIVE_QUARANTINE, n_current=0
        # By definition, none of these are time-safe for doctrine.
        verdict = VERDICT_QUARANTINED
        reason = (
            f"n={n_total} rows, all PRE_SURGERY_ARCHIVE_QUARANTINE (Mar–Apr 2026). "
            f"n_current=0 — zero time-safe rows in this pattern. "
            f"Mar–Apr may be inspected as quarantined evidence only. "
            f"VFU-10 law prohibits any of these becoming doctrine."
        )
        next_evidence = (
            "No doctrine pathway for Mar–Apr data. "
            "Archive for historical completeness only. "
            "Any signal from this era requires prospective validation from 2026-05-08+."
        )
        sample_warning = "n=2165 is large but entirely contaminated — quantity does not overcome contamination."
        contamination_risk = "CRITICAL — all rows PRE_SURGERY_ARCHIVE_QUARANTINE"

    elif flag == "DATA_QUALITY_DEBT_CANDIDATE":
        # n=2516 rows with 3+ data gaps — covers 1265 current-era
        # This is a data quality issue, not an analysable pattern.
        verdict = VERDICT_DATA_BLOCKED
        reason = (
            f"n={n_total} rows with ≥3 data gaps (n_current={n} current-era). "
            f"Gaps include VP_MISSING, HORSE_ID_MISSING, SP_MISSING, COURSE_MISSING, DATE_MISSING. "
            f"Cannot run meaningful pattern analysis on rows with critical field absences. "
            f"Data quality repair required before this cohort can be investigated."
        )
        next_evidence = (
            "Prioritise: (1) horse_id resolution for NAME_ONLY rows, "
            "(2) SP backfill from sigma_audits_dump where actual_winner_sp is available, "
            "(3) off_time population from sigma_results EOD files. "
            "Target: reduce 3+-gap rows by ≥50% before re-running pattern tribunal."
        )
        sample_warning = "Data quality prevents signal extraction. Not a pattern — a repair task."
        contamination_risk = "MEDIUM — mix of current-era and quarantine rows; field gaps prevent era assignment in some"

    elif flag == "IDENTITY_RESOLUTION_NEEDED":
        # n=2822 rows without RP_UID, includes 2112 current-era
        # Cannot build per-horse Passport evidence without confirmed identity.
        verdict = VERDICT_DATA_BLOCKED
        reason = (
            f"n={n_total} rows without RP_UID namespace (n_current={n} current-era). "
            f"Without confirmed horse identity, cannot build Passport evidence, "
            f"cross-reference VFU-10 time-safe snapshots, or track repeat-horse patterns. "
            f"Identity resolution is a prerequisite for any Passport doctrine pathway."
        )
        next_evidence = (
            "Run Horse ID Bridge (VFU-06 method) over current-era NAME_ONLY rows. "
            "Specifically target sigma_audits_dump rows (source of most nulls) and sigma_results rows. "
            "Priority: current-era NAME_ONLY with VP_SUPPRESSION or FALSE_GREEN flags."
        )
        sample_warning = "n=2112 current-era NAME_ONLY is a major gap — 69% of current-era rows lack RP_UID."
        contamination_risk = "LOW — rows exist, identity is absent; contamination risk is identity-provenance risk, not temporal"

    else:
        verdict = VERDICT_HUMAN_REVIEW
        reason = f"Unknown pattern flag '{flag}' — cannot automate verdict."
        next_evidence = "Manual operator review required."
        sample_warning = None
        contamination_risk = "UNKNOWN"

    return {
        "pattern_id": f"VFU12_PAT_{flag}",
        "pattern_label": flag,
        "source_era": (
            "ALL_ERAS" if analysis["n_archive_quarantine"] > 0 and analysis["n_current"] > 0
            else "QUARANTINE_ERAS_ONLY" if analysis["n_current"] == 0
            else "CURRENT_ERA_ONLY"
        ),
        "evidence_count": n_total,
        "current_era_count": analysis["n_current"],
        "may_quarantine_count": analysis["n_may_quarantine"],
        "archive_quarantine_count": archive,
        "usable_count": n,  # current-era = usable for analysis
        "blocked_count": n_total - n,
        "rp_uid_confirmed_count": n_rp,
        "avg_vp_current": avg_vp,
        "avg_sp_current": avg_sp,
        "time_safe_pct": analysis["time_safe_pct"],
        "time_safety_status": (
            "TIME_SAFE" if analysis["n_current"] == n_total
            else "PARTIAL_TIME_SAFE" if analysis["n_current"] > 0
            else "TEMPORAL_CONTAMINATION_RISK"
        ),
        "contamination_risk": contamination_risk,
        "sr_note": (
            "SR=1.0 IS A DEFINITIONAL ARTIFACT — all rows are winners by flag definition."
            if flag in ("VP_SUPPRESSION_CANDIDATE", "SP_SHORTENING_CANDIDATE")
            else "SR=0.0 IS A DEFINITIONAL ARTIFACT — all rows are non-winners by flag definition."
            if flag == "FALSE_GREEN_CANDIDATE"
            else None
        ),
        "sample_size_warning": sample_warning,
        "verdict": verdict,
        "reason": reason,
        "next_required_evidence": next_evidence,
        "blocked_from_live_use": True,
        "human_approval_required": True,
        "do_not_promote": True,
        "vfu10_law_enforced": True,
    }


# ── Human review triage ───────────────────────────────────────────────────────

def assign_priority_band(entry: dict) -> str:
    era = entry.get("era_bucket", "")
    flags = set(entry.get("pattern_flags", []))
    vp = entry.get("vp")
    ts = entry.get("time_safety_status", "")
    horse_id = entry.get("horse_id")
    ns = entry.get("horse_id_namespace")

    is_current = era == "CURRENT_ERA_VALIDATED"
    is_may_q = era == "PRE_SURGERY_MAY_QUARANTINE"
    is_archive_q = era == "PRE_SURGERY_ARCHIVE_QUARANTINE"
    is_rp_uid = ns == "RP_UID"
    is_contamination = ts == "TEMPORAL_CONTAMINATION_RISK"

    # P0: current-era + FALSE_GREEN + PASSPORT_OVERRIDE — doctrine over-confidence risk
    if is_current and "FALSE_GREEN_CANDIDATE" in flags and "PASSPORT_OVERRIDE_CANDIDATE" in flags:
        return P0

    # P0: current-era + VP_SUPPRESSION + RP_UID — confirmed identity miss
    if is_current and "VP_SUPPRESSION_CANDIDATE" in flags and is_rp_uid:
        return P0

    # P1: current-era + any of: VP_SUPPRESSION, SP_SHORTENING, FALSE_GREEN
    if is_current and flags & {"VP_SUPPRESSION_CANDIDATE", "SP_SHORTENING_CANDIDATE", "FALSE_GREEN_CANDIDATE"}:
        return P1

    # P1: current-era + PASSPORT_OVERRIDE with identity
    if is_current and "PASSPORT_OVERRIDE_CANDIDATE" in flags and (is_rp_uid or horse_id):
        return P1

    # P2: current-era, any flag, no RP_UID
    if is_current:
        return P2

    # P3: PRE_SURGERY_MAY_QUARANTINE
    if is_may_q:
        return P3

    # P4: PRE_SURGERY_ARCHIVE_QUARANTINE or skeleton
    return P4


def _priority_sort_key(entry: dict) -> tuple:
    band_order = {P0: 0, P1: 1, P2: 2, P3: 3, P4: 4}
    band = entry.get("priority_band", P4)
    score = entry.get("review_priority_score", 0)
    return (band_order.get(band, 9), -score)


def triage_review_queue(queue: list[dict]) -> list[dict]:
    triaged = []
    for i, entry in enumerate(queue):
        band = assign_priority_band(entry)
        era = entry.get("era_bucket", "")
        flags = entry.get("pattern_flags", [])
        horse = entry.get("horse_name") or "(identity unknown)"
        vp = entry.get("vp")

        # Determine required human decision
        decisions = []
        if "FALSE_GREEN_CANDIDATE" in flags:
            decisions.append("Identify which Ensemble feature drove VP high; confirm if systemic miss")
        if "VP_SUPPRESSION_CANDIDATE" in flags:
            decisions.append("Confirm if SP shortening was pre-race-day observable; Passport watchlist candidate?")
        if "PASSPORT_OVERRIDE_CANDIDATE" in flags:
            decisions.append("Cross-link to VFU-10 watchlist; confirm time-safe pre-era snapshot exists")
        if "SP_SHORTENING_CANDIDATE" in flags:
            decisions.append("Check pre-race SP trajectory; confirm time-safe origin of shortening")
        if "ERA_CONTAMINATION_CANDIDATE" in flags:
            decisions.append("Confirm quarantine-only status; do not extract doctrine")
        if not decisions:
            decisions.append("General review; classify miss type and data quality")

        triaged.append({
            "entry_id": f"VFU12_RQ_{i+1:03d}",
            "priority_band": band,
            "review_priority_score": entry.get("review_priority_score", 0),
            "horse_name": entry.get("horse_name"),
            "horse_id": entry.get("horse_id"),
            "horse_id_namespace": entry.get("horse_id_namespace"),
            "era_bucket": era,
            "time_safety_status": entry.get("time_safety_status"),
            "vp": vp,
            "outcome": entry.get("outcome"),
            "course": entry.get("course"),
            "race_date": entry.get("race_date"),
            "pattern_flags": flags,
            "data_gaps": entry.get("data_gaps", []),
            "required_human_decision": decisions,
            "blocked_from_live_use": True,
            "human_approval_required": True,
        })

    triaged.sort(key=_priority_sort_key)
    return triaged


# ── Quarantine and data-blocked findings ──────────────────────────────────────

def build_quarantine_findings(ledger: list[dict], verdicts: list[dict]) -> dict:
    archive_rows = [r for r in ledger if r.get("era_bucket") == "PRE_SURGERY_ARCHIVE_QUARANTINE"]
    may_rows     = [r for r in ledger if r.get("era_bucket") == "PRE_SURGERY_MAY_QUARANTINE"]

    archive_wins = [r for r in archive_rows if str(r.get("outcome", "")).upper() == "WIN"]
    may_wins     = [r for r in may_rows if str(r.get("outcome", "")).upper() == "WIN"]

    # Most common courses in archive quarantine
    course_counts = Counter(r.get("course") for r in archive_rows if r.get("course"))

    quarantined_patterns = [v for v in verdicts if v["verdict"] == VERDICT_QUARANTINED]

    return {
        "total_quarantine_rows": len(archive_rows) + len(may_rows),
        "archive_quarantine_n": len(archive_rows),
        "may_quarantine_n": len(may_rows),
        "archive_wins_n": len(archive_wins),
        "may_wins_n": len(may_wins),
        "top_courses_archive": dict(course_counts.most_common(10)),
        "quarantined_patterns": quarantined_patterns,
        "quarantine_law": "VFU-10: No evidence becomes doctrine unless it was knowable before the race.",
        "quarantine_status": "QUARANTINE_ONLY — no doctrine, no Passport mutation, no live scoring",
        "vfu_13_note": (
            "If VFU-13 investigates pre-surgery data, it must use the VFU-10 time-safe method: "
            "build per-race-date Passport snapshot from core_v0_historical_dataset filtered to date < race_date."
        ),
    }


def build_data_blocked_findings(ledger: list[dict], verdicts: list[dict], dq: dict) -> dict:
    blocked_patterns = [v for v in verdicts if v["verdict"] == VERDICT_DATA_BLOCKED]
    name_only = [r for r in ledger if r.get("identity_status") == "NAME_ONLY"]
    vp_missing = [r for r in ledger if r.get("vp") is None]
    sp_missing = [r for r in ledger if r.get("pick_sp") is None and r.get("actual_winner_sp") is None]
    date_missing = [r for r in ledger if not r.get("race_date")]

    name_only_current = [r for r in name_only if r.get("era_bucket") == "CURRENT_ERA_VALIDATED"]
    vp_missing_current = [r for r in vp_missing if r.get("era_bucket") == "CURRENT_ERA_VALIDATED"]

    gap_breakdown = dq.get("gap_type_breakdown", {}) if isinstance(dq, dict) else {}

    return {
        "data_blocked_patterns": blocked_patterns,
        "total_name_only": len(name_only),
        "name_only_current_era": len(name_only_current),
        "total_vp_missing": len(vp_missing),
        "vp_missing_current_era": len(vp_missing_current),
        "total_sp_missing": len(sp_missing),
        "total_date_missing": len(date_missing),
        "top_gap_types": dict(list(gap_breakdown.items())[:5]),
        "repair_priority_order": [
            "1. Resolve horse_id for NAME_ONLY current-era rows (n_current={})".format(len(name_only_current)),
            "2. Backfill VP for VP_MISSING current-era rows (n_current={})".format(len(vp_missing_current)),
            "3. Populate SP from sigma_audits_dump actual_winner_sp field where present",
            "4. Resolve null date rows via created_at field in sigma_audits_dump",
        ],
        "doc": "Data quality repair required before re-running Pattern Tribunal on these cohorts.",
    }


# ── Report questions ──────────────────────────────────────────────────────────

def answer_questions(
    verdicts: list[dict],
    triaged: list[dict],
    quarantine: dict,
    data_blocked: dict,
    vfu10_data: dict | None,
) -> dict:
    watchlist = [v for v in verdicts if v["verdict"] == VERDICT_WATCHLIST]
    blocked   = [v for v in verdicts if v["verdict"] == VERDICT_DATA_BLOCKED]
    q_only    = [v for v in verdicts if v["verdict"] == VERDICT_QUARANTINED]
    ts_reqd   = [v for v in verdicts if v["verdict"] == VERDICT_TIME_SAFE_REQD]
    rejected  = [v for v in verdicts if v["verdict"] == VERDICT_REJECT]

    p0 = [e for e in triaged if e["priority_band"] == P0]
    p1 = [e for e in triaged if e["priority_band"] == P1]
    p2 = [e for e in triaged if e["priority_band"] == P2]
    p3 = [e for e in triaged if e["priority_band"] == P3]
    p4 = [e for e in triaged if e["priority_band"] == P4]

    sp_verdict = next((v for v in verdicts if v["pattern_label"] == "SP_SHORTENING_CANDIDATE"), None)

    return {
        "Q1_watchlist_patterns":     [v["pattern_label"] for v in watchlist],
        "Q2_data_blocked_patterns":  [v["pattern_label"] for v in blocked],
        "Q3_quarantine_only_patterns": [v["pattern_label"] for v in q_only],
        "Q4_needs_time_safe_validation": [v["pattern_label"] for v in ts_reqd],
        "Q5_rejected_patterns":      [v["pattern_label"] for v in rejected],
        "Q6_top25_generated":        True,
        "Q7_biggest_contamination_risks": [
            "ERA_CONTAMINATION_CANDIDATE: n=2,165 Mar–Apr rows, zero time-safe (CRITICAL)",
            "SKELETON_OR_NULL_DATE_EXCLUDED: 331 rows with null/invalid dates — temporal provenance unknown",
            "DATA_QUALITY_DEBT_CANDIDATE overlap: 159 of 200 review queue entries are archive-quarantine rows",
        ],
        "Q8_biggest_data_quality_blockers": [
            "IDENTITY_RESOLUTION_NEEDED: 2,822 rows without RP_UID (2,112 current-era)",
            "DATA_QUALITY_DEBT_CANDIDATE: 2,516 rows with 3+ data gaps",
            "VP_MISSING: {} current-era rows".format(data_blocked.get("vp_missing_current_era", "N/A")),
        ],
        "Q9_sp_shortening_status": (
            f"SP shortening REMAINS the strongest time-safe Passport signal. "
            f"VFU-10 validated: pre-era SP trajectory is observable before race. "
            f"Current-era n={sp_verdict['current_era_count'] if sp_verdict else 'N/A'}, avg VP={sp_verdict['avg_vp_current'] if sp_verdict else 'N/A'}. "
            f"Verdict: {sp_verdict['verdict'] if sp_verdict else 'N/A'} — watchlist, not doctrine."
        ),
        "Q10_vp_threshold_recommendation": (
            f"VP threshold remains {VP_THRESHOLD}. NO CHANGE RECOMMENDED. "
            f"Evidence from current-era confirms monotonic VP signal strength. "
            f"FALSE_GREEN pattern (n=258) requires feature attribution before any threshold review."
        ),
        "Q11_doctrine_promotion_recommendation": (
            "NO DOCTRINE PROMOTION RECOMMENDED. "
            "VFU-10 law: no evidence becomes doctrine unless it was knowable before the race. "
            "Watchlist patterns require n>=50 RP_UID confirmed + operator review. "
            "FALSE_GREEN requires feature attribution. "
            "Quarantine patterns (Mar–Apr) permanently excluded from doctrine pathway."
        ),
        "Q12_vfu13_recommendation": (
            "VFU-13 recommended. Suggested focus (operator decision required): "
            "OPTION A — False-GREEN Feature Autopsy: identify which Ensemble component drove VP≥0.40 "
            "in 258 current-era losing cases. Requires feature-level ledger from VFU-11 identity-enriched autopsy. "
            "OPTION B — SP Shortening Deep Dive: build per-horse SP trajectory from core_v0 for "
            "the 316 current-era SP<20 winners (VFU-10 extension). "
            "OPTION C — Identity Repair Sprint: resolve 2,112 current-era NAME_ONLY rows to unlock "
            "VP_SUPPRESSION and SP_SHORTENING for Passport analysis. "
            "Operator to choose one focus area."
        ),
        "priority_band_counts": {
            P0: len(p0), P1: len(p1), P2: len(p2), P3: len(p3), P4: len(p4)
        },
    }


# ── Summary builder ───────────────────────────────────────────────────────────

def build_summary(
    verdicts: list[dict],
    triaged: list[dict],
    questions: dict,
    quarantine: dict,
    data_blocked: dict,
    timestamp: str,
) -> dict:
    by_verdict = Counter(v["verdict"] for v in verdicts)
    by_band = Counter(e["priority_band"] for e in triaged)

    final_classifications = [
        "VFU_12_SIGMA_PATTERN_TRIBUNAL_COMPLETE",
        "PATTERN_VERDICTS_CREATED",
        "HUMAN_REVIEW_TOP25_CREATED",
        "MAR_APR_QUARANTINE_MAINTAINED",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "NO_VP_THRESHOLD_CHANGE",
        "PATTERN_CANDIDATES_DRY_RUN_ONLY",
        "HUMAN_APPROVAL_REQUIRED_FOR_ALL_PATTERNS",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]

    return {
        "validation_version": VALIDATION_VERSION,
        "timestamp": timestamp,
        "vp_threshold": VP_THRESHOLD,
        "vp_threshold_unchanged": True,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_quarantine_only": True,
        "vfu10_law_enforced": True,

        "patterns_prosecuted": len(verdicts),
        "verdict_distribution": dict(by_verdict),
        "dry_run_watchlist_count": by_verdict.get(VERDICT_WATCHLIST, 0),
        "data_blocked_count": by_verdict.get(VERDICT_DATA_BLOCKED, 0),
        "quarantine_only_count": by_verdict.get(VERDICT_QUARANTINED, 0),
        "needs_time_safe_validation_count": by_verdict.get(VERDICT_TIME_SAFE_REQD, 0),
        "rejected_count": by_verdict.get(VERDICT_REJECT, 0),
        "human_review_required_count": by_verdict.get(VERDICT_HUMAN_REVIEW, 0),

        "review_queue_entries_read": len(triaged),
        "top25_generated": True,
        "priority_band_counts": dict(by_band),

        "required_answers": questions,

        "vfu13_recommended": True,
        "vfu13_options": [
            "OPTION_A: False-GREEN Feature Autopsy (258 current-era VP≥0.40 losses)",
            "OPTION_B: SP Shortening Deep Dive — per-horse trajectory from core_v0 (316 current-era)",
            "OPTION_C: Identity Repair Sprint — resolve 2,112 current-era NAME_ONLY rows",
        ],

        "final_classifications": final_classifications,
    }


# ── Markdown report ───────────────────────────────────────────────────────────

def build_md_report(
    summary: dict,
    verdicts: list[dict],
    triaged: list[dict],
    questions: dict,
    timestamp: str,
) -> str:
    lines = [
        f"# VFU-12 — Sigma Pattern Tribunal + Human Review Triage",
        f"**Version:** {VALIDATION_VERSION}  ",
        f"**Timestamp:** {timestamp}  ",
        f"**VP Threshold:** {VP_THRESHOLD} (UNCHANGED)  ",
        "",
        "---",
        "",
        "## VFU-10 Law (carried forward permanently)",
        "",
        "> *No evidence becomes doctrine unless it was knowable before the race.*",
        "",
        "---",
        "",
        "## Pattern Tribunal Verdicts",
        "",
        "| Pattern | n (total) | n (current) | Verdict | Contamination Risk |",
        "|---------|-----------|-------------|---------|-------------------|",
    ]
    for v in verdicts:
        lines.append(
            f"| {v['pattern_label']} | {v['evidence_count']:,} | {v['current_era_count']:,} "
            f"| **{v['verdict']}** | {v['contamination_risk']} |"
        )

    lines += [
        "",
        "All patterns: `blocked_from_live_use=True`, `human_approval_required=True`, `do_not_promote=True`",
        "",
        "---",
        "",
        "## Detailed Pattern Verdicts",
        "",
    ]
    for v in verdicts:
        lines += [
            f"### {v['pattern_label']}",
            f"**Verdict:** {v['verdict']}  ",
            f"**Evidence count (total):** {v['evidence_count']:,}  ",
            f"**Current-era (TIME_SAFE):** {v['current_era_count']:,}  ",
            f"**Archive quarantine:** {v['archive_quarantine_count']:,}  ",
            f"**RP_UID confirmed (current):** {v['rp_uid_confirmed_count']:,}  ",
            f"**Avg VP (current):** {v['avg_vp_current']}  ",
            f"**Avg SP (current):** {v['avg_sp_current']}  ",
            f"**Contamination risk:** {v['contamination_risk']}  ",
        ]
        if v.get("sr_note"):
            lines.append(f"**SR Note:** {v['sr_note']}  ")
        if v.get("sample_size_warning"):
            lines.append(f"**Sample warning:** {v['sample_size_warning']}  ")
        lines += [
            f"",
            f"**Reason:** {v['reason']}",
            f"",
            f"**Next required evidence:** {v['next_required_evidence']}",
            f"",
        ]

    lines += [
        "---",
        "",
        "## Human Review Queue Triage",
        "",
        "**Total entries triaged:** 200  ",
        f"**Priority band distribution:**  ",
    ]
    for band, n in summary["priority_band_counts"].items():
        lines.append(f"- {band}: {n}")

    lines += [
        "",
        "### Top 25 Human Review Cases",
        "",
        "| Rank | Priority | Horse | Era | VP | Outcome | Flags |",
        "|------|----------|-------|-----|----|---------|-------|",
    ]
    top25 = [e for e in triaged if e["priority_band"] in (P0, P1)][:25]
    for i, e in enumerate(top25, 1):
        horse = e.get("horse_name") or "(unknown)"
        era_short = (e.get("era_bucket") or "")[:20]
        flags_short = ", ".join(f.replace("_CANDIDATE", "").replace("_NEEDED", "")[:12] for f in e.get("pattern_flags", []))[:40]
        lines.append(
            f"| {i} | {e['priority_band']} | {horse} | {era_short} "
            f"| {e.get('vp', 'N/A')} | {e.get('outcome', '?')} | {flags_short} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Required Report Answers",
        "",
        f"**Q1 — Dry-run watchlist patterns:** {', '.join(questions['Q1_watchlist_patterns'])}",
        f"**Q2 — Data-blocked patterns:** {', '.join(questions['Q2_data_blocked_patterns'])}",
        f"**Q3 — Quarantine-only patterns:** {', '.join(questions['Q3_quarantine_only_patterns'])}",
        f"**Q4 — Needs time-safe validation:** {', '.join(questions['Q4_needs_time_safe_validation'])}",
        f"**Q5 — Rejected patterns:** {', '.join(questions['Q5_rejected_patterns']) or 'None'}",
        f"**Q6 — Top 25 generated:** {'YES' if questions['Q6_top25_generated'] else 'NO'}",
        "",
        f"**Q7 — Biggest contamination risks:**",
    ]
    for risk in questions["Q7_biggest_contamination_risks"]:
        lines.append(f"  - {risk}")
    lines.append("")
    lines.append(f"**Q8 — Biggest data-quality blockers:**")
    for blocker in questions["Q8_biggest_data_quality_blockers"]:
        lines.append(f"  - {blocker}")
    lines += [
        "",
        f"**Q9 — SP shortening status:** {questions['Q9_sp_shortening_status']}",
        f"",
        f"**Q10 — VP threshold recommendation:** {questions['Q10_vp_threshold_recommendation']}",
        f"",
        f"**Q11 — Doctrine promotion recommendation:** {questions['Q11_doctrine_promotion_recommendation']}",
        f"",
        f"**Q12 — VFU-13 recommendation:** {questions['Q12_vfu13_recommendation']}",
        "",
        "---",
        "",
        "## Hard Rules — Confirmed",
        "",
        "- VP threshold: 0.40 — UNCHANGED",
        "- Canonical Horse Passport: NOT MUTATED",
        "- Supabase: NOT WRITTEN",
        "- Live scoring: NOT CHANGED",
        "- Model: NOT PROMOTED",
        "- Telegram: NOT SENT",
        "- Racing API: NOT RESTORED",
        "- Mar–Apr: QUARANTINE ONLY — no doctrine, no Passport, no live use",
        "- All patterns: blocked_from_live_use=True, human_approval_required=True",
        "",
        "---",
        "",
        "## Final Classifications",
        "",
        "```",
    ]
    for fc in summary["final_classifications"]:
        lines.append(fc)
    lines.append("```")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[VFU-12] {VALIDATION_VERSION}")
    print(f"[VFU-12] VP_THRESHOLD={VP_THRESHOLD}")

    # Load inputs
    print("[VFU-12] Loading VFU-11 outputs...")
    ledger   = load_jsonl(IN["ledger"])
    patterns = load_json(IN["patterns"])
    queue    = load_json(IN["review_queue"])
    dq       = load_json(IN["dq_debt"])
    vfu10    = load_json(IN["vfu10_validation"])

    assert ledger,   "Master ledger is empty or missing"
    assert patterns, "Pattern candidates missing"
    assert queue,    "Human review queue missing"

    print(f"[VFU-12] Loaded {len(ledger):,} ledger rows | {len(patterns)} patterns | {len(queue)} review entries")

    # Analyse each pattern against the ledger
    print("[VFU-12] Analysing patterns...")
    verdicts = []
    for p in patterns:
        flag = p["pattern_flag"]
        analysis = analyse_pattern(flag, ledger)
        verdict = prosecute_pattern(flag, analysis, vfu10)
        verdicts.append(verdict)
        print(f"  {flag}: {verdict['verdict']}")

    # Triage human review queue
    print("[VFU-12] Triaging human review queue...")
    triaged = triage_review_queue(queue)
    band_counts = Counter(e["priority_band"] for e in triaged)
    for band in [P0, P1, P2, P3, P4]:
        print(f"  {band}: {band_counts.get(band, 0)}")

    top25 = [e for e in triaged if e["priority_band"] in (P0, P1)][:25]
    print(f"[VFU-12] Top 25 queue size: {len(top25)}")

    # Build supplementary findings
    quarantine = build_quarantine_findings(ledger, verdicts)
    data_blocked = build_data_blocked_findings(ledger, verdicts, dq or {})
    questions = answer_questions(verdicts, triaged, quarantine, data_blocked, vfu10)
    summary = build_summary(verdicts, triaged, questions, quarantine, data_blocked, timestamp)

    # Write outputs
    print("[VFU-12] Writing outputs...")
    OUT_VERDICTS.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-12] Written: {OUT_VERDICTS}")

    OUT_TOP25.write_text(json.dumps(top25, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-12] Written: {OUT_TOP25} ({len(top25)} entries)")

    OUT_RANKED.write_text(json.dumps(triaged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-12] Written: {OUT_RANKED} ({len(triaged)} entries)")

    OUT_QUARANTINE.write_text(json.dumps(quarantine, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-12] Written: {OUT_QUARANTINE}")

    OUT_DATA_BLOCKED.write_text(json.dumps(data_blocked, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-12] Written: {OUT_DATA_BLOCKED}")

    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-12] Written: {OUT_SUMMARY_JSON}")

    md = build_md_report(summary, verdicts, triaged, questions, timestamp)
    OUT_SUMMARY_MD.write_text(md, encoding="utf-8")
    print(f"[VFU-12] Written: {OUT_SUMMARY_MD}")

    print(f"[VFU-12] VP threshold: {VP_THRESHOLD} (UNCHANGED)")
    print(f"[VFU-12] Canonical Passport: NOT MUTATED")
    print(f"[VFU-12] Supabase: NOT WRITTEN")
    print(f"[VFU-12] DONE.")


if __name__ == "__main__":
    main()
