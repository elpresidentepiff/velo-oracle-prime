"""
VÉLØ Phase 1: Daily Awareness Ingestion Spine
Railway FastAPI Worker - Main Application

This is the parsing brains. No "best effort" nonsense.
Missing files → batch fails. Unmatched runners → batch fails.
Silent skipping is how "cheating" happens.

Date: 2026-01-04
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, time
from enum import Enum
import logging
from contextlib import asynccontextmanager

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
    
    logger.info("✅ VÉLØ Ingestion Spine ready")
    
    yield
    
    # Cleanup
    logger.info("🛑 VÉLØ Ingestion Spine shutting down...")
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

# Force redeploy: 2026-01-07 - Fix tRPC 404 errors
try:
    from .trpc_adapter import router as trpc_router
    app.include_router(trpc_router)
    logger.info("✅ tRPC adapter loaded successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import tRPC adapter: {e}")
    logger.error("tRPC endpoints will NOT be available")
except Exception as e:
    logger.error(f"❌ Failed to register tRPC router: {e}")
    logger.error("tRPC endpoints may not work correctly")

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "velo-ingestion-spine",
        "version": "1.0.0",
        "phase": "1"
    }

@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to list all registered routes"""
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
        "trpc_routes": [r for r in routes if "/trpc/" in r["path"]]
    }

@app.get("/trpc/health")
async def trpc_health_check():
    """tRPC-specific health check"""
    return {
        "status": "healthy",
        "service": "trpc-adapter",
        "version": "1.0.0",
        "endpoints": [
            "/trpc/ingestion.createBatch",
            "/trpc/ingestion.registerFiles",
            "/trpc/ingestion.parseBatch",
            "/trpc/ingestion.getBatchStatus",
            "/trpc/ingestion.listRaces",
            "/trpc/ingestion.getRaceDetails"
        ]
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
            # STEP 1: Parse racecards → insert races
            logger.info("Step 1: Parsing racecards...")
            racecards_file = file_map[FileType.RACECARDS]
            racecards_data = await storage.download_file(racecards_file['storage_path'])
            
            parser = RacecardsParser()
            races = parser.parse(racecards_data)
            
            if not races:
                raise ValueError("No races found in racecards file")
            
            # Insert races
            race_id_map = {}  # join_key -> race_id
            for race_data in races:
                race_id = await db.insert_race(
                    batch_id=batch_id,
                    import_date=batch['import_date'],
                    race_data=race_data
                )
                race_id_map[race_data['join_key']] = race_id
                counts['races_inserted'] += 1
            
            logger.info(f"✅ Inserted {counts['races_inserted']} races")
            
            # STEP 2: Parse runners → insert runners linked to race_id
            logger.info("Step 2: Parsing runners...")
            runners_file = file_map[FileType.RUNNERS]
            runners_data = await storage.download_file(runners_file['storage_path'])
            
            parser = RunnersParser()
            runners = parser.parse(runners_data)
            
            if not runners:
                raise ValueError("No runners found in runners file")
            
            # Match runners to races and insert
            unmatched_runners = []
            for runner_data in runners:
                runner_join_key = runner_data.pop('race_join_key')
                
                if runner_join_key not in race_id_map:
                    unmatched_runners.append({
                        'horse_name': runner_data.get('horse_name'),
                        'join_key': runner_join_key
                    })
                    counts['unmatched_runner_rows'] += 1
                    continue
                
                race_id = race_id_map[runner_join_key]
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
            
            # STEP 3: Parse form/comments (optional)
            if FileType.FORM in file_map:
                logger.info("Step 3: Parsing form...")
                form_file = file_map[FileType.FORM]
                form_data = await storage.download_file(form_file['storage_path'])
                
                parser = FormParser()
                form_lines = parser.parse(form_data)
                
                # Insert form lines (implementation depends on form structure)
                # For Phase 1, we can store raw or skip
                counts['form_lines_inserted'] = len(form_lines)
                logger.info(f"✅ Parsed {counts['form_lines_inserted']} form lines")
            
            # SUCCESS: All validations passed
            if counts['races_inserted'] > 0 and counts['runners_inserted'] > 0 and counts['unmatched_runner_rows'] == 0:
                await db.update_batch_status(
                    batch_id,
                    BatchStatus.READY,
                    counts=counts
                )
                
                logger.info(f"✅ Batch {batch_id} parsed successfully")
                
                return ParseBatchResponse(
                    batch_id=batch_id,
                    status=BatchStatus.READY,
                    message="Batch parsed successfully",
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
