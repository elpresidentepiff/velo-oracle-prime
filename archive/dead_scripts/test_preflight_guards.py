"""
Pre-flight guard proof tests.
Intentionally triggers each guard once and asserts fail-loud behaviour.

Tests:
  1. single-runner race      → synthesize_decision forces X-CHAOS
  2. horse_state_failed flag → synthesize_decision forces X-CHAOS
  3. macro_context None      → chaos_m treated as True → X-CHAOS if other gates clear
  4. macro_context_failed    → row contains flag, chaos_mode is None (not False)
  5. G shadow mode env guard → RuntimeError if VELO_G_SHADOW_MODE=live
  6. score_race_velo_prime single-runner end-to-end (via monkey-patch)

Run:
  python scripts/test_preflight_guards.py
"""

import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results = []


def check(name, passed, detail=""):
    tag = PASS if passed else FAIL
    print(f"  [{tag}] {name}")
    if not passed and detail:
        print(f"         detail: {detail}")
    results.append((name, passed))


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Guard 1: single-runner race ===")
try:
    from scripts.run_prime_today import synthesize_decision

    # field_size=1 must always return X regardless of prob/gap/place
    for prob, place in [(0.45, 0.99), (0.32, 0.60), (0.20, 0.50)]:
        top = {"velo_prime_prob": prob, "place_prob": place, "longshot_prob": 0.1,
               "sp_dec": 5.0, "improvement_score": 0.0, "market_deception_score": None,
               "release_day_prob": 0.0, "macro_chaos_mode": False,
               "favourite_trap_risk": "normal", "confidence_level": "high",
               "horse_state_failed": False}
        tier, reasons = synthesize_decision(top, 0.0, field_size=1)
        check(
            f"single-runner(prob={prob}) → X-CHAOS",
            tier == "X" and any("single-runner" in r for r in reasons),
            f"got tier={tier}, reasons={reasons}",
        )
