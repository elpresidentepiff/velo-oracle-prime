"""
VÉLØ Oracle Prime — Phase 1: Comprehensive Unit Tests
======================================================

Tests all four Phase 1 modules and the integration layer:
    1. Market Constraint Engine
    2. RPD-C v2 Calibration Engine
    3. Scenario Evidence Gate
    4. Track Profile Database
    5. Phase 1 Integration

Run with: python -m pytest tests/test_phase1.py -v
"""

import os
import sys
import sqlite3
import tempfile
import unittest

# Ensure the src directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.constraints.market_engine import (
    MarketConstraintEngine, MarketThresholds,
    DriftClassification, ConstraintVerdict, DriftResult,
    ConstraintDecision, DivergenceResult
)
from src.rpd.rpd_v2 import (
    RPDv2Engine, RPDTag, TagValidity,
    TagValidation, TagSuggestion, TagAuditResult,
    EVIDENCE_DEFINITIONS
)
from src.scenarios.evidence_gate import (
    ScenarioEvidenceGate, ScenarioVerdict,
    ScenarioValidation, ScenarioSuggestion, ScenarioAuditResult,
    SCENARIO_DEFINITIONS
)
from src.tracks.track_profiles import TrackProfileDB, TrackProfile
from src.phase1_integration import Phase1Integration


