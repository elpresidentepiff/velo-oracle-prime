# scripts/integrity_hooks.py

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from supabase import Client

@dataclass
class IntegrityResult:
    ok: bool
    duplicate_count: int
    missing_winner_count: int
    missing_vector_count: int
    checked_race_count: int
    detail: str = ""

def run_integrity_checks_via_rpc(
    sb: Client,
    reconstruction_version: str,
    min_race_id: Optional[str] = None,
    max_race_id: Optional[str] = None,
    fail_fast: bool = True,
) -> IntegrityResult:
    resp = sb.rpc(
        "hfs_integrity_metrics",
        {
            "p_reconstruction_version": reconstruction_version,
            "p_min_race_id": min_race_id,
            "p_max_race_id": max_race_id,
        },
    ).execute()
    
    data: Dict[str, Any] = resp.data or {}
    result = IntegrityResult(
        ok=bool(data.get("ok", False)),
        duplicate_count=int(data.get("duplicate_count", 0)),
        missing_winner_count=int(data.get("missing_winner_count", 0)),
        missing_vector_count=int(data.get("missing_vector_count", 0)),
        checked_race_count=int(data.get("checked_race_count", 0))
    )
    result.detail = (
        f"ok={result.ok} dupes={result.duplicate_count} "
        f"missing_winners={result.missing_winner_count} "
        f"missing_vectors={result.missing_vector_count} checked_races={result.checked_race_count}"
    )
    
    if fail_fast and not result.ok:
        raise RuntimeError(f"Integrity gate failed: {result.detail}")
    
    return result

def log_integrity(result: IntegrityResult) -> None:
    if result.ok:
        logging.info("INTEGRITY PASS %s", result.detail)
    else:
        logging.error("INTEGRITY FAIL %s", result.detail)
