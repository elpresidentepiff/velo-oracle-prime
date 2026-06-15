"""VFU-18: Place Data Enrichment + Dual-Lane Cockpit — DRY-RUN ONLY.

Governing law (VFU-10): No evidence becomes doctrine unless it was knowable before the race.

Hard rules (permanent):
- Does NOT mutate canonical Horse Passport
- Does NOT write Supabase
- Does NOT change live scoring or VP formula
- Does NOT change VP threshold (0.40 — UNCHANGED)
- Does NOT promote doctrine or models
- Does NOT send Telegram
- Does NOT restore Racing API
- All outputs: blocked_from_live_use=True, dry_run_only=True, human_approval_required=True
"""

from __future__ import annotations

import glob
import json
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

VALIDATION_VERSION = "VFU_18_PLACE_DATA_ENRICHMENT_V1"
VP_THRESHOLD = 0.40  # UNCHANGED — never alter

REPORTS = Path("data/reports")
RESULTS_DIR = Path("data/results")

# Outcome class strings (mirrors VFU-17)
WIN = "WIN"
PLACE = "PLACE"
FRAME = "FRAME"
MISS = "MISS"
UNKNOWN_RESULT = "UNKNOWN_RESULT"

# Place signal strings (mirrors VFU-17)
PLACE_SIGNAL_STRONG = "PLACE_SIGNAL_STRONG"
PLACE_SIGNAL_MODERATE = "PLACE_SIGNAL_MODERATE"
PLACE_SIGNAL_WEAK = "PLACE_SIGNAL_WEAK"
PLACE_SIGNAL_UNKNOWN = "PLACE_SIGNAL_UNKNOWN"

# Place cutoff strings (mirrors VFU-17)
PLACE_CUTOFF_UNKNOWN = "PLACE_CUTOFF_UNKNOWN"
PLACE_CUTOFF_WIN_ONLY = "PLACE_CUTOFF_WIN_ONLY"
PLACE_CUTOFF_FIELD_SIZE = "PLACE_CUTOFF_FIELD_SIZE"

# Each-way conclusion strings
EW_PROFITABLE = "EW_PROFITABLE"
EW_PLACE_PAID_WIN_MISS = "EW_PLACE_PAID_WIN_MISS"
EW_WIN_ONLY_PAID = "EW_WIN_ONLY_PAID"
EW_BOTH_MISS = "EW_BOTH_MISS"
EW_CONCLUSION_BLOCKED = "EW_CONCLUSION_BLOCKED"

# Dual-lane classification labels (10)
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

ALL_DUAL_LANE_LABELS = [
    WIN_LANE_CONFIRMED, PLACE_LANE_CONFIRMED, EACH_WAY_REVIEW,
    WIN_SIGNAL_PLACE_OUTCOME, PLACE_SIGNAL_WIN_OUTCOME,
    FALSE_WIN_SIGNAL, FALSE_PLACE_SIGNAL, PLACE_SPECIALIST,
    INSUFFICIENT_PLACE_DATA, EVENT_ONLY_UNUSABLE,
]

# Identity statuses that render a row unusable for dual-lane analysis
_BAD_IDENTITY = frozenset({
    "EVENT_ONLY", "UNRESOLVED", "UNKNOWN_IDENTITY", "UNKNOWN", "?", "",
})

