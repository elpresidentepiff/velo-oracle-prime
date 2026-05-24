"""
audit_rpdc_historical_coverage.py
-----------------------------------
Audits RPDC coverage across all historical scored dates.
LOCAL READ-ONLY — no Supabase writes.

Queries:
  - Local results files (data/results_YYYY_MM_DD.json)
  - Local verdict files (data/velo_prime_verdicts_YYYY_MM_DD.json)
  - Local sigma files (data/sigma_results/sigma_results_YYYY_MM_DD.json)
  - Supabase racing_horse_runs (read-only, optional — skipped if no credentials)
  - Supabase runner_release_candidates (read-only, optional)

Outputs:
  - data/reports/rpdc_historical_coverage_latest.json
  - data/reports/rpdc_historical_coverage_latest.md

Usage:
  source venv/bin/activate
  PYTHONPATH=. python scripts/audit_rpdc_historical_coverage.py
"""
import json
import logging
import os
import re
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

log = logging.getLogger("velo.audit_rpdc_coverage")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DATA_DIR = ROOT / "data"
SIGMA_DIR = DATA_DIR / "sigma_results"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Accept": "application/json",
}

_DATE_TAG_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})")  # matches YYYY_MM_DD in filename
_DATE_ISO_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")       # matches YYYY-MM-DD in filename


def _normalise_date(date_str: str) -> str:
    """Convert YYYY_MM_DD or YYYY-MM-DD to YYYY-MM-DD."""
    return date_str.replace("_", "-")


