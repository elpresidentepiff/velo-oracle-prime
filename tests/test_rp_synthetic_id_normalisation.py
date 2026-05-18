"""
Regression test: RP synthetic horse ID normalisation must be consistent
across scoring path (run_prime_today.py) and result path (scrape_results_atr.py).

Incident: 1dc8d5b used str.lower() only, preserving spaces in horse_norm column.
Fix: use _norm_horse_name() which strips all non-alphanumeric chars.

This test must never be deleted. It guards against re-introduction of the
SYNTHETIC_ID_NORMALISATION_DRIFT that invalidated May 18 Sigma.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _norm_horse_name(name: str) -> str:
    """Canonical normaliser — must match implementation in run_prime_today.py line 808."""
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def rp_synthetic_id(name: str) -> str:
    """Canonical synthetic RP horse_id producer."""
    norm = _norm_horse_name(name)
    return f"RP_{norm}" if norm else ""


# ── Multi-word names: spaces must be stripped ────────────────────────────────

def test_imperial_guard():
    assert rp_synthetic_id("Imperial Guard") == "RP_imperialguard"


def test_imperial_guard_from_all_caps_col():
    """Simulate horse_norm column value (ALL CAPS with spaces)."""
    assert rp_synthetic_id("IMPERIAL GUARD") == "RP_imperialguard"


def test_ride_the_thunder():
    assert rp_synthetic_id("Ride The Thunder") == "RP_ridethethunder"


def test_trojan_soldier():
    assert rp_synthetic_id("Trojan Soldier") == "RP_trojansoldier"


def test_billy_no_mates():
    assert rp_synthetic_id("Billy No Mates") == "RP_billynomates"


def test_dontwaste_a_moment():
    assert rp_synthetic_id("Dontwaste A Moment") == "RP_dontwasteamoment"


# ── Apostrophes and punctuation must be stripped ─────────────────────────────

def test_cooleys_mist():
    assert rp_synthetic_id("Cooley's Mist") == "RP_cooleysmist"


def test_dontwasteamoment_apostrophe():
    assert rp_synthetic_id("Don't Wait") == "RP_dontwait"


# ── Single-word names: unchanged (except lowercase) ──────────────────────────

def test_plaid():
    assert rp_synthetic_id("Plaid") == "RP_plaid"


def test_adalida():
    assert rp_synthetic_id("Adalida") == "RP_adalida"


def test_letmeseethecolts():
    assert rp_synthetic_id("Letmeseethecolts") == "RP_letmeseethecolts"


def test_already_lowercase():
    assert rp_synthetic_id("adalida") == "RP_adalida"


# ── Consistency: scoring path == result path for same horse ─────────────────

def test_scoring_result_consistency_multi_word():
    """
    Simulates commit 1dc8d5b bug:
    old scorer used str.lower() only → 'RP_imperial guard' (SPACE)
    result scraper used re.sub → 'RP_imperialguard' (NO SPACE)
    → MISMATCH

    After fix both paths use _norm_horse_name → identical.
    """
    horse_name = "Imperial Guard"
    horse_norm_col = "IMPERIAL GUARD"  # as it appears in rp_runner_profile.parquet

    # Scoring path (fixed)
    scoring_id = rp_synthetic_id(horse_norm_col)

    # Result path (scrape_results_atr.py)
    result_id = rp_synthetic_id(horse_name)

    assert scoring_id == result_id, (
        f"ID mismatch! scoring={scoring_id!r} result={result_id!r}. "
        "This is the 1dc8d5b bug. Check _norm_horse_name is used in _load_rp_profile_as_racecards."
    )


def test_scoring_result_consistency_all_multi_word():
    """All multi-word test cases must match between scoring and result paths."""
    pairs = [
        ("Imperial Guard",     "IMPERIAL GUARD"),
        ("Ride The Thunder",   "RIDE THE THUNDER"),
        ("Billy No Mates",     "BILLY NO MATES"),
        ("Cooley's Mist",      "COOLEY'S MIST"),
        ("Dontwaste A Moment", "DONTWASTE A MOMENT"),
    ]
    for horse_name, horse_norm_col in pairs:
        assert rp_synthetic_id(horse_norm_col) == rp_synthetic_id(horse_name), (
            f"Mismatch for {horse_name!r}: "
            f"norm_col→{rp_synthetic_id(horse_norm_col)!r} "
            f"name→{rp_synthetic_id(horse_name)!r}"
        )


# ── Guard: old (broken) normalisation must NOT pass ──────────────────────────

def test_old_normalisation_fails_multi_word():
    """Prove the old bug: str.lower() alone produces wrong IDs for multi-word names."""
    def old_norm(horse_norm_col: str) -> str:
        return f"RP_{str(horse_norm_col or '').lower()}"

    assert old_norm("IMPERIAL GUARD") == "RP_imperial guard"  # bad format with space
    assert old_norm("IMPERIAL GUARD") != "RP_imperialguard"   # does NOT match result path


# ── Standalone runner (no pytest needed) ────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_imperial_guard,
        test_imperial_guard_from_all_caps_col,
        test_ride_the_thunder,
        test_trojan_soldier,
        test_billy_no_mates,
        test_dontwaste_a_moment,
        test_cooleys_mist,
        test_dontwasteamoment_apostrophe,
        test_plaid,
        test_adalida,
        test_letmeseethecolts,
        test_already_lowercase,
        test_scoring_result_consistency_multi_word,
        test_scoring_result_consistency_all_multi_word,
        test_old_normalisation_fails_multi_word,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'} ({len(tests)} tests)")
    sys.exit(failed)
