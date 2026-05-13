"""
VÉLØ Ops Service Stub
Deterministic job tracking and persistence.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("velo.ops_service")

class OpsService:
    """Stub for VÉLØ job run persistence."""

    def __init__(self, dry_run: bool = True, execute: bool = False):
        self.dry_run = dry_run
        self.execute = execute

    def start_job(self, date: str, job_type: str) -> str:
        """Start a job run and return its ID."""
        logger.info("[OpsService] Starting %s job for %s (execute=%s)", job_type, date, self.execute)
        return "stub-job-id"

    def finish_job(self, job_id: str, status: str, metrics: Optional[Dict[str, Any]] = None):
        """Finish a job run with status and metrics."""
        logger.info("[OpsService] Finishing job %s with status %s", job_id, status)

    def log_error(self, job_id: str, error_type: str, message: str):
        """Log an error for a job run."""
        logger.error("[OpsService] Job %s failed: %s - %s", job_id, error_type, message)
