"""
Utility to generate and save pipeline run summary artifacts.
"""
import json
import os
import pathlib
import time
from datetime import datetime, UTC

def write_summary(
    *,
    pipeline_type: str,
    target_date: str,
    status: str,
    source: str = "unknown",
    counts: dict | None = None,
    degraded_reasons: list[str] | None = None,
    error: str | None = None,
    artifact_path: pathlib.Path | None = None
):
    from app.core.runtime_env import get_commit_sha
    
    summary = {
        "pipeline": pipeline_type,
        "target_date": target_date,
        "status": status,
        "source": source,
        "generated_at": datetime.now(UTC).isoformat(),
        "commit_sha": get_commit_sha(),
        "modes": {
            "g_shadow": os.getenv("VELO_G_SHADOW_MODE", "shadow"),
            "execution": os.getenv("VELO_EXECUTION_MODE", "PAPER"),
        },
        "counts": counts or {},
        "degraded_reasons": degraded_reasons or [],
        "error": error
    }
    
    if artifact_path:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Pipeline summary written to: {artifact_path}")
    
    return summary
