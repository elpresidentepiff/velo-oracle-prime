#!/usr/bin/env python3
"""
build_canonical_learning_events.py

Derives canonical learning events from public.canonical_model_scorecards
ONLY (Supabase, read-only for the source). No dirty-repo reads, no
dashboard reads, no ad-hoc local artifacts for model truth.

Default is --dry-run. --execute required to write, and only to
public.canonical_learning_events.

Usage:
  PYTHONPATH=. python scripts/ops/build_canonical_learning_events.py --date 2026-07-05 --dry-run
  PYTHONPATH=. python scripts/ops/build_canonical_learning_events.py --date 2026-07-05 --execute
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

EVENT_TYPE_MAP = {
    "MODEL_HIT_POLICY_BLOCKED": "VALUE_DISCOVERY_POLICY_BLOCKED",
    "MODEL_HIT_POLICY_ALLOWED": "MODEL_HIT_POLICY_ALLOWED_SHADOW",
    "MODEL_MISS_POLICY_ALLOWED": "POLICY_FALSE_POSITIVE",
    "MODEL_MISS_POLICY_BLOCKED": "MODEL_MISS_POLICY_BLOCKED",
    "PROXY_NOT_A_MODEL_CLAIM": "PROXY_CONTEXT_ONLY",
    "TIE_UNRESOLVED": "RANKING_INTEGRITY_BUG",
    "MODEL_HIT": "MODEL_HIT_NO_POLICY_LAYER",
    "MODEL_MISS": "MODEL_MISS_NO_POLICY_LAYER",
}

CSV_COLUMNS = [
    "run_date", "race_id", "model_name", "lane_name", "horse", "horse_id",
    "source_scorecard_id", "source_field", "rank", "score", "sp_dec",
    "result_position", "win", "frame", "policy_decision", "stake_authorised",
    "dashboard_visible", "learning_class", "event_type", "promotion_eligible",
    "promotion_block_reason", "lesson", "evidence", "generated_from_commit",
]


def _get_commit_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        return "UNKNOWN"


def _sb_get(path: str) -> list[dict]:
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return []
    req = urllib.request.Request(url + "/rest/v1" + path, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


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
        with urllib.request.urlopen(req, timeout=30):
            return len(rows), None
    except urllib.error.HTTPError as e:
        return 0, f"HTTP {e.code}: {e.read().decode()[:500]}"
    except Exception as e:
        return 0, str(e)


def _preflight(date: str) -> list[dict]:
    rows = _sb_get(f"/canonical_model_scorecards?select=*&run_date=eq.{date}")
    if len(rows) < 1:
        raise SystemExit(f"NEEDS_OPERATOR_EXECUTE: no canonical_model_scorecards rows for {date}")
    races = {r["race_id"] for r in rows}
    llr = [r for r in rows if r.get("race_id") == "922118" and r.get("horse") == "Little Lady Rock"]
    if date == "2026-07-05":
        if len(rows) != 374 or len(races) != 22:
            raise SystemExit(f"NEEDS_OPERATOR_EXECUTE: expected 374 rows/22 races, got {len(rows)}/{len(races)}")
        lane_a = [r for r in llr if r["model_name"] == "NEW_BUILD_LANE_A_MODEL"]
        if not lane_a or lane_a[0]["rank"] != 1 or lane_a[0]["policy_decision"] != "NO_EDGE":
            raise SystemExit("NEEDS_OPERATOR_EXECUTE: Little Lady Rock Lane A preflight facts not confirmed")
    return rows


def _lesson_for(row: dict) -> str:
    learning_class = row.get("learning_class")
    horse = row.get("horse")
    model = row.get("model_name")
    sp = row.get("sp_dec")
    if learning_class == "MODEL_HIT_POLICY_BLOCKED":
        return (
            f"{model} ranked {horse} (SP {sp}) as its top selection and it won -- "
            f"a real value-discovery signal -- but policy_v1 classified the pick "
            f"'{row.get('policy_decision')}' and did not clear it for any authorised action. "
            f"This is New Build value discovery, shadow evidence only, not staking profit, not promotion."
        )
    if learning_class == "PROXY_NOT_A_MODEL_CLAIM":
        return f"{model} is a feature-engineering input, not a calibrated model output -- context only, never a model claim."
    if learning_class == "TIE_UNRESOLVED":
        return f"{model}'s ranking field produced a tie for this race -- no principled top pick exists; a ranking-integrity bug, not a prediction."
    if learning_class == "MODEL_HIT":
        return f"{model} picked {horse} (SP {sp}) and it won."
    if learning_class == "MODEL_MISS":
        return f"{model} picked {horse} (SP {sp}) and it did not win."
    return f"{model}: {learning_class}"


def build_events(date: str) -> tuple[list[dict], dict]:
    scorecard_rows = _preflight(date)
    commit_sha = _get_commit_sha()
    events: list[dict] = []
    for row in scorecard_rows:
        learning_class = row.get("learning_class") or "UNKNOWN"
        event_type = EVENT_TYPE_MAP.get(learning_class, "UNCLASSIFIED")
        promotion_eligible = False  # every event on every date is gated in this mission
        block_reason = "POLICY_NO_EDGE_AND_SINGLE_DAY_EVIDENCE" if (
            row.get("race_id") == "922118" and row.get("horse") == "Little Lady Rock"
            and row.get("model_name") in ("NEW_BUILD_LANE_A_MODEL", "NEW_BUILD_LANE_B_MODEL")
        ) else "PROMOTION_GATED_BY_STANDING_HARD_LAW"
        events.append({
            "run_date": row.get("run_date") or date,
            "race_id": row.get("race_id"),
            "model_name": row.get("model_name"),
            "lane_name": row.get("lane_name"),
            "horse": row.get("horse"),
            "horse_id": row.get("horse_id"),
            "source_scorecard_id": row.get("id"),
            "source_field": row.get("source_field"),
            "rank": row.get("rank"),
            "score": row.get("score"),
            "sp_dec": row.get("sp_dec"),
            "result_position": row.get("result_position"),
            "win": row.get("win"),
            "frame": row.get("frame"),
            "policy_decision": row.get("policy_decision"),
            "stake_authorised": row.get("stake_authorised"),
            "dashboard_visible": row.get("dashboard_visible"),
            "learning_class": learning_class,
            "event_type": event_type,
            "promotion_eligible": promotion_eligible,
            "promotion_block_reason": block_reason,
            "lesson": _lesson_for(row),
            "evidence": json.dumps({"source_path": row.get("source_path"), "notes": row.get("notes")}),
            "generated_from_commit": commit_sha,
        })

    audit = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_table": "public.canonical_model_scorecards",
        "scorecard_row_count": len(scorecard_rows),
        "event_count": len(events),
        "event_type_counts": dict(Counter(e["event_type"] for e in events)),
        "promotion_eligible_count": sum(1 for e in events if e["promotion_eligible"]),
        "generated_from_commit": commit_sha,
        "target_table": "public.canonical_learning_events",
    }
    return events, audit


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in CSV_COLUMNS})


def _write_summary(events: list[dict], audit: dict, date: str, path: Path) -> None:
    lines = [
        f"# Canonical Learning Events — {date}",
        f"Generated: {audit['generated_at']}",
        "",
        f"Source: {audit['source_table']} ({audit['scorecard_row_count']} rows)",
        f"Events: {audit['event_count']}",
        "",
        "## Event type counts",
    ]
    for k, v in audit["event_type_counts"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", f"Promotion-eligible events: {audit['promotion_eligible_count']} (must be 0)", "", "## Value-discovery events (policy-blocked hits)"]
    for e in events:
        if e["event_type"] == "VALUE_DISCOVERY_POLICY_BLOCKED":
            lines.append(f"- {e['model_name']} rank {e['rank']}: {e['horse']} (SP {e['sp_dec']}) race {e['race_id']} -- {e['lesson']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canonical learning events from canonical_model_scorecards (read-only source).")
    parser.add_argument("--date", required=True)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    execute = args.execute

    events, audit = build_events(args.date)
    tag = args.date.replace("-", "_")
    out_dir = ROOT / "data" / "reports"
    csv_path = out_dir / f"canonical_learning_events_{tag}.csv"
    summary_path = out_dir / f"canonical_learning_events_{tag}_summary.md"
    audit_path = out_dir / f"canonical_learning_events_{tag}_audit.json"

    _write_csv(events, csv_path)
    _write_summary(events, audit, args.date, summary_path)

    audit["mode"] = "EXECUTE" if execute else "DRY_RUN"
    audit["rows_written"] = 0
    audit["write_error"] = None

    print(f"Scorecard rows read: {audit['scorecard_row_count']}")
    print(f"Events generated: {audit['event_count']}")
    print("Event type counts:", audit["event_type_counts"])
    print(f"Promotion-eligible events: {audit['promotion_eligible_count']} (must be 0)")

    if execute:
        written, error = _sb_upsert(
            "canonical_learning_events", events,
            "run_date,race_id,model_name,lane_name,horse_id,learning_class,event_type",
        )
        audit["rows_written"] = written
        audit["write_error"] = error
        if error:
            print(f"WRITE FAILED: {error}")
        else:
            print(f"WROTE {written} rows to public.canonical_learning_events")
    else:
        print("DRY RUN — no Supabase write performed. Pass --execute to write.")

    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"csv={csv_path}")
    print(f"summary={summary_path}")
    print(f"audit={audit_path}")


if __name__ == "__main__":
    main()
