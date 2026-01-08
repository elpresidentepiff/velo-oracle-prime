"""
Unit tests for agent graph orchestration

Tests state transitions and graph execution:
- Scout → Validate → Analyze → Critic → Archive
- Error handling with conditional edges
- Deterministic outputs with fixtures

Version: 1.0.0
"""

import pytest
from unittest.mock import patch, MagicMock
import json
from pathlib import Path

from agents.graph import (
    scout_node, validate_node, analyze_node, critic_node, archive_node,
    should_continue_after_scout, should_continue_after_validate,
    create_agent_graph, compile_agent_graph
)
from agents.models import Race, Runner


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
def initial_state():
    """Return initial state for testing"""
    return {
        "date": "2026-01-08",
        "dry_run": True,
        "races": [],
        "races_count": 0,
        "valid_races": [],
        "invalid_races": [],
        "validation_errors": [],
        "analyze_results": {},
        "critic_results": {},
        "archive_results": {},
        "races_processed": 0,
        "successes": 0,
        "failures": 0,
        "failure_details": [],
        "run_id": "test_run_001",
        "start_time": None,
        "end_time": None,
        "total_time_seconds": 0.0
    }


# ============================================================================
# NODE TESTS
# ============================================================================

def test_scout_node(initial_state):
    """Test scout_node execution"""
    result = scout_node(initial_state)
    
    assert "races" in result
    assert "races_count" in result
    assert "start_time" in result
    assert result["races_count"] == 5
    assert len(result["races"]) == 5


def test_validate_node(initial_state, validated_races):
    """Test validate_node execution"""
    initial_state["races"] = validated_races
    
    result = validate_node(initial_state)
    
    assert "valid_races" in result
    assert "invalid_races" in result
    assert "validation_errors" in result
    assert len(result["valid_races"]) == 2
    assert len(result["invalid_races"]) == 0


def test_validate_node_with_invalid_race(initial_state):
    """Test validate_node with invalid race"""
    invalid_race = Race(
        race_id="",  # Missing
        course="Ascot",
        race_date="2026-01-08",
        off_time="14:00",
        race_type="flat",
        distance=0,  # Invalid
        going="good",
        field_size=0,
        runners=[]  # No runners
    )
    
    initial_state["races"] = [invalid_race]
    
    result = validate_node(initial_state)
    
    assert len(result["valid_races"]) == 0
    assert len(result["invalid_races"]) == 1
    assert len(result["validation_errors"]) > 0


def test_analyze_node(initial_state, validated_races):
    """Test analyze_node execution"""
    initial_state["valid_races"] = validated_races
    
    result = analyze_node(initial_state)
    
    assert "analyze_results" in result
    assert len(result["analyze_results"]) == 2
    assert "race_001" in result["analyze_results"]
    assert "race_002" in result["analyze_results"]
    
    # Check analyze output structure
    analyze_output = result["analyze_results"]["race_001"]
    assert analyze_output.race_id == "race_001"
    assert len(analyze_output.predictions) > 0
    assert analyze_output.confidence > 0
    assert analyze_output.execution_time_ms > 0


def test_critic_node(initial_state, validated_races):
    """Test critic_node execution"""
    # First run analyze to get results
    initial_state["valid_races"] = validated_races
    analyze_result = analyze_node(initial_state)
    initial_state["analyze_results"] = analyze_result["analyze_results"]
    
    result = critic_node(initial_state)
    
    assert "critic_results" in result
    assert len(result["critic_results"]) == 2
    assert "race_001" in result["critic_results"]
    assert "race_002" in result["critic_results"]
    
    # Check critic output structure
    critic_output = result["critic_results"]["race_001"]
    assert critic_output.race_id == "race_001"
    assert critic_output.learning_event.event_type in ["prediction_accuracy", "data_quality", "anomaly"]
    assert critic_output.learning_event.severity in ["info", "warning", "error"]


def test_archive_node(initial_state, validated_races):
    """Test archive_node execution"""
    # Run through pipeline
    initial_state["valid_races"] = validated_races
    analyze_result = analyze_node(initial_state)
    initial_state["analyze_results"] = analyze_result["analyze_results"]
    
    critic_result = critic_node(initial_state)
    initial_state["critic_results"] = critic_result["critic_results"]
    
    initial_state["start_time"] = "2026-01-08T10:00:00.000Z"
    
    result = archive_node(initial_state)
    
    assert "archive_results" in result
    assert "races_processed" in result
    assert "successes" in result
    assert "failures" in result
    assert "end_time" in result
    assert "total_time_seconds" in result
    
    assert result["races_processed"] == 2
    assert result["successes"] == 2
    assert result["failures"] == 0


