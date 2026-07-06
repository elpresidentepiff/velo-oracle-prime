"""
Isolation guard for PASSPORT-INTENT-01-JULY06-RECOVERY-AND-SHADOW-WIRING.

This mission touches only: the July 06 passport bank/current-card feed, a
new current-card intent feature builder, and a new shadow scorecard. It must
never mutate the canonical July 05 Little Lady Rock proof case
(race_id 922118, MODEL-TRUTH-RESET-01-CANONICAL-SCORECARD-CONTRACT) or the
canonical learning-events table. Those are governed elsewhere and are only
verified, never edited, by this mission.
"""
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SCORECARD = ROOT / "data" / "reports" / "canonical_model_scorecard_2026_07_05.csv"

# Hash captured before/independent of the PASSPORT-INTENT-01 mission's changes.
# If this ever changes, something outside this mission's scope was edited —
# investigate before assuming it's fine to update the hash.
EXPECTED_SHA256 = "4d4e9fb3afbc6f5f6e14406364b029398d12a097666ff2bbd1eafcfb4ee8bcbd"


def test_canonical_scorecard_untouched_by_hash():
    if not CANONICAL_SCORECARD.exists():
        return  # nothing to guard if the local artifact isn't present in this environment
    digest = hashlib.sha256(CANONICAL_SCORECARD.read_bytes()).hexdigest()
    assert digest == EXPECTED_SHA256, (
        "canonical_model_scorecard_2026_07_05.csv changed — PASSPORT-INTENT-01 must never "
        "touch the Little Lady Rock canonical proof case"
    )


def test_little_lady_rock_race_922118_still_holds():
    if not CANONICAL_SCORECARD.exists():
        return
    with CANONICAL_SCORECARD.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["race_id"] == "922118"]
    lane_a = [r for r in rows if r["model_name"] == "NEW_BUILD_LANE_A_MODEL" and r["horse"] == "Little Lady Rock"]
    assert lane_a, "Little Lady Rock NEW_BUILD_LANE_A_MODEL row must still exist"
    assert lane_a[0]["rank"] == "1"
    assert lane_a[0]["stake_authorised"] == "False"
    assert lane_a[0]["policy_decision"] == "NO_EDGE"


def test_no_july06_script_writes_under_canonical_reports_namespace():
    """
    Static guard: none of the three new/updated July 06 scripts should ever
    construct a path into the canonical_model_scorecard_* or
    canonical_learning_events_* namespace.
    """
    new_scripts = [
        ROOT / "scripts" / "ops" / "build_current_card_intent_features.py",
        ROOT / "scripts" / "ops" / "build_intent_shadow_scorecard.py",
    ]
    for path in new_scripts:
        src = path.read_text(encoding="utf-8")
        assert "canonical_model_scorecard" not in src
        assert "canonical_learning_events" not in src
