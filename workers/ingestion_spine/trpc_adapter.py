"""
tRPC Compatibility Adapter for FastAPI
Wraps existing FastAPI endpoints to work with tRPC clients

This adapter layer translates between tRPC's request/response format and FastAPI's
native REST endpoints, allowing the Ops Console frontend to communicate with the
ingestion spine without requiring changes to the existing FastAPI implementation.

Date: 2026-01-06
"""

from fastapi import APIRouter, Request, HTTPException
from typing import Any, Dict
import logging
from datetime import date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trpc")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def parse_trpc_request(request: Request) -> Dict[str, Any]:
    """
    Parse tRPC request format and extract input data
    
    tRPC sends requests with structure:
    {
        "input": {
            "param1": "value1",
            "param2": "value2"
        }
    }
    """
    try:
        if request.method == "POST":
            body = await request.json()
            return body.get("input", {})
        else:
            # For GET requests, check query parameters
            # tRPC can send input as a query parameter
            return {}
    except Exception as e:
        logger.error(f"Failed to parse tRPC request: {e}")
        return {}

def format_trpc_response(data: Any) -> Dict[str, Any]:
    """
    Format response in tRPC format
    
    tRPC expects responses with structure:
    {
        "result": {
            "data": { ... actual data ... }
        }
    }
    """
    return {
        "result": {
            "data": data
        }
    }

def format_trpc_error(message: str, code: str = "INTERNAL_SERVER_ERROR") -> Dict[str, Any]:
    """
    Format error in tRPC format
    
    tRPC expects errors with structure:
    {
        "error": {
            "message": "Error description",
            "code": "ERROR_CODE"
        }
    }
    """
    return {
        "error": {
            "message": message,
            "code": code
        }
    }

# ============================================================================
# tRPC ENDPOINTS
# ============================================================================

@router.post("/ingestion.createBatch")
@router.get("/ingestion.createBatch")
async def trpc_create_batch(request: Request):
    """
    tRPC wrapper for POST /imports/batch
    
    Creates a new import batch for a given date.
    """
    try:
        input_data = await parse_trpc_request(request)
        
        # Import here to avoid circular imports
        from .main import create_batch
        from .models import CreateBatchRequest
        
        # Convert input to FastAPI request model
        batch_request = CreateBatchRequest(**input_data)
        
        # Call existing FastAPI endpoint logic
        result = await create_batch(batch_request)
        
        # Return tRPC response format
        return format_trpc_response(result.dict())
        
    except HTTPException as e:
        return format_trpc_error(e.detail, "BAD_REQUEST")
    except Exception as e:
        logger.error(f"tRPC createBatch error: {e}")
        return format_trpc_error(str(e), "INTERNAL_SERVER_ERROR")

@router.post("/ingestion.registerFiles")
@router.get("/ingestion.registerFiles")
async def trpc_register_files(request: Request):
    """
    tRPC wrapper for POST /imports/{batch_id}/files
    
    Registers file metadata for a batch.
    """
    try:
        input_data = await parse_trpc_request(request)
        
        # Extract batch_id from input
        batch_id = input_data.pop("batch_id", None)
        if not batch_id:
            return format_trpc_error("batch_id is required", "BAD_REQUEST")
        
        from .main import register_files
        from .models import RegisterFilesRequest
        
        # Convert input to FastAPI request model
        files_request = RegisterFilesRequest(**input_data)
        
        # Call existing FastAPI endpoint logic
        result = await register_files(batch_id, files_request)
        
        # Return tRPC response format
        return format_trpc_response(result.dict())
        
    except HTTPException as e:
        return format_trpc_error(e.detail, "BAD_REQUEST")
    except Exception as e:
        logger.error(f"tRPC registerFiles error: {e}")
        return format_trpc_error(str(e), "INTERNAL_SERVER_ERROR")

