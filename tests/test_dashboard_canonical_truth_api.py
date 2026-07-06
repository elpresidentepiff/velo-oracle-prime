"""
Regression tests for the MODEL-TRUTH-04 dashboard canonical-truth endpoints
in scripts/ops/new_build_dashboard_server.py.

These endpoints must read ONLY public.canonical_model_scorecards and
public.canonical_learning_events (Supabase, read-only). They must never
write to Supabase, and must never fall back to dirty-repo local artifacts
such as two_lane_readiness_*.json or passport_strength_score.

Hard regression case: 2026-07-05, race_id 922118, Little Lady Rock.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ops" / "new_build_dashboard_server.py"

spec = importlib.util.spec_from_file_location("new_build_dashboard_server", MODULE_PATH)
dashboard = importlib.util.module_from_spec(spec)
sys.modules["new_build_dashboard_server"] = dashboard
spec.loader.exec_module(dashboard)

try:
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("fastapi not installed", allow_module_level=True)

client = TestClient(dashboard.app)

DATE = "2026-07-05"
RACE_ID = "922118"


def _has_supabase_data():
    rows = dashboard.fetch_canonical_scorecard(DATE)
    return len(rows) > 0


pytestmark = pytest.mark.skipif(not _has_supabase_data(), reason="SUPABASE_URL/KEY not configured or no rows for date")


def test_source_reads_only_canonical_tables():
    assert "def fetch_canonical_scorecard" in MODULE_PATH.read_text(encoding="utf-8")
    assert "canonical_model_scorecards" in MODULE_PATH.read_text(encoding="utf-8")
    assert "canonical_learning_events" in MODULE_PATH.read_text(encoding="utf-8")


def test_no_supabase_write_function_exists_in_dashboard():
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "_sb_upsert" not in src, "dashboard server must never write to Supabase"
    assert "method=\"POST\"" not in src


def test_canonical_scorecard_endpoint():
    r = client.get(f"/api/canonical-scorecard?date={DATE}")
    assert r.status_code == 200
    data = r.json()
    assert data["source_table"] == "public.canonical_model_scorecards"
    assert data["no_supabase_write"] is True
    assert data["count"] == 374


def test_canonical_learning_events_endpoint():
    r = client.get(f"/api/canonical-learning-events?date={DATE}")
    assert r.status_code == 200
    data = r.json()
    assert data["source_table"] == "public.canonical_learning_events"
    assert data["no_supabase_write"] is True
    assert data["count"] == 374


def test_race_truth_requires_race_id():
    r = client.get(f"/api/canonical-race-truth?date={DATE}")
    assert r.status_code == 400


def _llr_rows():
    r = client.get(f"/api/canonical-race-truth?date={DATE}&race_id={RACE_ID}")
    assert r.status_code == 200
    data = r.json()
    llr = [row for row in data["scorecard_rows"] if row.get("horse") == "Little Lady Rock"]
    assert llr, "Little Lady Rock rows must be present for race 922118"
    return data, llr


def test_little_lady_rock_lane_a_and_b_rank_1_no_edge():
    _, llr = _llr_rows()
    lane_a = [r for r in llr if r["model_name"] == "NEW_BUILD_LANE_A_MODEL"][0]
    lane_b = [r for r in llr if r["model_name"] == "NEW_BUILD_LANE_B_MODEL"][0]
    assert lane_a["rank"] == 1
    assert lane_b["rank"] == 1
    assert lane_a["policy_decision"] == "NO_EDGE"
    assert lane_b["policy_decision"] == "NO_EDGE"
    assert lane_a["stake_authorised"] is False
    assert lane_b["stake_authorised"] is False
    assert float(lane_a["sp_dec"]) == 41.0


def test_little_lady_rock_cannot_appear_as_near_miss():
    data, llr = _llr_rows()
    for row in llr:
        notes = str(row.get("notes") or "").lower()
        assert "near-miss" not in notes and "near miss" not in notes
    for event in data["learning_events"]:
        if event.get("horse") == "Little Lady Rock":
            lesson = str(event.get("lesson") or "").lower()
            assert "near-miss" not in lesson and "near miss" not in lesson


def test_passport_proxy_not_shown_as_model_hit():
    data, llr = _llr_rows()
    proxy_rows = [r for r in llr if r["model_name"] == "PASSPORT_STRENGTH_SCORE_PROXY"]
    assert proxy_rows
    for event in data["learning_events"]:
        if event.get("model_name") == "PASSPORT_STRENGTH_SCORE_PROXY":
            assert event["event_type"] == "PROXY_CONTEXT_ONLY"


def test_policy_block_visible_in_learning_events():
    data, _ = _llr_rows()
    lane_events = [
        e for e in data["learning_events"]
        if e.get("horse") == "Little Lady Rock" and e.get("model_name") in ("NEW_BUILD_LANE_A_MODEL", "NEW_BUILD_LANE_B_MODEL")
    ]
    assert lane_events
    for e in lane_events:
        assert e["event_type"] == "VALUE_DISCOVERY_POLICY_BLOCKED"
        assert e["promotion_eligible"] is False


def test_main_velo_way_maker_loss_present_in_race_truth():
    r = client.get(f"/api/canonical-race-truth?date={DATE}&race_id={RACE_ID}")
    data = r.json()
    main_velo_rows = [row for row in data["scorecard_rows"] if row["model_name"] == "MAIN_VELO_PRIME"]
    assert main_velo_rows
    way_maker = [row for row in main_velo_rows if row.get("horse") == "Way Maker"]
    assert way_maker
    assert way_maker[0].get("win") in (False, "False")
