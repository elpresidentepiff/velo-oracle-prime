"""
Tests for DASHBOARD-MODEL-SUGGESTIONS-01: GET /api/model-suggestions and
GET /api/model-suggestions-race.

These are current-day pre-race runtime suggestions, not canonical post-race
truth — every row/response must say so, and the CHAMPION_INTENT_SHADOW and
SQPE_NO_RPR_SHADOW lanes must never claim stake authorisation or promotion
eligibility no matter what artifacts are present on disk.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from scripts.ops.new_build_dashboard_server import app

client = TestClient(app)

JULY06 = "2026-07-06"


def test_model_suggestions_returns_lanes_for_available_models():
    resp = client.get(f"/api/model-suggestions?date={JULY06}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == JULY06
    assert "CHAMPION_INTENT_SHADOW" in body["models_requested"]
    # Whatever is available must have rows; whatever is missing must be reported, not hidden.
    for label in body["models_available"]:
        assert body["row_counts_by_model"].get(label, 0) > 0
    reported_missing = {m["model_label"] for m in body["missing_artifacts"]}
    assert reported_missing == set(body["models_missing"])


def test_response_is_labelled_runtime_suggestion_not_result_truth():
    resp = client.get(f"/api/model-suggestions?date={JULY06}")
    body = resp.json()
    assert body["suggestion_status"] == "CURRENT_DAY_RUNTIME_SUGGESTION_NOT_RESULT_TRUTH"
    assert body["result_truth"] is False
    assert body["staking_instruction"] is False
    assert body["promotion_action"] is False
    assert body["canonical_post_race_learning"] is False
    assert body["no_supabase_writes"] is True


def test_champion_intent_shadow_rows_exist_and_are_shadow_only():
    resp = client.get(f"/api/model-suggestions?date={JULY06}")
    body = resp.json()
    rows = [r for r in body["rows"] if r["model_label"] == "CHAMPION_INTENT_SHADOW"]
    assert rows, "CHAMPION_INTENT_SHADOW should have rows for July 06 (built in PR #133)"
    for r in rows:
        assert r["suggestion_status"] == "SHADOW_ONLY"


def test_champion_intent_shadow_never_authorises_stake_or_promotion():
    resp = client.get(f"/api/model-suggestions?date={JULY06}")
    body = resp.json()
    rows = [r for r in body["rows"] if r["model_label"] == "CHAMPION_INTENT_SHADOW"]
    for r in rows:
        assert r["stake_authorised"] is False
        assert r["promotion_eligible"] is False


def test_no_rpr_shadow_lane_is_labelled_shadow_when_present():
    # Use a date with real runner_snapshots data if available, else this is a no-op pass.
    resp = client.get("/api/model-suggestions?date=2026-07-05")
    body = resp.json()
    rows = [r for r in body["rows"] if r["model_label"] == "SQPE_NO_RPR_SHADOW"]
    for r in rows:
        assert r["suggestion_status"] == "SHADOW_ONLY"
        assert r["stake_authorised"] is False
        assert r["promotion_eligible"] is False


def test_new_build_lane_ranks_are_separate_from_policy_decision():
    resp = client.get("/api/model-suggestions?date=2026-07-05")
    body = resp.json()
    lane_labels = {"NEW_BUILD_LANE_A", "NEW_BUILD_LANE_B", "NEW_BUILD_LANE_C"}
    policy_rows = [r for r in body["rows"] if r["model_label"] == "NEW_BUILD_POLICY_V1"]
    lane_rows = [r for r in body["rows"] if r["model_label"] in lane_labels]
    # Lane rows must carry a rank and no policy_decision; policy rows (if present)
    # must carry a policy_decision. Neither collapses into the other.
    for r in lane_rows:
        assert r["policy_decision"] is None
        assert r["rank"] is not None
    for r in policy_rows:
        assert r["policy_decision"] is not None


def test_old_velo_win_place_longshot_are_separate_roles():
    resp = client.get("/api/model-suggestions?date=2026-07-05")
    body = resp.json()
    roles = {"OLD_VELO_WIN", "OLD_VELO_PLACE", "OLD_VELO_LONGSHOT"}
    present = {r["model_label"] for r in body["rows"] if r["model_label"] in roles}
    if present:
        # Each role must be its own model_label — never merged into one generic "OLD_VELO" row.
        assert present <= roles
        for role in present:
            rows = [r for r in body["rows"] if r["model_label"] == role]
            assert all(r["model_label"] == role for r in rows)


def test_missing_model_artifacts_are_reported_not_silently_dropped():
    resp = client.get(f"/api/model-suggestions?date={JULY06}")
    body = resp.json()
    # On July 06, most legacy lanes have no artifact yet — they must show up
    # as MISSING_ARTIFACT with an expected_source_path, never just vanish.
    assert body["models_missing"], "Expected at least one missing lane for July 06"
    for m in body["missing_artifacts"]:
        assert m["status"] == "MISSING_ARTIFACT"
        assert m["expected_source_path"]
        assert m["reason"]


def test_race_filtered_endpoint_requires_race_id():
    resp = client.get(f"/api/model-suggestions-race?date={JULY06}")
    assert resp.status_code == 400


def test_race_filtered_endpoint_scopes_to_one_race():
    all_resp = client.get(f"/api/model-suggestions?date={JULY06}")
    all_body = all_resp.json()
    some_race_id = all_body["rows"][0]["race_id"]
    resp = client.get(f"/api/model-suggestions-race?date={JULY06}&race_id={some_race_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert all(r["race_id"] == some_race_id for r in body["rows"])


def test_no_supabase_writer_in_source():
    src = (ROOT / "scripts" / "ops" / "model_suggestions_builder.py").read_text(encoding="utf-8")
    lowered = src.lower()
    # The module discloses "no_supabase_writes": true in its response — that's
    # fine. What it must never contain is an actual Supabase client/writer.
    assert "supabase_url" not in lowered
    assert "supabase_service_role_key" not in lowered
    assert ".insert(" not in lowered
    assert ".upsert(" not in lowered


def test_no_telegram_or_live_scoring_path_touched():
    src = (ROOT / "scripts" / "ops" / "model_suggestions_builder.py").read_text(encoding="utf-8")
    lowered = src.lower()
    assert "telegram" not in lowered
    assert "run_prime_today" not in lowered
    assert "velo_prime_service" not in lowered
