from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.canonical_dashboard_metrics import build_canonical_dashboard_payload
from scripts.ops import new_build_dashboard_server as dashboard


ROOT = Path(__file__).resolve().parents[1]


def _captain_row(day: str, race: int, status: str, *, win=None, frame=None, captured=2.0, sp=2.0) -> dict:
    return {
        "run_date": day,
        "race_id": str(race),
        "off_time": f"1{race}:00",
        "model_name": "CAPTAIN_VELO_VALUE_V1",
        "lane_name": "selective_value_forward_shadow_only",
        "rank": 1,
        "truth_contract_version": "CANONICAL_TRUTH_V2",
        "horse": f"Horse {race}",
        "horse_id": f"h{race}",
        "dashboard_metrics_eligible": True,
        "settlement_status": status,
        "subject_outcome_code": "NR" if status == "VOID" else str(1 if win else 5),
        "win": win,
        "frame": frame,
        "captured_odds_dec": captured,
        "settled_sp_dec": sp,
        "odds_timestamp_before_off": True,
        "odds_capture_ts": f"{day}T08:00:00+00:00",
        "source_path": f"data/reports/captain_velo_shadow_{day.replace('-', '_')}.json",
        "price_source": "CAPTAIN_FORWARD_PACKET_DECIMAL_ODDS",
    }


def test_phase4_monday_captain_denominators_and_separate_price_books():
    rows = [
        _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True, captured=11.0, sp=4.33),
        _captain_row("2026-09-28", 2, "SETTLED", win=True, frame=True, captured=11.0, sp=6.0),
        *[_captain_row("2026-09-28", race, "SETTLED", win=False, frame=False) for race in range(3, 7)],
        _captain_row("2026-09-28", 7, "VOID", captured=15.0, sp=None),
    ]
    payload = build_canonical_dashboard_payload(rows, "2026-09-28")
    captain = payload["models"][0]
    assert (captain["wins"], captain["settled"], captain["voids"], captain["selections"]) == (2, 6, 1, 7)
    assert captain["captured_price"]["profit"] == 16.0
    assert captain["settled_sp"]["profit"] == 4.33
    assert payload["window"]["mode"] == "GOVERNED_TRUTH_V2"
    assert payload["window"]["forward_evidence_status"] == "UNAVAILABLE_NOT_PROVEN_FOR_WHOLE_WINDOW"
    assert len(payload["captain"]["canonical_selections"]) == 7
    assert payload["captain"]["canonical_selections"][-1]["settlement_status"] == "VOID"
    assert all(row["forward_evidence_status"] == "PREDECLARED_PACKET_PROVEN" for row in payload["captain"]["canonical_selections"])


def test_phase4_missing_capture_never_uses_sp():
    row = _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True, captured=None, sp=9.0)
    metric = build_canonical_dashboard_payload([row], "2026-09-28")["models"][0]
    assert metric["captured_price"]["status"] == "UNAVAILABLE"
    assert metric["captured_price"]["profit"] is None
    assert metric["settled_sp"]["status"] == "AVAILABLE"
    assert metric["settled_sp"]["profit"] == 8.0
    selection = build_canonical_dashboard_payload([row], "2026-09-28")["captain"]["canonical_selections"][0]
    assert selection["captured_price_status"] == "UNAVAILABLE"
    legacy = dict(row, truth_contract_version=None)
    assert build_canonical_dashboard_payload([legacy], "2026-09-28")["models"] == []


def test_phase4_uncertainty_and_drawdown_are_day_clustered():
    rows = []
    for index, day in enumerate(("2026-09-26", "2026-09-27", "2026-09-28"), 1):
        rows.append(_captain_row(day, index, "SETTLED", win=index == 1, frame=index == 1, captured=4.0, sp=3.0))
    metric = build_canonical_dashboard_payload(rows, "2026-09-28")["models"][0]
    assert metric["captured_price"]["uncertainty"]["status"] == "AVAILABLE"
    assert metric["captured_price"]["uncertainty"]["days"] == 3
    assert metric["captured_price"]["max_drawdown"] == 2.0
    assert metric["captured_price"]["profit_ex_biggest_winner"] == -2.0


