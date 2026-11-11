from __future__ import annotations

import pytest

from src import preflight


def test_no_notify_env_check_does_not_require_telegram(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = preflight._check_env_vars(require_telegram=False)

    assert result.passed is True
    assert "telegram disabled" in result.detail


def test_notify_env_check_stays_strict(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = preflight._check_env_vars(require_telegram=True)

    assert result.passed is False
    assert "TELEGRAM_BOT_TOKEN" in result.detail
    assert "TELEGRAM_CHAT_ID" in result.detail


def test_no_notify_preflight_does_not_call_telegram_on_failure(monkeypatch):
    failed = preflight.PreflightResult()
    failed.add(
        preflight.PreflightCheck(
            "supabase", preflight.Severity.CRITICAL, False, "unreachable"
        )
    )
    monkeypatch.setattr(preflight, "preflight", lambda **_: failed)
    calls: list[str] = []

    with pytest.raises(SystemExit):
        preflight.preflight_or_die(
            tg_fn=calls.append,
            require_telegram=False,
        )

    assert calls == []


def _passing(name: str):
    return lambda *a, **k: preflight.PreflightCheck(name, preflight.Severity.CRITICAL, True, "ok")


def _stub_checks(monkeypatch, formfav):
    for fn, name in (
        ("_check_env_vars", "env_vars"),
        ("_check_canonical_constants", "canonical_constants"),
        ("_check_supabase", "supabase"),
        ("_check_rp_capture_readiness", "racing_post_capture"),
        ("_check_sqpe_model", "sqpe_model"),
        ("_check_specialist_models", "specialist_models"),
        ("_check_supabase_schema", "supabase_schema"),
    ):
        monkeypatch.setattr(preflight, fn, _passing(name))
    monkeypatch.setattr(preflight, "_check_formfav_factual_readiness", formfav)


def test_settlement_does_not_require_fresh_formfav(monkeypatch):
    # 2026-11-10 21:05 UTC: newest FormFav form 12:46 -> CRIT -> no UK sigma. Settlement never reads FormFav.
    def stale():
        raise AssertionError("settlement must not run the FormFav freshness check")

    _stub_checks(monkeypatch, stale)
    result = preflight.preflight(require_telegram=False, settlement=True)
    assert result.status == "PASS"
    assert any(c.name == "formfav_factual" and "settlement" in c.detail for c in result.checks)


def test_scoring_still_blocks_on_stale_formfav(monkeypatch):
    stale = lambda: preflight.PreflightCheck("formfav_factual", preflight.Severity.CRITICAL, False, "older than 3:00:00")  # noqa: E731
    _stub_checks(monkeypatch, stale)
    assert preflight.preflight(require_telegram=False).status == "FAIL"


def test_only_the_results_run_asks_for_settlement_mode():
    from pathlib import Path

    root = Path(__file__).parents[1]
    sigma = (root / "scripts" / "ops" / "run_results_sigma.py").read_text(encoding="utf-8")
    scoring = (root / "scripts" / "ops" / "run_prime_today.py").read_text(encoding="utf-8")
    assert "settlement=True" in sigma
    assert "settlement=True" not in scoring
