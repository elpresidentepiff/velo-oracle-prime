"""Tests for parse quality calculation"""

import pytest
from workers.ingestion_spine.quality import (
    calculate_runner_confidence,
    calculate_race_quality,
    validate_race
)


class TestRunnerConfidence:
    def test_perfect_runner(self):
        """Runner with all fields should have 1.0 confidence"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 5.0,
            "jockey": "J. Smith",
            "trainer": "T. Jones",
            "weight": 9.0
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert confidence == 1.0
        assert flags == []
        assert method == "table"
    
    def test_missing_odds_penalty(self):
        """Missing odds should reduce confidence by 0.3"""
        runner = {
            "horse_name": "Test Horse",
            "jockey": "J. Smith"
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        # 1.0 - 0.3 (odds) - 0.1 (jockey present, so only trainer/weight missing) = 0.6
        assert abs(confidence - 0.6) < 0.01
        assert "missing_odds" in flags
    
    def test_missing_name_critical(self):
        """Missing horse name is critical (-0.5)"""
        runner = {
            "odds": 5.0,
            "jockey": "J. Smith"
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert confidence <= 0.5
        assert "missing_horse_name" in flags
    
    def test_suspicious_odds(self):
        """Odds outside reasonable range should be flagged"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 2000.0  # Suspiciously high
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert "suspicious_odds" in flags
    
    def test_empty_horse_name(self):
        """Empty/whitespace horse name should be treated as missing"""
        runner = {
            "horse_name": "   ",
            "odds": 5.0,
            "jockey": "J. Smith"
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert "missing_horse_name" in flags
        assert confidence <= 0.5
    
    def test_estimated_odds(self):
        """Estimated odds should reduce confidence and change method"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 5.0,
            "odds_estimated": True,
            "jockey": "J. Smith",
            "trainer": "T. Jones",
            "weight": 9.0
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert "estimated_odds" in flags
        assert method == "fallback"
        assert confidence < 1.0
    
    def test_fuzzy_extraction(self):
        """Fuzzy extraction should reduce confidence"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 5.0,
            "fuzzy_extraction": True,
            "jockey": "J. Smith"
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert "fuzzy_extraction" in flags
        assert method == "text"
        assert confidence < 1.0
    
    def test_low_odds(self):
        """Odds below 1.0 should be flagged as suspicious"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 0.5
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert "suspicious_odds" in flags
    
    def test_confidence_clamped_to_zero(self):
        """Confidence should not go below 0.0"""
        runner = {
            # Missing everything
        }
        
        confidence, flags, method = calculate_runner_confidence(runner)
        
        assert confidence >= 0.0
        assert confidence <= 1.0


class TestRaceQuality:
    def test_perfect_race(self):
        """Race with all fields and high-quality runners"""
        race = {
            "course": "Kempton",
            "distance": 2000,
            "race_time": "14:30"
        }
        runners = [
            {"horse_name": f"Horse {i}", "odds": 5.0, "confidence": 1.0}
            for i in range(10)
        ]
        
        parse_conf, quality, flags = calculate_race_quality(race, runners)
        
        assert parse_conf == 1.0
        assert quality == 1.0
        assert flags == []
    
    def test_duplicate_names_penalty(self):
        """Duplicate horse names should be heavily penalized"""
        race = {"course": "Kempton", "distance": 2000, "race_time": "14:30"}
        runners = [
            {"horse_name": "Same Name", "odds": 5.0, "confidence": 1.0},
            {"horse_name": "Same Name", "odds": 3.0, "confidence": 1.0},
            {"horse_name": "Different", "odds": 4.0, "confidence": 1.0}
        ]
        
        _, quality, flags = calculate_race_quality(race, runners)
        
        assert "duplicate_horse_names" in flags
        assert quality < 0.7  # Significant penalty
    
    def test_too_few_runners(self):
        """Less than 4 runners should be flagged"""
        race = {"course": "Kempton", "distance": 2000}
        runners = [
            {"horse_name": f"Horse {i}", "confidence": 1.0}
            for i in range(3)
        ]
        
        _, quality, flags = calculate_race_quality(race, runners)
        
        assert "too_few_runners" in flags
        assert quality < 0.8
    
    def test_too_many_runners(self):
        """More than 30 runners should be flagged"""
        race = {"course": "Kempton", "distance": 2000}
        runners = [
            {"horse_name": f"Horse {i}", "confidence": 1.0}
            for i in range(35)
        ]
        
        _, quality, flags = calculate_race_quality(race, runners)
        
        assert "too_many_runners" in flags
    
    def test_no_runners(self):
        """Race with no runners should have zero quality"""
        race = {"course": "Kempton", "distance": 2000}
        runners = []
        
        parse_conf, quality, flags = calculate_race_quality(race, runners)
        
        assert parse_conf == 0.0
        assert quality == 0.0
        assert "no_runners" in flags
    
    def test_missing_course(self):
        """Missing course should reduce quality"""
        race = {"distance": 2000, "race_time": "14:30"}
        runners = [
            {"horse_name": f"Horse {i}", "confidence": 1.0}
            for i in range(10)
        ]
        
        _, quality, flags = calculate_race_quality(race, runners)
        
        assert "missing_course" in flags
        assert quality < 1.0
    
    def test_missing_distance(self):
        """Missing distance should reduce quality"""
        race = {"course": "Kempton", "race_time": "14:30"}
        runners = [
            {"horse_name": f"Horse {i}", "confidence": 1.0}
            for i in range(10)
        ]
        
        _, quality, flags = calculate_race_quality(race, runners)
        
        assert "missing_distance" in flags
        assert quality < 1.0
    
    def test_missing_race_time(self):
        """Missing race time should reduce quality slightly"""
        race = {"course": "Kempton", "distance": 2000}
        runners = [
            {"horse_name": f"Horse {i}", "confidence": 1.0}
            for i in range(10)
        ]
        
        _, quality, flags = calculate_race_quality(race, runners)
        
        assert "missing_race_time" in flags
    
    def test_many_low_confidence_runners(self):
        """More than 30% low confidence runners should be flagged"""
        race = {"course": "Kempton", "distance": 2000}
        runners = [
            {"horse_name": f"Horse {i}", "confidence": 0.5 if i < 5 else 1.0}
            for i in range(10)
        ]
        
        _, quality, flags = calculate_race_quality(race, runners)
        
        assert "many_low_confidence_runners" in flags
    
    def test_parse_confidence_calculation(self):
        """Parse confidence should be average of runner confidences"""
        race = {"course": "Kempton", "distance": 2000}
        runners = [
            {"horse_name": "Horse 1", "confidence": 1.0},
            {"horse_name": "Horse 2", "confidence": 0.8},
            {"horse_name": "Horse 3", "confidence": 0.6}
        ]
        
        parse_conf, _, _ = calculate_race_quality(race, runners)
        
        expected = (1.0 + 0.8 + 0.6) / 3
        assert abs(parse_conf - expected) < 0.01
    
    def test_quality_clamped_to_range(self):
        """Quality should be clamped to [0.0, 1.0]"""
        race = {}  # Missing everything
        runners = [{"horse_name": f"Horse {i}", "confidence": 0.0} for i in range(2)]
        
        _, quality, _ = calculate_race_quality(race, runners)
        
        assert quality >= 0.0
        assert quality <= 1.0


class TestValidation:
    def test_valid_race(self):
        """High-quality race should validate as valid"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
            "quality_score": 0.95,
            "quality_flags": []
        }
        
        result = validate_race(race)
        
        assert result["status"] == "valid"
        assert result["issues"] == []
    
    def test_rejected_missing_course(self):
        """Missing course should reject"""
        race = {
            "id": "race-1",
            "distance": 2000,
            "runners": [{"horse_name": "Horse 1"}],
            "quality_score": 0.8
        }
        
        result = validate_race(race)
        
        assert result["status"] == "rejected"
        assert any("REJECT" in issue for issue in result["issues"])
    
    def test_rejected_missing_distance(self):
        """Missing distance should reject"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "runners": [{"horse_name": "Horse 1"}],
            "quality_score": 0.8
        }
        
        result = validate_race(race)
        
        assert result["status"] == "rejected"
        assert any("REJECT" in issue for issue in result["issues"])
    
    def test_rejected_no_runners(self):
        """No runners should reject"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [],
            "quality_score": 0.8
        }
        
        result = validate_race(race)
        
        assert result["status"] == "rejected"
        assert any("REJECT" in issue for issue in result["issues"])
    
    def test_rejected_duplicate_names(self):
        """Duplicate horse names should reject"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": "Horse 1"}],
            "quality_score": 0.8,
            "quality_flags": ["duplicate_horse_names"]
        }
        
        result = validate_race(race)
        
        assert result["status"] == "rejected"
        assert any("Duplicate horse names" in issue for issue in result["issues"])
    
    def test_needs_review_low_quality(self):
        """Low quality score should trigger review"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
            "quality_score": 0.4,  # Low
            "quality_flags": []
        }
        
        result = validate_race(race)
        
        assert result["status"] == "needs_review"
        assert any("FLAG" in issue for issue in result["issues"])
    
    def test_needs_review_few_runners(self):
        """Few runners should trigger review"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": f"Horse {i}"} for i in range(3)],
            "quality_score": 0.8,
            "quality_flags": []
        }
        
        result = validate_race(race)
        
        assert result["status"] == "needs_review"
        assert any("few runners" in issue for issue in result["issues"])
    
    def test_needs_review_many_runners(self):
        """Many runners should trigger review"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": f"Horse {i}"} for i in range(35)],
            "quality_score": 0.8,
            "quality_flags": []
        }
        
        result = validate_race(race)
        
        assert result["status"] == "needs_review"
        assert any("many runners" in issue for issue in result["issues"])
    
    def test_needs_review_low_confidence_runners(self):
        """Many low confidence runners should trigger review"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
            "quality_score": 0.8,
            "quality_flags": ["many_low_confidence_runners"]
        }
        
        result = validate_race(race)
        
        assert result["status"] == "needs_review"
    
    def test_rejection_takes_precedence(self):
        """Rejection should take precedence over review flags"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [],  # No runners = reject
            "quality_score": 0.4,  # Also would trigger review
            "quality_flags": []
        }
        
        result = validate_race(race)
        
        assert result["status"] == "rejected"
    
    def test_quality_score_rounded(self):
        """Quality score should be rounded to 3 decimal places"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
            "quality_score": 0.123456789,
            "quality_flags": []
        }
        
        result = validate_race(race)
        
        assert result["quality_score"] == 0.123
    
    def test_missing_quality_score(self):
        """Should handle missing quality_score gracefully"""
        race = {
            "id": "race-1",
            "course": "Kempton",
            "distance": 2000,
            "runners": [{"horse_name": f"Horse {i}"} for i in range(10)]
        }
        
        result = validate_race(race)
        
        assert "quality_score" in result
        assert result["quality_score"] == 0.0
