"""
LEARNING-LOOP-01A — Phase 4: dry-run training corpus proof.

Builds a dry-run LearningEventV2 corpus from runner_prediction_snapshots
(Supabase) joined to canonical results via the Phase 2 modules
(`result_source_selector` + `identity_resolver`).

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
)
from src.velo.learning.result_source_selector import (
    RESULTS_DIR_DEFAULT,
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


def process_race_group(race_id: str, rows: list[dict], selection) -> tuple[list[dict], list[dict]]:
    """Pure per-race function: resolve identity, build LearningEventV2
    events, and return (event_dicts, exclusion_dicts). No I/O, fully
    testable without Supabase or the local filesystem -- `selection` is
    just a `ResultSourceSelection` (real or hand-built for a test)."""
    events: list[dict] = []
    exclusions: list[dict] = []

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

    for r in rows:
        horse_res = resolve_horse(r.get("horse_id"), r.get("horse"), resolved_race or {})
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

        runner_positions: dict[str, str] = {}
        sp_by_horse: dict[str, float] = {}
        winner_horse_id = None
        frame_horse_ids: list[str] = []
        non_runners: list[str] = []
        for runner in (resolved_race or {}).get("runners", []):
            hid = runner.get("horse_id")
            if not hid:
                continue
            pos = str(runner.get("position") or runner.get("position_text") or "")
            runner_positions[hid] = pos or "NR"
            if not pos:
                non_runners.append(hid)
            sp = runner.get("sp_dec")
            if sp is not None:
                sp_by_horse[hid] = sp
            if pos == "1" or runner.get("is_winner"):
                winner_horse_id = hid
            if pos in {"1", "2", "3"}:
                frame_horse_ids.append(hid)

        ambiguous_blocked = race_res.method == "AMBIGUOUS" or horse_res.method == "AMBIGUOUS"
        odds_capture_ts = None  # not carried by runner_prediction_snapshots -- provenance unknown

        if ambiguous_blocked:
            time_safety = "EXCLUDED_IDENTITY_AMBIGUOUS"
        elif selection.classification in {"RESULT_SOURCE_PARTIAL", "RESULT_SOURCE_MISSING", "RESULT_SOURCE_CONFLICT"}:
            time_safety = "EXCLUDED_INCOMPLETE_RESULT"
        elif odds_capture_ts is None:
            time_safety = "EXCLUDED_UNTIMED_ODDS"
        else:
            time_safety = "CURRENT_CODE_COUNTERFACTUAL_REPLAY"

        learning_allowed = time_safety not in {
            "EXCLUDED_IDENTITY_AMBIGUOUS",
            "EXCLUDED_INCOMPLETE_RESULT",
            "EXCLUDED_UNTIMED_ODDS",
            "EXCLUDED_POST_RACE_LEAKAGE",
            "EXCLUDED_FEATURE_PROVENANCE_UNKNOWN",
        }

        prediction = PredictionTruth(
            race_date=date,
            race_id=race_id,
            course=first.get("course") or "",
            off_time=first.get("off_time") or "",
            runner_universe=tuple({"horse_id": rr.get("horse_id"), "horse_name": rr.get("horse")} for rr in rows),
            model_scores={f: r.get(f) for f in MODEL_SCORE_FIELDS},
            rank_order=rank_order,
            top_three=top_three,
            odds_value=None,
            odds_capture_ts=odds_capture_ts,
            source_commit=None,
            input_card_hash=str(race_id) + ":" + str(r.get("horse_id")),
            model_versions={},
            active_components=tuple(f for f in MODEL_SCORE_FIELDS if r.get(f) is not None),
            excluded_components=tuple(f for f in MODEL_SCORE_FIELDS if r.get(f) is None),
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
        )
        context = RaceContext(
            race_class=None,
            race_type=None,
            field_size=len(rows),
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
            learning_allowed=learning_allowed,
            promotion_eligible=False,
            result_source=selection.source,
            result_source_classification=selection.classification,
        )
        event = build_learning_event(prediction=prediction, outcome=outcome, context=context, safety=safety)
        events.append(event.to_dict())

    return events, exclusions


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


def main() -> None:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and a service key env var are required (read-only corpus proof).")
    sb = create_client(url, key)

    print("Fetching runner_prediction_snapshots ...")
    select_fields = "race_id,horse_id,horse,race_date,course,off_time,tier,rank," + ",".join(MODEL_SCORE_FIELDS)
    rps = fetch_all(sb, "runner_prediction_snapshots", select_fields)
    print(f"  {len(rps)} rows")

    print("Fetching Supabase legacy races/runner_results (for evidence-based fallback) ...")
    supa_races = fetch_all(sb, "races", "race_id,course,date,time")
    supa_runner_results = fetch_all(sb, "runner_results", "race_id,horse_id,position,sp,sp_dec,is_winner")
    supa_by_date = build_supabase_result_index(supa_races, supa_runner_results)
    print(f"  {len(supa_races)} races, {len(supa_runner_results)} runner_results rows")

    # -- group snapshot rows by race_id --------------------------------------
    races_by_id: dict[str, list[dict]] = defaultdict(list)
    for r in rps:
        rid = r.get("race_id")
        if rid:
            races_by_id[rid].append(r)

    source_rows = len(rps)
    source_races = len(races_by_id)
    all_events: list[dict] = []
    all_exclusions: list[dict] = []
    time_safety_counter: Counter = Counter()
    result_source_counter: Counter = Counter()
    result_classification_counter: Counter = Counter()
    source_hashes: set[str] = set()
    dates_seen: set[str] = set()
    selection_cache: dict[str, object] = {}
    resolved_races = 0
    unresolved_races = 0
    ambiguous_races = 0
    result_labelled_rows = 0

    for race_id, rows in races_by_id.items():
        date = rows[0].get("race_date")
        dates_seen.add(date)

        if date not in selection_cache:
            selection_cache[date] = select_result_source(
                date,
                results_dir=RESULTS_DIR_DEFAULT,
                supabase_fetch=lambda d: supa_by_date.get(d, []),
            )
        selection = selection_cache[date]
        result_source_counter[selection.source] += 1
        result_classification_counter[selection.classification] += 1
        if selection.source_hash:
            source_hashes.add(selection.source_hash)

        events, exclusions = process_race_group(race_id, rows, selection)
        race_was_resolved = not any(e["reason"].startswith("RACE_") for e in exclusions)
        if race_was_resolved:
            resolved_races += 1
            result_labelled_rows += len(rows)
        else:
            unresolved_races += 1
            if any(e["reason"] == "RACE_AMBIGUOUS" for e in exclusions):
                ambiguous_races += 1

        all_events.extend(events)
        all_exclusions.extend(exclusions)
        for ev in events:
            time_safety_counter[ev["safety"]["time_safety"]] += 1

    resolved_horse_rows = len(all_events)
    unresolved_horse_rows = sum(1 for e in all_exclusions if e["reason"].startswith("HORSE_"))
    safe_rows = sum(1 for e in all_events if e["safety"]["time_safety"] in {"SAFE_PROSPECTIVE", "SAFE_FROZEN_REPLAY"})
    sample_events = all_events[:SAMPLE_SIZE]
    exclusion_reason_counts = Counter(e["reason"] for e in all_exclusions)

    manifest = {
        "run_ts": RUN_TS,
        "mission": "LEARNING-LOOP-01A",
        "phase": 4,
        "read_only": True,
        "source_rows": source_rows,
        "source_races": source_races,
        "resolved_races": resolved_races,
        "unresolved_races": unresolved_races,
        "ambiguous_races": ambiguous_races,
        "resolved_horse_rows": resolved_horse_rows,
        "unresolved_horse_rows": unresolved_horse_rows,
        "result_labelled_rows": result_labelled_rows,
        "full_feature_rows": 0,  # RaceContext fields (class/type/going/distance/surface) are not
        # carried by runner_prediction_snapshots -- honestly reported as zero
        # rather than fabricated.
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
    print("=== Training corpus V2 (dry run) summary ===")
    for k in [
        "source_rows",
        "source_races",
        "resolved_races",
        "unresolved_races",
        "ambiguous_races",
        "resolved_horse_rows",
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
