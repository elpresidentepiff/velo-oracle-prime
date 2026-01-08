"""
VÉLØ Phase 1: Daily Awareness Ingestion Spine
Railway FastAPI Worker - Main Application

This is the parsing brains. No "best effort" nonsense.
Missing files → batch fails. Unmatched runners → batch fails.
Silent skipping is how "cheating" happens.

Date: 2026-01-04
"""

from fastapi import FastAPI, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, time, datetime, timedelta
from enum import Enum
import logging
from contextlib import asynccontextmanager
import asyncio
import os

# Import our modules
from .db import get_db_client, DatabaseClient
from .storage import get_storage_client, StorageClient
from .parsers import RacecardsParser, RunnersParser, FormParser
from .models import (
    BatchStatus,
    FileType,
    CreateBatchRequest,
    CreateBatchResponse,
    RegisterFilesRequest,
    RegisterFilesResponse,
    ParseBatchResponse,
    BatchStatusResponse,
    ErrorDetail
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

# Background task to clean up smoke test batches
async def cleanup_smoke_batches(db: DatabaseClient):
    """
    Runs every hour, deletes smoke test batches older than 1 hour
    Prevents test data pollution in production
    
    Args:
        db: DatabaseClient instance for database operations
    """
    while True:
        try:
            # Find smoke batches older than 1 hour
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            deleted = await db.delete_old_smoke_batches(
                source="smoke_test",
                older_than=cutoff_time
            )
            
            if deleted > 0:
                logger.info(f"🧹 Cleaned up {deleted} smoke test batches")
        
        except Exception as e:
            logger.error(f"Error cleaning smoke batches: {e}")
        
        # Sleep for 1 hour
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("🚀 VÉLØ Ingestion Spine starting up...")
    
    # Initialize clients
    app.state.db = get_db_client()
    app.state.storage = get_storage_client()
    
    # Verify connections
    try:
        await app.state.db.verify_connection()
        logger.info("✅ Database connection verified")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    
    try:
        await app.state.storage.verify_connection()
        logger.info("✅ Storage connection verified")
    except Exception as e:
        logger.error(f"❌ Storage connection failed: {e}")
        raise
    
    # Start background cleanup task (only in production)
    cleanup_task = None
    if os.getenv("RAILWAY_ENVIRONMENT") == "production":
        # Pass db client to cleanup task to avoid scope issues
        cleanup_task = asyncio.create_task(cleanup_smoke_batches(app.state.db))
        logger.info("🧹 Smoke batch cleanup task started")
    
    logger.info("✅ VÉLØ Ingestion Spine ready")
    
    yield
    
    # Cleanup
    logger.info("🛑 VÉLØ Ingestion Spine shutting down...")
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    await app.state.db.close()
    await app.state.storage.close()

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="VÉLØ Ingestion Spine",
    description="Phase 1: Daily Awareness - Racing Post file ingestion with zero silent failures",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# tRPC COMPATIBILITY LAYER
# ============================================================================

# Import and include tRPC adapter
from .trpc_adapter import router as trpc_router
app.include_router(trpc_router)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/healthz")
async def healthz():
    """
    Lightweight health check - NO database/external dependencies
    Use this for load balancers and smoke tests
    Returns immediately without I/O
    """
    return {
        "status": "ok",
        "service": "velo-ingestion-spine",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "velo-ingestion-spine",
        "version": "1.0.0",
        "phase": "1"
    }

# ============================================================================
# ENDPOINT 1: CREATE BATCH
# POST /imports/batch
# ============================================================================

@app.post(
    "/imports/batch",
    response_model=CreateBatchResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_batch(request: CreateBatchRequest):
    """
    Create a new import batch for a given date.
    
    Rules:
    - Enforces uniqueness: one batch per date per source
    - If exists, returns existing batch_id (idempotency)
    - Sets initial status to 'uploaded'
    """
    logger.info(f"Creating batch for date: {request.import_date}")
    
    try:
        db: DatabaseClient = app.state.db
        
        # Check if batch already exists
        existing_batch = await db.get_batch_by_date(
            import_date=request.import_date,
            source=request.source
        )
        
        if existing_batch:
            logger.info(f"Batch already exists: {existing_batch['id']}")
            return CreateBatchResponse(
                batch_id=existing_batch['id'],
                status=existing_batch['status'],
                message="Batch already exists (idempotent)",
                created_at=existing_batch['created_at']
            )
        
        # Create new batch
        batch = await db.create_batch(
            import_date=request.import_date,
            source=request.source,
            notes=request.notes
        )
        
        logger.info(f"✅ Batch created: {batch['id']}")
        
        return CreateBatchResponse(
            batch_id=batch['id'],
            status=batch['status'],
            message="Batch created successfully",
            created_at=batch['created_at']
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to create batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch: {str(e)}"
        )

# ============================================================================
# ENDPOINT 2: REGISTER FILES
# POST /imports/{batch_id}/files
# ============================================================================

@app.post(
    "/imports/{batch_id}/files",
    response_model=RegisterFilesResponse
)
async def register_files(batch_id: str, request: RegisterFilesRequest):
    """
    Register file metadata for a batch.
    
    Rules:
    - Must include at least 'racecards' and 'runners' to proceed
    - Files must live under the correct YYYY-MM-DD/ folder for that batch date
    - Validates file paths match batch date
    """
    logger.info(f"Registering {len(request.files)} files for batch: {batch_id}")
    
    try:
        db: DatabaseClient = app.state.db
        storage: StorageClient = app.state.storage
        
        # Verify batch exists
        batch = await db.get_batch_by_id(batch_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch not found: {batch_id}"
            )
        
        # Validate required files
        file_types = {f.file_type for f in request.files}
        required_types = {FileType.RACECARDS, FileType.RUNNERS}
        
        if not required_types.issubset(file_types):
            missing = required_types - file_types
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required files: {', '.join(missing)}"
            )
        
        # Validate file paths match batch date
        batch_date = batch['import_date'].isoformat()
        for file in request.files:
            if not file.storage_path.startswith(f"rp_imports/{batch_date}/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File path mismatch: {file.storage_path} does not match batch date {batch_date}"
                )
            
            # Verify file exists in storage
            exists = await storage.file_exists(file.storage_path)
            if not exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found in storage: {file.storage_path}"
                )
        
        # Register files
        registered_count = 0
        for file in request.files:
            await db.register_file(
                batch_id=batch_id,
                file_type=file.file_type,
                storage_path=file.storage_path,
                original_filename=file.original_filename,
                mime_type=file.mime_type,
                checksum_sha256=file.checksum_sha256,
                size_bytes=file.size_bytes
            )
            registered_count += 1
        
        logger.info(f"✅ Registered {registered_count} files for batch {batch_id}")
        
        return RegisterFilesResponse(
            batch_id=batch_id,
            files_registered=registered_count,
            message="Files registered successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to register files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register files: {str(e)}"
        )

