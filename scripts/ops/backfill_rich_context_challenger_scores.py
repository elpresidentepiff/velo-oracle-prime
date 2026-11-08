#!/usr/bin/env python3
"""One-time: score the shadow packets written before a fitted model existed.

``rich_context_shadow_packets`` is otherwise append-only (``build_runner_shadow_packet`` sets
``challenger_probability``/``challenger_rank`` to ``null`` and the writer upserts with
``ignore_duplicates=True``, so a normal run never overwrites a packet once stored). Those two fields
were always meant to be filled in once a model existed; this script is the one-time catch-up for the
races scored before 2026-11-08, when ``scripts/research/fit_rich_context_challenger_v1.py`` first
produced an artifact. It reads each packet's already-stored ``feature_families`` (never re-derives
them) and writes back only ``challenger_probability``, ``challenger_rank``, ``challenger_version`` and
``model_status`` for that same row (matched by its own primary key). Every future packet is scored
inline by ``run_prime_today.py`` and needs no backfill.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.rich_context_challenger_scorer import (  # noqa: E402
    load_artifact,
    rank_scored_packets,
    score_packet,
)


def _client():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    return create_client(url, key)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="race_date YYYY-MM-DD to backfill")
    ap.add_argument("--execute", action="store_true", help="write results; default is a dry-run report")
    args = ap.parse_args()

    artifact = load_artifact()
    if artifact is None:
        raise SystemExit("No fitted artifact found (models/rich_context_challenger_v1/); nothing to backfill.")
    print(f"[BACKFILL] artifact: {artifact['metadata'].get('model_version')}")

    client = _client()
    rows = (
        client.table("rich_context_shadow_packets")
        .select("id,race_id,horse_id,feature_families,challenger_probability")
        .eq("race_date", args.date)
        .execute()
        .data
        or []
    )
    print(
        f"[BACKFILL] {args.date}: {len(rows)} packets stored, "
        f"{sum(1 for r in rows if r.get('challenger_probability') is not None)} already scored"
    )

    by_race: dict[str, list[dict]] = {}
    for row in rows:
        by_race.setdefault(str(row["race_id"]), []).append(row)

    updates: list[dict] = []
    scored_n = unscored_n = 0
    for race_rows in by_race.values():
        scored_this_race = [
            (row, score_packet({"families": row.get("feature_families") or {}}, artifact=artifact)) for row in race_rows
        ]
        rank_scored_packets(scored_this_race)  # sets row["challenger_rank"] in place, per race
        for row, result in scored_this_race:
            if result is None:
                unscored_n += 1
                continue
            scored_n += 1
            updates.append(
                {
                    "id": row["id"],
                    "challenger_probability": result["challenger_probability"],
                    "challenger_rank": row.get("challenger_rank"),
                    "challenger_version": result["model_version"],
                    "model_status": "SHADOW_SCORED_V1",
                }
            )

    print(f"[BACKFILL] races={len(by_race)}: scored={scored_n} ineligible={unscored_n}")
    if not args.execute:
        print("[BACKFILL] dry-run (pass --execute to write). Sample:", updates[:2])
        return 0
    written = 0
    for update in updates:
        client.table("rich_context_shadow_packets").update(
            {
                "challenger_probability": update["challenger_probability"],
                "challenger_rank": update["challenger_rank"],
                "challenger_version": update["challenger_version"],
                "model_status": update["model_status"],
            }
        ).eq("id", update["id"]).execute()
        written += 1
    print(f"[BACKFILL] wrote {written} rows for {args.date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
