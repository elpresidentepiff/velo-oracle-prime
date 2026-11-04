"""Recover durable runner snapshots from an already-frozen Prime verdict.

This is an idempotent operational recovery path for a completed scoring date
whose auxiliary runner snapshot insert failed.  It reuses the immutable
``full_analysis.predictions`` already stored in ``velo_verdicts``; it does not
call the model, recompute probabilities, or modify the verdict.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from src.velo.runner_snapshot_store import build_run_id, write_runner_snapshots  # noqa: E402
from src.velo.verdict_loader import load_verdicts  # noqa: E402


def _race_metadata(date_str: str) -> dict[str, dict]:
    path = DATA / f"racecards_{date_str.replace('-', '_')}_standard.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    races = payload.get("racecards", []) if isinstance(payload, dict) else payload
    return {str(race.get("race_id")): race for race in races if isinstance(race, dict) and race.get("race_id")}


def recover(date_str: str, output_dir: Path = DATA) -> dict:
    verdicts, query_method = load_verdicts(date_str, select="*")
    metadata = _race_metadata(date_str)
    scored = []
    skipped = []
    for verdict in verdicts:
        race_id = str(verdict.get("race_id") or "")
        predictions = (verdict.get("full_analysis") or {}).get("predictions") or []
        if not race_id or not predictions:
            skipped.append(race_id or "MISSING_RACE_ID")
            continue
        race = dict(metadata.get(race_id) or {})
        race.update(
            {
                "race_id": race_id,
                "course": race.get("course") or verdict.get("course") or "",
                "off_time": race.get("off_time") or verdict.get("off_time") or "",
            }
        )
        scored.append((race, predictions, verdict.get("decision_tier") or "", []))

    if not scored:
        return {
            "status": "NO_FROZEN_RUNNER_PREDICTIONS",
            "date": date_str,
            "query_method": query_method,
            "rows": 0,
            "races": 0,
            "skipped": skipped,
        }

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase service credentials are required")
    client = create_client(url, key)
    run_id = build_run_id(date_str.replace("-", "_"), os.getenv("RAILWAY_GIT_COMMIT_SHA", "recovery"))
    written = write_runner_snapshots(
        scored,
        date_str,
        date_str.replace("-", "_"),
        run_id=run_id,
        snapshot_dir=output_dir,
        supabase_client=client,
    )
    return {
        "status": "RECOVERED_FROM_FROZEN_VERDICTS" if written else "RECOVERY_WRITE_FAILED",
        "date": date_str,
        "query_method": query_method,
        "run_id": run_id,
        "rows": written,
        "races": len(scored),
        "skipped": skipped,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "scoring_recomputed": False,
        "verdicts_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output-dir", type=Path, default=DATA)
    args = parser.parse_args()
    result = recover(args.date, args.output_dir)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["status"] == "RECOVERED_FROM_FROZEN_VERDICTS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
