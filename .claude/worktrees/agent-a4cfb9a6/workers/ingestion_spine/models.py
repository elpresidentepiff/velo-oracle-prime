"""
VÉLØ Phase 1: Pydantic Models
API request/response models with strict validation

Date: 2026-01-04
"""

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator

# ============================================================================
# ENUMS
# ============================================================================

class BatchStatus(str, Enum):
    """Batch processing status"""
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    FAILED = "failed"
    REJECTED_BAD_OUTPUT = "rejected_bad_output"  # Hard validation gate failure

class FileType(str, Enum):
    """File type classification"""
    RACECARDS = "racecards"
    RUNNERS = "runners"
    FORM = "form"
    COMMENTS = "comments"
    OTHER = "other"

# ============================================================================
# REQUEST MODELS
# ============================================================================

class CreateBatchRequest(BaseModel):
    """Request to create a new import batch"""
    import_date: date = Field(..., description="Date of the racing data (YYYY-MM-DD)")
    source: str = Field(default="racing_post", description="Data source identifier")
    notes: str | None = Field(None, description="Optional notes about this import")

    class Config:
        json_schema_extra = {
            "example": {
                "import_date": "2026-01-04",
                "source": "racing_post",
                "notes": "Saturday racing - full card"
            }
        }

class FileMetadata(BaseModel):
    """Metadata for a single uploaded file"""
    file_type: FileType = Field(..., description="Type of file (racecards, runners, etc.)")
    storage_path: str = Field(..., description="Path in Supabase storage")
    original_filename: str = Field(..., description="Original filename from upload")
    mime_type: str | None = Field(None, description="MIME type of the file")
    checksum_sha256: str | None = Field(None, description="SHA256 checksum for integrity")
    size_bytes: int | None = Field(None, description="File size in bytes")

    @validator('storage_path')
    def validate_storage_path(cls, v):
        """Ensure storage path follows convention"""
        if not v.startswith('rp_imports/'):
            raise ValueError("Storage path must start with 'rp_imports/'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "file_type": "racecards",
                "storage_path": "rp_imports/2026-01-04/racecards.csv",
                "original_filename": "racecards.csv",
                "mime_type": "text/csv",
                "checksum_sha256": "abc123...",
                "size_bytes": 102400
            }
        }

class RegisterFilesRequest(BaseModel):
    """Request to register multiple files for a batch"""
    files: list[FileMetadata] = Field(..., description="List of file metadata to register")

    @validator('files')
    def validate_required_files(cls, v):
        """Ensure required files are present"""
        file_types = {f.file_type for f in v}
        required = {FileType.RACECARDS, FileType.RUNNERS}

        if not required.issubset(file_types):
            missing = required - file_types
            raise ValueError(f"Missing required files: {', '.join(missing)}")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "files": [
                    {
                        "file_type": "racecards",
                        "storage_path": "rp_imports/2026-01-04/racecards.csv",
                        "original_filename": "racecards.csv",
                        "mime_type": "text/csv",
                        "size_bytes": 102400
                    },
                    {
                        "file_type": "runners",
                        "storage_path": "rp_imports/2026-01-04/runners.csv",
                        "original_filename": "runners.csv",
                        "mime_type": "text/csv",
                        "size_bytes": 204800
                    }
                ]
            }
        }

# ============================================================================
# RESPONSE MODELS
# ============================================================================

class CreateBatchResponse(BaseModel):
    """Response from creating a batch"""
    batch_id: str = Field(..., description="UUID of the created/existing batch")
    status: BatchStatus = Field(..., description="Current batch status")
    message: str = Field(..., description="Human-readable message")
    created_at: datetime = Field(..., description="Batch creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "uploaded",
                "message": "Batch created successfully",
                "created_at": "2026-01-04T10:00:00Z"
            }
        }

class RegisterFilesResponse(BaseModel):
    """Response from registering files"""
    batch_id: str = Field(..., description="UUID of the batch")
    files_registered: int = Field(..., description="Number of files successfully registered")
    message: str = Field(..., description="Human-readable message")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                "files_registered": 2,
                "message": "Files registered successfully"
            }
        }

class ErrorDetail(BaseModel):
    """Detailed error information"""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")

