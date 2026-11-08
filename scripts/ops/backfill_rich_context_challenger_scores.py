#!/usr/bin/env python3
"""One-time: score the shadow packets written before a fitted model existed.

``rich_context_shadow_packets`` has no UPDATE grant for ``service_role`` (append-only by design: the
packet is immutable evidence). Scores for packets written before 2026-11-08, when
``scripts/research/fit_rich_context_challenger_v1.py`` first produced an artifact, go into the
separate append-only ``rich_context_challenger_scores`` table instead, exactly like every packet
scored by the live pipeline from now on (``run_prime_today.py``). This script reads each packet's
already-stored ``feature_families`` (never re-derives them) and only ever inserts a score row.
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
    persist_scores,
    rank_scored_packets,
    score_packet,
    score_row,
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
    model_version = artifact["metadata"].get("model_version")
    print(f"[BACKFILL] artifact: {model_version}")

    client = _client()
    rows = (
        client.table("rich_context_shadow_packets")
        .select("race_date,race_id,horse_id,input_sha256,feature_families")
        .eq("race_date", args.date)
        .execute()
        .data
        or []
    )
    print(f"[BACKFILL] {args.date}: {len(rows)} packets stored")

    by_race: dict[str, list[dict]] = {}
    for row in rows:
        by_race.setdefault(str(row["race_id"]), []).append(row)

    score_rows: list[dict] = []
    scored_n = unscored_n = 0
    for race_rows in by_race.values():
        packets = [
            {
                "race_date": row["race_date"],
                "race_id": row["race_id"],
                "horse_id": row["horse_id"],
                "input_hash": row["input_sha256"],
                "families": row.get("feature_families") or {},
            }
            for row in race_rows
        ]
        scored_this_race = [(packet, score_packet(packet, artifact=artifact)) for packet in packets]
        rank_scored_packets(scored_this_race)  # writes challenger_rank onto each result dict, per race
        for packet, result in scored_this_race:
            if result is None:
                unscored_n += 1
                continue
            scored_n += 1
            score_rows.append(
                score_row(packet, result, code_sha=os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:12] or "backfill")
            )

    print(f"[BACKFILL] races={len(by_race)}: scored={scored_n} ineligible={unscored_n}")
    if not args.execute:
        print("[BACKFILL] dry-run (pass --execute to write). Sample:", score_rows[:2])
        return 0
    result = persist_scores(
        score_rows, client=client, code_sha=os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:12] or "backfill"
    )
    print(f"[BACKFILL] wrote: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
