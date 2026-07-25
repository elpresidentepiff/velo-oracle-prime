"""Read-only hydration of the local VELO verdict archive from Supabase."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT))
from src.velo.verdict_loader import load_verdicts as _shared_load_verdicts  # noqa: E402

_COLUMNS = (
    "race_id,generated_at,engine_version,git_commit_sha,environment,"
    "velo_prime_prob,improvement_score,market_deception_score,place_prob,"
    "longshot_prob,release_day_prob,decision_tier,confidence_level,"
    "assigned_product,router_reasons,execution_allowed,top_rank_horse_id,"
    "selections,full_analysis,active_components,excluded_from_ensemble,"
    "g_shadow_multiplier,g_shadow_flags"
)


def _fetch_verdicts(target: str) -> tuple[list[dict], str]:
    """Fetch verdicts for target date via the shared, bug-fixed loader.

    See src/velo/verdict_loader.py for why this can't be a hand-rolled
    generated_at query. This script used to try two separate generated_at
    windows (uk_window, utc_day) before a race_id fallback that queried a
    `races` table which turned out to be dead (fed by the decommissioned
    Racing API, last populated 2026-05-06) -- both of those were symptoms of
    not having race_id-first querying as the default. The shared loader
    supersedes all of that.
    """
    rows, method = _shared_load_verdicts(target, select=_COLUMNS, root=ROOT)
    rows.sort(key=lambda r: r.get("velo_prime_prob") or 0.0, reverse=True)
    return rows, method


def sync_local_verdict_archive(target: str) -> dict:
    """Hydrate the canonical dated local verdict file without scoring or DB writes."""
    output = DATA / f"velo_prime_verdicts_{target.replace('-', '_')}.json"
    rows, method = _fetch_verdicts(target)
    if not rows:
        return {
            "status": "NO_VERDICTS_FOUND",
            "date": target,
            "query_method": method,
            "row_count": 0,
            "path": str(output),
        }
    output.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return {
        "status": "LOCAL_HYDRATED",
        "date": target,
        "query_method": method,
        "row_count": len(rows),
        "path": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    args = parser.parse_args()
    print(json.dumps(sync_local_verdict_archive(args.date), indent=2))


if __name__ == "__main__":
    main()
