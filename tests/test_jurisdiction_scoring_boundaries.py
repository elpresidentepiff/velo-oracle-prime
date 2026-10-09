from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ops import build_rpdc_daily, new_build_two_lane_score
from src.velo.jurisdiction import (
    is_uk_ire_race,
    resolve_race_jurisdiction,
)
from src.velo.racecard_cache_gate import _is_uk_ire as cache_is_uk_ire
from workers.racing_api_normalizer import normalize_race

FOREIGN_2026_10_09 = {"930772", "930773", "930784"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("GB", "GB"),
        ("GBR", "GB"),
        ("UK", "GB"),
        ("IE", "IRE"),
        ("IRL", "IRE"),
        ("IRE", "IRE"),
        ("IRELAND", "IRE"),
    ],
)
def test_shared_resolver_accepts_all_governed_aliases(raw: str, expected: str) -> None:
    assert resolve_race_jurisdiction({"region": raw}) == expected
    assert resolve_race_jurisdiction({"country": raw.lower()}) == expected


@pytest.mark.parametrize(
    ("region", "country", "expected_code", "expected_normalized"),
    [
        ("GB", "GBR", "GB", "uk"),
        ("IRE", "IE", "IRE", "ire"),
        ("FR", "", "FR", "other"),
        ("", "", "", "unknown"),
        ("GB", "FR", "", "unknown"),
        ("FR", "GB", "", "unknown"),
        ("IRE", "GB", "", "unknown"),
        ("GB", "IRE", "", "unknown"),
    ],
)
def test_shared_and_main_normalizer_fail_closed_on_conflicts(
    region: str,
    country: str,
    expected_code: str,
    expected_normalized: str,
) -> None:
    raw = {"race_id": "100", "region": region, "country": country}

    assert resolve_race_jurisdiction(raw) == expected_code
    assert normalize_race(raw)["jurisdiction"] == expected_normalized


@pytest.mark.parametrize(
    ("region", "country", "expected"),
    [
        ("GBR", "", True),
        ("", "UK", True),
        ("IRL", "", True),
        ("", "IRELAND", True),
        ("FR", "", False),
        ("", "", False),
        ("GB", "FR", False),
        ("FR", "GB", False),
    ],
)
def test_cache_gate_uses_same_fail_closed_contract(region: str, country: str, expected: bool) -> None:
    race = {"region": region, "country": country}

    assert is_uk_ire_race(race) is expected
    assert cache_is_uk_ire(race) is expected


def _race(race_id: str, country: str = "", region: str = "") -> dict:
    return {
        "race_id": race_id,
        "course": f"Course {race_id}",
        "country": country,
        "region": region,
        "velo_scoring_allowed": False,
        "runners": [
            {"horse_id": f"{race_id}01", "horse": f"Horse {race_id}"},
        ],
    }


def _write_injection(path: Path, races: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"races": races}), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("country", "region", "expected"),
    [
        ("GB", "", True),
        ("", "IRE", True),
        ("gbr", "", True),
        ("UK", "", True),
        ("ie", "", True),
        ("IRL", "", True),
        ("IRELAND", "", True),
        ("FR", "", False),
        ("", "", False),
        ("GB", "FR", False),
        ("FR", "GB", False),
    ],
)
def test_rpdc_release_boundary_is_uk_ire_only(tmp_path: Path, country: str, region: str, expected: bool) -> None:
    path = _write_injection(
        tmp_path / "racecard_injection.json",
        [
            _race("100", country=country, region=region),
        ],
    )

    runners, race_ids = build_rpdc_daily._load_injection_runners(path)

    assert bool(runners) is expected
    assert bool(race_ids) is expected


def test_new_build_scoring_boundary_uses_authoritative_race_metadata(
    tmp_path: Path,
) -> None:
    path = _write_injection(
        tmp_path / "racecard_injection.json",
        [
            _race("100", country="GB"),
            _race("101", region="IRE"),
            _race("102", country="FR"),
            _race("103"),
        ],
    )
    rows = [
        {
            "race_date": "2026-10-09",
            "race_id": race_id,
            "velo_scoring_allowed": False,
        }
        for race_id in ("100", "101", "102", "103")
    ]

    filtered = new_build_two_lane_score._filter_scoring_rows(rows, "2026-10-09", path)

    assert {row["race_id"] for row in filtered} == {"100", "101"}


def test_rpdc_new_build_cache_and_main_have_identical_boundary_decisions(
    tmp_path: Path,
) -> None:
    races = [
        _race("100", region="GBR"),
        _race("101", country="IRELAND"),
        _race("102", country="FR"),
        _race("103"),
        _race("104", region="GB", country="FR"),
        _race("105", region="FR", country="GB"),
    ]
    path = _write_injection(tmp_path / "racecard_injection.json", races)
    rows = [{"race_date": "2026-10-09", "race_id": race["race_id"]} for race in races]

    _, rpdc_ids = build_rpdc_daily._load_injection_runners(path)
    new_build_ids = {row["race_id"] for row in new_build_two_lane_score._filter_scoring_rows(rows, "2026-10-09", path)}
    cache_ids = {race["race_id"] for race in races if cache_is_uk_ire(race)}
    main_ids = {race["race_id"] for race in races if normalize_race(race)["jurisdiction"] in {"uk", "ire"}}

    assert rpdc_ids == new_build_ids == cache_ids == main_ids == {"100", "101"}


def test_2026_10_09_artifacts_prove_exact_47_race_universe() -> None:
    injection_path = new_build_two_lane_score.PARSED_ROOT / "2026-10-09" / "racecard_injection.json"
    feed_path = new_build_two_lane_score.FEED_JSONL
    if not injection_path.exists() or not feed_path.exists():
        pytest.skip("2026-10-09 operational proof artifacts are not present")

    runners, rpdc_race_ids = build_rpdc_daily._load_injection_runners(injection_path)
    feed_rows = new_build_two_lane_score._read_jsonl(feed_path)
    scoring_rows = new_build_two_lane_score._filter_scoring_rows(feed_rows, "2026-10-09", injection_path)
    scoring_race_ids = {str(row.get("race_id")) for row in scoring_rows}

    assert runners
    assert len(rpdc_race_ids) == 47
    assert len(scoring_race_ids) == 47
    assert rpdc_race_ids == scoring_race_ids
    assert not (FOREIGN_2026_10_09 & rpdc_race_ids)
    assert not (FOREIGN_2026_10_09 & scoring_race_ids)
