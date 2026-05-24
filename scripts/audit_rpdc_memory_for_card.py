"""
audit_rpdc_memory_for_card.py
-------------------------------
Audits RPDC local memory coverage for a scoring day card.

Input sources (in priority order):
  1. Racecard standard JSON (data/racecards_YYYY_MM_DD_standard.json) — if available
  2. Runner snapshot JSONL (data/runner_snapshots_YYYY_MM_DD_*.jsonl) — if available
  3. Results file (data/results_YYYY_MM_DD.json) — fallback

RPDC memory source:
  data/rpdc_backfill/rpdc_tags_historical.jsonl

Outputs:
  data/reports/rpdc_memory_card_coverage_{date}.json
  data/reports/rpdc_memory_card_coverage_{date}.md

Usage:
  PYTHONPATH=. python scripts/audit_rpdc_memory_for_card.py --date 2026-05-25
  PYTHONPATH=. python scripts/audit_rpdc_memory_for_card.py  # uses today
"""
import argparse
import glob
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.load_rpdc_memory import (
    _normalise_name,
    get_memory_summary_for_runner,
    load_rpdc_memory,
)

DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _extract_date_tag(filename: str) -> str | None:
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _load_runners_from_racecard(date_str: str) -> tuple[list[dict], str]:
    """Try to load runners from standard racecard JSON."""
    date_tag = date_str.replace("-", "_")
    path = DATA_DIR / f"racecards_{date_tag}_standard.json"
    if not path.exists():
        return [], ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        races = data if isinstance(data, list) else data.get("racecards", data.get("races", []))
        runners = []
        for race in races:
            for r in (race.get("runners") or []):
                horse_id = r.get("horse_id", "")
                runners.append({
                    "horse_id": horse_id,
                    "horse": r.get("horse", ""),
                    "race_id": race.get("race_id", ""),
                    "course": race.get("course", ""),
                    "ofr": r.get("ofr"),
                    "rpr": r.get("rpr"),
                    "age": r.get("age"),
                })
        return runners, f"racecard:{path.name}"
    except Exception as e:
        return [], f"racecard_error:{e}"


def _load_runners_from_snapshots(date_str: str) -> tuple[list[dict], str]:
    """Load runners from runner_snapshots JSONL (most recent file for the date)."""
    date_tag = date_str.replace("-", "_")
    snap_files = sorted(glob.glob(str(DATA_DIR / f"runner_snapshots_{date_tag}_*.jsonl")))
    if not snap_files:
        return [], ""
    path = snap_files[-1]
    try:
        seen: dict[str, dict] = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = f"{r.get('horse_id','')}__{r.get('race_id','')}"
                if key not in seen:
                    seen[key] = {
                        "horse_id": r.get("horse_id", ""),
                        "horse": r.get("horse", ""),
                        "race_id": r.get("race_id", ""),
                        "course": r.get("course", ""),
                        "ofr": None,
                        "rpr": None,
                        "age": None,
                    }
        return list(seen.values()), f"snapshot:{Path(path).name}"
    except Exception as e:
        return [], f"snapshot_error:{e}"


def _load_runners_from_results(date_str: str) -> tuple[list[dict], str]:
    """Load runners from results JSON as fallback."""
    date_tag = date_str.replace("-", "_")
    path = DATA_DIR / f"results_{date_tag}.json"
    if not path.exists():
        return [], ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        races = raw.get("results", []) if isinstance(raw, dict) else raw
        runners = []
        for race in (races or []):
            for r in (race.get("runners") or []):
                if r.get("horse_id"):
                    runners.append({
                        "horse_id": r.get("horse_id", ""),
                        "horse": r.get("horse", ""),
                        "race_id": race.get("race_id", ""),
                        "course": race.get("course", ""),
                        "ofr": r.get("or"),
                        "rpr": None,
                        "age": None,
                    })
        return runners, f"results:{path.name}"
    except Exception as e:
        return [], f"results_error:{e}"


