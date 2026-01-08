"""
LangGraph state graph for agent orchestration

Implements the autonomous agent pipeline:
Scout → Validate → Analyze → Critic → Archive

Each node processes races and updates the shared state.

Version: 1.0.0
"""

import logging
from typing import Dict, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from agents.models import (
    AgentState,
    ScoutInput, ValidateInput, AnalyzeInput, CriticInput, ArchiveInput
)
from agents.tools import (
    scout_races, validate_race, analyze_race, critic_race, archive_results
)

logger = logging.getLogger(__name__)


# ============================================================================
# NODE FUNCTIONS
# ============================================================================

def scout_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scout node: Load validated races from Supabase
    
    Updates state with:
    - races: List of races found
    - races_count: Number of races
    """
    logger.info("=" * 80)
    logger.info("SCOUT NODE: Loading races from Supabase")
    logger.info("=" * 80)
    
    state["start_time"] = datetime.utcnow().isoformat()
    
    scout_input = ScoutInput(date=state["date"])
    scout_output = scout_races(scout_input, dry_run=state.get("dry_run", False))
    
    logger.info(f"Scout: Found {scout_output.count} races")
    
    return {
        "races": scout_output.races,
        "races_count": scout_output.count,
        "start_time": state["start_time"]
    }


def validate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate node: Validate race data integrity
    
    Updates state with:
    - valid_races: List of valid races
    - invalid_races: List of invalid races with errors
    - validation_errors: List of validation error messages
    """
    logger.info("=" * 80)
    logger.info("VALIDATE NODE: Validating race data")
    logger.info("=" * 80)
    
    validate_input = ValidateInput(races=state["races"])
    validate_output = validate_race(validate_input)
    
    logger.info(f"Validate: {len(validate_output.valid_races)} valid, {len(validate_output.invalid_races)} invalid")
    
    return {
        "valid_races": validate_output.valid_races,
        "invalid_races": validate_output.invalid_races,
        "validation_errors": validate_output.validation_errors
    }


def analyze_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze node: Run engine analysis for each valid race
    
    Updates state with:
    - analyze_results: Dict mapping race_id to AnalyzeOutput
    """
    logger.info("=" * 80)
    logger.info("ANALYZE NODE: Running engine analysis")
    logger.info("=" * 80)
    
    analyze_results = {}
    
    for race in state["valid_races"]:
        logger.info(f"Analyze: Processing race {race.race_id}")
        
        analyze_input = AnalyzeInput(
            race_id=race.race_id,
            runners=race.runners
        )
        
        analyze_output = analyze_race(analyze_input, dry_run=state.get("dry_run", False))
        analyze_results[race.race_id] = analyze_output
        
        logger.info(f"Analyze: Race {race.race_id} - Confidence: {analyze_output.confidence:.2f}")
    
    return {
        "analyze_results": analyze_results
    }


def critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Critic node: Evaluate predictions and create learning events
    
    Updates state with:
    - critic_results: Dict mapping race_id to CriticOutput
    """
    logger.info("=" * 80)
    logger.info("CRITIC NODE: Evaluating predictions")
    logger.info("=" * 80)
    
    critic_results = {}
    
    for race_id, analyze_output in state["analyze_results"].items():
        logger.info(f"Critic: Evaluating race {race_id}")
        
        critic_input = CriticInput(
            race_id=race_id,
            analyze_output=analyze_output
        )
        
        critic_output = critic_race(critic_input)
        critic_results[race_id] = critic_output
        
        logger.info(f"Critic: Race {race_id} - Event: {critic_output.learning_event.event_type}, Severity: {critic_output.learning_event.severity}")
    
    return {
        "critic_results": critic_results
    }


