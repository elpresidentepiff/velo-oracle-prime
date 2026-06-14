#!/usr/bin/env python3
"""
Build Horse Passport V1 from scraped RP form history and profile metadata.

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
PARSED_DIR = ROOT / "data" / "racing_post_account_parsed"
OUT_DIR = ROOT / "data" / "new_build" / "passports"
RPT_DIR = ROOT / "data" / "new_build" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RPT_DIR.mkdir(parents=True, exist_ok=True)


def _passport_key(row: dict) -> str:
    uid = row.get("horse_rp_uid")
    if uid not in (None, ""):
        return str(uid)
    return f"name:{row.get('horse_name', '').strip().lower()}"


def load_all_horses() -> dict[str, list[dict]]:
    """Load all form history AND horse profiles, grouped by horse_rp_uid."""
    # 1. Start with runs from form history
    by_horse: dict[str, list[dict]] = defaultdict(list)
    seen_run_keys: set[tuple[str, str, str, str, str, str]] = set()
    
    files = sorted(RACE_SHAPE_DIR.glob("form_history_*.json"))
    for f in files:
        if "latest" in f.name: continue
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
            if run_key in seen_run_keys: continue
            seen_run_keys.add(run_key)
            by_horse[key].append(run)

    # 2. Add horses from horse_profiles.json that might have 0 runs (debutants)
    profile_files = list(PARSED_DIR.glob("**/horse_profiles.json"))
    
    for f in profile_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profiles = data if isinstance(data, list) else data.get("horse_profiles", [])
            if not isinstance(profiles, list): continue
            
            for p in profiles:
                uid = p.get("horse_uid")
                name = p.get("horse_name")
                key = str(uid) if uid else name
                if not key: continue
                
                if key not in by_horse:
                    # Create a dummy run entry to ensure the horse gets a passport
                    by_horse[key] = [{"horse_name": name, "horse_rp_uid": uid}]
        except Exception:
            continue

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
        "# Horse Passport V2",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        f"- **Total passports**: {len(combined_rows)}",
        f"- **Existing before run**: {already_present}",
        f"- **Newly appended**: {newly_appended}",
        f"- **Source horses found (history + profiles)**: {source_horses_found}",
        f"- **Build failures**: {len(failures)}",
        f"- **Existing duplicate rows skipped**: {existing_duplicate_count}",
        f"- **Cash-run candidates**: {len(cash_candidates)}",
        f"- **Setup-run candidates**: {len(setup_candidates)}",
        f"- **Jockey anomaly candidates** (well-fancied failure rate >= 50%): {len(anomaly_candidates)}",
        "",
        "## Field Coverage",
        "| Field | Coverage |",
        "|---|---|",
        f"| last_run_date | {_coverage(combined_rows, 'last_run_date')}% |",
        f"| win_rate_last3 | {_coverage(combined_rows, 'win_rate_last3')}% |",
        f"| beaten_margin_slope | {_coverage(combined_rows, 'beaten_margin_slope')}% |",
        f"| sp_trajectory | {_coverage(combined_rows, 'sp_trajectory')}% |",
        f"| avg_sp_last5 | {_coverage(combined_rows, 'avg_sp_last5')}% |",
        f"| going_preference | {_coverage(combined_rows, 'going_preference')}% |",
        f"| course_affinity | {_coverage(combined_rows, 'course_affinity')}% |",
        f"| current_or | {_coverage(combined_rows, 'current_or')}% |",
        "",
        "## Top 10 Cash-Run Candidates",
        "| Horse | SP | WF Rate | WF Fail Rate | Last Run |",
        "|---|---|---|---|---|",
    ]
    for row in cash_candidates[:10]:
        lines.append(
            f"| {row.get('horse_name')} | {row.get('avg_sp_last5')} | "
            f"{(row.get('well_fancied_rate') or 0):.0%} | "
            f"{(row.get('well_fancied_failure_rate') or 0):.0%} | "
            f"{row.get('last_run_date')} |"
        )

    lines += ["", "## Bow Echo Passport"]
    if bow_echo:
        for key, value in bow_echo.items():
            if key not in ("trust_policy", "velo_scoring_allowed"):
                lines.append(f"- **{key}**: {value}")
    else:
        lines.append("*Not found in current captures.*")

    (RPT_DIR / "horse_passport_v2_latest.md").write_text("\n".join(lines), encoding="utf-8")

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
        "existing_duplicate_count": existing_duplicate_count,
    }
    (RPT_DIR / "horse_passport_v2_latest.json").write_text(json.dumps(report_json, indent=2), encoding="utf-8")


def run(*, rebuild: bool = False) -> dict:
    print("Loading form history and profiles ...")
    by_horse = load_all_horses()
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
    parser = argparse.ArgumentParser(description="Build Horse Passport V2.")
    parser.add_argument("--rebuild", action="store_true", help="Overwrite passport JSONL.")
    args = parser.parse_args()
    run(rebuild=args.rebuild)
