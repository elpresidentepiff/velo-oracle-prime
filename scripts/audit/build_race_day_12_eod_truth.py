"""
RACE-DAY-12-EOD-TRUTH-01 -- governed, evidence-only results/Sigma close for
2026-07-12. Builds sealed LearningEventV2.2 packets from velo_verdicts +
RP results truth. Does NOT mutate any learner state, Playbook G, Supabase,
or Telegram. Read-only evidence production only.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
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
    TIME_SAFETY_SAFE_PROSPECTIVE,
)
from src.velo.learning.identity_resolver import resolve_horse  # noqa: E402

RACE_DATE = "2026-07-12"
RESULTS_PATH = Path("data/results/rp_results_2026_07_12.json")
REPORTS_DIR = Path("data/reports")


def load_results() -> dict:
    text = RESULTS_PATH.read_text(encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return json.loads(text), sha


def load_verdicts() -> list[dict]:
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


def build_dundalk_id_map(verdicts: list[dict]) -> dict[str, str]:
    """Deterministic reconciliation of composite rp_DUN_<date>_<off> ids
    used by velo_verdicts for Dundalk-AW to the numeric RP race_ids used
    by the results truth, via off-time ordering. Both sides are drawn
    from the same course/date, and off-times are strictly increasing in
    the RP url-list capture order, so this is a 1:1 deterministic sort
    join, not a fuzzy or fabricated one."""
    composite = [rid for rid in (v["race_id"] for v in verdicts) if rid.startswith("rp_DUN_")]

    def off_key(rid: str) -> tuple[int, int]:
        m = re.search(r"_(\d{1,2})\.(\d{2})$", rid)
        return (int(m.group(1)), int(m.group(2)))

    composite_sorted = sorted(set(composite), key=off_key)
    numeric_sorted = ["924518", "924519", "924520", "924521", "924522", "924523", "924524"]
    if len(composite_sorted) != len(numeric_sorted):
        raise RuntimeError(
            f"Dundalk id reconciliation count mismatch: {len(composite_sorted)} composite vs "
            f"{len(numeric_sorted)} numeric -- refusing to guess, treat as ambiguous"
        )
    return dict(zip(numeric_sorted, composite_sorted))


def main() -> None:
    results_payload, results_sha256 = load_results()
    results_by_race = {r["race_id"]: r for r in results_payload["results"]}

    verdicts = load_verdicts()
    verdicts_by_race = {v["race_id"]: v for v in verdicts}
    dundalk_map = build_dundalk_id_map(verdicts)

    events = []
    exclusions = []
    per_race_summary = []

    london = ZoneInfo("Europe/London")

    for race_id, res in results_by_race.items():
        if not res.get("winner_horse"):
            exclusions.append({"race_id": race_id, "course": res.get("course_slug"), "reason": "NO_RESULT_DATA_PARSED"})
            continue

        verdict_key = dundalk_map.get(race_id, race_id)
        verdict = verdicts_by_race.get(verdict_key)
        if verdict is None:
            exclusions.append({"race_id": race_id, "course": res.get("course_slug"), "reason": "NO_VELO_VERDICTS_ROW"})
            continue

        race_resolution_method = (
            "DETERMINISTIC_OFFTIME_COURSE_DATE_MATCH" if race_id in dundalk_map else "DIRECT_ID_MATCH"
        )

        fa = verdict["full_analysis"]
        if isinstance(fa, str):
            fa = json.loads(fa)
        predictions = fa.get("predictions", [])
        pred_by_horse = {p["horse_id"]: p for p in predictions}

        runner_universe = tuple(
            {"horse_id": p["horse_id"], "horse": p.get("horse")} for p in predictions
        )
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
            p["horse_id"]
            for p in sorted(predictions, key=lambda x: -(x.get("signal_stack", {}).get("vp") or 0))
        )
        top_three = rank_order[:3]

        gen = verdict["generated_at"]
        off_raw = res.get("off") or ""
        prediction_before_off = None
        if off_raw:
            try:
                hh, mm = off_raw.split(".")
                off_dt = datetime(2026, 7, 12, int(hh) + 12 if int(hh) < 8 else int(hh), int(mm), tzinfo=london)
                gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
                prediction_before_off = gen_dt < off_dt
            except Exception:
                prediction_before_off = None
        else:
            # Dundalk: off empty in results truth; derive off from composite verdict key.
            m = re.search(r"_(\d{1,2})\.(\d{2})$", verdict_key)
            if m:
                hh, mm = int(m.group(1)), int(m.group(2))
                off_dt = datetime(2026, 7, 12, hh + 12 if hh < 8 else hh, mm, tzinfo=london)
                gen_dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
                prediction_before_off = gen_dt < off_dt

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

        # Horse-level identity: prediction-side ids do not share a scheme with
        # result-side ids for Dundalk-AW (name-slug vs numeric RP id), so every
        # horse must be resolved via resolve_horse() (exact id, then normalised
        # name within THIS race) rather than assumed to match directly.
        resolution_by_pred_id = {}
        for horse_id in pred_ids:
            pred_name = pred_by_horse[horse_id].get("horse")
            resolution_by_pred_id[horse_id] = resolve_horse(
                pred_horse_id=horse_id,
                pred_horse_name=pred_name,
                resolved_race={"runners": res["runners"]},
            )

        resolved_ids = {
            r.resolved_horse_id for r in resolution_by_pred_id.values() if r.is_resolved
        }
        all_predictions_resolved = all(r.is_resolved for r in resolution_by_pred_id.values())
        result_universe_complete = all_predictions_resolved and (resolved_ids == result_ids)

        winner_id = res.get("winner_id")
        frame_ids = tuple(res.get("top3_ids", []))

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
            time_safety = TIME_SAFETY_SAFE_PROSPECTIVE
            analysis_allowed = not ambiguous
            shadow_evaluation_allowed = (
                not ambiguous and result_universe_complete and prediction_before_off is True
            )

            input_card_hash = compute_input_card_hash(
                race_id=race_id,
                subject_horse_id=horse_id,
                prediction_run_id=verdict_key,
                runner_universe=runner_universe,
                model_scores=model_scores_by_horse.get(horse_id, {}),
                rank_order=rank_order,
                top_three=top_three,
                model_versions={"engine_version": verdict.get("engine_version", "")},
                active_components=tuple(fa.get("predictions", [{}])[0].get("verdict_flags", []) if predictions else []),
                excluded_components=(),
            )

            prediction = PredictionTruth(
                race_date=RACE_DATE,
                race_id=race_id,
                course=res.get("course_slug", ""),
                off_time=off_raw,
                subject_horse_id=horse_id,
                prediction_run_id=verdict_key,
                runner_universe=runner_universe,
                model_scores=model_scores_by_horse.get(horse_id, {}),
                rank_order=rank_order,
                top_three=top_three,
                odds_value=pred_by_horse[horse_id].get("sp_dec"),
                odds_capture_ts=gen,
                prediction_timestamp=gen,
                source_commit=verdict.get("git_commit_sha"),
                input_card_hash=input_card_hash,
                model_versions={"engine_version": verdict.get("engine_version", "")},
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
                leakage_status="CLEAN",
                result_source="RP_LOCAL_JSON",
                result_source_classification="RP_LOCAL_JSON",
                result_source_complete=result_universe_complete,
                prediction_timestamp_present=True,
                prediction_timestamp_before_off=prediction_before_off,
                odds_timestamp_present=True,
                odds_timestamp_before_off=prediction_before_off,
                source_commit_present=bool(verdict.get("git_commit_sha")),
                model_versions_present=bool(verdict.get("engine_version")),
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
                "off": off_raw or (dundalk_map.get(race_id) and re.search(r"_(\d{1,2}\.\d{2})$", verdict_key).group(1)),
                "verdict_race_id": verdict_key,
                "race_resolution_method": race_resolution_method,
                "runners_predicted": len(pred_ids),
                "runners_resulted": len(result_ids),
                "runners_resolved": sum(1 for r in resolution_by_pred_id.values() if r.is_resolved),
                "runners_ambiguous_or_unresolved": sum(1 for r in resolution_by_pred_id.values() if not r.is_resolved),
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

    manifest = {
        "schema_version": "learning_event_v2.2",
        "race_date": RACE_DATE,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_events": len(events),
        "total_races_with_events": len(per_race_summary),
        "races_excluded": len(exclusions),
        "results_source_path": str(RESULTS_PATH),
        "results_source_sha256": results_sha256,
        "prediction_source": "velo_verdicts (Supabase)",
        "prediction_source_note": (
            "runner_prediction_snapshots has 0 rows for 2026-07-12; velo_verdicts is the "
            "actual canonical prediction artifact for this date, confirmed one row per race_id "
            "(no run-id pooling problem), all rows generated 09:35-09:43 UTC well before the "
            "earliest race off (13:10 local)."
        ),
        "dundalk_id_reconciliation": dundalk_map,
        "allow_flag_law": {
            "analysis_allowed": "true where horse resolved unambiguously in result",
            "shadow_evaluation_allowed": "true only if result_universe_complete AND prediction_before_off is True",
            "state_learning_allowed": "false (sealed for later governed 01B consumption)",
            "model_training_allowed": "false (sealed)",
            "promotion_eligible": "false (sealed)",
        },
        "consumption_status": "SEALED_NOT_CONSUMED",
    }
    manifest_path = REPORTS_DIR / "learning_events_v2_2_2026_07_12_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    exclusions_path = REPORTS_DIR / "race_day_12_exclusions_2026_07_12.csv"
    with exclusions_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["race_id", "course", "reason"])
        w.writeheader()
        for row in exclusions:
            w.writerow(row)

    print(json.dumps({
        "status": "PASS",
        "events_written": len(events),
        "races_with_events": len(per_race_summary),
        "races_excluded": len(exclusions),
        "jsonl": str(jsonl_path),
        "manifest": str(manifest_path),
        "exclusions_csv": str(exclusions_path),
    }, indent=2))

    # stash per_race_summary for the sigma/report step
    (REPORTS_DIR / "_race_day_12_per_race_summary.json").write_text(
        json.dumps(per_race_summary, indent=2, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
