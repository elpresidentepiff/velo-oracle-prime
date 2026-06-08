"""
Tests for the read-only doctrine moat scorecard dashboard endpoint.

Verifies:
  - /api/doctrine-scorecard loads and returns JSON correctly
  - Missing scorecard file returns 404 with status NOT_FOUND
  - Endpoint does not trigger scoring, model calls, or live writes
  - GET request does not mutate any files
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ops.new_build_dashboard_server import app

client = TestClient(app, raise_server_exceptions=True)

SAMPLE_SCORECARD = {
    "gate_progress": {
        "target": 100,
        "flagged_races": 0,
        "cash_run_races": 0,
        "setup_run_races": 0,
        "decoy_support_races": 0,
        "completion_pct": 0.0,
        "remaining": 100,
    },
    "tier_a": {"sample_size": 163, "wins": 91, "strike_rate_pct": 55.8},
    "decoy_interception": {"sample_size": 0, "interceptions": 0, "interception_rate_pct": 0.0, "threshold": 0.5},
    "doctrine_vs_market": {
        "sample_size": 1059,
        "doctrine_win_rate_pct": 50.0,
        "market_win_rate_pct": None,
        "edge_pct_points": None,
    },
    "confidence_reliability": {"bands": [], "mean_abs_error_pct_points": None},
    "meta": {"input_path": "data/test.csv", "rows": 1059, "generated_at": "2026-05-29T12:00:00Z"},
}


def test_doctrine_scorecard_loads_json(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "doctrine_scorecard_latest.json").write_text(
        json.dumps(SAMPLE_SCORECARD), encoding="utf-8"
    )

    import scripts.ops.new_build_dashboard_server as srv
    monkeypatch.setattr(srv, "ROOT", tmp_path)

    res = client.get("/api/doctrine-scorecard")
    assert res.status_code == 200
    body = res.json()
    assert body["tier_a"]["strike_rate_pct"] == 55.8
    assert body["gate_progress"]["flagged_races"] == 0
    assert body["gate_progress"]["target"] == 100
    assert body["doctrine_vs_market"]["doctrine_win_rate_pct"] == 50.0


def test_doctrine_scorecard_missing_file(tmp_path, monkeypatch):
    import scripts.ops.new_build_dashboard_server as srv
    monkeypatch.setattr(srv, "ROOT", tmp_path)

    res = client.get("/api/doctrine-scorecard")
    assert res.status_code == 404
    body = res.json()
    assert body["status"] == "NOT_FOUND"
    assert "doctrine_scorecard_latest.json" in body["message"]


def test_doctrine_scorecard_no_scoring_triggered():
    """Endpoint source must not reference scoring, model, Telegram, or staking code."""
    import scripts.ops.new_build_dashboard_server as srv
    src = inspect.getsource(srv.doctrine_scorecard)
    forbidden_terms = [
        "model_manager",
        "run_prime",
        "telegram",
        "stake",
        "place_order",
        "place_bet",
        "supabase",
        "velo_prime_ensemble",
    ]
    for term in forbidden_terms:
        assert term not in src.lower(), (
            f"Forbidden scoring-related term '{term}' found in /api/doctrine-scorecard endpoint"
        )


def test_doctrine_scorecard_no_state_mutation(tmp_path, monkeypatch):
    """GET must not write, create, or delete any files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sc = data_dir / "doctrine_scorecard_latest.json"
    sc.write_text(json.dumps(SAMPLE_SCORECARD), encoding="utf-8")

    import scripts.ops.new_build_dashboard_server as srv
    monkeypatch.setattr(srv, "ROOT", tmp_path)

    before = {p: p.stat().st_mtime for p in tmp_path.rglob("*") if p.is_file()}
    client.get("/api/doctrine-scorecard")
    after = {p: p.stat().st_mtime for p in tmp_path.rglob("*") if p.is_file()}

    assert before == after, "GET /api/doctrine-scorecard must not mutate any files"


def test_doctrine_scorecard_endpoint_is_readonly():
    """Endpoint must not be registered on a mutating HTTP method."""
    routes = {r.path: list(r.methods) for r in app.routes if hasattr(r, "methods")}
    assert "/api/doctrine-scorecard" in routes
    assert routes["/api/doctrine-scorecard"] == ["GET"]
