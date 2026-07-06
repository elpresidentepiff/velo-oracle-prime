"""
Regression tests for PASSPORT-INTENT-01-JULY06-RECOVERY-AND-SHADOW-WIRING Part B:
current-card intent feature generation (scripts/ops/build_current_card_intent_features.py).

Covers:
- as-of / leakage safety (no banned current-race fields ever appear, audit reports PASS)
- output schema (every row carries all 15 intent feature keys plus required metadata)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSONL_PATH = ROOT / "data" / "new_build" / "current_cards" / "current_card_intent_features_2026_07_06.jsonl"
AUDIT_PATH = ROOT / "data" / "new_build" / "reports" / "current_card_intent_features_2026_07_06_audit.json"

ALL_INTENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_last_win_or", "curr_or_minus_best_or",
    "runs_since_win", "runs_since_place", "runs_since_mkt_support", "odds_resilience_score",
    "intent_trip_match", "intent_course_win_history", "intent_going_match",
    "intent_class_drop_vs_best", "intent_run_after_break", "intent_sp_shortening",
    "intent_wins_last10", "intent_top3_last6",
]

BANNED_FIELDS = {
    "sp_dec", "rpr", "rpr_num", "is_fav", "sp_rank", "implied_prob", "pos",
    "odds_contraction_score", "decoy_support_flag",
}


def _rows():
    if not JSONL_PATH.exists():
        return []
    return [json.loads(l) for l in JSONL_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_output_file_exists():
    assert JSONL_PATH.exists(), "Run scripts/ops/build_current_card_intent_features.py --date 2026-07-06 --execute"


def test_row_count_matches_card_runners():
    rows = _rows()
    assert len(rows) == 405


def test_every_row_has_all_intent_feature_keys():
    rows = _rows()
    for r in rows:
        for c in ALL_INTENT_FEATURES:
            assert c in r, f"Missing intent feature key {c} on row for {r.get('horse')}"


def test_every_row_has_required_shadow_metadata():
    rows = _rows()
    for r in rows:
        assert r["trust_policy"] == "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
        assert r["velo_scoring_allowed"] is False
        assert r["learning_class"] == "SHADOW_INTENT_SIGNAL"


def test_no_banned_leakage_fields_present_on_any_row():
    rows = _rows()
    for r in rows:
        hit = BANNED_FIELDS & set(r.keys())
        assert not hit, f"Leakage field(s) {hit} present on row for {r.get('horse')}"


def test_intent_class_drop_vs_best_is_never_fabricated():
    """The local archive has no race-class field; this must always be null, never guessed."""
    rows = _rows()
    for r in rows:
        assert r["intent_class_drop_vs_best"] is None


def test_audit_reports_leakage_pass():
    assert AUDIT_PATH.exists()
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert audit["leakage_check"] == "PASS"
    assert audit["leakage_hits"] == []


def test_audit_as_of_rule_is_documented():
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    assert "before target_date" in audit["as_of_rule"]
    assert audit["target_date"] == "2026-07-06"


def test_history_runs_used_never_negative_and_join_hits_consistent():
    rows = _rows()
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    with_history = sum(1 for r in rows if r["history_runs_used"] > 0)
    for r in rows:
        assert r["history_runs_used"] >= 0
    assert with_history == audit["runners_with_any_local_history"]