def test_phase4_clusters_correlated_families_and_scores_overlap_cohorts():
    production = dict(
        _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True),
        model_name="MAIN_VELO_PRIME", lane_name="main",
    )
    captain_overlap = _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True)
    captain_disagree = _captain_row("2026-09-28", 2, "SETTLED", win=False, frame=False)
    production_disagree = dict(
        _captain_row("2026-09-28", 2, "SETTLED", win=True, frame=True),
        model_name="MAIN_VELO_PRIME", lane_name="main", horse="Other", horse_id="other",
    )
    payload = build_canonical_dashboard_payload(
        [production, captain_overlap, captain_disagree, production_disagree], "2026-09-28"
    )
    captain = next(m for m in payload["models"] if m["model_name"].startswith("CAPTAIN"))
    assert captain["production_cohort"]["overlap"] == {"selections": 1, "settled": 1, "wins": 1}
    assert captain["production_cohort"]["disagreement"] == {"selections": 1, "settled": 1, "wins": 0}
    assert any(cluster["family"] == "CAPTAIN_VALUE" for cluster in payload["correlated_families"])


def test_phase4_overlap_fails_closed_for_ineligible_candidate_or_production():
    production = dict(_captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True), model_name="MAIN_VELO_PRIME", lane_name="main")
    candidate = _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True)
    candidate_ineligible = dict(candidate, dashboard_metrics_eligible=False)
    metric = next(m for m in build_canonical_dashboard_payload([production, candidate_ineligible], "2026-09-28")["models"] if m["model_name"].startswith("CAPTAIN"))
    assert metric["production_cohort"] == {"overlap": {"selections": 0, "settled": 0, "wins": 0}, "disagreement": {"selections": 0, "settled": 0, "wins": 0}}
    production_ineligible = dict(production, dashboard_metrics_eligible=False)
    metric = next(m for m in build_canonical_dashboard_payload([production_ineligible, candidate], "2026-09-28")["models"] if m["model_name"].startswith("CAPTAIN"))
    assert metric["production_cohort"]["overlap"]["selections"] == 0


def test_phase4_drawdown_uses_uk_race_time_not_lexical_order():
    rows = [
        dict(_captain_row("2026-09-28", 1, "SETTLED", win=False, frame=False, captured=2.0), off_time="3:00"),
        dict(_captain_row("2026-09-28", 2, "SETTLED", win=True, frame=True, captured=6.0), off_time="20:00"),
        dict(_captain_row("2026-09-28", 3, "SETTLED", win=False, frame=False, captured=2.0), off_time="9.00"),
        dict(_captain_row("2026-09-28", 4, "VOID", captured=2.0), off_time="2.30"),
        dict(_captain_row("2026-09-28", 5, "VOID", captured=2.0), off_time="10:00"),
    ]
    metric = build_canonical_dashboard_payload(rows, "2026-09-28")["models"][0]
    assert metric["captured_price"]["max_drawdown"] == 1.0


def test_phase4_captain_panel_uses_governed_chronology():
    rows = [
        dict(_captain_row("2026-09-28", 1, "VOID"), off_time="9.00", horse="Evening"),
        dict(_captain_row("2026-09-28", 2, "VOID"), off_time="2.30", horse="Afternoon"),
        dict(_captain_row("2026-09-28", 3, "VOID"), off_time="10:00", horse="Morning"),
    ]
    panel = build_canonical_dashboard_payload(rows, "2026-09-28")["captain"]["canonical_selections"]
    assert [row["horse"] for row in panel] == ["Morning", "Afternoon", "Evening"]


