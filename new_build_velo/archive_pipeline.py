"""Archive-only New Build VELO pipeline.

This is the clean front door for the Racing Post archive/database lane. It
reuses proven scripts without importing or wiring Live VELO scoring, Shadow
learning, Telegram, staking, or Playbook G runtime paths.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "new_build"

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
RPR_POLICY = "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO"

FORBIDDEN_COMMAND_TOKENS = (
    "run_prime_today",
    "velo_prime_service",
    "daily-eod",
    "learn-shadow",
    "bulk-shadow-consume",
    "sentient_state.json",
    "sentient_state_shadow_full_train_v1",
    "send_telegram",
    "telegram",
    "playbook",
    "staking",
)


@dataclass(frozen=True)
class ArchiveCounts:
    archive_date: str
    races: int
    runners: int
    horse_profiles: int
    horse_dossiers: int
    race_dossiers: int
    has_racecard: bool


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: list[str]
    writes_archive_only: bool = True
    requires_network: bool = False
    enabled: bool = True


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_range(start: str, end: str) -> list[str]:
    start_day = parse_date(start)
    end_day = parse_date(end)
    if end_day < start_day:
        raise ValueError("--to-date must be on or after --from-date")
    days: list[str] = []
    cursor = start_day
    while cursor <= end_day:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def list_payload_count(payload: Any, *keys: str) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        for key in ("rows", "items", "records", "dossiers", "race_dossiers", "horse_profiles"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    return 0


def counts_for_date(archive_date: str, parsed_root: Path = PARSED_ROOT) -> ArchiveCounts:
    day = parsed_root / archive_date
    racecard = load_json(day / "racecard_injection.json", {})
    profiles = load_json(day / "horse_profiles.json", {})
    horse_dossiers = load_json(day / "horse_dossiers.json", {})
    race_dossiers = load_json(day / "race_dossiers.json", {})

    races = 0
    runners = 0
    if isinstance(racecard, dict):
        race_rows = racecard.get("races") or []
        races = len(race_rows)
        runners = sum(len(race.get("runners") or []) for race in race_rows if isinstance(race, dict))

    return ArchiveCounts(
        archive_date=archive_date,
        races=races,
        runners=runners,
        horse_profiles=list_payload_count(profiles, "horse_profiles"),
        horse_dossiers=list_payload_count(horse_dossiers, "dossiers"),
        race_dossiers=list_payload_count(race_dossiers, "dossiers", "race_dossiers"),
        has_racecard=bool(races or runners),
    )


def discover_counts(from_date: str, to_date: str, parsed_root: Path = PARSED_ROOT) -> list[ArchiveCounts]:
    return [counts_for_date(day, parsed_root=parsed_root) for day in date_range(from_date, to_date)]


def py(script: str, *args: str) -> list[str]:
    return [sys.executable, script, *args]


def build_plan(
    from_date: str,
    to_date: str,
    *,
    execute_local: bool = False,
    supabase_dry_run: bool = False,
    supabase_execute: bool = False,
) -> list[PipelineStep]:
    execute_flag = ["--execute"] if execute_local else []
    steps: list[PipelineStep] = []
    for day in date_range(from_date, to_date):
        steps.append(
            PipelineStep(
                name=f"horse-dossiers-{day}",
                command=py("scripts/ops/build_rp_horse_dossiers.py", "--date", day, *execute_flag),
            )
        )
        steps.append(
            PipelineStep(
                name=f"race-dossiers-{day}",
                command=py("scripts/ops/build_rp_race_dossiers.py", "--date", day, *execute_flag),
            )
        )

    bridge_execute_flag = ["--execute"] if execute_local else []
    steps.extend(
        [
            PipelineStep(
                name="identity-bridge",
                command=py(
                    "scripts/ops/build_horse_identity_bridge.py",
                    "--start-date",
                    from_date,
                    "--end-date",
                    to_date,
                    *bridge_execute_flag,
                ),
            ),
            PipelineStep(
                name="source-value-matrix",
                command=py("scripts/ops/build_source_value_matrix.py", "--all-built", *bridge_execute_flag),
            ),
            PipelineStep(
                name="outcome-bridge",
                command=py("scripts/ops/build_rp_archive_outcome_bridge.py", *bridge_execute_flag),
            ),
            PipelineStep(
                name="rpr-boundary-audit",
                command=py("scripts/audit_rpr_scoring_boundary.py"),
            ),
            PipelineStep(
                name="archive-advantage-analysis",
                command=py(
                    "scripts/analysis/analyze_rp_archive_advantage.py",
                    "--from-date",
                    from_date,
                    "--to-date",
                    to_date,
                ),
            ),
        ]
    )

    if supabase_dry_run or supabase_execute:
        mode = "--execute" if supabase_execute else "--dry-run"
        steps.append(
            PipelineStep(
                name="supabase-archive-upload",
                command=py(
                    "scripts/ops/upload_rp_archive_to_supabase.py",
                    "--from-date",
                    from_date,
                    "--to-date",
                    to_date,
                    mode,
                ),
                requires_network=True,
            )
        )
        if supabase_execute:
            steps.append(
                PipelineStep(
                    name="supabase-archive-verify",
                    command=py(
                        "scripts/ops/verify_rp_supabase_archive_load.py",
                        "--from-date",
                        from_date,
                        "--to-date",
                        to_date,
                    ),
                    requires_network=True,
                )
            )

    validate_plan(steps)
    return steps


def validate_plan(steps: Iterable[PipelineStep]) -> None:
    for step in steps:
        joined = " ".join(step.command).lower()
        for token in FORBIDDEN_COMMAND_TOKENS:
            if token in joined:
                raise ValueError(f"Forbidden Live/Shadow token in New Build plan: {token} ({step.name})")


def run_steps(steps: list[PipelineStep], *, execute: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in steps:
        row: dict[str, Any] = {
            "step": step.name,
            "command": step.command,
            "enabled": step.enabled,
            "writes_archive_only": step.writes_archive_only,
            "requires_network": step.requires_network,
            "status": "PLANNED",
        }
        if execute and step.enabled:
            proc = subprocess.run(step.command, cwd=ROOT, text=True, capture_output=True)
            row.update(
                {
                    "status": "PASS" if proc.returncode == 0 else "FAIL",
                    "returncode": proc.returncode,
                    "stdout_tail": proc.stdout[-4000:],
                    "stderr_tail": proc.stderr[-4000:],
                }
            )
            if proc.returncode != 0:
                results.append(row)
                break
        results.append(row)
    return results


def build_report(
    from_date: str,
    to_date: str,
    *,
    counts: list[ArchiveCounts],
    steps: list[PipelineStep],
    step_results: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "classification": "NEW_BUILD_ARCHIVE_PIPELINE_READY",
        "mode": mode,
        "from_date": from_date,
        "to_date": to_date,
        "trust_policy": TRUST_POLICY,
        "rpr_policy": RPR_POLICY,
        "velo_scoring_allowed": False,
        "live_velo_touched": False,
        "shadow_velo_touched": False,
        "forbidden_live_shadow_tokens": list(FORBIDDEN_COMMAND_TOKENS),
        "counts": [asdict(row) for row in counts],
        "totals": {
            "races": sum(row.races for row in counts),
            "runners": sum(row.runners for row in counts),
            "horse_profiles": sum(row.horse_profiles for row in counts),
            "horse_dossiers": sum(row.horse_dossiers for row in counts),
            "race_dossiers": sum(row.race_dossiers for row in counts),
        },
        "steps": [asdict(step) for step in steps],
        "step_results": step_results,
    }


def write_report(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_ROOT / "archive_pipeline_latest.json"
    md_path = REPORT_ROOT / "archive_pipeline_latest.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# New Build VELO Archive Pipeline",
        "",
        f"- Classification: `{report['classification']}`",
        f"- Mode: `{report['mode']}`",
        f"- Date range: `{report['from_date']}` to `{report['to_date']}`",
        f"- Trust policy: `{report['trust_policy']}`",
        f"- RPR policy: `{report['rpr_policy']}`",
        "- Live VELO touched: `false`",
        "- Shadow VELO touched: `false`",
        "",
        "## Totals",
        "",
    ]
    for key, value in report["totals"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Planned Steps", ""])
    for step in report["steps"]:
        command = " ".join(step["command"])
        lines.append(f"- `{step['name']}`: `{command}`")
    lines.extend(["", "## Results", ""])
    for result in report["step_results"]:
        lines.append(f"- `{result['step']}`: `{result['status']}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean New Build VELO archive pipeline front door.")
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--execute-local", action="store_true", help="Run local archive builders with --execute.")
    parser.add_argument("--supabase-dry-run", action="store_true", help="Include archive-table Supabase dry-run upload.")
    parser.add_argument("--supabase-execute", action="store_true", help="Execute archive-table Supabase upload and verify.")
    parser.add_argument("--run", action="store_true", help="Actually run the planned commands. Default only plans.")
    parser.add_argument("--no-report", action="store_true", help="Do not write data/new_build report artifacts.")
    args = parser.parse_args(argv)

    if args.supabase_execute and not args.run:
        parser.error("--supabase-execute requires --run")

    counts = discover_counts(args.from_date, args.to_date)
    steps = build_plan(
        args.from_date,
        args.to_date,
        execute_local=args.execute_local,
        supabase_dry_run=args.supabase_dry_run,
        supabase_execute=args.supabase_execute,
    )
    mode = "RUN" if args.run else "PLAN_ONLY"
    step_results = run_steps(steps, execute=args.run)
    report = build_report(args.from_date, args.to_date, counts=counts, steps=steps, step_results=step_results, mode=mode)
    if not args.no_report:
        json_path, md_path = write_report(report)
        report["report_paths"] = {"json": str(json_path), "md": str(md_path)}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if any(row.get("status") == "FAIL" for row in step_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

