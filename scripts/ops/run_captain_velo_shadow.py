#!/usr/bin/env python3
"""Emit a forward-only, non-executing Captain Velo decision packet."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analysis.captain_velo_challenger import (  # noqa: E402
    EVIDENCE_END_DATE,
    MARKET_BLEND_ALPHA,
    MAX_DECIMAL_ODDS,
    MIN_DECIMAL_ODDS,
    MIN_QUOTED_EXPECTED_EDGE,
    MIN_STRUCTURAL_MARKET_RATIO,
    MODEL_VERSION,
    STRUCTURAL_BETA,
    STRUCTURAL_WEIGHTS,
    score_field,
    select_value_pick,
)
from scripts.analysis.playbook_g_full_field_benchmark import select_latest_pre_off_fields  # noqa: E402


def _runner_packet(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "horse": row["horse"],
            "horse_id": row["horse_id"],
            "decimal_odds": row["decimal_odds"],
            "market_probability": round(row["market_probability"], 8),
            "structural_probability": round(row["structural_probability"], 8),
            "consensus_probability": round(row["consensus_probability"], 8),
            "structural_market_ratio": round(row["structural_market_ratio"], 6),
            "quoted_expected_edge": round(row["quoted_expected_edge"], 6),
            "clears_policy": row["eligible"],
        }
        for row in sorted(scored, key=lambda item: (-item["consensus_probability"], item["index"]))
    ]


def build_forward_packet(
    date: str,
    selected_fields: dict[str, list[dict[str, Any]]],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    races = []
    actionable = 0
    for race_id, field in sorted(selected_fields.items()):
        scored = score_field(field)
        if scored is None:
            races.append(
                {
                    "race_id": race_id,
                    "course": field[0].get("course") if field else None,
                    "off_time": field[0].get("off_time") if field else None,
                    "action": "DATA_INCOMPLETE",
                    "selection": None,
                    "runners": [],
                }
            )
            continue
        selection = select_value_pick(field)
        actionable += int(selection is not None)
        races.append(
            {
                "race_id": race_id,
                "course": field[0].get("course"),
                "off_time": field[0].get("off_time"),
                "snapshot_created_at": field[0].get("created_at"),
                "action": "SHADOW_SELECTION" if selection is not None else "ABSTAIN",
                "selection": (
                    None
                    if selection is None
                    else {
                        key: (round(value, 8) if isinstance(value, float) else value)
                        for key, value in selection.items()
                        if key not in {"index", "eligible"}
                    }
                ),
                "runners": _runner_packet(scored),
            }
        )

    return {
        "date": date,
        "generated_at": datetime.now(UTC).isoformat(),
        "model_version": MODEL_VERSION,
        "classification": "FORWARD_ONLY_SHADOW_DECISION_PACKET",
        "evidence_window_ended": EVIDENCE_END_DATE,
        "source": "latest complete strictly pre-off local runner snapshot per race",
        "race_count": len(races),
        "shadow_selection_count": actionable,
        "parameters": {
            "structural_weights": STRUCTURAL_WEIGHTS,
            "structural_beta": STRUCTURAL_BETA,
            "market_blend_alpha": MARKET_BLEND_ALPHA,
            "minimum_structural_market_ratio": MIN_STRUCTURAL_MARKET_RATIO,
            "minimum_quoted_expected_edge": MIN_QUOTED_EXPECTED_EDGE,
            "decimal_odds_range": [MIN_DECIMAL_ODDS, MAX_DECIMAL_ODDS],
        },
        "selection_diagnostics": diagnostics or {},
        "safety": {
            "paper_sim_only": True,
            "bets_placed": False,
            "stakes_generated": False,
            "execution_allowed": False,
            "verdicts_written": False,
            "supabase_writes": False,
            "production_weights_changed": False,
            "production_scoring_changed": False,
            "promotion_authorized": False,
        },
        "promotion_gate": "fresh forward settlements after 2026-09-24 plus explicit operator decision",
        "races": races,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.date <= EVIDENCE_END_DATE:
        print(f"[REFUSED] {args.date} is inside the evidence window through {EVIDENCE_END_DATE}.")
        return 2
    fields, diagnostics = select_latest_pre_off_fields(args.data_dir, args.date, args.date)
    if not fields:
        print(f"[FAIL] No complete strictly pre-off runner snapshots found for {args.date}.")
        return 1
    packet = build_forward_packet(args.date, fields, diagnostics)
    output = args.output or ROOT / "data" / "reports" / f"captain_velo_shadow_{args.date.replace('-', '_')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, indent=2, allow_nan=False), encoding="utf-8")
    print(
        f"CAPTAIN_VELO_SHADOW {args.date}: races={packet['race_count']} "
        f"selections={packet['shadow_selection_count']} -> {output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
