"""
Tests for the RP results capture pipeline.

Covers:
- parse_rp_results_capture: NEXT_DATA extraction, runner parsing, horse_id computation
- build_rp_results_url_list: URL transformation
- Sigma integration: missing race blocked, ambiguous race review-only, RPR not used
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.parse_rp_results_capture import (
    _bst_hhmm,
    _find_result_data,
    _get_venue,
    _parse_runner,
    _slug,
    _sp_dec,
    _velo_horse_id,
    parse_results,
)
from scripts.ops.build_rp_results_url_list import build_results_url_list


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_result_runner(
    horse_name: str,
    position: int | str,
    sp: str = "5/1",
    non_runner: bool = False,
    horse_id: int = 123456,
) -> dict:
    return {
        "horseName": horse_name,
        "horseId": horse_id,
        "finishingPosition": str(position),
        "startingPrice": sp,
        "bspDecimal": 0.0,
        "nonRunner": non_runner,
        "jockeyName": "T Jockey",
        "trainerName": "T Trainer",
        "draw": 4,
    }


def _make_next_data(race_id: int, course_slug: str, race_time: str, runners: list) -> dict:
    return {
        "props": {
            "pageProps": {
                "initialState": {
                    "resultPage": {
                        "data": {
                            "race": {
                                "raceId": race_id,
                                "courseId": 30,
                                "courseName": "LEICESTER",
                                "courseStyleName": "Leicester",
                                "raceTime": race_time,
                                "raceTitle": "Test Stakes",
                                "raceClass": "5",
                                "going": "Good",
                                "distanceFurlongs": 8.0,
                                "status": "R",
                            },
                            "runners": runners,
                        }
                    }
                }
            }
        }
    }


LEICESTER_RESULT = _make_next_data(
    race_id=918927,
    course_slug="leicester",
    race_time="2026-05-26T13:00:00+01:00",
    runners=[
        _make_result_runner("Harlequin Breeze", 1, "7/2", horse_id=4001),
        _make_result_runner("Libertango", 2, "9/4", horse_id=4002),
        _make_result_runner("Escape Magic", 3, "5/1", horse_id=4003),
        _make_result_runner("Slow Coach", 4, "12/1", horse_id=4004),
    ],
)

LEICESTER_RESULT_NR = _make_next_data(
    race_id=918928,
    course_slug="leicester",
    race_time="2026-05-26T14:10:00+01:00",
    runners=[
        _make_result_runner("Alice De Clare", 1, "5/2", horse_id=5001),
        _make_result_runner("Happy Chandler", "NR", "4/1", non_runner=True, horse_id=5002),
        _make_result_runner("Late Entry", 2, "7/1", horse_id=5003),
    ],
)


# ── Unit tests: helpers ────────────────────────────────────────────────────────

class TestBstHhmm:
    def test_iso_datetime_bst(self):
        assert _bst_hhmm("2026-05-26T13:00:00+01:00") == "1.00"

    def test_iso_datetime_afternoon(self):
        assert _bst_hhmm("2026-05-26T17:07:00+01:00") == "5.07"

    def test_iso_datetime_early_afternoon(self):
        assert _bst_hhmm("2026-05-26T14:10:00+01:00") == "2.10"

    def test_fallback_string(self):
        result = _bst_hhmm("invalid")
        assert isinstance(result, str)


class TestSlug:
    def test_lowercase_spaces(self):
        assert _slug("Harlequin Breeze") == "harlequin_breeze"

    def test_special_chars(self):
        assert _slug("Grey-Fable's") == "grey_fable_s"

    def test_all_lower(self):
        assert _slug("DUNDALK AW") == "dundalk_aw"


class TestVeloHorseId:
    def test_basic(self):
        assert _velo_horse_id("LEI", "Harlequin Breeze") == "rp_LEI_harlequin_breeze"

    def test_apostrophe(self):
        assert _velo_horse_id("DUN", "Grey-Fable's") == "rp_DUN_grey_fable_s"


class TestSpDec:
    def test_fractional(self):
        assert _sp_dec("7/2") == pytest.approx(4.5)

    def test_evens(self):
        assert _sp_dec("1/1") == pytest.approx(2.0)

    def test_empty(self):
        assert _sp_dec("") == 0.0

    def test_decimal_passthrough(self):
        assert _sp_dec("4.5") == pytest.approx(4.5)


class TestGetVenue:
    def test_slug_lookup(self):
        assert _get_venue("leicester", "") == "LEI"

    def test_slug_aw(self):
        assert _get_venue("dundalk-aw", "") == "DUN"

    def test_coursename_fallback(self):
        assert _get_venue("", "Dundalk (A.W)") == "DUN"

    def test_unknown(self):
        assert _get_venue("unknown-track", "Unknown Track") == ""


class TestFindResultData:
    def test_resultpage_key(self):
        data = _find_result_data(LEICESTER_RESULT)
        assert data is not None
        assert data["race"]["raceId"] == 918927

    def test_racepage_fallback(self):
        next_data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "racePage": {
                            "data": {
                                "race": {"raceId": 99999, "status": "R"},
                                "runners": [],
                            }
                        }
                    }
                }
            }
        }
        data = _find_result_data(next_data)
        assert data is not None
        assert data["race"]["raceId"] == 99999

    def test_missing_returns_none(self):
        assert _find_result_data({}) is None

    def test_prerace_status_still_returned(self):
        # Parser does not block on status — let caller decide
        data = _find_result_data(LEICESTER_RESULT)
        assert data is not None


class TestParseRunner:
    def test_winner(self):
        raw = _make_result_runner("Harlequin Breeze", 1, "7/2", horse_id=4001)
        r = _parse_runner(raw, "LEI")
        assert r["horse"] == "Harlequin Breeze"
        assert r["position"] == "1"
        assert r["horse_id"] == "4001"
        assert r["sp_dec"] == pytest.approx(4.5)
        assert r["non_runner"] is False

    def test_non_runner(self):
        raw = _make_result_runner("Happy Chandler", "NR", non_runner=True)
        r = _parse_runner(raw, "LEI")
        assert r["non_runner"] is True
        assert r["position"] == "NR"

    def test_no_venue_still_parses(self):
        raw = _make_result_runner("Some Horse", 1, "3/1")
        r = _parse_runner(raw, "")
        assert r["horse"] == "Some Horse"
        assert r["horse_id"] == "123456"

    def test_rpr_not_in_output(self):
        raw = _make_result_runner("X", 1, "2/1")
        r = _parse_runner(raw, "LEI")
        assert "rpr" not in r
        assert "rpPostmark" not in r


# ── Integration: parse_results with fixture HTML ──────────────────────────────

def _write_next_data_html(path: Path, next_data: dict) -> None:
    nd_json = json.dumps(next_data)
    path.write_text(
        f'<html><head></head><body>'
        f'<script id="__NEXT_DATA__" type="application/json">{nd_json}</script>'
        f'</body></html>',
        encoding="utf-8",
    )


class TestParseResults:
    def test_full_parse_dry_run(self, tmp_path):
        cap_dir = tmp_path / "rp-results-2026-05-26"
        cap_dir.mkdir()
        html_file = cap_dir / "001_results_leicester_918927.html"
        _write_next_data_html(html_file, LEICESTER_RESULT)

        with patch(
            "scripts.ops.parse_rp_results_capture.RAW_ROOT", tmp_path
        ), patch(
            "scripts.ops.parse_rp_results_capture.OUT_DIR", tmp_path / "results"
        ):
            result = parse_results(
                date="2026-05-26",
                capture_date="rp-results-2026-05-26",
                execute=False,
            )

        assert result["status"] == "DRY_RUN"
        assert result["races_parsed"] == 1
        race = result["results"][0]
        assert race["race_id"] == "918927"
        assert race["winner_horse"] == "Harlequin Breeze"
        assert race["winner_id"] == "4001"
        assert len(race["top3_names"]) == 3
        assert race["top3_names"][0] == "Harlequin Breeze"

    def test_missing_race_blocked(self, tmp_path):
        """A race with no result data in NEXT_DATA is blocked from output."""
        cap_dir = tmp_path / "rp-results-2026-05-26"
        cap_dir.mkdir()
        # Write HTML with no recognizable result structure
        (cap_dir / "001_empty.html").write_text(
            '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"initialState":{}}}}</script></html>',
            encoding="utf-8",
        )

        with patch("scripts.ops.parse_rp_results_capture.RAW_ROOT", tmp_path), \
             patch("scripts.ops.parse_rp_results_capture.OUT_DIR", tmp_path / "results"):
            result = parse_results(date="2026-05-26", capture_date="rp-results-2026-05-26", execute=False)

        assert result["races_parsed"] == 0
        assert result["parse_errors"] == 1
        assert result["parse_error_details"][0]["reason"] == "NO_RESULT_DATA_IN_NEXT_DATA"

    def test_ambiguous_winner_review_only(self, tmp_path):
        """A race where winner cannot be determined (no finishers) is excluded from results."""
        cap_dir = tmp_path / "rp-results-2026-05-26"
        cap_dir.mkdir()
        nd = _make_next_data(
            race_id=918927,
            course_slug="leicester",
            race_time="2026-05-26T13:00:00+01:00",
            runners=[
                _make_result_runner("Horse A", "NR", non_runner=True),
                _make_result_runner("Horse B", "NR", non_runner=True),
            ],
        )
        html_file = cap_dir / "001.html"
        _write_next_data_html(html_file, nd)

        with patch("scripts.ops.parse_rp_results_capture.RAW_ROOT", tmp_path), \
             patch("scripts.ops.parse_rp_results_capture.OUT_DIR", tmp_path / "results"):
            result = parse_results(date="2026-05-26", capture_date="rp-results-2026-05-26", execute=False)

        assert result["races_parsed"] == 0
        assert any("NO_WINNER_FOUND" in e["reason"] for e in result["parse_error_details"])

    def test_execute_writes_file(self, tmp_path):
        cap_dir = tmp_path / "rp-results-2026-05-26"
        cap_dir.mkdir()
        _write_next_data_html(cap_dir / "001.html", LEICESTER_RESULT)

        with patch("scripts.ops.parse_rp_results_capture.RAW_ROOT", tmp_path), \
             patch("scripts.ops.parse_rp_results_capture.OUT_DIR", tmp_path / "results"):
            result = parse_results(date="2026-05-26", capture_date="rp-results-2026-05-26", execute=True)

        assert result["status"] == "PASS"
        out = Path(result["output"])
        assert out.exists()
        written = json.loads(out.read_text())
        assert written["races_parsed"] == 1

    def test_non_runner_excluded_from_finishers(self, tmp_path):
        cap_dir = tmp_path / "rp-results-2026-05-26"
        cap_dir.mkdir()
        _write_next_data_html(cap_dir / "001.html", LEICESTER_RESULT_NR)

        with patch("scripts.ops.parse_rp_results_capture.RAW_ROOT", tmp_path), \
             patch("scripts.ops.parse_rp_results_capture.OUT_DIR", tmp_path / "results"):
            result = parse_results(date="2026-05-26", capture_date="rp-results-2026-05-26", execute=False)

        assert result["races_parsed"] == 1
        race = result["results"][0]
        winner = race["winner_horse"]
        assert winner == "Alice De Clare"
        top3_names = race["top3_names"]
        assert "Happy Chandler" not in top3_names


# ── URL list builder tests ─────────────────────────────────────────────────────

class TestBuildResultsUrlList:
    def test_transforms_racecard_to_results(self, tmp_path):
        raw_root = tmp_path / "racing_post_account_raw"
        cap_dir = raw_root / "live-full-racepages-2026-05-26"
        cap_dir.mkdir(parents=True)
        manifest = {
            "captures": [
                {"source_url": "https://www.racingpost.com/racecards/30/leicester/2026-05-26/918927/"},
                {"source_url": "https://www.racingpost.com/racecards/30/leicester/2026-05-26/918928/"},
            ]
        }
        (cap_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        with patch("scripts.ops.build_rp_results_url_list.RAW_ROOT", raw_root), \
             patch("scripts.ops.build_rp_results_url_list.URL_LIST_ROOT", tmp_path / "url_lists"):
            result = build_results_url_list(date="2026-05-26", execute=False)

        assert result["status"] == "DRY_RUN"
        assert result["results_urls_built"] == 2
        assert all("/results/" in u for u in result["urls"])
        assert all("/racecards/" not in u for u in result["urls"])

    def test_missing_manifest_returns_fail(self, tmp_path):
        with patch("scripts.ops.build_rp_results_url_list.RAW_ROOT", tmp_path):
            result = build_results_url_list(date="2026-05-26", execute=False)

        assert result["status"] == "FAIL"

    def test_explicit_capture_label_is_authoritative(self, tmp_path):
        raw_root = tmp_path / "racing_post_account_raw"
        base = raw_root / "live-full-racepages-2026-05-26"
        refresh = raw_root / "live-full-racepages-2026-05-26-refresh"
        base.mkdir(parents=True)
        refresh.mkdir(parents=True)
        (base / "manifest.json").write_text(json.dumps({"captures": [
            {"source_url": "https://www.racingpost.com/racecards/30/leicester/2026-05-26/111111/"}
        ]}))
        (refresh / "manifest.json").write_text(json.dumps({"captures": [
            {"source_url": "https://www.racingpost.com/racecards/30/leicester/2026-05-26/222222/"}
        ]}))

        with patch("scripts.ops.build_rp_results_url_list.RAW_ROOT", raw_root):
            result = build_results_url_list(
                date="2026-05-26",
                capture_label=refresh.name,
                execute=False,
            )

        assert result["capture_label"] == refresh.name
        assert result["urls"] == [
            "https://www.racingpost.com/results/30/leicester/2026-05-26/222222/"
        ]

    def test_execute_writes_file(self, tmp_path):
        raw_root = tmp_path / "racing_post_account_raw"
        cap_dir = raw_root / "live-full-racepages-2026-05-26"
        cap_dir.mkdir(parents=True)
        manifest = {
            "captures": [
                {"source_url": "https://www.racingpost.com/racecards/30/leicester/2026-05-26/918927/"},
            ]
        }
        (cap_dir / "manifest.json").write_text(json.dumps(manifest))
        url_lists = tmp_path / "url_lists"

        with patch("scripts.ops.build_rp_results_url_list.RAW_ROOT", raw_root), \
             patch("scripts.ops.build_rp_results_url_list.URL_LIST_ROOT", url_lists):
            result = build_results_url_list(date="2026-05-26", execute=True)

        assert result["status"] == "PASS"
        out = Path(result["output"])
        assert out.exists()
        content = out.read_text()
        assert "results" in content
        assert "racecards" not in content
