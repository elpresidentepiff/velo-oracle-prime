"""The EOD container must receive the files the shadow lanes' scorecard rows are rebuilt from.

2026-11-07: Champion Intent, New Build A/B and the Passport proxy had ~75 top-pick rows each and 0 results after the
EOD passed. Their rows are rebuilt from files the morning container writes (two_lane_readiness JSON, the passport feed
JSONL, the intent shadow CSV). The EOD container starts clean and only restored the report artifacts that had been
persisted, which did not include those three, so the rebuild skipped the lanes.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import scripts.ops.build_canonical_model_scorecard as bcms
import scripts.ops.persist_daily_artifacts as pda
import scripts.ops.rp_cloud_eod as eod

DATE = "2026-11-07"
TAG = "2026_11_07"
READINESS = f"data/new_build/reports/two_lane_readiness_{TAG}.json"
FEED = f"data/new_build/current_cards/current_card_passport_feed_{TAG}.jsonl"
CHAMPION = f"data/reports/intent_shadow_scorecard_{TAG}.csv"


def _write_morning_files(root: Path, *, crlf: bool = False) -> None:
    (root / READINESS).parent.mkdir(parents=True, exist_ok=True)
    (root / READINESS).write_text(
        json.dumps(
            {
                "race_day_scorecards": [
                    {
                        "race_id": "1",
                        "course": "Kelso",
                        "off_time": "2.00",
                        "lane_a_top3": [{"horse": "Alpha", "rank": 1, "prob": 0.4, "nb_decision_lane": "WIN_TRUST"}],
                        "lane_b_top3": [{"horse": "Beta", "rank": 1, "prob": 0.3, "nb_decision_lane": "FRAME_TRUST"}],
                        "lane_c_top3": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / FEED).parent.mkdir(parents=True, exist_ok=True)
    feed = [{"race_id": "1", "horse": "Alpha", "rp_uid": 11, "passport_strength_score": 0.9}]
    (root / FEED).write_text("\n".join(json.dumps(r) for r in feed) + "\n", encoding="utf-8")
    (root / CHAMPION).parent.mkdir(parents=True, exist_ok=True)
    header = [
        "race_id",
        "horse",
        "rank_in_race",
        "champion_intent_shadow_prob",
        "velo_scoring_allowed",
        "trust_policy",
        "stake_authorised",
        "dashboard_visible",
        "rp_uid",
        "course",
        "off_time",
    ]
    body = [
        ["1", "Alpha", "1", "0.5", "False", "ARCHIVE_CONTEXT_ONLY_NOT_SCORING", "False", "False", "11", "Kelso", "2.00"]
    ]
    with (root / CHAMPION).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\r\n" if crlf else "\n")
        writer.writerow(header)
        writer.writerows(body)


def _write_results(root: Path) -> None:
    path = root / "data" / "results" / f"rp_results_{TAG}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "race_id": "1",
                        "course": "Kelso",
                        "off": "2.00",
                        "runners": [
                            {"horse": "Alpha", "position": "1", "horse_id": "11", "sp_dec": 3.0},
                            {"horse": "Beta", "position": "2", "horse_id": "22", "sp_dec": 5.0},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _rebuild(root: Path, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    monkeypatch.setattr(bcms, "ROOT", root)
    monkeypatch.setattr(bcms, "_ensure_env", lambda: None)
    monkeypatch.setattr(bcms, "load_verdicts", lambda *a, **k: ([], "NONE"))
    rows, _audit = bcms.build_scorecard(DATE)
    return rows


def _eod_container_after_morning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, crlf: bool = False) -> Path:
    """Morning container persists its artifacts; a clean EOD container restores them from the table."""
    morning, evening = tmp_path / "morning", tmp_path / "evening"
    morning.mkdir()
    evening.mkdir()
    _write_morning_files(morning, crlf=crlf)
    monkeypatch.setattr(pda, "ROOT", morning)
    persisted = json.loads(json.dumps(pda.build_reports([DATE]), default=str))  # what comes back from Supabase
    monkeypatch.setattr(eod, "ROOT", evening)
    monkeypatch.setattr(eod, "_get", lambda table, params: persisted)
    eod._hydrate_report_artifacts(DATE)
    _write_results(evening)  # the EOD's own capture + parse writes this one
    return evening


def test_clean_eod_container_without_the_inputs_settles_none_of_the_four_lanes(tmp_path, monkeypatch) -> None:
    clean = tmp_path / "clean"
    clean.mkdir()
    _write_results(clean)
    lanes = {r["model_name"] for r in _rebuild(clean, monkeypatch)}
    assert not lanes & {
        "CHAMPION_INTENT_SHADOW",
        "NEW_BUILD_LANE_A_MODEL",
        "NEW_BUILD_LANE_B_MODEL",
        "PASSPORT_STRENGTH_SCORE_PROXY",
    }


def test_after_persist_and_restore_the_four_lanes_are_rebuilt_with_results(tmp_path, monkeypatch) -> None:
    evening = _eod_container_after_morning(tmp_path, monkeypatch)
    rows = {r["model_name"]: r for r in _rebuild(evening, monkeypatch)}
    for model in ("CHAMPION_INTENT_SHADOW", "NEW_BUILD_LANE_A_MODEL", "PASSPORT_STRENGTH_SCORE_PROXY"):
        assert rows[model]["horse"] == "Alpha"
        assert rows[model]["result_position"] == "1" and rows[model]["win"] is True, model
    assert rows["NEW_BUILD_LANE_B_MODEL"]["horse"] == "Beta"
    assert rows["NEW_BUILD_LANE_B_MODEL"]["result_position"] == "2"
    assert rows["NEW_BUILD_LANE_B_MODEL"]["win"] is False and rows["NEW_BUILD_LANE_B_MODEL"]["frame"] is True


def test_restored_text_files_are_identical_to_what_the_morning_wrote(tmp_path, monkeypatch) -> None:
    evening = _eod_container_after_morning(tmp_path, monkeypatch, crlf=True)
    morning = tmp_path / "morning"
    for rel in (FEED, CHAMPION):
        assert (evening / rel).read_bytes() == (morning / rel).read_bytes(), rel
    assert b"\r\n" in (evening / CHAMPION).read_bytes()  # CRLF survives, it is not rewritten to LF
    assert json.loads((evening / READINESS).read_text(encoding="utf-8")) == json.loads(
        (morning / READINESS).read_text(encoding="utf-8")
    )


def test_persist_registers_the_three_inputs_and_json_artifacts_keep_their_old_shape(tmp_path, monkeypatch) -> None:
    _write_morning_files(tmp_path)
    monkeypatch.setattr(pda, "ROOT", tmp_path)
    rows = {r["artifact_type"]: r for r in pda.build_reports([DATE])}
    assert set(rows) == {
        "new_build_two_lane_readiness",
        "new_build_current_card_passport_feed",
        "champion_intent_shadow_scorecard",
    }
    assert "race_day_scorecards" in rows["new_build_two_lane_readiness"]["payload"]  # plain JSON, as before
    assert set(rows["champion_intent_shadow_scorecard"]["payload"]) == {pda.TEXT_PAYLOAD_KEY, "format"}
    assert rows["champion_intent_shadow_scorecard"]["payload"]["format"] == "csv"
    assert rows["new_build_current_card_passport_feed"]["payload"]["format"] == "jsonl"


def test_an_oversize_text_input_is_skipped_not_fatal(tmp_path, monkeypatch) -> None:
    _write_morning_files(tmp_path)
    monkeypatch.setattr(pda, "ROOT", tmp_path)
    monkeypatch.setattr(pda, "TEXT_REPORT_MAX_BYTES", 10)
    types = {r["artifact_type"] for r in pda.build_reports([DATE])}
    assert "new_build_two_lane_readiness" in types
    assert not types & {"new_build_current_card_passport_feed", "champion_intent_shadow_scorecard"}


def test_hydrate_still_writes_ordinary_json_and_still_skips_the_verdict_backup(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(eod, "ROOT", tmp_path)
    rows = [
        {
            "artifact_type": "mds_heavy_shadow",
            "source_path": f"data/reports/mds_heavy_shadow_{TAG}.json",
            "payload": {"a": 1},
        },
        {
            "artifact_type": "velo_prime_verdicts",
            "source_path": f"data/velo_prime_verdicts_{TAG}.json",
            "payload": {"b": 2},
        },
        {"artifact_type": "evil", "source_path": "../outside.txt", "payload": {"__text": "x"}},
    ]
    monkeypatch.setattr(eod, "_get", lambda table, params: rows)
    assert eod._hydrate_report_artifacts(DATE) == 1
    assert json.loads((tmp_path / f"data/reports/mds_heavy_shadow_{TAG}.json").read_text(encoding="utf-8")) == {"a": 1}
    assert not (tmp_path / f"data/velo_prime_verdicts_{TAG}.json").exists()
    assert not (tmp_path.parent / "outside.txt").exists()


def test_the_registered_paths_are_the_ones_the_scorecard_builder_reads() -> None:
    builder = (Path(__file__).parents[1] / "scripts" / "ops" / "build_canonical_model_scorecard.py").read_text(
        encoding="utf-8"
    )
    for rel in (
        pda.REPORTS["new_build_two_lane_readiness"][0],
        pda.TEXT_REPORTS["new_build_current_card_passport_feed"],
        pda.TEXT_REPORTS["champion_intent_shadow_scorecard"],
    ):
        leaf = rel.rsplit("/", 1)[1]
        assert leaf in builder, f"the builder no longer reads {leaf}; update the persisted registry to match"