def test_phase4_forward_evidence_requires_complete_packet_provenance():
    proven = _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True, captured=3.0)
    assert build_canonical_dashboard_payload([proven], "2026-09-28")["captain"]["canonical_selections"][0]["forward_evidence_status"] == "PREDECLARED_PACKET_PROVEN"
    variants = [
        dict(proven, odds_capture_ts=None),
        dict(proven, odds_capture_ts="not-a-timestamp"),
        dict(proven, odds_capture_ts="2026-09-28T08:00:00"),
        dict(proven, captured_odds_dec=1.0),
        dict(proven, source_path="data/reports/not_the_authoritative_packet.json"),
        dict(proven, source_path="data/reports/captain_velo_shadow_2026_09_27.json"),
        {**proven, "price_source": None, "odds_capture_ts": None, "captured_odds_dec": None},
    ]
    for row in variants:
        selection = build_canonical_dashboard_payload([row], "2026-09-28")["captain"]["canonical_selections"][0]
        assert selection["forward_evidence_status"] == "UNAVAILABLE_NOT_PROVEN"


def test_phase4_lane_taxonomy_is_explicit_and_unknown_fails_closed():
    cases = [
        ("MAIN_VELO_PRIME", "main", "PRODUCTION"),
        ("CAPTAIN_VELO_VALUE_V1", "selective_value_forward_shadow_only", "SELECTIVE_VALUE_SHADOW"),
        ("NEW_BUILD_LANE_A_MODEL", "lane_a", "SHADOW"),
        ("OLD_VELO_WIN_ROLE", "WIN", "REPORT_ONLY"),
        ("PASSPORT_STRENGTH_SCORE_PROXY", "proxy_not_a_model", "PROXY"),
        ("MYSTERY_MODEL", "mystery", "UNKNOWN"),
    ]
    rows = [dict(_captain_row("2026-09-28", index, "SETTLED", win=False, frame=False), model_name=model, lane_name=lane) for index, (model, lane, _) in enumerate(cases, 1)]
    payload = build_canonical_dashboard_payload(rows, "2026-09-28")
    observed = {m["model_name"]: m["lane_type"] for m in payload["models"]}
    assert observed == {model: expected for model, _, expected in cases}


def test_phase4_invalid_decimal_odds_are_unavailable():
    row = _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True, captured=1.0, sp=0.5)
    metric = build_canonical_dashboard_payload([row], "2026-09-28")["models"][0]
    assert metric["captured_price"]["status"] == "UNAVAILABLE"
    assert metric["settled_sp"]["status"] == "UNAVAILABLE"


def test_phase4_bootstrap_is_deterministic():
    rows = [_captain_row(day, index, "SETTLED", win=index % 2 == 0, frame=True, captured=4.0) for index, day in enumerate(("2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28"), 1)]
    first = build_canonical_dashboard_payload(rows, "2026-09-28")["models"][0]["captured_price"]["uncertainty"]
    second = build_canonical_dashboard_payload(list(reversed(rows)), "2026-09-28")["models"][0]["captured_price"]["uncertainty"]
    assert first == second


def test_phase4_endpoint_is_supabase_read_only(monkeypatch):
    row = _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True, captured=3.0, sp=2.5)
    calls = []

    def fake_get(path: str, *, strict: bool = False):
        calls.append(path)
        if path.startswith("/canonical_model_scorecards"):
            return [row]
        if path.startswith("/velo_mission_control"):
            return [{"run_date": "2026-09-28", "generated_at": "2026-09-28T23:00:00Z", "learning_gate_status": "PASS", "payload": {"learning_admission": {"eligibility_status": "ADMITTED", "eligible_rows": 7, "excluded_rows": 1}}}]
        raise AssertionError(path)

    monkeypatch.setattr(dashboard, "_sb_get", fake_get)
    response = TestClient(dashboard.app).get("/api/canonical-performance?date=2026-09-28")
    assert response.status_code == 200
    data = response.json()
    assert data["no_supabase_write"] is True
    assert data["post_learning_mission_control"]["learning_admission_status"] == "ADMITTED"
    assert data["post_learning_mission_control"]["learning_eligible_rows"] == 7
    assert calls and all(path.startswith(("/canonical_model_scorecards", "/velo_mission_control")) for path in calls)
    assert "rank=eq.1" in calls[0] and "truth_contract_version=eq.CANONICAL_TRUTH_V2" in calls[0]
    assert "select=*" not in calls[0]


