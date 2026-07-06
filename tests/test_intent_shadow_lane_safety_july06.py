"""
Regression tests for PASSPORT-INTENT-01-JULY06-RECOVERY-AND-SHADOW-WIRING Part C:
the intent shadow lane (scripts/ops/build_intent_shadow_scorecard.py) must never be
able to authorise a stake or mark itself promotion-eligible, no matter what the
model scores. This is a hard safety boundary, not a tunable default.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "reports" / "july06_intent_shadow_scorecard.csv"
AUDIT_PATH = ROOT / "data" / "reports" / "july06_intent_shadow_audit.json"
SCRIPT_PATH = ROOT / "scripts" / "ops" / "build_intent_shadow_scorecard.py"


def _rows():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_scorecard_exists():
    assert CSV_PATH.exists(), "Run scripts/ops/build_intent_shadow_scorecard.py --date 2026-07-06 --execute"


def test_no_row_ever_authorises_stake():
    rows = _rows()
    assert rows
    for r in rows:
        assert r["stake_authorised"] == "False", f"stake_authorised must never be True: {r['horse']}"


def test_no_row_is_ever_promotion_eligible():
    rows = _rows()
    for r in rows:
        assert r["promotion_eligible"] == "False", f"promotion_eligible must never be True: {r['horse']}"


def test_no_row_is_ever_dashboard_visible():
    rows = _rows()
    for r in rows:
        assert r["dashboard_visible"] == "False"


def test_every_row_labelled_shadow_intent_and_correct_model():
    rows = _rows()
    for r in rows:
        assert r["learning_class"] == "SHADOW_INTENT_SIGNAL"
        assert r["model_label"] == "CHAMPION_INTENT_SHADOW"
        assert r["velo_scoring_allowed"] == "False"
        assert r["trust_policy"] == "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"


def test_audit_summary_flags_are_hardcoded_false():
    assert AUDIT_PATH.exists()
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["stake_authorised"] is False
    assert audit["promotion_eligible"] is False
    assert audit["dashboard_visible"] is False


def test_source_code_never_assigns_true_to_the_three_safety_flags():
    """
    Static guard: the row-construction call site in the script must set these
    three flags to a literal False, not a variable that could evaluate truthy
    from model output or config.
    """
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert '"stake_authorised": False,' in src
    assert '"promotion_eligible": False,' in src
    assert '"dashboard_visible": False,' in src
    # guard against a future edit accidentally wiring these to a variable
    assert '"stake_authorised": True' not in src
    assert '"promotion_eligible": True' not in src


def test_rank_1_within_each_race_is_unique():
    rows = _rows()
    by_race = {}
    for r in rows:
        by_race.setdefault(r["race_id"], []).append(r)
    for race_id, race_rows in by_race.items():
        top_picks = [r for r in race_rows if r["top_pick_shadow"] == "True"]
        assert len(top_picks) == 1, f"Race {race_id} must have exactly one shadow top pick"
