#!/usr/bin/env python3
"""
RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01 -- v2 (P0-19..P0-24 fixes)

Portable: resolves repo root from this script's own location (parents[2]),
or accepts --repo-root. No hardcoded absolute worktree paths.

Fixes applied per operator REQUEST CHANGES on PR #151:
 - P0-19: strict pre-race timing computed from canonical race_time_raw (local
   wall clock, unambiguous 24h) + a per-course UTC offset table, NOT the
   ambiguous 'H.MM' off-string heuristic. Three explicit views: full replay,
   strict pre-race, timing-unproven.
 - P0-20: genuine No-RPR reconstructed from the immutable morning snapshot's
   sqpe_no_rpr_shadow_prob field, by horse_id, with duplicate collapse and
   fail-closed tie handling. Radical Shadow is kept as its own signal,
   labelled RADICAL_SHADOW, never as No-RPR.
 - P0-21: New Build / Champion Intent classified per-race (POST_RACE_GENERATED
   / AFTERNOON_PRE_RACE_PROVEN / TIMING_UNPROVEN) using each artifact's own
   generated_at vs canonical off_dt.
 - P0-24: horse_id joins (name fallback only when id missing, flagged),
   source_row_sha256 computed from the raw JSONL line bytes, tier read from
   the snapshot's own 'tier' field.
"""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_root(cli_root: str | None) -> Path:
    if cli_root:
        return Path(cli_root).resolve()
    # scripts/forensics/<this file>.py -> repo root is parents[1]
    return SCRIPT_DIR.parents[1]


# ---------------------------------------------------------------------------
# Timing law: race_time_raw in rp_results_2026_07_15.json is the LOCAL wall
# clock of the race, reformatted as an ISO string with no timezone conversion
# applied (confirmed: Happy Valley off=1.00 -> race_time_raw 13:00:00, i.e.
# RP has already resolved AM/PM into unambiguous 24h form; it is NOT UTC).
# To get true UTC we subtract each course's real July UTC offset.
# ---------------------------------------------------------------------------
COURSE_TZ_OFFSET_HOURS = {
    "Happy Valley": 8,   # HKT, UTC+8, no DST
}
DEFAULT_TZ_OFFSET_HOURS = 1  # GB/IRE BST/IST in July