@router.post("/ingestion.parseBatch")
@router.get("/ingestion.parseBatch")
async def trpc_parse_batch(request: Request):
    """
    tRPC wrapper for POST /imports/{batch_id}/parse
    
    Parses all files in a batch and inserts into canonical tables.
    """
    try:
        input_data = await parse_trpc_request(request)
        
        # Extract batch_id from input
        batch_id = input_data.get("batch_id")
        if not batch_id:
            return format_trpc_error("batch_id is required", "BAD_REQUEST")
        
        from .main import parse_batch
        
        # Call existing FastAPI endpoint logic
        result = await parse_batch(batch_id)
        
        # Return tRPC response format
        return format_trpc_response(result.dict())
        
    except HTTPException as e:
        return format_trpc_error(e.detail, "BAD_REQUEST")
    except Exception as e:
        logger.error(f"tRPC parseBatch error: {e}")
        return format_trpc_error(str(e), "INTERNAL_SERVER_ERROR")

@router.post("/ingestion.getBatchStatus")
@router.get("/ingestion.getBatchStatus")
async def trpc_get_batch_status(request: Request):
    """
    tRPC wrapper for GET /imports/{batch_id}
    
    Gets the status and details of a batch.
    """
    try:
        input_data = await parse_trpc_request(request)
        
        # Extract batch_id from input
        batch_id = input_data.get("batch_id")
        if not batch_id:
            return format_trpc_error("batch_id is required", "BAD_REQUEST")
        
        from .main import get_batch_status
        
        # Call existing FastAPI endpoint logic
        result = await get_batch_status(batch_id)
        
        # Return tRPC response format
        return format_trpc_response(result.dict())
        
    except HTTPException as e:
        return format_trpc_error(e.detail, "BAD_REQUEST")
    except Exception as e:
        logger.error(f"tRPC getBatchStatus error: {e}")
        return format_trpc_error(str(e), "INTERNAL_SERVER_ERROR")

@router.post("/ingestion.listRaces")
@router.get("/ingestion.listRaces")
async def trpc_list_races(request: Request):
    """
    tRPC wrapper for GET /races/{import_date}
    
    Lists all races for a given import date.
    """
    try:
        input_data = await parse_trpc_request(request)
        
        # Extract import_date from input
        import_date_str = input_data.get("import_date")
        if not import_date_str:
            return format_trpc_error("import_date is required", "BAD_REQUEST")
        
        from .main import list_races
        
        # Convert string to date
        import_date = date.fromisoformat(import_date_str)
        
        # Call existing FastAPI endpoint logic
        result = await list_races(import_date)
        
        # Return tRPC response format
        return format_trpc_response(result)
        
    except ValueError as e:
        return format_trpc_error(f"Invalid date format: {str(e)}", "BAD_REQUEST")
    except HTTPException as e:
        return format_trpc_error(e.detail, "BAD_REQUEST")
    except Exception as e:
        logger.error(f"tRPC listRaces error: {e}")
        return format_trpc_error(str(e), "INTERNAL_SERVER_ERROR")

@router.post("/ingestion.getRaceDetails")
@router.get("/ingestion.getRaceDetails")
async def trpc_get_race_details(request: Request):
    """
    tRPC wrapper for GET /races/{race_id}/details
    
    Gets detailed information about a race including all runners.
    """
    try:
        input_data = await parse_trpc_request(request)
        
        # Extract race_id from input
        race_id = input_data.get("race_id")
        if not race_id:
            return format_trpc_error("race_id is required", "BAD_REQUEST")
        
        from .main import get_race_details
        
        # Call existing FastAPI endpoint logic
        result = await get_race_details(race_id)
        
        # Return tRPC response format
        return format_trpc_response(result)
        
    except HTTPException as e:
        return format_trpc_error(e.detail, "BAD_REQUEST")
    except Exception as e:
        logger.error(f"tRPC getRaceDetails error: {e}")
        return format_trpc_error(str(e), "INTERNAL_SERVER_ERROR")
