"""Regression test for UK/IRE venue slug classification in the RP racecard URL list builder.

southwell-aw (Southwell's all-weather fixture slug) was missing from UK_IRE_VENUES,
causing today's Southwell meeting to be misclassified as international and dropped
from the UK/IRE racecard URL list on 2026-07-05.

The identical class of bug recurred one day later on 2026-07-06: lingfield-aw,
lingfield-aw-gb, and wolverhampton-aw were also missing from UK_IRE_VENUES,
silently routing 15 real UK races into the "international, not fed to VELO" file.
This is a live race-universe correctness bug, not a one-off scrape issue --
every downstream stage (passports, scoring, Sigma, dashboard, learning) depends
on the race universe being complete before anything else runs.
"""
import json
from pathlib import Path

import pytest

from scripts.ops.build_racing_post_racecard_url_list import (
    UK_IRE_VENUES,
    _venue_slug_from_url,
    build_racecard_urls,
)

ROOT = Path(__file__).resolve().parents[1]


def test_southwell_aw_is_classified_uk_ire():
    assert "southwell-aw" in UK_IRE_VENUES


def test_southwell_aw_url_extracts_matching_slug():
    url = "https://www.racingpost.com/racecards/394/southwell-aw/2026-07-05/921916"
    slug = _venue_slug_from_url(url)
    assert slug is not None
    assert slug.lower() in UK_IRE_VENUES


def test_lingfield_aw_is_classified_uk_ire():
    assert "lingfield-aw" in UK_IRE_VENUES


def test_lingfield_aw_gb_is_classified_uk_ire():
    assert "lingfield-aw-gb" in UK_IRE_VENUES


def test_wolverhampton_aw_is_classified_uk_ire():
    assert "wolverhampton-aw" in UK_IRE_VENUES


def test_lingfield_aw_url_extracts_matching_slug():
    url = "https://www.racingpost.com/racecards/393/lingfield-aw/2026-07-06/922456"
    slug = _venue_slug_from_url(url)
    assert slug is not None
    assert slug.lower() in UK_IRE_VENUES


def test_lingfield_aw_gb_url_extracts_matching_slug():
    url = "https://www.racingpost.com/racecards/1321/lingfield-aw-gb/2026-07-06/924398"
    slug = _venue_slug_from_url(url)
    assert slug is not None
    assert slug.lower() in UK_IRE_VENUES


def test_wolverhampton_aw_url_extracts_matching_slug():
    url = "https://www.racingpost.com/racecards/513/wolverhampton-aw/2026-07-06/922462"
    slug = _venue_slug_from_url(url)
    assert slug is not None
    assert slug.lower() in UK_IRE_VENUES


def test_no_known_aw_track_missing_its_aw_variant():
    """Guard against this exact bug class recurring: every known all-weather
    track's -aw slug must be present in the allowlist alongside its turf slug."""
    known_aw_tracks = {"kempton", "newcastle", "southwell", "lingfield", "wolverhampton"}
    for track in known_aw_tracks:
        assert track in UK_IRE_VENUES, f"{track} missing from UK_IRE_VENUES"
        assert f"{track}-aw" in UK_IRE_VENUES, f"{track}-aw missing from UK_IRE_VENUES"


def test_dundalk_aw_is_classified_uk_ire():
    """Same bug class, third occurrence: Dundalk-AW was missing from
    UK_IRE_VENUES (only "dundalk" was present, not the actual "dundalk-aw"
    slug RP uses), silently dropping the entire Dundalk-AW card from the
    UK/IRE URL list on 2026-07-12 until an operator manually recovered it."""
    assert "dundalk-aw" in UK_IRE_VENUES
    url = "https://www.racingpost.com/racecards/1138/dundalk-aw/2026-07-12/924518"
    slug = _venue_slug_from_url(url)
    assert slug is not None
    assert slug.lower() in UK_IRE_VENUES


def test_newton_abbot_is_classified_uk_ire():
    """Same bug class, fourth occurrence: Newton Abbot (an English course)
    was entirely absent from UK_IRE_VENUES, silently dropping its card on
    2026-07-13 until an operator manually recovered it."""
    assert "newton-abbot" in UK_IRE_VENUES
    url = "https://www.racingpost.com/racecards/39/newton-abbot/2026-07-13/922979"
    slug = _venue_slug_from_url(url)
    assert slug is not None
    assert slug.lower() in UK_IRE_VENUES


