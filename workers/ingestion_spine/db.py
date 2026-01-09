"""
VÉLØ Phase 1: Database Client
Supabase PostgreSQL operations with service role access

Date: 2026-01-04
"""

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

from supabase import Client, create_client

from .models import BatchStatus, FileType

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CLIENT
# ============================================================================

class DatabaseClient:
    """
    Supabase database client for VÉLØ Ingestion Spine.
    Uses service role for full write access.
    """

    def __init__(self):
        """Initialize Supabase client with service role"""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Service role, not anon key

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

        self.client: Client = create_client(self.url, self.key)
        logger.info("Database client initialized")

    async def verify_connection(self):
        """Verify database connection"""
        try:
            # Simple query to verify connection
            result = self.client.table('import_batches').select('count').execute()
            logger.info("Database connection verified")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    async def close(self):
        """Close database connection"""
        # Supabase client doesn't require explicit close
        logger.info("Database client closed")

    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================

    async def create_batch(
        self,
        import_date: date,
        source: str = "racing_post",
        notes: str | None = None
    ) -> dict[str, Any]:
        """
        Create a new import batch.
        
        Returns the created batch record.
        """
        data = {
            "import_date": import_date.isoformat(),
            "source": source,
            "status": BatchStatus.UPLOADED.value,
            "notes": notes,
            "counts": {}
        }

        result = self.client.table('import_batches').insert(data).execute()

        if not result.data:
            raise ValueError("Failed to create batch")

        return result.data[0]

    async def get_batch_by_id(self, batch_id: str) -> dict[str, Any] | None:
        """Get batch by ID"""
        result = self.client.table('import_batches').select('*').eq('id', batch_id).execute()

        if not result.data:
            return None

        return result.data[0]

    async def get_batch_by_date(
        self,
        import_date: date,
        source: str = "racing_post"
    ) -> dict[str, Any] | None:
        """Get batch by import date and source"""
        result = self.client.table('import_batches')\
            .select('*')\
            .eq('import_date', import_date.isoformat())\
            .eq('source', source)\
            .execute()

        if not result.data:
            return None

        return result.data[0]

    async def update_batch_status(
        self,
        batch_id: str,
        status: BatchStatus,
        error_summary: str | None = None,
        counts: dict[str, Any] | None = None
    ):
        """
        Update batch status with validation
        
        Valid transitions:
        - uploaded -> parsing -> parsed -> validated | needs_review
        """
        valid_statuses = [
            "uploaded", "parsing", "parsed", "validated", "needs_review", "ready", "failed"
        ]

        status_value = status.value if isinstance(status, BatchStatus) else status

        if status_value not in valid_statuses:
            raise ValueError(f"Invalid status: {status_value}")

        data = {
            "status": status_value,
            "updated_at": datetime.utcnow().isoformat()
        }

        if error_summary:
            data["error_summary"] = error_summary

        if counts:
            data["counts"] = counts

        self.client.table('import_batches').update(data).eq('id', batch_id).execute()

    async def get_batch_stats(self, batch_id: str) -> dict[str, Any]:
        """Get batch statistics using helper function"""
        result = self.client.rpc('get_batch_stats', {'p_batch_id': batch_id}).execute()

        if not result.data:
            return {}

        return result.data

    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================

    async def register_file(
        self,
        batch_id: str,
        file_type: FileType,
        storage_path: str,
        original_filename: str,
        mime_type: str | None = None,
        checksum_sha256: str | None = None,
        size_bytes: int | None = None
    ) -> dict[str, Any]:
        """Register a file for a batch"""
        data = {
            "batch_id": batch_id,
            "file_type": file_type.value,
            "storage_path": storage_path,
            "original_filename": original_filename,
            "mime_type": mime_type,
            "checksum_sha256": checksum_sha256,
            "size_bytes": size_bytes
        }

        result = self.client.table('import_files').insert(data).execute()

        if not result.data:
            raise ValueError("Failed to register file")

        return result.data[0]

    async def get_batch_files(self, batch_id: str) -> list[dict[str, Any]]:
        """Get all files for a batch"""
        result = self.client.table('import_files')\
            .select('*')\
            .eq('batch_id', batch_id)\
            .execute()

        return result.data or []

    async def mark_file_parsed(self, file_id: str, error: str | None = None):
        """Mark a file as parsed"""
        data = {
            "parsed_at": datetime.utcnow().isoformat()
        }

        if error:
            data["error"] = error

        self.client.table('import_files').update(data).eq('id', file_id).execute()

    # ========================================================================
    # RACE OPERATIONS
    # ========================================================================

    async def insert_race(
        self,
        batch_id: str,
        import_date: date,
        race_data: dict[str, Any]
    ) -> str:
        """
        Insert a race record.
        
        Returns the race_id.
        """
        data = {
            "batch_id": batch_id,
            "import_date": import_date.isoformat(),
            "course": race_data.get('course'),
            "off_time": race_data.get('off_time'),
            "race_name": race_data.get('race_name'),
            "race_type": race_data.get('race_type'),
            "distance": race_data.get('distance'),
            "class_band": race_data.get('class_band'),
            "going": race_data.get('going'),
            "field_size": race_data.get('field_size'),
            "prize": race_data.get('prize'),
            "join_key": race_data.get('join_key'),
            "raw": race_data.get('raw', {}),
            # Quality metadata
            "parse_confidence": race_data.get('parse_confidence'),
            "quality_score": race_data.get('quality_score'),
            "quality_flags": race_data.get('quality_flags', [])
        }

        result = self.client.table('races').insert(data).execute()

        if not result.data:
            raise ValueError("Failed to insert race")

        return result.data[0]['id']

    async def get_race_by_id(self, race_id: str) -> dict[str, Any] | None:
        """Get race by ID"""
        result = self.client.table('races').select('*').eq('id', race_id).execute()

        if not result.data:
            return None

        return result.data[0]

    async def get_races_by_date(self, import_date: date) -> list[dict[str, Any]]:
        """Get all races for a date"""
        result = self.client.table('races')\
            .select('*')\
            .eq('import_date', import_date.isoformat())\
            .order('off_time')\
            .execute()

        return result.data or []

    # ========================================================================
    # RUNNER OPERATIONS
    # ========================================================================

    async def insert_runner(
        self,
        race_id: str,
        runner_data: dict[str, Any]
    ) -> str:
        """
        Insert runner into racecards table (one row per horse).
        
        NOTE: Database schema uses 'racecards' not 'runners' table.
        Each row = one horse in one race.
        
        Returns the racecard_id.
        """
        data = {
            # Link to race
            "race_id": race_id,
            
            # Race context (from parent race or passed in runner_data)
            "date": runner_data.get('date'),
            "course": runner_data.get('course'),
            "off_time": runner_data.get('off_time'),
            "race_name": runner_data.get('race_name', ''),
            "distance": runner_data.get('distance'),
            "going": runner_data.get('going'),
            
            # Runner-specific data
            "horse": runner_data.get('horse_name'),
            "jockey": runner_data.get('jockey'),
            "trainer": runner_data.get('trainer'),
            "weight": runner_data.get('weight'),
            "draw": runner_data.get('draw'),
            "age": runner_data.get('age'),
            "official_rating": runner_data.get('or_rating'),
            "form": runner_data.get('form_figures'),
            "odds": runner_data.get('odds'),
            "last_run_date": runner_data.get('last_run_date')
            # scraped_at uses database DEFAULT NOW()
        }

        # INSERT INTO racecards (not runners!)
        result = self.client.table('racecards').insert(data).execute()

        if not result.data:
            raise ValueError("Failed to insert runner into racecards")

        return result.data[0]['id']

    async def get_race_runners(self, race_id: str) -> list[dict[str, Any]]:
        """Get all runners for a race from racecards table"""
        result = self.client.table('racecards')\
            .select('*')\
            .eq('race_id', race_id)\
            .order('draw')\
            .execute()

        return result.data or []

    # ========================================================================
    # FORM LINE OPERATIONS
    # ========================================================================

    async def insert_form_line(
        self,
        runner_id: str,
        form_data: dict[str, Any]
    ) -> str:
        """
        Insert a form line record.
        
        Returns the form_line_id.
        """
        data = {
            "runner_id": runner_id,
            "run_date": form_data.get('run_date'),
            "course": form_data.get('course'),
            "distance": form_data.get('distance'),
            "going": form_data.get('going'),
            "position": form_data.get('position'),
            "rpr": form_data.get('rpr'),
            "ts": form_data.get('ts'),
            "or_rating": form_data.get('or_rating'),
            "notes": form_data.get('notes'),
            "raw": form_data.get('raw', {})
        }

        result = self.client.table('runner_form_lines').insert(data).execute()

        if not result.data:
            raise ValueError("Failed to insert form line")

        return result.data[0]['id']

    async def get_runner_form_lines(self, runner_id: str) -> list[dict[str, Any]]:
        """Get all form lines for a runner"""
        result = self.client.table('runner_form_lines')\
            .select('*')\
            .eq('runner_id', runner_id)\
            .order('run_date', desc=True)\
            .execute()

        return result.data or []

    # ========================================================================
    # SMOKE BATCH CLEANUP
    # ========================================================================

    async def delete_old_smoke_batches(
        self,
        source: str = "smoke_test",
        older_than: datetime = None
    ) -> int:
        """
        Delete smoke test batches older than specified time
        
        Args:
            source: Source identifier for smoke batches (default: "smoke_test")
            older_than: Delete batches created before this datetime
        
        Returns:
            Number of batches deleted
        """
        if older_than is None:
            older_than = datetime.utcnow() - timedelta(hours=1)

        result = self.client.table("import_batches").delete().match({
            "source": source
        }).lt("created_at", older_than.isoformat()).execute()

        return len(result.data) if result.data else 0

    # ========================================================================
    # VALIDATION OPERATIONS
    # ========================================================================

    async def store_validation_report(self, batch_id: str, report: dict) -> dict[str, Any] | None:
        """
        Store validation report on batch record
        
        Args:
            batch_id: UUID of the batch
            report: Validation report dictionary
        
        Returns:
            Updated batch record
        """
        result = self.client.table("import_batches").update({
            "validation_report": report,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", batch_id).execute()

        return result.data[0] if result.data else None

    async def get_batch_races(self, batch_id: str) -> list[dict[str, Any]]:
        """
        Get all races for a batch
        
        Args:
            batch_id: UUID of the batch
        
        Returns:
            List of race records with all fields
        """
        result = self.client.table("races").select("*").eq(
            "batch_id", batch_id
        ).execute()

        return result.data if result.data else []
    
    # ========================================================================
    # FEATURE MART OPERATIONS
    # ========================================================================
    
    async def build_feature_mart(self, as_of_date: date) -> None:
        """
        Build feature mart for a specific as_of_date.
        
        Calls the PostgreSQL build_feature_mart function to compute
        deterministic trainer, jockey, JT combo, and course/distance stats.
        
        Args:
            as_of_date: Date to use as reference for feature computation
        """
        try:
            # Supabase uses RPC to call PostgreSQL functions
            date_str = as_of_date.isoformat() if isinstance(as_of_date, date) else as_of_date
            
            # Note: Supabase RPC requires the function to return something
            # Our function returns VOID, so this might need adjustment
            result = self.client.rpc('build_feature_mart', {
                'p_as_of_date': date_str
            }).execute()
            
            logger.info(f"Feature mart built for as_of_date: {date_str}")
            
        except Exception as e:
            logger.error(f"Failed to build feature mart: {e}")
            raise

# ============================================================================
# CLIENT FACTORY
# ============================================================================

_db_client: DatabaseClient | None = None

def get_db_client() -> DatabaseClient:
    """Get or create database client singleton"""
    global _db_client

    if _db_client is None:
        _db_client = DatabaseClient()

    return _db_client
