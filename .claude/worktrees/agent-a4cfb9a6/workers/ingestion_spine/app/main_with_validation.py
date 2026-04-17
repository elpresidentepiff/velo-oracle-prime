"""
VÉLØ Racing Post Parser API - Integration Example
Shows how to integrate racingpost_pdf module with validation gates.

This example demonstrates:
1. Parsing PDFs with the new racingpost_pdf module
2. Running hard validation gates
3. Blocking bad output from database insert
4. Returning validation errors to client
"""

import os
import sys
from typing import List
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from racingpost_pdf import parse_meeting
from models import BatchStatus


# Request/Response models
class ParseBatchRequest(BaseModel):
    """Request to parse a batch of PDFs"""
    batch_id: str
    pdf_paths: List[str]


class ParseBatchResponse(BaseModel):
    """Response from parsing a batch"""
    batch_id: str
    status: BatchStatus
    message: str
    races_count: int = 0
    runners_count: int = 0
    errors: List[str] = []


# FastAPI app
app = FastAPI(title="VÉLØ RP Parser with Validation Gates", version="2.0.0")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True, "service": "velo-rp-parser-v2", "features": ["validation_gates"]}


@app.post("/imports/{batch_id}/parse", response_model=ParseBatchResponse)
async def parse_batch(batch_id: str, request: ParseBatchRequest):
    """
    Parse PDFs → validate → insert only if clean.
    
    This endpoint:
    1. Parses all PDFs (XX, OR, TS, PM)
    2. Runs hard validation gates
    3. Rejects batch if ANY gate fails
    4. Only inserts to Supabase if ALL gates pass
    
    Returns:
        ParseBatchResponse with status and any errors
        
    Status codes:
        - 200: Parse succeeded, validation passed
        - 422: Parse succeeded, validation FAILED (rejected_bad_output)
        - 500: Parse failed (technical error)
    """
    
    # 1. Parse PDFs
    try:
        report = parse_meeting(request.pdf_paths, validate_output=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parse failed: {str(e)}"
        )
    
    # 2. Check validation status
    if not report.success:
        # Hard gates failed → rejected_bad_output
        
        # TODO: Update batch status in database
        # await db.execute(
        #     """UPDATE import_batches 
        #        SET status = 'rejected_bad_output',
        #            validation_errors = $1
        #        WHERE id = $2""",
        #     [e.message for e in report.errors],
        #     batch_id
        # )
        
        return ParseBatchResponse(
            batch_id=batch_id,
            status=BatchStatus.REJECTED_BAD_OUTPUT,
            message=f"Parse failed validation gates. {len(report.errors)} errors found. NO INSERT.",
            errors=[e.message for e in report.errors]
        )
    
    # 3. Insert to Supabase (only if clean)
    meeting = report.meeting
    
    # TODO: Insert races and runners to database
    # await db.insert_meeting(meeting)
    
    # 4. Update batch status to 'parsed'
    # TODO: Update batch status in database
    # await db.execute(
    #     "UPDATE import_batches SET status = 'parsed' WHERE id = $1",
    #     batch_id
    # )
    
    return ParseBatchResponse(
        batch_id=batch_id,
        status=BatchStatus.PARSED,
        message="Parse successful. All validation gates passed.",
        races_count=len(meeting.races),
        runners_count=sum(len(r.runners) for r in meeting.races)
    )


@app.post("/imports/{batch_id}/validate-only")
async def validate_only(batch_id: str, request: ParseBatchRequest):
    """
    Validate PDFs without inserting (dry-run).
    
    Useful for:
    - Testing validation gates
    - Checking data quality before import
    - Debugging parse issues
    """
    
    try:
        report = parse_meeting(request.pdf_paths, validate_output=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parse failed: {str(e)}"
        )
    
    if not report.success:
        return {
            "valid": False,
            "errors": [e.dict() for e in report.errors],
            "warnings": [e.dict() for e in report.warnings],
            "stats": report.stats
        }
    
    return {
        "valid": True,
        "errors": [],
        "warnings": [e.dict() for e in report.warnings],
        "stats": report.stats,
        "meeting": {
            "course": report.meeting.course_name,
            "date": str(report.meeting.meeting_date),
            "races_count": len(report.meeting.races),
            "runners_count": sum(len(r.runners) for r in report.meeting.races)
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