def test_aintree_is_classified_uk_ire():
    """Aintree (Grand National course) was also absent from UK_IRE_VENUES --
    caught during the Newton Abbot fix audit, fixed proactively before it
    could cause a live incident."""
    assert "aintree" in UK_IRE_VENUES


def test_run_full_raceday_captures_intl_list_as_safety_net():
    """Architectural fix, not another allowlist patch: this exact class of
    bug (a genuine UK/IRE course missing from UK_IRE_VENUES, silently
    dropped from the day's card) has now recurred four times. Patching the
    allowlist each time it's caught does not prevent the *next* unknown
    venue from being silently dropped. run_full_raceday.py must therefore
    also capture the "_intl" URL list as a supplementary batch, so nothing
    RP shows for the date is silently lost before the real, independent
    per-race jurisdiction check (workers/racing_api_normalizer.py, keyed
    off each race's own RP-supplied country field) decides inclusion."""
    script_path = ROOT / "scripts" / "ops" / "run_full_raceday.py"
    source = script_path.read_text(encoding="utf-8")
    assert "_intl.txt" in source, (
        "run_full_raceday.py no longer references the _intl URL list -- "
        "the supplementary capture safety net appears to have been removed"
    )
    assert "Step 3.5" in source, (
        "run_full_raceday.py no longer has a Step 3.5 supplementary capture step"
    )


JULY06_INDEX_CAPTURE_DATE = "index-2026-07-06-FINAL"
JULY06_INJECTION_PATH = (
    ROOT / "data" / "racing_post_account_parsed" / "live-full-racepages-2026-07-06" / "racecard_injection.json"
)
JULY06_STANDARD_CACHE_PATH = ROOT / "data" / "racecards_2026_07_06_standard.json"


def _july06_index_available() -> bool:
    return (ROOT / "data" / "racing_post_account_raw" / JULY06_INDEX_CAPTURE_DATE).exists()


def test_july06_universe_rebuild_recovers_all_36_races(tmp_path):
    """Full regression proof: rebuilding the July 06 UK/IRE URL list from the
    already-captured index HTML must now produce 36 races across 5 physical
    venues (6 course entries, since Lingfield's two fixture IDs are counted
    separately), with an empty international bucket -- not 21 races / 3 tracks."""
    if not _july06_index_available():
        pytest.skip("July 06 index capture not present in this environment")

    scratch_dir = ROOT / "data" / "racing_post_url_lists" / "_test_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    output = scratch_dir / "rp_racecards_2026-07-06_test.txt"
    try:
        result = build_racecard_urls(
            capture_date=JULY06_INDEX_CAPTURE_DATE,
            target_date="2026-07-06",
            output=output,
            execute=True,
        )

        assert result["uk_ire_url_count"] == 36
        assert result["international_url_count"] == 0

        lines = output.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 36

        slugs = {_venue_slug_from_url(u) for u in lines}
        assert slugs == {"ayr", "ripon", "roscommon", "lingfield-aw", "lingfield-aw-gb", "wolverhampton-aw"}
    finally:
        for f in scratch_dir.glob("*"):
            f.unlink()
        scratch_dir.rmdir()


def test_july06_injection_has_36_races_zero_skipped():
    if not JULY06_INJECTION_PATH.exists():
        pytest.skip("July 06 injection file not present in this environment")
    data = json.loads(JULY06_INJECTION_PATH.read_text(encoding="utf-8"))
    assert data["races_count"] == 36
    assert data["skipped_count"] == 0


def test_july06_standard_cache_has_405_active_runners():
    if not JULY06_STANDARD_CACHE_PATH.exists():
        pytest.skip("July 06 standard cache not present in this environment")
    data = json.loads(JULY06_STANDARD_CACHE_PATH.read_text(encoding="utf-8"))
    races = data if isinstance(data, list) else data.get("races", [])
    assert len(races) == 36
    total_runners = sum(len(r.get("runners", [])) for r in races)
    assert total_runners == 405
