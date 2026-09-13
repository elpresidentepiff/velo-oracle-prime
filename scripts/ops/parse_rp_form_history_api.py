#!/usr/bin/env python3
"""
VÉLØ — Parse RP horse form from the JSON API captures
======================================================
Reads what capture_rp_horse_form_api.py wrote and emits the two files the
passport builder (new_build_horse_passports.py, Step 21E) already globs:

    data/race_shape/form_history_<capture-date>.json
    data/racing_post_account_parsed/<capture-date>/horse_profiles.json

Step 21E is deliberately untouched. It dedupes runs on
(horse_rp_uid, race_date, course_rp_uid|course_key, result_url, position,
sp_raw), so every one of those keys is populated here exactly as the old
HTML parser populated it — otherwise the same run would land twice under
two shapes and quietly double-count a horse's record.

FIELD MAPPING, AND THE TWO THAT ARE NOT OBVIOUS
-----------------------------------------------
    race_outcome_code       -> position        finishing position, verified
                                               against Bow Echo (7947753):
                                               record says 6 starts / 6 wins,
                                               form returns 5 runs all coded 1
    odds_value              -> sp_dec          FRACTIONAL, not decimal.
                                               85/40F carries odds_value 2.125,
                                               so decimal is odds_value + 1.
                                               Reading it as decimal would
                                               price a 3.12 shot at 2.12 and
                                               silently corrupt every ROI
                                               computed downstream.
    odds_desc               -> sp_raw          "85/40F" — the F/J/C suffix is
                                               kept, matching the old scrape
    rp_postmark             -> rpr_rating
    rp_topspeed             -> ts_rating
    official_rating_ran_off -> or_rating       0 means unrated, mapped to None
    other_horse.style_name  -> winner_name     the beaten-by horse when the
                                               subject lost; the runner-up
                                               when it won, so it is only
                                               written as winner_name on a loss
    no_of_runners           -> field_size
    going_type_services_desc-> going
    distance_furlong        -> distance        rendered "8f"

Career aggregates from the /record endpoint are carried through in
horse_summaries as career_* fields. They are authoritative lifetime totals,
unlike the row counts the HTML scrape inferred from whatever it captured.

BOUNDARY
--------
Archive context only. Inherits the trust policy the HTML parser stamped:
ARCHIVE_CONTEXT_ONLY_NOT_SCORING, velo_scoring_allowed false. No scoring
change, no Supabase writes, no Telegram.

Usage:
    python scripts/ops/parse_rp_form_history_api.py --date passport-bank-2026-09-03
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "racing_post_account_raw"
RACE_SHAPE_DIR = ROOT / "data" / "race_shape"
PARSED_DIR = ROOT / "data" / "racing_post_account_parsed"

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"

# Same floor and the same reasoning as the HTML parser: a parse that reads
# every capture and understands none of them is broken, never a quiet night.
MIN_PARSE_RATE = 0.50


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _course_key(name: str | None) -> str | None:
    if not name:
        return None
    key = re.sub(r"\(.*?\)", "", name).strip().lower()
    key = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
    return key or None


def _int_or_none(v):
    try:
        i = int(v)
    except (TypeError, ValueError):
        return None
    return i


def _rating(v):
    """RP writes 0 for 'no rating'; 0 is not a rating and must not average in."""
    i = _int_or_none(v)
    return i if i else None


def _map_run(horse_name: str, horse_uid: int, run: dict) -> dict:
    pos = _int_or_none(run.get("race_outcome_code"))
    dt = str(run.get("race_datetime") or "")
    race_date = dt[:10] or None
    course_name = run.get("course_name")
    ckey = _course_key(course_name)
    course_uid = _int_or_none(run.get("course_uid"))
    race_uid = run.get("race_instance_uid")

    odds_value = run.get("odds_value")
    sp_dec = round(float(odds_value) + 1.0, 3) if isinstance(odds_value, (int, float)) else None

    other = run.get("other_horse") or {}
    other_name = other.get("style_name") if isinstance(other, dict) else None

    furlongs = run.get("distance_furlong")
    distance = f"{furlongs}f" if furlongs not in (None, "") else None

    result_url = None
    if course_uid and ckey and race_date and race_uid:
        result_url = f"/results/{course_uid}/{ckey}/{race_date}/{race_uid}"

    return {
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": False,
        "horse_name": horse_name,
        "horse_rp_uid": horse_uid,
        "race_date": race_date,
        "race_datetime": run.get("race_datetime"),
        "course_name": course_name,
        "course_rp_uid": course_uid,
        "course_key": ckey,
        "course_type_code": run.get("course_type_code"),
        "race_type_code": run.get("race_type_code"),
        "race_class": run.get("race_class"),
        "race_title": run.get("race_instance_title"),
        "distance": distance,
        "distance_furlong": furlongs,
        "distance_yard": run.get("distance_yard"),
        "going": run.get("going_type_services_desc"),
        "going_code": run.get("going_type_code"),
        "weight_lbs": _int_or_none(run.get("weight_carried_lbs")),
        "gear": run.get("horse_head_gear"),
        "first_time_headgear": run.get("first_time_headgear"),
        "position": pos,
        "field_size": _int_or_none(run.get("no_of_runners")),
        "draw": _int_or_none(run.get("draw")),
        "beaten_margin": run.get("distance_to_winner") or run.get("winning_distance"),
        # other_horse is whoever the subject was measured against: the winner
        # when it lost, the runner-up when it won. Only the first is a winner.
        "winner_name": other_name if (pos is not None and pos != 1) else None,
        "runner_up_name": other_name if pos == 1 else None,
        "result_type": ("WIN" if pos == 1 else ("LOSS" if pos is not None else None)),
        "sp_raw": run.get("odds_desc"),
        "sp_dec": sp_dec,
        "jockey_name": run.get("jockey_style_name") or run.get("jockey_short_name"),
        "jockey_rp_uid": _int_or_none(run.get("jockey_uid")),
        "ts_rating": _rating(run.get("rp_topspeed")),
        "rpr_rating": _rating(run.get("rp_postmark")),
        "or_rating": _rating(run.get("official_rating_ran_off")),
        "prize_sterling": run.get("prize_sterling"),
        "close_up_comment": run.get("rp_close_up_comment"),
        "betting_movements": run.get("rp_betting_movements"),
        "race_instance_uid": race_uid,
        "result_url": result_url,
        "source": "rp_horse_profile_form_api",
    }


def _career(record_payload: dict | None) -> dict:
    """Flatten the lifetime record. RP keys it by discipline; 'Rules Races' is
    the all-code total where present, otherwise the widest discipline wins."""
    if not isinstance(record_payload, dict):
        return {}
    rec = record_payload.get("record") or {}
    lifetime = rec.get("lifetime_records") or {}
    if not isinstance(lifetime, dict) or not lifetime:
        return {}
    block = lifetime.get("Rules Races")
    if not isinstance(block, dict):
        block = max(
            (b for b in lifetime.values() if isinstance(b, dict)),
            key=lambda b: b.get("starts") or 0,
            default={},
        )
    best = max((b for b in lifetime.values() if isinstance(b, dict)),
               key=lambda b: (b.get("best_rpr") or 0), default={})
    return {
        "career_starts": _int_or_none(block.get("starts")),
        "career_wins": _int_or_none(block.get("wins")),
        "career_seconds": _int_or_none(block.get("2nds")),
        "career_thirds": _int_or_none(block.get("3rds")),
        "career_prize_sterling": block.get("total_prize"),
        "career_best_rpr": _rating(best.get("best_rpr")),
        "career_best_ts": _rating(best.get("best_ts")),
        "career_disciplines": sorted(lifetime.keys()),
    }


def parse_day(capture_date: str, raw_dir: Path) -> dict:
    day_dir = raw_dir / capture_date
    if not day_dir.exists():
        raise FileNotFoundError(f"No capture directory for {capture_date}: {day_dir}")

    files = sorted(f for f in day_dir.glob("horse_*.json"))
    runs: list[dict] = []
    summaries: list[dict] = []
    profiles: list[dict] = []
    statuses: list[str] = []
    failed = 0

    for fp in files:
        try:
            doc = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            statuses.append("UNREADABLE_JSON")
            failed += 1
            continue

        hid = _int_or_none(doc.get("horse_id"))
        prof = ((doc.get("profile") or {}).get("horse") or {}).get("profile") or {}
        name = prof.get("horse_name") or (doc.get("slug") or "").replace("-", " ").title()

        form_map = ((doc.get("form") or {}).get("form")) or {}
        if not isinstance(form_map, dict):
            statuses.append("NO_FORM_BLOCK")
            failed += 1
            continue

        horse_runs = [_map_run(name, hid, r) for r in form_map.values() if isinstance(r, dict)]
        horse_runs.sort(key=lambda r: r.get("race_datetime") or "", reverse=True)

        # Stamp the authoritative lifetime totals onto every run. The form
        # endpoint caps at 5 runs, so a passport built by counting them would
        # record Banbridge as a 5-start horse when the record endpoint says 27.
        # HorsePassportBuilder reads these off runs[0] and exposes them as
        # career_*_official, leaving the observed-window rates untouched.
        career = _career(doc.get("record"))
        if career:
            for r in horse_runs:
                r["career_starts_official"] = career.get("career_starts")
                r["career_wins_official"] = career.get("career_wins")
                r["career_best_rpr"] = career.get("career_best_rpr")
                r["career_best_ts"] = career.get("career_best_ts")
                r["career_prize_sterling_official"] = career.get("career_prize_sterling")
        runs.extend(horse_runs)

        dates = sorted(r["race_date"] for r in horse_runs if r.get("race_date"))
        summary = {
            "horse": name,
            "horse_uid": hid,
            "runs_found": len(horse_runs),
            "date_range": f"{dates[0]} → {dates[-1]}" if dates else None,
        }
        summary.update(career)
        summaries.append(summary)

        # Debutants with zero runs still need a passport, and Step 21E picks
        # them up from horse_profiles.json rather than from the run list.
        profiles.append({
            "horse_uid": hid,
            "horse_name": name,
            "slug": doc.get("slug"),
            "source_url": doc.get("source_url"),
            "runs_found": len(horse_runs),
        })
        statuses.append("PARSED" if horse_runs else "PARSED_NO_RUNS")

    parsed = len(profiles)
    payload = {
        "capture_date": capture_date,
        "generated_at": _utc_now(),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": False,
        "source": "rp_horse_profile_form_api",
        "captures_seen": len(files),
        "horses_processed": parsed,
        "horses_failed": failed,
        "total_runs": len(runs),
        "status_breakdown": dict(Counter(statuses)),
        "horse_summaries": summaries,
        "runs": runs,
    }

    if files and not parsed:
        payload["status"] = "FAIL_NO_HORSES_PARSED"
        payload["failure_reason"] = (
            f"read {len(files)} capture file(s) and parsed 0 horses; "
            f"statuses: {Counter(statuses).most_common(3)}"
        )
    elif files and parsed / len(files) < MIN_PARSE_RATE:
        payload["status"] = "FAIL_PARSE_RATE_COLLAPSED"
        payload["failure_reason"] = (
            f"parsed {parsed}/{len(files)} ({parsed / len(files):.1%}) captures, "
            f"below the {MIN_PARSE_RATE:.0%} floor"
        )
    elif not files:
        payload["status"] = "FAIL_NO_CAPTURES"
        payload["failure_reason"] = f"no horse_*.json capture files in {day_dir}"
    else:
        payload["status"] = "PASS"
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="Capture tag, e.g. passport-bank-2026-09-03")
    ap.add_argument("--raw-dir", default=str(RAW_DIR))
    args = ap.parse_args()

    payload = parse_day(args.date, Path(args.raw_dir))

    RACE_SHAPE_DIR.mkdir(parents=True, exist_ok=True)
    out = RACE_SHAPE_DIR / f"form_history_{args.date}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    parsed_day = PARSED_DIR / args.date
    parsed_day.mkdir(parents=True, exist_ok=True)
    (parsed_day / "horse_profiles.json").write_text(json.dumps({
        "capture_date": args.date,
        "generated_at": _utc_now(),
        "source": "rp_horse_profile_form_api",
        "pages_seen": payload["captures_seen"],
        "horse_profiles_count": payload["horses_processed"],
        "horse_profiles": [
            {"horse_uid": p["horse_uid"], "horse_name": p["horse_name"],
             "slug": p["slug"], "source_url": p["source_url"]}
            for p in [{"horse_uid": s["horse_uid"], "horse_name": s["horse"],
                       "slug": None, "source_url": None} for s in payload["horse_summaries"]]
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"RP_FORM_HISTORY_API {payload['status']} date={args.date} "
          f"horses={payload['horses_processed']}/{payload['captures_seen']} "
          f"runs={payload['total_runs']} failed={payload['horses_failed']}")
    print(f"  form history : {out}")
    print(f"  profiles     : {parsed_day / 'horse_profiles.json'}")

    if payload["status"].startswith("FAIL"):
        print(f"\n[FAIL] {payload['status']}: {payload.get('failure_reason', '')}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
