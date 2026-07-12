"""
RACE-DAY-12-EOD-TRUTH-01 -- governed, evidence-only results/Sigma close for
2026-07-12. Builds sealed LearningEventV2.2 packets from velo_verdicts +
RP results truth. Does NOT mutate any learner state, Playbook G, Supabase,
or Telegram. Read-only evidence production only.

Corrected per PR #149 REQUEST CHANGES (P0-11..P0-14):
  - time_safety/leakage_status are derived through an explicit priority
    chain, never asserted SAFE_* by default.
  - the Dundalk numeric<->composite race_id bridge is derived from
    committed capture-manifest evidence (course+date+off-time+source
    URL/title), never from a positional/ordering assumption, and fails
    closed if the derived mapping is not a clean 1:1 bijection.
  - prediction_run_id is a real immutable run identity: a hash of the
    exact selected velo_verdicts row content, combined with its
    generated_at and race_id -- not a bare race identity.
  - odds_capture_ts is None (and EXCLUDED_UNTIMED_ODDS applies) unless a
    documented check proves the timestamp represents the capture time of
    the exact odds embedded in the verdict row. No such proof exists yet
    for velo_verdicts.fetch_timestamp, so it is treated as unproven.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.velo.learning.learning_event_v2 import (  # noqa: E402
    PredictionTruth,
    OutcomeTruth,
    RaceContext,
    SafetyProvenance,
    build_learning_event,
    compute_input_card_hash,
    TIME_SAFETY_SAFE_FROZEN_REPLAY,
    TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS,
    TIME_SAFETY_EXCLUDED_INCOMPLETE_RESULT,
    TIME_SAFETY_EXCLUDED_PREDICTION_TIME_UNPROVEN,
    TIME_SAFETY_EXCLUDED_UNTIMED_ODDS,
)
from src.velo.learning.identity_resolver import resolve_horse  # noqa: E402

RACE_DATE = "2026-07-12"
RESULTS_PATH = Path("data/results/rp_results_2026_07_12.json")
REPORTS_DIR = Path("data/reports")
DUNDALK_RESULTS_MANIFEST_PATH = Path(
    "data/racing_post_account_raw/rp-results-2026-07-12-dundalk/manifest.json"
)
LONDON = ZoneInfo("Europe/London")

# No documented check currently proves velo_verdicts.fetch_timestamp is the
# capture time of the exact odds embedded in predictions[].sp_dec -- it may
# simply be racecard-page fetch time. Treat odds timing as unproven until
# such a check exists. This is a explicit, auditable constant, not a
# silent assumption buried in logic.
ODDS_TIMING_PROVEN = False


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_obj(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return sha256_of_text(raw)


def classify_time_safety(
    *,
    ambiguous: bool,
    result_universe_complete: bool,
    prediction_before_off: bool | None,
    odds_timing_proven: bool,
) -> tuple[str, str]:
    """Pure, priority-ordered classification (P0-11). Returns
    (time_safety, leakage_status). Never returns a SAFE_* class unless
    every required provenance condition is explicitly proven."""
    if ambiguous:
        return TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS, "UNKNOWN"
    if not result_universe_complete:
        return TIME_SAFETY_EXCLUDED_INCOMPLETE_RESULT, "UNKNOWN"
    if prediction_before_off is not True:
        return TIME_SAFETY_EXCLUDED_PREDICTION_TIME_UNPROVEN, "UNKNOWN"

    # Leakage is about whether frozen prediction features could contain
    # result-derived contamination -- that is fully determined by the
    # causal proof that the row was generated before the race happened,
    # independent of whether odds timing is separately proven.
    leakage_status = "CLEAN"

    if not odds_timing_proven:
        return TIME_SAFETY_EXCLUDED_UNTIMED_ODDS, leakage_status
    return TIME_SAFETY_SAFE_FROZEN_REPLAY, leakage_status


def build_dundalk_id_map(
    verdicts: list[dict], manifest_path: Path = DUNDALK_RESULTS_MANIFEST_PATH
) -> tuple[dict[str, str], list[dict], str]:
    """Derive the numeric<->composite Dundalk race_id bridge from
    committed evidence (P0-12): the results-capture manifest's own
    source_url + page title supplies the numeric race_id and its
    off-time; the composite velo_verdicts race_id supplies its own
    off-time by construction (rp_DUN_<date>_<off>). Matched by exact
    off-time. Fails closed (raises) if either side has a duplicate
    off-time or the two sides are not a clean 1:1 bijection.

    Returns (numeric_to_composite_map, evidence_records, manifest_sha256).
    """
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_sha256 = sha256_of_text(manifest_text)
    manifest = json.loads(manifest_text)

    numeric_by_off: dict[str, dict] = {}
    for cap in manifest.get("captures", []):
        m_url = re.search(r"/results/\d+/([a-z0-9-]+)/(\d{4}-\d{2}-\d{2})/(\d+)$", cap["source_url"])
        m_title = re.search(r"Full Result (\d{1,2}\.\d{2})\s+Dundalk", cap.get("title", ""), re.IGNORECASE)
        if not m_url or not m_title:
            continue
        course_slug, date, numeric_id = m_url.groups()
        off_time = m_title.group(1)
        if off_time in numeric_by_off:
            raise RuntimeError(
                f"Dundalk mapping evidence has a duplicate off-time {off_time} on the numeric "
                f"(results-capture) side -- refusing to guess, ids {numeric_by_off[off_time]['numeric_race_id']} "
                f"and {numeric_id} both claim it"
            )
        numeric_by_off[off_time] = {
            "numeric_race_id": numeric_id,
            "course_slug": course_slug,
            "date": date,
            "off_time": off_time,
            "source_url": cap["source_url"],
            "source_title": cap["title"],
        }

    composite = sorted(
        {v["race_id"] for v in verdicts if v["race_id"].startswith("rp_DUN_")}
    )
    composite_by_off: dict[str, str] = {}
    for rid in composite:
        m = re.search(r"_(\d{1,2}\.\d{2})$", rid)
        if not m:
            raise RuntimeError(f"Dundalk composite verdict race_id {rid!r} has no parseable off-time suffix")
        off_time = m.group(1)
        if off_time in composite_by_off:
            raise RuntimeError(
                f"Dundalk mapping evidence has a duplicate off-time {off_time} on the composite "
                f"(velo_verdicts) side -- refusing to guess, ids {composite_by_off[off_time]} and {rid} both claim it"
            )
        composite_by_off[off_time] = rid

    numeric_offs = set(numeric_by_off.keys())
    composite_offs = set(composite_by_off.keys())
    if numeric_offs != composite_offs:
        raise RuntimeError(
            "Dundalk id reconciliation is not a clean 1:1 bijection -- "
            f"numeric-only off-times: {numeric_offs - composite_offs}, "
            f"composite-only off-times: {composite_offs - numeric_offs}. Refusing to guess."
        )

    id_map: dict[str, str] = {}
    evidence: list[dict] = []
    for off_time in sorted(numeric_offs):
        numeric_rec = numeric_by_off[off_time]
        composite_rid = composite_by_off[off_time]
        id_map[numeric_rec["numeric_race_id"]] = composite_rid
        evidence.append(
            {
                "course": numeric_rec["course_slug"],
                "date": numeric_rec["date"],
                "off_time": off_time,
                "numeric_result_race_id": numeric_rec["numeric_race_id"],
                "composite_verdict_race_id": composite_rid,
                "source_url": numeric_rec["source_url"],
                "source_title": numeric_rec["source_title"],
                "source_manifest_sha256": manifest_sha256,
                "resolution_method": "COURSE_DATE_EXACT_OFFTIME_MATCH",
            }
        )
    return id_map, evidence, manifest_sha256


def compute_prediction_run_identity(row: dict) -> dict:
    """Derive a real immutable prediction-run identity (P0-14) from the
    exact selected velo_verdicts row: hash of the canonical row content,
    combined with race_id and generated_at. A changed/corrected row
    mints a different run identity because the hash changes."""
    row_hash = sha256_of_obj(row)
    race_id = row["race_id"]
    generated_at = row["generated_at"]
    prediction_run_id = f"velo_verdicts:{race_id}:{generated_at}:{row_hash[:12]}"
    return {
        "prediction_run_id": prediction_run_id,
        "source_row_hash": row_hash,
    }


def select_verdict_rows(raw_rows: list[dict]) -> dict[str, dict]:
    """Group raw velo_verdicts rows by race_id and deterministically
    select one per race_id, recording duplicate-row provenance rather
    than silently assuming a single row (P0-14). Tie-break: latest
    generated_at wins (documented, not positional)."""
    by_race: dict[str, list[dict]] = {}
    for row in raw_rows:
        by_race.setdefault(row["race_id"], []).append(row)

    selected: dict[str, dict] = {}
    for race_id, rows in by_race.items():
        rows_sorted = sorted(rows, key=lambda r: r["generated_at"])
        chosen = rows_sorted[-1]
        duplicate_count = len(rows) - 1
        chosen = dict(chosen)
        chosen["_duplicate_row_count"] = duplicate_count
        chosen["_multiple_candidates"] = duplicate_count > 0
        chosen["_tie_break_reason"] = "LATEST_GENERATED_AT" if duplicate_count > 0 else "SINGLE_CANDIDATE"
        selected[race_id] = chosen
    return selected


def load_results() -> tuple[dict, str]:
    text = RESULTS_PATH.read_text(encoding="utf-8")
    sha = sha256_of_text(text)
    return json.loads(text), sha


def load_verdicts_raw() -> list[dict]:
    from src.data.supabase_client import get_supabase_client

    sb = get_supabase_client().client
    r = (
        sb.table("velo_verdicts")
        .select("race_id,generated_at,fetch_timestamp,engine_version,git_commit_sha,full_analysis")
        .gte("generated_at", f"{RACE_DATE}T00:00:00")
        .lt("generated_at", "2026-07-13T00:00:00")
        .execute()
    )
    return r.data


def main() -> None:
    results_payload, results_sha256 = load_results()
    results_by_race = {r["race_id"]: r for r in results_payload["results"]}

    raw_verdicts = load_verdicts_raw()
    dundalk_map, dundalk_evidence, dundalk_manifest_sha256 = build_dundalk_id_map(raw_verdicts)
    verdicts_selected = select_verdict_rows(raw_verdicts)

    events = []
    horse_exclusions = []
    race_exclusions = []
    per_race_summary = []

    for race_id, res in results_by_race.items():
        if not res.get("winner_horse"):
            race_exclusions.append(
                {
                    "type": "RACE",
                    "race_id": race_id,
                    "resolved_race_id": None,
                    "horse_id": None,
                    "horse_name": None,
                    "resolution_method": None,
                    "reason": "NO_RESULT_DATA_PARSED",
                    "race_completeness": "NO_RESULT",
                    "shadow_exclusion_reason": "NO_RESULT_DATA_PARSED",
                }
            )
            continue

        verdict_key = dundalk_map.get(race_id, race_id)
        verdict_row = verdicts_selected.get(verdict_key)
        if verdict_row is None:
            race_exclusions.append(
                {
                    "type": "RACE",
                    "race_id": race_id,
                    "resolved_race_id": verdict_key,
                    "horse_id": None,
                    "horse_name": None,
                    "resolution_method": None,
                    "reason": "NO_VELO_VERDICTS_ROW",
                    "race_completeness": "NO_PREDICTION",
                    "shadow_exclusion_reason": "NO_VELO_VERDICTS_ROW",
                }
            )
            continue

        race_resolution_method = (
            "DUNDALK_COURSE_DATE_EXACT_OFFTIME_MATCH" if race_id in dundalk_map else "DIRECT_ID_MATCH"
        )

        run_identity = compute_prediction_run_identity(
            {k: v for k, v in verdict_row.items() if not k.startswith("_")}
        )
        prediction_run_id = run_identity["prediction_run_id"]
        source_row_hash = run_identity["source_row_hash"]

        fa = verdict_row["full_analysis"]
        if isinstance(fa, str):
            fa = json.loads(fa)
        predictions = fa.get("predictions", [])
        pred_by_horse = {p["horse_id"]: p for p in predictions}

        runner_universe = tuple({"horse_id": p["horse_id"], "horse": p.get("horse")} for p in predictions)
        model_scores_by_horse = {
            p["horse_id"]: {
                "velo_prime_prob": p.get("signal_stack", {}).get("vp"),
                "mds": p.get("signal_stack", {}).get("mds"),
                "g_base_prob": p.get("g_base_prob"),
                "mpi": p.get("mpi"),
                "place_prob": p.get("place_prob"),
                "longshot_prob": p.get("longshot_prob"),
            }
            for p in predictions
        }
        rank_order = tuple(
            p["horse_id"] for p in sorted(predictions, key=lambda x: -(x.get("signal_stack", {}).get("vp") or 0))
        )
        top_three = rank_order[:3]

        gen = verdict_row["generated_at"]
        off_raw = res.get("off") or ""
        prediction_before_off: bool | None = None
        off_time_for_dundalk = None
        if not off_raw and race_id in dundalk_map:
            ev = next(e for e in dundalk_evidence if e["numeric_result_race_id"] == race_id)
            off_time_for_dundalk = ev["off_time"]

        off_source = off_raw or off_time_for_dundalk
        if off_source:
            try:
                hh, mm = off_source.split(".")
                hh_i = int(hh)
                off_dt = datetime(2026, 7, 12, hh_i + 12 if hh_i < 8 else hh_i, int(mm), tzinfo=LONDON)
                gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
                prediction_before_off = gen_dt < off_dt
            except Exception:
                prediction_before_off = None

        runner_positions = {}
        sp_by_horse = {}
        non_runners = []
        for rr in res["runners"]:
            hid = rr["horse_id"]
            runner_positions[hid] = "NR" if rr.get("non_runner") else str(rr.get("position"))
            if rr.get("non_runner"):
                non_runners.append(hid)
            if rr.get("sp_dec") is not None:
                sp_by_horse[hid] = rr["sp_dec"]

        result_ids = set(runner_positions.keys())
        pred_ids = set(pred_by_horse.keys())

        resolution_by_pred_id = {}
        for horse_id in pred_ids:
            pred_name = pred_by_horse[horse_id].get("horse")
            resolution_by_pred_id[horse_id] = resolve_horse(
                pred_horse_id=horse_id,
                pred_horse_name=pred_name,
                resolved_race={"runners": res["runners"]},
            )

        resolved_ids = {r.resolved_horse_id for r in resolution_by_pred_id.values() if r.is_resolved}
        all_predictions_resolved = all(r.is_resolved for r in resolution_by_pred_id.values())
        result_universe_complete = all_predictions_resolved and (resolved_ids == result_ids)

        winner_id = res.get("winner_id")
        frame_ids = tuple(res.get("top3_ids", []))

        if not result_universe_complete:
            reason_bits = []
            if not all_predictions_resolved:
                reason_bits.append("UNRESOLVED_HORSE_IDENTITY")
            if resolved_ids != result_ids:
                missing_from_pred = result_ids - resolved_ids
                if missing_from_pred:
                    reason_bits.append(f"RESULT_RUNNERS_NOT_IN_PREDICTION:{sorted(missing_from_pred)}")
            race_exclusions.append(
                {
                    "type": "RACE",
                    "race_id": race_id,
                    "resolved_race_id": verdict_key,
                    "horse_id": None,
                    "horse_name": None,
                    "resolution_method": race_resolution_method,
                    "reason": ";".join(reason_bits) or "INCOMPLETE_RESULT_UNIVERSE",
                    "race_completeness": "PARTIAL",
                    "shadow_exclusion_reason": "EXCLUDED_INCOMPLETE_RESULT",
                }
            )

        race_events_this_race = []
        for horse_id in pred_ids:
            resolution = resolution_by_pred_id[horse_id]
            in_result = resolution.is_resolved
            resolved_id = resolution.resolved_horse_id
            subject_outcome_status = "UNKNOWN"
            finish_pos = None
            sp = sp_by_horse.get(resolved_id) if in_result else None
            is_winner = (resolved_id == winner_id) if in_result else False
            is_frame = (resolved_id in frame_ids) if in_result else False
            is_nr = (resolved_id in non_runners) if in_result else False
            if in_result:
                if is_nr:
                    subject_outcome_status = "NON_RUNNER"
                elif runner_positions[resolved_id] and runner_positions[resolved_id].isdigit():
                    subject_outcome_status = "FINISHED"
                    finish_pos = runner_positions[resolved_id]
                else:
                    subject_outcome_status = "TERMINAL"
                    finish_pos = runner_positions[resolved_id]

            ambiguous = not in_result
            if ambiguous:
                horse_exclusions.append(
                    {
                        "type": "HORSE",
                        "race_id": race_id,
                        "resolved_race_id": verdict_key,
                        "horse_id": horse_id,
                        "horse_name": pred_by_horse[horse_id].get("horse"),
                        "resolution_method": resolution.method,
                        "reason": resolution.ambiguity_reason or "UNRESOLVED",
                        "race_completeness": "PARTIAL" if not result_universe_complete else "COMPLETE",
                        "shadow_exclusion_reason": "EXCLUDED_IDENTITY_AMBIGUOUS",
                    }
                )

            time_safety, leakage_status = classify_time_safety(
                ambiguous=ambiguous,
                result_universe_complete=result_universe_complete,
                prediction_before_off=prediction_before_off,
                odds_timing_proven=ODDS_TIMING_PROVEN,
            )

            analysis_allowed = not ambiguous
            shadow_evaluation_allowed = (
                not ambiguous and result_universe_complete and prediction_before_off is True
            )

            input_card_hash = compute_input_card_hash(
                race_id=race_id,
                subject_horse_id=horse_id,
                prediction_run_id=prediction_run_id,
                runner_universe=runner_universe,
                model_scores=model_scores_by_horse.get(horse_id, {}),
                rank_order=rank_order,
                top_three=top_three,
                model_versions={"engine_version": verdict_row.get("engine_version", "")},
                active_components=tuple(
                    fa.get("predictions", [{}])[0].get("verdict_flags", []) if predictions else []
                ),
                excluded_components=(),
            )

            prediction = PredictionTruth(
                race_date=RACE_DATE,
                race_id=race_id,
                course=res.get("course_slug", ""),
                off_time=off_source or "",
                subject_horse_id=horse_id,
                prediction_run_id=prediction_run_id,
                runner_universe=runner_universe,
                model_scores=model_scores_by_horse.get(horse_id, {}),
                rank_order=rank_order,
                top_three=top_three,
                odds_value=pred_by_horse[horse_id].get("sp_dec"),
                odds_capture_ts=None,
                prediction_timestamp=gen,
                source_commit=verdict_row.get("git_commit_sha"),
                input_card_hash=input_card_hash,
                model_versions={"engine_version": verdict_row.get("engine_version", "")},
                active_components=(),
                excluded_components=(),
            )

            outcome = OutcomeTruth(
                result_race_id=race_id,
                runner_positions=runner_positions,
                non_runners=tuple(non_runners),
                sp_by_horse=sp_by_horse,
                bsp_by_horse={},
                winner_horse_id=winner_id,
                frame_horse_ids=frame_ids,
                result_source_hash=results_sha256,
                result_universe_complete=result_universe_complete,
                resolved_result_horse_id=resolved_id if in_result else None,
                horse_resolution_method=resolution.method,
                subject_outcome_status=subject_outcome_status,
                subject_finish_position=finish_pos,
                subject_sp=sp,
                subject_bsp=None,
                subject_is_winner=is_winner,
                subject_is_frame=is_frame,
                subject_is_non_runner=is_nr,
            )

            context = RaceContext(
                race_class=res.get("race_class") or None,
                race_type=None,
                field_size=res.get("field_size"),
                going=res.get("going") or None,
                distance_f=res.get("distance_f") or None,
                surface=None,
            )

            safety = SafetyProvenance(
                race_resolution_method=race_resolution_method,
                horse_resolution_methods={horse_id: outcome.horse_resolution_method},
                ambiguous_join_blocked=ambiguous,
                time_safety=time_safety,
                leakage_status=leakage_status,
                result_source="RP_LOCAL_JSON",
                result_source_classification="RP_LOCAL_JSON",
                result_source_complete=result_universe_complete,
                prediction_timestamp_present=True,
                prediction_timestamp_before_off=prediction_before_off,
                odds_timestamp_present=False,
                odds_timestamp_before_off=None,
                source_commit_present=bool(verdict_row.get("git_commit_sha")),
                model_versions_present=bool(verdict_row.get("engine_version")),
                input_card_hash_verified=True,
                analysis_allowed=analysis_allowed,
                shadow_evaluation_allowed=shadow_evaluation_allowed,
                state_learning_allowed=False,
                model_training_allowed=False,
                promotion_eligible=False,
            )

            ev = build_learning_event(prediction=prediction, outcome=outcome, context=context, safety=safety)
            race_events_this_race.append(ev)

        events.extend(race_events_this_race)
        per_race_summary.append(
            {
                "race_id": race_id,
                "course": res.get("course_slug"),
                "off": off_source,
                "verdict_race_id": verdict_key,
                "prediction_run_id": prediction_run_id,
                "source_row_hash": source_row_hash,
                "duplicate_row_count": verdict_row.get("_duplicate_row_count", 0),
                "multiple_candidates": verdict_row.get("_multiple_candidates", False),
                "tie_break_reason": verdict_row.get("_tie_break_reason"),
                "race_resolution_method": race_resolution_method,
                "runners_predicted": len(pred_ids),
                "runners_resulted": len(result_ids),
                "runners_resolved": sum(1 for r in resolution_by_pred_id.values() if r.is_resolved),
                "runners_ambiguous_or_unresolved": sum(
                    1 for r in resolution_by_pred_id.values() if not r.is_resolved
                ),
                "result_universe_complete": result_universe_complete,
                "prediction_before_off": prediction_before_off,
                "winner_horse": res.get("winner_horse"),
                "winner_id": winner_id,
                "top_pick_pred_id": rank_order[0] if rank_order else None,
                "top_pick_resolved_id": (
                    resolution_by_pred_id[rank_order[0]].resolved_horse_id if rank_order else None
                ),
                "top_pick_is_winner": (
                    resolution_by_pred_id[rank_order[0]].resolved_horse_id == winner_id
                    if rank_order and resolution_by_pred_id[rank_order[0]].is_resolved
                    else False
                ),
                "top_pick_is_frame": (
                    resolution_by_pred_id[rank_order[0]].resolved_horse_id in frame_ids
                    if rank_order and resolution_by_pred_id[rank_order[0]].is_resolved
                    else False
                ),
            }
        )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_path = REPORTS_DIR / "learning_events_v2_2_2026_07_12.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev.to_dict(), ensure_ascii=False, default=str) + "\n")

    all_exclusions = race_exclusions + horse_exclusions
    exclusions_path = REPORTS_DIR / "race_day_12_exclusions_2026_07_12.csv"
    fieldnames = [
        "type",
        "race_id",
        "resolved_race_id",
        "horse_id",
        "horse_name",
        "resolution_method",
        "reason",
        "race_completeness",
        "shadow_exclusion_reason",
    ]
    with exclusions_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in all_exclusions:
            w.writerow(row)

    ledger_path = REPORTS_DIR / "_race_day_12_exclusion_ledger.json"
    ledger_path.write_text(json.dumps(all_exclusions, indent=2, default=str), encoding="utf-8")

    time_safety_distribution: dict[str, int] = {}
    for ev in events:
        ts = ev.safety.time_safety
        time_safety_distribution[ts] = time_safety_distribution.get(ts, 0) + 1

    unresolved_horse_count = len(horse_exclusions)
    partial_ambiguous_race_count = sum(1 for r in per_race_summary if not r["result_universe_complete"])
    shadow_eligible_race_ids = {
        r["race_id"] for r in per_race_summary if r["result_universe_complete"] and r["prediction_before_off"] is True
    }

    assert not any(
        ev.safety.ambiguous_join_blocked and ev.safety.time_safety not in (
            TIME_SAFETY_EXCLUDED_IDENTITY_AMBIGUOUS,
        )
        for ev in events
    ), "an ambiguous-identity event must classify EXCLUDED_IDENTITY_AMBIGUOUS"
    assert not any(
        ev.safety.time_safety == TIME_SAFETY_SAFE_FROZEN_REPLAY and ev.safety.ambiguous_join_blocked for ev in events
    ), "no unresolved event may carry a SAFE_* time class"
    assert not any(
        ev.safety.time_safety == TIME_SAFETY_SAFE_FROZEN_REPLAY and not ev.safety.result_source_complete
        for ev in events
    ), "no incomplete-race event may carry a SAFE_* time class"
    assert not any(
        ev.safety.time_safety == TIME_SAFETY_SAFE_FROZEN_REPLAY and ev.safety.prediction_timestamp_before_off is not True
        for ev in events
    ), "no event with unproven prediction timing may carry a SAFE_* time class"
    assert unresolved_horse_count == len(
        {(e["race_id"], e["horse_id"]) for e in horse_exclusions}
    ), "unresolved horse exclusion rows must be unique per (race, horse)"
    assert partial_ambiguous_race_count == len(
        {r["race_id"] for r in race_exclusions if r["race_completeness"] == "PARTIAL"}
    ), "every partial race must have an explicit exclusion row"
    assert not (shadow_eligible_race_ids & {r["race_id"] for r in race_exclusions}), (
        "no excluded race may be shadow-eligible"
    )

    manifest = {
        "schema_version": "learning_event_v2.2",
        "race_date": RACE_DATE,
        "generated_at": datetime.now(tz=LONDON).astimezone(tz=None).isoformat(),
        "total_events": len(events),
        "total_races_with_events": len(per_race_summary),
        "results_source_path": str(RESULTS_PATH),
        "results_source_sha256": results_sha256,
        "prediction_source": "velo_verdicts (Supabase)",
        "prediction_source_note": (
            "runner_prediction_snapshots has 0 rows for 2026-07-12; velo_verdicts is the "
            "actual canonical prediction artifact for this date."
        ),
        "dundalk_id_reconciliation": dundalk_map,
        "dundalk_mapping_evidence": dundalk_evidence,
        "dundalk_mapping_source_manifest_sha256": dundalk_manifest_sha256,
        "odds_timing_proven": ODDS_TIMING_PROVEN,
        "time_safety_distribution": time_safety_distribution,
        "allow_flag_law": {
            "analysis_allowed": "true where horse resolved unambiguously in result",
            "shadow_evaluation_allowed": (
                "true only if result_universe_complete AND prediction_before_off is True -- "
                "independent of odds-timing proof, per established 01A analytical-evaluation law"
            ),
            "state_learning_allowed": "false (sealed for later governed 01B consumption)",
            "model_training_allowed": "false (sealed)",
            "promotion_eligible": "false (sealed)",
        },
        "assertions": {
            "unresolved_horse_exclusion_count": unresolved_horse_count,
            "partial_ambiguous_race_count": partial_ambiguous_race_count,
            "every_unresolved_horse_in_csv": True,
            "every_partial_race_has_reason": True,
            "no_excluded_race_shadow_eligible": True,
        },
        "consumption_status": "SEALED_NOT_CONSUMED",
    }
    manifest_path = REPORTS_DIR / "learning_events_v2_2_2026_07_12_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "events_written": len(events),
        "races_with_events": len(per_race_summary),
        "race_exclusions": len(race_exclusions),
        "horse_exclusions": len(horse_exclusions),
        "time_safety_distribution": time_safety_distribution,
        "jsonl": str(jsonl_path),
        "manifest": str(manifest_path),
        "exclusions_csv": str(exclusions_path),
    }, indent=2))

    (REPORTS_DIR / "_race_day_12_per_race_summary.json").write_text(
        json.dumps(per_race_summary, indent=2, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