def archive_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Archive node: Write results to Supabase
    
    Updates state with:
    - archive_results: Dict mapping race_id to ArchiveOutput
    - races_processed: Total races processed
    - successes: Number of successful archives
    - failures: Number of failed archives
    - failure_details: List of failure details
    - end_time: Timestamp when processing completed
    - total_time_seconds: Total execution time
    """
    logger.info("=" * 80)
    logger.info("ARCHIVE NODE: Writing results to Supabase")
    logger.info("=" * 80)
    
    archive_results = {}
    successes = 0
    failures = 0
    failure_details = []
    
    for race_id, analyze_output in state["analyze_results"].items():
        logger.info(f"Archive: Storing race {race_id}")
        
        critic_output = state["critic_results"].get(race_id)
        if not critic_output:
            logger.error(f"Archive: No critic output for race {race_id}")
            failures += 1
            failure_details.append({
                "race_id": race_id,
                "error": "Missing critic output"
            })
            continue
        
        # Generate unique run_id for this race
        run_id = f"{state['run_id']}_{race_id}"
        
        archive_input = ArchiveInput(
            race_id=race_id,
            run_id=run_id,
            analyze_output=analyze_output,
            learning_event=critic_output.learning_event
        )
        
        archive_output = archive_results(archive_input, dry_run=state.get("dry_run", False))
        archive_results[race_id] = archive_output
        
        if archive_output.success:
            successes += 1
            logger.info(f"Archive: Successfully stored race {race_id}")
        else:
            failures += 1
            failure_details.append({
                "race_id": race_id,
                "error": archive_output.error
            })
            logger.error(f"Archive: Failed to store race {race_id}: {archive_output.error}")
    
    # Calculate total time
    end_time = datetime.utcnow().isoformat()
    start_dt = datetime.fromisoformat(state["start_time"])
    end_dt = datetime.fromisoformat(end_time)
    total_time_seconds = (end_dt - start_dt).total_seconds()
    
    logger.info("=" * 80)
    logger.info(f"ARCHIVE COMPLETE: {successes} successes, {failures} failures")
    logger.info(f"Total time: {total_time_seconds:.2f}s")
    logger.info("=" * 80)
    
    return {
        "archive_results": archive_results,
        "races_processed": len(state["analyze_results"]),
        "successes": successes,
        "failures": failures,
        "failure_details": failure_details,
        "end_time": end_time,
        "total_time_seconds": total_time_seconds
    }


# ============================================================================
# CONDITIONAL EDGES
# ============================================================================

def should_continue_after_scout(state: Dict[str, Any]) -> str:
    """Decide whether to continue after scout"""
    if state["races_count"] == 0:
        logger.warning("Scout: No races found - ending workflow")
        return "end"
    return "validate"


def should_continue_after_validate(state: Dict[str, Any]) -> str:
    """Decide whether to continue after validate"""
    if not state["valid_races"]:
        logger.warning("Validate: No valid races - ending workflow")
        return "end"
    return "analyze"


# ============================================================================
# GRAPH BUILDER
# ============================================================================

def create_agent_graph() -> StateGraph:
    """
    Create the LangGraph state graph for agent orchestration
    
    Graph structure:
    START → Scout → Validate → Analyze → Critic → Archive → END
    
    Conditional edges:
    - Scout → END if no races found
    - Validate → END if no valid races
    
    Returns:
        StateGraph instance
    """
    # Create state graph
    workflow = StateGraph(dict)
    
    # Add nodes
    workflow.add_node("scout", scout_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("archive", archive_node)
    
    # Set entry point
    workflow.set_entry_point("scout")
    
    # Add edges
    workflow.add_conditional_edges(
        "scout",
        should_continue_after_scout,
        {
            "validate": "validate",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "validate",
        should_continue_after_validate,
        {
            "analyze": "analyze",
            "end": END
        }
    )
    
    workflow.add_edge("analyze", "critic")
    workflow.add_edge("critic", "archive")
    workflow.add_edge("archive", END)
    
    logger.info("Agent graph created successfully")
    return workflow


def compile_agent_graph() -> Any:
    """
    Compile the agent graph into an executable runnable
    
    Returns:
        Compiled graph
    """
    workflow = create_agent_graph()
    app = workflow.compile()
    logger.info("Agent graph compiled successfully")
    return app
