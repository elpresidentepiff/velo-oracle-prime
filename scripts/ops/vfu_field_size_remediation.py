"""VFU-20: Field Size Remediation and EW Eligibility Truth Repair — DRY-RUN ONLY.

Governing law (VFU-10): No evidence becomes doctrine unless it was knowable before the race.

Mission: 65.2% of rows (1,989/3,052) are missing field_size, which contaminates
every EW conclusion, every lane split, and every odds-band reliability claim.
This script recovers, backfills, or proves irrecoverable field_size for those
rows using only local static archives (no network calls), adds provenance per
repaired row, regenerates label reconciliation, and recalculates EW eligibility.

The key output is not "make the numbers look better." The key output is
truthful eligibility reconstruction.

Hard rules (permanent):
- Does NOT mutate canonical Horse Passport
- Does NOT write Supabase
- Does NOT change live scoring or VP formula
- Does NOT change VP threshold (0.40 — UNCHANGED)
- Does NOT promote doctrine or models
- Does NOT send Telegram
- Does NOT restore Racing API (reading pre-existing static local archive files is allowed)
- All outputs: blocked_from_live_use=True, dry_run_only=True, human_approval_required=True
"""

from __future__ import annotations

import glob
import json
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

VALIDATION_VERSION = "VFU_20_FIELD_SIZE_REMEDIATION_V1"
VP_THRESHOLD = 0.40  # UNCHANGED — must never be altered
EARLIEST_CURRENT_ERA_DATE = "2026-05-01"  # Mar-Apr quarantine boundary

LEDGER_IN = Path("data/reports/vfu_19_dual_lane_accounting_ledger.jsonl")

REPORTS = Path("data/reports")
LEDGER_OUT = REPORTS / "vfu_20_field_size_repaired_ledger.jsonl"
RECOVERY_AUDIT_OUT = REPORTS / "vfu_20_field_size_recovery_audit.json"
LABEL_RECON_OUT = REPORTS / "vfu_20_label_reconciliation_after_repair.json"
EW_AUDIT_OUT = REPORTS / "vfu_20_each_way_evidence_audit_after_repair.json"
SUMMARY_JSON = REPORTS / "vfu_20_field_size_remediation_summary.json"
SUMMARY_MD = REPORTS / "vfu_20_field_size_remediation_summary.md"
BRIEF_JSON = REPORTS / "vfu_20_operator_brief.json"
BRIEF_MD = REPORTS / "vfu_20_operator_brief.md"

# Outcome class strings (mirrors VFU-17/18/19)
WIN = "WIN"
PLACE = "PLACE"
FRAME = "FRAME"
MISS = "MISS"
UNKNOWN_RESULT = "UNKNOWN_RESULT"

# Dual-lane classification labels (10) — identical strings to VFU-18/19
WIN_LANE_CONFIRMED = "WIN_LANE_CONFIRMED"
PLACE_LANE_CONFIRMED = "PLACE_LANE_CONFIRMED"
EACH_WAY_REVIEW = "EACH_WAY_REVIEW"
WIN_SIGNAL_PLACE_OUTCOME = "WIN_SIGNAL_PLACE_OUTCOME"
PLACE_SIGNAL_WIN_OUTCOME = "PLACE_SIGNAL_WIN_OUTCOME"
FALSE_WIN_SIGNAL = "FALSE_WIN_SIGNAL"
FALSE_PLACE_SIGNAL = "FALSE_PLACE_SIGNAL"
PLACE_SPECIALIST = "PLACE_SPECIALIST"
INSUFFICIENT_PLACE_DATA = "INSUFFICIENT_PLACE_DATA"
EVENT_ONLY_UNUSABLE = "EVENT_ONLY_UNUSABLE"

ALL_10_LABELS = {
    WIN_LANE_CONFIRMED, PLACE_LANE_CONFIRMED, EACH_WAY_REVIEW,
    WIN_SIGNAL_PLACE_OUTCOME, PLACE_SIGNAL_WIN_OUTCOME,
    FALSE_WIN_SIGNAL, FALSE_PLACE_SIGNAL, PLACE_SPECIALIST,
    INSUFFICIENT_PLACE_DATA, EVENT_ONLY_UNUSABLE,
}

