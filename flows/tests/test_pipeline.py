import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import date

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from prefect_flow.daily_pipeline import ingest_and_parse, atomic_insert_to_supabase

class MockRunner:
    def __init__(self, name, age=3):
        self.name = name
        self.age = age
        self.weight_lbs = 120
        self.jockey = "Jockey A"
        self.trainer = "Trainer A"
        self.or_rating = 80

class MockRace:
    def __init__(self, race_id, runners):
        self.race_id = race_id
        self.race_name = "Test Race"
        self.off_time = "14:00"
        self.distance_yards = 1200
        self.runners = runners
        self.has_non_runners = False
        self.runners_count = len(runners)

class MockMeeting:
    def __init__(self, course_name, races):
        self.course_name = course_name
        self.meeting_date = date(2026, 1, 9)
        self.races = races

@pytest.mark.asyncio
async def test_ingest_and_parse_failure():
    """Test that parse failure raises ValueError and stops the flow."""
    with patch('prefect_flow.daily_pipeline.parse_meeting') as mock_parse:
        mock_report = MagicMock()
        mock_report.success = False
        mock_report.errors = [MagicMock(message="Invalid runner count")]
        mock_parse.return_value = mock_report
        
        with pytest.raises(ValueError, match="Parse rejected"):
            ingest_and_parse(["mock.pdf"])

@pytest.mark.asyncio
async def test_atomic_insert_rollback_on_failure():
    """Test that insert failure raises exception."""
    meeting = MockMeeting("Wolverhampton", [
        MockRace("R1", [MockRunner("Horse 1")])
    ])
    
    with patch('prefect_flow.daily_pipeline.get_db_client') as mock_db_client:
        db = MagicMock()
        db.create_import_batch.side_effect = Exception("DB Connection Failed")
        mock_db_client.return_value = db
        
        with pytest.raises(Exception, match="DB Connection Failed"):
            await atomic_insert_to_supabase(meeting)

@pytest.mark.asyncio
async def test_pipeline_success_path():
    """Test the success path of the pipeline components."""
    meeting = MockMeeting("Wolverhampton", [
        MockRace("R1", [MockRunner("Horse 1")])
    ])
    
    with patch('prefect_flow.daily_pipeline.get_db_client') as mock_db_client:
        db = MagicMock()
        db.create_import_batch.return_value = "batch-123"
        db.insert_race.return_value = "race-123"
        db.insert_runner.return_value = "runner-123"
        mock_db_client.return_value = db
        
        batch_id = await atomic_insert_to_supabase(meeting)
        assert batch_id == "batch-123"
        assert db.create_import_batch.called
        assert db.insert_race.called
        assert db.insert_runner.called
        assert db.update_batch_status.called