# VFU-13→17 lineage facts (verified from git log and report files)
_LINEAGE = [
    {
        "vfu": "VFU-13",
        "commit": "f5a0ada",
        "title": "False-GREEN Feature Autopsy",
        "report_files": [
            "vfu_13_false_green_feature_autopsy_summary.json",
            "vfu_13_false_green_feature_autopsy_summary.md",
            "vfu_13_false_green_cases.jsonl",
        ],
        "changed_live_scoring": False,
        "mutated_passport": False,
        "wrote_supabase": False,
        "promoted_doctrine": False,
        "sent_telegram": False,
        "touched_racing_api": False,
    },
    {
        "vfu": "VFU-14",
        "commit": "dcbe13b",
        "title": "SP Data Recovery + False-GREEN Price Attribution",
        "report_files": [
            "vfu_14_false_green_sp_enriched_cases.jsonl",
            "vfu_14_sp_data_recovery_summary.json",
            "vfu_14_sp_data_recovery_summary.md",
        ],
        "changed_live_scoring": False,
        "mutated_passport": False,
        "wrote_supabase": False,
        "promoted_doctrine": False,
        "sent_telegram": False,
        "touched_racing_api": False,
    },
    {
        "vfu": "VFU-15",
        "commit": "daa5d7c",
        "title": "False-GREEN MISS Autopsy — 56 MISS cases separated and classified",
        "report_files": [
            "vfu_15_miss_cases.jsonl",
            "vfu_15_miss_autopsy_summary.json",
            "vfu_15_miss_autopsy_summary.md",
        ],
        "changed_live_scoring": False,
        "mutated_passport": False,
        "wrote_supabase": False,
        "promoted_doctrine": False,
        "sent_telegram": False,
        "touched_racing_api": False,
    },
    {
        "vfu": "VFU-16",
        "commit": "fd7da92",
        "title": "Win/Place Conversion Tribunal — mechanism split + guardrail proposal",
        "report_files": [
            "vfu_16_false_green_mechanism_split.json",
            "vfu_16_place_prob_dominant_cases.jsonl",
            "vfu_16_win_weak_place_strong_watchlist.json",
            "vfu_16_human_review_queue.json",
            "vfu_16_win_place_conversion_summary.json",
            "vfu_16_win_place_conversion_summary.md",
        ],
        "changed_live_scoring": False,
        "mutated_passport": False,
        "wrote_supabase": False,
        "promoted_doctrine": False,
        "sent_telegram": False,
        "touched_racing_api": False,
    },
    {
        "vfu": "VFU-17",
        "commit": "296c56b",
        "title": "Win/Place Position Engine — dual-lane classification + specialists",
        "report_files": [
            "vfu_17_win_place_records.jsonl",
            "vfu_17_place_specialist_candidates.json",
            "vfu_17_win_to_place_downgrades.json",
            "vfu_17_place_to_win_upgrades.json",
            "vfu_17_human_review_queue.json",
            "vfu_17_win_place_position_summary.json",
            "vfu_17_win_place_position_summary.md",
        ],
        "changed_live_scoring": False,
        "mutated_passport": False,
        "wrote_supabase": False,
        "promoted_doctrine": False,
        "sent_telegram": False,
        "touched_racing_api": False,
    },
]


# ── Helper functions ───────────────────────────────────────────────────────────


def _norm_name(name: str | None) -> str:
    return (name or "").strip().lower()


def place_cutoff(field_size) -> tuple:
    """Return (cutoff_places, confidence_label) from field size."""
    if field_size is None:
        return None, PLACE_CUTOFF_UNKNOWN
    fs = int(field_size)
    if fs <= 4:
        return 1, PLACE_CUTOFF_WIN_ONLY
    elif fs <= 7:
        return 2, PLACE_CUTOFF_FIELD_SIZE
    elif fs <= 15:
        return 3, PLACE_CUTOFF_FIELD_SIZE
    else:
        return 4, PLACE_CUTOFF_FIELD_SIZE


def place_terms_estimate(field_size) -> str:
    """Return place terms string for a given field size."""
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


def each_way_conclusion(outcome_class: str, cutoff: int | None) -> str:
    """Determine each-way outcome label."""
    if cutoff is None:
        return EW_CONCLUSION_BLOCKED
    if cutoff == 1:
        # WIN_ONLY — no place leg
        if outcome_class == WIN:
            return EW_WIN_ONLY_PAID
        return EW_BOTH_MISS
    # Place leg exists
    if outcome_class == WIN:
        return EW_PROFITABLE
    if outcome_class == PLACE:
        return EW_PLACE_PAID_WIN_MISS
    return EW_BOTH_MISS


# ── Lineage reconciliation ─────────────────────────────────────────────────────


def build_lineage_reconciliation() -> dict:
    """Verify VFU-13 → VFU-17 lineage from local report files."""
    entries = []
    all_clean = True

    for lf in _LINEAGE:
        present = []
        missing = []
        for rf in lf["report_files"]:
            p = REPORTS / rf
            if p.exists():
                present.append(rf)
            else:
                missing.append(rf)

        dirty = (
            lf["changed_live_scoring"]
            or lf["mutated_passport"]
            or lf["wrote_supabase"]
            or lf["promoted_doctrine"]
            or lf["sent_telegram"]
            or lf["touched_racing_api"]
        )
        if dirty or missing:
            all_clean = False

        entries.append({
            **lf,
            "report_files_present": present,
            "report_files_missing": missing,
            "lineage_clean": not dirty and not missing,
        })

    return {
        "lineage_version": "VFU_18_LINEAGE_RECONCILIATION_V1",
        "scope": "VFU-13 through VFU-17",
        "all_phases_clean": all_clean,
        "phases": entries,
        "verdict": "LINEAGE_CLEAN_PROCEED_TO_VFU18" if all_clean else "LINEAGE_GAPS_FOUND_STOP",
        "blocked_from_live_use": True,
        "dry_run_only": True,
    }


