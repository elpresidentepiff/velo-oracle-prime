"""
backfill_shadow_ledger_outcomes.py
===================================
Takes closed results from data/results_*.json and updates local shadow/paper
ledgers with outcome columns.

Target ledgers:
  data/racing_api_shadow_forward_ledger.csv
  data/velo_execution_bridge_paper_ledger.csv

Matching strategy:
  1. Exact race_id + horse_id match
  2. race_id + normalized horse name (lowercase, strip punctuation)
  NEVER cross-race fuzzy matching.

Added columns:
  result_position, result_position_int, won, placed, sp_decimal,
  flat_profit_loss, outcome_source, outcome_backfilled_at

NO fabrication. If no match found, leave blank.
AUDIT / BACKFILL ONLY — does not alter Supabase or any model.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEDGERS = [
    ROOT / "data" / "racing_api_shadow_forward_ledger.csv",
    ROOT / "data" / "velo_execution_bridge_paper_ledger.csv",
]

NEW_COLS = [
    "result_position",
    "result_position_int",
    "won",
    "placed",
    "sp_decimal",
    "flat_profit_loss",
    "outcome_source",
    "outcome_backfilled_at",
]

# ── Name normalisation ─────────────────────────────────────────────────────────

_STRIP_PUNCT = re.compile(r"[^\w\s]")


def _norm_name(name: str) -> str:
    return _STRIP_PUNCT.sub("", str(name or "")).strip().lower()


# ── Results loader ─────────────────────────────────────────────────────────────

def _load_all_results() -> dict[str, list[dict[str, Any]]]:
    """
    Returns {race_id: [runner_dict, ...]} for all results_*.json files.
    Each runner dict includes horse_id, horse, position, sp_dec, is_winner.
    """
    results: dict[str, list[dict[str, Any]]] = {}
    files = sorted(ROOT.glob("data/results_*.json"))
    print(f"  Loading results from {len(files)} JSON files ...")
    for rf in files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"    WARNING: Could not parse {rf.name}: {e}", file=sys.stderr)
            continue
        races = data.get("results", []) if isinstance(data, dict) else data
        if not isinstance(races, list):
            continue
        for race in races:
            rid = str(race.get("race_id") or "")
            if not rid:
                continue
            runners = race.get("runners", [])
            parsed = []
            for r in runners:
                pos_raw = str(r.get("position") or "")
                try:
                    pos_int = int(pos_raw)
                except ValueError:
                    pos_int = None
                sp_raw = r.get("sp_dec")
                try:
                    sp = float(sp_raw) if sp_raw not in (None, "", "–", "-") else None
                except (ValueError, TypeError):
                    sp = None
                is_winner = pos_int == 1
                parsed.append({
                    "horse_id": str(r.get("horse_id") or ""),
                    "horse": str(r.get("horse") or ""),
                    "horse_norm": _norm_name(str(r.get("horse") or "")),
                    "position": pos_raw,
                    "position_int": pos_int,
                    "sp_dec": sp,
                    "is_winner": is_winner,
                })
            if parsed:
                results[rid] = parsed
    total_races = sum(len(v) for v in results.values())
    print(f"  Loaded {len(results)} races, {total_races} runners from results JSON.")
    return results


# ── Matching ─────────────────────────────────────────────────────────────────

def _find_runner(
    race_id: str,
    horse_id: str,
    horse_name: str,
    results_by_race: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    runners = results_by_race.get(race_id)
    if not runners:
        return None

    # Strategy 1: exact horse_id match
    if horse_id:
        for r in runners:
            if r["horse_id"] == horse_id:
                return r

    # Strategy 2: normalized horse name match within the same race
    if horse_name:
        norm = _norm_name(horse_name)
        for r in runners:
            if r["horse_norm"] == norm:
                return r

    return None


# ── Profit/Loss ───────────────────────────────────────────────────────────────

def _flat_pnl(sp: float | None, is_winner: bool) -> float | None:
    if sp is None or sp <= 0:
        return None
    return round((sp - 1.0) if is_winner else -1.0, 4)


# ── Ledger processing ─────────────────────────────────────────────────────────

def _read_csv(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def _write_csv(path: Path, rows: list[dict], all_fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _process_ledger(
    ledger_path: Path,
    results_by_race: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows, original_fields = _read_csv(ledger_path)
    if not rows:
        return {
            "ledger_name": ledger_path.name,
            "rows_before": 0,
            "outcomes_before": 0,
            "outcomes_after": 0,
            "rows_updated": 0,
            "rows_unresolved": 0,
            "unresolved_reasons": ["LEDGER_EMPTY_OR_MISSING"],
        }

    rows_before = len(rows)

    # Count pre-existing outcomes
    outcomes_before = sum(1 for r in rows if r.get("won") not in (None, ""))

    # Build merged fieldnames (preserve original + add new cols only if absent)
    all_fields = list(original_fields)
    for col in NEW_COLS:
        if col not in all_fields:
            all_fields.append(col)

    backfill_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    rows_updated = 0
    unresolved_reasons: list[str] = []

    for row in rows:
        # Skip if already backfilled
        if row.get("outcome_source") == "results_json" and row.get("won") not in (None, ""):
            continue

        race_id = str(row.get("race_id") or "")
        horse_id = str(row.get("horse_id") or "")
        horse_name = str(row.get("horse") or "")

        if not race_id:
            unresolved_reasons.append("missing_race_id")
            continue

        matched = _find_runner(race_id, horse_id, horse_name, results_by_race)
        if not matched:
            if race_id not in results_by_race:
                unresolved_reasons.append(f"race_not_in_results:{race_id}")
            else:
                unresolved_reasons.append(f"horse_not_matched:{race_id}:{horse_id or horse_name}")
            continue

        # Write outcome fields
        pos_int = matched["position_int"]
        is_winner = matched["is_winner"]
        placed = pos_int is not None and pos_int <= 3
        sp = matched["sp_dec"]

        row["result_position"] = matched["position"]
        row["result_position_int"] = str(pos_int) if pos_int is not None else ""
        row["won"] = "1" if is_winner else "0"
        row["placed"] = "1" if placed else "0"
        row["sp_decimal"] = str(sp) if sp is not None else ""
        row["flat_profit_loss"] = str(_flat_pnl(sp, is_winner)) if sp is not None else ""
        row["outcome_source"] = "results_json"
        row["outcome_backfilled_at"] = backfill_ts
        rows_updated += 1

    outcomes_after = sum(1 for r in rows if r.get("won") not in (None, ""))
    rows_unresolved = rows_before - outcomes_after

    # Write back
    _write_csv(ledger_path, rows, all_fields)

    # Summarize unresolved reasons
    from collections import Counter
    reason_counts = Counter(unresolved_reasons)
    top_reasons = [f"{r} x{c}" for r, c in reason_counts.most_common(10)]

    return {
        "ledger_name": ledger_path.name,
        "rows_before": rows_before,
        "outcomes_before": outcomes_before,
        "outcomes_after": outcomes_after,
        "rows_updated": rows_updated,
        "rows_unresolved": rows_unresolved,
        "unresolved_reasons": top_reasons,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 70)
    print("VÉLØ BACKFILL SHADOW LEDGER OUTCOMES")
    print("=" * 70)
    print("Audit/backfill only — no Supabase writes, no model changes.")
    print()

    results_by_race = _load_all_results()
    if not results_by_race:
        print("WARNING: No results loaded — nothing to backfill.")
        return 1

    reports = []
    for ledger_path in LEDGERS:
        print(f"Processing: {ledger_path.name}")
        report = _process_ledger(ledger_path, results_by_race)
        reports.append(report)
        print(f"  rows_before={report['rows_before']}")
        print(f"  outcomes_before={report['outcomes_before']}")
        print(f"  rows_updated={report['rows_updated']}")
        print(f"  outcomes_after={report['outcomes_after']}")
        print(f"  rows_unresolved={report['rows_unresolved']}")
        if report["unresolved_reasons"]:
            print(f"  top unresolved reasons: {report['unresolved_reasons'][:5]}")
        print()

    print("=" * 70)
    print("BACKFILL COMPLETE")
    for r in reports:
        print(f"  {r['ledger_name']}: updated {r['rows_updated']} rows")
    print("=" * 70)

    # Return per ledger summary as JSON to stdout for orchestrator
    output_json = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ledgers": reports,
    }
    print(json.dumps(output_json, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
