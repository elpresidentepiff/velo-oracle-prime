#!/usr/bin/env python3
"""
persist_canonical_model_scorecard.py

Idempotent upsert of a canonical_model_scorecard_{date}.csv into Supabase
public.canonical_model_scorecards ONLY. Writes nowhere else.

Default is --dry-run. --execute is required to write.

Usage:
  PYTHONPATH=. python scripts/ops/persist_canonical_model_scorecard.py \
    --date 2026-07-05 \
    --csv data/reports/canonical_model_scorecard_2026_07_05.csv \
    --dry-run

  # Real write, requires explicit operator authorisation:
  PYTHONPATH=. python scripts/ops/persist_canonical_model_scorecard.py \
    --date 2026-07-05 \
    --csv data/reports/canonical_model_scorecard_2026_07_05.csv \
    --execute
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_COLUMNS = [
    "date", "race_id", "course", "off_time", "model_name", "lane_name",
    "source_path", "source_field", "sort_direction", "rank", "horse",
    "horse_id", "score", "sp_dec", "result_position", "win", "frame",
    "policy_decision", "stake_authorised", "dashboard_visible",
    "learning_class", "tie_status", "notes",
]

TABLE_PATH = "/canonical_model_scorecards"


def _get_commit_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        return "UNKNOWN"


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = [c for c in REQUIRED_COLUMNS if rows and c not in rows[0]]
    if missing:
        raise SystemExit(f"CSV missing required columns: {missing}")
    return rows


def _validate_little_lady_rock(rows: list[dict], date: str) -> list[str]:
    """Regression check: for 2026-07-05 the Little Lady Rock proof row must hold."""
    if date != "2026-07-05":
        return []
    problems = []
    race_rows = [r for r in rows if r["race_id"] == "922118" and r["horse"] == "Little Lady Rock"]
    lane_a = [r for r in race_rows if r["model_name"] == "NEW_BUILD_LANE_A_MODEL"]
    if not lane_a:
        problems.append("Missing NEW_BUILD_LANE_A_MODEL row for Little Lady Rock in race 922118")
    elif lane_a[0]["rank"] != "1":
        problems.append(f"Little Lady Rock Lane A rank expected 1, got {lane_a[0]['rank']}")
    elif lane_a[0]["policy_decision"] != "NO_EDGE":
        problems.append(f"Little Lady Rock policy_decision expected NO_EDGE, got {lane_a[0]['policy_decision']}")
    elif lane_a[0]["stake_authorised"] != "False":
        problems.append(f"Little Lady Rock stake_authorised expected False, got {lane_a[0]['stake_authorised']}")
    return problems


def _to_bool(v: str) -> bool | None:
    if v in (None, ""):
        return None
    return str(v).strip().lower() in ("true", "1", "yes")


def _to_num(v: str):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _to_int(v: str):
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def _row_to_payload(row: dict, date: str, commit_sha: str) -> dict:
    return {
        "run_date": date,
        "race_id": row["race_id"],
        "course": row.get("course") or None,
        "off_time": row.get("off_time") or None,
        "model_name": row["model_name"],
        "lane_name": row.get("lane_name") or None,
        "source_path": row["source_path"],
        "source_field": row.get("source_field") or None,
        "sort_direction": row.get("sort_direction") or None,
        "rank": _to_int(row.get("rank")),
        "horse": row.get("horse") or None,
        "horse_id": row.get("horse_id") or None,
        "score": _to_num(row.get("score")),
        "sp_dec": _to_num(row.get("sp_dec")),
        "result_position": _to_int(row.get("result_position")) if str(row.get("result_position") or "").isdigit() else None,
        "win": _to_bool(row.get("win")),
        "frame": _to_bool(row.get("frame")),
        "policy_decision": row.get("policy_decision") or None,
        "stake_authorised": _to_bool(row.get("stake_authorised")),
        "dashboard_visible": _to_bool(row.get("dashboard_visible")),
        "learning_class": row.get("learning_class") or None,
        "tie_status": row.get("tie_status") or None,
        "notes": row.get("notes") or None,
        "generated_from_commit": commit_sha,
    }


def conflict_key_columns() -> tuple[str, ...]:
    """The unique key Supabase upserts on. Single source of truth so the
    in-batch dedupe below and the on_conflict clause can never drift apart."""
    return ("run_date", "race_id", "model_name", "lane_name",
            "source_path", "source_field", "horse_id", "rank")


def _sb_upsert(rows: list[dict]) -> tuple[int, str | None]:
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return 0, "SUPABASE_URL/KEY not configured"
    conflict_cols = ",".join(conflict_key_columns())
    req = urllib.request.Request(
        url + "/rest/v1" + TABLE_PATH + f"?on_conflict={conflict_cols}",
        data=json.dumps(rows).encode("utf-8"),
        method="POST",
        headers={
            "apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            return len(rows), None
    except urllib.error.HTTPError as e:
        return 0, f"HTTP {e.code}: {e.read().decode()[:500]}"
    except Exception as e:
        return 0, str(e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist canonical model scorecard CSV to Supabase (idempotent upsert).")
    parser.add_argument("--date", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    execute = args.execute
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    rows = _load_csv(csv_path)
    problems = _validate_little_lady_rock(rows, args.date)
    if problems:
        raise SystemExit("REGRESSION CHECK FAILED:\n" + "\n".join(problems))

    races = {r["race_id"] for r in rows}
    model_counts = Counter(r["model_name"] for r in rows)
    win_counts = Counter(r["model_name"] for r in rows if r.get("win") == "True")
    learning_counts = Counter(r.get("learning_class") for r in rows)

    print(f"Rows: {len(rows)}")
    print(f"Unique races: {len(races)}")
    print("Model counts:", dict(model_counts))
    print("Win counts by model:", dict(win_counts))
    print("Learning class counts:", dict(learning_counts))

    commit_sha = _get_commit_sha()
    audit = {
        "date": args.date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "csv_path": str(csv_path),
        "row_count": len(rows),
        "unique_races": len(races),
        "model_counts": dict(model_counts),
        "win_counts": dict(win_counts),
        "learning_class_counts": dict(learning_counts),
        "regression_check": "PASS" if not problems else "FAIL",
        "mode": "DRY_RUN" if not execute else "EXECUTE",
        "generated_from_commit": commit_sha,
        "table": "public.canonical_model_scorecards",
        "rows_written": 0,
        "write_error": None,
    }

    if execute:
        payloads = [_row_to_payload(r, args.date, commit_sha) for r in rows]
        # Collapse rows that repeat a conflict key within this batch, keeping the
        # last. Postgres rejects the ENTIRE statement with 21000 "ON CONFLICT DO
        # UPDATE command cannot affect row a second time" if one appears, so a
        # single duplicated source row silently cost a whole day's persist:
        # 2026-07-18's midprice source listed 65 races for 61 distinct ids, which
        # produced 30 duplicate keys, failed the write, and left that date sitting
        # at 0 wins while its CSV held 271 -- and because this script exited 0
        # (see below) every caller reported success.
        _seen: dict[tuple, int] = {}
        _deduped: list[dict] = []
        for p in payloads:
            k = tuple(p.get(c) for c in conflict_key_columns())
            if k in _seen:
                _deduped[_seen[k]] = p
            else:
                _seen[k] = len(_deduped)
                _deduped.append(p)
        dropped = len(payloads) - len(_deduped)
        audit["duplicate_conflict_keys_collapsed"] = dropped
        if dropped:
            print(f"  [WARN] collapsed {dropped} rows sharing a conflict key with an earlier row in this batch")
        payloads = _deduped
        written, error = _sb_upsert(payloads)
        audit["rows_written"] = written
        audit["write_error"] = error
        if error:
            print(f"WRITE FAILED: {error}")
        else:
            print(f"WROTE {written} rows to public.canonical_model_scorecards")
    else:
        print("DRY RUN — no Supabase write performed. Pass --execute to write.")

    out_path = ROOT / "data" / "reports" / f"canonical_model_scorecard_persist_{args.date.replace('-', '_')}_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"audit={out_path}")

    # Exit non-zero when the write failed. This printed "WRITE FAILED" and then
    # returned success, so every orchestrator and backfill driver that checked
    # the return code recorded a clean pass over a database that had not been
    # written to (2026-08-02).
    if audit.get("write_error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
