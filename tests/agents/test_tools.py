"""
Unit tests for agent tool functions

Tests each tool function in isolation with mocked dependencies:
- scout_races
- validate_race
- analyze_race
- critic_race
- archive_results

Version: 1.0.0
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from agents.models import (
    Race, Runner,
    ScoutInput, ValidateInput, AnalyzeInput, CriticInput, ArchiveInput
)
from agents.tools import (
    scout_races, validate_race, analyze_race, critic_race, archive_results
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def validated_races(fixtures_dir):
    """Load validated races fixture"""
    with open(fixtures_dir / "validated_races.json") as f:
        data = json.load(f)
    return [Race(**race_data) for race_data in data]


@pytest.fixture
def engine_results(fixtures_dir):
    """Load engine results fixture"""
    with open(fixtures_dir / "engine_results.json") as f:
        return json.load(f)


@pytest.fixture
def sample_race(validated_races):
    """Return first race from fixtures"""
    return validated_races[0]


# ============================================================================
# SCOUT TESTS
# ============================================================================

def test_scout_races_dry_run():
    """Test scout_races in dry-run mode"""
    scout_input = ScoutInput(date="2026-01-08")
    result = scout_races(scout_input, dry_run=True)
    
    assert result.count == 5
    assert len(result.races) == 5
    assert result.races[0].race_id == "race_1"
    assert result.races[0].course == "Ascot"
    assert len(result.races[0].runners) == 8


@patch("agents.tools.get_supabase_client")
def test_scout_races_no_client(mock_get_client):
    """Test scout_races when Supabase client fails"""
    mock_get_client.return_value = None
    
    scout_input = ScoutInput(date="2026-01-08")
    result = scout_races(scout_input, dry_run=False)
    
    assert result.count == 0
    assert len(result.races) == 0


@patch("agents.tools.get_supabase_client")
def test_scout_races_with_data(mock_get_client, validated_races):
    """Test scout_races with mocked Supabase data"""
    # Mock Supabase client
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    # Mock races query
    mock_races_response = MagicMock()
    mock_races_response.data = [
        {
            "race_id": "race_001",
            "course": "Ascot",
            "race_date": "2026-01-08",
            "off_time": "14:00",
            "race_type": "flat",
            "distance": 1760,
            "going": "good",
            "field_size": 3,
            "batch_status": "validated"
        }
    ]
    
    # Mock runners query
    mock_runners_response = MagicMock()
    mock_runners_response.data = [
        {
            "runner_id": "runner_001_1",
            "horse": "Thunder Bolt",
            "weight_lbs": 126,
            "jockey": "John Smith",
            "trainer": "Jane Doe",
            "odds_live": 5.5,
            "claims_lbs": 0,
            "stall": 3,
            "OR": 85,
            "TS": 75,
            "RPR": 80
        }
    ]
    
    # Setup mock chain
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_races_response
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_runners_response
    
    scout_input = ScoutInput(date="2026-01-08")
    result = scout_races(scout_input, dry_run=False)
    
    assert result.count == 1
    assert len(result.races) == 1
    assert result.races[0].race_id == "race_001"


# ============================================================================
# VALIDATE TESTS
# ============================================================================

def test_validate_race_valid_races(validated_races):
    """Test validate_race with valid races"""
    validate_input = ValidateInput(races=validated_races)
    result = validate_race(validate_input)
    
    assert len(result.valid_races) == 2
    assert len(result.invalid_races) == 0
    assert len(result.validation_errors) == 0


def test_validate_race_missing_race_id():
    """Test validate_race with missing race_id"""
    invalid_race = Race(
        race_id="",  # Missing
        course="Ascot",
        race_date="2026-01-08",
        off_time="14:00",
        race_type="flat",
        distance=1760,
        going="good",
        field_size=3,
        runners=[
            Runner(
                runner_id="r1",
                horse="Horse 1",
                weight_lbs=126,
                jockey="Jockey 1",
                trainer="Trainer 1",
                odds_live=5.0
            )
        ]
    )
    
    validate_input = ValidateInput(races=[invalid_race])
    result = validate_race(validate_input)
    
    assert len(result.valid_races) == 0
    assert len(result.invalid_races) == 1
    assert "Missing race_id" in result.invalid_races[0]["errors"]


def test_validate_race_no_runners():
    """Test validate_race with no runners"""
    invalid_race = Race(
        race_id="race_001",
        course="Ascot",
        race_date="2026-01-08",
        off_time="14:00",
        race_type="flat",
        distance=1760,
        going="good",
        field_size=0,
        runners=[]  # No runners
    )
    
    validate_input = ValidateInput(races=[invalid_race])
    result = validate_race(validate_input)
    
    assert len(result.valid_races) == 0
    assert len(result.invalid_races) == 1
    assert any("No runners" in err for err in result.invalid_races[0]["errors"])


def test_validate_race_invalid_distance():
    """Test validate_race with invalid distance"""
    invalid_race = Race(
        race_id="race_001",
        course="Ascot",
        race_date="2026-01-08",
        off_time="14:00",
        race_type="flat",
        distance=0,  # Invalid
        going="good",
        field_size=1,
        runners=[
            Runner(
                runner_id="r1",
                horse="Horse 1",
                weight_lbs=126,
                jockey="Jockey 1",
                trainer="Trainer 1",
                odds_live=5.0
            )
        ]
    )
    
    validate_input = ValidateInput(races=[invalid_race])
    result = validate_race(validate_input)
    
    assert len(result.valid_races) == 0
    assert len(result.invalid_races) == 1
    assert any("Invalid distance" in err for err in result.invalid_races[0]["errors"])


# ============================================================================
# ANALYZE TESTS
# ============================================================================

def test_analyze_race_dry_run(sample_race):
    """Test analyze_race in dry-run mode"""
    analyze_input = AnalyzeInput(
        race_id=sample_race.race_id,
        runners=sample_race.runners
    )
    
    result = analyze_race(analyze_input, dry_run=True)
    
    assert result.race_id == sample_race.race_id
    assert len(result.predictions) == len(sample_race.runners)
    assert result.confidence == 0.75
    assert result.execution_time_ms >= 0  # Allow 0 or greater


@patch("agents.tools.get_engine_runner")
def test_analyze_race_no_engine(mock_get_engine):
    """Test analyze_race when engine import fails"""
    mock_get_engine.return_value = (None, None)
    
    analyze_input = AnalyzeInput(
        race_id="race_001",
        runners=[
            Runner(
                runner_id="r1",
                horse="Horse 1",
                weight_lbs=126,
                jockey="Jockey 1",
                trainer="Trainer 1",
                odds_live=5.0
            )
        ]
    )
    
    result = analyze_race(analyze_input, dry_run=False)
    
    assert result.race_id == "race_001"
    assert len(result.predictions) == 0
    assert result.confidence == 0.0


# ============================================================================
# CRITIC TESTS
# ============================================================================

def test_critic_race_good_prediction(engine_results):
    """Test critic_race with good prediction"""
    from agents.models import AnalyzeOutput
    
    analyze_output = AnalyzeOutput(
        race_id="race_001",
        predictions=engine_results["race_001"]["predictions"],
        confidence=engine_results["race_001"]["confidence"],
        execution_time_ms=engine_results["race_001"]["execution_time_ms"]
    )
    
    critic_input = CriticInput(
        race_id="race_001",
        analyze_output=analyze_output
    )
    
    result = critic_race(critic_input)
    
    assert result.race_id == "race_001"
    # Event type depends on data completeness
    assert result.learning_event.event_type in ["prediction_accuracy", "data_quality", "anomaly"]
    assert result.learning_event.severity == "info"
    assert result.learning_event.prediction_quality_score == 0.78
    assert len(result.learning_event.anomalies) == 0


def test_critic_race_low_confidence():
    """Test critic_race with low confidence prediction"""
    from agents.models import AnalyzeOutput
    
    analyze_output = AnalyzeOutput(
        race_id="race_002",
        predictions={"Horse 1": 0.2},
        confidence=0.3,  # Low confidence
        execution_time_ms=150
    )
    
    critic_input = CriticInput(
        race_id="race_002",
        analyze_output=analyze_output
    )
    
    result = critic_race(critic_input)
    
    assert result.learning_event.severity == "error"
    assert any("Low confidence" in a for a in result.learning_event.anomalies)


def test_critic_race_slow_execution():
    """Test critic_race with slow execution"""
    from agents.models import AnalyzeOutput
    
    analyze_output = AnalyzeOutput(
        race_id="race_003",
        predictions={"Horse 1": 0.5},
        confidence=0.75,
        execution_time_ms=15000  # Slow
    )
    
    critic_input = CriticInput(
        race_id="race_003",
        analyze_output=analyze_output
    )
    
    result = critic_race(critic_input)
    
    assert any("Slow execution" in a for a in result.learning_event.anomalies)


def test_critic_race_no_predictions():
    """Test critic_race with no predictions"""
    from agents.models import AnalyzeOutput
    
    analyze_output = AnalyzeOutput(
        race_id="race_004",
        predictions={},  # No predictions
        confidence=0.0,
        execution_time_ms=100
    )
    
    critic_input = CriticInput(
        race_id="race_004",
        analyze_output=analyze_output
    )
    
    result = critic_race(critic_input)
    
    assert any("No predictions" in a for a in result.learning_event.anomalies)
    assert result.learning_event.event_type in ["anomaly", "data_quality"]


# ============================================================================
# ARCHIVE TESTS
# ============================================================================

def test_archive_results_dry_run(engine_results):
    """Test archive_results in dry-run mode"""
    from agents.models import AnalyzeOutput, LearningEvent
    
    analyze_output = AnalyzeOutput(
        race_id="race_001",
        predictions=engine_results["race_001"]["predictions"],
        confidence=engine_results["race_001"]["confidence"],
        execution_time_ms=engine_results["race_001"]["execution_time_ms"]
    )
    
    learning_event = LearningEvent(
        race_id="race_001",
        event_type="prediction_accuracy",
        severity="info",
        feedback={"test": "data"}
    )
    
    archive_input = ArchiveInput(
        race_id="race_001",
        run_id="run_test_001",
        analyze_output=analyze_output,
        learning_event=learning_event
    )
    
    result = archive_results(archive_input, dry_run=True)
    
    assert result.success is True
    assert result.race_id == "race_001"
    assert result.run_id == "run_test_001"
    assert result.error is None


@patch("agents.tools.get_supabase_client")
def test_archive_results_no_client(mock_get_client):
    """Test archive_results when Supabase client fails"""
    from agents.models import AnalyzeOutput, LearningEvent
    
    mock_get_client.return_value = None
    
    analyze_output = AnalyzeOutput(
        race_id="race_001",
        predictions={"Horse 1": 0.5},
        confidence=0.75,
        execution_time_ms=100
    )
    
    learning_event = LearningEvent(
        race_id="race_001",
        event_type="prediction_accuracy",
        severity="info",
        feedback={}
    )
    
    archive_input = ArchiveInput(
        race_id="race_001",
        run_id="run_test_001",
        analyze_output=analyze_output,
        learning_event=learning_event
    )
    
    result = archive_results(archive_input, dry_run=False)
    
    assert result.success is False
    assert result.error == "Failed to connect to Supabase"


@patch("agents.tools.get_supabase_client")
def test_archive_results_with_success(mock_get_client):
    """Test archive_results with successful write"""
    from agents.models import AnalyzeOutput, LearningEvent
    
    # Mock Supabase client
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    # Mock successful inserts
    mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock()
    
    analyze_output = AnalyzeOutput(
        race_id="race_001",
        predictions={"Horse 1": 0.5},
        confidence=0.75,
        execution_time_ms=100
    )
    
    learning_event = LearningEvent(
        race_id="race_001",
        event_type="prediction_accuracy",
        severity="info",
        feedback={}
    )
    
    archive_input = ArchiveInput(
        race_id="race_001",
        run_id="run_test_001",
        analyze_output=analyze_output,
        learning_event=learning_event
    )
    
    result = archive_results(archive_input, dry_run=False)
    
    assert result.success is True
    assert result.race_id == "race_001"
    assert mock_client.table.call_count >= 2  # Called for engine_runs and learning_events