# ── RP field-size index ────────────────────────────────────────────────────────


def build_rp_field_index() -> dict:
    """Index field_size from RP results files (schema-A only — dict top-level)."""
    rp_files = sorted(glob.glob(str(RESULTS_DIR / "rp_results_*.json")))
    race_field_map: dict[str, dict] = {}
    files_skipped = []

    for fp in rp_files:
        try:
            raw = open(fp, encoding="utf-8").read()
            d = json.loads(raw)
        except Exception:
            files_skipped.append(fp)
            continue

        if not isinstance(d, dict):
            # Schema-B (top-level list, e.g. May 29) — no field_size available
            files_skipped.append(fp)
            continue

        for race in d.get("results", []):
            if not isinstance(race, dict):
                continue
            rid = race.get("race_id")
            runners = race.get("runners")
            fs = len(runners) if isinstance(runners, list) else 0
            if rid and fs > 0:
                race_field_map[rid] = {
                    "field_size": fs,
                    "going": race.get("going"),
                    "dist_f": race.get("dist_f"),
                    "race_name": race.get("race_name"),
                    "course": race.get("course"),
                    "date": race.get("date"),
                }

    return race_field_map


# ── Dual-lane classification ───────────────────────────────────────────────────


def classify_dual_lane_label(
    row: dict,
    specialist_set: frozenset,
    race_field_map: dict,
) -> str:
    """Assign primary dual-lane label. Ten possible values, mutually exclusive."""
    outcome_class = row.get("outcome_class") or UNKNOWN_RESULT
    vp = row.get("vp") or 0.0
    place_signal = row.get("place_signal_strength") or PLACE_SIGNAL_UNKNOWN
    identity_status = (row.get("identity_status") or "").strip()
    horse_name = _norm_name(row.get("horse_name"))
    race_id = row.get("race_id") or ""

    # 1. Unusable identity
    if identity_status in _BAD_IDENTITY or not horse_name or horse_name in ("?", "unknown"):
        return EVENT_ONLY_UNUSABLE

    # 2. Outcome unknown
    if outcome_class == UNKNOWN_RESULT:
        return INSUFFICIENT_PLACE_DATA

    # Get field size for this race
    field_info = race_field_map.get(race_id, {})
    field_size = field_info.get("field_size")

    is_win = outcome_class == WIN
    is_placed_not_won = outcome_class == PLACE
    is_miss_or_frame = outcome_class in (MISS, FRAME)
    is_place_signal_active = place_signal in (PLACE_SIGNAL_STRONG, PLACE_SIGNAL_MODERATE)
    vp_fires = vp >= VP_THRESHOLD

    # 3. Known place specialist (takes precedence over signal labels)
    if horse_name in specialist_set:
        return PLACE_SPECIALIST

    # 4-7. VP signal fires (≥ 0.40)
    if vp_fires:
        if is_win:
            return WIN_LANE_CONFIRMED
        if is_placed_not_won:
            if field_size is not None and field_size >= 5:
                return EACH_WAY_REVIEW
            return WIN_SIGNAL_PLACE_OUTCOME
        return FALSE_WIN_SIGNAL

    # 8-10. Place signal active but VP doesn't fire
    if is_place_signal_active:
        if is_win:
            return PLACE_SIGNAL_WIN_OUTCOME
        if is_placed_not_won:
            return PLACE_LANE_CONFIRMED
        return FALSE_PLACE_SIGNAL

    return INSUFFICIENT_PLACE_DATA


# ── Row enrichment ─────────────────────────────────────────────────────────────


def enrich_row(
    row: dict,
    specialist_set: frozenset,
    race_field_map: dict,
) -> dict:
    """Enrich a VFU-17 row with field_size, place terms, EW conclusion, dual-lane label."""
    race_id = row.get("race_id") or ""
    outcome_class = row.get("outcome_class") or UNKNOWN_RESULT

    field_info = race_field_map.get(race_id, {})
    field_size = field_info.get("field_size")
    going = field_info.get("going")
    dist_f = field_info.get("dist_f")

    cutoff, cutoff_conf = place_cutoff(field_size)
    terms = place_terms_estimate(field_size)
    ew_conc = each_way_conclusion(outcome_class, cutoff)
    dual_label = classify_dual_lane_label(row, specialist_set, race_field_map)

    return {
        **row,
        # Field-size enrichment
        "rp_field_size": field_size,
        "rp_going": going,
        "rp_dist_f": dist_f,
        "field_size_source": "RP_RESULTS" if field_size is not None else "UNKNOWN",
        # Place terms
        "place_cutoff_vfu18": cutoff,
        "place_cutoff_confidence_vfu18": cutoff_conf,
        "place_terms_estimate": terms,
        # Each-way
        "each_way_conclusion": ew_conc,
        "each_way_conclusion_blocked": field_size is None,
        # Dual-lane
        "dual_lane_label": dual_label,
        # VFU-18 safety locks
        "vfu18_validation_version": VALIDATION_VERSION,
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "human_approval_required": True,
    }


