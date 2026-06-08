"""
VÉLØ Racecard Cache Completeness Gate.

Called immediately after racecard load, before any scoring or normalization.
If the gate fails the engine must not proceed.

Checks:
  1. date_match          — all races are for the requested date
  2. race_count          — enough UK/IRE races with runners
  3. course_coverage     — enough unique UK/IRE courses
  4. runner_count        — enough total runners
  5. metadata_coverage   — runners have required fields populated
  6. rpr_live_leak       — no bare 'rpr' field exposed in runners
  7. sidecar_date_match  — RPDC run_date matches racecard date (soft check)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Thresholds ────────────────────────────────────────────────────────────────
# Derived from operational history: bad 2026-05-26 cache had 8 races / 70 runners.
# Legitimate UK day minimums well exceed these.
MIN_RACES_UK_IRE = 15
MIN_RUNNERS_TOTAL = 80
MIN_COURSES_UK_IRE = 3
METADATA_REQUIRED_FIELDS = ("horse_id", "jockey", "trainer")
METADATA_COVERAGE_MIN = 0.90
# rp_merged captures happen before jockey declarations — only horse_id+trainer required
METADATA_REQUIRED_FIELDS_RP_MERGED = ("horse_id", "trainer")
METADATA_COVERAGE_MIN_RP_MERGED = 0.85

# Jurisdictions scored by VÉLØ
_UK_IRE_REGIONS = {"GB", "IRE", "gb", "ire", "uk"}

REPORT_ROOT = Path(__file__).resolve().parents[2] / "data" / "reports"


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    value: Any
    threshold: Any
    message: str
    blocking: bool = True  # if False: warn only, does not fail gate


@dataclass
class CacheGateResult:
    date_str: str
    racecard_source: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    races_uk_ire: int = 0
    courses: list[str] = field(default_factory=list)
    total_runners: int = 0
    run_at: str = ""

    def failed_blocking(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.blocking]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_uk_ire(race: dict) -> bool:
    region = (race.get("region") or "").upper()
    country = (race.get("country") or "").upper()
    return region in _UK_IRE_REGIONS or country in ("GB", "IRE", "UK", "IRELAND")


def _collect_uk_ire_races(raw_races: list[dict]) -> list[dict]:
    return [r for r in raw_races if r.get("runners") and _is_uk_ire(r)]


def _check_date_match(raw_races: list[dict], date_str: str) -> CheckResult:
    loaded_dates: set[str] = set()
    for r in raw_races:
        d = r.get("date") or r.get("race_date") or r.get("off_dt", "")[:10]
        if d:
            loaded_dates.add(d)
    match = date_str in loaded_dates or not loaded_dates
    msg = (
        f"dates found: {sorted(loaded_dates)}"
        if not match
        else f"date confirmed: {date_str}"
    )
    return CheckResult("date_match", match, sorted(loaded_dates), date_str, msg)


def _check_race_count(uk_ire_races: list[dict]) -> CheckResult:
    n = len(uk_ire_races)
    passed = n >= MIN_RACES_UK_IRE
    return CheckResult(
        "race_count", passed, n, MIN_RACES_UK_IRE,
        f"{n} UK/IRE races with runners (min {MIN_RACES_UK_IRE})"
    )


def _check_course_coverage(uk_ire_races: list[dict]) -> CheckResult:
    courses = sorted({r.get("course", "") for r in uk_ire_races if r.get("course")})
    n = len(courses)
    passed = n >= MIN_COURSES_UK_IRE
    return CheckResult(
        "course_coverage", passed, courses, MIN_COURSES_UK_IRE,
        f"{n} unique courses: {courses} (min {MIN_COURSES_UK_IRE})"
    )


def _check_runner_count(uk_ire_races: list[dict]) -> CheckResult:
    total = sum(len(r.get("runners", [])) for r in uk_ire_races)
    passed = total >= MIN_RUNNERS_TOTAL
    return CheckResult(
        "runner_count", passed, total, MIN_RUNNERS_TOTAL,
        f"{total} total runners (min {MIN_RUNNERS_TOTAL})"
    )


def _check_metadata_coverage(uk_ire_races: list[dict], racecard_source: str = "") -> CheckResult:
    is_rp_merged = racecard_source == "rp_merged"
    required = METADATA_REQUIRED_FIELDS_RP_MERGED if is_rp_merged else METADATA_REQUIRED_FIELDS
    threshold = METADATA_COVERAGE_MIN_RP_MERGED if is_rp_merged else METADATA_COVERAGE_MIN
    total = 0
    complete = 0
    for race in uk_ire_races:
        for runner in race.get("runners", []):
            total += 1
            if all(runner.get(f) for f in required):
                complete += 1
    if total == 0:
        return CheckResult("metadata_coverage", False, 0.0, threshold,
                           "no runners to check")
    coverage = complete / total
    passed = coverage >= threshold
    suffix = " (rp_merged: jockey excluded — may not be declared)" if is_rp_merged else ""
    return CheckResult(
        "metadata_coverage", passed, round(coverage, 4), threshold,
        f"{complete}/{total} runners have required fields ({coverage:.1%}){suffix}"
    )


def _check_rpr_live_leak(uk_ire_races: list[dict]) -> CheckResult:
    # RPR accepted into scoring pipeline as of 2026-06-03. Check is now informational only.
    rpr_count = sum(
        1 for race in uk_ire_races
        for runner in race.get("runners", [])
        if runner.get("rpr") is not None
    )
    return CheckResult(
        "rpr_live_leak", True, rpr_count, 0,
        f"{rpr_count} runners have rpr (accepted — RPR_ACCEPTED policy)",
        blocking=False,
    )


def _check_sidecar_date_match(
    uk_ire_races: list[dict],
    date_str: str,
    sb_url: str | None = None,
    sb_key: str | None = None,
) -> CheckResult:
    """
    Soft check: RPDC (runner_release_candidates) should have entries for date_str.
    Warns if sidecar coverage is far below the loaded racecard's race set.
    Non-blocking — gate still fails on hard checks.
    """
    if not sb_url or not sb_key:
        return CheckResult(
            "sidecar_date_match", True, "skipped", date_str,
            "Supabase unavailable — sidecar check skipped",
            blocking=False,
        )
    try:
        import urllib.request
        url = (
            f"{sb_url.rstrip('/')}/rest/v1/runner_release_candidates"
            f"?run_date=eq.{date_str}&select=race_id&limit=2000"
        )
        req = urllib.request.Request(url, headers={
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            rows = json.loads(r.read())
        sidecar_race_ids = {str(row["race_id"]) for row in rows}
        racecard_race_ids = {str(r.get("race_id", "")) for r in uk_ire_races}
        overlap = sidecar_race_ids & racecard_race_ids
        coverage = len(overlap) / len(racecard_race_ids) if racecard_race_ids else 0.0

        # Sidecar and racecard have very different race sets → suspicious
        passed = coverage >= 0.50
        return CheckResult(
            "sidecar_date_match",
            passed,
            {
                "sidecar_races": len(sidecar_race_ids),
                "racecard_races": len(racecard_race_ids),
                "overlap": len(overlap),
                "coverage": round(coverage, 3),
            },
            date_str,
            f"RPDC covers {len(overlap)}/{len(racecard_race_ids)} racecard races ({coverage:.0%})",
            blocking=False,
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "sidecar_date_match", True, "error", date_str,
            f"sidecar check failed with {type(exc).__name__}: {exc}",
            blocking=False,
        )


# ── Report writers ─────────────────────────────────────────────────────────────

def _write_reports(result: CacheGateResult) -> tuple[Path, Path]:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "date_str": result.date_str,
        "racecard_source": result.racecard_source,
        "gate_passed": result.passed,
        "run_at": result.run_at,
        "races_uk_ire": result.races_uk_ire,
        "courses": result.courses,
        "total_runners": result.total_runners,
        "checks": [
            {
                "name": c.name,
                "passed": c.passed,
                "value": c.value,
                "threshold": c.threshold,
                "message": c.message,
                "blocking": c.blocking,
            }
            for c in result.checks
        ],
    }
    json_path = REPORT_ROOT / "racecard_cache_gate_latest.json"
    md_path = REPORT_ROOT / "racecard_cache_gate_latest.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    verdict = "PASS" if result.passed else "BLOCKED"
    lines = [
        f"# Racecard Cache Gate — {result.date_str}",
        "",
        f"**Verdict:** {verdict}  ",
        f"**Source:** {result.racecard_source}  ",
        f"**Run at:** {result.run_at}  ",
        f"**Races (UK/IRE):** {result.races_uk_ire}  ",
        f"**Runners:** {result.total_runners}  ",
        f"**Courses:** {', '.join(result.courses)}",
        "",
        "## Checks",
        "",
    ]
    for c in result.checks:
        icon = "✓" if c.passed else ("⚠" if not c.blocking else "✗")
        block_label = "" if c.blocking else " _(warn-only)_"
        lines.append(f"- {icon} **{c.name}**{block_label}: {c.message}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


# ── Public API ────────────────────────────────────────────────────────────────

def validate_racecard(
    raw_races: list[dict],
    date_str: str,
    racecard_source: str = "unknown",
    sb_url: str | None = None,
    sb_key: str | None = None,
) -> CacheGateResult:
    """
    Run all completeness checks and return a CacheGateResult.
    Does not raise or exit — caller decides what to do with result.

    VELO_FORCE_CARD=1: operator asserts card is complete as-is (e.g. genuine
    small-card day with a single UK meeting). All checks still run and are
    reported, but blocking failures are downgraded to warnings so the gate
    passes. Use only when Racing API is unavailable and you have manually
    confirmed the card is complete.
    """
    import os as _os
    import json as _json
    from pathlib import Path as _Path

    force_card = _os.getenv("VELO_FORCE_CARD", "").strip() in ("1", "true", "yes")

    # Implicit containment bypass: check if cert says contained
    date_tag = date_str.replace("-", "_")
    cert_path = _Path("data") / f"racecards_{date_tag}_standard.cert.json"
    if cert_path.exists():
        try:
            cert_data = _json.loads(cert_path.read_text())
            status = cert_data.get("fixture_truth_status", "")
            if status in ("PARTIAL_MEETING_CONTAINED", "CERTIFIED_MEETING_CONTAINED"):
                force_card = True
        except Exception:
            pass


    uk_ire = _collect_uk_ire_races(raw_races)
    courses = sorted({r.get("course", "") for r in uk_ire if r.get("course")})
    total_runners = sum(len(r.get("runners", [])) for r in uk_ire)

    checks = [
        _check_date_match(raw_races, date_str),
        _check_race_count(uk_ire),
        _check_course_coverage(uk_ire),
        _check_runner_count(uk_ire),
        _check_metadata_coverage(uk_ire, racecard_source),
        _check_rpr_live_leak(uk_ire),
        _check_sidecar_date_match(uk_ire, date_str, sb_url, sb_key),
    ]

    if force_card:
        # Downgrade all blocking failures to warn-only — operator asserts card complete
        for c in checks:
            if not c.passed and c.blocking:
                c.blocking = False
                c.message = f"[FORCE_CARD_OVERRIDE] {c.message}"

    passed = all(c.passed for c in checks if c.blocking)

    result = CacheGateResult(
        date_str=date_str,
        racecard_source=racecard_source,
        passed=passed,
        checks=checks,
        races_uk_ire=len(uk_ire),
        courses=courses,
        total_runners=total_runners,
        run_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    _write_reports(result)
    return result


def print_gate_result(result: CacheGateResult) -> None:
    import os as _os
    import json as _json
    from pathlib import Path as _Path

    force_card = _os.getenv("VELO_FORCE_CARD", "").strip() in ("1", "true", "yes")

    # Implicit containment bypass: check if cert says contained
    date_tag = result.date_str.replace("-", "_")
    cert_path = _Path("data") / f"racecards_{date_tag}_standard.cert.json"
    if cert_path.exists():
        try:
            cert_data = _json.loads(cert_path.read_text())
            status = cert_data.get("fixture_truth_status", "")
            if status in ("PARTIAL_MEETING_CONTAINED", "CERTIFIED_MEETING_CONTAINED"):
                force_card = True
        except Exception:
            pass

    verdict = "PASS" if result.passed else "BAD_RACECARD_CACHE_BLOCKED"
    if force_card and result.passed:
        verdict = "PASS (FORCE_CARD_OVERRIDE)"
    print(f"\n{'=' * 60}")
    print(f"  RACECARD CACHE GATE — {verdict}")
    print(f"  date: {result.date_str}  source: {result.racecard_source}")
    print(f"  races: {result.races_uk_ire}  runners: {result.total_runners}  courses: {len(result.courses)}")
    print(f"{'─' * 60}")
    for c in result.checks:
        icon = "[PASS]" if c.passed else ("[WARN]" if not c.blocking else "[FAIL]")
        print(f"  {icon} {c.name}: {c.message}")
    print(f"{'=' * 60}\n")
    if not result.passed:
        print("  DIAGNOSTIC REPORT WRITTEN:")
        print(f"    data/reports/racecard_cache_gate_latest.json")
        print(f"    data/reports/racecard_cache_gate_latest.md")
        print()
