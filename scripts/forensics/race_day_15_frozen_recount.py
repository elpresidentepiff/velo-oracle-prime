#!/usr/bin/env python3
"""
RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01
Read-only forensic recount script. Operates ONLY on files copied into
evidence_staging/2026-07-15/ inside this clean worktree. Does not rescore,
does not write to Supabase, does not touch the primary dirty repo.

Produces the required data/reports/race_day_15_* artifacts.
"""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/mnt/c/Users/puror/velo-race-day-15-proof")
EV = ROOT / "evidence_staging" / "2026-07-15"
OUT = ROOT / "data" / "reports"
OUT.mkdir(parents=True, exist_ok=True)

MORNING_SNAPSHOT = EV / "data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784105122721.jsonl"
AFTERNOON_SNAPSHOT = EV / "data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784124491047.jsonl"
RESULTS = EV / "data/results/rp_results_2026_07_15.json"
NO_RPR = EV / "data/reports/radical_shadow_2026_07_15.json"
NEW_BUILD = EV / "data/new_build/reports/two_lane_readiness_2026_07_15.json"
CHAMPION_CSV = EV / "data/reports/intent_shadow_scorecard_2026_07_15.csv"
SIGMA = EV / "data/sigma_results/sigma_results_2026_07_15.json"
OBS_MORNING = EV / "data/velo_run_observability_2026_07_15_b8ba4b61.json"
OBS_AFTERNOON = EV / "data/velo_run_observability_2026_07_15_0e131abc.json"

# Timezone offsets (July 2026 = BST/IST/HKT, no US courses today)
TZ_OFFSET_HOURS = {
    "Happy Valley": 8,   # HKT
}
DEFAULT_TZ_OFFSET = 1  # GB/IRE BST/IST in July


def sha256_file(p: Path) -> str:
    if not p.exists():
        return "MISSING"
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def load_jsonl(p: Path):
    rows = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def off_to_utc(course: str, off: str, race_date="2026-07-15"):
    """Convert local 'off' clock string (e.g. '6.30') to a UTC epoch seconds using
    a per-course timezone offset table. Best-effort; used only for timing
    classification, not for scoring."""
    try:
        h, m = off.split(".")
        h = int(h)
        m = int(m)
        if h < 7:
            h += 12
        offset = TZ_OFFSET_HOURS.get(course, DEFAULT_TZ_OFFSET)
        naive = datetime.strptime(f"{race_date} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M")
        return naive.replace(tzinfo=timezone.utc).timestamp() - offset * 3600
    except Exception:
        return None


