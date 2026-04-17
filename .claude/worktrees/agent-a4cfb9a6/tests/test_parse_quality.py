"""
Unit tests for parse quality calculations
Tests the quality metadata calculation logic
"""

import pytest

from workers.ingestion_spine.parsers.quality import calculate_race_quality, calculate_runner_confidence


class TestRunnerConfidence:
    """Tests for calculate_runner_confidence function"""

    def test_perfect_runner_confidence(self):
        """Runner with all fields should have 1.0 confidence"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 5.0,
            "jockey": "Test Jockey",
            "trainer": "Test Trainer"
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence == 1.0
        assert flags == []
        assert method == "table"

    def test_missing_horse_name_penalty(self):
        """Missing horse name should reduce confidence by 0.5"""
        runner = {
            "odds": 5.0,
            "jockey": "Test Jockey"
            # horse_name missing
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence == 0.5  # 1.0 - 0.5
        assert "missing_horse_name" in flags
        assert method == "table"

    def test_missing_odds_penalty(self):
        """Missing odds should reduce confidence by 0.3"""
        runner = {
            "horse_name": "Test Horse",
            "jockey": "Test Jockey"
            # odds missing
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence == 0.7  # 1.0 - 0.3
        assert "missing_odds" in flags
        assert method == "table"

    def test_zero_odds_penalty(self):
        """Odds of 0 should be treated as missing"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 0,
            "jockey": "Test Jockey"
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence == 0.7  # 1.0 - 0.3
        assert "missing_odds" in flags

    def test_missing_jockey_penalty(self):
        """Missing jockey should reduce confidence by 0.1"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 5.0
            # jockey missing
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence == 0.9  # 1.0 - 0.1
        assert "missing_jockey" in flags
        assert method == "table"

    def test_estimated_odds_penalty(self):
        """Estimated odds should reduce confidence and change method"""
        runner = {
            "horse_name": "Test Horse",
            "odds": 5.0,
            "odds_estimated": True,
            "jockey": "Test Jockey"
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence == 0.8  # 1.0 - 0.2
        assert "estimated_odds" in flags
        assert method == "fallback"

    def test_multiple_penalties(self):
        """Multiple issues should accumulate penalties"""
        runner = {
            "horse_name": "Test Horse"
            # missing odds (-0.3) and jockey (-0.1)
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence == 0.6  # 1.0 - 0.3 - 0.1
        assert "missing_odds" in flags
        assert "missing_jockey" in flags
        assert len(flags) == 2

    def test_confidence_clamping_at_zero(self):
        """Confidence should never go below 0.0"""
        runner = {
            # missing everything
        }

        confidence, flags, method = calculate_runner_confidence(runner)

        assert confidence >= 0.0
        assert confidence <= 1.0
        assert len(flags) > 0


class TestRaceQuality:
    """Tests for calculate_race_quality function"""

    def test_perfect_race_quality(self):
        """Race with all fields and high-quality runners should score well"""
        race = {
            "course": "Kempton",
            "distance": "2000m"
        }
        runners = [
            {"horse_name": "Horse 1", "odds": 5.0, "confidence": 1.0},
            {"horse_name": "Horse 2", "odds": 3.0, "confidence": 1.0},
            {"horse_name": "Horse 3", "odds": 4.0, "confidence": 1.0},
            {"horse_name": "Horse 4", "odds": 2.0, "confidence": 1.0},
            {"horse_name": "Horse 5", "odds": 6.0, "confidence": 1.0}
        ]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert parse_conf == 1.0  # Average of runner confidences
        assert quality == 1.0  # No penalties
        assert flags == []

    def test_no_runners(self):
        """Race with no runners should score 0.0"""
        race = {"course": "Kempton", "distance": "2000m"}
        runners = []

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert parse_conf == 0.0
        assert quality == 0.0
        assert "no_runners" in flags

    def test_missing_course_penalty(self):
        """Missing course should reduce quality by 0.2"""
        race = {
            "distance": "2000m"
            # course missing
        }
        runners = [
            {"horse_name": "Horse 1", "confidence": 1.0},
            {"horse_name": "Horse 2", "confidence": 1.0},
            {"horse_name": "Horse 3", "confidence": 1.0},
            {"horse_name": "Horse 4", "confidence": 1.0}
        ]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert parse_conf == 1.0
        assert quality == 0.8  # 1.0 - 0.2
        assert "missing_course" in flags

    def test_missing_distance_penalty(self):
        """Missing distance should reduce quality by 0.1"""
        race = {
            "course": "Kempton"
            # distance missing
        }
        runners = [
            {"horse_name": "Horse 1", "confidence": 1.0},
            {"horse_name": "Horse 2", "confidence": 1.0},
            {"horse_name": "Horse 3", "confidence": 1.0},
            {"horse_name": "Horse 4", "confidence": 1.0}
        ]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert parse_conf == 1.0
        assert quality == 0.9  # 1.0 - 0.1
        assert "missing_distance" in flags

    def test_too_few_runners_penalty(self):
        """Less than 4 runners should reduce quality by 0.2"""
        race = {"course": "Kempton", "distance": "2000m"}
        runners = [
            {"horse_name": "Horse 1", "confidence": 1.0},
            {"horse_name": "Horse 2", "confidence": 1.0},
            {"horse_name": "Horse 3", "confidence": 1.0}
        ]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert parse_conf == 1.0
        assert quality == 0.8  # 1.0 - 0.2
        assert "too_few_runners" in flags

    def test_too_many_runners_penalty(self):
        """More than 30 runners should reduce quality by 0.1"""
        race = {"course": "Kempton", "distance": "2000m"}
        runners = [{"horse_name": f"Horse {i}", "confidence": 1.0} for i in range(31)]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert parse_conf == 1.0
        assert quality == 0.9  # 1.0 - 0.1
        assert "too_many_runners" in flags

    def test_duplicate_names_detection(self):
        """Race with duplicate names should be flagged"""
        race = {"course": "Kempton", "distance": "2000m"}
        runners = [
            {"horse_name": "Same Name", "odds": 5.0, "confidence": 1.0},
            {"horse_name": "Same Name", "odds": 3.0, "confidence": 1.0},
            {"horse_name": "Different", "odds": 4.0, "confidence": 1.0},
            {"horse_name": "Another", "odds": 2.0, "confidence": 1.0}
        ]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert "duplicate_horse_names" in flags
        assert quality <= 0.7  # 1.0 - 0.3 = 0.7

    def test_average_runner_confidence(self):
        """Parse confidence should be average of runner confidences"""
        race = {"course": "Kempton", "distance": "2000m"}
        runners = [
            {"horse_name": "Horse 1", "confidence": 1.0},
            {"horse_name": "Horse 2", "confidence": 0.8},
            {"horse_name": "Horse 3", "confidence": 0.6},
            {"horse_name": "Horse 4", "confidence": 0.4}
        ]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        expected_avg = (1.0 + 0.8 + 0.6 + 0.4) / 4
        assert parse_conf == pytest.approx(expected_avg)
        # Quality starts with parse_conf then may have penalties
        assert quality <= parse_conf

    def test_quality_clamping(self):
        """Quality score should be clamped between 0.0 and 1.0"""
        race = {
            # missing course and distance
        }
        runners = [
            {"horse_name": "Horse 1", "confidence": 0.1},
            {"horse_name": "Horse 2", "confidence": 0.1}
        ]

        parse_conf, quality, flags = calculate_race_quality(race, runners)

        assert 0.0 <= quality <= 1.0
        assert 0.0 <= parse_conf <= 1.0
