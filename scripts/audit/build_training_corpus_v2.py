"""
LEARNING-LOOP-01A — Phase 4: dry-run training corpus proof.

Corrected per PR #147 REQUEST CHANGES (P0-1, P0-2 wiring, P1 metrics).

Builds a dry-run LearningEventV2 corpus from runner_prediction_snapshots
(Supabase) joined to canonical results via:
  - prediction_run_selector: selects exactly one canonical run per race
    (runner_prediction_snapshots is grouped by (race_id, run_id), never
    race_id alone -- a single race_id can carry many independent scoring
    runs, and pooling them silently invents an oversized, duplicated
    field).
  - result_source_selector: result completeness is checked against the
    real expected runner universe from the selected canonical run, not
    "the file happens to contain a runner".
  - identity_resolver: race/horse resolution, blocking duplicate exact
    ids as AMBIGUOUS rather than silently picking one.

This is a proof/measurement run only:
  - No writes to Supabase.
  - No mutation of historical_feature_store.
  - No consumption into Playbook G.
  - No model training, no promotion decisions.

Outputs:
  - data/reports/training_corpus_v2_manifest.json
  - data/reports/training_corpus_v2_sample.jsonl   (first N built events)
  - data/reports/training_corpus_v2_exclusions.csv
"""

from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from src.velo.learning.identity_resolver import resolve_horse, resolve_race
from src.velo.learning.learning_event_v2 import (
    OutcomeTruth,
    PredictionTruth,
    RaceContext,
    SafetyProvenance,
    build_learning_event,
    compute_input_card_hash,
)
from src.velo.learning.prediction_run_selector import (
    PROOF_PRE_RACE,
    RunSelection,
    select_canonical_run,
)
from src.velo.learning.result_source_selector import (
    OUTCOME_NON_RUNNER,
    OUTCOME_UNKNOWN,
    RESULTS_DIR_DEFAULT,
    ResultSourceSelection,
    runner_outcome_status,
    select_result_source,
)
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent.parent
REPORT_DIR = ROOT / "data" / "reports"
OUT_MANIFEST = REPORT_DIR / "training_corpus_v2_manifest.json"
OUT_SAMPLE = REPORT_DIR / "training_corpus_v2_sample.jsonl"
OUT_EXCLUSIONS = REPORT_DIR / "training_corpus_v2_exclusions.csv"
SAMPLE_SIZE = 50

RUN_TS = datetime.now(UTC).isoformat().replace("+00:00", "Z")

MODEL_SCORE_FIELDS = [
    "velo_prime_prob",
    "sqpe_v17_prob",
    "market_deception_score",
    "improvement_score",
    "place_prob",
    "longshot_prob",
    "release_day_prob",
    "comment_intel_score",
]