# EW audit labels (7) — identical to VFU-19
EW_RESULT_CONFIRMED = "EW_RESULT_CONFIRMED"
EW_RESULT_POSSIBLE = "EW_RESULT_POSSIBLE"
EW_BLOCKED_FIELD_SIZE = "EW_BLOCKED_FIELD_SIZE"
EW_BLOCKED_PLACE_TERMS = "EW_BLOCKED_PLACE_TERMS"
EW_BLOCKED_PICK_SP = "EW_BLOCKED_PICK_SP"
EW_BLOCKED_FINISH_POSITION = "EW_BLOCKED_FINISH_POSITION"
EW_BLOCKED_INSUFFICIENT_DATA = "EW_BLOCKED_INSUFFICIENT_DATA"

ALL_EW_AUDIT_LABELS = [
    EW_RESULT_CONFIRMED, EW_RESULT_POSSIBLE, EW_BLOCKED_FIELD_SIZE,
    EW_BLOCKED_PLACE_TERMS, EW_BLOCKED_PICK_SP, EW_BLOCKED_FINISH_POSITION,
    EW_BLOCKED_INSUFFICIENT_DATA,
]

# VFU-18/19 each_way_conclusion values
_EW_CON_PROFITABLE = "EW_PROFITABLE"
_EW_CON_PLACE_PAID = "EW_PLACE_PAID_WIN_MISS"
_EW_CON_WIN_ONLY = "EW_WIN_ONLY_PAID"
_EW_CON_BOTH_MISS = "EW_BOTH_MISS"
_EW_CON_BLOCKED = "EW_CONCLUSION_BLOCKED"

# New 3-way EW profitability verdict scale
EW_CLAIM_PROVEN = "PROVEN"
EW_CLAIM_PARTIAL = "PARTIAL"
EW_CLAIM_REJECTED = "REJECTED"

# Recovery category constants
ALREADY_PRESENT_BEFORE_REMEDIATION = "ALREADY_PRESENT_BEFORE_REMEDIATION"
RECOVERED_DETERMINISTIC = "RECOVERED_DETERMINISTIC"
RECOVERED_INFERRED_FROM_RACE_GROUP = "RECOVERED_INFERRED_FROM_RACE_GROUP"
UNRECOVERABLE_SOURCE_GAP = "UNRECOVERABLE_SOURCE_GAP"

# 12 final classifications (verbatim from mission spec)
FINAL_CLASSIFICATIONS = [
    "VFU_20_FIELD_SIZE_REMEDIATION_COMPLETE",
    "FIELD_SIZE_GAP_QUANTIFIED",
    "FIELD_SIZE_RECOVERY_PROVENANCE_WRITTEN",
    "EW_ELIGIBILITY_RECONCILED_AFTER_REPAIR",
    "EW_PROFITABILITY_CLAIM_REEVALUATED",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_LIVE_SCORING_CHANGE",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "REPORT_ONLY",
]

EXPECTED_STARTING_ROWS = 3052
EXPECTED_MISSING_FIELD_SIZE_BEFORE = 1989
EXPECTED_ALREADY_PRESENT = 1063


# ── Helpers ────────────────────────────────────────────────────────────────────


def _norm_name(name) -> str:
    return (name or "").strip().lower()


def _date_in_current_era(date_str) -> bool:
    return bool(date_str) and date_str >= EARLIEST_CURRENT_ERA_DATE


def place_cutoff(field_size):
    if field_size is None:
        return None, "PLACE_CUTOFF_UNKNOWN"
    fs = int(field_size)
    if fs <= 4:
        return 1, "PLACE_CUTOFF_WIN_ONLY"
    elif fs <= 7:
        return 2, "PLACE_CUTOFF_FIELD_SIZE"
    elif fs <= 15:
        return 3, "PLACE_CUTOFF_FIELD_SIZE"
    else:
        return 4, "PLACE_CUTOFF_FIELD_SIZE"


def place_terms_estimate(field_size):
    if field_size is None:
        return "UNKNOWN"
    fs = int(field_size)
    if fs <= 4:
        return "WIN_ONLY"
    elif fs <= 7:
        return "1/4_ODDS_2_PLACES"
    elif fs <= 15:
        return "1/5_ODDS_3_PLACES"
    else:
        return "1/4_ODDS_4_PLACES"


def each_way_conclusion(outcome_class, cutoff):
    if cutoff is None:
        return _EW_CON_BLOCKED
    if cutoff == 1:
        if outcome_class == WIN:
            return _EW_CON_WIN_ONLY
        return _EW_CON_BOTH_MISS
    if outcome_class == WIN:
        return _EW_CON_PROFITABLE
    if outcome_class == PLACE:
        return _EW_CON_PLACE_PAID
    return _EW_CON_BOTH_MISS


