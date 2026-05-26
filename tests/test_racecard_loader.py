"""
Tests for Issue #83 — VÉLØ Racecard Loader source contract fix.

Validates:
  - cache source wins before API call
  - RP merged source works when Racing API creds absent
  - VELO_DISABLE_RACING_API=1 prevents API call
  - API 401 fails clearly when no local source exists
  - load_rp_merged_as_racecards: synthesises races with region and runners
  - Irish venues get region=IRE; GB venues get region=GB
  - Explicit --source cache / rp / api flags behave correctly
"""

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.velo.racecard_loader import (  # noqa: E402
    load_racecards,
    load_rp_merged_as_racecards,
)

_DATE_STR = "2026-05-20"
_DATE_TAG = "2026_05_20"

_RP_MERGED_SAMPLE = {
    "venue": "Yarmouth",
    "date": _DATE_STR,
    "generated_at": "2026-05-20T06:00:00Z",
    "races": {
        "14:00": {
            "race_info": "5f Class 4",
            "horses": [
                {"horse_name": "Alpha Star", "ts_latest": 72, "ts_base": 70, "plot_conviction": 0.8},
                {"horse_name": "Beta Wind", "ts_latest": 68, "ts_base": 65, "plot_conviction": 0.3},
            ],
        },
        "14:30": {
            "race_info": "1m Class 3",
            "horses": [
                {"horse_name": "Gamma Ray", "ts_latest": 80, "ts_base": 78, "plot_conviction": 0.9},
            ],
        },
    },
}

_CACHE_RACES = [
    {"race_id": "rac_cache_001", "course": "Ascot", "off_time": "14:00", "runners": [{"horse": "Cache Horse"}]},
]


def _make_rp_file(tmp_path, venue_code="YAR", content=None):
    merged_dir = tmp_path / "racecard_merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    content = content or _RP_MERGED_SAMPLE
    (merged_dir / f"racecard_{venue_code}_{_DATE_STR}.json").write_text(json.dumps(content))
    return tmp_path


def _make_cache_file(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / f"racecards_{_DATE_TAG}_standard.json").write_text(json.dumps(_CACHE_RACES))
    return tmp_path


def _loader(tmp_path, source=None, disable_api=False):
    env = {"VELO_RACECARD_SOURCE": "auto"}
    if disable_api:
        env["VELO_DISABLE_RACING_API"] = "1"
    with patch.dict("os.environ", env, clear=False):
        return load_racecards(
            date_tag=_DATE_TAG,
            date_str=_DATE_STR,
            data_root=tmp_path,
            racing_base="https://api.example.com",
            racing_user="testuser",
            racing_pass="testpass",
            source=source,
        )


# ── Cache wins before API ─────────────────────────────────────────────────────


def test_cache_wins_before_api(tmp_path):
    _make_cache_file(tmp_path)
    # API should NOT be called — cache exists
    with patch("src.velo.racecard_loader.fetch_api_racecards") as mock_api:
        races, src = _loader(tmp_path)
    assert src == "cache"
    mock_api.assert_not_called()


def test_cache_wins_before_rp(tmp_path):
    _make_cache_file(tmp_path)
    _make_rp_file(tmp_path)
    races, src = _loader(tmp_path)
    assert src == "cache"
    # Sanitization adds rpr_policy + rp_rpr_velo_allowed — check identity fields only
    assert len(races) == len(_CACHE_RACES)
    assert races[0]["race_id"] == _CACHE_RACES[0]["race_id"]
    assert races[0]["course"] == _CACHE_RACES[0]["course"]


# ── RP merged source ──────────────────────────────────────────────────────────


def test_rp_source_works_without_api_creds(tmp_path):
    _make_rp_file(tmp_path)
    races, src = load_racecards(
        date_tag=_DATE_TAG,
        date_str=_DATE_STR,
        data_root=tmp_path,
        racing_base="https://api.example.com",
        racing_user="",
        racing_pass="",
        source="rp",
    )
    assert src == "rp_merged"
    assert len(races) == 2  # 2 race times in sample


def test_auto_falls_to_rp_when_no_cache(tmp_path):
    _make_rp_file(tmp_path)
    races, src = _loader(tmp_path)
    assert src == "rp_merged"
    assert len(races) == 2


def test_rp_merged_synthesises_runners(tmp_path):
    _make_rp_file(tmp_path)
    races = load_rp_merged_as_racecards(_DATE_STR, tmp_path)
    runners_total = sum(len(r["runners"]) for r in races)
    assert runners_total == 3  # 2 + 1 from sample


def test_rp_merged_empty_when_no_files(tmp_path):
    races = load_rp_merged_as_racecards(_DATE_STR, tmp_path)
    assert races == []


# ── Region / jurisdiction ─────────────────────────────────────────────────────


def test_gb_venue_gets_gb_region(tmp_path):
    _make_rp_file(tmp_path, venue_code="YAR")
    races = load_rp_merged_as_racecards(_DATE_STR, tmp_path)
    for race in races:
        assert race["region"] == "GB", f"Expected GB, got {race['region']}"


def test_ire_venue_gets_ire_region(tmp_path):
    ire_content = {**_RP_MERGED_SAMPLE, "venue": "Gowran Park"}
    _make_rp_file(tmp_path, venue_code="GOW", content=ire_content)
    races = load_rp_merged_as_racecards(_DATE_STR, tmp_path)
    for race in races:
        assert race["region"] == "IRE", f"Expected IRE, got {race['region']}"


def test_rp_runners_have_horse_name(tmp_path):
    _make_rp_file(tmp_path)
    races = load_rp_merged_as_racecards(_DATE_STR, tmp_path)
    names = [r["horse"] for race in races for r in race["runners"]]
    assert "Alpha Star" in names
    assert "Beta Wind" in names
    assert "Gamma Ray" in names