def test_phase4_strict_pagination_never_returns_partial_history(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    first_page = MagicMock()
    first_page.__enter__.return_value.read.return_value = __import__("json").dumps([{"race_id": str(i)} for i in range(1000)]).encode()
    monkeypatch.setattr(dashboard.urllib.request, "urlopen", MagicMock(side_effect=[first_page, OSError("page two failed")]))
    try:
        dashboard.fetch_canonical_scorecard_window("2026-09-28")
    except RuntimeError as exc:
        assert "offset 1000" in str(exc)
    else:
        raise AssertionError("strict canonical pagination returned partial history")


def test_phase4_strict_pagination_cap_fails_instead_of_truncating(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setattr(dashboard, "STRICT_CANONICAL_MAX_ROWS", 2)
    page = MagicMock()
    page.__enter__.return_value.read.return_value = __import__("json").dumps([{"race_id": "1"}, {"race_id": "2"}, {"race_id": "3"}]).encode()
    monkeypatch.setattr(dashboard.urllib.request, "urlopen", MagicMock(return_value=page))
    try:
        dashboard.fetch_canonical_scorecard_window("2026-09-28")
    except RuntimeError as exc:
        assert "safety ceiling of 2 rows" in str(exc)
    else:
        raise AssertionError("strict canonical pagination silently truncated at the safety ceiling")
    monkeypatch.setattr(dashboard, "fetch_canonical_scorecard_window", MagicMock(side_effect=RuntimeError("safety ceiling of 2 rows")))
    assert TestClient(dashboard.app).get("/api/canonical-performance?date=2026-09-28").status_code == 503


def test_phase4_endpoint_parity_and_iso_validation(monkeypatch):
    from app.main import app as canonical_app

    row = _captain_row("2026-09-28", 1, "SETTLED", win=True, frame=True)
    monkeypatch.setattr(dashboard, "fetch_canonical_scorecard_window", MagicMock(return_value=[row]))
    monkeypatch.setattr(dashboard, "fetch_final_mission_control", MagicMock(return_value={}))
    primary = TestClient(canonical_app).get("/api/canonical-performance?date=2026-09-28")
    deprecated = TestClient(dashboard.app).get("/api/canonical-performance?date=2026-09-28")
    assert primary.status_code == deprecated.status_code == 200
    assert primary.json()["models"] == deprecated.json()["models"]
    assert TestClient(canonical_app).get("/api/canonical-performance?date=28-09-2026").status_code == 400
    assert TestClient(dashboard.app).get("/api/canonical-performance?date=2026-9-28").status_code == 400
    monkeypatch.setattr(dashboard, "fetch_canonical_scorecard_window", MagicMock(side_effect=RuntimeError("page two failed")))
    assert TestClient(canonical_app).get("/api/canonical-performance?date=2026-09-28").status_code == 503
    assert TestClient(dashboard.app).get("/api/canonical-performance?date=2026-09-28").status_code == 503


def test_phase4_dashboard_uses_canonical_aggregate_and_has_no_write_call():
    html = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
    server = (ROOT / "scripts/ops/new_build_dashboard_server.py").read_text(encoding="utf-8")
    canonical_app = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "/api/canonical-performance" in html
    assert '@app.get("/api/canonical-performance")' in canonical_app
    assert "CAPTAIN VELO — CANONICAL SELECTIONS" in html
    assert "FAMILY GROUPS ARE NON-INDEPENDENT" in html
    assert "member hits are not votes" in html
    assert "member-row observations" in html
    assert "frozen_selections" not in html
    assert "FINAL POST-LEARNING MISSION CONTROL" in html
    assert "UNAVAILABLE" in html
    assert "method=\"POST\"" not in server
    assert "_sb_upsert" not in server
