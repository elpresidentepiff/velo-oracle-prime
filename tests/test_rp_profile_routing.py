from pathlib import Path

from scripts.ops import check_rp_session_health
from scripts.ops import fetch_rp_meeting_pdfs
from scripts.ops import racing_post_account_collector
from scripts.ops import run_full_raceday
from scripts.ops import run_full_raceday_eod


def test_all_rp_runtime_consumers_share_the_verified_firefox_profile() -> None:
    expected = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "browser_profiles"
        / "racing_post_account_firefox"
    )

    assert racing_post_account_collector.DEFAULT_PROFILE_DIR == expected
    assert check_rp_session_health.DEFAULT_PROFILE_DIR == expected
    assert fetch_rp_meeting_pdfs.DEFAULT_PROFILE_DIR == expected
    assert run_full_raceday.FIREFOX_PROFILE == expected
    assert run_full_raceday_eod.FIREFOX_PROFILE == expected