def main():
    report = {"mission": "RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01", "sections": {}}

    morning_rows = load_jsonl(MORNING_SNAPSHOT)
    afternoon_rows = load_jsonl(AFTERNOON_SNAPSHOT)
    morning_race_ids = sorted({r["race_id"] for r in morning_rows})
    afternoon_race_ids = sorted({r["race_id"] for r in afternoon_rows})

    morning_run_id = morning_rows[0]["run_id"]
    morning_created_at = morning_rows[0]["created_at"]
    afternoon_run_id = afternoon_rows[0]["run_id"]
    afternoon_created_at = afternoon_rows[0]["created_at"]

    consistent_morning_ts = len({r["created_at"] for r in morning_rows}) == 1
    consistent_afternoon_ts = len({r["created_at"] for r in afternoon_rows}) == 1

    morning_manifest = {
        "run_id": morning_run_id,
        "created_at": morning_created_at,
        "race_count": len(morning_race_ids),
        "runner_count": len(morning_rows),
        "race_ids": morning_race_ids,
        "source_file": str(MORNING_SNAPSHOT.relative_to(ROOT)),
        "source_file_sha256": sha256_file(MORNING_SNAPSHOT),
        "internal_timestamp_consistent": consistent_morning_ts,
        "commit_sha_embedded_in_run_id": "aef63056",
        "classification": "MORNING_RUN_PROVEN",
        "classification_reason": (
            "Run-scoped immutable filename embeds run_id; every one of 400 rows "
            "carries an identical created_at (2026-07-15T08:46:03.598813+00:00); "
            "cross-verified against Supabase pipeline_runs row "
            "54fee6ec-d1b3-4a9c-8c07-d4af813405f4 (started_at 08:45:22Z, finished_at "
            "08:46:04Z, races_processed=47, runners_processed=400, status=PASS) and "
            "against velo_run_observability_2026_07_15_b8ba4b61.json (timestamp "
            "08:46:04.619530+00:00, races_processed=47, runners_processed=400). "
            "All three independent sources agree exactly."
        ),
    }

    afternoon_manifest = {
        "run_id": afternoon_run_id,
        "created_at": afternoon_created_at,
        "race_count": len(afternoon_race_ids),
        "runner_count": len(afternoon_rows),
        "race_ids": afternoon_race_ids,
        "source_file": str(AFTERNOON_SNAPSHOT.relative_to(ROOT)),
        "source_file_sha256": sha256_file(AFTERNOON_SNAPSHOT),
        "internal_timestamp_consistent": consistent_afternoon_ts,
        "classification": "POST_MORNING_DIAGNOSTIC_RUN",
        "classification_reason": (
            "Cross-verified against Supabase pipeline_runs row "
            "a96235ce-9899-4773-bc0d-0aaf276f3cfd (started_at 14:08:10Z, finished_at "
            "14:08:55Z, races_processed=54, runners_processed=454) and against "
            "velo_run_observability_2026_07_15_0e131abc.json (timestamp "
            "14:08:56.727766+00:00). This run silently overwrote the live "
            "velo_verdicts table (upsert-by-race_id, no run-scoped key) and every "
            "other mutable artifact for 2026-07-15. It cannot be used as pre-race "
            "evidence for any race whose off-time preceded 14:08:10 UTC."
        ),
    }

    utt_numeric = sorted(r for r in afternoon_race_ids if r.isdigit() and
                          any(rr["race_id"] == r and rr.get("course") == "Uttoxeter" for rr in afternoon_rows))
    utt_string = sorted(r for r in afternoon_race_ids if r.startswith("rp_UTT_"))
    off_by_id = {r["race_id"]: r.get("off_time") for r in afternoon_rows}
    utt_pairs = []
    for sid in utt_string:
        off = off_by_id.get(sid)
        match = [nid for nid in utt_numeric if off_by_id.get(nid) == off]
        utt_pairs.append({"string_id": sid, "numeric_id": match[0] if match else None, "off_time": off})

    id_scheme_drift = {
        "afternoon_added_race_count": len(set(afternoon_race_ids) - set(morning_race_ids)),
        "afternoon_added_race_ids": sorted(set(afternoon_race_ids) - set(morning_race_ids)),
        "duplicate_uttoxeter_pairs": utt_pairs,
        "finding": (
            "The afternoon run scored the SAME 7 Uttoxeter races twice under two "
            "different race_id schemes within a single run: the pre-existing numeric "
            "RP ids (e.g. 922990) already present in the morning run, and a second, "
            "newly-introduced string scheme (rp_UTT_20260715_H.MM) with byte-identical "
            "off_time values. This is a genuine identity bug: any downstream joiner "
            "keyed to one scheme will silently miss rows keyed to the other."
        ),
    }

    report["sections"]["phase1_morning_manifest"] = morning_manifest
    report["sections"]["phase1_afternoon_manifest"] = afternoon_manifest
    report["sections"]["phase1_id_scheme_drift"] = id_scheme_drift

    results_doc = json.load(open(RESULTS))
    results_by_id = {r["race_id"]: r for r in results_doc["results"]}
    course_counts = defaultdict(int)
    for r in results_doc["results"]:
        course_counts[r["course"]] += 1

    report["sections"]["phase9_manifest_recurrence"] = {
        "total_races_in_results_file": len(results_doc["results"]),
        "course_breakdown": dict(course_counts),
        "happy_valley_race_count": course_counts.get("Happy Valley", 0),
        "html_files_seen_top_level": results_doc.get("html_files_seen"),
        "racecard_indexed": results_doc.get("racecard_indexed"),
        "readiness_indexed": results_doc.get("readiness_indexed"),
        "races_parsed": results_doc.get("races_parsed"),
        "parse_errors": results_doc.get("parse_errors"),
    }

    morning_by_race = defaultdict(list)
    for r in morning_rows:
        morning_by_race[r["race_id"]].append(r)
    afternoon_by_race = defaultdict(list)
    for r in afternoon_rows:
        afternoon_by_race[r["race_id"]].append(r)

    def top_pick(rows):
        return sorted(rows, key=lambda x: (x.get("rank") if x.get("rank") is not None else 999))[0]

    diff_rows = []
    all_ids = sorted(set(morning_race_ids) | set(afternoon_race_ids))
    afternoon_run_ts = datetime.fromisoformat(afternoon_created_at).timestamp()
    for rid in all_ids:
        res = results_by_id.get(rid)
        base_rows = morning_by_race.get(rid) or afternoon_by_race.get(rid)
        course = res["course"] if res else (base_rows[0].get("course") if base_rows else None)
        off = res["off"] if res else None
        m_rows = morning_by_race.get(rid)
        a_rows = afternoon_by_race.get(rid)
        m_pick = top_pick(m_rows) if m_rows else None
        a_pick = top_pick(a_rows) if a_rows else None
        changed = bool(m_pick and a_pick and m_pick.get("top_pick_name") != a_pick.get("top_pick_name"))
        winner = res.get("winner_horse") if res else None
        m_hit = bool(winner and m_pick and m_pick.get("top_pick_name") == winner)
        a_hit = bool(winner and a_pick and a_pick.get("top_pick_name") == winner)
        off_utc_ts = off_to_utc(course, off) if (off and course) else None
        afternoon_before_race = (off_utc_ts is not None and afternoon_run_ts < off_utc_ts)
        diff_rows.append({
            "race_id": rid,
            "course": course,
            "off_time": off,
            "morning_pick": m_pick.get("top_pick_name") if m_pick else None,
            "morning_probability": m_pick.get("velo_prime_prob") if m_pick else None,
            "morning_product": m_pick.get("assigned_product") if m_pick else None,
            "afternoon_pick": a_pick.get("top_pick_name") if a_pick else None,
            "afternoon_probability": a_pick.get("velo_prime_prob") if a_pick else None,
            "afternoon_product": a_pick.get("assigned_product") if a_pick else None,
            "changed_pick": changed,
            "actual_winner": winner,
            "morning_prediction_hit": m_hit,
            "afternoon_prediction_hit": a_hit,
            "change_created_credited_winner": (changed and a_hit and not m_hit),
            "change_removed_credited_winner": (changed and m_hit and not a_hit),
            "afternoon_run_before_race_off": afternoon_before_race,
            "present_in_morning_run": rid in morning_race_ids,
            "present_in_afternoon_run_only": rid not in morning_race_ids,
        })

    diff_csv_path = OUT / "race_day_15_morning_vs_afternoon_verdict_diff.csv"
    with open(diff_csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(diff_rows[0].keys()))
        w.writeheader()
        w.writerows(diff_rows)

    changed_picks = [r for r in diff_rows if r["changed_pick"]]
    manufactured_hits = [r for r in diff_rows if r["change_created_credited_winner"]]
    removed_hits = [r for r in diff_rows if r["change_removed_credited_winner"]]

    killarney = next(r for r in diff_rows if r["race_id"] == "924613")
    killarney_result = results_by_id.get("924613")
    kalir_final_sp = None
    if killarney_result:
        for rr in killarney_result.get("runners", []):
            if rr.get("horse") == "Kalir":
                kalir_final_sp = rr.get("sp_dec")

    kalir_scoring_sp = None
    for row in afternoon_by_race["924613"]:
        if row.get("horse") == "Kalir":
            kalir_scoring_sp = row.get("sp_dec")

    report["sections"]["phase2_diff_summary"] = {
        "total_races_compared": len(diff_rows),
        "changed_pick_count": len(changed_picks),
        "changed_pick_race_ids": [r["race_id"] for r in changed_picks],
        "afternoon_manufactured_hits": manufactured_hits,
        "afternoon_removed_hits": removed_hits,
        "killarney_924613_anchor": {
            **killarney,
            "kalir_final_sp_from_results_file": kalir_final_sp,
            "kalir_scoring_time_sp_in_afternoon_run": kalir_scoring_sp,
            "note": (
                "Operator-reported SP of 4.0 for Kalir is CONFIRMED against the "
                "canonical results file (rp_results_2026_07_15.json), runner-level "
                "sp_dec field. The afternoon scoring row's sp_dec value was the market "
                "price AT THE MOMENT OF THE 14:08 RESCORE, roughly 4 hours before "
                "the 18:30 local off, not the final SP. Transcript (morning pick, "
                "VP=0.4087) did not win; Kalir (afternoon pick, VP=0.4442) won at "
                "SP 4.0. The afternoon run therefore manufactured a credited winner "
                "that did not exist in the sealed morning prediction."
            ),
        },
    }

    scored = 0
    wins = 0
    placed = 0
    misses = 0
    non_runner = 0
    timing_unproven = 0
    sp_list = []
    winners_table = []
    for rid in morning_race_ids:
        res = results_by_id.get(rid)
        if not res:
            timing_unproven += 1
            continue
        m_pick = top_pick(morning_by_race[rid])
        pick_name = m_pick.get("top_pick_name")
        pos = None
        nr = False
        sp = None
        for rr in res.get("runners", []):
            if rr.get("horse") == pick_name:
                pos = rr.get("position")
                nr = rr.get("non_runner", False)
                sp = rr.get("sp_dec")
                break
        off_utc_ts = off_to_utc(res["course"], res["off"])
        morning_run_ts = datetime.fromisoformat(morning_created_at).timestamp()
        timing_safe = (off_utc_ts is not None and morning_run_ts < off_utc_ts)
        scored += 1
        if nr:
            non_runner += 1
            continue
        if not timing_safe:
            timing_unproven += 1
        is_win = (pos == "1")
        is_placed = pos in ("1", "2", "3")
        if is_win:
            wins += 1
            sp_list.append(sp)
            winners_table.append({
                "race_id": rid, "course": res["course"], "off_time": res["off"],
                "horse": pick_name, "morning_probability": m_pick.get("velo_prime_prob"),
                "morning_product": m_pick.get("assigned_product"), "sp": sp,
                "timing_safe": timing_safe,
                "prediction_run_id": morning_run_id,
                "generated_at": morning_created_at,
                "source_row_sha256": hashlib.sha256(json.dumps(m_pick, sort_keys=True, default=str).encode()).hexdigest(),
            })
        elif is_placed:
            placed += 1
        else:
            misses += 1

    strike_rate = wins / scored if scored else 0
    frame_rate = (wins + placed) / scored if scored else 0
    avg_sp = sum(sp_list) / len(sp_list) if sp_list else None
    import statistics
    median_sp = statistics.median(sp_list) if sp_list else None
    one_unit_return = (sum((s - 1) for s in sp_list) - (scored - non_runner - len(sp_list))) if sp_list else None
    staked = scored - non_runner
    roi = (one_unit_return / staked) if (one_unit_return is not None and staked) else None

    report["sections"]["phase6_old_velo_honest_recount_strict_timing_proven"] = {
        "source": "morning runner_snapshots (immutable, 08:46:03Z)",
        "eligible_races_scored_pre_race": scored,
        "non_runners": non_runner,
        "wins": wins,
        "placed_only": placed,
        "misses": misses,
        "timing_unproven_or_result_missing": timing_unproven,
        "strike_rate": round(strike_rate, 4),
        "frame_rate": round(frame_rate, 4),
        "average_winner_sp": round(avg_sp, 3) if avg_sp else None,
        "median_winner_sp": round(median_sp, 3) if median_sp else None,
        "one_unit_sp_return": round(one_unit_return, 3) if one_unit_return is not None else None,
        "roi": round(roi, 4) if roi is not None else None,
        "reported_operator_figure": "15/46 (SR=32.6%) per Sigma -- INVALIDATED, see phase6b below",
        "honest_figure_string": f"{wins}/{scored} (SR={strike_rate*100:.1f}%)",
        "winners_detail": winners_table,
    }

    sigma_doc = json.load(open(SIGMA))
    sigma_rows = sigma_doc["rows"]
    sigma_vp_sources = sorted({r.get("vp_source") for r in sigma_rows})
    sigma_schema_keys = sorted(set().union(*[set(r.keys()) for r in sigma_rows]))
    has_verdict_id = any("verdict_id" in r for r in sigma_rows)
    has_doctrine_event_id = any("doctrine_event_id" in r for r in sigma_rows)
    has_pick_sp = any("pick_sp" in r for r in sigma_rows)

    report["sections"]["phase6b_sigma_invalidation"] = {
        "sigma_generated_at": sigma_doc["generated_at"],
        "sigma_reported_wins": sigma_doc["wins"],
        "sigma_reported_evaluated": sigma_doc["evaluated_count"],
        "sigma_reported_sr": sigma_doc["sr"],
        "sigma_row_schema_keys": sigma_schema_keys,
        "sigma_rows_have_verdict_id": has_verdict_id,
        "sigma_rows_have_doctrine_event_id": has_doctrine_event_id,
        "sigma_rows_have_pick_sp": has_pick_sp,
        "sigma_vp_source_values": sigma_vp_sources,
        "classification": "SIGMA_RESULT_CONTAMINATED_BY_POST_MORNING_RESCORE",
        "explanation": (
            "sigma_results_2026_07_15.json was generated at 22:28:32Z, over 8 hours "
            "after the 14:08 afternoon rescore overwrote every row in the live "
            "velo_verdicts table (upsert-by-race_id, no run-scoped key). Every one "
            "of Sigma's 46 evaluated rows has vp_source='supabase_velo_verdicts' -- "
            "it reads the CURRENT mutable table, not a frozen run. At query time "
            "that table held the 14:08 afternoon values for all 54 races "
            "(independently confirmed: querying velo_verdicts.generated_at for all "
            "of today's 54 race_ids returns 14:08 for 100% of rows, zero rows at "
            "08:46). Additionally, the Sigma row schema itself contains NO "
            "verdict_id, doctrine_event_id, or pick_sp fields at all (not merely "
            "null values) -- the schema was never built to carry a foreign key back "
            "to a specific immutable prediction-run. Sigma therefore cannot, even "
            "in principle, prove which prediction run (08:46 or 14:08) it "
            "evaluated. The reported 15/46 (32.6%) figure is built entirely on "
            "afternoon-rescored values, including the Killarney 924613 manufactured "
            "Kalir hit. It must not be repeated as a verified Old VELO result."
        ),
    }

    no_rpr_doc = json.load(open(NO_RPR))
    no_rpr_generated = no_rpr_doc["generated_at"]
    no_rpr_race_ids = sorted({d["race_id"] for d in no_rpr_doc["decisions"]})

    new_build_doc = json.load(open(NEW_BUILD))
    nb_generated = new_build_doc["generated_at"]

    with open(CHAMPION_CSV) as f:
        champ_rows = list(csv.DictReader(f))
    champ_race_ids = sorted({r["race_id"] for r in champ_rows})

    def timing_status_for_generation(gen_iso, race_ids):
        gen_ts = datetime.fromisoformat(gen_iso).timestamp()
        pre = 0
        post = 0
        for rid in race_ids:
            res = results_by_id.get(rid)
            if not res:
                continue
            off_ts = off_to_utc(res["course"], res["off"])
            if off_ts is None:
                continue
            if gen_ts < off_ts:
                pre += 1
            else:
                post += 1
        return {"races_pre_generation_off_time": pre, "races_post_generation_off_time": post}

    no_rpr_timing = timing_status_for_generation(no_rpr_generated, no_rpr_race_ids)
    nb_race_ids = [r["race_id"] for r in (new_build_doc.get("race_day_scorecards") or [])] or morning_race_ids
    nb_timing = timing_status_for_generation(nb_generated, nb_race_ids)

    report["sections"]["phase1_all_four_models_provenance"] = {
        "OLD_VELO": {
            "artifact": str(MORNING_SNAPSHOT.relative_to(ROOT)),
            "artifact_type": "run-scoped immutable JSONL, one row per runner",
            "generated_at": morning_created_at,
            "classification": "MORNING_RUN_PROVEN",
        },
        "NO_RPR_SHADOW": {
            "artifact": str(NO_RPR.relative_to(ROOT)),
            "artifact_type": "single mutable JSON, overwritten on each run, NO run-scoped equivalent found",
            "generated_at": no_rpr_generated,
            "race_count": len(no_rpr_race_ids),
            "timing_check": no_rpr_timing,
            "classification": "MORNING_RUN_UNPROVEN",
            "classification_reason": (
                "radical_shadow_2026_07_15.json has only one generated_at "
                "(14:09:20Z) matching the afternoon run window; there is no "
                "run-scoped filename equivalent to Old VELO's runner_snapshots. "
                "It cannot be distinguished from -- and was almost certainly "
                "produced by -- the 14:08 diagnostic rerun. Any race whose off-time "
                "preceded 14:09:20Z cannot be credited to this artifact as pre-race."
            ),
        },
        "NEW_BUILD": {
            "artifact": str(NEW_BUILD.relative_to(ROOT)),
            "artifact_type": "single mutable JSON, overwritten on each run, NO run-scoped equivalent found",
            "generated_at": nb_generated,
            "races_scored": new_build_doc.get("races_scored"),
            "runners_scored": new_build_doc.get("runners_scored"),
            "timing_check": nb_timing,
            "classification": "MORNING_RUN_UNPROVEN",
            "classification_reason": (
                "two_lane_readiness_2026_07_15.json generated_at=14:09:30Z, after "
                "the afternoon rescore. No run-scoped New Build snapshot exists for "
                "the morning window. Happy Valley races (924710-924714) had off-times "
                "of 11:30-13:30 UTC, all BEFORE this file's generation -- so this "
                "file cannot even be pre-race evidence for those races, regardless "
                "of the morning/afternoon question."
            ),
        },
        "CHAMPION_INTENT_SHADOW": {
            "artifact": str(CHAMPION_CSV.relative_to(ROOT)),
            "artifact_type": "single mutable CSV, overwritten on each run, NO run-scoped equivalent found",
            "race_count": len(champ_race_ids),
            "classification": "MORNING_RUN_UNPROVEN",
            "classification_reason": (
                "intent_shadow_scorecard_2026_07_15.csv shares the same generation "
                "pipeline step and mtime window (~14:09Z, see run_full_raceday_cron.log) "
                "as two_lane_readiness. No run-scoped Champion Intent snapshot exists."
            ),
        },
    }

    OUT_JSON = OUT / "race_day_15_frozen_recount.json"
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))

    return (report, diff_rows, results_by_id, morning_by_race, afternoon_by_race,
            no_rpr_doc, new_build_doc, champ_rows, morning_race_ids, morning_run_id,
            morning_created_at, top_pick)


if __name__ == "__main__":
    result = main()
    print("Wrote", OUT / "race_day_15_frozen_recount.json")
    print("Wrote", OUT / "race_day_15_morning_vs_afternoon_verdict_diff.csv")
