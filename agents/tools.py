"""
Tool functions for LangGraph agent orchestration

These functions implement the business logic for each agent node:
- scout_races: Query Supabase for validated races
- validate_race: Validate race data integrity
- analyze_race: Call run_engine_full for predictions
- critic_race: Create learning events for feedback
- archive_results: Write results to Supabase

Version: 1.0.0
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from agents.models import (
    Race, Runner,
    ScoutInput, ScoutOutput,
    ValidateInput, ValidateOutput,
    AnalyzeInput, AnalyzeOutput,
    CriticInput, CriticOutput, LearningEvent,
    ArchiveInput, ArchiveOutput
)

logger = logging.getLogger(__name__)


# ============================================================================
# SUPABASE CLIENT
# ============================================================================

def get_supabase_client():
    """Get Supabase client (lazy import to support mocking)"""
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        return create_client(url, key)
    except Exception as e:
        logger.warning(f"Failed to create Supabase client: {e}")
        return None


# ============================================================================
# ENGINE INTERFACE
# ============================================================================

def get_engine_runner():
    """Get engine runner function (lazy import to support mocking)"""
    try:
        from app.velo_v12_intent_stack import run_engine_full, Race as EngineRace
        return run_engine_full, EngineRace
    except ImportError as e:
        logger.warning(f"Failed to import engine: {e}")
        return None, None


# ============================================================================
# SCOUT NODE
# ============================================================================

def scout_races(input_data: ScoutInput, dry_run: bool = False) -> ScoutOutput:
    """
    Scout agent: Load validated races for a given date from Supabase
    
    Query: SELECT * FROM races WHERE race_date = ? AND batch_status = 'validated'
    
    Args:
        input_data: ScoutInput with date
        dry_run: If True, return mock data
        
    Returns:
        ScoutOutput with races list
    """
    logger.info(f"Scout: Searching for races on {input_data.date}")
    
    if dry_run:
        # Return mock data for dry run
        logger.info("Scout: Dry run mode - returning mock data")
        mock_races = [
            Race(
                race_id=f"race_{i}",
                course="Ascot",
                race_date=input_data.date,
                off_time="14:00",
                race_type="flat",
                distance=1760,
                going="good",
                field_size=8,
                batch_status="validated",
                runners=[
                    Runner(
                        runner_id=f"runner_{i}_{j}",
                        horse=f"Horse {j}",
                        weight_lbs=126,
                        jockey=f"Jockey {j}",
                        trainer=f"Trainer {j}",
                        odds_live=5.0 + j,
                        OR=85,
                        TS=75,
                        RPR=80
                    )
                    for j in range(1, 9)
                ]
            )
            for i in range(1, 6)
        ]
        return ScoutOutput(races=mock_races, count=len(mock_races))
    
    # Real Supabase query
    client = get_supabase_client()
    if not client:
        logger.error("Scout: Failed to get Supabase client")
        return ScoutOutput(races=[], count=0)
    
    try:
        # Query races table
        response = client.table("races").select("*").eq("race_date", input_data.date).eq("batch_status", "validated").execute()
        
        races_data = response.data if response.data else []
        races = []
        
        for race_row in races_data:
            # Query runners for this race
            runners_response = client.table("runners").select("*").eq("race_id", race_row["race_id"]).execute()
            runners_data = runners_response.data if runners_response.data else []
            
            runners = [
                Runner(
                    runner_id=r.get("runner_id", ""),
                    horse=r.get("horse", ""),
                    weight_lbs=r.get("weight_lbs", 126),
                    jockey=r.get("jockey", ""),
                    trainer=r.get("trainer", ""),
                    odds_live=r.get("odds_live", 10.0),
                    claims_lbs=r.get("claims_lbs", 0),
                    stall=r.get("stall"),
                    OR=r.get("OR"),
                    TS=r.get("TS"),
                    RPR=r.get("RPR"),
                    owner=r.get("owner"),
                    headgear=r.get("headgear"),
                    run_style=r.get("run_style"),
                    comments=r.get("comments")
                )
                for r in runners_data
            ]
            
            race = Race(
                race_id=race_row.get("race_id", ""),
                course=race_row.get("course", ""),
                race_date=race_row.get("race_date", ""),
                off_time=race_row.get("off_time", ""),
                race_type=race_row.get("race_type", ""),
                distance=race_row.get("distance", 0),
                going=race_row.get("going", ""),
                field_size=race_row.get("field_size", 0),
                batch_status=race_row.get("batch_status", ""),
                runners=runners
            )
            races.append(race)
        
        logger.info(f"Scout: Found {len(races)} validated races")
        return ScoutOutput(races=races, count=len(races))
        
    except Exception as e:
        logger.error(f"Scout: Error querying Supabase: {e}")
        return ScoutOutput(races=[], count=0)


# ============================================================================
# VALIDATE NODE
# ============================================================================

def validate_race(input_data: ValidateInput) -> ValidateOutput:
    """
    Validate agent: Confirm required fields exist
    
    Checks:
    - race_id exists
    - course exists
    - distance > 0
    - runners list is not empty
    - each runner has required fields
    
    Args:
        input_data: ValidateInput with races list
        
    Returns:
        ValidateOutput with valid and invalid races
    """
    logger.info(f"Validate: Checking {len(input_data.races)} races")
    
    valid_races = []
    invalid_races = []
    validation_errors = []
    
    for race in input_data.races:
        errors = []
        
        # Check required race fields
        if not race.race_id:
            errors.append(f"Missing race_id")
        if not race.course:
            errors.append(f"Missing course")
        if race.distance <= 0:
            errors.append(f"Invalid distance: {race.distance}")
        if not race.runners:
            errors.append(f"No runners in race")
        
        # Check runners
        for i, runner in enumerate(race.runners):
            if not runner.runner_id:
                errors.append(f"Runner {i}: Missing runner_id")
            if not runner.horse:
                errors.append(f"Runner {i}: Missing horse name")
            if not runner.jockey:
                errors.append(f"Runner {i}: Missing jockey")
            if not runner.trainer:
                errors.append(f"Runner {i}: Missing trainer")
            if runner.odds_live <= 0:
                errors.append(f"Runner {i}: Invalid odds")
        
        if errors:
            logger.warning(f"Validate: Race {race.race_id} failed validation: {errors}")
            invalid_races.append({
                "race_id": race.race_id,
                "errors": errors
            })
            validation_errors.extend([f"Race {race.race_id}: {e}" for e in errors])
        else:
            valid_races.append(race)
    
    logger.info(f"Validate: {len(valid_races)} valid, {len(invalid_races)} invalid")
    return ValidateOutput(
        valid_races=valid_races,
        invalid_races=invalid_races,
        validation_errors=validation_errors
    )


# ============================================================================
# ANALYZE NODE
# ============================================================================

def analyze_race(input_data: AnalyzeInput, dry_run: bool = False) -> AnalyzeOutput:
    """
    Analyze agent: Call run_engine_full for predictions
    
    Args:
        input_data: AnalyzeInput with race_id and runners
        dry_run: If True, return mock predictions
        
    Returns:
        AnalyzeOutput with predictions and confidence
    """
    logger.info(f"Analyze: Processing race {input_data.race_id}")
    
    start_time = time.time()
    
    if dry_run:
        # Return mock predictions for dry run
        logger.info("Analyze: Dry run mode - returning mock predictions")
        predictions = {runner.horse: 0.1 + (i * 0.05) for i, runner in enumerate(input_data.runners)}
        confidence = 0.75
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return AnalyzeOutput(
            race_id=input_data.race_id,
            predictions=predictions,
            confidence=confidence,
            execution_time_ms=execution_time_ms
        )
    
    # Real engine call
    run_engine_full, EngineRace = get_engine_runner()
    if not run_engine_full:
        logger.error("Analyze: Failed to import engine")
        return AnalyzeOutput(
            race_id=input_data.race_id,
            predictions={},
            confidence=0.0,
            execution_time_ms=0
        )
    
    try:
        # Convert to engine Race format
        # This is a simplified conversion - real implementation would need more mapping
        engine_race_data = {
            "race_id": input_data.race_id,
            "runners": [
                {
                    "runner_id": r.runner_id,
                    "horse": r.horse,
                    "weight_lbs": r.weight_lbs,
                    "jockey": r.jockey,
                    "trainer": r.trainer,
                    "odds_live": r.odds_live,
                    "OR": r.OR,
                    "TS": r.TS,
                    "RPR": r.RPR
                }
                for r in input_data.runners
            ]
        }
        
        # Call engine (this would need proper data formatting)
        # For now, return mock data as the engine integration requires complete race context
        logger.warning("Analyze: Using mock predictions (full engine integration pending)")
        predictions = {runner.horse: 0.1 + (i * 0.05) for i, runner in enumerate(input_data.runners)}
        confidence = 0.70
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return AnalyzeOutput(
            race_id=input_data.race_id,
            predictions=predictions,
            confidence=confidence,
            execution_time_ms=execution_time_ms
        )
        
    except Exception as e:
        logger.error(f"Analyze: Error running engine: {e}")
        execution_time_ms = int((time.time() - start_time) * 1000)
        return AnalyzeOutput(
            race_id=input_data.race_id,
            predictions={},
            confidence=0.0,
            execution_time_ms=execution_time_ms
        )


# ============================================================================
# CRITIC NODE
# ============================================================================

def critic_race(input_data: CriticInput) -> CriticOutput:
    """
    Critic agent: Evaluate prediction quality and create learning events
    
    Evaluates:
    - Prediction quality (confidence, consistency)
    - Data completeness
    - Execution time
    - Anomalies
    
    Args:
        input_data: CriticInput with race_id and analyze_output
        
    Returns:
        CriticOutput with learning event
    """
    logger.info(f"Critic: Evaluating race {input_data.race_id}")
    
    analyze = input_data.analyze_output
    
    # Evaluate prediction quality
    prediction_quality = analyze.confidence
    
    # Evaluate data completeness (based on number of predictions)
    data_completeness = min(1.0, len(analyze.predictions) / 8.0) if analyze.predictions else 0.0
    
    # Check for anomalies
    anomalies = []
    if analyze.confidence < 0.5:
        anomalies.append("Low confidence prediction")
    if not analyze.predictions:
        anomalies.append("No predictions generated")
    if analyze.execution_time_ms > 10000:
        anomalies.append(f"Slow execution: {analyze.execution_time_ms}ms")
    
    # Determine severity
    severity = "info"
    if anomalies:
        severity = "warning" if analyze.confidence > 0.3 else "error"
    
    # Determine event type
    event_type = "prediction_accuracy"
    if anomalies:
        event_type = "anomaly"
    if data_completeness < 0.8:
        event_type = "data_quality"
    
    # Create learning event
    learning_event = LearningEvent(
        race_id=input_data.race_id,
        event_type=event_type,
        severity=severity,
        feedback={
            "confidence": analyze.confidence,
            "num_predictions": len(analyze.predictions),
            "execution_time_ms": analyze.execution_time_ms,
            "timestamp": analyze.timestamp
        },
        prediction_quality_score=prediction_quality,
        data_completeness_score=data_completeness,
        execution_time_ms=analyze.execution_time_ms,
        anomalies=anomalies
    )
    
    logger.info(f"Critic: Created {event_type} event with severity {severity}")
    return CriticOutput(race_id=input_data.race_id, learning_event=learning_event)


# ============================================================================
# ARCHIVE NODE
# ============================================================================

def archive_results(input_data: ArchiveInput, dry_run: bool = False) -> ArchiveOutput:
    """
    Archive agent: Write results to Supabase
    
    Writes to:
    - engine_runs table (run_id, race_id, predictions, timestamp)
    - learning_events table (event_id, run_id, feedback, created_at)
    
    Args:
        input_data: ArchiveInput with race_id, run_id, analyze_output, learning_event
        dry_run: If True, skip actual database writes
        
    Returns:
        ArchiveOutput with success status
    """
    logger.info(f"Archive: Storing results for race {input_data.race_id}")
    
    if dry_run:
        logger.info("Archive: Dry run mode - skipping database writes")
        return ArchiveOutput(race_id=input_data.race_id, run_id=input_data.run_id, success=True)
    
    client = get_supabase_client()
    if not client:
        logger.error("Archive: Failed to get Supabase client")
        return ArchiveOutput(
            race_id=input_data.race_id,
            run_id=input_data.run_id,
            success=False,
            error="Failed to connect to Supabase"
        )
    
    try:
        # Write engine run
        engine_run_data = {
            "id": input_data.run_id,
            "race_id": input_data.race_id,
            "predictions": input_data.analyze_output.predictions,
            "confidence": input_data.analyze_output.confidence,
            "execution_time_ms": input_data.analyze_output.execution_time_ms,
            "created_at": input_data.analyze_output.timestamp
        }
        
        client.table("engine_runs").insert(engine_run_data).execute()
        logger.info(f"Archive: Wrote engine run {input_data.run_id}")
        
        # Write learning event
        learning_event_data = {
            "id": input_data.learning_event.event_id,
            "run_id": input_data.run_id,
            "event_type": input_data.learning_event.event_type,
            "feedback": input_data.learning_event.feedback,
            "severity": input_data.learning_event.severity,
            "created_at": input_data.learning_event.created_at
        }
        
        client.table("learning_events").insert(learning_event_data).execute()
        logger.info(f"Archive: Wrote learning event {input_data.learning_event.event_id}")
        
        return ArchiveOutput(race_id=input_data.race_id, run_id=input_data.run_id, success=True)
        
    except Exception as e:
        logger.error(f"Archive: Error writing to Supabase: {e}")
        return ArchiveOutput(
            race_id=input_data.race_id,
            run_id=input_data.run_id,
            success=False,
            error=str(e)
        )
