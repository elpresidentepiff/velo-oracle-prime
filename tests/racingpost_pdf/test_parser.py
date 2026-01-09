"""
Tests for racingpost_pdf module
"""

import pytest
from datetime import date, time

from workers.ingestion_spine.racingpost_pdf.types import Meeting, Race, Runner
from workers.ingestion_spine.racingpost_pdf.validate import validate_meeting
from workers.ingestion_spine.racingpost_pdf.normalize import (
    parse_distance,
    normalize_horse_name,
    is_placeholder_name,
    extract_age_from_line,
    extract_days_since_run,
)


class TestNormalization:
    """Test normalization functions"""
    
    def test_parse_distance_sprints(self):
        """Test distance parsing for sprints"""
        yards, furlongs, meters = parse_distance("5f")
        assert yards == 1100
        assert furlongs == 5.0
        assert meters == 1005
        
        yards, furlongs, meters = parse_distance("6f")
        assert yards == 1320
        assert furlongs == 6.0
        
        yards, furlongs, meters = parse_distance("7f")
        assert yards == 1540
        assert furlongs == 7.0
    
    def test_parse_distance_miles(self):
        """Test distance parsing for miles"""
        yards, furlongs, meters = parse_distance("1m")
        assert yards == 1760
        assert furlongs == 8.0
        
        yards, furlongs, meters = parse_distance("1m 2f")
        assert yards == 2200
        assert furlongs == 10.0
        
        yards, furlongs, meters = parse_distance("2m 4f")
        assert yards == 4400
        assert furlongs == 20.0
    
    def test_parse_distance_unmapped(self):
        """Test unmapped distance returns None"""
        yards, furlongs, meters = parse_distance("unknown")
        assert yards is None
        assert furlongs is None
        assert meters is None
    
    def test_normalize_horse_name(self):
        """Test horse name normalization"""
        assert normalize_horse_name("  Brave Empire ") == "BRAVE EMPIRE"
        assert normalize_horse_name("Sea The Stars (IRE)") == "SEA THE STARS"
        assert normalize_horse_name("Enable (GB)") == "ENABLE"
    
    def test_is_placeholder_name(self):
        """Test placeholder name detection"""
        assert is_placeholder_name("TBD") is True
        assert is_placeholder_name("RUNNER A") is True
        assert is_placeholder_name("RUNNER B") is True
        assert is_placeholder_name("UNKNOWN") is True
        assert is_placeholder_name("N/A") is True
        assert is_placeholder_name("-") is True
        
        assert is_placeholder_name("BRAVE EMPIRE") is False
        assert is_placeholder_name("SEA THE STARS") is False
    
    def test_extract_age_from_line(self):
        """Test age extraction from line"""
        assert extract_age_from_line("4  9-8  William Cox") == 4
        assert extract_age_from_line("3  10-0  John Smith") == 3
        assert extract_age_from_line("5  8-12  Jane Doe") == 5
        
        # Out of range - lines without valid ages
        assert extract_age_from_line("No numbers here") is None
        assert extract_age_from_line("1234567890") is None
    
    def test_extract_days_since_run(self):
        """Test days since run extraction"""
        assert extract_days_since_run("09353-  BRAVE EMPIRE  21 D 5") == 21
        assert extract_days_since_run("12345  TEST HORSE  10 D") == 10
        assert extract_days_since_run("No days marker") is None


