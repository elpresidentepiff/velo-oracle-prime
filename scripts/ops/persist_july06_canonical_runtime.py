#!/usr/bin/env python3
"""
JULY06-CANONICAL-RUNTIME-PERSISTENCE

Idempotent upsert of the July 06 runtime canonical scorecard + learning
event candidates into Supabase. Writes ONLY to public.canonical_model_scorecards
and public.canonical_learning_events. Never touches public.velo_verdicts.

Schema-compatibility note: canonical_model_scorecards has no
promotion_eligible/source_type/sigma_classification columns (see
supabase/migrations/20260706_create_canonical_model_scorecards.sql). Those
labels are packed into the existing learning_class and notes text columns
instead of inventing new columns via an unauthorised schema migration.
canonical_learning_events DOES have promotion_eligible/promotion_block_reason
columns natively (see scripts/ops/build_canonical_learning_events.py), so
those are written as real typed columns there.

Default is --dry-run. --execute required to write.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATE_STR = "2026-07-06"

SCORECARD_CSV = ROOT / "data" / "reports" / "canonical_model_scorecard_2026_07_06_runtime.csv"
EVENTS_CSV = ROOT / "data" / "reports" / "canonical_learning_events_2026_07_06_runtime.csv"
REPORT_PATH = ROOT / "data" / "reports" / "july06_canonical_runtime_persistence_report.md"

SIGMA_CLASSIFICATION = "SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS"
PROMOTION_BLOCK_REASON = "JULY06_RUNTIME_ARTIFACT_LEARNING_NOT_PROMOTION_GRADE"
SCORECARD_NOTES = (
    f"source_type=RUNTIME_RACEDAY_MODEL_SUGGESTION; sigma_classification={SIGMA_CLASSIFICATION}; "
    f"not_official_live_sigma=true; promotion_block_reason={PROMOTION_BLOCK_REASON}"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_commit_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        return "UNKNOWN"


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_bool(v) -> bool | None:
    if v in (None, ""):
        return None
    return str(v).strip().lower() in ("true", "1", "yes")


def _to_num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _to_int(v):
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _load_race_meta() -> dict[str, dict]:
    results_path = ROOT / "data" / "results" / "rp_results_2026_07_06.json"
    d = json.loads(results_path.read_text(encoding="utf-8"))
    return {str(r["race_id"]): r for r in d.get("results", [])}


def _scorecard_payload(row: dict, race_meta: dict, commit_sha: str) -> dict:
    race = race_meta.get(row["race_id"], {})
    return {
        "run_date": DATE_STR,
        "race_id": row["race_id"],
        "course": race.get("course") or None,
        "off_time": race.get("off") or None,
        "model_name": row["model_name"],
        "lane_name": row.get("lane_name") or None,
        "source_path": row["source_path"],
        "source_field": row.get("source_field") or None,
        "sort_direction": None,
        "rank": _to_int(row.get("rank")),
        "horse": row.get("horse") or None,
        # NOT NULL-safe for the UNIQUE constraint: Postgres treats every NULL
        # as distinct, so a nullable horse_id silently breaks idempotent
        # upsert (each re-run inserts fresh duplicates instead of merging).
        # Coalesce to '' so re-runs actually conflict and merge.
        "horse_id": row.get("horse_id") or "",
        "score": _to_num(row.get("score")),
        "sp_dec": _to_num(row.get("sp_dec")),
        "result_position": _to_int(row.get("result_position")),
        "win": _to_bool(row.get("win")),
        "frame": _to_bool(row.get("frame")),
        "policy_decision": row.get("policy_decision") or None,
        "stake_authorised": False,
        "dashboard_visible": _to_bool(row.get("dashboard_visible")),
        "learning_class": "RUNTIME_RACEDAY_MODEL_SUGGESTION",
        "tie_status": row.get("match_kind") or None,
        "notes": SCORECARD_NOTES,
        "generated_from_commit": commit_sha,
    }


EVENT_LESSON = {
    "MODEL_HIT_RUNTIME_ONLY": "Top pick won.",
    "MODEL_MISS_RUNTIME_ONLY": "Top pick lost.",
    "SHADOW_SIGNAL_HIT": "Shadow-lane top pick won — accumulating day-after evidence.",
    "SHADOW_SIGNAL_MISS": "Shadow-lane top pick lost — accumulating day-after evidence.",
    "SHORT_PRICE_TRAP": "Short-priced top pick (SP<=2.5) lost.",
    "VALUE_DISCOVERY": "Top pick won at SP>=6.0 — found value.",
    "POLICY_BLOCKED": "Policy decision withheld stake authority from this pick.",
    "MISSING_ARTIFACT": "Model lane had no artifact to score from on this date.",
    "RESULT_PARSE_GAP": "No parsed result row could be matched for this pick.",
}


def _event_payload(row: dict, commit_sha: str) -> dict:
    evidence = f"source_path={row.get('source_path') or ''}; match_kind={row.get('match_kind') or ''}"
    return {
        "run_date": DATE_STR,
        "race_id": row.get("race_id") or None,
        "model_name": row["model_name"],
        "lane_name": row["model_name"],
        "horse": row.get("horse") or None,
        "horse_id": row.get("horse_id") or "",  # see note in _scorecard_payload — NULL breaks idempotent conflict matching
        "source_scorecard_id": None,
        "source_field": None,
        "rank": 1 if row.get("race_id") else None,
        "score": None,
        "sp_dec": _to_num(row.get("sp_dec")),
        "result_position": _to_int(row.get("result_position")),
        "win": _to_bool(row.get("win")),
        "frame": _to_bool(row.get("frame")),
        "policy_decision": None,
        "stake_authorised": False,
        "dashboard_visible": True,
        "learning_class": "RUNTIME_RACEDAY_MODEL_SUGGESTION",
        "event_type": row["event_class"],
        "promotion_eligible": False,
        "promotion_block_reason": PROMOTION_BLOCK_REASON,
        "lesson": EVENT_LESSON.get(row["event_class"], row["event_class"]),
        "evidence": evidence,
        "generated_from_commit": commit_sha,
    }


def _sb_upsert(table: str, rows: list[dict], conflict_cols: str) -> tuple[int, str | None]:
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return 0, "SUPABASE_URL/KEY not configured"
    req = urllib.request.Request(
        url + "/rest/v1/" + table + f"?on_conflict={conflict_cols}",
        data=json.dumps(rows).encode("utf-8"), method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60):
            return len(rows), None
    except urllib.error.HTTPError as e:
        return 0, f"HTTP {e.code}: {e.read().decode()[:800]}"
    except Exception as e:
        return 0, str(e)


def _sb_count(table: str, run_date: str) -> int | None:
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    req = urllib.request.Request(
        url + "/rest/v1/" + table + f"?select=id&run_date=eq.{run_date}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            cr = r.headers.get("Content-Range", "")
            if "/" in cr:
                return int(cr.split("/")[-1])
            return len(json.loads(r.read().decode()))
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    execute = args.execute

    scorecard_rows = _load_csv(SCORECARD_CSV)
    event_rows = _load_csv(EVENTS_CSV)
    commit_sha = _get_commit_sha()
    race_meta = _load_race_meta()

    # ── Preflight ─────────────────────────────────────────────────────────
    preflight = {
        "scorecard_row_count": len(scorecard_rows),
        "expected_scorecard_rows": 1647,
        "learning_event_count": len(event_rows),
        "expected_learning_events": 325,
        "scorecard_promotion_eligible_column_present": False,  # table has no such column, see docstring
        "scorecard_stake_authorised_true_count": sum(1 for r in scorecard_rows if str(r.get("stake_authorised")).lower() == "true"),
        "event_promotion_eligible_true_count": sum(1 for r in event_rows if str(r.get("promotion_eligible")).lower() == "true"),
        "no_velo_verdicts_target": True,
        "preflight_pass": (
            len(scorecard_rows) == 1647 and len(event_rows) == 325
            and sum(1 for r in scorecard_rows if str(r.get("stake_authorised")).lower() == "true") == 0
            and sum(1 for r in event_rows if str(r.get("promotion_eligible")).lower() == "true") == 0
        ),
    }

    if not preflight["preflight_pass"]:
        print(json.dumps({"status": "PREFLIGHT_FAIL", "preflight": preflight}, indent=2))
        REPORT_PATH.write_text(
            "# July 06 Canonical Runtime Persistence Report\n\nPREFLIGHT FAILED — no writes attempted.\n\n"
            f"```json\n{json.dumps(preflight, indent=2)}\n```\n", encoding="utf-8"
        )
        raise SystemExit(1)

    scorecard_payloads = [_scorecard_payload(r, race_meta, commit_sha) for r in scorecard_rows]
    # canonical_learning_events.race_id is NOT NULL. The one lane-level
    # MISSING_ARTIFACT event (NEW_BUILD_POLICY_V1) has no race_id — it is not
    # tied to any single race. Excluded from Supabase persistence; it remains
    # in the local CSV/audit as a real record of that gap.
    raceless_events = [r for r in event_rows if not (r.get("race_id") or "").strip()]
    race_scoped_events = [r for r in event_rows if (r.get("race_id") or "").strip()]
    event_payloads = [_event_payload(r, commit_sha) for r in race_scoped_events]

    result = {
        "generated_at": _utc_now(),
        "date": DATE_STR,
        "mode": "EXECUTE" if execute else "DRY_RUN",
        "preflight": preflight,
        "scorecard_rows_written": 0,
        "scorecard_write_error": None,
        "event_rows_written": 0,
        "event_write_error": None,
        "post_write_scorecard_count": None,
        "post_write_event_count": None,
        "raceless_events_skipped": len(raceless_events),
    }

    if execute:
        written, error = _sb_upsert(
            "canonical_model_scorecards", scorecard_payloads,
            "run_date,race_id,model_name,lane_name,source_path,source_field,horse_id,rank",
        )
        result["scorecard_rows_written"] = written
        result["scorecard_write_error"] = error
        print(f"canonical_model_scorecards: wrote {written} rows" + (f" ERROR={error}" if error else ""))

        ev_written, ev_error = _sb_upsert(
            "canonical_learning_events", event_payloads,
            "run_date,race_id,model_name,lane_name,horse_id,learning_class,event_type",
        )
        result["event_rows_written"] = ev_written
        result["event_write_error"] = ev_error
        print(f"canonical_learning_events: wrote {ev_written} rows" + (f" ERROR={ev_error}" if ev_error else ""))

        result["post_write_scorecard_count"] = _sb_count("canonical_model_scorecards", DATE_STR)
        result["post_write_event_count"] = _sb_count("canonical_learning_events", DATE_STR)
    else:
        print("DRY RUN — no Supabase write performed. Pass --execute to write.")

    # ── Report ────────────────────────────────────────────────────────────
    md = f"""# July 06 Canonical Runtime Persistence Report

