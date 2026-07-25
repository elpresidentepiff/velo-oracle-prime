"""New Build join in the dashboard's live-snapshot governed-card path (2026-07-18 fix).

Regression guard: _build_governed_card_from_live_snapshots() must join New Build's
race_day_scorecards to live runner snapshot rows by plain numeric race_id with NO
remap -- both sources already use the same numeric scheme. A prior bug applied the
numeric->rp_COURSE_DATE_TIME remap here (correct only for a different endpoint's
CHAMPION_INTENT_SHADOW join), which broke this join 100% of the time.
"""
import json

import scripts.ops.new_build_dashboard_server as server


def _write_runner_snapshot(tmp_path, date_hyphen, race_id, horse="Rizal"):
    date_tag = date_hyphen.replace("-", "_")
    path = tmp_path / "data" / f"runner_snapshots_{date_tag}_test.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "race_date": date_hyphen, "race_id": race_id, "horse": horse,
        "course": "Newbury", "off_time": "17:05", "rank": 1,
        "velo_prime_prob": 0.4, "market_deception_score": 0.1,
        "improvement_score": 0.1, "place_prob": 0.6,
    }
    path.write_text(json.dumps(row) + "\n")


def _write_two_lane_readiness(tmp_path, date_hyphen, race_id):
    d = tmp_path / "data" / "new_build" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "race_day_scorecards": [{
            "race_id": race_id,
            "runner_count": 8,
            "passport_coverage": 0.5,
            "lane_a_top3": [
                {"horse": "Rizal", "rank": 1, "prob": 0.42, "nb_decision_lane": "LANE_A"},
            ],
        }],
    }
    (d / f"two_lane_readiness_{date_hyphen.replace('-', '_')}.json").write_text(json.dumps(payload))


def test_new_build_top3_joins_by_plain_numeric_race_id(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "NEW_BUILD_ROOT", tmp_path / "data" / "new_build")
    monkeypatch.setattr(server, "REPORT_DIR", tmp_path / "data" / "new_build" / "reports")

    race_id = "923137"
    _write_runner_snapshot(tmp_path, "2026-07-18", race_id)
    _write_two_lane_readiness(tmp_path, "2026-07-18", race_id)

    result = server._build_governed_card_from_live_snapshots("2026-07-18")
    assert result is not None
    verdict = result["verdicts"][0]
    assert verdict["new_build_top3"], "New Build top3 must join by plain numeric race_id"
    assert verdict["new_build_top3"][0]["horse"] == "Rizal"


def test_new_build_top3_empty_when_race_ids_genuinely_differ(tmp_path, monkeypatch):
    """Sanity check the join isn't vacuously true -- mismatched IDs stay empty."""
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "NEW_BUILD_ROOT", tmp_path / "data" / "new_build")
    monkeypatch.setattr(server, "REPORT_DIR", tmp_path / "data" / "new_build" / "reports")

    _write_runner_snapshot(tmp_path, "2026-07-18", "923137")
    _write_two_lane_readiness(tmp_path, "2026-07-18", "999999")  # different race

    result = server._build_governed_card_from_live_snapshots("2026-07-18")
    assert result is not None
    verdict = result["verdicts"][0]
    assert verdict["new_build_top3"] == []