class TestValidationGates:
    """Test hard validation gates"""
    
    def test_gate1_placeholder_names(self):
        """Gate 1: No placeholder names"""
        meeting = Meeting(
            course_code="TEST",
            course_name="Test",
            meeting_date=date(2026, 1, 9),
            races=[
                Race(
                    race_id="test_001",
                    course="Test",
                    off_time=time(13, 30),
                    distance_text="6f",
                    distance_yards=1320,
                    distance_furlongs=6.0,
                    runners_count=1,
                    runners=[
                        Runner(runner_number=1, name="TBD", age=4)
                    ]
                )
            ]
        )
        
        is_valid, errors = validate_meeting(meeting)
        assert not is_valid
        assert any("Placeholder name" in e for e in errors)
    
    def test_gate2_impossible_age(self):
        """Gate 2: Impossible ages (not 2-15)"""
        meeting = Meeting(
            course_code="TEST",
            course_name="Test",
            meeting_date=date(2026, 1, 9),
            races=[
                Race(
                    race_id="test_002",
                    course="Test",
                    off_time=time(13, 30),
                    distance_text="6f",
                    distance_yards=1320,
                    distance_furlongs=6.0,
                    runners_count=1,
                    runners=[
                        Runner(runner_number=1, name="Test Horse", age=122)  # Bug!
                    ]
                )
            ]
        )
        
        is_valid, errors = validate_meeting(meeting)
        assert not is_valid
        assert any("Impossible age" in e for e in errors)
    
    def test_gate3_runner_count_mismatch(self):
        """Gate 3: Runner count consistency"""
        meeting = Meeting(
            course_code="TEST",
            course_name="Test",
            meeting_date=date(2026, 1, 9),
            races=[
                Race(
                    race_id="test_003",
                    course="Test",
                    off_time=time(13, 30),
                    distance_text="6f",
                    distance_yards=1320,
                    distance_furlongs=6.0,
                    runners_count=5,  # Declared 5
                    runners=[
                        Runner(runner_number=1, name="Horse A", age=4),
                        Runner(runner_number=2, name="Horse B", age=4),
                        # Only 2 runners, but declared 5
                    ]
                )
            ]
        )
        
        is_valid, errors = validate_meeting(meeting)
        assert not is_valid
        assert any("Runner count mismatch" in e for e in errors)
    
    def test_gate4_distance_not_mapped(self):
        """Gate 4: Distance must be mapped"""
        meeting = Meeting(
            course_code="TEST",
            course_name="Test",
            meeting_date=date(2026, 1, 9),
            races=[
                Race(
                    race_id="test_004",
                    course="Test",
                    off_time=time(13, 30),
                    distance_text="unknown",
                    distance_yards=None,  # Not mapped!
                    runners_count=1,
                    runners=[
                        Runner(runner_number=1, name="Test Horse", age=4)
                    ]
                )
            ]
        )
        
        is_valid, errors = validate_meeting(meeting)
        assert not is_valid
        assert any("Distance not mapped" in e for e in errors)
    
    def test_gate5_distance_consistency(self):
        """Gate 5: Distance consistency check"""
        meeting = Meeting(
            course_code="TEST",
            course_name="Test",
            meeting_date=date(2026, 1, 9),
            races=[
                Race(
                    race_id="test_005",
                    course="Test",
                    off_time=time(13, 30),
                    distance_text="6f",
                    distance_yards=1320,
                    distance_furlongs=999.0,  # Inconsistent!
                    runners_count=1,
                    runners=[
                        Runner(runner_number=1, name="Test Horse", age=4)
                    ]
                )
            ]
        )
        
        is_valid, errors = validate_meeting(meeting)
        assert not is_valid
        assert any("Distance mismatch" in e for e in errors)
    
    def test_valid_meeting_passes(self):
        """Valid meeting should pass all gates"""
        meeting = Meeting(
            course_code="WOL",
            course_name="Wolverhampton",
            meeting_date=date(2026, 1, 9),
            races=[
                Race(
                    race_id="20260109_Wolverhampton_1330",
                    course="Wolverhampton",
                    off_time=time(13, 30),
                    race_name="Handicap",
                    distance_text="6f",
                    distance_yards=1320,
                    distance_furlongs=6.0,
                    distance_meters=1207,
                    runners_count=8,
                    runners=[
                        Runner(runner_number=1, name="BRAVE EMPIRE", age=4, weight="9-8"),
                        Runner(runner_number=2, name="FAST HORSE", age=5, weight="9-10"),
                        Runner(runner_number=3, name="QUICK RUNNER", age=3, weight="9-6"),
                        Runner(runner_number=4, name="SPEED DEMON", age=4, weight="9-9"),
                        Runner(runner_number=5, name="LIGHTNING BOLT", age=6, weight="9-11"),
                        Runner(runner_number=6, name="THUNDER STRIKE", age=4, weight="9-7"),
                        Runner(runner_number=7, name="STORM CHASER", age=5, weight="9-8"),
                        Runner(runner_number=8, name="WIND RUNNER", age=4, weight="9-10"),
                    ]
                )
            ]
        )
        
        is_valid, errors = validate_meeting(meeting)
        assert is_valid
        assert len(errors) == 0


class TestTypes:
    """Test Pydantic models"""
    
    def test_runner_model(self):
        """Test Runner model"""
        runner = Runner(
            runner_number=1,
            name="BRAVE EMPIRE",
            age=4,
            weight="9-8",
            days_since_run=21,
            jockey="William Cox",
            or_rating=70
        )
        
        assert runner.runner_number == 1
        assert runner.name == "BRAVE EMPIRE"
        assert runner.age == 4
        assert runner.days_since_run == 21
    
    def test_race_model(self):
        """Test Race model"""
        race = Race(
            race_id="test_001",
            course="Wolverhampton",
            off_time=time(13, 30),
            distance_text="6f",
            distance_yards=1320,
            distance_furlongs=6.0,
            runners_count=2,
            runners=[
                Runner(runner_number=1, name="Horse A", age=4),
                Runner(runner_number=2, name="Horse B", age=5),
            ]
        )
        
        assert race.race_id == "test_001"
        assert len(race.runners) == 2
        assert race.distance_yards == 1320
    
    def test_meeting_model(self):
        """Test Meeting model"""
        meeting = Meeting(
            course_code="WOL",
            course_name="Wolverhampton",
            meeting_date=date(2026, 1, 9),
            races=[]
        )
        
        assert meeting.course_code == "WOL"
        assert meeting.meeting_date == date(2026, 1, 9)
