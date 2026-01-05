"""
VÉLØ Phase 1: Database Client
Supabase PostgreSQL operations with service role access

Date: 2026-01-04
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime, time
from supabase import create_client, Client
from .models import BatchStatus, FileType, RaceData, RunnerData

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
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
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
    
    async def get_batch_by_id(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch by ID"""
        result = self.client.table('import_batches').select('*').eq('id', batch_id).execute()
        
        if not result.data:
            return None
        
        return result.data[0]
    
    async def get_batch_by_date(
        self,
        import_date: date,
        source: str = "racing_post"
    ) -> Optional[Dict[str, Any]]:
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
        error_summary: Optional[str] = None,
        counts: Optional[Dict[str, Any]] = None
    ):
        """Update batch status"""
        data = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if error_summary:
            data["error_summary"] = error_summary
        
        if counts:
            data["counts"] = counts
        
        self.client.table('import_batches').update(data).eq('id', batch_id).execute()
    
    async def get_batch_stats(self, batch_id: str) -> Dict[str, Any]:
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
        mime_type: Optional[str] = None,
        checksum_sha256: Optional[str] = None,
        size_bytes: Optional[int] = None
    ) -> Dict[str, Any]:
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
    
    async def get_batch_files(self, batch_id: str) -> List[Dict[str, Any]]:
        """Get all files for a batch"""
        result = self.client.table('import_files')\
            .select('*')\
            .eq('batch_id', batch_id)\
            .execute()
        
        return result.data or []
    
    async def mark_file_parsed(self, file_id: str, error: Optional[str] = None):
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
        race_data: Dict[str, Any]
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
            "raw": race_data.get('raw', {})
        }
        
        result = self.client.table('races').insert(data).execute()
        
        if not result.data:
            raise ValueError("Failed to insert race")
        
        return result.data[0]['id']
    
    async def get_race_by_id(self, race_id: str) -> Optional[Dict[str, Any]]:
        """Get race by ID"""
        result = self.client.table('races').select('*').eq('id', race_id).execute()
        
        if not result.data:
            return None
        
        return result.data[0]
    
    async def get_races_by_date(self, import_date: date) -> List[Dict[str, Any]]:
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
        runner_data: Dict[str, Any]
    ) -> str:
        """
        Insert a runner record.
        
        Returns the runner_id.
        """
        data = {
            "race_id": race_id,
            "cloth_no": runner_data.get('cloth_no'),
            "horse_name": runner_data.get('horse_name'),
            "age": runner_data.get('age'),
            "sex": runner_data.get('sex'),
            "weight": runner_data.get('weight'),
            "or_rating": runner_data.get('or_rating'),
            "rpr": runner_data.get('rpr'),
            "ts": runner_data.get('ts'),
            "trainer": runner_data.get('trainer'),
            "jockey": runner_data.get('jockey'),
            "owner": runner_data.get('owner'),
            "draw": runner_data.get('draw'),
            "headgear": runner_data.get('headgear'),
            "form_figures": runner_data.get('form_figures'),
            "raw": runner_data.get('raw', {})
        }
        
        result = self.client.table('runners').insert(data).execute()
        
        if not result.data:
            raise ValueError("Failed to insert runner")
        
        return result.data[0]['id']
    
    async def get_race_runners(self, race_id: str) -> List[Dict[str, Any]]:
        """Get all runners for a race"""
        result = self.client.table('runners')\
            .select('*')\
            .eq('race_id', race_id)\
            .order('cloth_no')\
            .execute()
        
        return result.data or []
    
    # ========================================================================
    # FORM LINE OPERATIONS
    # ========================================================================
    
    async def insert_form_line(
        self,
        runner_id: str,
        form_data: Dict[str, Any]
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
    
    async def get_runner_form_lines(self, runner_id: str) -> List[Dict[str, Any]]:
        """Get all form lines for a runner"""
        result = self.client.table('runner_form_lines')\
            .select('*')\
            .eq('runner_id', runner_id)\
            .order('run_date', desc=True)\
            .execute()
        
        return result.data or []

# ============================================================================
# CLIENT FACTORY
# ============================================================================

_db_client: Optional[DatabaseClient] = None

def get_db_client() -> DatabaseClient:
    """Get or create database client singleton"""
    global _db_client
    
    if _db_client is None:
        _db_client = DatabaseClient()
    
    return _db_client