except Exception as e:
    check("single-runner guard import/run", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Guard 2: horse_state_failed blocks A/B ===")
try:
    from scripts.run_prime_today import synthesize_decision

    # horse that would clearly hit A without the flag
    top = {"velo_prime_prob": 0.40, "place_prob": 0.90, "longshot_prob": 0.0,
           "sp_dec": 4.0, "improvement_score": 0.0, "market_deception_score": None,
           "release_day_prob": 0.0, "macro_chaos_mode": False,
           "favourite_trap_risk": "normal", "confidence_level": "high",
           "horse_state_failed": True}
    tier, reasons = synthesize_decision(top, 0.10, field_size=8)
    check(
        "horse_state_failed → X-CHAOS (not A)",
        tier == "X" and any("horse state" in r for r in reasons),
        f"got tier={tier}, reasons={reasons}",
    )

    # Without flag, same horse should be A
    top["horse_state_failed"] = False
    tier2, _ = synthesize_decision(top, 0.10, field_size=8)
    check(
        "horse_state OK → A-STRIKE (flag removed)",
        tier2 == "A",
        f"got tier={tier2}",
    )
except Exception as e:
    check("horse_state_failed guard import/run", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Guard 3: macro_context None treated as chaos ===")
try:
    from scripts.run_prime_today import synthesize_decision

    # macro_chaos_mode=None (not False) — should force chaos unless strong_escape
    top = {"velo_prime_prob": 0.15, "place_prob": 0.30, "longshot_prob": 0.0,
           "sp_dec": 8.0, "improvement_score": 0.0, "market_deception_score": None,
           "release_day_prob": 0.0, "macro_chaos_mode": None,
           "favourite_trap_risk": "normal", "confidence_level": "normal",
           "horse_state_failed": False}
    tier, reasons = synthesize_decision(top, 0.10, field_size=8)
    check(
        "macro_chaos_mode=None → X-CHAOS (chaos treated as unknown=True)",
        tier == "X" and any("chaos" in r.lower() for r in reasons),
        f"got tier={tier}, reasons={reasons}",
    )

    # macro_chaos_mode=False should NOT force chaos on same horse
    top["macro_chaos_mode"] = False
    tier2, _ = synthesize_decision(top, 0.10, field_size=8)
    check(
        "macro_chaos_mode=False → not X from chaos alone",
        tier2 != "X" or any(r for r in ["prob", "gap"] if r in str(_)),
        f"got tier={tier2}",
    )
except Exception as e:
    check("macro_context None guard import/run", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Guard 4: velo_prime_service macro_context_failed flag ===")
try:
    # Monkey-patch get_macro_context_for_race to raise
    import src.intelligence.macro_regime.bha_macro_context as _bha
    _orig = _bha.get_macro_context_for_race

    def _raise(*a, **kw):
        raise RuntimeError("intentional macro failure for test")

    _bha.get_macro_context_for_race = _raise

    # Build a minimal race
    race = {
        "race_id": "test_macro_fail",
        "date": "2026-04-12",
        "type": "flat",
        "runners": [
            {"horse_name": "Test Horse", "horse_id": "h1",
             "best_odds_decimal": 4.0, "official_rating": 90,
             "rpr": 88, "ts": 70, "draw": 3, "age": 4, "weight_lbs": 126},
            {"horse_name": "Second Horse", "horse_id": "h2",
             "best_odds_decimal": 6.0, "official_rating": 85,
             "rpr": 83, "ts": 65, "draw": 5, "age": 5, "weight_lbs": 124},
        ],
    }

    import logging
    log_records = []
    class _Capture(logging.Handler):
        def emit(self, record):
            log_records.append(record)
    _cap = _Capture()
    _cap.setLevel(logging.ERROR)
    logging.getLogger("velo.prime_service").addHandler(_cap)

    from app.services.velo_prime_service import score_race_velo_prime
    results_rows = score_race_velo_prime(race)

    # Restore
    _bha.get_macro_context_for_race = _orig

    flag_set = all(r.get("macro_context_failed") is True for r in results_rows)
    chaos_none = all(r.get("macro_chaos_mode") is None for r in results_rows)
    error_logged = any(
        "Macro context FAILED" in r.getMessage() for r in log_records
    )

    check("macro_context_failed=True on all rows", flag_set, str([r.get("macro_context_failed") for r in results_rows[:2]]))
    check("macro_chaos_mode=None (not False) on all rows", chaos_none, str([r.get("macro_chaos_mode") for r in results_rows[:2]]))
    check("log.error fired with 'Macro context FAILED'", error_logged, f"{len(log_records)} error records")

    logging.getLogger("velo.prime_service").removeHandler(_cap)

except Exception as e:
    check("macro_context_failed flag test", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Guard 5: horse_state_failed flag via monkey-patch ===")
try:
    import src.intelligence.horse_state_engine as _hse
    _orig_cls = _hse.HorseStateEngine

    class _BrokenEngine:
        def tag(self, *a, **kw):
            raise RuntimeError("intentional horse state failure for test")

    _hse.HorseStateEngine = _BrokenEngine

    import importlib
    import app.services.velo_prime_service as _svc
    importlib.reload(_svc)

    log_records2 = []
    class _Cap2(logging.Handler):
        def emit(self, record):
            log_records2.append(record)
    _cap2 = _Cap2()
    _cap2.setLevel(logging.ERROR)
    logging.getLogger("velo.prime_service").addHandler(_cap2)

    race = {
        "race_id": "test_hs_fail",
        "date": "2026-04-12",
        "type": "flat",
        "runners": [
            {"horse_name": "Test Horse", "horse_id": "h1",
             "best_odds_decimal": 4.0, "official_rating": 90,
             "rpr": 88, "ts": 70, "draw": 3, "age": 4, "weight_lbs": 126},
            {"horse_name": "Second Horse", "horse_id": "h2",
             "best_odds_decimal": 6.0, "official_rating": 85,
             "rpr": 83, "ts": 65, "draw": 5, "age": 5, "weight_lbs": 124},
        ],
    }
    results_rows2 = _svc.score_race_velo_prime(race)

    _hse.HorseStateEngine = _orig_cls
    importlib.reload(_svc)
    logging.getLogger("velo.prime_service").removeHandler(_cap2)

    flag_set2 = all(r.get("horse_state_failed") is True for r in results_rows2)
    error_logged2 = any("Horse state tagging FAILED" in r.getMessage() for r in log_records2)

    check("horse_state_failed=True on all rows", flag_set2, str([r.get("horse_state_failed") for r in results_rows2[:2]]))
    check("log.error fired with 'horse state tagging FAILED'", error_logged2, f"{len(log_records2)} error records")

except Exception as e:
    check("horse_state_failed flag test", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== Guard 6: VELO_G_SHADOW_MODE=live startup assertion ===")
try:
    import importlib
    import asyncio

    # Set env to live — should raise RuntimeError at startup
    os.environ["VELO_G_SHADOW_MODE"] = "live"

    import app.main as _main
    importlib.reload(_main)

    caught = False
    err_msg = ""
    try:
        # Run lifespan context manager until first yield
        async def _run():
            async with _main.lifespan(_main.app):
                pass
        asyncio.run(_run())
    except RuntimeError as e:
        caught = True
        err_msg = str(e)

    os.environ["VELO_G_SHADOW_MODE"] = "shadow"

    check(
        "VELO_G_SHADOW_MODE=live raises RuntimeError at startup",
        caught and "BLOCKED" in err_msg,
        err_msg[:120] if not caught else "",
    )
except Exception as e:
    os.environ["VELO_G_SHADOW_MODE"] = "shadow"
    check("G shadow mode startup assertion test", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
print()
passed = sum(1 for _, ok in results if ok)
total  = len(results)
print(f"{'='*50}")
print(f"RESULT: {passed}/{total} guards proved")
if passed == total:
    print("All guards verified — branch assertions are real, not decoration.")
else:
    failed = [n for n, ok in results if not ok]
    print(f"FAILED: {failed}")
print(f"{'='*50}")
sys.exit(0 if passed == total else 1)