def off_dt_utc(course: str, race_time_raw: str):
    """Return an aware UTC datetime for a race's true off-time, derived from
    the canonical race_time_raw local wall-clock string + course offset
    table. Returns None if race_time_raw is missing/unparseable."""
    if not race_time_raw:
        return None
    try:
        local_naive = datetime.strptime(race_time_raw[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None
    offset_hours = COURSE_TZ_OFFSET_HOURS.get(course, DEFAULT_TZ_OFFSET_HOURS)
    return local_naive.replace(tzinfo=timezone.utc) - timedelta(hours=offset_hours)


def parse_iso(ts: str):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def sha256_file(p: Path) -> str:
    if not p.exists():
        return "MISSING"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_jsonl_with_raw(p: Path):
    """Returns (parsed_rows, raw_line_sha256_by_index) preserving exact raw
    line bytes for hashing, per P0-24 (source_row_sha256 must be the raw
    JSONL line hash, not a re-serialized JSON hash)."""
    rows = []
    raw_hashes = []
    with open(p, "rb") as f:
        for raw_line in f:
            raw_line_stripped = raw_line.rstrip(b"\n").rstrip(b"\r")
            if not raw_line_stripped.strip():
                continue
            rows.append(json.loads(raw_line_stripped))
            raw_hashes.append(hashlib.sha256(raw_line_stripped).hexdigest())
    return rows, raw_hashes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()

    ROOT = resolve_root(args.repo_root)
    EV = ROOT / "evidence_staging" / "2026-07-15"
    OUT = ROOT / "data" / "reports"
    OUT.mkdir(parents=True, exist_ok=True)

    MORNING_SNAPSHOT = EV / "data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784105122721.jsonl"
    AFTERNOON_SNAPSHOT = EV / "data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784124491047.jsonl"
    RESULTS = EV / "data/results/rp_results_2026_07_15.json"
    RADICAL_SHADOW = EV / "data/reports/radical_shadow_2026_07_15.json"
    NEW_BUILD = EV / "data/new_build/reports/two_lane_readiness_2026_07_15.json"
    CHAMPION_CSV = EV / "data/reports/intent_shadow_scorecard_2026_07_15.csv"
    CHAMPION_AUDIT = EV / "data/reports/intent_shadow_audit_2026_07_15.json"
    SIGMA = EV / "data/sigma_results/sigma_results_2026_07_15.json"
    OBS_MORNING = EV / "data/velo_run_observability_2026_07_15_b8ba4b61.json"
    OBS_AFTERNOON = EV / "data/velo_run_observability_2026_07_15_0e131abc.json"
    RC_MANIFEST = EV / "data/racing_post_account_raw/2026-07-15/manifest.json"
    RESULTS_MANIFEST = EV / "data/racing_post_account_raw/rp-results-2026-07-15/manifest.json"
    RAW_HTML_LIST = EV / "data/racing_post_account_raw/2026-07-15/RAW_HTML_FILENAMES.txt"
    RESULTS_URL_LIST = EV / "data/racing_post_url_lists/rp_results_2026-07-15.txt"
    RACECARD_URL_LIST = EV / "data/racing_post_url_lists/rp_racecards_2026-07-15.txt"
    RACECARD_URL_LIST_INTL = EV / "data/racing_post_url_lists/rp_racecards_2026-07-15_intl.txt"
    COLLECTOR_SCRIPT = EV / "scripts/ops/racing_post_account_collector.py"

    report = {"mission": "RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01", "revision": "v2_post_operator_request_changes", "sections": {}}

    morning_rows, morning_raw_hashes = load_jsonl_with_raw(MORNING_SNAPSHOT)
    afternoon_rows, afternoon_raw_hashes = load_jsonl_with_raw(AFTERNOON_SNAPSHOT)

    # hash lookup keyed by (race_id, horse_id)
    morning_hash_by_key = {}
    for row, h in zip(morning_rows, morning_raw_hashes):
        morning_hash_by_key[(row["race_id"], row.get("horse_id"))] = h

    morning_race_ids = sorted({r["race_id"] for r in morning_rows})
    afternoon_race_ids = sorted({r["race_id"] for r in afternoon_rows})
    morning_run_id = morning_rows[0]["run_id"]
    morning_created_at = morning_rows[0]["created_at"]
    afternoon_run_id = afternoon_rows[0]["run_id"]
    afternoon_created_at = afternoon_rows[0]["created_at"]

    results_doc = json.load(open(RESULTS))
    results_by_id = {r["race_id"]: r for r in results_doc["results"]}

    morning_by_race = defaultdict(list)
    for r in morning_rows:
        morning_by_race[r["race_id"]].append(r)
    afternoon_by_race = defaultdict(list)
    for r in afternoon_rows:
        afternoon_by_race[r["race_id"]].append(r)

    def top_pick_old_velo(rows):
        return sorted(rows, key=lambda x: (x.get("rank") if x.get("rank") is not None else 999))[0]

    def result_lookup_by_horse_id(rid, horse_id, horse_name=None):
        res = results_by_id.get(rid)
        if not res:
            return None, None, None, "NO_RESULT"
        for rr in res.get("runners", []):
            if horse_id is not None and str(rr.get("horse_id")) == str(horse_id):
                return rr.get("position"), rr.get("sp_dec"), rr.get("non_runner", False), "MATCHED_BY_HORSE_ID"
        if horse_name:
            for rr in res.get("runners", []):
                if rr.get("horse") == horse_name:
                    return rr.get("position"), rr.get("sp_dec"), rr.get("non_runner", False), "MATCHED_BY_NAME_FALLBACK"
        return None, None, None, "NO_MATCH"

    # =====================================================================
    # Phase 1 -- manifest / provenance (unchanged from v1, still valid)
    # =====================================================================
    report["sections"]["phase1_morning_manifest"] = {
        "run_id": morning_run_id, "created_at": morning_created_at,
        "race_count": len(morning_race_ids), "runner_count": len(morning_rows),
        "source_file": str(MORNING_SNAPSHOT.relative_to(ROOT)),
        "source_file_sha256": sha256_file(MORNING_SNAPSHOT),
        "classification": "MORNING_RUN_PROVEN",
    }
    report["sections"]["phase1_afternoon_manifest"] = {
        "run_id": afternoon_run_id, "created_at": afternoon_created_at,
        "race_count": len(afternoon_race_ids), "runner_count": len(afternoon_rows),
        "source_file": str(AFTERNOON_SNAPSHOT.relative_to(ROOT)),
        "source_file_sha256": sha256_file(AFTERNOON_SNAPSHOT),
        "classification": "POST_MORNING_DIAGNOSTIC_RUN",
    }

    # =====================================================================
    # P0-19 -- Old VELO: FULL_SNAPSHOT_REPLAY / STRICT_PRE_RACE / TIMING_UNPROVEN
    # =====================================================================
    morning_run_dt = parse_iso(morning_created_at)
    full_replay = []
    strict_pre_race = []
    timing_unproven = []

    for rid in morning_race_ids:
        res = results_by_id.get(rid)
        pick = top_pick_old_velo(morning_by_race[rid])
        horse_id = pick.get("horse_id")
        horse_name = pick.get("top_pick_name")
        if not res:
            timing_unproven.append({"race_id": rid, "reason": "NO_RESULT"})
            continue
        pos, sp, nr, match_method = result_lookup_by_horse_id(rid, horse_id, horse_name)
        off_dt = off_dt_utc(res["course"], res.get("race_time_raw"))
        row_hash = morning_hash_by_key.get((rid, horse_id), "HASH_NOT_FOUND")
        row_record = {
            "race_id": rid, "course": res["course"], "off_time_local": res["off"],
            "off_dt_utc": off_dt.isoformat() if off_dt else None,
            "horse": horse_name, "horse_id": horse_id, "morning_probability": pick.get("velo_prime_prob"),
            "morning_product": pick.get("assigned_product"), "tier": pick.get("tier"),
            "sp_final": sp, "position": pos, "non_runner": nr, "result_match_method": match_method,
            "run_id": morning_run_id, "generated_at": morning_created_at,
            "source_row_sha256": row_hash,
        }
        full_replay.append(row_record)
        if off_dt is None:
            timing_unproven.append({**row_record, "reason": "OFF_DT_UNRESOLVED"})
            continue
        if morning_run_dt < off_dt:
            strict_pre_race.append(row_record)
        else:
            timing_unproven.append({**row_record, "reason": "GENERATED_AFTER_OFF_TIME_POST_RACE"})

    def summarize(rows, label):
        eligible = [r for r in rows if not r["non_runner"]]
        wins = [r for r in eligible if r["position"] == "1"]
        placed = [r for r in eligible if r["position"] in ("2", "3")]
        misses = [r for r in eligible if r["position"] not in ("1", "2", "3")]
        sp_list = [r["sp_final"] for r in wins if r["sp_final"] is not None]
        strike_rate = len(wins) / len(eligible) if eligible else 0
        frame_rate = (len(wins) + len(placed)) / len(eligible) if eligible else 0
        one_unit = (sum(s - 1 for s in sp_list) - (len(eligible) - len(sp_list))) if sp_list else None
        roi = (one_unit / len(eligible)) if (one_unit is not None and eligible) else None
        return {
            "label": label, "total_rows": len(rows), "non_runners": len(rows) - len(eligible),
            "eligible": len(eligible), "wins": len(wins), "placed_only": len(placed), "misses": len(misses),
            "strike_rate": round(strike_rate, 4), "frame_rate": round(frame_rate, 4),
            "average_winner_sp": round(sum(sp_list) / len(sp_list), 3) if sp_list else None,
            "one_unit_sp_return": round(one_unit, 3) if one_unit is not None else None,
            "roi": round(roi, 4) if roi is not None else None,
            "figure_string": f"{len(wins)}/{len(eligible)} (SR={strike_rate*100:.1f}%)",
            "rows": rows,
        }

    old_velo_full = summarize(full_replay, "FULL_SNAPSHOT_REPLAY_INCLUDING_POST_RACE")
    old_velo_strict = summarize(strict_pre_race, "STRICT_PRE_RACE")

    report["sections"]["phase6_old_velo"] = {
        "FULL_SNAPSHOT_REPLAY": {k: v for k, v in old_velo_full.items() if k != "rows"},
        "STRICT_PRE_RACE": {k: v for k, v in old_velo_strict.items() if k != "rows"},
        "TIMING_UNPROVEN_count": len(timing_unproven),
        "timing_unproven_race_ids": [r["race_id"] for r in timing_unproven],
        "note": (
            "FULL_SNAPSHOT_REPLAY includes all 47 morning-scored races regardless of "
            "whether the race had already run before the 08:46:03Z snapshot was "
            "generated -- it is NOT a predictive-performance figure and must never be "
            "quoted as a strike rate. STRICT_PRE_RACE excludes every race whose "
            "canonical off_dt_utc (derived from race_time_raw + course UTC offset, "
            "NOT the ambiguous 'H.MM' off-string) preceded morning generation "
            "(08:46:03Z) -- this includes all 9 Happy Valley races (11:30-15:50 HKT "
            "= 03:30-07:50 UTC, all before 08:46 UTC)."
        ),
    }

    # =====================================================================
    # P0-20 -- genuine No-RPR from sqpe_no_rpr_shadow_prob
    # =====================================================================
    no_rpr_full = []
    no_rpr_strict = []
    no_rpr_ties = []
    for rid in morning_race_ids:
        res = results_by_id.get(rid)
        rows = morning_by_race[rid]
        # collapse exact duplicate horse_id rows
        by_horse = {}
        for r in rows:
            hid = r.get("horse_id")
            if hid not in by_horse:
                by_horse[hid] = r
        candidates = [r for r in by_horse.values() if r.get("sqpe_no_rpr_shadow_prob") is not None]
        if not candidates:
            continue
        candidates.sort(key=lambda x: -x["sqpe_no_rpr_shadow_prob"])
        top_score = candidates[0]["sqpe_no_rpr_shadow_prob"]
        tied = [c for c in candidates if c["sqpe_no_rpr_shadow_prob"] == top_score]
        if len(tied) > 1:
            no_rpr_ties.append({
                "race_id": rid, "tied_horses": [{"horse_id": t.get("horse_id"), "horse": t.get("horse") or t.get("top_pick_name"), "score": top_score} for t in tied],
                "resolution": "FAIL_CLOSED_EXCLUDED_FROM_STRICT_DENOMINATOR",
            })
            continue
        pick = tied[0]
        horse_id = pick.get("horse_id")
        horse_name = pick.get("horse") or pick.get("top_pick_name")
        if not res:
            continue
        pos, sp, nr, match_method = result_lookup_by_horse_id(rid, horse_id, horse_name)
        off_dt = off_dt_utc(res["course"], res.get("race_time_raw"))
        row_hash = morning_hash_by_key.get((rid, horse_id), "HASH_NOT_FOUND")
        row_record = {
            "race_id": rid, "course": res["course"], "off_time_local": res["off"],
            "off_dt_utc": off_dt.isoformat() if off_dt else None,
            "horse": horse_name, "horse_id": horse_id, "no_rpr_score": top_score,
            "sp_final": sp, "position": pos, "non_runner": nr, "result_match_method": match_method,
            "run_id": morning_run_id, "generated_at": morning_created_at,
            "source_row_sha256": row_hash,
        }
        no_rpr_full.append(row_record)
        if off_dt is not None and morning_run_dt < off_dt:
            no_rpr_strict.append(row_record)

    no_rpr_full_summary = summarize(no_rpr_full, "NO_RPR_FULL_SNAPSHOT_REPLAY")
    no_rpr_strict_summary = summarize(no_rpr_strict, "NO_RPR_STRICT_PRE_RACE")

    report["sections"]["phase6_no_rpr_genuine"] = {
        "source_field": "sqpe_no_rpr_shadow_prob (immutable morning snapshot, per-runner)",
        "FULL_SNAPSHOT_REPLAY": {k: v for k, v in no_rpr_full_summary.items() if k != "rows"},
        "STRICT_PRE_RACE": {k: v for k, v in no_rpr_strict_summary.items() if k != "rows"},
        "tie_ledger": no_rpr_ties,
        "note": (
            "This replaces the v1 report's invalid labelling of "
            "radical_shadow_2026_07_15.json as NO_RPR_SHADOW. Radical Shadow is a "
            "distinct, mutable, afternoon-generated decision layer built around Old "
            "VELO's own top horse (status=SHADOW_ONLY_NOT_LIVE, source=mutable "
            "velo_prime_verdicts) -- it is kept separately below as RADICAL_SHADOW "
            "and must never be read as the No-RPR model. The genuine No-RPR lane "
            "lives inside the immutable morning snapshot as sqpe_no_rpr_shadow_prob, "
            "one value per runner, alongside Old VELO's velo_prime_prob -- it shares "
            "the same MORNING_RUN_PROVEN provenance as Old VELO."
        ),
    }

    # Radical Shadow kept separate, correctly labelled
    radical_doc = json.load(open(RADICAL_SHADOW))
    report["sections"]["radical_shadow_separate_signal"] = {
        "artifact": str(RADICAL_SHADOW.relative_to(ROOT)),
        "label": "RADICAL_SHADOW",
        "status_in_source_file": radical_doc.get("status"),
        "generated_at": radical_doc.get("generated_at"),
        "decision_count": len(radical_doc.get("decisions", [])),
        "note": "NOT No-RPR. A separate win/frame-gate decision layer built around Old VELO's own top horse, reading the mutable velo_prime_verdicts table. Explicitly excluded from the four-model comparison.",
    }

    # =====================================================================
    # P0-21 -- New Build / Champion Intent per-race timing
    # =====================================================================
    new_build_doc = json.load(open(NEW_BUILD))
    nb_generated_dt = parse_iso(new_build_doc["generated_at"])
    nb_rows = []
    for card in (new_build_doc.get("race_day_scorecards") or []):
        rid = card.get("race_id")
        res = results_by_id.get(rid)
        if not res:
            continue
        off_dt = off_dt_utc(res["course"], res.get("race_time_raw"))
        lane_a = card.get("lane_a_top3") or []
        top = lane_a[0] if lane_a else None
        horse_name = top.get("horse") if top else None
        pos, sp, nr, match_method = result_lookup_by_horse_id(rid, None, horse_name)
        if off_dt is None:
            timing_status = "TIMING_UNPROVEN"
        elif nb_generated_dt < off_dt:
            timing_status = "AFTERNOON_PRE_RACE_PROVEN"
        else:
            timing_status = "POST_RACE_GENERATED"
        nb_rows.append({
            "race_id": rid, "course": res["course"], "off_time_local": res["off"],
            "horse": horse_name, "lane_decision": top.get("nb_decision_lane") if top else card.get("top_pick_lane"),
            "top_pick_lane_policy": card.get("top_pick_lane"),
            "score": top.get("prob") if top else None,
            "sp_final": sp, "position": pos, "non_runner": nr, "result_match_method": match_method,
            "generated_at": new_build_doc["generated_at"], "timing_status": timing_status,
        })

    champ_rows_raw = list(csv.DictReader(open(CHAMPION_CSV)))
    champ_audit = json.load(open(CHAMPION_AUDIT))
    champ_generated_dt = parse_iso(champ_audit["generated_at"])
    champ_by_race = defaultdict(list)
    for r in champ_rows_raw:
        champ_by_race[r["race_id"]].append(r)
    ci_rows = []
    for rid, rows in champ_by_race.items():
        res = results_by_id.get(rid)
        if not res:
            continue
        top = sorted(rows, key=lambda x: int(x.get("rank_in_race", 999)))[0]
        horse_name = top.get("horse")
        pos, sp, nr, match_method = result_lookup_by_horse_id(rid, top.get("rp_uid"), horse_name)
        off_dt = off_dt_utc(res["course"], res.get("race_time_raw"))
        if off_dt is None:
            timing_status = "TIMING_UNPROVEN"
        elif champ_generated_dt < off_dt:
            timing_status = "AFTERNOON_PRE_RACE_PROVEN"
        else:
            timing_status = "POST_RACE_GENERATED"
        ci_rows.append({
            "race_id": rid, "course": res["course"], "off_time_local": res["off"],
            "horse": horse_name, "score": top.get("champion_intent_shadow_prob"),
            "velo_scoring_allowed": top.get("velo_scoring_allowed"),
            "trust_policy": top.get("trust_policy"), "model_label": top.get("model_label"),
            "sp_final": sp, "position": pos, "non_runner": nr, "result_match_method": match_method,
            "generated_at": champ_audit["generated_at"], "timing_status": timing_status,
        })

    def timing_breakdown(rows):
        c = defaultdict(int)
        for r in rows:
            c[r["timing_status"]] += 1
        return dict(c)

    def perf_for_status(rows, status):
        subset = [r for r in rows if r["timing_status"] == status and not r["non_runner"]]
        wins = sum(1 for r in subset if r["position"] == "1")
        return {"eligible": len(subset), "wins": wins, "strike_rate": round(wins / len(subset), 4) if subset else None}

    report["sections"]["phase7_new_build_per_race_timing"] = {
        "artifact": str(NEW_BUILD.relative_to(ROOT)),
        "generated_at": new_build_doc["generated_at"],
        "timing_breakdown": timing_breakdown(nb_rows),
        "AFTERNOON_PRE_RACE_PROVEN_performance": perf_for_status(nb_rows, "AFTERNOON_PRE_RACE_PROVEN"),
        "POST_RACE_GENERATED_excluded_performance_informational_only": perf_for_status(nb_rows, "POST_RACE_GENERATED"),
        "note": "Lane A top pick shown per race; rows whose nb_decision_lane/top_pick_lane is SUPPRESS or LOW_DATA are policy-suppressed, not live recommendations -- see race_day_15_specialist_winners.csv / four_model CSVs for the explicit lane_decision column.",
        "rows": nb_rows,
    }
    report["sections"]["phase7_champion_intent_per_race_timing"] = {
        "artifact": str(CHAMPION_CSV.relative_to(ROOT)),
        "generated_at": champ_audit["generated_at"],
        "velo_scoring_allowed": False,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING (per source file, applies to all rows)",
        "timing_breakdown": timing_breakdown(ci_rows),
        "AFTERNOON_PRE_RACE_PROVEN_performance": perf_for_status(ci_rows, "AFTERNOON_PRE_RACE_PROVEN"),
        "POST_RACE_GENERATED_excluded_performance_informational_only": perf_for_status(ci_rows, "POST_RACE_GENERATED"),
        "note": "SHADOW_ONLY signal, velo_scoring_allowed=False for every row in the source file -- never a live recommendation regardless of timing status.",
        "rows": ci_rows,
    }

    # =====================================================================
    # Phase 2 -- morning vs afternoon diff (unchanged logic, still valid;
    # regenerated here for consistency with corrected off_dt_utc)
    # =====================================================================
    diff_rows = []
    all_ids = sorted(set(morning_race_ids) | set(afternoon_race_ids))
    afternoon_run_dt = parse_iso(afternoon_created_at)
    for rid in all_ids:
        res = results_by_id.get(rid)
        base_rows = morning_by_race.get(rid) or afternoon_by_race.get(rid)
        course = res["course"] if res else (base_rows[0].get("course") if base_rows else None)
        off = res["off"] if res else None
        m_rows = morning_by_race.get(rid)
        a_rows = afternoon_by_race.get(rid)
        m_pick = top_pick_old_velo(m_rows) if m_rows else None
        a_pick = top_pick_old_velo(a_rows) if a_rows else None
        changed = bool(m_pick and a_pick and m_pick.get("top_pick_name") != a_pick.get("top_pick_name"))
        winner = res.get("winner_horse") if res else None
        m_hit = bool(winner and m_pick and m_pick.get("top_pick_name") == winner)
        a_hit = bool(winner and a_pick and a_pick.get("top_pick_name") == winner)
        off_dt = off_dt_utc(course, res.get("race_time_raw")) if res else None
        afternoon_before_race = (off_dt is not None and afternoon_run_dt < off_dt)
        diff_rows.append({
            "race_id": rid, "course": course, "off_time_local": off,
            "off_dt_utc": off_dt.isoformat() if off_dt else None,
            "morning_pick": m_pick.get("top_pick_name") if m_pick else None,
            "morning_probability": m_pick.get("velo_prime_prob") if m_pick else None,
            "morning_product": m_pick.get("assigned_product") if m_pick else None,
            "afternoon_pick": a_pick.get("top_pick_name") if a_pick else None,
            "afternoon_probability": a_pick.get("velo_prime_prob") if a_pick else None,
            "afternoon_product": a_pick.get("assigned_product") if a_pick else None,
            "changed_pick": changed, "actual_winner": winner,
            "morning_prediction_hit": m_hit, "afternoon_prediction_hit": a_hit,
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

    killarney = next(r for r in diff_rows if r["race_id"] == "924613")
    killarney_result = results_by_id.get("924613")
    kalir_final_sp = None
    if killarney_result:
        for rr in killarney_result.get("runners", []):
            if rr.get("horse") == "Kalir":
                kalir_final_sp = rr.get("sp_dec")
    report["sections"]["phase2_diff_summary"] = {
        "total_races_compared": len(diff_rows),
        "changed_pick_count": sum(1 for r in diff_rows if r["changed_pick"]),
        "changed_pick_race_ids": [r["race_id"] for r in diff_rows if r["changed_pick"]],
        "killarney_924613_anchor": {**killarney, "kalir_final_sp_from_results_file": kalir_final_sp},
    }

    # =====================================================================
    # P0-22 -- manifest recurrence, code-level root cause
    # =====================================================================
    rc_manifest = json.load(open(RC_MANIFEST))
    results_manifest = json.load(open(RESULTS_MANIFEST))
    raw_html_names = [l.strip() for l in open(RAW_HTML_LIST) if l.strip()]
    racecard_urls = [l.strip() for l in open(RACECARD_URL_LIST) if l.strip()]
    racecard_urls_intl = [l.strip() for l in open(RACECARD_URL_LIST_INTL) if l.strip()]
    results_urls = [l.strip() for l in open(RESULTS_URL_LIST) if l.strip()]

    report["sections"]["phase9_manifest_recurrence_v2"] = {
        "classification": "MANIFEST_TRUNCATION_CONFIRMED_RECURRING_ROOT_CAUSE_LOCATED",
        "final_racecard_manifest_final_state": {
            "path": str(RC_MANIFEST.relative_to(ROOT)),
            "url_count": rc_manifest.get("url_count"),
            "latest_url_count": rc_manifest.get("latest_url_count"),
            "captures": len(rc_manifest.get("captures", [])),
            "generated_at": rc_manifest.get("generated_at"),
            "all_captures_are_happy_valley": all("happy-valley" in c.get("source_url", "") for c in rc_manifest.get("captures", [])),
        },
        "raw_html_files_on_disk": {
            "total": len(raw_html_names),
            "happy_valley": sum(1 for n in raw_html_names if "happy_valley" in n),
            "non_happy_valley": sum(1 for n in raw_html_names if "happy_valley" not in n),
        },
        "url_lists": {
            "uk_ire_racecard_urls": len(racecard_urls),
            "intl_racecard_urls_happy_valley": len(racecard_urls_intl),
            "results_url_list_final": len(results_urls),
        },
        "collector_invocations_from_cron_log": [
            "racing_post_account_collector.py capture --date 2026-07-15 --url-list rp_racecards_2026-07-15.txt (Step 3, UK/IRE, 40 URLs)",
            "racing_post_account_collector.py capture --date 2026-07-15 --url-list rp_racecards_2026-07-15_intl.txt (Step 3.5, Happy Valley, 9 URLs) -- runs AFTER Step 3, writes to the SAME manifest.json path",
        ],
        "root_cause_code_location": f"{str(COLLECTOR_SCRIPT.relative_to(ROOT))}:329-334 (function capture_urls)",
        "root_cause_mechanism": (
            "Both Step 3 and Step 3.5 invoke capture_urls() with the SAME output_dir/capture_date "
            "(data/racing_post_account_raw/2026-07-15/), so both write to the SAME manifest.json. "
            "Inside capture_urls(), after each capture the manifest is rebuilt as: "
            "`captures_by_url = {item['source_url']: item for item in existing_captures + captures}` "
            "then `all_captures = [captures_by_url[u] for u in urls if u in captures_by_url]` -- "
            "the final list comprehension filters strictly by membership in THIS invocation's own "
            "`urls` list. When Step 3.5 runs with its 9-URL intl list, `existing_captures` correctly "
            "loads Step 3's 40 previously-captured UK/IRE entries into captures_by_url, but the final "
            "`all_captures` line then DISCARDS all 40 of them because they are not present in Step "
            "3.5's own 9-URL `urls` list. The manifest.json left on disk after Step 3.5 completes "
            "therefore contains only the 9 Happy Valley captures, even though all 49 raw HTML files "
            "(40 UK/IRE + 9 Happy Valley) are still present on disk untouched -- only the manifest's "
            "bookkeeping is truncated, not the underlying captures."
        ),
        "why_47_results_still_worked": (
            "rp_results_2026_07_15.json's race universe (47 races, 7 courses) matches "
            "results_url_list_final (47 URLs), NOT the truncated 9-entry racecard manifest. "
            "build_rp_results_url_list.py derives its URL list from a racecard manifest via "
            "_find_manifest(), which for 2026-07-15 could only have resolved to this same "
            "truncated 9-entry manifest.json (no live-full-racepages-2026-07-15* directory "
            "exists) -- yet the actual results URL list on disk has 47 entries. This proves "
            "the 47-URL results list was NOT produced by a straightforward run of "
            "build_rp_results_url_list.py against the truncated manifest; it required some "
            "other reconstruction path (consistent with the raw HTML files themselves, which "
            "were never deleted, being used to rebuild the full 47-URL list some other way). "
            "The exact reconstruction command was not preserved in evidence available to this "
            "mission (not present in run_full_raceday_cron.log, which only shows the standard "
            "Step 1-3.5 sequence) -- this specific gap remains open."
        ),
        "unresolved_items": [
            "The exact command/script invocation that produced the 47-line rp_results_2026-07-15.txt from a 9-entry manifest was not found in any log copied into this mission's evidence set.",
            "No pre-Step-3.5 snapshot of manifest.json (i.e. the 40-entry UK/IRE-only intermediate state) was preserved on disk to hash directly -- its prior existence is inferred from the collector script's own atomic-write-per-capture behavior and the raw HTML file timestamps, not from a captured intermediate file.",
        ],
    }

    # =====================================================================
    # P0-23 -- trigger origin, corrected classification
    # =====================================================================
    report["sections"]["phase8_trigger_origin_v2"] = {
        "morning_run_08_45": {
            "pipeline_runs_trigger_source": "manual",
            "classification": "MORNING_TRIGGER_ORIGIN_UNPROVEN",
            "reason": "pipeline_runs.trigger_source='manual' only proves the run was not self-reported as an automated GH Actions/Railway-scheduled trigger. No cron-daemon log, shell history, or process-parent evidence in this mission's evidence set attributes the 08:45 invocation to any specific actor or mechanism. It has no corresponding entry anywhere in run_full_raceday_cron.log.",
        },
        "afternoon_run_14_08": {
            "pipeline_runs_trigger_source": "manual",
            "classification": "AFTERNOON_TRIGGER_ORIGIN_UNPROVEN",
            "reason": "run_full_raceday_cron.log proves that scripts/ops/run_full_raceday.py executed with its output redirected into that log file, ending 14:09:41Z. This is evidence the WRAPPER SCRIPT RAN -- it is NOT evidence that the cron daemon itself fired it at that time. The log contains no cron-daemon PID, no crontab invocation marker, and no timestamp confirming the process was launched by cron rather than a manual shell invocation using the identical '>> ... 2>&1' redirection pattern that happens to match the crontab entry's own syntax. Absent a syslog/cron-daemon record, the origin cannot be distinguished between 'cron fired late/on a delayed wake' and 'a human ran the exact same command manually.'",
        },
        "retained_structural_finding": "NO_SINGLE_DAILY_RUN_OWNER_AND_NO_RUN_LOCK -- regardless of which mechanism triggered each run, both pipeline_runs rows are self-reported manual triggers, no locking or duplicate-run guard exists, and the second run silently overwrote the first's mutable artifacts.",
        "gh_actions_scheduler_state": "score-daily.yml confirmed state=disabled_manually since 2026-06-10T16:09:52-07:00, zero runs since -- this remains independently verified and unchanged from v1.",
    }

    OUT_JSON = OUT / "race_day_15_frozen_recount.json"
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    print("Wrote", OUT_JSON)
    print("Wrote", diff_csv_path)

    return {
        "ROOT": ROOT, "OUT": OUT, "report": report,
        "results_by_id": results_by_id, "morning_by_race": morning_by_race,
        "afternoon_by_race": afternoon_by_race, "morning_race_ids": morning_race_ids,
        "old_velo_full_rows": full_replay, "old_velo_strict_rows": strict_pre_race,
        "no_rpr_full_rows": no_rpr_full, "no_rpr_strict_rows": no_rpr_strict,
        "nb_rows": nb_rows, "ci_rows": ci_rows,
        "morning_run_id": morning_run_id, "morning_created_at": morning_created_at,
        "off_dt_utc": off_dt_utc, "result_lookup_by_horse_id": result_lookup_by_horse_id,
        "top_pick_old_velo": top_pick_old_velo,
    }


if __name__ == "__main__":
    main()
