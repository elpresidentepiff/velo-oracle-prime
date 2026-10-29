import json

from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def _packet() -> dict:
    return {
        "date": "2026-10-12",
        "status": "SHADOW_ONLY_ENRICHED",
        "feature_schema_version": "FORMFAV_UK_SHADOW_V1",
        "races_primary": 1,
        "races_enriched": 1,
        "runners": 2,
        "training_eligible_runners": 1,
        "identity_mismatches": 1,
        "draw_conflicts": 0,
        "mean_quality_score": 0.75,
        "coverage": {"form": 1, "class_profile": 2, "class_fit": 1, "track_bias": 2, "speed_map": 1, "pace_scenario": 0},
        "enrichment_audit": {"track_bias_calls_failed": 1, "errors": ["not found"]},
        "races": [
            {
                "race_id": "race-1",
                "course": "Test Course",
                "off_time": "2.30",
                "runner_count": 2,
                "training_eligible_runners": 1,
                "mean_quality_score": 0.75,
                "formfav_pace_scenario": None,
                "speedmap_coverage": 0.5,
                "runners": [
                    {"ff_form_present": 1, "ff_class_fit_present": 1, "ff_track_bias_present": 1, "ff_speedmap_present": 1},
                    {"ff_form_present": 0, "ff_class_fit_present": 0, "ff_track_bias_present": 1, "ff_speedmap_present": 0},
                ],
            }
        ],
    }


def test_formfav_dashboard_endpoint_is_read_only_shadow(monkeypatch, tmp_path):
    packet_path = tmp_path / "formfav.json"
    packet_path.write_text(json.dumps(_packet()), encoding="utf-8")
    monkeypatch.setattr(main, "_report_artifact", lambda artifact_type, date, local_path: (_packet(), "local_file"))

    response = client.get("/api/formfav-shadow?date=2026-10-12")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert body["health_status"] == "PASS"
    assert body["artifact_status"] == "SHADOW_ONLY_ENRICHED"
    assert body["shadow_only"] is True
    assert body["production_influence"] is False
    assert body["stake_authorised"] is False
    assert body["promotion_eligible"] is False
    assert body["summary"]["identity_mismatches"] == 1
    assert body["races"][0]["feature_coverage"] == {
        "form": 1,
        "class_fit": 1,
        "track_bias": 2,
        "speed_map": 1,
    }


def test_formfav_dashboard_missing_packet_is_explicit(monkeypatch):
    monkeypatch.setattr(main, "_report_artifact", lambda artifact_type, date, local_path: (None, None))
    monkeypatch.setattr(main, "_sb_rest_rows", lambda path: None)

    body = client.get("/api/formfav-shadow?date=2099-01-01").json()

    assert body["status"] == "NOT_RUN"
    assert body["health_status"] == "FAIL"
    assert body["artifact_status"] == "MISSING"
    assert body["races"] == []
    assert body["production_influence"] is False


def test_formfav_zero_coverage_packet_is_explicit_failure(monkeypatch):
    packet = _packet()
    packet.update(
        {
            "status": "SHADOW_NO_USABLE_ENRICHMENT",
            "races_enriched": 0,
            "runners": 0,
            "races": [],
        }
    )
    monkeypatch.setattr(
        main,
        "_report_artifact",
        lambda artifact_type, date, local_path: (packet, "supabase_report_artifacts"),
    )

    body = client.get("/api/formfav-shadow?date=2026-10-14").json()

    assert body["status"] == "OK"
    assert body["health_status"] == "FAIL"
    assert body["artifact_status"] == "SHADOW_NO_USABLE_ENRICHMENT"
    assert body["summary"]["races_enriched"] == 0