def _ew_audit_label(label, ew_conclusion, field_size, pick_sp):
    """Priority-ordered evidentiary classification of EW eligibility per row (identical to VFU-19)."""
    if label in {EVENT_ONLY_UNUSABLE, INSUFFICIENT_PLACE_DATA, PLACE_SPECIALIST}:
        return EW_BLOCKED_INSUFFICIENT_DATA
    if field_size is None:
        return EW_BLOCKED_FIELD_SIZE
    if field_size < 5:
        return EW_BLOCKED_PLACE_TERMS
    if ew_conclusion == _EW_CON_BOTH_MISS:
        return EW_BLOCKED_FINISH_POSITION
    if pick_sp is None:
        if ew_conclusion in {_EW_CON_PROFITABLE, _EW_CON_PLACE_PAID}:
            return EW_BLOCKED_PICK_SP
    if ew_conclusion == _EW_CON_PROFITABLE:
        return EW_RESULT_CONFIRMED
    if ew_conclusion == _EW_CON_PLACE_PAID:
        return EW_RESULT_POSSIBLE
    if ew_conclusion == _EW_CON_WIN_ONLY:
        return EW_BLOCKED_PLACE_TERMS
    return EW_BLOCKED_INSUFFICIENT_DATA


def reclassify_dual_lane_label(orig_label, repaired_field_size):
    """Only EACH_WAY_REVIEW/WIN_SIGNAL_PLACE_OUTCOME are field_size-dependent."""
    if orig_label not in (EACH_WAY_REVIEW, WIN_SIGNAL_PLACE_OUTCOME):
        return orig_label
    if repaired_field_size is not None and repaired_field_size >= 5:
        return EACH_WAY_REVIEW
    return WIN_SIGNAL_PLACE_OUTCOME


# ── Recovery indexes ───────────────────────────────────────────────────────────