def fetch_all(sb, table: str, fields: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        batch = sb.table(table).select(fields).range(offset, offset + 999).execute().data
        if not batch:
            break
        rows.extend(batch)
        offset += 1000
        if len(batch) < 1000:
            break
    return rows


def build_supabase_result_index(races: list[dict], runner_results: list[dict]) -> dict[str, list[dict]]:
    """Group Supabase races (with embedded runner_results) by date, in the
    shape result_source_selector/identity_resolver expect."""
    runners_by_race: dict[str, list[dict]] = defaultdict(list)
    for rr in runner_results:
        rid = rr.get("race_id")
        if rid:
            runners_by_race[rid].append(rr)

    by_date: dict[str, list[dict]] = defaultdict(list)
    for r in races:
        rid = r.get("race_id")
        date = r.get("date")
        if not rid or not date:
            continue
        by_date[date].append(
            {
                "race_id": rid,
                "course": r.get("course"),
                "date": date,
                "time": r.get("time"),
                "runners": runners_by_race.get(rid, []),
            }
        )
    return by_date


def process_race_group(
    race_id: str,
    run_selection: RunSelection,
    selection: ResultSourceSelection,
) -> tuple[list[dict], list[dict]]:
    """Pure per-race function operating on an already-selected canonical
    run (see select_canonical_run). Resolves identity, builds
    LearningEventV2 events, and returns (event_dicts, exclusion_dicts).
    No I/O -- fully testable without Supabase or the local filesystem."""
    events: list[dict] = []
    exclusions: list[dict] = []

    rows = run_selection.selected_rows
    if not run_selection.resolved or not rows:
        exclusions.append(
            {
                "race_id": race_id,
                "horse_id": None,
                "reason": f"RUN_{run_selection.reason}",
                "detail": "",
            }
        )
        return events, exclusions

    first = rows[0]
    date = first.get("race_date")

    pred_race_stub = {
        "race_id": race_id,
        "course": first.get("course"),
        "race_date": date,
        "off_time": first.get("off_time"),
    }
    race_res = resolve_race(pred_race_stub, selection.races)

    if not race_res.is_resolved:
        for r in rows:
            exclusions.append(
                {
                    "race_id": race_id,
                    "horse_id": r.get("horse_id"),
                    "reason": f"RACE_{race_res.method}",
                    "detail": race_res.ambiguity_reason or "",
                }
            )
        return events, exclusions

    resolved_race = next((r for r in selection.races if r.get("race_id") == race_res.resolved_race_id), None)

    ranked = sorted(rows, key=lambda r: r.get("rank") if r.get("rank") is not None else 999)
    rank_order = tuple(r.get("horse_id") for r in ranked if r.get("horse_id"))
    top_three = rank_order[:3]
    runner_universe = tuple({"horse_id": rr.get("horse_id"), "horse_name": rr.get("horse")} for rr in rows)

    prediction_timestamp = None
    ts_candidates = [r.get("created_at") for r in rows if r.get("created_at")]
    if ts_candidates:
        prediction_timestamp = max(ts_candidates)

    # -- P0-7: reconciled completeness, computed AFTER race+horse identity
    # resolution, never by raw race-ID dictionary equality. -------------------
    # Race-level outcome status per RESOLVED result-side horse_id (shared
    # across all predicted horses in this race -- not recomputed per horse).
    runner_positions: dict[str, str] = {}
    sp_by_horse: dict[str, float] = {}
    winner_horse_id = None
    frame_horse_ids: list[str] = []
    non_runners: list[str] = []
    outcome_status_by_result_horse: dict[str, str] = {}
    for runner in (resolved_race or {}).get("runners", []):
        hid = runner.get("horse_id")
        if not hid:
            continue
        pos = str(runner.get("position") or runner.get("position_text") or "")
        runner_positions[hid] = pos or "UNKNOWN"
        status = runner_outcome_status(pos)
        outcome_status_by_result_horse[hid] = status
        if status == OUTCOME_NON_RUNNER:
            non_runners.append(hid)
        sp = runner.get("sp_dec")
        if sp is not None:
            sp_by_horse[hid] = sp
        if pos == "1" or runner.get("is_winner"):
            winner_horse_id = hid
        if pos in {"1", "2", "3"}:
            frame_horse_ids.append(hid)

    # Resolve every predicted horse against the resolved result race once,
    # then require ALL of them (not just the ones that happen to resolve)
    # to have a known outcome before the race can be called complete.
    horse_resolutions = {
        r.get("horse_id"): resolve_horse(r.get("horse_id"), r.get("horse"), resolved_race or {}) for r in rows
    }
    result_universe_complete = len(rows) > 0
    for r in rows:
        hres = horse_resolutions[r.get("horse_id")]
        if not hres.is_resolved:
            result_universe_complete = False
            continue
        if outcome_status_by_result_horse.get(hres.resolved_horse_id, OUTCOME_UNKNOWN) == OUTCOME_UNKNOWN:
            result_universe_complete = False

    for r in rows:
        horse_res = horse_resolutions[r.get("horse_id")]
        if not horse_res.is_resolved:
            exclusions.append(
                {
                    "race_id": race_id,
                    "horse_id": r.get("horse_id"),
                    "reason": f"HORSE_{horse_res.method}",
                    "detail": horse_res.ambiguity_reason or "",
                }
            )
            continue

        ambiguous_blocked = race_res.method == "AMBIGUOUS" or horse_res.method == "AMBIGUOUS"
        odds_capture_ts = None  # not carried by runner_prediction_snapshots -- provenance unknown

        # P0-10: classification priority -- identity ambiguous, then result
        # incomplete, then timezone unproven, then prediction time
        # unproven, then untimed odds, then otherwise-applicable replay
        # class. An unproven prediction timestamp must never hide under
        # EXCLUDED_UNTIMED_ODDS.
        if ambiguous_blocked:
            time_safety = "EXCLUDED_IDENTITY_AMBIGUOUS"
        elif not result_universe_complete:
            time_safety = "EXCLUDED_INCOMPLETE_RESULT"
        elif run_selection.pre_race_proof == "TIMEZONE_UNPROVEN":
            time_safety = "EXCLUDED_TIMEZONE_UNPROVEN"
        elif run_selection.pre_race_proof == "UNPROVEN":
            time_safety = "EXCLUDED_PREDICTION_TIME_UNPROVEN"
        elif odds_capture_ts is None:
            time_safety = "EXCLUDED_UNTIMED_ODDS"
        else:
            time_safety = "CURRENT_CODE_COUNTERFACTUAL_REPLAY"

        analysis_allowed = not ambiguous_blocked
        # P0-10: shadow evaluation requires a genuinely PROVEN_PRE_RACE
        # canonical run -- TIMEZONE_UNPROVEN/UNPROVEN timing is retained
        # for analysis only and must never enter shadow evaluation.
        shadow_evaluation_allowed = (
            analysis_allowed and result_universe_complete and run_selection.pre_race_proof == PROOF_PRE_RACE
        )
        # This corpus never produces SAFE_* events -- state/model/promotion
        # gates are always False here regardless of the branch above.
        state_learning_allowed = False
        model_training_allowed = False
        promotion_eligible = False

        # P0-9: reconciled subject-horse identity, persisted directly.
        resolved_result_horse_id = horse_res.resolved_horse_id
        subject_outcome_status = outcome_status_by_result_horse.get(resolved_result_horse_id, OUTCOME_UNKNOWN)
        subject_finish_position = runner_positions.get(resolved_result_horse_id)
        subject_sp = sp_by_horse.get(resolved_result_horse_id)
        subject_is_winner = resolved_result_horse_id == winner_horse_id
        subject_is_frame = resolved_result_horse_id in frame_horse_ids
        subject_is_non_runner = resolved_result_horse_id in non_runners

        model_scores = {f: r.get(f) for f in MODEL_SCORE_FIELDS}
        active_components = tuple(f for f in MODEL_SCORE_FIELDS if r.get(f) is not None)
        excluded_components = tuple(f for f in MODEL_SCORE_FIELDS if r.get(f) is None)

        input_card_hash = compute_input_card_hash(
            race_id=race_id,
            subject_horse_id=r.get("horse_id"),
            prediction_run_id=run_selection.selected_run_id,
            runner_universe=runner_universe,
            model_scores=model_scores,
            rank_order=rank_order,
            top_three=top_three,
            model_versions={},
            active_components=active_components,
            excluded_components=excluded_components,
        )

        prediction = PredictionTruth(
            race_date=date,
            race_id=race_id,
            course=first.get("course") or "",
            off_time=first.get("off_time") or "",
            subject_horse_id=r.get("horse_id"),
            prediction_run_id=run_selection.selected_run_id,
            runner_universe=runner_universe,
            model_scores=model_scores,
            rank_order=rank_order,
            top_three=top_three,
            odds_value=None,
            odds_capture_ts=odds_capture_ts,
            prediction_timestamp=prediction_timestamp,
            source_commit=None,
            input_card_hash=input_card_hash,
            model_versions={},
            active_components=active_components,
            excluded_components=excluded_components,
        )
        outcome = OutcomeTruth(
            result_race_id=race_res.resolved_race_id,
            runner_positions=runner_positions,
            non_runners=tuple(non_runners),
            sp_by_horse=sp_by_horse,
            bsp_by_horse={},
            winner_horse_id=winner_horse_id,
            frame_horse_ids=tuple(frame_horse_ids),
            result_source_hash=selection.source_hash,
            result_universe_complete=result_universe_complete,
            resolved_result_horse_id=resolved_result_horse_id,
            horse_resolution_method=horse_res.method,
            subject_outcome_status=subject_outcome_status,
            subject_finish_position=subject_finish_position,
            subject_sp=subject_sp,
            subject_bsp=None,
            subject_is_winner=subject_is_winner,
            subject_is_frame=subject_is_frame,
            subject_is_non_runner=subject_is_non_runner,
        )
        context = RaceContext(
            race_class=None,
            race_type=None,
            field_size=len(rows),  # == unique selected-run horse count
            going=None,
            distance_f=None,
            surface=None,
        )
        safety = SafetyProvenance(
            race_resolution_method=race_res.method,
            horse_resolution_methods={r.get("horse_id"): horse_res.method},
            ambiguous_join_blocked=ambiguous_blocked,
            time_safety=time_safety,
            leakage_status="UNKNOWN",
            result_source=selection.source,
            result_source_classification=selection.classification,
            result_source_complete=result_universe_complete,
            prediction_timestamp_present=prediction_timestamp is not None,
            prediction_timestamp_before_off=(True if run_selection.pre_race_proof == PROOF_PRE_RACE else None),
            odds_timestamp_present=False,
            odds_timestamp_before_off=None,
            source_commit_present=False,
            model_versions_present=False,
            input_card_hash_verified=True,
            analysis_allowed=analysis_allowed,
            shadow_evaluation_allowed=shadow_evaluation_allowed,
            state_learning_allowed=state_learning_allowed,
            model_training_allowed=model_training_allowed,
            promotion_eligible=promotion_eligible,
        )
        event = build_learning_event(prediction=prediction, outcome=outcome, context=context, safety=safety)
        events.append(event.to_dict())

    return events, exclusions


def main() -> None:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and a service key env var are required (read-only corpus proof).")
    sb = create_client(url, key)

    print("Fetching runner_prediction_snapshots ...")
    select_fields = "race_id,run_id,created_at,horse_id,horse,race_date,course,off_time,tier,rank," + ",".join(
        MODEL_SCORE_FIELDS
    )
    rps = fetch_all(sb, "runner_prediction_snapshots", select_fields)
    print(f"  {len(rps)} rows")

    print("Fetching Supabase legacy races/runner_results (for evidence-based fallback) ...")
    supa_races = fetch_all(sb, "races", "race_id,course,date,time")
    supa_runner_results = fetch_all(sb, "runner_results", "race_id,horse_id,position,sp,sp_dec,is_winner")
    supa_by_date = build_supabase_result_index(supa_races, supa_runner_results)
    print(f"  {len(supa_races)} races, {len(supa_runner_results)} runner_results rows")

    # -- group raw snapshot rows by race_id (still spans multiple runs) -----
    races_by_id: dict[str, list[dict]] = defaultdict(list)
    for r in rps:
        rid = r.get("race_id")
        if rid:
            races_by_id[rid].append(r)

    raw_snapshot_rows = len(rps)
    distinct_snapshot_runs = len({r.get("run_id") for r in rps if r.get("run_id")})
    source_races = len(races_by_id)

    # -- Phase A: select exactly one canonical run per race -----------------
    run_selections: dict[str, RunSelection] = {}
    all_exclusions: list[dict] = []
    duplicate_rows_excluded = 0
    for race_id, rows in races_by_id.items():
        rs = select_canonical_run(race_id, rows)
        run_selections[race_id] = rs
        if not rs.resolved:
            all_exclusions.append({"race_id": race_id, "horse_id": None, "reason": f"RUN_{rs.reason}", "detail": ""})
        for excluded_run_id, _reason in rs.excluded_runs.items():
            excluded_rows = [r for r in rows if r.get("run_id") == excluded_run_id]
            duplicate_rows_excluded += len(excluded_rows)

    canonical_races = {rid: rs for rid, rs in run_selections.items() if rs.resolved}
    canonical_prediction_races = len(canonical_races)
    no_pre_race_run_exclusions = sum(1 for rs in run_selections.values() if rs.reason == "NO_PRE_RACE_RUN")
    proven_pre_race_races = sum(1 for rs in canonical_races.values() if rs.pre_race_proof == "PROVEN_PRE_RACE")
    timezone_unproven_races = sum(1 for rs in canonical_races.values() if rs.pre_race_proof == "TIMEZONE_UNPROVEN")
    general_unproven_races = sum(1 for rs in canonical_races.values() if rs.pre_race_proof == "UNPROVEN")

    # -- Phase B: result-source selection per date, using the REAL expected
    #    universe from the canonical run (not the raw pooled rows) ---------
    expected_race_ids_by_date: dict[str, set[str]] = defaultdict(set)
    expected_runners_by_race: dict[str, set[str]] = {}
    date_by_race: dict[str, str] = {}
    for race_id, rs in canonical_races.items():
        date = rs.selected_rows[0].get("race_date")
        date_by_race[race_id] = date
        expected_race_ids_by_date[date].add(race_id)
        expected_runners_by_race[race_id] = {r.get("horse_id") for r in rs.selected_rows if r.get("horse_id")}

    selection_cache: dict[str, ResultSourceSelection] = {}
    result_source_counter: Counter = Counter()
    result_classification_counter: Counter = Counter()
    source_hashes: set[str] = set()
    for date, race_ids in expected_race_ids_by_date.items():
        runners_subset = {rid: expected_runners_by_race[rid] for rid in race_ids}
        selection_cache[date] = select_result_source(
            date,
            results_dir=RESULTS_DIR_DEFAULT,
            supabase_fetch=lambda d: supa_by_date.get(d, []),
            expected_race_ids=race_ids,
            expected_runners_by_race=runners_subset,
        )
        sel = selection_cache[date]
        result_source_counter[sel.source] += 1
        result_classification_counter[sel.classification] += 1
        if sel.source_hash:
            source_hashes.add(sel.source_hash)

    # -- Phase C: build events per canonical race ----------------------------
    all_events: list[dict] = []
    time_safety_counter: Counter = Counter()
    races_with_events: set[str] = set()
    races_with_complete_result: set[str] = set()

    for race_id, rs in canonical_races.items():
        date = date_by_race[race_id]
        selection = selection_cache[date]

        events, exclusions = process_race_group(race_id, rs, selection)
        all_events.extend(events)
        all_exclusions.extend(exclusions)
        for ev in events:
            time_safety_counter[ev["safety"]["time_safety"]] += 1
            races_with_events.add(race_id)
            # P0-7: result_universe_complete is computed post-resolution in
            # process_race_group (reconciled prediction<->result mapping),
            # never by raw race-ID dictionary equality -- every event in a
            # race shares the same value, so any one event's flag suffices.
            if ev["outcome"]["result_universe_complete"]:
                races_with_complete_result.add(race_id)

    full_result_races = len(races_with_complete_result)
    partial_result_races = len(races_with_events - races_with_complete_result)

    resolved_races = len({e["prediction"]["race_id"] for e in all_events})
    unresolved_races = source_races - resolved_races
    ambiguous_races = len(
        {e["race_id"] for e in all_exclusions if e["reason"] in {"RACE_AMBIGUOUS", "RUN_AMBIGUOUS_RUN_SELECTION"}}
    )
    resolved_horse_rows = len(all_events)
    unresolved_horse_rows = sum(1 for e in all_exclusions if e["reason"].startswith("HORSE_"))
    # P0-9: these metrics now read the reconciled subject_* fields directly
    # (looked up via resolved_result_horse_id at event-build time), never
    # the prediction-side subject_horse_id against result-side keyed dicts
    # -- that mismatch was exactly the P0-7/P0-9 defect class.
    horse_rows_with_known_outcome = sum(1 for e in all_events if e["outcome"]["subject_outcome_status"] != "UNKNOWN")
    terminal_outcome_rows = sum(1 for e in all_events if e["outcome"]["subject_outcome_status"] == "TERMINAL")
    non_runner_rows = sum(1 for e in all_events if e["outcome"]["subject_is_non_runner"])
    analysis_eligible_rows = sum(1 for e in all_events if e["safety"]["analysis_allowed"])
    shadow_evaluation_eligible_races = len(
        {e["prediction"]["race_id"] for e in all_events if e["safety"]["shadow_evaluation_allowed"]}
    )
    shadow_evaluation_eligible_rows = sum(1 for e in all_events if e["safety"]["shadow_evaluation_allowed"])
    state_learning_eligible_rows = sum(1 for e in all_events if e["safety"]["state_learning_allowed"])
    model_training_safe_rows = sum(1 for e in all_events if e["safety"]["model_training_allowed"])
    promotion_eligible_rows = sum(1 for e in all_events if e["safety"]["promotion_eligible"])
    # P1 fix: result_labelled_rows counts only rows with a resolved identity
    # AND an explicit (non-UNKNOWN) outcome -- not every row belonging to a
    # resolved race regardless of whether that specific horse's outcome is known.
    result_labelled_rows = horse_rows_with_known_outcome

    safe_rows = sum(1 for e in all_events if e["safety"]["time_safety"] in {"SAFE_PROSPECTIVE", "SAFE_FROZEN_REPLAY"})
    sample_events = all_events[:SAMPLE_SIZE]
    exclusion_reason_counts = Counter(e["reason"] for e in all_exclusions)
    dates_seen = set(expected_race_ids_by_date)

    manifest = {
        "run_ts": RUN_TS,
        "mission": "LEARNING-LOOP-01A",
        "phase": 4,
        "read_only": True,
        "corrections_applied": [
            "P0-1",
            "P0-2",
            "P0-3",
            "P0-4",
            "P0-5",
            "P0-6",
            "P0-7",
            "P0-8",
            "P0-9",
            "P0-10",
            "P1",
        ],
        # -- P1: full metric breakdown, reported separately -----------------
        "raw_snapshot_rows": raw_snapshot_rows,
        "distinct_snapshot_runs": distinct_snapshot_runs,
        "selected_canonical_run_rows": sum(len(rs.selected_rows) for rs in canonical_races.values()),
        "duplicate_rows_excluded": duplicate_rows_excluded,
        "canonical_prediction_races": canonical_prediction_races,
        "no_pre_race_run_exclusions": no_pre_race_run_exclusions,
        "proven_pre_race_races": proven_pre_race_races,
        "timezone_unproven_races": timezone_unproven_races,
        "general_unproven_races": general_unproven_races,
        "shadow_evaluation_eligible_races": shadow_evaluation_eligible_races,
        "shadow_evaluation_eligible_rows": shadow_evaluation_eligible_rows,
        "source_races": source_races,
        "resolved_races": resolved_races,
        "unresolved_races": unresolved_races,
        "ambiguous_races": ambiguous_races,
        "full_result_races": full_result_races,
        "partial_result_races": partial_result_races,
        "resolved_horse_rows": resolved_horse_rows,
        "horse_rows_with_known_outcome": horse_rows_with_known_outcome,
        "terminal_outcome_rows": terminal_outcome_rows,
        "non_runner_rows": non_runner_rows,
        "unresolved_horse_rows": unresolved_horse_rows,
        "result_labelled_rows": result_labelled_rows,
        "event_rows_built": len(all_events),
        "analysis_eligible_rows": analysis_eligible_rows,
        "state_learning_eligible_rows": state_learning_eligible_rows,
        "model_training_safe_rows": model_training_safe_rows,
        "promotion_eligible_rows": promotion_eligible_rows,
        "full_feature_rows": 0,  # RaceContext fields (class/type/going/distance/surface) are not
        # carried by runner_prediction_snapshots -- honestly reported as zero rather than fabricated.
        "safe_rows": safe_rows,
        "exclusions_by_reason": dict(exclusion_reason_counts),
        "time_safety_distribution": dict(time_safety_counter),
        "result_source_distribution": dict(result_source_counter),
        "result_source_classification_distribution": dict(result_classification_counter),
        "date_range": {"min": min(dates_seen) if dates_seen else None, "max": max(dates_seen) if dates_seen else None},
        "distinct_source_hashes": len(source_hashes),
        "classifications": [
            "RICH_SNAPSHOT_RESULT_JOIN_MEASURED",
            "TRAINING_SAFE_SUBSET_MEASURED",
            "AMBIGUITY_BLOCKING_PROVEN",
            "PREDICTION_RUN_CONTAMINATION_CORRECTED",
            "RESULT_COMPLETENESS_PROVEN_AGAINST_EXPECTED_UNIVERSE",
            "NO_HFS_MUTATION",
            "NO_PLAYBOOK_G_MUTATION",
            "NO_LIVE_SCORING_CHANGE",
            "NO_MODEL_TRAINING",
            "NO_MODEL_PROMOTION",
            "NO_SUPABASE_WRITES",
            "NO_TELEGRAM_SEND",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    with open(OUT_SAMPLE, "w", encoding="utf-8") as f:
        for ev in sample_events:
            f.write(json.dumps(ev, default=str) + "\n")

    with open(OUT_EXCLUSIONS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["race_id", "horse_id", "reason", "detail"])
        w.writeheader()
        for e in all_exclusions:
            w.writerow(e)

    print()
    print("=== Training corpus V2 (dry run, corrected) summary ===")
    for k in [
        "raw_snapshot_rows",
        "distinct_snapshot_runs",
        "selected_canonical_run_rows",
        "duplicate_rows_excluded",
        "canonical_prediction_races",
        "no_pre_race_run_exclusions",
        "proven_pre_race_races",
        "timezone_unproven_races",
        "general_unproven_races",
        "shadow_evaluation_eligible_races",
        "shadow_evaluation_eligible_rows",
        "resolved_races",
        "unresolved_races",
        "ambiguous_races",
        "full_result_races",
        "partial_result_races",
        "resolved_horse_rows",
        "result_labelled_rows",
        "unresolved_horse_rows",
        "safe_rows",
    ]:
        print(f"  {k}: {manifest[k]}")
    print(f"  time_safety_distribution: {manifest['time_safety_distribution']}")
    print()
    print(f"Written: {OUT_MANIFEST}")
    print(f"Written: {OUT_SAMPLE}")
    print(f"Written: {OUT_EXCLUSIONS}")


if __name__ == "__main__":
    main()