def _extract_date_tag(filename: str) -> str | None:
    m = _DATE_TAG_RE.search(filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _DATE_ISO_RE.search(filename)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Local file discovery
# ---------------------------------------------------------------------------

def _discover_results_files() -> dict[str, Path]:
    """Returns {date_str: path} for all results_{date}.json files."""
    out: dict[str, Path] = {}
    for p in sorted(DATA_DIR.glob("results_*.json")):
        if "partial" in p.name:
            continue
        d = _extract_date_tag(p.name)
        if d:
            out[d] = p
    return out


def _discover_verdict_files() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in sorted(DATA_DIR.glob("velo_prime_verdicts_*.json")):
        d = _extract_date_tag(p.name)
        if d:
            out[d] = p
    return out


def _discover_sigma_files() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in sorted(SIGMA_DIR.glob("sigma_results_*.json")):
        d = _extract_date_tag(p.name)
        if d:
            out[d] = p
    return out


# ---------------------------------------------------------------------------
# Local file inspection
# ---------------------------------------------------------------------------

def _inspect_results(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        races = data.get("results", []) if isinstance(data, dict) else data
        race_count = len(races)
        runner_count = sum(len(r.get("runners", [])) for r in races if isinstance(r, dict))
        return {"race_count": race_count, "runner_count": runner_count, "error": None}
    except Exception as e:
        return {"race_count": 0, "runner_count": 0, "error": str(e)}


def _inspect_verdicts(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        races = data if isinstance(data, list) else []
        race_count = len(races)
        rpdc_statuses: Counter = Counter()
        total_tag_count = 0
        for race in races:
            top = race.get("top", {}) or {}
            status = top.get("rpdc_lookup_status")
            if status is None:
                status = "missing_field"
            rpdc_statuses[status] += 1
            total_tag_count += top.get("rpdc_tag_count") or 0
        return {
            "race_count": race_count,
            "rpdc_statuses": dict(rpdc_statuses),
            "total_rpdc_tags": total_tag_count,
            "any_attached": rpdc_statuses.get("attached", 0) > 0,
            "attached_count": rpdc_statuses.get("attached", 0),
            "error": None,
        }
    except Exception as e:
        return {
            "race_count": 0,
            "rpdc_statuses": {},
            "total_rpdc_tags": 0,
            "any_attached": False,
            "attached_count": 0,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Supabase read (optional)
# ---------------------------------------------------------------------------

def _sb_paginate(path: str, select_fields: str = "run_date") -> list[dict]:
    """Read all rows from a Supabase table, paginating until exhausted."""
    if not SB_URL or not SB_KEY:
        return []
    all_rows: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        url = f"{SB_URL}/rest/v1{path}?select={select_fields}&limit={page_size}&offset={offset}&order=run_date"
        req = urllib.request.Request(url, headers=SB_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                batch = json.loads(r.read().decode())
                if not batch:
                    break
                all_rows.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size
        except Exception as e:
            log.warning("sb_paginate failed at offset=%d: %s", offset, e)
            break
    return all_rows


def _load_supabase_horse_runs() -> Counter:
    """Returns Counter of {date_str: row_count} from racing_horse_runs."""
    log.info("Fetching racing_horse_runs dates from Supabase …")
    rows = _sb_paginate("/racing_horse_runs", "run_date")
    log.info("  → %d rows fetched", len(rows))
    return Counter(row["run_date"] for row in rows)


def _load_supabase_rpdc_candidates() -> Counter:
    """Returns Counter of {date_str: row_count} from runner_release_candidates."""
    log.info("Fetching runner_release_candidates dates from Supabase …")
    rows = _sb_paginate("/runner_release_candidates", "run_date")
    log.info("  → %d rows fetched", len(rows))
    return Counter(row["run_date"] for row in rows)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

_CLASSIFICATIONS = (
    "RPDC_COMPLETE",
    "HORSE_RUNS_PRESENT_TAGS_MISSING",
    "RESULTS_PRESENT_HORSE_RUNS_MISSING",
    "SCORED_NO_RESULTS",
    "RESULTS_ONLY_NOT_SCORED",
    "NOT_ELIGIBLE",
)


def _classify(
    has_results: bool,
    has_verdict: bool,
    has_sigma: bool,
    horse_runs_rows: int | None,
    rpdc_candidate_rows: int | None,
    verdict_any_attached: bool,
) -> str:
    supabase_available = horse_runs_rows is not None

    if has_verdict and verdict_any_attached and (rpdc_candidate_rows or 0) > 0:
        return "RPDC_COMPLETE"

    if supabase_available and (horse_runs_rows or 0) > 0 and has_results:
        # Horse history exists — RPDC tags just haven't been built yet
        return "HORSE_RUNS_PRESENT_TAGS_MISSING"

    if has_results and (not supabase_available or (horse_runs_rows or 0) == 0):
        return "RESULTS_PRESENT_HORSE_RUNS_MISSING"

    if has_verdict and not has_results:
        return "SCORED_NO_RESULTS"

    if has_results and not has_verdict:
        return "RESULTS_ONLY_NOT_SCORED"

    return "NOT_ELIGIBLE"


def _backfill_eligible(has_results: bool, horse_runs_rows: int | None) -> str:
    """
    LOCAL_BACKFILL_ELIGIBLE: results file present → can run local backfill script
    SUPABASE_INGEST_ELIGIBLE: results present, horse_runs missing → needs operator approval
    HORSE_RUNS_PRESENT: history already in DB, only RPDC tags need rebuild
    NOT_ELIGIBLE: no results file
    """
    if not has_results:
        return "NOT_ELIGIBLE"
    if horse_runs_rows is None:
        # No Supabase info
        return "LOCAL_BACKFILL_ELIGIBLE"
    if horse_runs_rows == 0:
        return "SUPABASE_INGEST_ELIGIBLE"  # requires operator approval
    return "HORSE_RUNS_PRESENT"


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def run_audit() -> dict:
    log.info("=== RPDC Historical Coverage Audit ===")

    results_files = _discover_results_files()
    verdict_files = _discover_verdict_files()
    sigma_files = _discover_sigma_files()

    log.info(
        "Local files — results: %d, verdicts: %d, sigma: %d",
        len(results_files), len(verdict_files), len(sigma_files),
    )

    supabase_available = bool(SB_URL and SB_KEY)
    horse_runs_by_date: Counter = Counter()
    rpdc_candidates_by_date: Counter = Counter()

    if supabase_available:
        horse_runs_by_date = _load_supabase_horse_runs()
        rpdc_candidates_by_date = _load_supabase_rpdc_candidates()
    else:
        log.warning("Supabase credentials absent — skipping DB row counts")

    # Union of all known dates
    all_dates = sorted(
        set(results_files) | set(verdict_files) | set(sigma_files)
    )
    log.info("Total unique dates to audit: %d", len(all_dates))

    rows: list[dict] = []
    classification_counts: Counter = Counter()
    backfill_counts: Counter = Counter()

    for date_str in all_dates:
        has_results = date_str in results_files
        has_verdict = date_str in verdict_files
        has_sigma = date_str in sigma_files

        results_info = _inspect_results(results_files[date_str]) if has_results else {}
        verdict_info = _inspect_verdicts(verdict_files[date_str]) if has_verdict else {}

        horse_runs = horse_runs_by_date.get(date_str, 0) if supabase_available else None
        rpdc_cands = rpdc_candidates_by_date.get(date_str, 0) if supabase_available else None

        verdict_any_attached = verdict_info.get("any_attached", False)

        classification = _classify(
            has_results, has_verdict, has_sigma,
            horse_runs, rpdc_cands, verdict_any_attached,
        )
        backfill = _backfill_eligible(has_results, horse_runs)

        classification_counts[classification] += 1
        backfill_counts[backfill] += 1

        row = {
            "date": date_str,
            "classification": classification,
            "backfill_eligibility": backfill,
            "results_file": has_results,
            "results_race_count": results_info.get("race_count"),
            "results_runner_count": results_info.get("runner_count"),
            "verdict_file": has_verdict,
            "verdict_race_count": verdict_info.get("race_count"),
            "sigma_file": has_sigma,
            "horse_runs_rows": horse_runs,
            "rpdc_candidate_rows": rpdc_cands,
            "rpdc_any_attached": verdict_any_attached,
            "rpdc_attached_count": verdict_info.get("attached_count"),
            "rpdc_total_tags": verdict_info.get("total_rpdc_tags"),
            "rpdc_statuses": verdict_info.get("rpdc_statuses"),
        }
        rows.append(row)

    run_ts = datetime.now(timezone.utc).isoformat()

    summary = {
        "audit_run_at": run_ts,
        "supabase_available": supabase_available,
        "total_dates": len(all_dates),
        "horse_runs_total_rows": sum(horse_runs_by_date.values()),
        "horse_runs_distinct_dates": len(horse_runs_by_date),
        "rpdc_candidates_total_rows": sum(rpdc_candidates_by_date.values()),
        "rpdc_candidates_distinct_dates": len(rpdc_candidates_by_date),
        "classifications": dict(classification_counts),
        "backfill_eligibility": dict(backfill_counts),
        "date_range": {
            "first": all_dates[0] if all_dates else None,
            "last": all_dates[-1] if all_dates else None,
        },
    }

    output = {"summary": summary, "dates": rows}

    # Write JSON
    json_path = REPORTS_DIR / "rpdc_historical_coverage_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    log.info("JSON written → %s", json_path)

    # Write Markdown
    md_path = REPORTS_DIR / "rpdc_historical_coverage_latest.md"
    _write_markdown(md_path, summary, rows, supabase_available)
    log.info("MD  written → %s", md_path)

    _print_summary(summary, rows)
    return output


def _write_markdown(path: Path, summary: dict, rows: list[dict], supabase_available: bool) -> None:
    lines = [
        "# RPDC Historical Coverage Audit",
        "",
        f"**Generated:** {summary['audit_run_at']}  ",
        f"**Supabase:** {'CONNECTED' if supabase_available else 'SKIPPED (no credentials)'}  ",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total dates audited | {summary['total_dates']} |",
        f"| Date range | {summary['date_range']['first']} → {summary['date_range']['last']} |",
        f"| racing_horse_runs total rows | {summary['horse_runs_total_rows']:,} |",
        f"| racing_horse_runs distinct dates | {summary['horse_runs_distinct_dates']} |",
        f"| runner_release_candidates total rows | {summary['rpdc_candidates_total_rows']:,} |",
        f"| runner_release_candidates distinct dates | {summary['rpdc_candidates_distinct_dates']} |",
        "",
        "## Classification Breakdown",
        "",
        "| Classification | Count |",
        "|---|---|",
    ]
    for cls, count in sorted(summary["classifications"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{cls}` | {count} |")

    lines += [
        "",
        "## Backfill Eligibility",
        "",
        "| Eligibility | Count |",
        "|---|---|",
    ]
    for k, count in sorted(summary["backfill_eligibility"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {count} |")

    lines += [
        "",
        "---",
        "",
        "## Per-Date Detail",
        "",
        "| Date | Classification | Results | Results Races | Verdicts | V Races | Sigma | Horse Runs | RPDC Candidates | RPDC Attached |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['date']} "
            f"| `{row['classification']}` "
            f"| {'Y' if row['results_file'] else '-'} "
            f"| {row['results_race_count'] or '-'} "
            f"| {'Y' if row['verdict_file'] else '-'} "
            f"| {row['verdict_race_count'] or '-'} "
            f"| {'Y' if row['sigma_file'] else '-'} "
            f"| {row['horse_runs_rows'] if row['horse_runs_rows'] is not None else '?'} "
            f"| {row['rpdc_candidate_rows'] if row['rpdc_candidate_rows'] is not None else '?'} "
            f"| {row['rpdc_attached_count'] if row['rpdc_attached_count'] is not None else '-'} "
            f"|"
        )

    lines += [
        "",
        "---",
        "",
        "## Classification Definitions",
        "",
        "| Classification | Meaning | Fix Path |",
        "|---|---|---|",
        "| `RPDC_COMPLETE` | Verdicts have attached RPDC tags, chain worked | None needed |",
        "| `HORSE_RUNS_PRESENT_TAGS_MISSING` | Horse history in DB but RPDC tags not built | Run `build_rpdc_daily.py` for this date |",
        "| `RESULTS_PRESENT_HORSE_RUNS_MISSING` | Local results exist but not in Supabase | Run `ingest_results_to_horse_runs.py` (operator approval required) |",
        "| `SCORED_NO_RESULTS` | Verdicts exist but no results file — cannot backfill horse history | Download results if available |",
        "| `RESULTS_ONLY_NOT_SCORED` | Results available but never scored — partial backfill only | Run local RPDC backfill script |",
        "| `NOT_ELIGIBLE` | No results, no verdicts — no recoverable data | None |",
        "",
        "## Backfill Eligibility Definitions",
        "",
        "| Eligibility | Meaning |",
        "|---|---|",
        "| `LOCAL_BACKFILL_ELIGIBLE` | Results file present — run `backfill_rpdc_historical_local.py` (no Supabase) |",
        "| `SUPABASE_INGEST_ELIGIBLE` | Results present, horse_runs missing — run `ingest_results_to_horse_runs.py` (requires operator approval) |",
        "| `HORSE_RUNS_PRESENT` | Horse history already in DB — only RPDC tags need rebuilding |",
        "| `NOT_ELIGIBLE` | No results file — cannot reconstruct horse history |",
        "",
        "```",
        f"AUDIT_STATUS:          COMPLETE",
        f"SUPABASE_CONNECTED:    {supabase_available}",
        f"HORSE_RUNS_TOTAL:      {summary['horse_runs_total_rows']:,}",
        f"RPDC_CANDIDATES_TOTAL: {summary['rpdc_candidates_total_rows']:,}",
        f"TOTAL_DATES:           {summary['total_dates']}",
        "```",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


def _print_summary(summary: dict, rows: list[dict]) -> None:
    print()
    print("=" * 60)
    print("RPDC HISTORICAL COVERAGE AUDIT — SUMMARY")
    print("=" * 60)
    print(f"  Dates audited:          {summary['total_dates']}")
    print(f"  Date range:             {summary['date_range']['first']} → {summary['date_range']['last']}")
    print(f"  Supabase connected:     {summary['supabase_available']}")
    if summary["supabase_available"]:
        print(f"  racing_horse_runs:      {summary['horse_runs_total_rows']:,} rows / {summary['horse_runs_distinct_dates']} dates")
        print(f"  rpdc_candidates:        {summary['rpdc_candidates_total_rows']:,} rows / {summary['rpdc_candidates_distinct_dates']} dates")
    print()
    print("Classifications:")
    for cls, count in sorted(summary["classifications"].items(), key=lambda x: -x[1]):
        print(f"  {cls:<45} {count:>4}")
    print()
    print("Backfill Eligibility:")
    for k, count in sorted(summary["backfill_eligibility"].items(), key=lambda x: -x[1]):
        print(f"  {k:<45} {count:>4}")
    print()

    # Highlight dates that are RPDC_COMPLETE
    complete = [r["date"] for r in rows if r["classification"] == "RPDC_COMPLETE"]
    if complete:
        print(f"RPDC_COMPLETE dates ({len(complete)}):")
        for d in complete:
            print(f"  {d}")
    else:
        print("RPDC_COMPLETE dates: NONE — RPDC has never been fully operational across historical range")
    print()
    print(f"Output → data/reports/rpdc_historical_coverage_latest.json")
    print(f"Output → data/reports/rpdc_historical_coverage_latest.md")
    print("=" * 60)


if __name__ == "__main__":
    run_audit()
