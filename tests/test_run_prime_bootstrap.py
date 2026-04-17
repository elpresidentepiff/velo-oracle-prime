from __future__ import annotations

import json

from scripts import run_prime_today


def test_bootstrap_runtime_disables_notifications_when_requested(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setenv("RACING_API_USERNAME", "user")
    monkeypatch.setenv("RACING_API_PASSWORD", "pass")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")

    run_prime_today._bootstrap_runtime(notify=False)

    assert run_prime_today.TOKEN == ""
    assert run_prime_today.CHAT_ID == ""
    assert run_prime_today._SB_URL == "https://example.supabase.co"
    assert run_prime_today._SB_KEY == "service-role"


def test_bootstrap_runtime_keeps_telegram_when_enabled(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setenv("RACING_API_USERNAME", "user")
    monkeypatch.setenv("RACING_API_PASSWORD", "pass")

    run_prime_today._bootstrap_runtime(notify=True)

    assert run_prime_today.TOKEN == "token"
    assert run_prime_today.CHAT_ID == "chat"
    assert run_prime_today.RACING_HEADERS["Authorization"].startswith("Basic ")


def test_attach_rpdc_marks_ambiguous_latest_and_uses_newest_row(monkeypatch):
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                [
                    {
                        "generated_at": "2026-04-15T12:00:00+00:00",
                        "rpdc_release_score": 4.2,
                        "rpdc_cash_window_flag": True,
                        "rpdc_tag_count": 2,
                        "rpdc_tags": ["CASH_WINDOW", "MARK_READY"],
                    },
                    {
                        "generated_at": "2026-04-15T11:00:00+00:00",
                        "rpdc_release_score": 1.1,
                        "rpdc_cash_window_flag": False,
                        "rpdc_tag_count": 1,
                        "rpdc_tags": ["OLDER"],
                    },
                ]
            ).encode("utf-8")

    monkeypatch.setattr(run_prime_today, "_SB_URL", "https://example.supabase.co")
    monkeypatch.setattr(run_prime_today, "_SB_HDRS", {"Authorization": "Bearer token"})
    monkeypatch.setattr(run_prime_today.urllib.request, "urlopen", lambda *args, **kwargs: _Response())

    top = {"horse_id": "horse-1"}
    run_prime_today._attach_rpdc(top, "race-1")

    assert top["rpdc_lookup_status"] == "ambiguous_latest"
    assert top["rpdc_cash_window_flag"] is True
    assert top["rpdc_release_score"] == 4.2
    assert top["rpdc_primary_tag"] == "CASH_WINDOW"
