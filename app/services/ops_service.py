"""
VÉLØ Ops Service — Phase 2
Job tracking with real Supabase writes when execute=True.
Dry-run path is identical to Phase 1 (no DB side effects).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("velo.ops_service")

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "data" / "ops_worker_dry_run"

# Sigma failure taxonomy — ordered by specificity (first match wins)
_SIGMA_PATTERNS: list[tuple[str, list[str]]] = [
    ("API_FAILURE",             ["api error", "http error", "connection error", "timeout", "connectionerror", "httperror"]),
    ("DB_WRITE_FAILURE",        ["db write", "supabase error", "insert failed", "db_write_failure", "postgrest"]),
    ("DUPLICATE_RACE",          ["duplicate race", "duplicate_race", "already reconciled"]),
    ("DUPLICATE_RUNNER",        ["duplicate runner", "duplicate_runner"]),
    ("IDENTITY_MISMATCH",       ["identity mismatch", "horse name mismatch", "identity_mismatch", "name mismatch"]),
    ("NON_RUNNER_CONFLICT",     ["non-runner", "non_runner", "void race", "race void"]),
    ("MISSING_PREDICTION",      ["missing_prediction", "no prediction", "not in verdicts", "prediction not found"]),
    ("AMBIGUOUS_MATCH",         ["ambiguous", "multiple match", "ambiguous_match"]),
    ("CONTEXT_VOID",            ["context void", "no context", "context_void"]),
    ("ODDS_MISSING",            ["odds missing", "sp missing", "no odds", "odds_missing", "no sp"]),
    ("RESULT_PARTIAL",          ["partial result", "incomplete result", "result_partial"]),
    ("MISSING_RESULT",          ["no result", "result not found", "missing_result", "no results available"]),
]


class OpsService:
    """VÉLØ job run persistence. Writes to Supabase when execute=True."""

    def __init__(self, dry_run: bool = True, execute: bool = False):
        self.dry_run = dry_run
        self.execute = execute
        self._sb = None  # lazy-init to avoid crashing at import time

    def _get_sb(self):
        if self._sb is None:
            from src.data.supabase_client import get_supabase_client  # noqa: PLC0415
            self._sb = get_supabase_client()
        return self._sb

    # ── Job lifecycle ──────────────────────────────────────────────────────────

    def start_job(self, date: str, job_type: str) -> str:
        job_id = str(uuid.uuid4())
        if self.execute:
            row = {
                "id": job_id,
                "run_date": date,
                "job_type": job_type,
                "status": "RUNNING",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                self._get_sb().client.table("velo_job_runs").insert(row).execute()
                logger.info("[OpsService] start_job %s/%s → %s (DB written)", job_type, date, job_id)
            except Exception as exc:
                logger.warning("[OpsService] DB start_job failed (continuing): %s", exc)
        else:
            logger.info("[OpsService] DRY-RUN start_job %s/%s → %s", job_type, date, job_id)
        return job_id

    def finish_success(
        self,
        job_id: str,
        metrics: Optional[Dict[str, Any]] = None,
        output_artifacts: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.execute:
            update = {
                "status": "PASS",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics or {},
                "output_artifacts": output_artifacts or {},
            }
            try:
                self._get_sb().client.table("velo_job_runs").update(update).eq("id", job_id).execute()
                logger.info("[OpsService] finish_success %s (DB updated)", job_id)
            except Exception as exc:
                logger.warning("[OpsService] DB finish_success failed: %s", exc)
        else:
            logger.info("[OpsService] DRY-RUN finish_success %s", job_id)

    def finish_failure(self, job_id: str, error_type: str, error_message: str) -> None:
        if self.execute:
            update = {
                "status": "FAIL",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "error_type": error_type,
                "error_message": error_message[:2000],
            }
            try:
                self._get_sb().client.table("velo_job_runs").update(update).eq("id", job_id).execute()
                logger.info("[OpsService] finish_failure %s %s (DB updated)", job_id, error_type)
            except Exception as exc:
                logger.warning("[OpsService] DB finish_failure failed: %s", exc)
        else:
            logger.info("[OpsService] DRY-RUN finish_failure %s %s", job_id, error_type)

    # ── Phase 1 compatibility shims ───────────────────────────────────────────

    def finish_job(self, job_id: str, status: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        if status == "SUCCESS":
            self.finish_success(job_id, metrics=metrics)
        else:
            self.finish_failure(job_id, "UNKNOWN_UNCLASSIFIED", status)

    def log_error(self, job_id: str, error_type: str, message: str) -> None:
        self.finish_failure(job_id, error_type, message)

    # ── Error classification ──────────────────────────────────────────────────

    def classify_error(self, stdout: str, stderr: str, exit_code: int) -> str:
        combined = (stdout + "\n" + stderr).lower()
        for code, patterns in _SIGMA_PATTERNS:
            if any(p in combined for p in patterns):
                return code
        return "UNKNOWN_UNCLASSIFIED"

    # ── Healthcheck reads ─────────────────────────────────────────────────────

    def read_jobs_for_date(self, date: str) -> List[Dict[str, Any]]:
        try:
            result = (
                self._get_sb()
                .client.table("velo_job_runs")
                .select("job_type,status,started_at,finished_at,error_type,metrics")
                .eq("run_date", date)
                .order("created_at")
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("[OpsService] read_jobs_for_date failed: %s", exc)
            return []
