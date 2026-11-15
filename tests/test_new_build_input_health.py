"""A failed Supabase hydrate or low passport coverage must not read as a healthy New Build day.

2026-11-12, Railway: "Passport cover: WARN 59/224 runners have a passport (26.3%)", then New Build
and Champion Intent were scored, persisted and settled like any other day.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.ops import new_build_input_health as health

ROOT = Path(__file__).resolve().parents[1]


def _coverage(found: int, total: int, threshold: float = 0.70, split: bool = True) -> dict:
    cov = found / total if total else 0.0
    return {
        "total": total,
        "found": found,
        "coverage": cov,
        "gbire_total": total,
        "gbire_found": found,
        "gbire_coverage": cov,
        "threshold": threshold,
        "region_split_available": split,
    }


def test_the_12_november_day_is_degraded() -> None:
    verdict = health.assess("2026-11-12", hydrate="OK", coverage=_coverage(59, 224))
    assert verdict["status"] == health.DEGRADED
    assert verdict["passport_coverage"] == 0.2634
    assert "PASSPORT_COVERAGE_BELOW_THRESHOLD: 26.3% of GB/IRE runners" in verdict["reasons"][0]


def test_a_failed_hydrate_degrades_the_day_even_when_coverage_looks_fine() -> None:
    """The git copy can clear the threshold on a small card; it is still not the Supabase bank."""
    verdict = health.assess("2026-11-16", hydrate="FAILED", coverage=_coverage(180, 200))
    assert verdict["status"] == health.DEGRADED
    assert verdict["reasons"] == ["SUPABASE_HYDRATE_FAILED: the passport bank is the git copy, not Supabase"]


def test_a_hydrate_that_never_ran_is_not_a_pass() -> None:
    assert health.assess("2026-11-16", hydrate="NOT_RUN", coverage=_coverage(180, 200))["status"] == health.DEGRADED
    assert health.hydrate_outcome([]) == "NOT_RUN"
    assert health.hydrate_outcome([{"step": health.HYDRATE_STEP, "ok": False}]) == "FAILED"
    assert health.hydrate_outcome([{"step": health.HYDRATE_STEP, "ok": True}]) == "OK"


def test_a_hydrated_day_above_the_threshold_is_healthy() -> None:
    verdict = health.assess("2026-11-16", hydrate="OK", coverage=_coverage(180, 200))
    assert (verdict["status"], verdict["reasons"]) == (health.HEALTHY, [])


def test_a_missing_feed_is_degraded() -> None:
    verdict = health.assess("2026-11-16", hydrate="OK", coverage={"error": "FEED_MISSING", "threshold": 0.7})
    assert verdict["status"] == health.DEGRADED and verdict["reasons"] == ["PASSPORT_FEED_FEED_MISSING"]


def test_only_the_passport_dependent_lanes_are_stamped() -> None:
    degraded = health.assess("2026-11-12", hydrate="FAILED", coverage=_coverage(59, 224))
    for model in health.DEPENDENT_MODELS:
        assert health.row_note(model, degraded).startswith("INPUT_DEGRADED: SUPABASE_HYDRATE_FAILED")
    for model in ("MAIN_VELO_PRIME", "SQPE_NO_RPR_SHADOW", "OLD_VELO_WIN_ROLE", "MDS_HEAVY_SHADOW_V1"):
        assert health.row_note(model, degraded) == ""
        assert health.row_note(model, None) == ""


def test_no_verdict_is_reported_as_unverified_not_as_healthy() -> None:
    assert health.row_note("NEW_BUILD_LANE_A_MODEL", None).startswith("INPUT_HEALTH_UNVERIFIED")
    healthy = health.assess("2026-11-16", hydrate="OK", coverage=_coverage(180, 200))
    assert health.row_note("NEW_BUILD_LANE_A_MODEL", healthy) == ""


def test_the_verdict_round_trips_through_its_file(tmp_path: Path) -> None:
    verdict = health.assess("2026-11-12", hydrate="OK", coverage=_coverage(59, 224))
    path = health.write(verdict, tmp_path)
    assert path.name == "new_build_input_health_2026_11_12.json"
    assert health.load("2026-11-12", tmp_path)["status"] == health.DEGRADED
    assert health.load("2026-11-13", tmp_path) is None
    path.write_text("not json", encoding="utf-8")
    assert health.load("2026-11-12", tmp_path) is None


def test_the_scorecard_build_stamps_the_dependent_rows(tmp_path: Path, monkeypatch) -> None:
    from scripts.ops import build_canonical_model_scorecard as scorecard

    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "_load_results", lambda date: {})
    monkeypatch.setattr(scorecard, "_sb_get", lambda path: [])
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *a, **k: [])
    monkeypatch.setattr(scorecard, "_ensure_env", lambda: None)
    degraded = health.assess("2026-11-12", hydrate="FAILED", coverage=_coverage(59, 224))
    monkeypatch.setattr(scorecard._nb_health, "load", lambda date: degraded)

    _rows, audit = scorecard.build_scorecard("2026-11-12")

    assert audit["new_build_input_health"] == health.DEGRADED


def test_the_verdict_is_wired_into_the_run_and_persisted_for_the_evening_rebuild() -> None:
    runner = (ROOT / "scripts/ops/run_full_raceday.py").read_text(encoding="utf-8")
    gate = runner.index("_cov_ok, _cov_stats = check_passport_coverage(date)")
    assess = runner.index("_nb_health.assess(date, hydrate=_nb_health.hydrate_outcome(results), coverage=_cov_stats)")
    scoring = runner.index('"Step 9: Live scoring (run_prime_today.py)"')
    assert gate < assess < scoring
    assert f'"{health.HYDRATE_STEP}"' in runner  # the step name the verdict looks for is the one the runner uses

    from scripts.ops import persist_daily_artifacts as daily

    assert daily.REPORTS["new_build_input_health"][0] == "data/reports/new_build_input_health_{tag}.json"
    builder = (ROOT / "scripts/ops/build_canonical_model_scorecard.py").read_text(encoding="utf-8")
    assert '_nb_health.row_note(base.get("model_name"), input_health)' in builder
