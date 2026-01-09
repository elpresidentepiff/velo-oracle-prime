"""
VÉLØ Daily Meeting Pipeline (Prefect Flow)
=====================================

Orchestrates the complete daily racing data pipeline:
1. Ingest PDFs
2. Parse and validate meeting data
3. Insert to Supabase
4. Build feature mart
5. Run Phase 2A analysis
6. Persist outputs

All operations have enforced logging with BOOT/STEP/DONE markers.
No silent runs allowed.
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from prefect import flow, task, get_run_logger


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ParseResult:
    """Result from parse_and_validate task"""
    status: str  # "VALID" or "REJECTED_BAD_OUTPUT"
    meeting: Optional[object] = None
    errors: Optional[List[str]] = None
    races_count: Optional[int] = None
    runners_count: Optional[int] = None


@dataclass
class AnalysisResult:
    """Result from phase2a analysis"""
    predictions_count: int
    output_path: str
    status: str


# ============================================================================
# TASKS
# ============================================================================

@task(retries=3, retry_delay_seconds=60)
def ingest_pdfs(as_of_date: str) -> str:
    """
    Ingest PDF files for a specific date.
    
    Args:
        as_of_date: Date string in YYYY-MM-DD format
        
    Returns:
        batch_id: UUID of the created batch
    """
    logger = get_run_logger()
    logger.info(f"ENTER ingest_pdfs as_of_date={as_of_date}")
    
    try:
        # Mock implementation - in real system this would:
        # 1. Download PDFs from storage/API
        # 2. Create batch record in DB
        # 3. Register files
        
        from datetime import date
        import uuid
        
        # Create mock batch_id
        batch_id = str(uuid.uuid4())
        
        logger.info(f"Created batch {batch_id} for date {as_of_date}")
        logger.info(f"EXIT ingest_pdfs batch_id={batch_id}")
        
        return batch_id
        
    except Exception as e:
        logger.exception("ingest_pdfs EXCEPTION")
        raise


@task(retries=3, retry_delay_seconds=60)
def parse_and_validate(batch_id: str, as_of_date: str) -> ParseResult:
    """
    Parse meeting data and run validation gates.
    
    Args:
        batch_id: Batch UUID
        as_of_date: Date string in YYYY-MM-DD format
        
    Returns:
        ParseResult with status and meeting data
    """
    logger = get_run_logger()
    logger.info(f"ENTER parse_and_validate batch_id={batch_id}")
    
    try:
        # Mock implementation - in real system this would:
        # 1. Get batch files from DB
        # 2. Call racingpost_pdf.parse_meeting()
        # 3. Call racingpost_pdf.validate.validate_meeting()
        # 4. Return structured result
        
        # For smoke test, return a valid result
        result = ParseResult(
            status="VALID",
            meeting=None,  # Would contain Meeting object
            races_count=8,
            runners_count=96
        )
        
        logger.info(f"Parsed meeting: {result.races_count} races, {result.runners_count} runners")
        logger.info(f"EXIT parse_and_validate status={result.status}")
        
        return result
        
    except Exception as e:
        logger.exception("parse_and_validate EXCEPTION")
        raise


@task
def insert_to_supabase(batch_id: str, meeting: object) -> None:
    """
    Insert validated meeting data to Supabase.
    
    Args:
        batch_id: Batch UUID
        meeting: Validated Meeting object
    """
    logger = get_run_logger()
    logger.info(f"ENTER insert_to_supabase batch_id={batch_id}")
    
    try:
        # Mock implementation - in real system this would:
        # 1. Get DatabaseClient
        # 2. Insert races
        # 3. Insert runners
        # 4. Update batch status
        
        logger.info("Inserted meeting data to Supabase")
        logger.info("EXIT insert_to_supabase success")
        
    except Exception as e:
        logger.exception("insert_to_supabase EXCEPTION")
        raise


@task
def build_feature_mart(as_of_date: str) -> None:
    """
    Build feature mart for the specified date.
    
    Computes deterministic trainer/jockey/course stats.
    
    Args:
        as_of_date: Date string in YYYY-MM-DD format
    """
    logger = get_run_logger()
    logger.info(f"ENTER build_feature_mart as_of_date={as_of_date}")
    
    try:
        # Mock implementation - in real system this would:
        # 1. Get DatabaseClient
        # 2. Call db.build_feature_mart(as_of_date)
        
        logger.info("Feature mart built successfully")
        logger.info("EXIT build_feature_mart success")
        
    except Exception as e:
        logger.exception("build_feature_mart EXCEPTION")
        raise


@task
def run_phase2a_analysis(as_of_date: str) -> AnalysisResult:
    """
    Run Phase 2A analytical engine.
    
    Args:
        as_of_date: Date string in YYYY-MM-DD format
        
    Returns:
        AnalysisResult with prediction counts and output path
    """
    logger = get_run_logger()
    logger.info(f"ENTER run_phase2a_analysis as_of_date={as_of_date}")
    
    try:
        # Mock implementation - in real system this would:
        # 1. Load features from feature mart
        # 2. Run analytical models
        # 3. Generate predictions
        
        result = AnalysisResult(
            predictions_count=96,
            output_path=f"/tmp/predictions_{as_of_date}.json",
            status="SUCCESS"
        )
        
        logger.info(f"Generated {result.predictions_count} predictions")
        logger.info("EXIT run_phase2a_analysis success")
        
        return result
        
    except Exception as e:
        logger.exception("run_phase2a_analysis EXCEPTION")
        raise


@task
def persist_outputs(batch_id: str, analysis_result: AnalysisResult) -> None:
    """
    Persist analysis outputs to storage.
    
    Args:
        batch_id: Batch UUID
        analysis_result: Analysis results to persist
    """
    logger = get_run_logger()
    logger.info(f"ENTER persist_outputs batch_id={batch_id}")
    
    try:
        # Mock implementation - in real system this would:
        # 1. Write predictions to DB
        # 2. Upload reports to storage
        # 3. Update batch status to 'ready'
        
        logger.info(f"Persisted {analysis_result.predictions_count} predictions")
        logger.info("EXIT persist_outputs success")
        
    except Exception as e:
        logger.exception("persist_outputs EXCEPTION")
        raise


@task
def persist_rejection_report(batch_id: str, errors: List[str]) -> None:
    """
    Persist rejection report for failed validation.
    
    Args:
        batch_id: Batch UUID
        errors: List of validation errors
    """
    logger = get_run_logger()
    logger.info(f"ENTER persist_rejection_report batch_id={batch_id}")
    
    try:
        # Mock implementation - in real system this would:
        # 1. Write errors to DB
        # 2. Update batch status to 'rejected'
        # 3. Send notification
        
        logger.info(f"Persisted rejection report with {len(errors)} errors")
        logger.info("EXIT persist_rejection_report success")
        
    except Exception as e:
        logger.exception("persist_rejection_report EXCEPTION")
        raise


# ============================================================================
# FLOW
# ============================================================================

@flow(name="daily-meeting-pipeline", log_prints=True)
def daily_meeting_pipeline(as_of_date: str):
    """
    Daily meeting pipeline orchestration flow.
    
    Enforced logging: All steps emit BOOT/STEP/DONE markers.
    No silent runs allowed.
    
    Args:
        as_of_date: Date string in YYYY-MM-DD format (e.g., "2026-01-09")
    """
    logger = get_run_logger()
    logger.info(f"BOOT flow start as_of_date={as_of_date}")
    
    # STEP 1: Ingest PDFs
    try:
        logger.info("STEP 1 ingest start")
        batch_id = ingest_pdfs(as_of_date)
        logger.info(f"STEP 1 ingest done batch_id={batch_id}")
    except Exception as e:
        logger.exception("STEP 1 ingest FAILED")
        raise
    
    # STEP 2: Parse and validate
    try:
        logger.info("STEP 2 parse_validate start")
        parse_result = parse_and_validate(batch_id, as_of_date)
        logger.info(f"STEP 2 parse_validate done status={parse_result.status}")
    except Exception as e:
        logger.exception("STEP 2 parse_validate FAILED")
        raise
    
    # If rejected, log and exit cleanly
    if parse_result.status == "REJECTED_BAD_OUTPUT":
        logger.error(f"Batch {batch_id} rejected. Errors: {parse_result.errors}")
        persist_rejection_report(batch_id, parse_result.errors)
        raise ValueError(f"Batch {batch_id} rejected. No inserts.")
    
    # STEP 3: Insert to Supabase
    try:
        logger.info("STEP 3 supabase_insert start")
        insert_to_supabase(batch_id, parse_result.meeting)
        logger.info("STEP 3 supabase_insert done")
    except Exception as e:
        logger.exception("STEP 3 supabase_insert FAILED")
        raise
    
    # STEP 4: Build feature mart
    try:
        logger.info("STEP 4 build_feature_mart start")
        build_feature_mart(as_of_date)
        logger.info("STEP 4 build_feature_mart done")
    except Exception as e:
        logger.exception("STEP 4 build_feature_mart FAILED")
        raise
    
    # STEP 5: Run Phase 2A analysis
    try:
        logger.info("STEP 5 phase2a start")
        analysis_result = run_phase2a_analysis(as_of_date)
        logger.info("STEP 5 phase2a done")
    except Exception as e:
        logger.exception("STEP 5 phase2a FAILED")
        raise
    
    # STEP 6: Persist outputs
    try:
        logger.info("STEP 6 persist_outputs start")
        persist_outputs(batch_id, analysis_result)
        logger.info("STEP 6 persist_outputs done")
    except Exception as e:
        logger.exception("STEP 6 persist_outputs FAILED")
        raise
    
    logger.info("DONE flow complete")


# ============================================================================
# DIRECT RUN ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    # Default to 2026-01-09 if no arg provided
    as_of_date = sys.argv[1] if len(sys.argv) > 1 else "2026-01-09"
    
    print(f"Running daily_meeting_pipeline with as_of_date={as_of_date}")
    daily_meeting_pipeline(as_of_date=as_of_date)