def run_audit(date_str: str) -> dict:
    print(f"\n{'='*60}")
    print(f"RPDC MEMORY CARD COVERAGE AUDIT — {date_str}")
    print(f"{'='*60}")

    # Load RPDC memory
    memory = load_rpdc_memory()
    if not memory["_loaded"]:
        print(f"  ERROR: RPDC memory not loaded from {memory['_path']}")
        return {}
    print(f"  RPDC memory: {memory['_total_rows']:,} rows ({memory['_date_range']['first']} → {memory['_date_range']['last']})")

    # Load card runners (priority: racecard > snapshot > results)
    runners, source = _load_runners_from_racecard(date_str)
    if not runners:
        runners, source = _load_runners_from_snapshots(date_str)
    if not runners:
        runners, source = _load_runners_from_results(date_str)

    card_available = bool(runners)
    if not card_available:
        print(f"  WARNING: No card data found for {date_str}")
        print(f"  Expected sources:")
        date_tag = date_str.replace("-", "_")
        print(f"    data/racecards_{date_tag}_standard.json")
        print(f"    data/runner_snapshots_{date_tag}_*.jsonl")
        print(f"    data/results_{date_tag}.json")
        # Report that card is unavailable
        output = {
            "audit_date": date_str,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "card_available": False,
            "card_source": None,
            "rpdc_memory_rows": memory["_total_rows"],
            "rpdc_memory_date_range": memory["_date_range"],
            "status": "CARD_UNAVAILABLE",
        }
        _write_outputs(date_str, output)
        return output

    print(f"  Card source: {source}")
    print(f"  Total runners: {len(runners)}")

    # Build race index
    races_seen: dict[str, list[dict]] = defaultdict(list)
    for r in runners:
        races_seen[r.get("race_id", "?")].append(r)
    print(f"  Total races: {len(races_seen)}")

    # Match each runner to RPDC memory
    match_results: list[dict] = []
    matched = 0
    identity_mismatch = 0  # rp_ ids that couldn't find hrs_ match
    no_memory = 0
    tags_seen: Counter = Counter()
    prior_runs_dist: list[int] = []
    cash_window_count = 0

    for runner in runners:
        ctx = get_memory_summary_for_runner(
            horse_id=runner["horse_id"],
            horse_name=runner["horse"],
            as_of_date=date_str,
            memory=memory,
        )
        if ctx["memory_found"]:
            matched += 1
            if ctx["match_method"] in ("name", "rp_slug"):
                identity_mismatch += 1  # matched by name, not by canonical ID
            for tag in ctx["rpdc_tags"]:
                tags_seen[tag] += 1
            if ctx["prior_runs_count"] is not None:
                prior_runs_dist.append(ctx["prior_runs_count"])
            if ctx["rpdc_cash_window_flag"]:
                cash_window_count += 1
        else:
            no_memory += 1

        match_results.append({
            "horse_id": runner["horse_id"],
            "horse": runner["horse"],
            "race_id": runner["race_id"],
            "course": runner["course"],
            "memory_found": ctx["memory_found"],
            "match_method": ctx["match_method"],
            "memory_date": ctx["memory_date"],
            "prior_runs_count": ctx["prior_runs_count"],
            "rpdc_tag_count": ctx["rpdc_tag_count"],
            "rpdc_primary_tag": ctx["rpdc_primary_tag"],
            "rpdc_release_score": ctx["rpdc_release_score"],
            "rpdc_cash_window_flag": ctx["rpdc_cash_window_flag"],
        })

    match_rate = round(matched / len(runners) * 100, 1) if runners else 0
    cash_window_rate = round(cash_window_count / len(runners) * 100, 1) if runners else 0

    # Prior runs distribution
    prior_runs_buckets = {"0": 0, "1-2": 0, "3-5": 0, "6-10": 0, "11+": 0}
    for n in prior_runs_dist:
        if n == 0:
            prior_runs_buckets["0"] += 1
        elif n <= 2:
            prior_runs_buckets["1-2"] += 1
        elif n <= 5:
            prior_runs_buckets["3-5"] += 1
        elif n <= 10:
            prior_runs_buckets["6-10"] += 1
        else:
            prior_runs_buckets["11+"] += 1

    # Memory adequacy verdict
    if match_rate >= 80:
        memory_verdict = "STRONG — sufficient coverage for RPDC context"
    elif match_rate >= 60:
        memory_verdict = "MODERATE — usable but identity gap is material"
    elif match_rate >= 40:
        memory_verdict = "WEAK — too many runners unmatched for reliable context"
    else:
        memory_verdict = "INSUFFICIENT — memory coverage too low to use as primary source"

    run_ts = datetime.now(timezone.utc).isoformat()

    output = {
        "audit_date": date_str,
        "run_at": run_ts,
        "card_available": True,
        "card_source": source,
        "rpdc_memory_rows": memory["_total_rows"],
        "rpdc_memory_date_range": memory["_date_range"],
        "runner_count": len(runners),
        "race_count": len(races_seen),
        "matched_count": matched,
        "no_memory_count": no_memory,
        "identity_mismatch_count": identity_mismatch,
        "match_rate_pct": match_rate,
        "cash_window_count": cash_window_count,
        "cash_window_rate_pct": cash_window_rate,
        "prior_runs_distribution": prior_runs_buckets,
        "tag_distribution": dict(tags_seen.most_common()),
        "memory_verdict": memory_verdict,
        "status": "COMPLETE",
        "runners": match_results,
    }

    _write_outputs(date_str, output)
    _print_summary(output)
    return output


