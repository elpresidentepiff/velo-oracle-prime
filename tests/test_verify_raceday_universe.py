import json
from pathlib import Path

import pytest

import scripts.ops.verify_raceday_universe as verifier


DATE = "2099-09-29"
SLUG = "2099_09_29"
REAL_DATE = "2026-09-29"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _injection_payload(ids: list[str]) -> dict:
    return {"races": [{"race_id": race_id} for race_id in ids]}


def _status_row(race_id: str, *, authenticated: bool = True) -> dict:
    evidence = {
        "source_name": "official results summary",
        "source_url": "https://example.test/results",
        "observed_at": "2026-09-30T09:00:00+01:00",
    }
    if not authenticated:
        evidence["source_url"] = "/results"
    return {
        "race_id": race_id,
        "course": "Cork",
        "off": "3.55",
        "race_status": "ABANDONED",
        "race_status_evidence": evidence,
    }


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(verifier, "DATA", tmp_path)
    return tmp_path


def test_resolves_dated_injection_layout(data_root: Path) -> None:
    expected = data_root / "racing_post_account_parsed" / DATE / "racecard_injection.json"
    _write(expected, _injection_payload(["1"]))
    assert verifier._resolve_injection_path(DATE) == expected


def test_resolves_legacy_live_full_racepages_layout(data_root: Path) -> None:
    expected = data_root / "racing_post_account_parsed" / f"live-full-racepages-{DATE}" / "racecard_injection.json"
    _write(expected, _injection_payload(["1"]))
    assert verifier._resolve_injection_path(DATE) == expected


def test_multiple_supported_injection_layouts_fail_closed(data_root: Path) -> None:
    _write(data_root / "racing_post_account_parsed" / DATE / "racecard_injection.json", _injection_payload(["1"]))
    _write(
        data_root / "racing_post_account_parsed" / f"live-full-racepages-{DATE}" / "racecard_injection.json",
        _injection_payload(["1"]),
    )
    with pytest.raises(ValueError, match="ambiguous RP injection artifacts"):
        verifier._resolve_injection_path(DATE)


def test_conflicting_supported_injection_layouts_fail_closed(data_root: Path) -> None:
    _write(data_root / "racing_post_account_parsed" / DATE / "racecard_injection.json", _injection_payload(["1"]))
    _write(
        data_root / "racing_post_account_parsed" / f"live-full-racepages-{DATE}" / "racecard_injection.json",
        _injection_payload(["2"]),
    )
    with pytest.raises(ValueError, match="ambiguous RP injection artifacts"):
        verifier._resolve_injection_path(DATE)


def test_results_account_for_35_run_and_4_governed_abandoned(data_root: Path) -> None:
    run_ids = [str(i) for i in range(1, 36)]
    abandoned_ids = [str(i) for i in range(36, 40)]
    _write(data_root / "results" / f"rp_results_{SLUG}.json", {"results": [{"race_id": i} for i in run_ids]})
    _write(
        data_root / "results" / f"race_status_{SLUG}.json",
        {
            "date": DATE,
            "contract": "GOVERNED_RACE_STATUS_V1",
            "races": [_status_row(i) for i in abandoned_ids],
        },
    )
    assert verifier._race_ids_from_results(DATE) == set(run_ids + abandoned_ids)


def test_unauthenticated_void_status_fails_closed(data_root: Path) -> None:
    _write(data_root / "results" / f"rp_results_{SLUG}.json", {"results": [{"race_id": "1"}]})
    _write(
        data_root / "results" / f"race_status_{SLUG}.json",
        {
            "date": DATE,
            "contract": "GOVERNED_RACE_STATUS_V1",
            "races": [_status_row("2", authenticated=False)],
        },
    )
    with pytest.raises(ValueError, match="invalid or unauthoritative"):
        verifier._race_ids_from_results(DATE)


def test_missing_results_fail_when_results_are_required(data_root: Path) -> None:
    _write(data_root / "racing_post_account_parsed" / DATE / "racecard_injection.json", _injection_payload(["1"]))
    report = verifier.build_report(DATE, require_results=True)
    assert report["status"] == "FAIL"
    result_comparison = next(row for row in report["comparisons"] if row["name"] == "rp_results")
    assert result_comparison["required"] is True
    assert result_comparison["count"] == 0


def test_pre_results_mode_passes_on_prediction_universe(data_root: Path) -> None:
    _write(data_root / "racing_post_account_parsed" / DATE / "racecard_injection.json", _injection_payload(["1"]))
    report = verifier.build_report(DATE)
    assert report["status"] == "PASS"
    assert report["require_results"] is False


def test_status_only_all_abandoned_is_complete_when_results_required(data_root: Path) -> None:
    race_ids = ["1", "2"]
    _write(data_root / "racing_post_account_parsed" / DATE / "racecard_injection.json", _injection_payload(race_ids))
    _write(
        data_root / "results" / f"race_status_{SLUG}.json",
        {
            "date": DATE,
            "contract": "GOVERNED_RACE_STATUS_V1",
            "races": [_status_row(race_id) for race_id in race_ids],
        },
    )
    report = verifier.build_report(DATE, require_results=True)
    assert report["status"] == "PASS"
    assert report["sources"]["rp_results"] == race_ids


def test_complete_non_abandoned_results_pass_when_required(data_root: Path) -> None:
    race_ids = ["1", "2"]
    _write(data_root / "racing_post_account_parsed" / DATE / "racecard_injection.json", _injection_payload(race_ids))
    _write(data_root / "results" / f"rp_results_{SLUG}.json", {"results": [{"race_id": i} for i in race_ids]})
    assert verifier.build_report(DATE, require_results=True)["status"] == "PASS"


@pytest.mark.parametrize(
    "rows, message",
    [
        ([{"course": "York"}], "blank race_id"),
        ([{"race_id": "1"}, {"race_id": "1"}], "duplicate race_id"),
    ],
)
def test_malformed_or_duplicate_result_ids_fail_closed(data_root: Path, rows: list[dict], message: str) -> None:
    _write(data_root / "results" / f"rp_results_{SLUG}.json", {"results": rows})
    with pytest.raises(ValueError, match=message):
        verifier._race_ids_from_results(DATE)


def test_real_2026_09_29_universe_passes() -> None:
    report = verifier.build_report(REAL_DATE, require_results=True)
    assert report["status"] == "PASS"
    assert report["expected_count"] == 39
    assert len(report["sources"]["rp_results"]) == 39