# ── VELO_DISABLE_RACING_API ───────────────────────────────────────────────────


def test_disable_api_prevents_api_call_when_rp_exists(tmp_path):
    _make_rp_file(tmp_path)
    with patch("src.velo.racecard_loader.fetch_api_racecards") as mock_api:
        races, src = _loader(tmp_path, disable_api=True)
    assert src == "rp_merged"
    mock_api.assert_not_called()


def test_disable_api_raises_when_no_local_source(tmp_path):
    import pytest
    with pytest.raises(RuntimeError, match="VELO_DISABLE_RACING_API"):
        _loader(tmp_path, disable_api=True)


# ── API 401 handling ──────────────────────────────────────────────────────────


def test_api_401_raises_clearly_when_no_local_source(tmp_path):
    import pytest
    http_err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(RuntimeError, match="401"):
            load_racecards(
                date_tag=_DATE_TAG,
                date_str=_DATE_STR,
                data_root=tmp_path,
                racing_base="https://api.example.com",
                racing_user="user",
                racing_pass="pass",
            )


def test_api_not_called_when_rp_exists_in_auto(tmp_path):
    _make_rp_file(tmp_path)
    http_err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)
    with patch("urllib.request.urlopen", side_effect=http_err):
        # Should use RP merged, never reach the API
        races, src = _loader(tmp_path)
    assert src == "rp_merged"


# ── Explicit source flags ─────────────────────────────────────────────────────


def test_explicit_source_cache_fails_clearly_when_absent(tmp_path):
    import pytest
    with pytest.raises(RuntimeError, match="cache"):
        load_racecards(
            date_tag=_DATE_TAG,
            date_str=_DATE_STR,
            data_root=tmp_path,
            racing_base="https://api.example.com",
            racing_user="user",
            racing_pass="pass",
            source="cache",
        )


def test_explicit_source_rp_fails_clearly_when_absent(tmp_path):
    import pytest
    with pytest.raises(RuntimeError, match="rp"):
        load_racecards(
            date_tag=_DATE_TAG,
            date_str=_DATE_STR,
            data_root=tmp_path,
            racing_base="https://api.example.com",
            racing_user="user",
            racing_pass="pass",
            source="rp",
        )


# ── RPR sanitization ──────────────────────────────────────────────────────────

from src.velo.racecard_loader import _sanitize_api_rpr  # noqa: E402

_CACHE_WITH_RPR = [
    {
        "race_id": "r1",
        "course": "Ascot",
        "date": _DATE_STR,
        "region": "GB",
        "runners": [
            {"horse": "Alpha", "horse_id": "1", "rpr": 105, "jockey": "J", "trainer": "T"},
            {"horse": "Beta",  "horse_id": "2", "rpr": 98,  "jockey": "J", "trainer": "T"},
            {"horse": "Gamma", "horse_id": "3", "rpr": None, "jockey": "J", "trainer": "T"},
        ],
    }
]


def test_cache_source_sanitizes_rpr(tmp_path):
    """Cache-sourced runners must have rpr nulled and archived."""
    cache_races = [
        {**r, "runners": [dict(run) for run in r["runners"]]}
        for r in _CACHE_WITH_RPR
    ]
    (tmp_path / f"racecards_{_DATE_TAG}_standard.json").write_text(
        json.dumps(cache_races)
    )
    races, src = _loader(tmp_path, source="cache")
    assert src == "cache"
    runner = races[0]["runners"][0]
    assert runner["rpr"] is None, "rpr must be nulled after sanitization"
    assert runner["rp_rpr_archive_only"] == 105, "live rpr must be archived"
    assert runner["rp_rpr_velo_allowed"] is False


def test_rp_merged_source_not_sanitized(tmp_path):
    """RP-merged runners must not be modified by the sanitization step."""
    _make_rp_file(tmp_path)
    races, src = _loader(tmp_path, source="rp")
    assert src == "rp_merged"
    # RP merged runners have no 'rpr' key at all — sanitizer must not touch them
    for race in races:
        for runner in race["runners"]:
            assert "rpr" not in runner or runner.get("rpr") is None


def test_sanitize_api_rpr_direct():
    """_sanitize_api_rpr moves live rpr to archive, nulls scoring field."""
    import copy
    races = copy.deepcopy(_CACHE_WITH_RPR)
    result = _sanitize_api_rpr(races)
    r0, r1, r2 = result[0]["runners"]
    assert r0["rpr"] is None
    assert r0["rp_rpr_archive_only"] == 105
    assert r0["rp_rpr_velo_allowed"] is False
    assert r1["rp_rpr_archive_only"] == 98
    assert r2["rpr"] is None  # was already None — must stay None


def test_sanitize_does_not_overwrite_existing_archive_value():
    """If rp_rpr_archive_only is already set, it must not be overwritten."""
    import copy
    races = copy.deepcopy(_CACHE_WITH_RPR)
    races[0]["runners"][0]["rp_rpr_archive_only"] = 999  # pre-existing value
    result = _sanitize_api_rpr(races)
    assert result[0]["runners"][0]["rp_rpr_archive_only"] == 999


def test_allow_api_rpr_env_skips_sanitization(tmp_path):
    """VELO_ALLOW_API_RPR=1 must bypass RPR sanitization entirely."""
    import copy
    races = copy.deepcopy(_CACHE_WITH_RPR)
    with patch.dict("os.environ", {"VELO_ALLOW_API_RPR": "1"}):
        result = _sanitize_api_rpr(races)
    assert result[0]["runners"][0]["rpr"] == 105  # unchanged