def _write_outputs(date_str: str, output: dict) -> None:
    json_path = REPORTS_DIR / f"rpdc_memory_card_coverage_{date_str}.json"
    md_path = REPORTS_DIR / f"rpdc_memory_card_coverage_{date_str}.md"

    json_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    lines = [
        f"# RPDC Memory Card Coverage Audit — {date_str}",
        "",
        f"**Generated:** {output.get('run_at', '')}  ",
        f"**Card source:** {output.get('card_source') or 'UNAVAILABLE'}  ",
        "",
        "---",
        "",
    ]

    if not output.get("card_available"):
        lines += [
            "## Status: CARD UNAVAILABLE",
            "",
            f"No card data found for {date_str}. Run after scoring or after racecard is available.",
            "",
            "```",
            f"AUDIT_STATUS: CARD_UNAVAILABLE",
            "```",
        ]
    else:
        lines += [
            "## Coverage",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Runners on card | {output['runner_count']} |",
            f"| Races on card | {output['race_count']} |",
            f"| Matched to RPDC memory | {output['matched_count']} ({output['match_rate_pct']}%) |",
            f"| No memory (unmatched) | {output['no_memory_count']} |",
            f"| Identity mismatch (name-matched, not ID-matched) | {output['identity_mismatch_count']} |",
            f"| Cash window runners | {output['cash_window_count']} ({output['cash_window_rate_pct']}%) |",
            "",
            f"**Memory verdict:** {output['memory_verdict']}",
            "",
            "## Prior Run History Distribution (matched runners)",
            "",
            "| Prior runs | Count |",
            "|---|---|",
        ]
        for bucket, count in output["prior_runs_distribution"].items():
            lines.append(f"| {bucket} | {count} |")

        if output["tag_distribution"]:
            lines += [
                "",
                "## Tag Distribution",
                "",
                "| Tag | Count |",
                "|---|---|",
            ]
            for tag, count in list(output["tag_distribution"].items())[:15]:
                lines.append(f"| `{tag}` | {count} |")

        lines += [
            "",
            "```",
            f"AUDIT_DATE:        {date_str}",
            f"CARD_SOURCE:       {output.get('card_source')}",
            f"RUNNER_COUNT:      {output.get('runner_count')}",
            f"MATCH_RATE:        {output.get('match_rate_pct')}%",
            f"MEMORY_VERDICT:    {output.get('memory_verdict', '').split(' —')[0]}",
            "SUPABASE_READS:    NONE",
            "SCORING_CHANGE:    NONE",
            "```",
        ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  JSON → {json_path}")
    print(f"  MD  → {md_path}")


def _print_summary(output: dict) -> None:
    if not output.get("card_available"):
        print(f"\n  STATUS: CARD_UNAVAILABLE for {output['audit_date']}")
        return
    print(f"\n  Runners: {output['runner_count']} across {output['race_count']} races")
    print(f"  Matched: {output['matched_count']} ({output['match_rate_pct']}%)")
    print(f"  No memory: {output['no_memory_count']}")
    print(f"  ID mismatch (name-matched): {output['identity_mismatch_count']}")
    print(f"  Cash window: {output['cash_window_count']} ({output['cash_window_rate_pct']}%)")
    print(f"  Verdict: {output['memory_verdict']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RPDC memory card coverage audit")
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        help="Audit date (YYYY-MM-DD)")
    args = parser.parse_args()
    run_audit(args.date)


if __name__ == "__main__":
    main()