# ── Output builders ────────────────────────────────────────────────────────────


def build_place_specialist_watchlist(enriched_rows: list, specialist_set: frozenset) -> dict:
    """Collect all PLACE_SPECIALIST rows + meta."""
    entries = [r for r in enriched_rows if r.get("dual_lane_label") == PLACE_SPECIALIST]

    by_name: dict[str, list] = defaultdict(list)
    for r in entries:
        by_name[r.get("horse_name", "?")].append(r)

    summaries = []
    for name, rows in by_name.items():
        summaries.append({
            "horse_name": name,
            "appearances": len(rows),
            "dual_lane_label": PLACE_SPECIALIST,
            "avg_vp": round(sum(r.get("vp") or 0 for r in rows) / len(rows), 4),
            "outcomes": Counter(r.get("outcome") for r in rows),
            "courses": sorted({r.get("course") for r in rows if r.get("course")}),
            "rp_field_sizes": sorted({r.get("rp_field_size") for r in rows if r.get("rp_field_size") is not None}),
            "blocked_from_live_use": True,
            "dry_run_only": True,
            "human_approval_required": True,
            "vfu18_validation_version": VALIDATION_VERSION,
        })

    return {
        "watchlist_version": "VFU_18_PLACE_SPECIALIST_WATCHLIST_V1",
        "total_specialists": len(by_name),
        "total_rows": len(entries),
        "named_specialists": sorted(specialist_set),
        "entries": summaries,
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "vfu18_validation_version": VALIDATION_VERSION,
    }