class BaseTestCase(unittest.TestCase):
    """Base test case with temp database setup."""

    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_velo.db")

    def tearDown(self):
        """Clean up temporary database."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        # Remove WAL/SHM files if present
        for suffix in ["-wal", "-shm"]:
            path = self.db_path + suffix
            if os.path.exists(path):
                os.remove(path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)


# ===================================================================
# MODULE 1: Market Constraint Engine Tests
# ===================================================================

class TestDriftClassification(BaseTestCase):
    """Test the drift analysis functionality."""

    def setUp(self):
        super().setUp()
        self.engine = MarketConstraintEngine(db_path=self.db_path)

    def test_steamer_detection(self):
        """Shortening >15% should classify as STEAMER."""
        # 12.0 → 9.71 = 19.1% shortened
        result = self.engine.analyse_drift("Cressida Wildes", 12.0, 9.71)
        self.assertEqual(result.classification, DriftClassification.STEAMER)
        self.assertGreater(result.pct_change, 15.0)
        self.assertIn("SHORTENED", result.description)

    def test_drifter_detection(self):
        """Lengthening >20% should classify as DRIFTER."""
        # 3.0 → 4.5 = -50% (lengthened)
        result = self.engine.analyse_drift("Test Horse", 3.0, 4.5)
        self.assertEqual(result.classification, DriftClassification.DRIFTER)
        self.assertLess(result.pct_change, -20.0)
        self.assertIn("DRIFTED", result.description)

    def test_stable_classification(self):
        """Price within normal range should classify as STABLE."""
        # 5.0 → 5.3 = -6% (minor drift)
        result = self.engine.analyse_drift("Steady Eddie", 5.0, 5.3)
        self.assertEqual(result.classification, DriftClassification.STABLE)
        self.assertIn("normal range", result.description)

    def test_steamer_boundary(self):
        """Exactly 15% shortening should classify as STEAMER."""
        # 10.0 → 8.5 = 15% shortened
        result = self.engine.analyse_drift("Boundary Horse", 10.0, 8.5)
        self.assertEqual(result.classification, DriftClassification.STEAMER)

    def test_drifter_boundary(self):
        """Exactly 20% lengthening should classify as DRIFTER."""
        # 10.0 → 12.0 = -20% (lengthened)
        result = self.engine.analyse_drift("Drift Boundary", 10.0, 12.0)
        self.assertEqual(result.classification, DriftClassification.DRIFTER)

    def test_invalid_prices(self):
        """Invalid prices should return STABLE with error message."""
        result = self.engine.analyse_drift("Bad Data", 0, 5.0)
        self.assertEqual(result.classification, DriftClassification.STABLE)
        self.assertIn("Invalid", result.description)

        result2 = self.engine.analyse_drift("Bad Data 2", 5.0, 0)
        self.assertEqual(result2.classification, DriftClassification.STABLE)

    def test_custom_thresholds(self):
        """Custom thresholds should change classification boundaries."""
        custom = MarketThresholds(steam_pct=10.0, drift_pct=10.0)
        engine = MarketConstraintEngine(
            db_path=self.db_path, thresholds=custom
        )
        # 10.0 → 8.9 = 11% shortened (above custom 10% threshold)
        result = engine.analyse_drift("Custom Horse", 10.0, 8.9)
        self.assertEqual(result.classification, DriftClassification.STEAMER)


class TestConstraintDecisions(BaseTestCase):
    """Test the hard gate constraint logic."""

    def setUp(self):
        super().setUp()
        self.engine = MarketConstraintEngine(db_path=self.db_path)

    def test_blocked_dismiss_shortening_favourite(self):
        """Dismissing a shortening favourite without counter-signals MUST be BLOCKED."""
        selection = {
            "horse": "Alondra",
            "role": "false_favourite",
            "counter_signals": []
        }
        market_data = {
            "morning_price": 4.0,
            "bsp": 3.0,  # 25% shortened
            "is_favourite": True
        }
        result = self.engine.apply_constraint(selection, market_data)
        self.assertEqual(result.verdict, ConstraintVerdict.BLOCKED)
        self.assertIn("Cannot dismiss", result.message)

    def test_override_with_3_counter_signals(self):
        """3+ counter-signals should allow override of BLOCKED verdict."""
        selection = {
            "horse": "Alondra",
            "role": "false_favourite",
            "counter_signals": [
                "poor_track_record",
                "jockey_negative_stats",
                "trainer_cold_form"
            ]
        }
        market_data = {
            "morning_price": 4.0,
            "bsp": 3.0,
            "is_favourite": True
        }
        result = self.engine.apply_constraint(selection, market_data)
        self.assertEqual(result.verdict, ConstraintVerdict.WARNING)
        self.assertTrue(result.override_allowed)

    def test_insufficient_counter_signals(self):
        """Fewer than 3 counter-signals should keep BLOCKED verdict."""
        selection = {
            "horse": "Alondra",
            "role": "dismiss",
            "counter_signals": ["poor_track_record"]
        }
        market_data = {
            "morning_price": 4.0,
            "bsp": 3.0,
            "is_favourite": True
        }
        result = self.engine.apply_constraint(selection, market_data)
        self.assertEqual(result.verdict, ConstraintVerdict.BLOCKED)
        self.assertFalse(result.override_allowed)

    def test_clear_for_non_dismissal(self):
        """Non-dismissal roles should get CLEAR verdict."""
        selection = {
            "horse": "Good Horse",
            "role": "top_strike",
            "counter_signals": []
        }
        market_data = {
            "morning_price": 5.0,
            "bsp": 5.2,
            "is_favourite": False
        }
        result = self.engine.apply_constraint(selection, market_data)
        self.assertEqual(result.verdict, ConstraintVerdict.CLEAR)

    def test_warning_for_drifter(self):
        """Drifting horse should get WARNING verdict."""
        selection = {
            "horse": "Drifting Horse",
            "role": "top_strike",
            "counter_signals": []
        }
        market_data = {
            "morning_price": 3.0,
            "bsp": 4.5,  # -50% drift
            "is_favourite": False
        }
        result = self.engine.apply_constraint(selection, market_data)
        self.assertEqual(result.verdict, ConstraintVerdict.WARNING)


class TestFavouriteOverrideCheck(BaseTestCase):
    """Test the favourite override check for E tag."""

    def setUp(self):
        super().setUp()
        self.engine = MarketConstraintEngine(db_path=self.db_path)

    def test_blocked_e_tag_on_shortening_favourite(self):
        """E tag on shortening favourite MUST be BLOCKED."""
        result = self.engine.favourite_override_check(
            "Alondra", "E",
            {"morning_price": 4.0, "bsp": 3.0, "is_favourite": True}
        )
        self.assertEqual(result.verdict, ConstraintVerdict.BLOCKED)
        self.assertIn("Exhausted", result.message)

    def test_warning_e_tag_on_shortening_non_favourite(self):
        """E tag on shortening non-favourite should get WARNING."""
        result = self.engine.favourite_override_check(
            "Some Horse", "E",
            {"morning_price": 10.0, "bsp": 8.0, "is_favourite": False}
        )
        self.assertEqual(result.verdict, ConstraintVerdict.WARNING)

    def test_clear_non_e_tag(self):
        """Non-E tags should get CLEAR verdict."""
        result = self.engine.favourite_override_check(
            "Good Horse", "T",
            {"morning_price": 4.0, "bsp": 3.0, "is_favourite": True}
        )
        self.assertEqual(result.verdict, ConstraintVerdict.CLEAR)


class TestBSPISPDivergence(BaseTestCase):
    """Test BSP vs ISP divergence analysis."""

    def setUp(self):
        super().setUp()
        self.engine = MarketConstraintEngine(db_path=self.db_path)

    def test_large_divergence_flagged(self):
        """Large BSP/ISP divergence should be flagged."""
        # Faster Bee: ISP 13 → BSP 21.42 = 64.8% divergence
        result = self.engine.bsp_isp_divergence("Faster Bee", 21.42, 13.0)
        self.assertTrue(result.flagged)
        self.assertEqual(result.direction, "BSP_LONGER")
        self.assertGreater(result.divergence_pct, 60.0)

    def test_small_divergence_not_flagged(self):
        """Small BSP/ISP divergence should NOT be flagged."""
        result = self.engine.bsp_isp_divergence("Steady Horse", 5.0, 4.8)
        self.assertFalse(result.flagged)

    def test_bsp_shorter_direction(self):
        """BSP shorter than ISP should show BSP_SHORTER direction."""
        result = self.engine.bsp_isp_divergence("Short Horse", 3.0, 5.0)
        self.assertEqual(result.direction, "BSP_SHORTER")

    def test_aligned_prices(self):
        """Equal BSP and ISP should show ALIGNED."""
        result = self.engine.bsp_isp_divergence("Equal Horse", 5.0, 5.0)
        self.assertEqual(result.direction, "ALIGNED")
        self.assertFalse(result.flagged)

    def test_invalid_prices(self):
        """Invalid prices should return INVALID direction."""
        result = self.engine.bsp_isp_divergence("Bad Horse", 0, 5.0)
        self.assertEqual(result.direction, "INVALID")
        self.assertFalse(result.flagged)


class TestMarketReport(BaseTestCase):
    """Test market report generation."""

    def setUp(self):
        super().setUp()
        self.engine = MarketConstraintEngine(db_path=self.db_path)

    def test_report_generation(self):
        """Market report should include all runners."""
        race_data = {
            "race_id": "R001",
            "track": "Wolverhampton",
            "runners": [
                {"horse": "Horse A", "morning_price": 4.0, "bsp": 3.0,
                 "is_favourite": True},
                {"horse": "Horse B", "morning_price": 10.0, "bsp": 15.0,
                 "is_favourite": False},
                {"horse": "Horse C", "morning_price": 6.0, "bsp": 6.1,
                 "is_favourite": False},
            ]
        }
        report = self.engine.generate_market_report(race_data)
        self.assertEqual(len(report["runner_reports"]), 3)
        self.assertEqual(report["constraint_counts"]["steamers"], 1)
        self.assertEqual(report["constraint_counts"]["drifters"], 1)

    def test_report_with_isp(self):
        """Market report should include divergence when ISP provided."""
        race_data = {
            "race_id": "R002",
            "track": "Kempton",
            "runners": [
                {"horse": "Horse A", "morning_price": 4.0, "bsp": 3.5,
                 "isp": 4.0, "is_favourite": True},
            ]
        }
        report = self.engine.generate_market_report(race_data)
        self.assertIn("divergence_pct", report["runner_reports"][0])


class TestMarketStorage(BaseTestCase):
    """Test database persistence of market decisions."""

    def setUp(self):
        super().setUp()
        self.engine = MarketConstraintEngine(db_path=self.db_path)

    def test_decision_stored(self):
        """Constraint decisions should be persisted to database."""
        selection = {
            "horse": "Test Horse",
            "role": "top_strike",
            "counter_signals": []
        }
        market_data = {
            "morning_price": 5.0,
            "bsp": 5.2,
            "is_favourite": False
        }
        self.engine.apply_constraint(selection, market_data)
        history = self.engine.get_horse_market_history("Test Horse")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["horse"], "Test Horse")


# ===================================================================
# MODULE 2: RPD-C v2 Calibration Engine Tests
# ===================================================================

class TestTagValidation(BaseTestCase):
    """Test RPD-C tag validation."""

    def setUp(self):
        super().setUp()
        self.engine = RPDv2Engine(db_path=self.db_path)

    def test_valid_t_tag(self):
        """T tag with sufficient evidence should be VALID."""
        result = self.engine.validate_tag(
            "Target Horse", "T",
            ["peak_fitness", "class_appropriate", "course_distance_proven"]
        )
        self.assertEqual(result.validity, TagValidity.VALID)
        self.assertGreater(result.confidence, 0.0)

    def test_invalid_t_tag_insufficient_evidence(self):
        """T tag with insufficient evidence should be INVALID."""
        result = self.engine.validate_tag(
            "Weak Evidence", "T",
            ["peak_fitness"]  # Only 1 of 2 minimum required
        )
        self.assertEqual(result.validity, TagValidity.INVALID)

    def test_e_tag_blocked_by_market_shortening(self):
        """E tag should be BLOCKED when horse is shortening."""
        result = self.engine.validate_tag(
            "Alondra", "E",
            ["long_campaign", "declining_positions"],
            market_shortening=True
        )
        self.assertEqual(result.validity, TagValidity.INVALID)
        self.assertTrue(len(result.blockers_triggered) > 0)
        self.assertIn("CANNOT assign E", result.blockers_triggered[0])

    def test_e_tag_blocked_by_won_last_time(self):
        """E tag should be BLOCKED when horse won last time."""
        result = self.engine.validate_tag(
            "Recent Winner", "E",
            ["long_campaign", "declining_positions"],
            won_last_time=True
        )
        self.assertEqual(result.validity, TagValidity.INVALID)
        self.assertTrue(len(result.blockers_triggered) > 0)

    def test_p_tag_blocked_by_market_shortening(self):
        """P tag should be BLOCKED when horse is shortening."""
        result = self.engine.validate_tag(
            "Ready Horse", "P",
            ["trainer_prep_pattern", "long_absence"],
            market_shortening=True
        )
        self.assertEqual(result.validity, TagValidity.INVALID)

    def test_h_tag_default(self):
        """H tag with consistent_form should be VALID."""
        result = self.engine.validate_tag(
            "Honest Horse", "H",
            ["consistent_form"]
        )
        self.assertEqual(result.validity, TagValidity.VALID)

    def test_s_tag_valid(self):
        """S tag with evidence should be VALID."""
        result = self.engine.validate_tag(
            "Unknown Horse", "S",
            ["first_time_conditions"]
        )
        self.assertEqual(result.validity, TagValidity.VALID)

    def test_invalid_tag_code(self):
        """Unknown tag code should be INVALID."""
        result = self.engine.validate_tag(
            "Horse", "X",
            ["some_evidence"]
        )
        self.assertEqual(result.validity, TagValidity.INVALID)

    def test_confidence_boost_for_trainer_track(self):
        """T tag with trainer_track_strike should get confidence boost."""
        result_with = self.engine.validate_tag(
            "Boosted Horse", "T",
            ["peak_fitness", "class_appropriate", "trainer_track_strike"]
        )
        result_without = self.engine.validate_tag(
            "Normal Horse", "T",
            ["peak_fitness", "class_appropriate"]
        )
        self.assertGreater(result_with.confidence, result_without.confidence)


class TestTagSuggestion(BaseTestCase):
    """Test RPD-C tag suggestion."""

    def setUp(self):
        super().setUp()
        self.engine = RPDv2Engine(db_path=self.db_path)

    def test_suggest_t_tag(self):
        """Evidence matching T should suggest T."""
        result = self.engine.suggest_tag(
            "Target Horse",
            ["peak_fitness", "class_appropriate", "course_distance_proven"]
        )
        self.assertEqual(result.suggested_tag, RPDTag.T)
        self.assertGreater(result.confidence, 0.3)

    def test_suggest_h_as_default(self):
        """No matching evidence should default to H."""
        result = self.engine.suggest_tag(
            "Unknown Horse",
            ["random_evidence_that_matches_nothing"]
        )
        self.assertEqual(result.suggested_tag, RPDTag.H)

    def test_blocked_tags_excluded(self):
        """Blocked tags should not be suggested."""
        result = self.engine.suggest_tag(
            "Shortening Horse",
            ["long_campaign", "declining_positions"],
            market_shortening=True
        )
        # E and P should be blocked, so should not be suggested
        self.assertNotEqual(result.suggested_tag, RPDTag.E)
        self.assertNotEqual(result.suggested_tag, RPDTag.P)


class TestTagAudit(BaseTestCase):
    """Test post-race tag audit."""

    def setUp(self):
        super().setUp()
        self.engine = RPDv2Engine(db_path=self.db_path)

    def test_audit_correct_t_tag(self):
        """T tag on horse that finished 1st should be correct."""
        predictions = [
            {"horse": "Winner", "tag": "T", "confidence": 0.8,
             "role": "top_strike"}
        ]
        results = [
            {"horse": "Winner", "finish_pos": 1, "bsp": 3.0, "won": True}
        ]
        audit = self.engine.tag_audit(predictions, results)
        self.assertEqual(audit.total_predictions, 1)
        self.assertEqual(audit.correct_tags, 1)
        self.assertEqual(audit.accuracy_pct, 100.0)

    def test_audit_incorrect_e_tag(self):
        """E tag on horse that won should be incorrect."""
        predictions = [
            {"horse": "Surprise", "tag": "E", "confidence": 0.6,
             "role": "danger"}
        ]
        results = [
            {"horse": "Surprise", "finish_pos": 1, "bsp": 15.0, "won": True}
        ]
        audit = self.engine.tag_audit(predictions, results)
        self.assertEqual(audit.correct_tags, 0)
        self.assertTrue(len(audit.lessons) > 0)
        self.assertIn("Exhausted", audit.lessons[0])

    def test_audit_h_tag_big_price_winner(self):
        """H tag on horse that won at big price should be incorrect."""
        predictions = [
            {"horse": "Faster Bee", "tag": "H", "confidence": 0.5,
             "role": "honest"}
        ]
        results = [
            {"horse": "Faster Bee", "finish_pos": 1, "bsp": 21.42,
             "won": True}
        ]
        audit = self.engine.tag_audit(predictions, results)
        self.assertEqual(audit.correct_tags, 0)
        self.assertTrue(any("21.42" in l for l in audit.lessons))

    def test_audit_multiple_predictions(self):
        """Audit should handle multiple predictions correctly."""
        predictions = [
            {"horse": "Horse A", "tag": "T", "confidence": 0.8,
             "role": "top_strike"},
            {"horse": "Horse B", "tag": "E", "confidence": 0.6,
             "role": "danger"},
            {"horse": "Horse C", "tag": "H", "confidence": 0.5,
             "role": "honest"},
        ]
        results = [
            {"horse": "Horse A", "finish_pos": 1, "bsp": 3.0, "won": True},
            {"horse": "Horse B", "finish_pos": 6, "bsp": 10.0, "won": False},
            {"horse": "Horse C", "finish_pos": 3, "bsp": 5.0, "won": False},
        ]
        audit = self.engine.tag_audit(predictions, results)
        self.assertEqual(audit.total_predictions, 3)
        self.assertEqual(audit.correct_tags, 3)  # All correct


class TestRecalibration(BaseTestCase):
    """Test sigma-based recalibration."""

    def setUp(self):
        super().setUp()
        self.engine = RPDv2Engine(db_path=self.db_path)

    def test_recalibration_updates_weights(self):
        """Recalibration with sufficient data should update weights."""
        sigma_data = [
            {"horse": f"Horse{i}", "tag": "T",
             "evidence_used": ["peak_fitness", "class_appropriate"],
             "tag_correct": True, "finish_pos": 1, "bsp": 3.0}
            for i in range(5)
        ]
        result = self.engine.recalibrate_from_sigma(sigma_data)
        self.assertGreater(result["weights_updated"], 0)


class TestEvidenceRequirements(BaseTestCase):
    """Test evidence requirement retrieval."""

    def setUp(self):
        super().setUp()
        self.engine = RPDv2Engine(db_path=self.db_path)

    def test_get_evidence_for_all_tags(self):
        """All valid tags should return evidence requirements."""
        for tag in ["P", "T", "E", "H", "S"]:
            reqs = self.engine.get_evidence_requirements(tag)
            self.assertIn("evidence_types", reqs)
            self.assertIn("min_evidence", reqs)

    def test_unknown_tag_returns_error(self):
        """Unknown tag should return error dict."""
        reqs = self.engine.get_evidence_requirements("Z")
        self.assertIn("error", reqs)


# ===================================================================
# MODULE 3: Scenario Evidence Gate Tests
# ===================================================================

class TestScenarioValidation(BaseTestCase):
    """Test scenario code validation."""

    def setUp(self):
        super().setUp()
        self.gate = ScenarioEvidenceGate(db_path=self.db_path)

    def test_s1_approved(self):
        """S1 with all 3 signals should be APPROVED."""
        result = self.gate.validate_scenario(
            "S1", ["form", "class", "market_agreement"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.APPROVED)

    def test_s1_rejected_insufficient(self):
        """S1 with fewer than 3 signals should be REJECTED."""
        result = self.gate.validate_scenario("S1", ["form", "class"])
        self.assertEqual(result.verdict, ScenarioVerdict.REJECTED)

    def test_s6_approved_with_market(self):
        """S6 with all 4 signals including market_shortening should be APPROVED."""
        result = self.gate.validate_scenario(
            "S6",
            ["trainer_pattern", "jockey_upgrade", "gear_change",
             "market_shortening"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.APPROVED)
        self.assertTrue(result.hard_requirements_met)

    def test_s6_rejected_without_market(self):
        """S6 without market_shortening MUST be REJECTED (hard requirement)."""
        result = self.gate.validate_scenario(
            "S6",
            ["trainer_pattern", "jockey_upgrade", "gear_change"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.REJECTED)
        self.assertFalse(result.hard_requirements_met)

    def test_s6_hard_gate_explicit(self):
        """S6 hard gate method should explicitly reject without market signal."""
        result = self.gate.s6_hard_gate(
            ["trainer_pattern", "jockey_upgrade", "gear_change"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.REJECTED)
        self.assertIn("HARD GATE FAILURE", result.reasoning)
        self.assertIn("fiction", result.reasoning)

    def test_s6_hard_gate_approved(self):
        """S6 hard gate with market_shortening should pass."""
        result = self.gate.s6_hard_gate(
            ["trainer_pattern", "jockey_upgrade", "gear_change",
             "market_shortening"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.APPROVED)

    def test_s8_approved_minimal(self):
        """S8 with insufficient_data signal should be APPROVED."""
        result = self.gate.validate_scenario(
            "S8", ["insufficient_data"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.APPROVED)

    def test_unknown_scenario_rejected(self):
        """Unknown scenario code should be REJECTED."""
        result = self.gate.validate_scenario("S99", ["some_signal"])
        self.assertEqual(result.verdict, ScenarioVerdict.REJECTED)

    def test_s2_approved(self):
        """S2 with 2 signals should be APPROVED."""
        result = self.gate.validate_scenario(
            "S2", ["pace_shape", "jockey_tactical"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.APPROVED)

    def test_s3_requires_3_signals(self):
        """S3 with only 2 of 3 required signals should be REJECTED."""
        result = self.gate.validate_scenario(
            "S3", ["pace_suicide_risk", "closer_form"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.REJECTED)

    def test_s3_approved_with_all_signals(self):
        """S3 with all 3 signals should be APPROVED."""
        result = self.gate.validate_scenario(
            "S3", ["pace_suicide_risk", "closer_form", "draw_position"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.APPROVED)


class TestScenarioSuggestion(BaseTestCase):
    """Test scenario suggestion."""

    def setUp(self):
        super().setUp()
        self.gate = ScenarioEvidenceGate(db_path=self.db_path)

    def test_suggest_s1(self):
        """S1 signals should suggest S1."""
        result = self.gate.suggest_scenario(
            ["form", "class", "market_agreement"]
        )
        self.assertEqual(result.suggested_code, "S1")

    def test_suggest_s8_default(self):
        """No matching signals should suggest S8 (Chaos)."""
        result = self.gate.suggest_scenario(
            ["random_signal_that_matches_nothing"]
        )
        self.assertEqual(result.suggested_code, "S8")
        self.assertIn("Chaos", result.reasoning)

    def test_suggestion_has_alternatives(self):
        """Suggestion should include alternative scenarios."""
        result = self.gate.suggest_scenario(
            ["form", "class", "market_agreement",
             "pace_shape", "jockey_tactical"]
        )
        # Should have alternatives since multiple scenarios match
        self.assertIsInstance(result.alternatives, list)


class TestScenarioAudit(BaseTestCase):
    """Test post-race scenario audit."""

    def setUp(self):
        super().setUp()
        self.gate = ScenarioEvidenceGate(db_path=self.db_path)

    def test_audit_correct_scenario(self):
        """Correct scenario prediction should count as correct."""
        predictions = [
            {"race_id": "R1", "scenario_code": "S1",
             "horse": "Winner", "confidence": 0.8}
        ]
        results = [
            {"race_id": "R1", "actual_scenario": "S1",
             "horse": "Winner", "finish_pos": 1, "won": True}
        ]
        audit = self.gate.scenario_audit(predictions, results)
        self.assertEqual(audit.correct_scenarios, 1)
        self.assertEqual(audit.accuracy_pct, 100.0)

    def test_audit_s6_overuse(self):
        """S6 predicted but wrong should generate overuse lesson."""
        predictions = [
            {"race_id": "R1", "scenario_code": "S6",
             "horse": "Horse A", "confidence": 0.6}
        ]
        results = [
            {"race_id": "R1", "actual_scenario": "S8",
             "horse": "Horse A", "finish_pos": 5, "won": False}
        ]
        audit = self.gate.scenario_audit(predictions, results)
        self.assertEqual(audit.correct_scenarios, 0)
        self.assertTrue(any("S6 overuse" in l for l in audit.lessons))


class TestScenarioRequirements(BaseTestCase):
    """Test scenario requirement retrieval."""

    def setUp(self):
        super().setUp()
        self.gate = ScenarioEvidenceGate(db_path=self.db_path)

    def test_get_all_scenario_requirements(self):
        """All scenario codes should return requirements."""
        for code in ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]:
            reqs = self.gate.get_requirements(code)
            self.assertIn("required_signal_types", reqs)
            self.assertIn("min_signals", reqs)

    def test_s6_has_hard_requirements(self):
        """S6 should have market_shortening as hard requirement."""
        reqs = self.gate.get_requirements("S6")
        self.assertIn("market_shortening", reqs["hard_requirements"])


# ===================================================================
# MODULE 4: Track Profile Database Tests
# ===================================================================

class TestTrackProfileDB(BaseTestCase):
    """Test track profile database."""

    def setUp(self):
        super().setUp()
        self.db = TrackProfileDB(db_path=self.db_path, auto_load=True)

    def test_minimum_40_tracks(self):
        """Database should contain at least 40 tracks."""
        count = self.db.get_track_count()
        self.assertGreaterEqual(count, 40)

    def test_wolverhampton_profile(self):
        """Wolverhampton profile should exist with correct data."""
        profile = self.db.get_profile("Wolverhampton")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["surface"], "AW")
        self.assertEqual(profile["aw_surface_type"], "Tapeta")
        self.assertEqual(profile["direction"], "left-handed")
        self.assertEqual(profile["circuit_type"], "sharp")
        self.assertGreaterEqual(profile["chaos_rating"], 4)

    def test_case_insensitive_lookup(self):
        """Track lookup should be case-insensitive."""
        profile = self.db.get_profile("wolverhampton")
        self.assertIsNotNone(profile)
        profile2 = self.db.get_profile("WOLVERHAMPTON")
        self.assertIsNotNone(profile2)

    def test_nonexistent_track(self):
        """Non-existent track should return None."""
        profile = self.db.get_profile("Narnia Racecourse")
        self.assertIsNone(profile)

    def test_draw_bias_lookup(self):
        """Draw bias should return data for known distances."""
        bias = self.db.get_draw_bias("Wolverhampton", "5f")
        self.assertIsNotNone(bias)
        self.assertIn("Low draw", bias)

    def test_draw_bias_general_fallback(self):
        """Unknown distance should fall back to general description."""
        bias = self.db.get_draw_bias("Wolverhampton", "99f")
        self.assertIsNotNone(bias)

    def test_pace_bias(self):
        """Pace bias should return valid classification."""
        pace = self.db.get_pace_bias("Wolverhampton")
        self.assertIn(pace, ["front", "hold-up", "neutral"])

    def test_chaos_rating(self):
        """Chaos rating should be between 1 and 5."""
        for track in self.db.get_all_tracks():
            rating = self.db.get_chaos_rating(track)
            self.assertIsNotNone(rating)
            self.assertGreaterEqual(rating, 1)
            self.assertLessEqual(rating, 5)


class TestPreRaceContext(BaseTestCase):
    """Test pre-race context generation."""

    def setUp(self):
        super().setUp()
        self.db = TrackProfileDB(db_path=self.db_path, auto_load=True)

    def test_context_for_known_track(self):
        """Pre-race context should include key intelligence."""
        context = self.db.pre_race_context("Wolverhampton", "5f 21y", "Standard")
        self.assertIn("WOLVERHAMPTON", context)
        self.assertIn("Tapeta", context)
        self.assertIn("Chaos Rating", context)
        self.assertIn("HIGH CHAOS", context)

    def test_context_for_unknown_track(self):
        """Unknown track should return warning message."""
        context = self.db.pre_race_context("Unknown Track", "1m", "Good")
        self.assertIn("NO TRACK PROFILE FOUND", context)

    def test_chaos_warning_in_context(self):
        """High chaos tracks should include warning in context."""
        context = self.db.pre_race_context("Wolverhampton", "5f", "Standard")
        self.assertIn("RPD-C layer MANDATORY", context)


class TestTrackComparison(BaseTestCase):
    """Test track comparison functionality."""

    def setUp(self):
        super().setUp()
        self.db = TrackProfileDB(db_path=self.db_path, auto_load=True)

    def test_compare_similar_tracks(self):
        """Similar AW tracks should have higher similarity score."""
        result = self.db.compare_tracks("Wolverhampton", "Lingfield")
        self.assertIn("similarity_score", result)
        self.assertGreater(result["similarity_score"], 0.3)

    def test_compare_different_tracks(self):
        """Very different tracks should have lower similarity score."""
        result = self.db.compare_tracks("Wolverhampton", "York")
        self.assertIn("differences", result)
        self.assertTrue(len(result["differences"]) > 0)

    def test_compare_nonexistent_track(self):
        """Comparing with non-existent track should return error."""
        result = self.db.compare_tracks("Wolverhampton", "Narnia")
        self.assertIn("error", result)


class TestAWTrackQueries(BaseTestCase):
    """Test AW-specific queries."""

    def setUp(self):
        super().setUp()
        self.db = TrackProfileDB(db_path=self.db_path, auto_load=True)

    def test_get_aw_tracks(self):
        """Should return all AW tracks."""
        aw_tracks = self.db.get_aw_tracks()
        self.assertGreaterEqual(len(aw_tracks), 5)
        for track in aw_tracks:
            self.assertEqual(track["surface"], "AW")

    def test_search_by_characteristic(self):
        """Should find tracks matching characteristic keyword."""
        results = self.db.search_by_characteristic("front-runners")
        self.assertGreater(len(results), 0)

    def test_search_by_chaos(self):
        """Should find tracks matching 'chaos' keyword."""
        results = self.db.search_by_characteristic("chaos")
        self.assertGreater(len(results), 0)


class TestTrackUpdate(BaseTestCase):
    """Test track profile updates."""

    def setUp(self):
        super().setUp()
        self.db = TrackProfileDB(db_path=self.db_path, auto_load=True)

    def test_update_chaos_rating(self):
        """Should be able to update chaos rating."""
        success = self.db.update_profile("Wolverhampton", "chaos_rating", 5)
        self.assertTrue(success)
        rating = self.db.get_chaos_rating("Wolverhampton")
        self.assertEqual(rating, 5)

    def test_update_disallowed_field(self):
        """Should not allow updating disallowed fields."""
        success = self.db.update_profile("Wolverhampton", "id", 999)
        self.assertFalse(success)

    def test_update_nonexistent_track(self):
        """Updating non-existent track should return False."""
        success = self.db.update_profile("Narnia", "chaos_rating", 5)
        self.assertFalse(success)


# ===================================================================
# MODULE 5: Phase 1 Integration Tests
# ===================================================================

class TestPhase1Integration(BaseTestCase):
    """Test the unified Phase 1 integration layer."""

    def setUp(self):
        super().setUp()
        self.p1 = Phase1Integration(db_path=self.db_path)

    def test_system_status(self):
        """System status should report all modules active."""
        status = self.p1.get_system_status()
        self.assertEqual(status["phase"], "Phase 1")
        for module in status["modules"].values():
            self.assertEqual(module["status"], "ACTIVE")

    def test_track_count_in_status(self):
        """Status should report 40+ tracks loaded."""
        status = self.p1.get_system_status()
        total = status["modules"]["track_profile_db"]["total_tracks"]
        self.assertGreaterEqual(total, 40)


class TestPreRaceCheck(BaseTestCase):
    """Test the consolidated pre-race check."""

    def setUp(self):
        super().setUp()
        self.p1 = Phase1Integration(db_path=self.db_path)

    def test_pre_race_check_basic(self):
        """Pre-race check should return all expected fields."""
        race_data = {
            "race_id": "WOL_R1",
            "track": "Wolverhampton",
            "distance": "5f 21y",
            "going": "Standard",
            "runners": [
                {
                    "horse": "Cressida Wildes",
                    "morning_price": 12.0,
                    "bsp": 9.71,
                    "is_favourite": False,
                    "proposed_tag": "S",
                    "tag_evidence": ["first_time_conditions"],
                },
                {
                    "horse": "Alondra",
                    "morning_price": 4.0,
                    "bsp": 3.0,
                    "is_favourite": True,
                    "proposed_tag": "E",
                    "tag_evidence": ["long_campaign", "declining_positions"],
                },
            ],
            "proposed_scenario": "S6",
            "scenario_signals": ["trainer_pattern", "jockey_upgrade"],
        }
        result = self.p1.pre_race_check(race_data)

        # Check structure
        self.assertIn("track_context", result)
        self.assertIn("chaos_rating", result)
        self.assertIn("market_report", result)
        self.assertIn("runner_assessments", result)
        self.assertIn("scenario_validation", result)
        self.assertIn("alerts", result)
        self.assertIn("summary", result)

        # Check chaos rating for Wolverhampton
        self.assertGreaterEqual(result["chaos_rating"], 4)

        # Check alerts generated
        self.assertTrue(len(result["alerts"]) > 0)

    def test_pre_race_check_favourite_block(self):
        """Pre-race check should generate alert for E tag on shortening fav."""
        race_data = {
            "race_id": "WOL_R2",
            "track": "Wolverhampton",
            "distance": "7f 36y",
            "going": "Standard",
            "runners": [
                {
                    "horse": "Alondra",
                    "morning_price": 4.0,
                    "bsp": 3.0,
                    "is_favourite": True,
                    "proposed_tag": "E",
                    "tag_evidence": ["long_campaign", "declining_positions"],
                },
            ],
        }
        result = self.p1.pre_race_check(race_data)
        # Should have alert about blocked E tag or favourite override
        alerts_text = " ".join(result["alerts"])
        self.assertTrue(
            "BLOCKED" in alerts_text or "TAG INVALID" in alerts_text
        )

    def test_pre_race_check_s6_rejection(self):
        """Pre-race check should reject S6 without market_shortening."""
        race_data = {
            "race_id": "WOL_R3",
            "track": "Wolverhampton",
            "distance": "1m 142y",
            "going": "Standard",
            "runners": [],
            "proposed_scenario": "S6",
            "scenario_signals": ["trainer_pattern", "jockey_upgrade",
                                 "gear_change"],
        }
        result = self.p1.pre_race_check(race_data)
        self.assertIn("scenario_validation", result)
        self.assertEqual(
            result["scenario_validation"]["verdict"], "REJECTED"
        )

    def test_pre_race_check_tag_suggestion(self):
        """Pre-race check should suggest tags when none proposed."""
        race_data = {
            "race_id": "KEM_R1",
            "track": "Kempton",
            "distance": "7f",
            "going": "Standard",
            "runners": [
                {
                    "horse": "Mystery Horse",
                    "morning_price": 8.0,
                    "bsp": 8.5,
                    "is_favourite": False,
                    "tag_evidence": ["consistent_form"],
                },
            ],
        }
        result = self.p1.pre_race_check(race_data)
        runner = result["runner_assessments"][0]
        self.assertIn("tag_suggestion", runner)

    def test_pre_race_check_scenario_suggestion(self):
        """Pre-race check should suggest scenario when none proposed."""
        race_data = {
            "race_id": "KEM_R2",
            "track": "Kempton",
            "distance": "1m",
            "going": "Standard",
            "runners": [],
            "scenario_signals": ["form", "class", "market_agreement"],
        }
        result = self.p1.pre_race_check(race_data)
        self.assertIn("scenario_validation", result)
        self.assertIn("suggested_code", result["scenario_validation"])


class TestPostRaceAudit(BaseTestCase):
    """Test the consolidated post-race audit."""

    def setUp(self):
        super().setUp()
        self.p1 = Phase1Integration(db_path=self.db_path)

    def test_post_race_audit_basic(self):
        """Post-race audit should return all expected fields."""
        predictions = [
            {"horse": "Horse A", "tag": "T", "confidence": 0.8,
             "role": "top_strike", "scenario_code": "S1",
             "race_id": "R1"},
            {"horse": "Horse B", "tag": "E", "confidence": 0.6,
             "role": "danger", "scenario_code": "S1",
             "race_id": "R1"},
        ]
        results = [
            {"horse": "Horse A", "finish_pos": 1, "bsp": 3.0,
             "won": True, "actual_scenario": "S1", "race_id": "R1"},
            {"horse": "Horse B", "finish_pos": 5, "bsp": 10.0,
             "won": False, "actual_scenario": "S1", "race_id": "R1"},
        ]
        audit = self.p1.post_race_audit(predictions, results)

        self.assertIn("tag_audit", audit)
        self.assertIn("scenario_audit", audit)
        self.assertIn("combined_accuracy", audit)
        self.assertIn("lessons", audit)
        self.assertIn("recommendations", audit)

    def test_post_race_audit_generates_recommendations(self):
        """Low accuracy should generate recommendations."""
        predictions = [
            {"horse": f"Horse{i}", "tag": "E", "confidence": 0.6,
             "role": "danger", "scenario_code": "S6",
             "race_id": f"R{i}"}
            for i in range(5)
        ]
        results = [
            {"horse": f"Horse{i}", "finish_pos": 1, "bsp": 15.0,
             "won": True, "actual_scenario": "S8", "race_id": f"R{i}"}
            for i in range(5)
        ]
        audit = self.p1.post_race_audit(predictions, results)
        # Should have recommendations about low accuracy
        self.assertTrue(len(audit["recommendations"]) > 0)


class TestWolverhamptonDay1Replay(BaseTestCase):
    """Replay the Wolverhampton Day 1 failure to verify fixes.

    This is the most important test class — it verifies that the
    specific failure modes from SIGMA-02 are now caught.
    """

    def setUp(self):
        super().setUp()
        self.p1 = Phase1Integration(db_path=self.db_path)

    def test_alondra_e_tag_blocked(self):
        """Day 1 failure: Alondra tagged E despite being shortening favourite.
        System should now BLOCK this.
        """
        result = self.p1.rpd_engine.validate_tag(
            "Alondra", "E",
            ["long_campaign", "declining_positions"],
            market_shortening=True
        )
        self.assertEqual(result.validity, TagValidity.INVALID)
        self.assertTrue(len(result.blockers_triggered) > 0)

    def test_cressida_wildes_steamer_detection(self):
        """Day 1 failure: Cressida Wildes shortened from 12.0 to 9.71.
        System should now detect this as STEAMER.
        """
        drift = self.p1.market_engine.analyse_drift(
            "Cressida Wildes", 12.0, 9.71
        )
        self.assertEqual(drift.classification, DriftClassification.STEAMER)

    def test_faster_bee_divergence_flagged(self):
        """Day 1 failure: Faster Bee ISP 13 → BSP 21.42.
        System should now flag this divergence.
        """
        divergence = self.p1.market_engine.bsp_isp_divergence(
            "Faster Bee", 21.42, 13.0
        )
        self.assertTrue(divergence.flagged)
        self.assertGreater(divergence.divergence_pct, 60.0)

    def test_s6_without_market_rejected(self):
        """Day 1 failure: S6 deployed without market confirmation.
        System should now REJECT this.
        """
        result = self.p1.scenario_gate.s6_hard_gate(
            ["trainer_pattern", "jockey_upgrade"]
        )
        self.assertEqual(result.verdict, ScenarioVerdict.REJECTED)

    def test_wolverhampton_chaos_rating(self):
        """Day 1 failure: No track intelligence for Wolverhampton.
        System should now have chaos rating >= 4.
        """
        rating = self.p1.track_db.get_chaos_rating("Wolverhampton")
        self.assertGreaterEqual(rating, 4)

    def test_wolverhampton_pre_race_context(self):
        """Day 1 failure: No track context available.
        System should now provide full intelligence brief.
        """
        context = self.p1.track_db.pre_race_context(
            "Wolverhampton", "5f 21y", "Standard"
        )
        self.assertIn("Tapeta", context)
        self.assertIn("sharp", context)
        self.assertIn("HIGH CHAOS", context)


# ===================================================================
# Run Tests
# ===================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
