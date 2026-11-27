from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def _report() -> dict:
    return {
        "date": "2026-11-27",
        "status": "OK",
        "tag_scorecards": [{
            "tag": "HANDICAP_RELEASE",
            "treatment": {"n": 3, "sp_decimal_coverage_pct": 100.0},
            "same_race_control": {"n": 12},
            "delta_win_rate_pp": 8.3,
            "delta_top_3_rate_pp": 12.5,
        }],
        "guardrails": {"scoring_effect": "NONE", "promotion_effect": "NONE"},
    }


def test_rpdc_matched_control_endpoint_reads_exact_dated_artifact(monkeypatch):
    requested: list[tuple[str, str | None]] = []

    def artifact(artifact_type, date, local_path):
        requested.append((artifact_type, date))
        return _report(), "supabase_report_artifacts"

    monkeypatch.setattr(main, "_report_artifact", artifact)
    response = client.get("/rpdc_tag_matched_control.json?date=2026-11-27")

    assert response.status_code == 200
    body = response.json()
    assert requested == [("rpdc_tag_matched_control", "2026-11-27")]
    assert body["date"] == "2026-11-27"
    assert body["source"] == "supabase_report_artifacts"
    assert body["tag_scorecards"][0]["tag"] == "HANDICAP_RELEASE"


def test_rpdc_matched_control_never_substitutes_another_date(monkeypatch):
    monkeypatch.setattr(main, "_report_artifact", lambda *args: (None, None))
    response = client.get("/rpdc_tag_matched_control.json?date=2026-11-27")

    assert response.status_code == 200
    assert response.json()["status"] == "NOT_AVAILABLE_FOR_REQUESTED_DATE"
    assert response.json()["tag_scorecards"] == []


def test_rpdc_matched_control_rejects_missing_or_bad_date():
    assert client.get("/rpdc_tag_matched_control.json").status_code == 400
    assert client.get("/rpdc_tag_matched_control.json?date=not-a-date").status_code == 400


def test_dashboard_has_visible_read_only_rpdc_tag_evidence_card():
    html = (main.pathlib.Path(main.__file__).parent / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")

    assert "RPDC TAG EVIDENCE" in html
    assert "/rpdc_tag_matched_control.json" in html
    assert "no scoring, promotion, or staking effect" in html


def test_cumulative_rpdc_evidence_endpoint_is_date_bound(monkeypatch):
    packet = {"as_of_date": "2026-11-27", "status": "OK", "tag_scorecards": [], "days_with_usable_evidence": 1}
    monkeypatch.setattr(main, "_report_artifact", lambda *args: (packet, "supabase_report_artifacts"))

    response = client.get("/rpdc_tag_matched_control_cumulative.json?date=2026-11-27")

    assert response.status_code == 200
    assert response.json()["as_of_date"] == "2026-11-27"
    assert response.json()["source"] == "supabase_report_artifacts"


def test_cumulative_rpdc_evidence_missing_date_remains_explicit(monkeypatch):
    monkeypatch.setattr(main, "_report_artifact", lambda *args: (None, None))

    response = client.get("/rpdc_tag_matched_control_cumulative.json?date=2026-11-27")

    assert response.status_code == 200
    assert response.json()["status"] == "NOT_AVAILABLE_FOR_REQUESTED_DATE"