def build_win_to_place_downgrades(enriched_rows: list) -> list:
    """Rows where VP fired (≥ 0.40) but horse only placed, not won."""
    target_labels = {EACH_WAY_REVIEW, WIN_SIGNAL_PLACE_OUTCOME}
    rows = [r for r in enriched_rows if r.get("dual_lane_label") in target_labels]
    return [
        {
            "ledger_id": r.get("ledger_id"),
            "horse_name": r.get("horse_name"),
            "race_id": r.get("race_id"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "vp": r.get("vp"),
            "outcome": r.get("outcome"),
            "dual_lane_label": r.get("dual_lane_label"),
            "rp_field_size": r.get("rp_field_size"),
            "place_terms_estimate": r.get("place_terms_estimate"),
            "each_way_conclusion": r.get("each_way_conclusion"),
            "place_signal_strength": r.get("place_signal_strength"),
            "blocked_from_live_use": True,
            "dry_run_only": True,
            "human_approval_required": True,
            "vfu18_validation_version": VALIDATION_VERSION,
        }
        for r in rows
    ]


def build_place_to_win_upgrades(enriched_rows: list) -> list:
    """Place signal fired (VP < 0.40) but horse actually won."""
    rows = [r for r in enriched_rows if r.get("dual_lane_label") == PLACE_SIGNAL_WIN_OUTCOME]
    return [
        {
            "ledger_id": r.get("ledger_id"),
            "horse_name": r.get("horse_name"),
            "race_id": r.get("race_id"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "vp": r.get("vp"),
            "outcome": r.get("outcome"),
            "dual_lane_label": r.get("dual_lane_label"),
            "place_signal_strength": r.get("place_signal_strength"),
            "rp_field_size": r.get("rp_field_size"),
            "upgrade_signal": "PLACE_SIGNAL_ACTIVE_AT_LOW_VP_CAUGHT_WIN",
            "blocked_from_live_use": True,
            "dry_run_only": True,
            "human_approval_required": True,
            "vfu18_validation_version": VALIDATION_VERSION,
        }
        for r in rows
    ]


def build_place_data_quality_gaps(enriched_rows: list) -> dict:
    """Report on rows with missing or insufficient place data."""
    unknown_field = [r for r in enriched_rows if r.get("field_size_source") == "UNKNOWN"]
    ew_blocked = [r for r in enriched_rows if r.get("each_way_conclusion_blocked")]
    insufficient = [r for r in enriched_rows if r.get("dual_lane_label") == INSUFFICIENT_PLACE_DATA]
    event_only = [r for r in enriched_rows if r.get("dual_lane_label") == EVENT_ONLY_UNUSABLE]

    return {
        "gap_report_version": "VFU_18_PLACE_DATA_QUALITY_GAPS_V1",
        "total_rows": len(enriched_rows),
        "rows_missing_field_size": len(unknown_field),
        "rows_ew_conclusion_blocked": len(ew_blocked),
        "rows_insufficient_place_data": len(insufficient),
        "rows_event_only_unusable": len(event_only),
        "field_size_coverage_pct": round(
            (len(enriched_rows) - len(unknown_field)) / max(len(enriched_rows), 1) * 100, 1
        ),
        "gap_recommendations": [
            "Run full RP results capture for dates without rp_results JSON to extend field_size coverage.",
            "Schema-B files (list top-level) do not carry field_size — re-parse or skip for EW analysis.",
            "EVENT_ONLY rows cannot be classified — identity enrichment required before further use.",
        ],
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "vfu18_validation_version": VALIDATION_VERSION,
    }


def build_dual_lane_cockpit(enriched_rows: list, race_field_map: dict) -> dict:
    """Aggregate dual-lane cockpit — top-level signal summary."""
    label_dist = Counter(r.get("dual_lane_label") for r in enriched_rows)
    ew_dist = Counter(r.get("each_way_conclusion") for r in enriched_rows)

    vp_rows = [r for r in enriched_rows if (r.get("vp") or 0) >= VP_THRESHOLD]
    win_lane = [r for r in vp_rows if r.get("dual_lane_label") == WIN_LANE_CONFIRMED]
    place_lane = [r for r in vp_rows if r.get("dual_lane_label") in (EACH_WAY_REVIEW, WIN_SIGNAL_PLACE_OUTCOME)]
    false_win = [r for r in vp_rows if r.get("dual_lane_label") == FALSE_WIN_SIGNAL]
    specialist_rows = [r for r in enriched_rows if r.get("dual_lane_label") == PLACE_SPECIALIST]
    place_signal_rows = [
        r for r in enriched_rows
        if r.get("dual_lane_label") in (PLACE_LANE_CONFIRMED, PLACE_SIGNAL_WIN_OUTCOME, FALSE_PLACE_SIGNAL)
    ]
    ew_profitable = [r for r in enriched_rows if r.get("each_way_conclusion") == EW_PROFITABLE]
    ew_place_paid = [r for r in enriched_rows if r.get("each_way_conclusion") == EW_PLACE_PAID_WIN_MISS]

    rows_with_fs = sum(1 for r in enriched_rows if r.get("rp_field_size") is not None)
    total = len(enriched_rows)

    return {
        "cockpit_version": "VFU_18_DUAL_LANE_COCKPIT_V1",
        "total_rows": total,
        "vp_threshold": VP_THRESHOLD,
        "field_size_coverage": {
            "rows_with_field_size": rows_with_fs,
            "rows_unknown": total - rows_with_fs,
            "coverage_pct": round(rows_with_fs / max(total, 1) * 100, 1),
            "rp_races_indexed": len(race_field_map),
        },
        "dual_lane_distribution": {k: label_dist.get(k, 0) for k in ALL_DUAL_LANE_LABELS},
        "win_lane_summary": {
            "total_vp_fires": len(vp_rows),
            "win_lane_confirmed": len(win_lane),
            "place_lane_from_vp": len(place_lane),
            "false_win_signals": len(false_win),
            "win_hit_rate": round(len(win_lane) / max(len(vp_rows), 1) * 100, 1),
            "vp_place_conversion_rate": round(
                (len(win_lane) + len(place_lane)) / max(len(vp_rows), 1) * 100, 1
            ),
        },
        "place_lane_summary": {
            "place_signal_active_rows": len(place_signal_rows),
            "place_specialist_rows": len(specialist_rows),
            "place_lane_confirmed": label_dist.get(PLACE_LANE_CONFIRMED, 0),
            "place_signal_win_outcome": label_dist.get(PLACE_SIGNAL_WIN_OUTCOME, 0),
            "false_place_signals": label_dist.get(FALSE_PLACE_SIGNAL, 0),
        },
        "each_way_summary": {
            "ew_profitable": len(ew_profitable),
            "ew_place_paid_win_miss": len(ew_place_paid),
            "ew_win_only_paid": ew_dist.get(EW_WIN_ONLY_PAID, 0),
            "ew_both_miss": ew_dist.get(EW_BOTH_MISS, 0),
            "ew_conclusion_blocked": ew_dist.get(EW_CONCLUSION_BLOCKED, 0),
        },
        "key_findings": [
            f"VP >= 0.40 fired on {len(vp_rows)} rows.",
            f"WIN_LANE_CONFIRMED: {len(win_lane)} rows ({round(len(win_lane)/max(len(vp_rows),1)*100,1)}% of VP fires).",
            f"EACH_WAY_REVIEW (placed, field_size>=5): {label_dist.get(EACH_WAY_REVIEW, 0)} rows.",
            f"WIN_SIGNAL_PLACE_OUTCOME (placed, field unknown/<5): {label_dist.get(WIN_SIGNAL_PLACE_OUTCOME, 0)} rows.",
            f"FALSE_WIN_SIGNAL (VP fires, MISS/FRAME): {len(false_win)} rows.",
            f"PLACE_SPECIALIST: {len(specialist_rows)} rows from {len({r.get('horse_name') for r in specialist_rows})} horses.",
            f"EACH_WAY profitable (both legs win): {len(ew_profitable)} rows.",
            f"Field size coverage: {round(rows_with_fs/max(total,1)*100,1)}% — {total-rows_with_fs} rows EW conclusion blocked.",
        ],
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "human_approval_required": True,
        "vfu18_validation_version": VALIDATION_VERSION,
    }


# ── Summary builder ────────────────────────────────────────────────────────────

FINAL_CLASSIFICATIONS = [
    "VFU_18_PLACE_DATA_ENRICHMENT_COMPLETE",
    "VFU_LINEAGE_RECONCILED",
    "DUAL_LANE_CLASSIFICATIONS_CREATED",
    "PLACE_SPECIALIST_WATCHLIST_CREATED",
    "WIN_TO_PLACE_DOWNGRADES_REPORTED",
    "PLACE_TO_WIN_UPGRADES_REPORTED",
    "FIELD_SIZE_GAPS_REPORTED",
    "NO_STAKING_INSTRUCTIONS_CREATED",
    "NO_LIVE_DOCTRINE_PROMOTION",
    "NO_VP_THRESHOLD_CHANGE",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "NO_LIVE_SCORING_CHANGE",
    "NO_SUPABASE_WRITES",
    "NO_MODEL_PROMOTION",
    "NO_TELEGRAM_SEND",
    "NO_RACING_API_RESTORATION",
]


def build_summary(
    enriched_rows: list,
    lineage: dict,
    cockpit: dict,
    n_specialist_watchlist: int,
    n_win_to_place: int,
    n_place_to_win: int,
) -> dict:
    label_dist = {k: 0 for k in ALL_DUAL_LANE_LABELS}
    for r in enriched_rows:
        lbl = r.get("dual_lane_label")
        if lbl in label_dist:
            label_dist[lbl] += 1

    return {
        "summary_version": VALIDATION_VERSION,
        "total_vfu17_rows_loaded": len(enriched_rows),
        "total_enriched_rows": len(enriched_rows),
        "lineage_status": lineage["verdict"],
        "dual_lane_distribution": label_dist,
        "field_size_coverage_pct": cockpit["field_size_coverage"]["coverage_pct"],
        "win_lane_hit_rate_pct": cockpit["win_lane_summary"]["win_hit_rate"],
        "vp_place_conversion_pct": cockpit["win_lane_summary"]["vp_place_conversion_rate"],
        "each_way_profitable_count": cockpit["each_way_summary"]["ew_profitable"],
        "specialist_watchlist_entries": n_specialist_watchlist,
        "win_to_place_downgrades": n_win_to_place,
        "place_to_win_upgrades": n_place_to_win,
        "vp_threshold": VP_THRESHOLD,
        "final_classifications": FINAL_CLASSIFICATIONS,
        "blocked_from_live_use": True,
        "dry_run_only": True,
        "human_approval_required": True,
        "vfu18_validation_version": VALIDATION_VERSION,
    }


def build_summary_md(summary: dict, cockpit: dict) -> str:
    dist = summary["dual_lane_distribution"]
    findings = cockpit.get("key_findings", [])
    return textwrap.dedent(f"""
        # VFU-18: Place Data Enrichment + Dual-Lane Cockpit

        **Validation version:** {VALIDATION_VERSION}
        **Status:** DRY-RUN ONLY — blocked_from_live_use=True

        ## Field-Size Coverage
        - RP results races indexed: {cockpit['field_size_coverage']['rp_races_indexed']}
        - VFU-17 rows matched: {cockpit['field_size_coverage']['rows_with_field_size']} / {summary['total_enriched_rows']} ({cockpit['field_size_coverage']['coverage_pct']}%)
        - Rows with EW conclusion blocked: {cockpit['each_way_summary']['ew_conclusion_blocked']}

        ## Dual-Lane Distribution
        | Label | Count |
        |---|---|
        {"".join(f"| {k} | {v} |{chr(10)}" for k, v in dist.items())}
        ## Win Lane
        - VP >= 0.40 fires: {cockpit['win_lane_summary']['total_vp_fires']}
        - WIN_LANE_CONFIRMED: {cockpit['win_lane_summary']['win_lane_confirmed']} ({cockpit['win_lane_summary']['win_hit_rate']}%)
        - VP place conversion (WIN + PLACED): {cockpit['win_lane_summary']['vp_place_conversion_rate']}%

        ## Each-Way Summary
        - EW profitable (both legs): {cockpit['each_way_summary']['ew_profitable']}
        - EW place paid, win missed: {cockpit['each_way_summary']['ew_place_paid_win_miss']}
        - EW conclusion blocked (no field size): {cockpit['each_way_summary']['ew_conclusion_blocked']}

        ## Key Findings
        {"".join(f"- {f}{chr(10)}" for f in findings)}
        ## Lineage
        - Scope: VFU-13 → VFU-17
        - Verdict: {summary['lineage_status']}

        ## Final Classifications
        {chr(10).join(f"- {c}" for c in FINAL_CLASSIFICATIONS)}

        ## Hard Rules
        - VP threshold: {VP_THRESHOLD} (UNCHANGED)
        - No live doctrine promotion
        - No Passport mutation
        - No Supabase writes
        - No Racing API restoration
        - No Telegram send
    """).strip()


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)

    # Step 1: Lineage reconciliation
    print("Step 1: Lineage reconciliation VFU-13 → VFU-17 …")
    lineage = build_lineage_reconciliation()
    (REPORTS / "vfu_18_lineage_reconciliation.json").write_text(
        json.dumps(lineage, indent=2), encoding="utf-8"
    )
    recon_md_lines = ["# VFU-18 Lineage Reconciliation\n"]
    recon_md_lines.append(f"**Verdict:** {lineage['verdict']}\n")
    for phase in lineage["phases"]:
        status = "CLEAN" if phase["lineage_clean"] else "GAPS FOUND"
        recon_md_lines.append(
            f"- **{phase['vfu']}** ({phase['commit']}): {phase['title']} — {status}"
        )
        if phase["report_files_missing"]:
            for mf in phase["report_files_missing"]:
                recon_md_lines.append(f"  - MISSING: {mf}")
    (REPORTS / "vfu_18_lineage_reconciliation.md").write_text(
        "\n".join(recon_md_lines), encoding="utf-8"
    )
    print(f"  Lineage verdict: {lineage['verdict']}")
    if lineage["verdict"] != "LINEAGE_CLEAN_PROCEED_TO_VFU18":
        print("  STOP: lineage gaps found — see vfu_18_lineage_reconciliation.json")
        return

    # Step 2: Build RP field-size index
    print("Step 2: Building RP field-size index …")
    race_field_map = build_rp_field_index()
    print(f"  Indexed {len(race_field_map)} races with field_size from RP results")

    # Step 3: Load VFU-17 records
    print("Step 3: Loading VFU-17 win_place_records.jsonl …")
    vfu17_path = REPORTS / "vfu_17_win_place_records.jsonl"
    if not vfu17_path.exists():
        raise FileNotFoundError(f"VFU-17 records not found: {vfu17_path}")
    vfu17_rows = [
        json.loads(ln)
        for ln in vfu17_path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    print(f"  Loaded {len(vfu17_rows)} VFU-17 rows")

    # Step 4: Load specialist candidates
    print("Step 4: Loading VFU-17 place specialist candidates …")
    spec_path = REPORTS / "vfu_17_place_specialist_candidates.json"
    if not spec_path.exists():
        raise FileNotFoundError(f"Specialist candidates not found: {spec_path}")
    spec_candidates = json.loads(spec_path.read_text(encoding="utf-8"))
    specialist_set = frozenset(
        _norm_name(c.get("horse_name")) for c in spec_candidates if c.get("horse_name")
    )
    print(f"  Loaded {len(specialist_set)} specialist names")

    # Step 5: Enrich all rows
    print("Step 5: Enriching rows with field_size, place terms, EW conclusion, dual-lane label …")
    enriched_rows = [enrich_row(r, specialist_set, race_field_map) for r in vfu17_rows]

    label_dist = Counter(r.get("dual_lane_label") for r in enriched_rows)
    fs_matched = sum(1 for r in enriched_rows if r.get("rp_field_size") is not None)
    print(f"  Field-size matched: {fs_matched}/{len(enriched_rows)} = {fs_matched/len(enriched_rows)*100:.1f}%")
    print("  Dual-lane distribution:")
    for lbl in ALL_DUAL_LANE_LABELS:
        print(f"    {lbl}: {label_dist.get(lbl, 0)}")

    # Step 6: Write dual_lane_records.jsonl
    print("Step 6: Writing vfu_18_dual_lane_records.jsonl …")
    dual_lane_path = REPORTS / "vfu_18_dual_lane_records.jsonl"
    dual_lane_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in enriched_rows) + "\n",
        encoding="utf-8",
    )
    print(f"  Written {len(enriched_rows)} rows")

    # Step 7: Place specialist watchlist
    print("Step 7: Building place specialist watchlist …")
    watchlist = build_place_specialist_watchlist(enriched_rows, specialist_set)
    (REPORTS / "vfu_18_place_specialist_watchlist.json").write_text(
        json.dumps(watchlist, indent=2), encoding="utf-8"
    )
    print(f"  Watchlist: {watchlist['total_specialists']} specialists, {watchlist['total_rows']} rows")

    # Step 8: Win-to-place downgrades
    print("Step 8: Building win-to-place downgrades …")
    win_to_place = build_win_to_place_downgrades(enriched_rows)
    (REPORTS / "vfu_18_win_to_place_downgrades.json").write_text(
        json.dumps(win_to_place, indent=2), encoding="utf-8"
    )
    print(f"  Win-to-place downgrades: {len(win_to_place)}")

    # Step 9: Place-to-win upgrades
    print("Step 9: Building place-to-win upgrades …")
    place_to_win = build_place_to_win_upgrades(enriched_rows)
    (REPORTS / "vfu_18_place_to_win_upgrades.json").write_text(
        json.dumps(place_to_win, indent=2), encoding="utf-8"
    )
    print(f"  Place-to-win upgrades: {len(place_to_win)}")

    # Step 10: Place data quality gaps
    print("Step 10: Building place data quality gaps report …")
    gaps = build_place_data_quality_gaps(enriched_rows)
    (REPORTS / "vfu_18_place_data_quality_gaps.json").write_text(
        json.dumps(gaps, indent=2), encoding="utf-8"
    )
    print(f"  Rows missing field_size: {gaps['rows_missing_field_size']}")

    # Step 11: Dual-lane cockpit
    print("Step 11: Building dual-lane cockpit …")
    cockpit = build_dual_lane_cockpit(enriched_rows, race_field_map)
    (REPORTS / "vfu_18_dual_lane_cockpit.json").write_text(
        json.dumps(cockpit, indent=2), encoding="utf-8"
    )
    print(f"  WIN hit rate: {cockpit['win_lane_summary']['win_hit_rate']}%")
    print(f"  EW profitable: {cockpit['each_way_summary']['ew_profitable']}")

    # Step 12: Summary JSON + MD
    print("Step 12: Writing summary …")
    summary = build_summary(
        enriched_rows,
        lineage,
        cockpit,
        n_specialist_watchlist=watchlist["total_specialists"],
        n_win_to_place=len(win_to_place),
        n_place_to_win=len(place_to_win),
    )
    (REPORTS / "vfu_18_place_data_enrichment_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (REPORTS / "vfu_18_place_data_enrichment_summary.md").write_text(
        build_summary_md(summary, cockpit), encoding="utf-8"
    )

    print("\n── VFU-18 COMPLETE ──")
    print(f"Total enriched rows: {len(enriched_rows)}")
    print(f"Lineage: {lineage['verdict']}")
    print(f"Field-size coverage: {cockpit['field_size_coverage']['coverage_pct']}%")
    print(f"VP fires: {cockpit['win_lane_summary']['total_vp_fires']}")
    print(f"  WIN_LANE_CONFIRMED: {cockpit['win_lane_summary']['win_lane_confirmed']}")
    print(f"  EACH_WAY_REVIEW: {label_dist.get(EACH_WAY_REVIEW, 0)}")
    print(f"  FALSE_WIN_SIGNAL: {cockpit['win_lane_summary']['false_win_signals']}")
    print(f"Final classifications: {len(FINAL_CLASSIFICATIONS)}")
    print("\nOutputs:")
    outputs = [
        "vfu_18_lineage_reconciliation.json",
        "vfu_18_lineage_reconciliation.md",
        "vfu_18_dual_lane_records.jsonl",
        "vfu_18_place_specialist_watchlist.json",
        "vfu_18_win_to_place_downgrades.json",
        "vfu_18_place_to_win_upgrades.json",
        "vfu_18_place_data_quality_gaps.json",
        "vfu_18_dual_lane_cockpit.json",
        "vfu_18_place_data_enrichment_summary.json",
        "vfu_18_place_data_enrichment_summary.md",
    ]
    for o in outputs:
        p = REPORTS / o
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        print(f"  {'OK' if exists else 'MISSING':6s} {o} ({size} bytes)")


if __name__ == "__main__":
    main()