def test_formfav_dashboard_shows_cached_predictions_while_enrichment_is_pending(monkeypatch):
    monkeypatch.setattr(main, "_report_artifact", lambda artifact_type, date, local_path: (None, None))

    def rest(path: str):
        if path.startswith("formfav_races?"):
            return [
                {
                    "provider_race_key": "formfav:gb:2026-10-21:test:r1",
                    "track": "Test Course",
                    "race_number": 1,
                    "start_time": "2026-10-21T12:00:00Z",
                    "metadata": {"raceName": "Test Race", "numberOfRunners": 2},
                }
            ]
        if path.startswith("formfav_predictions?"):
            return [{
                "provider_race_key": "formfav:gb:2026-10-21:test:r1",
                "model_version": "2026-10-10",
                "confidence": "medium",
                "captured_at": "2026-10-20T23:00:00Z",
            }]
        if path.startswith("formfav_runner_form?"):
            return [
                {"provider_race_key": "formfav:gb:2026-10-21:test:r1", "scratched": False,
                 "form_payload": {"form": "12", "stats": {"overall": {"starts": 2}}, "speedMap": {}}},
                {"provider_race_key": "formfav:gb:2026-10-21:test:r1", "scratched": False,
                 "form_payload": {"form": "3", "classProfile": {}, "raceClassFit": {}}},
            ]
        raise AssertionError(path)

    monkeypatch.setattr(main, "_sb_rest_rows", rest)

    body = client.get("/api/formfav-shadow?date=2026-10-21").json()

    assert body["status"] == "OK"
    assert body["health_status"] == "PENDING"
    assert body["artifact_status"] == "FORMFAV_PREDICTIONS_READY_ENRICHMENT_PENDING"
    assert body["source"] == "supabase_formfav_cache"
    assert body["summary"]["predictions_ready"] == 1
    assert body["summary"]["races_enriched"] == 0
    assert body["races"][0]["feature_coverage"]["form"] == 2
    assert body["production_influence"] is False


def test_dashboard_displays_formfav_shadow_boundary():
    html = (main.pathlib.Path(main.__file__).parent / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")

    assert "/api/formfav-shadow" in html
    assert "SHADOW ONLY · PRODUCTION INFLUENCE 0 · NO STAKING" in html


def test_track_bias_coverage_requires_a_sample_when_the_packet_has_one(monkeypatch):
    packet = _packet()
    for runner in packet["races"][0]["runners"]:
        runner["ff_barrier_bias_sample_ok"] = 0  # row matched, but no usable sample
    packet["races"][0]["runners"][0]["ff_barrier_bias_sample_ok"] = 1
    monkeypatch.setattr(main, "_report_artifact", lambda artifact_type, date, local_path: (packet, "local_file"))

    body = client.get("/api/formfav-shadow?date=2026-10-12").json()

    assert body["races"][0]["feature_coverage"]["track_bias"] == 1


def test_feature_coverage_is_computed_per_race_not_from_a_shared_loop_variable(monkeypatch):
    packet = _packet()
    race_a = packet["races"][0]
    race_a["race_id"] = "race-a"
    race_a["runners"] = [
        {"ff_form_present": 1, "ff_class_fit_present": 0, "ff_barrier_bias_sample_ok": 1, "ff_speedmap_present": 0},
        {"ff_form_present": 1, "ff_class_fit_present": 0, "ff_barrier_bias_sample_ok": 0, "ff_speedmap_present": 0},
    ]
    race_b = {
        "race_id": "race-b",
        "course": "Other Course",
        "off_time": "3.00",
        "runners": [
            {"ff_form_present": 0, "ff_class_fit_present": 1, "ff_track_bias_present": 1, "ff_speedmap_present": 1},
            {"ff_form_present": 0, "ff_class_fit_present": 1, "ff_track_bias_present": 1, "ff_speedmap_present": 1},
            {"ff_form_present": 0, "ff_class_fit_present": 1, "ff_track_bias_present": 0, "ff_speedmap_present": 1},
        ],
    }
    packet["races"].append(race_b)
    monkeypatch.setattr(main, "_report_artifact", lambda artifact_type, date, local_path: (packet, "local_file"))

    races = {r["race_id"]: r["feature_coverage"] for r in client.get("/api/formfav-shadow?date=2026-10-12").json()["races"]}

    # race-a has the newer sample flag, so only the sampled runner counts; race-b falls back to the matched flag.
    assert races["race-a"] == {"form": 2, "class_fit": 0, "track_bias": 1, "speed_map": 0}
    assert races["race-b"] == {"form": 0, "class_fit": 3, "track_bias": 2, "speed_map": 3}
