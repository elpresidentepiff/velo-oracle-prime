from __future__ import annotations

import json

import pytest

from scripts.ops import run_results_sigma as sigma


def test_open_sigma_run_uses_null_status_for_active_row(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_request(method: str, path: str, data: dict | None = None) -> tuple[int, bytes]:
        captured.update(method=method, path=path, data=data)
        return 201, b""

    monkeypatch.setattr(sigma, "SB_URL", "https://example.supabase.co")
    monkeypatch.setattr(sigma, "SB_KEY", "service-key")
    monkeypatch.setattr(sigma, "_pipeline_request", fake_request)

    run_id = sigma._open_sigma_run("2026-11-03")

    assert run_id
    assert captured["method"] == "POST"
    assert captured["path"] == "/pipeline_runs"
    assert captured["data"]["run_state"] == "running"  # type: ignore[index]
    assert captured["data"]["status"] is None  # type: ignore[index]


def test_open_sigma_run_fails_loudly_when_persistence_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"code": "23514", "message": "terminal-only contract rejected active status"}

    monkeypatch.setattr(sigma, "SB_URL", "https://example.supabase.co")
    monkeypatch.setattr(sigma, "SB_KEY", "service-key")
    monkeypatch.setattr(
        sigma,
        "_pipeline_request",
        lambda *_args, **_kwargs: (400, json.dumps(body).encode()),
    )

    with pytest.raises(RuntimeError, match="HTTP 400.*23514"):
        sigma._open_sigma_run("2026-11-03")


def _capture_patches(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    patches: list[dict] = []

    def fake_request(method: str, path: str, data: dict | None = None) -> tuple[int, bytes]:
        patches.append({"method": method, "path": path, "data": data})
        return 201, b""

    monkeypatch.setattr(sigma, "SB_URL", "https://example.supabase.co")
    monkeypatch.setattr(sigma, "SB_KEY", "service-key")
    monkeypatch.setattr(sigma, "_pipeline_request", fake_request)
    monkeypatch.setattr(sigma, "_SIGMA_RUN_CLOSED", False)
    return patches


def test_a_pass_records_how_many_races_and_results_it_settled(monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-11-04 to 2026-11-14: every nightly row read PASS / 0 races / 0 results, settled or not."""
    patches = _capture_patches(monkeypatch)

    sigma._close_sigma_run("run-1", status="PASS", races_processed=36, results_processed=35)

    assert patches[0]["method"] == "PATCH"
    assert patches[0]["path"] == "/pipeline_runs?id=eq.run-1"
    data = patches[0]["data"]
    assert (data["status"], data["run_state"]) == ("PASS", "completed")
    assert (data["races_processed"], data["results_processed"]) == (36, 35)


def test_a_failure_without_counts_leaves_the_count_columns_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    patches = _capture_patches(monkeypatch)

    sigma._close_sigma_run("run-2", status="FAIL", error="SIGMA_RESULTS_INCOMPLETE_BLOCKED")

    data = patches[0]["data"]
    assert data["error_message"] == "SIGMA_RESULTS_INCOMPLETE_BLOCKED"
    assert "races_processed" not in data and "results_processed" not in data


def test_the_open_row_carries_the_commit_that_settled_the_night(monkeypatch: pytest.MonkeyPatch) -> None:
    patches = _capture_patches(monkeypatch)
    monkeypatch.delenv("PIPELINE_RUN_ID", raising=False)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "094b9c44086b9e31324371fda836ccc6b17c8c22")

    sigma._open_sigma_run("2026-11-14")

    assert patches[0]["data"]["commit_sha"] == "094b9c44086b9e31324371fda836ccc6b17c8c22"


def test_an_unknown_commit_is_recorded_as_null_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.ops.runtime_truth_support as truth

    monkeypatch.setattr(truth, "get_commit_sha", lambda: "unknown")
    assert sigma._sigma_commit_sha() is None


def test_the_final_pass_passes_its_counts() -> None:
    from pathlib import Path

    src = (Path(__file__).parents[1] / "scripts" / "ops" / "run_results_sigma.py").read_text(encoding="utf-8")
    assert '_close_sigma_run(run_id, status="PASS", races_processed=total_matched, results_processed=sigma_ok)' in src
    assert '_close_sigma_run(run_id, status="PASS")' not in src