class ParseBatchResponse(BaseModel):
    """Response from parsing a batch"""
    batch_id: str = Field(..., description="UUID of the batch")
    status: BatchStatus = Field(..., description="Current batch status")
    message: str = Field(..., description="Human-readable message")
    counts: dict[str, Any] = Field(default_factory=dict, description="Parse statistics")
    error: ErrorDetail | None = Field(None, description="Error details if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "ready",
                "message": "Batch parsed successfully",
                "counts": {
                    "races_inserted": 45,
                    "runners_inserted": 387,
                    "form_lines_inserted": 0,
                    "unmatched_runner_rows": 0
                }
            }
        }

class BatchStatusResponse(BaseModel):
    """Detailed batch status response"""
    batch_id: str = Field(..., description="UUID of the batch")
    import_date: date = Field(..., description="Import date")
    source: str = Field(..., description="Data source")
    status: BatchStatus = Field(..., description="Current batch status")
    notes: str | None = Field(None, description="Batch notes")
    error_summary: str | None = Field(None, description="Error summary if failed")
    counts: dict[str, Any] = Field(default_factory=dict, description="Parse statistics")
    files_count: int = Field(..., description="Number of registered files")
    races_count: int = Field(..., description="Number of races inserted")
    runners_count: int = Field(..., description="Number of runners inserted")
    created_at: datetime = Field(..., description="Batch creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                "import_date": "2026-01-04",
                "source": "racing_post",
                "status": "ready",
                "notes": "Saturday racing - full card",
                "error_summary": None,
                "counts": {
                    "races_inserted": 45,
                    "runners_inserted": 387
                },
                "files_count": 2,
                "races_count": 45,
                "runners_count": 387,
                "created_at": "2026-01-04T10:00:00Z",
                "updated_at": "2026-01-04T10:05:00Z"
            }
        }

# ============================================================================
# DATABASE MODELS (for internal use)
# ============================================================================

class RaceData(BaseModel):
    """Canonical race data structure"""
    course: str
    off_time: time
    race_name: str | None = None
    race_type: str | None = None
    distance: str | None = None
    class_band: str | None = None
    going: str | None = None
    field_size: int | None = None
    prize: str | None = None
    join_key: str
    raw: dict[str, Any] = Field(default_factory=dict)

class RunnerData(BaseModel):
    """Canonical runner data structure"""
    cloth_no: int | None = None
    horse_name: str
    age: int | None = None
    sex: str | None = None
    weight: str | None = None
    or_rating: int | None = None
    rpr: int | None = None
    ts: int | None = None
    trainer: str | None = None
    jockey: str | None = None
    owner: str | None = None
    draw: int | None = None
    headgear: str | None = None
    form_figures: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

class FormLineData(BaseModel):
    """Form line data structure"""
    run_date: date | None = None
    course: str | None = None
    distance: str | None = None
    going: str | None = None
    position: str | None = None
    rpr: int | None = None
    ts: int | None = None
    or_rating: int | None = None
    notes: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# VALIDATION MODELS
# ============================================================================

class RaceValidationResult(BaseModel):
    """Validation result for a single race"""
    race_id: str = Field(..., description="UUID of the race")
    status: str = Field(..., description="valid | needs_review | rejected")
    issues: list[str] = Field(default_factory=list, description="List of validation issues")
    quality_score: float = Field(..., description="Quality score 0.0-1.0")


class ValidateBatchResponse(BaseModel):
    """Response from validating a batch"""
    batch_id: str = Field(..., description="UUID of the batch")
    total_races: int = Field(..., description="Total number of races")
    valid_count: int = Field(..., description="Number of valid races")
    needs_review_count: int = Field(..., description="Number of races needing review")
    rejected_count: int = Field(..., description="Number of rejected races")
    avg_quality_score: float = Field(..., description="Average quality score")
    new_status: str = Field(..., description="New batch status")
    races: list[RaceValidationResult] = Field(default_factory=list, description="Validation results per race")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "550e8400-e29b-41d4-a716-446655440000",
                "total_races": 45,
                "valid_count": 42,
                "needs_review_count": 2,
                "rejected_count": 1,
                "avg_quality_score": 0.87,
                "new_status": "needs_review",
                "races": [
                    {
                        "race_id": "race-123",
                        "status": "valid",
                        "issues": [],
                        "quality_score": 0.95
                    }
                ]
            }
        }
