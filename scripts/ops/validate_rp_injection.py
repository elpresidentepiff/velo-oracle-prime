"""Fail-closed validation for the exact Racing Post injection used that day."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def validate_injection(path: Path) -> tuple[list[str], dict]:
    failures: list[str] = []
    if not path.exists():
        return [f"INJECTION_MISSING: {path}"], {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"INJECTION_PARSE_ERROR: {exc}"], {}

    races = payload.get("races") or []
    if not races:
        return ["INJECTION_EMPTY: no races found"], {}

    race_ids = [str(race.get("race_id") or "").strip() for race in races]
    missing_ids = sum(not race_id for race_id in race_ids)
    duplicate_ids = len(race_ids) - len(set(race_ids))
    null_off_times = [race.get("course", "?") for race in races if not race.get("off_time")]
    courses = sorted({race.get("course") for race in races if race.get("course")})
    active_runners = sum(
        1
        for race in races
        for runner in race.get("runners") or []
        if not runner.get("non_runner") and runner.get("horse_id")
    )

    if missing_ids:
        failures.append(f"RACE_ID_MISSING: {missing_ids} race(s)")
    if duplicate_ids:
        failures.append(f"RACE_ID_DUPLICATE: {duplicate_ids} duplicate race(s)")
    if null_off_times:
        failures.append(f"OFF_TIME_NULL: {len(null_off_times)} race(s): {null_off_times[:5]}")
    if len(courses) < 3:
        failures.append(f"COURSE_COUNT_LOW: {len(courses)} course(s): {courses}")
    if active_runners < len(races) * 2:
        failures.append(
            f"RUNNER_COUNT_LOW: {active_runners} active runners across {len(races)} races"
        )

    summary = {
        "injection_path": str(path),
        "races": len(races),
        "unique_race_ids": len(set(race_ids)),
        "courses": len(courses),
        "active_runners": active_runners,
    }
    return failures, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--injection-path", required=True)
    args = parser.parse_args()

    path = Path(args.injection_path)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()

    failures, summary = validate_injection(path)
    if failures:
        print("RP_INJECTION_PREFLIGHT_BLOCKED")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("RP_INJECTION_PREFLIGHT_PASS")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
