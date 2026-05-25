#!/usr/bin/env python3
"""
new_build_horse_passports.py
Build Horse Passport V1 for all horses with scraped RP form history.
Shadow only — velo_scoring_allowed = False.
"""
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


def load_all_runs() -> dict[str, list[dict]]:
    """Load all form history JSON files, group runs by horse_rp_uid."""
    by_horse: dict[str, list[dict]] = defaultdict(list)
    files = sorted(RACE_SHAPE_DIR.glob("form_history_2026-*.json"))
    for f in files:
        if "latest" in f.name:
            continue
        data = json.loads(f.read_text())
        for run in data.get("runs", []):
            uid = run.get("horse_rp_uid")
            key = str(uid) if uid else run.get("horse_name", "unknown")
            by_horse[key].append(run)
    return by_horse


def run():
    print("Loading form history runs ...")
    by_horse = load_all_runs()
    print(f"  {len(by_horse)} distinct horses found")

    builder = HorsePassportBuilder()
    passports = []
    failures = []

    for key, runs in by_horse.items():
        try:
            passport = builder.build(runs)
            passports.append(passport)
        except Exception as e:
            failures.append({"key": key, "error": str(e)})

    print(f"  Built: {len(passports)} passports, {len(failures)} failures")

    # Write JSONL
    out_path = OUT_DIR / "horse_passports_v1.jsonl"
    with out_path.open("w") as f:
        for p in passports:
            f.write(json.dumps(asdict(p)) + "\n")
    print(f"  Written: {out_path}")

    # Report
    cash_candidates = sorted([p for p in passports if p.cash_run_candidate],
                              key=lambda p: p.well_fancied_rate, reverse=True)
    setup_candidates = sorted([p for p in passports if p.setup_run_candidate],
                               key=lambda p: -(p.avg_beaten_margin or 0))
    anomaly_candidates = sorted([p for p in passports if p.well_fancied_failure_rate >= 0.5 and p.career_runs >= 3],
                                 key=lambda p: p.well_fancied_failure_rate, reverse=True)

    # Bow Echo
    bow_echo = next((p for p in passports if "bow echo" in p.horse_name.lower()), None)

    # Coverage stats
    def cov(attr):
        vals = [getattr(p, attr) for p in passports]
        non_none = sum(1 for v in vals if v is not None and v is not False)
        return round(non_none / len(passports) * 100, 1) if passports else 0

    lines = [
        "# Horse Passport V1",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"## Summary",
        f"- **Total passports**: {len(passports)}",
        f"- **Build failures**: {len(failures)}",
        f"- **Cash-run candidates**: {len(cash_candidates)}",
        f"- **Setup-run candidates**: {len(setup_candidates)}",
        f"- **Jockey anomaly candidates** (well_fancied_failure_rate ≥ 50%): {len(anomaly_candidates)}",
        "",
        "## Field Coverage",
        "| Field | Coverage |",
        "|---|---|",
        f"| days_since_last_run | {cov('days_since_last_run')}% |",
        f"| avg_days_between_runs | {cov('avg_days_between_runs')}% |",
        f"| sp_trajectory | {cov('sp_trajectory')}% |",
        f"| avg_sp_last5 | {cov('avg_sp_last5')}% |",
        f"| going_preference | {cov('going_preference')}% |",
        f"| course_affinity | {cov('course_affinity')}% |",
        f"| margin_trend | {cov('margin_trend')}% |",
        f"| or_trajectory | {cov('or_trajectory')}% |",
        f"| current_or | {cov('current_or')}% |",
        "",
        "## Top 10 Cash-Run Candidates",
        "| Horse | SP | WF Rate | WF Fail Rate | Last Run DaysAgo |",
        "|---|---|---|---|---|",
    ]
    for p in cash_candidates[:10]:
        lines.append(f"| {p.horse_name} | {p.avg_sp_last5} | {p.well_fancied_rate:.0%} | {p.well_fancied_failure_rate:.0%} | {p.days_since_last_run}d |")

    lines += [
        "",
        "## Top 10 Setup-Run Candidates",
        "| Horse | Avg Beaten Margin | OR Change | Days Since Run |",
        "|---|---|---|---|",
    ]
    for p in setup_candidates[:10]:
        lines.append(f"| {p.horse_name} | {p.avg_beaten_margin} | {p.or_change_last3} | {p.days_since_last_run}d |")

    lines += [
        "",
        "## Top 10 Jockey Anomaly Horses (well-fancied failures)",
        "| Horse | Well-Fancied Failure Rate | Well-Fancied Runs | Career Runs |",
        "|---|---|---|---|",
    ]
    for p in anomaly_candidates[:10]:
        lines.append(f"| {p.horse_name} | {p.well_fancied_failure_rate:.0%} | {p.well_fancied_rate:.0%} of career | {p.career_runs} |")

    lines += ["", "## Bow Echo Passport"]
    if bow_echo:
        for k, v in asdict(bow_echo).items():
            if k not in ("trust_policy", "velo_scoring_allowed"):
                lines.append(f"- **{k}**: {v}")
    else:
        lines.append("*Not found in current form history captures — run parser for May 24.*")

    (RPT_DIR / "horse_passport_v1_latest.md").write_text("\n".join(lines))

    report_json = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "total_passports": len(passports),
        "failures": len(failures),
        "cash_run_candidates": len(cash_candidates),
        "setup_run_candidates": len(setup_candidates),
        "jockey_anomaly_candidates": len(anomaly_candidates),
        "bow_echo": asdict(bow_echo) if bow_echo else None,
    }
    (RPT_DIR / "horse_passport_v1_latest.json").write_text(json.dumps(report_json, indent=2))
    print("  Reports written.")


if __name__ == "__main__":
    run()
