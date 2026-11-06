"""Regression perimeter for the governed RP-only UK/IRE live path."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.ops import run_cloud_raceday
from src import preflight
from src.velo.racecard_loader import load_racecards
from src.velo.source_truth_enforcer import SourceTruthBlockError, enforce_source_truth


ROOT = Path(__file__).resolve().parents[1]


def test_score_daily_wrapper_targets_governed_rp_executor() -> None:
    source = (ROOT / "app" / "pipelines" / "score_daily_runner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert "rp_cloud_raceday.py" in string_literals
    assert "run_cloud_raceday.py" not in string_literals


def test_retired_cloud_runner_is_a_fail_closed_tombstone() -> None:
    source = (ROOT / "scripts" / "ops" / "run_cloud_raceday.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert run_cloud_raceday.main() == 2
    assert "src.velo.racecard_loader" not in imports
    assert "fetch_api_racecards" not in source
    assert "api.theracingapi.com" not in source


@pytest.mark.parametrize(
    "alias",
    ["api", "api_clean", "racing_api", "racing_api_standard", "racing api", "theracingapi"],
)
def test_retired_api_aliases_fail_closed(alias: str) -> None:
    with pytest.raises(SourceTruthBlockError):
        enforce_source_truth(alias)


def test_loader_has_no_live_racing_api_fetch_symbol() -> None:
    import src.velo.racecard_loader as loader

    assert not hasattr(loader, "fetch_api_racecards")


def test_prime_cli_does_not_offer_retired_api_source() -> None:
    source = (ROOT / "scripts" / "ops" / "run_prime_today.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    source_choice_lists = [
        [element.value for element in node.elts if isinstance(element, ast.Constant)]
        for node in ast.walk(tree)
        if isinstance(node, ast.List)
    ]

    assert ["auto", "cache", "rp"] in source_choice_lists
    assert ["auto", "cache", "rp", "api"] not in source_choice_lists


def test_loader_missing_rp_evidence_never_uses_legacy_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("RACING_API_USERNAME", "legacy-user")
    monkeypatch.setenv("RACING_API_PASSWORD", "legacy-password")

    with pytest.raises(RuntimeError, match="supplier fallback is forbidden"):
        load_racecards(
            date_tag="2026_11_06",
            date_str="2026-11-06",
            data_root=tmp_path,
            source="auto",
        )


def test_system_preflight_has_explicit_rp_and_factual_formfav_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "_check_env_vars", lambda **_: preflight.PreflightCheck(
        "env_vars", preflight.Severity.CRITICAL, True, "test"
    ))
    monkeypatch.setattr(preflight, "_check_canonical_constants", lambda: preflight.PreflightCheck(
        "canonical_constants", preflight.Severity.CRITICAL, True, "test"
    ))
    monkeypatch.setattr(preflight, "_check_supabase", lambda: preflight.PreflightCheck(
        "supabase", preflight.Severity.CRITICAL, True, "test"
    ))
    monkeypatch.setattr(preflight, "_check_sqpe_model", lambda: preflight.PreflightCheck(
        "sqpe_model", preflight.Severity.CRITICAL, True, "test"
    ))
    monkeypatch.setattr(preflight, "_check_specialist_models", lambda: preflight.PreflightCheck(
        "specialist_models", preflight.Severity.DEGRADED, True, "test"
    ))
    monkeypatch.setattr(preflight, "_check_supabase_schema", lambda: preflight.PreflightCheck(
        "supabase_schema", preflight.Severity.DEGRADED, True, "test"
    ))
    monkeypatch.setattr(preflight, "_check_rp_capture_readiness", lambda: preflight.PreflightCheck(
        "racing_post_capture", preflight.Severity.CRITICAL, True, "test"
    ))
    monkeypatch.setattr(preflight, "_check_formfav_factual_readiness", lambda: preflight.PreflightCheck(
        "formfav_factual", preflight.Severity.CRITICAL, True, "predictions non-gating"
    ))

    result = preflight.preflight(require_telegram=False)
    checks = {check.name for check in result.checks}

    assert result.status == "PASS"
    assert "racing_post_capture" in checks
    assert "formfav_factual" in checks
    assert "racing_api" not in checks
