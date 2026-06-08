from __future__ import annotations

import json
from pathlib import Path

from scripts.ops import build_rpdc_daily
from scripts.ops.validate_rp_injection import validate_injection
from src import preflight


def _write_injection(path: Path, race_count: int = 3) -> Path:
    races = []
    for index in range(race_count):
        races.append({
            "race_id": str(100 + index),
            "course": f"Course {index}",
            "off_time": f"1{index}:00",
            "runners": [
                {"horse_id": f"{index}01", "horse": "Alpha"},
                {"horse_id": f"{index}02", "horse": "Beta"},
            ],
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"races": races}), encoding="utf-8")
    return path


def test_resolve_injection_prefers_explicit_path(monkeypatch, tmp_path):
    monkeypatch.setattr(build_rpdc_daily, "ROOT", tmp_path)
    explicit = _write_injection(tmp_path / "chosen" / "racecard_injection.json")
    _write_injection(
        tmp_path
        / "data"
        / "racing_post_account_parsed"
        / "live-full-racepages-2026-06-08-refresh"
        / "racecard_injection.json"
    )

    assert build_rpdc_daily._resolve_injection_path("2026-06-08", explicit) == explicit.resolve()


def test_resolve_injection_uses_newest_file_not_path_sort(monkeypatch, tmp_path):
    monkeypatch.setattr(build_rpdc_daily, "ROOT", tmp_path)
    base = _write_injection(
        tmp_path
        / "data"
        / "racing_post_account_parsed"
        / "live-full-racepages-2026-06-08"
        / "racecard_injection.json"
    )
    refresh = _write_injection(
        tmp_path
        / "data"
        / "racing_post_account_parsed"
        / "live-full-racepages-2026-06-08-refresh"
        / "racecard_injection.json"
    )
    base.touch()
    refresh.touch()
    refresh_mtime = base.stat().st_mtime_ns + 10_000_000
    refresh.touch()
    import os
    os.utime(refresh, ns=(refresh_mtime, refresh_mtime))

    assert build_rpdc_daily._resolve_injection_path("2026-06-08") == refresh


def test_preflight_blocks_duplicate_race_identity(tmp_path):
    path = _write_injection(tmp_path / "racecard_injection.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["races"][1]["race_id"] = payload["races"][0]["race_id"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    failures, _ = validate_injection(path)

    assert any("RACE_ID_DUPLICATE" in failure for failure in failures)


def test_system_preflight_does_not_require_or_check_racing_api(monkeypatch):
    monkeypatch.delenv("RACING_API_USERNAME", raising=False)
    monkeypatch.delenv("RACING_API_PASSWORD", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
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

    result = preflight.preflight()

    assert result.status == "PASS"
    assert "racing_api" not in {check.name for check in result.checks}