Generated: {result['generated_at']}
Mode: **{result['mode']}**

## Classification

- source_type = RUNTIME_RACEDAY_MODEL_SUGGESTION
- sigma_classification = {SIGMA_CLASSIFICATION}
- not_official_live_sigma = true
- promotion_block_reason = {PROMOTION_BLOCK_REASON}

## Schema-compatibility note

`canonical_model_scorecards` (see `supabase/migrations/20260706_create_canonical_model_scorecards.sql`)
has no `promotion_eligible` / `source_type` / `sigma_classification` columns.
Those labels are packed into the existing `learning_class` (=
`RUNTIME_RACEDAY_MODEL_SUGGESTION`) and `notes` text columns instead of
adding new columns via an unauthorised schema migration. `stake_authorised`
is a real boolean column and is written as `false` on every row.

`canonical_learning_events` natively has `promotion_eligible` and
`promotion_block_reason` typed columns (per `scripts/ops/build_canonical_learning_events.py`) —
written as real typed `false` / `{PROMOTION_BLOCK_REASON}` there.

## Preflight

```json
{json.dumps(preflight, indent=2)}
```

## Write result

- canonical_model_scorecards rows written: **{result['scorecard_rows_written']}**{' (ERROR: ' + result['scorecard_write_error'] + ')' if result['scorecard_write_error'] else ''}
- canonical_learning_events rows written: **{result['event_rows_written']}**{' (ERROR: ' + result['event_write_error'] + ')' if result['event_write_error'] else ''}
- Post-write canonical_model_scorecards count for 2026-07-06: {result['post_write_scorecard_count']}
- Post-write canonical_learning_events count for 2026-07-06: {result['post_write_event_count']}
- velo_verdicts touched: **false** (this script never references that table)

## Known field-mapping gaps (disclosed, not fabricated)

- `canonical_learning_events.source_scorecard_id`, `.score`: not populated (local join did not
  retain the parent scorecard row id or a numeric score per event) — left NULL.
- `canonical_learning_events.rank`: set to 1 for every event, since only top-pick (rank=1) rows
  were ever converted into learning events by the Task 4 builder.
"""
    REPORT_PATH.write_text(md, encoding="utf-8")
    print(f"report={REPORT_PATH}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
