import json
from datetime import date

from scripts.ops.run_handicap_release_shadow import build


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_runner_writes_auditable_candidate_from_preoff_card_and_history(tmp_path):
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    _write(history_dir / "form_history_test.json", {"runs": [
        {"horse_rp_uid": "7", "race_date": "2026-08-01", "or_rating": 75, "position": 4, "course_key": "york", "distance": "1m", "going": "GOOD"},
        {"horse_rp_uid": "7", "race_date": "2026-09-01", "or_rating": 74, "position": 1, "course_key": "york", "distance": "1m", "going": "GOOD"},
        {"horse_rp_uid": "7", "race_date": "2026-10-01", "or_rating": 72, "position": 6, "course_key": "ascot", "distance": "1m2f", "going": "SOFT"},
        {"horse_rp_uid": "7", "race_date": "2026-11-01", "or_rating": 71, "position": 7, "course_key": "ascot", "distance": "1m2f", "going": "SOFT"},
    ]})
    card = tmp_path / "card.json"
    _write(card, [{"race_id": "r1", "category": "Handicap", "course": "York", "going": "Good", "distance_furlongs": 8,
                   "race_time": "2026-11-26T14:00:00+00:00", "parsed_at": "2026-11-26T08:00:00+00:00", "source": "racing_post_account_racecard_capture", "html_sha256": "hash",
                   "runners": [{"horse_id": 7, "horse": "Evidence Horse", "official_rating": 70, "non_runner": False, "irish_reserve": False}]}])
    summary = build(standard_cache=card, target_date="2026-11-26", execute=True, history_dir=history_dir, report_dir=tmp_path / "reports")
    assert summary["candidate_for_review"] == 1
    assert summary["rows"][0]["status"] == "CANDIDATE_FOR_REVIEW"
    assert summary["rows"][0]["provider_predictions_consumed"] is False
    assert (tmp_path / "reports" / "handicap_release_shadow_2026_11_26.json").exists()


def test_after_off_or_reserve_card_never_creates_candidate(tmp_path):
    card = tmp_path / "card.json"
    _write(card, [{"race_id": "r1", "category": "Handicap", "course": "York", "going": "Good", "distance_furlongs": 8,
                   "race_time": "2026-11-26T14:00:00+00:00", "parsed_at": "2026-11-26T15:00:00+00:00", "runners": [{"horse_id": 7, "horse": "Late", "official_rating": 70}]}])
    summary = build(standard_cache=card, target_date="2026-11-26", execute=False, history_dir=tmp_path, report_dir=tmp_path)
    assert summary["candidate_for_review"] == 0
    assert summary["rows"][0]["missing"] == ["PREOFF_CARD_TIMESTAMP_UNPROVEN"]
