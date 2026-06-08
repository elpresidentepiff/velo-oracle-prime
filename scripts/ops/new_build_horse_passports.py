#!/usr/bin/env python3
"""
Build Horse Passport V1 from scraped RP form history.

Default mode is append-only: existing passport rows are preserved and only
missing horse_rp_uid records are appended. Use --rebuild only for a deliberate
full overwrite.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.horse_passport import HorsePassportBuilder

RACE_SHAPE_DIR = ROOT / "data" / "race_shape"
OUT_DIR = ROOT / "data" / "new_build" / "passports"
RPT_DIR = ROOT / "data" / "new_build" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RPT_DIR.mkdir(parents=True, exist_ok=True)


def _passport_key(row: dict) -> str:
    uid = row.get("horse_rp_uid")
    if uid not in (None, ""):
        return str(uid)
    return f"name:{row.get('horse_name', '').strip().lower()}"


def load_all_runs() -> dict[str, list[dict]]:
    """Load all form history JSON files, grouped by horse_rp_uid."""
    by_horse: dict[str, list[dict]] = defaultdict(list)
    seen_run_keys: set[tuple[str, str, str, str, str, str]] = set()
    files = sorted(RACE_SHAPE_DIR.glob("form_history_*.json"))
    for f in files:
        if "latest" in f.name:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for run in data.get("runs", []):
            uid = run.get("horse_rp_uid")
            key = str(uid) if uid else run.get("horse_name", "unknown")
            run_key = (
                key,
                str(run.get("race_date") or ""),
                str(run.get("course_rp_uid") or run.get("course_key") or ""),
                str(run.get("result_url") or ""),
                str(run.get("position") or ""),
                str(run.get("sp_raw") or ""),
            )
            if run_key in seen_run_keys:
                continue
            seen_run_keys.add(run_key)
            by_horse[key].append(run)
    return by_horse


def load_existing_passports(path: Path) -> tuple[dict[str, dict], int]:
    if not path.exists():
        return {}, 0
    rows: dict[str, dict] = {}
    duplicate_count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = _passport_key(row)
        if key in rows:
            duplicate_count += 1
            continue
        rows[key] = row
    return rows, duplicate_count


def write_passport_rows(path: Path, rows: list[dict], *, append: bool) -> None:
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _coverage(rows: list[dict], attr: str) -> float:
    vals = [row.get(attr) for row in rows]
    non_none = sum(1 for value in vals if value is not None and value is not False)
    return round(non_none / len(rows) * 100, 1) if rows else 0.0


def write_reports(
    *,
    combined_rows: list[dict],
    failures: list[dict],
    already_present: int,
    newly_appended: int,
    source_horses_found: int,
    existing_duplicate_count: int,
    rebuild: bool,
) -> None:
    cash_candidates = sorted(
        [row for row in combined_rows if row.get("cash_run_candidate")],
        key=lambda row: row.get("well_fancied_rate") or 0,
        reverse=True,
    )
    setup_candidates = sorted(
        [row for row in combined_rows if row.get("setup_run_candidate")],
        key=lambda row: -(row.get("avg_beaten_margin") or 0),
    )
    anomaly_candidates = sorted(
        [
            row
            for row in combined_rows
            if (row.get("well_fancied_failure_rate") or 0) >= 0.5
            and (row.get("career_runs") or 0) >= 3
        ],
        key=lambda row: row.get("well_fancied_failure_rate") or 0,
        reverse=True,
    )
    bow_echo = next((row for row in combined_rows if "bow echo" in (row.get("horse_name") or "").lower()), None)

    lines = [
        "# Horse Passport V1",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        f"- **Total passports**: {len(combined_rows)}",
        f"- **Existing before run**: {already_present}",
        f"- **Newly appended**: {newly_appended}",
        f"- **Source horses found in form history**: {source_horses_found}",
        f"- **Build failures**: {len(failures)}",
        f"- **Existing duplicate rows skipped**: {existing_duplicate_count}",
        f"- **Cash-run candidates**: {len(cash_candidates)}",
        f"- **Setup-run candidates**: {len(setup_candidates)}",
        f"- **Jockey anomaly candidates** (well-fancied failure rate >= 50%): {len(anomaly_candidates)}",
        "",
        "## Field Coverage",
        "| Field | Coverage |",
        "|---|---|",
        f"| days_since_last_run | {_coverage(combined_rows, 'days_since_last_run')}% |",
        f"| avg_days_between_runs | {_coverage(combined_rows, 'avg_days_between_runs')}% |",
        f"| sp_trajectory | {_coverage(combined_rows, 'sp_trajectory')}% |",
        f"| avg_sp_last5 | {_coverage(combined_rows, 'avg_sp_last5')}% |",
        f"| going_preference | {_coverage(combined_rows, 'going_preference')}% |",
        f"| course_affinity | {_coverage(combined_rows, 'course_affinity')}% |",
        f"| margin_trend | {_coverage(combined_rows, 'margin_trend')}% |",
        f"| or_trajectory | {_coverage(combined_rows, 'or_trajectory')}% |",
        f"| current_or | {_coverage(combined_rows, 'current_or')}% |",
        "",
        "## Top 10 Cash-Run Candidates",
        "| Horse | SP | WF Rate | WF Fail Rate | Last Run DaysAgo |",
        "|---|---|---|---|---|",
    ]
    for row in cash_candidates[:10]:
        lines.append(
            f"| {row.get('horse_name')} | {row.get('avg_sp_last5')} | "
            f"{(row.get('well_fancied_rate') or 0):.0%} | "
            f"{(row.get('well_fancied_failure_rate') or 0):.0%} | "
            f"{row.get('days_since_last_run')}d |"
        )

    lines += [
        "",
        "## Top 10 Setup-Run Candidates",
        "| Horse | Avg Beaten Margin | OR Change | Days Since Run |",
        "|---|---|---|---|",
    ]
    for row in setup_candidates[:10]:
        lines.append(
            f"| {row.get('horse_name')} | {row.get('avg_beaten_margin')} | "
            f"{row.get('or_change_last3')} | {row.get('days_since_last_run')}d |"
        )

    lines += [
        "",
        "## Top 10 Jockey Anomaly Horses (well-fancied failures)",
        "| Horse | Well-Fancied Failure Rate | Well-Fancied Runs | Career Runs |",
        "|---|---|---|---|",
    ]
    for row in anomaly_candidates[:10]:
        lines.append(
            f"| {row.get('horse_name')} | {(row.get('well_fancied_failure_rate') or 0):.0%} | "
            f"{(row.get('well_fancied_rate') or 0):.0%} of career | {row.get('career_runs')} |"
        )

    lines += ["", "## Bow Echo Passport"]
    if bow_echo:
        for key, value in bow_echo.items():
            if key not in ("trust_policy", "velo_scoring_allowed"):
                lines.append(f"- **{key}**: {value}")
    else:
        lines.append("*Not found in current form history captures.*")

    (RPT_DIR / "horse_passport_v1_latest.md").write_text("\n".join(lines), encoding="utf-8")

    report_json = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "append_only": not rebuild,
        "total_passports": len(combined_rows),
        "existing_before_run": already_present,
        "newly_appended": newly_appended,
        "source_horses_found": source_horses_found,
        "failures": len(failures),
        "existing_duplicate_rows_skipped": existing_duplicate_count,
        "cash_run_candidates": len(cash_candidates),
        "setup_run_candidates": len(setup_candidates),
        "jockey_anomaly_candidates": len(anomaly_candidates),
        "bow_echo": bow_echo,
    }
    (RPT_DIR / "horse_passport_v1_latest.json").write_text(json.dumps(report_json, indent=2), encoding="utf-8")


def run(*, rebuild: bool = False) -> dict:
    print("Loading form history runs ...")
    by_horse = load_all_runs()
    print(f"  {len(by_horse)} distinct horses found")

    builder = HorsePassportBuilder()
    passports = []
    failures = []

    for key, runs in by_horse.items():
        try:
            passports.append(builder.build(runs))
        except Exception as exc:
            failures.append({"key": key, "error": str(exc)})

    print(f"  Built from source: {len(passports)} passports, {len(failures)} failures")

    out_path = OUT_DIR / "horse_passports_v1.jsonl"
    existing_by_key, existing_duplicate_count = load_existing_passports(out_path)
    built_rows = [asdict(passport) for passport in passports]
    built_by_key = {_passport_key(row): row for row in built_rows}

    if rebuild:
        combined_rows = list(built_by_key.values())
        write_passport_rows(out_path, combined_rows, append=False)
        already_present = 0
        newly_appended = len(combined_rows)
        print(f"  Rebuilt: {out_path}")
    else:
        new_rows = [row for key, row in built_by_key.items() if key not in existing_by_key]
        if new_rows:
            write_passport_rows(out_path, new_rows, append=True)
        combined_by_key = dict(existing_by_key)
        for row in new_rows:
            combined_by_key[_passport_key(row)] = row
        combined_rows = list(combined_by_key.values())
        already_present = len(existing_by_key)
        newly_appended = len(new_rows)
        print(f"  Existing passports: {already_present}")
        print(f"  Newly appended: {newly_appended}")
        print(f"  Written append-only: {out_path}")

    write_reports(
        combined_rows=combined_rows,
        failures=failures,
        already_present=already_present,
        newly_appended=newly_appended,
        source_horses_found=len(by_horse),
        existing_duplicate_count=existing_duplicate_count,
        rebuild=rebuild,
    )
    print("  Reports written.")
    return {
        "total_passports": len(combined_rows),
        "existing_before_run": already_present,
        "newly_appended": newly_appended,
        "failures": len(failures),
        "source_horses_found": len(by_horse),
        "append_only": not rebuild,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Horse Passport V1 append-only by default.")
    parser.add_argument("--rebuild", action="store_true", help="Overwrite passport JSONL from source form history.")
    args = parser.parse_args()
    run(rebuild=args.rebuild)
