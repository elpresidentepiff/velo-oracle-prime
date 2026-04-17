"""
VÉLØ Phase 1: Storage Client
Supabase Storage operations for file upload/download

Date: 2026-01-04
"""

import os
import logging
from typing import Optional, BinaryIO
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# ============================================================================
# STORAGE CLIENT
# ============================================================================

class StorageClient:
    """
    Supabase storage client for VÉLØ Ingestion Spine.
    Handles file upload/download from rp_imports bucket.
    """
    
    BUCKET_NAME = "rp_imports"
    
    def __init__(self):
        """Initialize Supabase client with service role"""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Service role for full access
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        
        self.client: Client = create_client(self.url, self.key)
        logger.info("Storage client initialized")
    
    async def verify_connection(self):
        """Verify storage connection"""
        try:
            # List buckets to verify connection
            buckets = self.client.storage.list_buckets()
            
            # Check if rp_imports bucket exists
            bucket_names = [b['name'] for b in buckets]
            if self.BUCKET_NAME not in bucket_names:
                logger.warning(f"Bucket '{self.BUCKET_NAME}' not found. Available: {bucket_names}")
            else:
                logger.info(f"Storage connection verified. Bucket '{self.BUCKET_NAME}' found.")
        except Exception as e:
            logger.error(f"Storage connection failed: {e}")
            raise
    
    async def close(self):
        """Close storage connection"""
        # Supabase client doesn't require explicit close
        logger.info("Storage client closed")
    
    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================
    
    async def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            path: Full path in bucket (e.g., "rp_imports/2026-01-04/racecards.csv")
        
        Returns:
            True if file exists, False otherwise
        """
        try:
            # Remove bucket prefix if present
            if path.startswith(f"{self.BUCKET_NAME}/"):
                path = path[len(f"{self.BUCKET_NAME}/"):]
            
            # List files in the directory
            folder = "/".join(path.split("/")[:-1])
            filename = path.split("/")[-1]
            
            files = self.client.storage.from_(self.BUCKET_NAME).list(folder)
            
            # Check if file exists
            return any(f['name'] == filename for f in files)
        
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False
    
    async def download_file(self, path: str) -> bytes:
        """
        Download a file from storage.
        
        Args:
            path: Full path in bucket (e.g., "rp_imports/2026-01-04/racecards.csv")
        
        Returns:
            File content as bytes
        """
        try:
            # Remove bucket prefix if present
            if path.startswith(f"{self.BUCKET_NAME}/"):
                path = path[len(f"{self.BUCKET_NAME}/"):]
            
            # Download file
            response = self.client.storage.from_(self.BUCKET_NAME).download(path)
            
            if not response:
                raise ValueError(f"File not found: {path}")
            
            logger.info(f"Downloaded file: {path} ({len(response)} bytes)")
            return response
        
        except Exception as e:
            logger.error(f"Error downloading file {path}: {e}")
            raise
    
    async def upload_file(
        self,
        path: str,
        file_data: bytes,
        mime_type: str = "text/csv"
    ) -> str:
        """
        Upload a file to storage.
        
        Args:
            path: Full path in bucket (e.g., "rp_imports/2026-01-04/racecards.csv")
            file_data: File content as bytes
            mime_type: MIME type of the file
        
        Returns:
            Public URL of the uploaded file (if applicable)
        """
        try:
            # Remove bucket prefix if present
            if path.startswith(f"{self.BUCKET_NAME}/"):
                path = path[len(f"{self.BUCKET_NAME}/"):]
            
            # Upload file
            response = self.client.storage.from_(self.BUCKET_NAME).upload(
                path=path,
                file=file_data,
                file_options={"content-type": mime_type}
            )
            
            logger.info(f"Uploaded file: {path} ({len(file_data)} bytes)")
            
            # Return the path (bucket is private, so no public URL)
            return f"{self.BUCKET_NAME}/{path}"
        
        except Exception as e:
            logger.error(f"Error uploading file {path}: {e}")
            raise
    
    async def delete_file(self, path: str):
        """
        Delete a file from storage.
        
        Args:
            path: Full path in bucket (e.g., "rp_imports/2026-01-04/racecards.csv")
        """
        try:
            # Remove bucket prefix if present
            if path.startswith(f"{self.BUCKET_NAME}/"):
                path = path[len(f"{self.BUCKET_NAME}/"):]
            
            # Delete file
            self.client.storage.from_(self.BUCKET_NAME).remove([path])
            
            logger.info(f"Deleted file: {path}")
        
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
            raise
    
    async def list_files(self, folder: str = "") -> list:
        """
        List files in a folder.
        
        Args:
            folder: Folder path (e.g., "2026-01-04")
        
        Returns:
            List of file metadata
        """
        try:
            files = self.client.storage.from_(self.BUCKET_NAME).list(folder)
            
            logger.info(f"Listed {len(files)} files in folder: {folder}")
            return files
        
        except Exception as e:
            logger.error(f"Error listing files in {folder}: {e}")
            raise
    
    async def get_file_metadata(self, path: str) -> dict:
        """
        Get metadata for a file.
        
        Args:
            path: Full path in bucket
        
        Returns:
            File metadata dictionary
        """
        try:
            # Remove bucket prefix if present
            if path.startswith(f"{self.BUCKET_NAME}/"):
                path = path[len(f"{self.BUCKET_NAME}/"):]
            
            # Get file info by listing parent folder
            folder = "/".join(path.split("/")[:-1])
            filename = path.split("/")[-1]
            
            files = self.client.storage.from_(self.BUCKET_NAME).list(folder)
            
            # Find the file
            for file in files:
                if file['name'] == filename:
                    return file
            
            raise ValueError(f"File not found: {path}")
        
        except Exception as e:
            logger.error(f"Error getting file metadata for {path}: {e}")
            raise
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def generate_path(self, import_date: str, file_type: str, extension: str = "csv") -> str:
        """
        Generate a standard storage path.
        
        Args:
            import_date: Date in YYYY-MM-DD format
            file_type: Type of file (racecards, runners, etc.)
            extension: File extension (default: csv)
        
        Returns:
            Full storage path
        """
        return f"{self.BUCKET_NAME}/{import_date}/{file_type}.{extension}"
    
    def parse_path(self, path: str) -> dict:
        """
        Parse a storage path into components.
        
        Args:
            path: Full storage path
        
        Returns:
            Dictionary with date, file_type, extension
        """
        # Remove bucket prefix if present
        if path.startswith(f"{self.BUCKET_NAME}/"):
            path = path[len(f"{self.BUCKET_NAME}/"):]
        
        parts = path.split("/")
        
        if len(parts) < 2:
            raise ValueError(f"Invalid path format: {path}")
        
        import_date = parts[0]
        filename = parts[1]
        file_type, extension = filename.rsplit(".", 1) if "." in filename else (filename, "")
        
        return {
            "import_date": import_date,
            "file_type": file_type,
            "extension": extension,
            "filename": filename
        }

# ============================================================================
# CLIENT FACTORY
# ============================================================================

_storage_client: Optional[StorageClient] = None

def get_storage_client() -> StorageClient:
    """Get or create storage client singleton"""
    global _storage_client
    
    if _storage_client is None:
        _storage_client = StorageClient()
    
    return _storage_client