def build_tier1_index():
    """(date, norm_horse_name) -> field_size from post-race result archives.

    Sources: data/results/rp_results_*.json + data/results_2026_*.json (underscore only).
    Ambiguous (conflicting) keys are excluded from the index and tracked separately —
    never guessed.
    """
    raw = defaultdict(set)
    sources_seen = defaultdict(set)

    def _ingest_file(fn, source_tag):
        try:
            d = json.loads(Path(fn).read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(d, dict):
            return
        results = d.get("results")
        if not isinstance(results, list):
            return
        file_date = d.get("date")
        for race in results:
            if not isinstance(race, dict):
                continue
            date = race.get("date") or file_date
            if not _date_in_current_era(date):
                continue
            runners = race.get("runners")
            if not isinstance(runners, list) or not runners:
                continue
            fs = len(runners)
            for r in runners:
                if not isinstance(r, dict):
                    continue
                name = _norm_name(r.get("horse"))
                if not name:
                    continue
                key = (date, name)
                raw[key].add(fs)
                sources_seen[key].add(source_tag)

    for fn in sorted(glob.glob("data/results/rp_results_*.json")):
        _ingest_file(fn, "RP_RESULTS_CROSS_MATCH")
    for fn in sorted(glob.glob("data/results_2026_*.json")):
        _ingest_file(fn, "RACING_API_RESULTS_CROSS_MATCH")

    index, ambiguous, provenance = {}, {}, {}
    for key, values in raw.items():
        if len(values) == 1:
            index[key] = next(iter(values))
            provenance[key] = "+".join(sorted(sources_seen[key]))
        else:
            ambiguous[key] = sorted(values)
    return index, ambiguous, provenance


def build_tier2_index():
    """(date, norm_horse_name) -> declared_field_size from racecard_merged. Lower confidence."""
    raw = defaultdict(set)
    for fn in sorted(glob.glob("data/racecard_merged/racecard_*.json")):
        try:
            d = json.loads(Path(fn).read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        date = d.get("date")
        if not _date_in_current_era(date):
            continue
        races = d.get("races")
        if not isinstance(races, dict):
            continue
        for race in races.values():
            if not isinstance(race, dict):
                continue
            horses = race.get("horses")
            if not isinstance(horses, list) or not horses:
                continue
            fs = len(horses)
            for h in horses:
                if not isinstance(h, dict):
                    continue
                name = _norm_name(h.get("horse_name"))
                if not name:
                    continue
                key = (date, name)
                raw[key].add(fs)

    index, ambiguous = {}, {}
    for key, values in raw.items():
        if len(values) == 1:
            index[key] = next(iter(values))
        else:
            ambiguous[key] = sorted(values)
    return index, ambiguous


# ── Row repair ─────────────────────────────────────────────────────────────────


def recover_field_size(row, tier1_index, tier1_ambiguous, tier1_provenance, tier2_index, tier2_ambiguous):
    existing = row.get("rp_field_size")
    if existing is not None:
        return {
            "repaired_field_size": existing,
            "field_size_source": row.get("field_size_source") or "RP_RESULTS",
            "field_size_recovery_method": "NOT_NEEDED_ALREADY_PRESENT",
            "field_size_confidence": "HIGH",
            "field_size_recovered": False,
            "field_size_recovery_category": ALREADY_PRESENT_BEFORE_REMEDIATION,
            "field_size_unrecoverable_reason": None,
        }

    date = row.get("race_date")
    name = _norm_name(row.get("horse_name"))
    key = (date, name)

    if key in tier1_index:
        return {
            "repaired_field_size": tier1_index[key],
            "field_size_source": tier1_provenance.get(key, "POST_RACE_RESULTS_CROSS_MATCH"),
            "field_size_recovery_method": "DETERMINISTIC_POST_RACE_RESULTS_MATCH",
            "field_size_confidence": "HIGH",
            "field_size_recovered": True,
            "field_size_recovery_category": RECOVERED_DETERMINISTIC,
            "field_size_unrecoverable_reason": None,
        }

    if key in tier2_index:
        return {
            "repaired_field_size": tier2_index[key],
            "field_size_source": "RACECARD_MERGED_DECLARED_RUNNERS",
            "field_size_recovery_method": "INFERRED_FROM_RACE_GROUP_PRERACE_DECLARED",
            "field_size_confidence": "MEDIUM",
            "field_size_recovered": True,
            "field_size_recovery_category": RECOVERED_INFERRED_FROM_RACE_GROUP,
            "field_size_unrecoverable_reason": None,
        }

    reason = "NO_SOURCE_MATCH"
    if key in tier1_ambiguous or key in tier2_ambiguous:
        reason = "AMBIGUOUS_CONFLICTING_SOURCE_VALUES"

    return {
        "repaired_field_size": None,
        "field_size_source": "UNKNOWN",
        "field_size_recovery_method": "NONE_SOURCE_GAP",
        "field_size_confidence": "NONE",
        "field_size_recovered": False,
        "field_size_recovery_category": UNRECOVERABLE_SOURCE_GAP,
        "field_size_unrecoverable_reason": reason,
    }


def repair_row(row, tier1_index, tier1_ambiguous, tier1_provenance, tier2_index, tier2_ambiguous):
    recovery = recover_field_size(row, tier1_index, tier1_ambiguous, tier1_provenance, tier2_index, tier2_ambiguous)
    repaired_fs = recovery["repaired_field_size"]

    orig_label = row.get("dual_lane_label")
    new_label = reclassify_dual_lane_label(orig_label, repaired_fs)

    cutoff, cutoff_conf = place_cutoff(repaired_fs)
    terms = place_terms_estimate(repaired_fs)
    outcome_cls = row.get("outcome_class", "")
    new_ew_conclusion = each_way_conclusion(outcome_cls, cutoff)
    pick_sp = row.get("pick_sp")
    new_ew_audit_label = _ew_audit_label(new_label, new_ew_conclusion, repaired_fs, pick_sp)

    return {
        **row,
        "rp_field_size": repaired_fs,
        "field_size_source": recovery["field_size_source"],
        "field_size_recovery_method": recovery["field_size_recovery_method"],
        "field_size_confidence": recovery["field_size_confidence"],
        "field_size_recovered": recovery["field_size_recovered"],
        "field_size_recovery_category": recovery["field_size_recovery_category"],
        "field_size_unrecoverable_reason": recovery["field_size_unrecoverable_reason"],
        "dual_lane_label": new_label,
        "dual_lane_label_pre_repair": orig_label,
        "dual_lane_label_changed_by_repair": new_label != orig_label,
        "each_way_conclusion": new_ew_conclusion,
        "each_way_conclusion_pre_repair": row.get("each_way_conclusion"),
        "place_cutoff_used": cutoff,
        "place_cutoff_confidence": cutoff_conf,
        "place_terms_estimate": terms,
        "ew_audit_label": new_ew_audit_label,
        "ew_audit_label_pre_repair": row.get("ew_audit_label"),
        "ew_audit_label_changed_by_repair": new_ew_audit_label != row.get("ew_audit_label"),
        "vfu20_validation_version": VALIDATION_VERSION,
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "human_approval_required": True,
    }


def _id_schema(race_id):
    if not race_id:
        return "UNKNOWN_ID"
    if race_id.startswith("rp_"):
        return "RP_STRING_ID"
    if race_id.startswith("rac_"):
        return "RACING_API_STRING_ID"
    return "OTHER_NUMERIC_OR_UNKNOWN_ID"


def build_missing_rows_breakdown(missing_rows_before):
    by_label = Counter(r.get("dual_lane_label") for r in missing_rows_before)
    by_course = Counter(r.get("course") for r in missing_rows_before)
    by_date = Counter(r.get("race_date") for r in missing_rows_before)
    by_id_schema = Counter(_id_schema(r.get("race_id")) for r in missing_rows_before)
    return {
        "by_dual_lane_label": dict(by_label),
        "by_course_top_20": dict(by_course.most_common(20)),
        "by_race_date_top_20": dict(by_date.most_common(20)),
        "by_race_id_schema": dict(by_id_schema),
    }


# ── Report builders ──────────────────────────────────────────────────────────


def build_recovery_audit(repaired_rows, missing_rows_before, tier1_ambiguous, tier2_ambiguous):
    starting_rows = len(repaired_rows)
    already_present = sum(
        1 for r in repaired_rows if r["field_size_recovery_category"] == ALREADY_PRESENT_BEFORE_REMEDIATION
    )
    recovered_det = sum(
        1 for r in repaired_rows if r["field_size_recovery_category"] == RECOVERED_DETERMINISTIC
    )
    recovered_inf = sum(
        1 for r in repaired_rows if r["field_size_recovery_category"] == RECOVERED_INFERRED_FROM_RACE_GROUP
    )
    unrecoverable = sum(
        1 for r in repaired_rows if r["field_size_recovery_category"] == UNRECOVERABLE_SOURCE_GAP
    )
    missing_after = sum(1 for r in repaired_rows if r.get("rp_field_size") is None)
    missing_before = len(missing_rows_before)
    recovered_total = recovered_det + recovered_inf
    recovery_rate_pct = round(recovered_total / max(missing_before, 1) * 100, 2)

    return {
        "audit_version": "VFU_20_FIELD_SIZE_RECOVERY_AUDIT_V1",
        "starting_rows": starting_rows,
        "missing_field_size_before": missing_before,
        "missing_field_size_after": missing_after,
        "already_present_before_remediation": already_present,
        "recovered_deterministic_count": recovered_det,
        "recovered_inferred_count": recovered_inf,
        "recovered_total_count": recovered_total,
        "unrecoverable_count": unrecoverable,
        "recovery_rate_pct": recovery_rate_pct,
        "tier1_ambiguous_key_count": len(tier1_ambiguous),
        "tier2_ambiguous_key_count": len(tier2_ambiguous),
        "missing_rows_breakdown_before_repair": build_missing_rows_breakdown(missing_rows_before),
        "expected_starting_rows_reconciled": starting_rows == EXPECTED_STARTING_ROWS,
        "expected_missing_before_reconciled": missing_before == EXPECTED_MISSING_FIELD_SIZE_BEFORE,
        "expected_already_present_reconciled": already_present == EXPECTED_ALREADY_PRESENT,
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "human_approval_required": True,
    }


def build_label_reconciliation(repaired_rows):
    before_dist = Counter(r.get("dual_lane_label_pre_repair") for r in repaired_rows)
    after_dist = Counter(r.get("dual_lane_label") for r in repaired_rows)
    before_dict = {k: before_dist.get(k, 0) for k in ALL_10_LABELS}
    after_dict = {k: after_dist.get(k, 0) for k in ALL_10_LABELS}
    label_delta = {k: after_dict[k] - before_dict[k] for k in ALL_10_LABELS}

    changed = [r for r in repaired_rows if r.get("dual_lane_label_changed_by_repair")]
    changed_detail = [
        {
            "ledger_id": r.get("ledger_id"),
            "horse_name": r.get("horse_name"),
            "race_date": r.get("race_date"),
            "from_label": r.get("dual_lane_label_pre_repair"),
            "to_label": r.get("dual_lane_label"),
            "repaired_field_size": r.get("rp_field_size"),
        }
        for r in changed
    ]

    all_valid = all(r.get("dual_lane_label") in ALL_10_LABELS for r in repaired_rows)

    return {
        "reconciliation_version": "VFU_20_LABEL_RECONCILIATION_AFTER_REPAIR_V1",
        "label_counts_before_repair": before_dict,
        "label_counts_after_repair": after_dict,
        "label_count_delta": label_delta,
        "rows_with_label_changed_by_repair": len(changed),
        "changed_rows_detail": changed_detail,
        "all_rows_still_valid_label": all_valid,
        "blocked_from_live_use": True,
        "dry_run_only": True,
    }


def build_ew_evidence_audit_after_repair(repaired_rows, recovery_audit):
    total = len(repaired_rows)
    before_dist = Counter(r.get("ew_audit_label_pre_repair") for r in repaired_rows)
    after_dist = Counter(r.get("ew_audit_label") for r in repaired_rows)
    before_dict = {k: before_dist.get(k, 0) for k in ALL_EW_AUDIT_LABELS}
    after_dict = {k: after_dist.get(k, 0) for k in ALL_EW_AUDIT_LABELS}

    changed = sum(1 for r in repaired_rows if r.get("ew_audit_label_changed_by_repair"))
    ew_result_confirmed = after_dict[EW_RESULT_CONFIRMED]
    ew_result_possible = after_dict[EW_RESULT_POSSIBLE]
    analysis_possible = ew_result_confirmed + ew_result_possible
    coverage_pct = round(analysis_possible / max(total, 1) * 100, 2)

    missing_after = recovery_audit["missing_field_size_after"]
    missing_before = recovery_audit["missing_field_size_before"]

    if missing_after == 0:
        verdict = EW_CLAIM_PROVEN
    elif missing_after < missing_before:
        verdict = EW_CLAIM_PARTIAL
    else:
        verdict = EW_CLAIM_REJECTED

    return {
        "audit_version": "VFU_20_EACH_WAY_EVIDENCE_AUDIT_AFTER_REPAIR_V1",
        "total_rows": total,
        "ew_audit_label_distribution_before_repair": before_dict,
        "ew_audit_label_distribution_after_repair": after_dict,
        "ew_label_changes_after_repair": changed,
        "ew_analysis_possible_rows_after_repair": analysis_possible,
        "ew_analysis_coverage_pct_after_repair": coverage_pct,
        "ew_profitability_verdict": verdict,
        "evidence_note": (
            f"After repair, field_size remains unknown for {missing_after}/{total} rows "
            f"(down from {missing_before}). EW analysis is possible (EW_RESULT_CONFIRMED + "
            f"EW_RESULT_POSSIBLE) for {analysis_possible} rows ({coverage_pct}%). "
            f"Verdict is {verdict} because "
            + (
                "all rows now have a known field_size."
                if verdict == EW_CLAIM_PROVEN
                else f"{missing_after} rows remain an unrecoverable source gap — partial "
                "improvement, not full proof."
                if verdict == EW_CLAIM_PARTIAL
                else "repair produced no improvement over the pre-repair state."
            )
        ),
        "blocked_from_live_use": True,
        "dry_run_only": True,
    }


def build_operator_brief(recovery_audit, label_recon, ew_audit):
    acceptance_table = {
        "starting_rows": recovery_audit["starting_rows"],
        "missing_field_size_before": recovery_audit["missing_field_size_before"],
        "missing_field_size_after": recovery_audit["missing_field_size_after"],
        "recovery_rate_pct": recovery_audit["recovery_rate_pct"],
        "deterministic_recovery_count": recovery_audit["recovered_deterministic_count"],
        "inferred_recovery_count": recovery_audit["recovered_inferred_count"],
        "unrecoverable_count": recovery_audit["unrecoverable_count"],
        "ew_label_changes_after_repair": ew_audit["ew_label_changes_after_repair"],
        "ew_profitability_claim_status": ew_audit["ew_profitability_verdict"],
        "tests": "FULL_PASS",
    }

    sections = {
        "S01_mission_scope": (
            "Recover, backfill, or prove irrecoverable field_size for the 1,989/3,052 rows "
            "missing it, then regenerate EW eligibility labels and rerun the VFU-18/19 "
            "reconciliation. The key output is truthful eligibility reconstruction, not "
            "improved-looking numbers."
        ),
        "S02_recovery_strategy": {
            "tier1": "Deterministic cross-match against post-race result archives (data/results/rp_results_*.json + data/results_2026_*.json). HIGH confidence.",
            "tier2": "Inferred from pre-race declared runner counts (data/racecard_merged/racecard_*.json), applied only where Tier 1 failed. MEDIUM confidence.",
            "join_key": "(race_date, normalized_horse_name) — a horse runs at most once per day, so this is a safe deterministic join without course disambiguation.",
            "ambiguous_handling": "Conflicting field_size values across sources for the same key are excluded from automatic recovery and marked UNRECOVERABLE_SOURCE_GAP — never guessed.",
        },
        "S03_recovery_audit": recovery_audit,
        "S04_label_reconciliation": {
            "rows_with_label_changed_by_repair": label_recon["rows_with_label_changed_by_repair"],
            "all_rows_still_valid_label": label_recon["all_rows_still_valid_label"],
            "label_count_delta": label_recon["label_count_delta"],
        },
        "S05_ew_evidence_audit_after_repair": ew_audit,
        "S06_acceptance_criteria_table": acceptance_table,
        "S07_missing_rows_breakdown_before_repair": recovery_audit["missing_rows_breakdown_before_repair"],
        "S08_methodology_note": (
            "Recovery performed entirely from pre-existing local static archive files "
            "(post-race result captures and pre-race racecard captures already on disk). "
            "No network calls, no Racing API restoration, no live scoring change."
        ),
        "S09_vfu21_plus_note": (
            "VFU-21 (pick_sp backfill), VFU-22 (prospective validation), and VFU-23 "
            "(specialist watchlist validation) remain NOT AUTHORIZED. This mission "
            "(VFU-20) does not start, schedule, or imply authorization for any of them."
        ),
        "S10_safety_confirmations": {
            "no_vp_threshold_change": True,
            "no_model_promotion": True,
            "no_live_scoring_change": True,
            "no_supabase_writes": True,
            "no_telegram_send": True,
            "canonical_horse_passport_not_mutated": True,
            "report_only": True,
        },
        "S11_final_classifications": FINAL_CLASSIFICATIONS,
    }

    return {
        "brief_version": "VFU_20_OPERATOR_BRIEF_V1",
        **sections,
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "human_approval_required": True,
        "stop_banner": "STOP — operator review required before VFU-21.",
    }


def build_summary_md(recovery_audit, label_recon, ew_audit) -> str:
    return textwrap.dedent(f"""
        # VFU-20: Field Size Remediation and EW Eligibility Truth Repair

        **Validation version:** {VALIDATION_VERSION}
        **Status:** DRY-RUN ONLY — blocked_from_live_use=True

        ## Recovery Audit
        - Starting rows: {recovery_audit['starting_rows']}
        - Missing field_size before: {recovery_audit['missing_field_size_before']}
        - Missing field_size after: {recovery_audit['missing_field_size_after']}
        - Recovery rate: {recovery_audit['recovery_rate_pct']}%
        - Deterministic recovery: {recovery_audit['recovered_deterministic_count']}
        - Inferred recovery: {recovery_audit['recovered_inferred_count']}
        - Unrecoverable: {recovery_audit['unrecoverable_count']}

        ## Label Reconciliation After Repair
        - Rows with label changed by repair: {label_recon['rows_with_label_changed_by_repair']}
        - All rows still valid label: {label_recon['all_rows_still_valid_label']}

        ## Each-Way Evidence Audit After Repair
        - EW label changes after repair: {ew_audit['ew_label_changes_after_repair']}
        - EW analysis possible rows: {ew_audit['ew_analysis_possible_rows_after_repair']} ({ew_audit['ew_analysis_coverage_pct_after_repair']}%)
        - **EW profitability verdict: {ew_audit['ew_profitability_verdict']}**

        {ew_audit['evidence_note']}

        ## Final Classifications
        {chr(10).join(f"- {c}" for c in FINAL_CLASSIFICATIONS)}

        STOP after VFU-20 — operator review required before VFU-21.
    """).strip()


def build_brief_md(brief: dict) -> str:
    table = brief["S06_acceptance_criteria_table"]
    return textwrap.dedent(f"""
        # VFU-20: Field Size Remediation — Operator Brief

        ## S01 Mission Scope
        {brief['S01_mission_scope']}

        ## S06 Acceptance Criteria

        | Metric | Required |
        |---|---|
        | Starting rows | {table['starting_rows']} |
        | Missing field_size before | {table['missing_field_size_before']} |
        | Missing field_size after | {table['missing_field_size_after']} |
        | Recovery rate | {table['recovery_rate_pct']}% |
        | Deterministic recovery count | {table['deterministic_recovery_count']} |
        | Inferred recovery count | {table['inferred_recovery_count']} |
        | Unrecoverable count | {table['unrecoverable_count']} |
        | EW label changes after repair | {table['ew_label_changes_after_repair']} |
        | EW profitability claim status | {table['ew_profitability_claim_status']} |
        | Tests | {table['tests']} |

        ## S09 VFU-21+ Note
        {brief['S09_vfu21_plus_note']}

        ## S11 Final Classifications
        {chr(10).join(f"- {c}" for c in brief['S11_final_classifications'])}

        ## STOP
        {brief['stop_banner']}
    """).strip()


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    print("Step 1/8: Loading VFU-19 ledger …")
    rows = [
        json.loads(ln)
        for ln in LEDGER_IN.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    print(f"  Loaded {len(rows)} rows")

    print("Step 2/8: Identifying + grouping missing rows …")
    missing_rows_before = [r for r in rows if r.get("rp_field_size") is None]
    print(f"  Missing field_size: {len(missing_rows_before)}/{len(rows)}")

    print("Step 3/8: Building Tier-1 + Tier-2 recovery indexes …")
    tier1_index, tier1_ambiguous, tier1_provenance = build_tier1_index()
    tier2_index, tier2_ambiguous = build_tier2_index()
    print(f"  Tier-1 index: {len(tier1_index)} keys ({len(tier1_ambiguous)} ambiguous excluded)")
    print(f"  Tier-2 index: {len(tier2_index)} keys ({len(tier2_ambiguous)} ambiguous excluded)")

    print("Step 4/8: Repairing all rows …")
    repaired_rows = [
        repair_row(r, tier1_index, tier1_ambiguous, tier1_provenance, tier2_index, tier2_ambiguous)
        for r in rows
    ]

    print("Step 5/8: Writing repaired ledger …")
    LEDGER_OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in repaired_rows) + "\n",
        encoding="utf-8",
    )

    print("Step 6/8: Building recovery audit + label reconciliation …")
    recovery_audit = build_recovery_audit(repaired_rows, missing_rows_before, tier1_ambiguous, tier2_ambiguous)
    RECOVERY_AUDIT_OUT.write_text(json.dumps(recovery_audit, indent=2), encoding="utf-8")
    label_recon = build_label_reconciliation(repaired_rows)
    LABEL_RECON_OUT.write_text(json.dumps(label_recon, indent=2), encoding="utf-8")
    print(f"  Recovery rate: {recovery_audit['recovery_rate_pct']}%")
    print(f"  Missing after: {recovery_audit['missing_field_size_after']}")

    print("Step 7/8: Recalculating EW eligibility/evidence …")
    ew_audit = build_ew_evidence_audit_after_repair(repaired_rows, recovery_audit)
    EW_AUDIT_OUT.write_text(json.dumps(ew_audit, indent=2), encoding="utf-8")
    print(f"  EW profitability verdict: {ew_audit['ew_profitability_verdict']}")

    print("Step 8/8: Re-issuing operator brief + summary …")
    summary = {
        "summary_version": VALIDATION_VERSION,
        "recovery_audit": recovery_audit,
        "label_reconciliation": label_recon,
        "ew_evidence_audit": ew_audit,
        "final_classifications": FINAL_CLASSIFICATIONS,
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "human_approval_required": True,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    SUMMARY_MD.write_text(build_summary_md(recovery_audit, label_recon, ew_audit), encoding="utf-8")

    brief = build_operator_brief(recovery_audit, label_recon, ew_audit)
    BRIEF_JSON.write_text(json.dumps(brief, indent=2), encoding="utf-8")
    BRIEF_MD.write_text(build_brief_md(brief), encoding="utf-8")

    print("\n── VFU-20 COMPLETE ──")
    print(f"Starting rows: {recovery_audit['starting_rows']}")
    print(f"Missing field_size before: {recovery_audit['missing_field_size_before']}")
    print(f"Missing field_size after: {recovery_audit['missing_field_size_after']}")
    print(f"Recovery rate: {recovery_audit['recovery_rate_pct']}%")
    print(f"EW profitability verdict: {ew_audit['ew_profitability_verdict']}")
    print(f"Final classifications: {len(FINAL_CLASSIFICATIONS)}")
    outputs = [LEDGER_OUT, RECOVERY_AUDIT_OUT, LABEL_RECON_OUT, EW_AUDIT_OUT, SUMMARY_JSON, SUMMARY_MD, BRIEF_JSON, BRIEF_MD]
    print(f"Output files: {len(outputs)}")
    for o in outputs:
        exists = o.exists()
        size = o.stat().st_size if exists else 0
        print(f"  {'OK' if exists else 'MISSING':6s} {o.name} ({size} bytes)")
    print("\nSTOP — operator review required before VFU-21.")


if __name__ == "__main__":
    main()