# ============================================================================
# CONDITIONAL EDGE TESTS
# ============================================================================

def test_should_continue_after_scout_with_races():
    """Test should_continue_after_scout with races found"""
    state = {"races_count": 5}
    assert should_continue_after_scout(state) == "validate"


def test_should_continue_after_scout_no_races():
    """Test should_continue_after_scout with no races"""
    state = {"races_count": 0}
    assert should_continue_after_scout(state) == "end"


def test_should_continue_after_validate_with_valid():
    """Test should_continue_after_validate with valid races"""
    state = {"valid_races": [{"race_id": "race_001"}]}
    assert should_continue_after_validate(state) == "analyze"


def test_should_continue_after_validate_no_valid():
    """Test should_continue_after_validate with no valid races"""
    state = {"valid_races": []}
    assert should_continue_after_validate(state) == "end"


# ============================================================================
# GRAPH TESTS
# ============================================================================

def test_create_agent_graph():
    """Test create_agent_graph returns valid graph"""
    graph = create_agent_graph()
    
    assert graph is not None
    # Graph should have nodes
    assert len(graph.nodes) == 5


def test_compile_agent_graph():
    """Test compile_agent_graph returns compiled runnable"""
    app = compile_agent_graph()
    
    assert app is not None


def test_full_graph_execution_dry_run():
    """Test full graph execution in dry-run mode"""
    app = compile_agent_graph()
    
    initial_state = {
        "date": "2026-01-08",
        "dry_run": True,
        "races": [],
        "races_count": 0,
        "valid_races": [],
        "invalid_races": [],
        "validation_errors": [],
        "analyze_results": {},
        "critic_results": {},
        "archive_results": {},
        "races_processed": 0,
        "successes": 0,
        "failures": 0,
        "failure_details": [],
        "run_id": "test_run_full",
        "start_time": None,
        "end_time": None,
        "total_time_seconds": 0.0
    }
    
    result = app.invoke(initial_state)
    
    # Check final state
    assert result["races_processed"] == 5
    assert result["successes"] == 5
    assert result["failures"] == 0
    assert result["total_time_seconds"] > 0
    assert result["end_time"] is not None


def test_graph_execution_no_races():
    """Test graph execution when scout finds no races"""
    app = compile_agent_graph()
    
    initial_state = {
        "date": "2026-01-08",
        "dry_run": True,
        "races": [],
        "races_count": 0,
        "valid_races": [],
        "invalid_races": [],
        "validation_errors": [],
        "analyze_results": {},
        "critic_results": {},
        "archive_results": {},
        "races_processed": 0,
        "successes": 0,
        "failures": 0,
        "failure_details": [],
        "run_id": "test_run_no_races",
        "start_time": None,
        "end_time": None,
        "total_time_seconds": 0.0
    }
    
    # Mock scout to return no races
    with patch("agents.tools.scout_races") as mock_scout:
        from agents.models import ScoutOutput
        mock_scout.return_value = ScoutOutput(races=[], count=0)
        
        result = app.invoke(initial_state)
        
        # Should terminate after scout
        assert result["races_count"] == 0
        # Archive should not run
        assert "end_time" not in result or result["end_time"] is None


def test_graph_execution_all_invalid():
    """Test graph execution when all races are invalid"""
    app = compile_agent_graph()
    
    initial_state = {
        "date": "2026-01-08",
        "dry_run": True,
        "races": [],
        "races_count": 0,
        "valid_races": [],
        "invalid_races": [],
        "validation_errors": [],
        "analyze_results": {},
        "critic_results": {},
        "archive_results": {},
        "races_processed": 0,
        "successes": 0,
        "failures": 0,
        "failure_details": [],
        "run_id": "test_run_invalid",
        "start_time": None,
        "end_time": None,
        "total_time_seconds": 0.0
    }
    
    # Mock scout to return invalid races
    invalid_races = [
        Race(
            race_id="",
            course="Ascot",
            race_date="2026-01-08",
            off_time="14:00",
            race_type="flat",
            distance=0,
            going="good",
            field_size=0,
            runners=[]
        )
    ]
    
    with patch("agents.tools.scout_races") as mock_scout:
        from agents.models import ScoutOutput
        mock_scout.return_value = ScoutOutput(races=invalid_races, count=1)
        
        result = app.invoke(initial_state)
        
        # Should have races but no valid ones
        assert result["races_count"] == 1
        assert len(result["valid_races"]) == 0
        # Should terminate after validate
        assert len(result["analyze_results"]) == 0