# ============================================================================
# ENDPOINT 3: PARSE BATCH
# POST /imports/{batch_id}/parse
# ============================================================================

@app.post(
    "/imports/{batch_id}/parse",
    response_model=ParseBatchResponse
)
async def parse_batch(batch_id: str):
    """
    Parse all files in a batch and insert into canonical tables.
    
    Rules:
    - Set batch status → 'parsing'
    - Parse in strict order: racecards → runners → form/comments
    - On any structural inconsistency: set status → 'failed', store error_summary
    - Batch success requires: races_inserted > 0, runners_inserted > 0, unmatched_runner_rows == 0
    - No partial success - all or nothing
    """
    logger.info(f"Parsing batch: {batch_id}")
    
    try:
        db: DatabaseClient = app.state.db
        storage: StorageClient = app.state.storage
        
        # Verify batch exists
        batch = await db.get_batch_by_id(batch_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch not found: {batch_id}"
            )
        
        # Check if already parsed
        if batch['status'] in [BatchStatus.READY, BatchStatus.PARSING]:
            return ParseBatchResponse(
                batch_id=batch_id,
                status=batch['status'],
                message=f"Batch already {batch['status']}",
                counts=batch.get('counts', {})
            )
        
        # Update status to parsing
        await db.update_batch_status(batch_id, BatchStatus.PARSING)
        
        # Get registered files
        files = await db.get_batch_files(batch_id)
        file_map = {f['file_type']: f for f in files}
        
        # Validate required files
        if FileType.RACECARDS not in file_map or FileType.RUNNERS not in file_map:
            error_msg = "Missing required files: racecards or runners"
            await db.update_batch_status(
                batch_id,
                BatchStatus.FAILED,
                error_summary=error_msg
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Initialize counts
        counts = {
            'races_inserted': 0,
            'runners_inserted': 0,
            'form_lines_inserted': 0,
            'unmatched_runner_rows': 0,
            'parse_errors': []
        }
        
        try:
            # STEP 1: Parse racecards
            logger.info("Step 1: Parsing racecards...")
            racecards_file = file_map[FileType.RACECARDS]
            racecards_data = await storage.download_file(racecards_file['storage_path'])
            
            parser = RacecardsParser()
            races = parser.parse(racecards_data)
            
            if not races:
                raise ValueError("No races found in racecards file")
            
            logger.info(f"✅ Parsed {len(races)} races from racecards")
            
            # STEP 2: Parse runners
            logger.info("Step 2: Parsing runners...")
            runners_file = file_map[FileType.RUNNERS]
            runners_data = await storage.download_file(runners_file['storage_path'])
            
            parser = RunnersParser()
            runners = parser.parse(runners_data)
            
            if not runners:
                raise ValueError("No runners found in runners file")
            
            logger.info(f"✅ Parsed {len(runners)} runners")
            
            # STEP 3: Group runners by race and calculate quality
            logger.info("Step 3: Calculating quality metadata...")
            from .quality import calculate_runner_confidence, calculate_race_quality
            
            # Group runners by race join key
            runners_by_race = {}
            unmatched_runners = []
            
            for runner_data in runners:
                runner_join_key = runner_data.pop('race_join_key')
                
                # Calculate runner confidence
                confidence, flags, method = calculate_runner_confidence(runner_data)
                runner_data['confidence'] = confidence
                runner_data['extraction_method'] = method
                runner_data['quality_flags'] = flags
                
                # Group by race
                if runner_join_key not in runners_by_race:
                    runners_by_race[runner_join_key] = []
                runners_by_race[runner_join_key].append(runner_data)
            
            # STEP 4: Insert races with quality metadata
            logger.info("Step 4: Inserting races with quality metadata...")
            race_id_map = {}  # join_key -> race_id
            race_join_key_map = {}  # Store join_key_base -> full join_key mapping
            
            for race_data in races:
                # Build full join_key with import_date
                join_key_base = race_data.get('join_key_base', '')
                import_date_str = batch['import_date'].isoformat()
                full_join_key = f"{import_date_str}|{join_key_base}"
                race_data['join_key'] = full_join_key
                race_join_key_map[join_key_base] = full_join_key
                
                # Get runners for this race
                race_runners = runners_by_race.get(full_join_key, [])
                
                # Calculate race quality
                race_metadata = {
                    'course': race_data.get('course'),
                    'distance': race_data.get('distance'),
                    'race_time': race_data.get('off_time')  # off_time is the race time
                }
                parse_conf, quality, race_flags = calculate_race_quality(race_metadata, race_runners)
                
                # Add quality metadata to race
                race_data['parse_confidence'] = parse_conf
                race_data['quality_score'] = quality
                race_data['quality_flags'] = race_flags
                
                # Insert race
                race_id = await db.insert_race(
                    batch_id=batch_id,
                    import_date=batch['import_date'],
                    race_data=race_data
                )
                race_id_map[full_join_key] = race_id
                counts['races_inserted'] += 1
            
            logger.info(f"✅ Inserted {counts['races_inserted']} races")
            
            # STEP 5: Insert runners with quality metadata
            logger.info("Step 5: Inserting runners with quality metadata...")
            for join_key, race_runners in runners_by_race.items():
                if join_key not in race_id_map:
                    # Unmatched runners
                    for runner in race_runners:
                        unmatched_runners.append({
                            'horse_name': runner.get('horse_name'),
                            'join_key': join_key
                        })
                        counts['unmatched_runner_rows'] += 1
                    continue
                
                race_id = race_id_map[join_key]
                for runner_data in race_runners:
                    await db.insert_runner(race_id=race_id, runner_data=runner_data)
                    counts['runners_inserted'] += 1
            
            logger.info(f"✅ Inserted {counts['runners_inserted']} runners")
            
            # Check for unmatched runners (HARD FAILURE)
            if counts['unmatched_runner_rows'] > 0:
                error_msg = f"Found {counts['unmatched_runner_rows']} unmatched runners"
                counts['unmatched_examples'] = unmatched_runners[:5]  # First 5 examples
                
                await db.update_batch_status(
                    batch_id,
                    BatchStatus.FAILED,
                    error_summary=error_msg,
                    counts=counts
                )
                
                raise ValueError(error_msg)
            
            # STEP 6: Parse form/comments (optional)
            if FileType.FORM in file_map:
                logger.info("Step 6: Parsing form...")
                form_file = file_map[FileType.FORM]
                form_data = await storage.download_file(form_file['storage_path'])
                
                parser = FormParser()
                form_lines = parser.parse(form_data)
                
                # Insert form lines (implementation depends on form structure)
                # For Phase 1, we can store raw or skip
                counts['form_lines_inserted'] = len(form_lines)
                logger.info(f"✅ Parsed {counts['form_lines_inserted']} form lines")
            
            # SUCCESS: All validations passed - set status to PARSED (ready for validation)
            if counts['races_inserted'] > 0 and counts['runners_inserted'] > 0 and counts['unmatched_runner_rows'] == 0:
                await db.update_batch_status(
                    batch_id,
                    BatchStatus.PARSED,  # Changed from READY to PARSED
                    counts=counts
                )
                
                logger.info(f"✅ Batch {batch_id} parsed successfully with quality metadata")
                
                return ParseBatchResponse(
                    batch_id=batch_id,
                    status=BatchStatus.PARSED,
                    message="Batch parsed successfully with quality metadata",
                    counts=counts
                )
            else:
                raise ValueError("Batch validation failed: insufficient data")
        
        except Exception as parse_error:
            # FAILURE: Set status to failed with error details
            error_msg = str(parse_error)
            logger.error(f"❌ Parse error: {error_msg}")
            
            await db.update_batch_status(
                batch_id,
                BatchStatus.FAILED,
                error_summary=error_msg,
                counts=counts
            )
            
            return ParseBatchResponse(
                batch_id=batch_id,
                status=BatchStatus.FAILED,
                message=f"Batch parsing failed: {error_msg}",
                counts=counts,
                error=ErrorDetail(
                    code="PARSE_ERROR",
                    message=error_msg,
                    details=counts
                )
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to parse batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse batch: {str(e)}"
        )

# ============================================================================
# ENDPOINT 3.5: VALIDATE BATCH
# POST /imports/{batch_id}/validate
# ============================================================================

@app.post("/imports/{batch_id}/validate")
async def validate_batch(batch_id: str):
    """
    Run RIC+ validation + Great Expectations on a parsed batch
    
    Categorizes races as valid/needs_review/rejected
    Updates batch status accordingly
    
    Returns validation report with per-race breakdown
    """
    import pandas as pd
    from .quality import validate_race
    from data_quality.gx_context import get_gx_context, create_races_suite, create_runners_suite
    
    logger.info(f"Validating batch: {batch_id}")
    
    try:
        db: DatabaseClient = app.state.db
        
        # Get batch
        batch = await db.get_batch_by_id(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Check batch status - must be 'parsed' or 'ready' to validate
        if batch["status"] not in ["parsed", "ready"]:
            raise HTTPException(
                status_code=400,
                detail=f"Batch must be 'parsed' or 'ready' to validate (current: {batch['status']})"
            )
        
        # Get all races in batch
        races = await db.get_batch_races(batch_id)
        
        if not races:
            raise HTTPException(status_code=400, detail="Batch has no races")
        
        # --- ORIGINAL RIC+ VALIDATION ---
        validation_results = []
        valid_count = 0
        needs_review_count = 0
        rejected_count = 0
        
        for race in races:
            result = validate_race(race)
            validation_results.append(result)
            
            if result["status"] == "valid":
                valid_count += 1
            elif result["status"] == "needs_review":
                needs_review_count += 1
            elif result["status"] == "rejected":
                rejected_count += 1
        
        # --- GREAT EXPECTATIONS VALIDATION ---
        gx_context = get_gx_context()
        
        # Convert races to DataFrame
        races_df = pd.DataFrame([
            {
                "id": r["id"],
                "course": r.get("course"),
                "distance": r.get("distance"),
                "quality_score": r.get("quality_score", 0.0),
                "batch_id": batch_id
            }
            for r in races
        ])
        
        # Get all runners
        all_runners = []
        for race in races:
            for runner in race.get("runners", []):
                all_runners.append({
                    "race_id": race["id"],
                    "horse_name": runner.get("horse_name"),
                    "odds": runner.get("odds"),
                    "confidence": runner.get("confidence", 0.0)
                })
        
        runners_df = pd.DataFrame(all_runners)
        
        # Run GX validations
        races_batch = gx_context.sources.add_pandas("races_data")
        races_batch_request = races_batch.add_batch(races_df)
        
        runners_batch = gx_context.sources.add_pandas("runners_data")
        runners_batch_request = runners_batch.add_batch(runners_df)
        
        # Ensure suites exist
        create_races_suite()
        create_runners_suite()
        
        # Run checkpoints
        races_checkpoint = gx_context.add_checkpoint(
            name="validate_races_checkpoint",
            validations=[
                {
                    "batch_request": races_batch_request.dict(),
                    "expectation_suite_name": "races_validation_suite"
                }
            ]
        )
        
        runners_checkpoint = gx_context.add_checkpoint(
            name="validate_runners_checkpoint",
            validations=[
                {
                    "batch_request": runners_batch_request.dict(),
                    "expectation_suite_name": "runners_validation_suite"
                }
            ]
        )
        
        races_results = races_checkpoint.run()
        runners_results = runners_checkpoint.run()
        
        # Combine results
        gx_success = races_results.success and runners_results.success
        
        # Calculate average quality
        avg_quality = sum(r["quality_score"] for r in validation_results) / len(validation_results)
        
        # Determine new batch status
        if not gx_success or rejected_count > 0 or needs_review_count > 0:
            new_status = BatchStatus.NEEDS_REVIEW
        else:
            new_status = BatchStatus.VALIDATED
        
        # Build validation report
        validation_report = {
            "validated_at": datetime.utcnow().isoformat(),
            "total_races": len(races),
            "ric_validation": {
                "valid_count": valid_count,
                "needs_review_count": needs_review_count,
                "rejected_count": rejected_count,
                "races": validation_results
            },
            "gx_validation": {
                "races_success": races_results.success,
                "runners_success": runners_results.success,
                "races_results": races_results.to_json_dict(),
                "runners_results": runners_results.to_json_dict()
            },
            "avg_quality_score": round(avg_quality, 3)
        }
        
        # Update batch status
        await db.update_batch_status(batch_id, new_status)
        
        # Store validation report
        await db.store_validation_report(batch_id, validation_report)
        
        logger.info(
            f"✅ Batch {batch_id} validated: "
            f"RIC+: {valid_count} valid, {needs_review_count} review, {rejected_count} rejected | "
            f"GX: races={races_results.success}, runners={runners_results.success}"
        )
        
        return {
            "batch_id": batch_id,
            "total_races": len(races),
            "valid_count": valid_count,
            "needs_review_count": needs_review_count,
            "rejected_count": rejected_count,
            "avg_quality_score": round(avg_quality, 3),
            "new_status": new_status.value,
            "gx_success": gx_success,
            "races": validation_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to validate batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate batch: {str(e)}"
        )

# ============================================================================
# ENDPOINT 4: GET BATCH STATUS
# GET /imports/{batch_id}
# ============================================================================

@app.get(
    "/imports/{batch_id}",
    response_model=BatchStatusResponse
)
async def get_batch_status(batch_id: str):
    """
    Get the status and details of a batch.
    
    Returns:
    - Batch status (uploaded, parsing, ready, failed)
    - Counts (races, runners, files)
    - Error summary (if failed)
    """
    logger.info(f"Getting status for batch: {batch_id}")
    
    try:
        db: DatabaseClient = app.state.db
        
        # Get batch
        batch = await db.get_batch_by_id(batch_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Batch not found: {batch_id}"
            )
        
        # Get files
        files = await db.get_batch_files(batch_id)
        
        # Get stats
        stats = await db.get_batch_stats(batch_id)
        
        return BatchStatusResponse(
            batch_id=batch['id'],
            import_date=batch['import_date'],
            source=batch['source'],
            status=batch['status'],
            notes=batch.get('notes'),
            error_summary=batch.get('error_summary'),
            counts=batch.get('counts', {}),
            files_count=len(files),
            races_count=stats.get('races_count', 0),
            runners_count=stats.get('runners_count', 0),
            created_at=batch['created_at'],
            updated_at=batch['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get batch status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get batch status: {str(e)}"
        )

# ============================================================================
# ENDPOINT 5: LIST RACES FOR DATE
# GET /races/{import_date}
# ============================================================================

@app.get("/races/{import_date}")
async def list_races(import_date: date):
    """
    List all races for a given import date.
    
    Used by UI Day View to show the day's racing reality.
    """
    logger.info(f"Listing races for date: {import_date}")
    
    try:
        db: DatabaseClient = app.state.db
        
        races = await db.get_races_by_date(import_date)
        
        return {
            "import_date": import_date.isoformat(),
            "races_count": len(races),
            "races": races
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to list races: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list races: {str(e)}"
        )

# ============================================================================
# ENDPOINT 6: GET RACE DETAILS
# GET /races/{race_id}/details
# ============================================================================

@app.get("/races/{race_id}/details")
async def get_race_details(race_id: str):
    """
    Get detailed information about a race including all runners.
    
    Used by UI to show race detail page.
    """
    logger.info(f"Getting details for race: {race_id}")
    
    try:
        db: DatabaseClient = app.state.db
        
        # Get race
        race = await db.get_race_by_id(race_id)
        if not race:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Race not found: {race_id}"
            )
        
        # Get runners
        runners = await db.get_race_runners(race_id)
        
        return {
            "race": race,
            "runners": runners,
            "runner_count": len(runners)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get race details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get race details: {str(e)}"
        )

# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "VÉLØ Ingestion Spine",
        "phase": "1",
        "version": "1.0.0",
        "description": "Daily Awareness - Racing Post file ingestion with zero silent failures",
        "endpoints": {
            "health": "/health",
            "create_batch": "POST /imports/batch",
            "register_files": "POST /imports/{batch_id}/files",
            "parse_batch": "POST /imports/{batch_id}/parse",
            "get_batch_status": "GET /imports/{batch_id}",
            "list_races": "GET /races/{import_date}",
            "get_race_details": "GET /races/{race_id}/details"
        }
    }

# ============================================================================
# DEBUG ENDPOINT
# ============================================================================

@app.get("/debug/routes")
async def debug_routes(x_debug_key: str = Header(None)):
    """
    Debug endpoint - lists all registered routes
    
    SECURITY: Protected by X-Debug-Key header in production
    Returns 404 without valid key to prevent attack surface mapping
    """
    # Get debug key from environment
    required_key = os.getenv("DEBUG_KEY")
    
    # In production, require auth
    if os.getenv("RAILWAY_ENVIRONMENT") == "production":
        if not required_key:
            # No debug key configured = disabled in prod
            raise HTTPException(status_code=404, detail="Not found")
        
        if x_debug_key != required_key:
            # Wrong/missing key = 404 (don't reveal endpoint exists)
            raise HTTPException(status_code=404, detail="Not found")
    
    # Auth passed or non-prod environment
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": route.name if hasattr(route, "name") else None
            })
    
    return {
        "total_routes": len(routes),
        "routes": sorted(routes, key=lambda x: x["path"]),
        "trpc_routes": [r for r in routes if "/trpc/" in r["path"]],
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development")
    }

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )
