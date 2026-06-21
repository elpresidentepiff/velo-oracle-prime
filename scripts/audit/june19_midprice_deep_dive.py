#!/usr/bin/env python3
"""June 19 mid-price deep dive.

Evidence-only audit used to prime June 20 rules. It joins:
  - sigma reconciliation rows
  - RP final results
  - per-runner snapshots
  - top-pick verdicts

No scoring, routing, or execution state is changed.
"""

from __future__ import annotations

import collections
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-06-19"
TAG = DATE.replace("-", "_")


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _load_snapshot_rows() -> dict[str, list[dict[str, Any]]]:
    paths = sorted((ROOT / "data").glob(f"runner_snapshots_{TAG}*.jsonl"))
    if not paths:
        raise FileNotFoundError(f"runner_snapshots_{TAG}*.jsonl")
    latest = max(paths, key=lambda p: p.stat().st_mtime)
    races: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for line in latest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        races[str(row.get("race_id"))].append(row)
    for rows in races.values():
        rows.sort(key=lambda r: int(r.get("rank") if r.get("rank") is not None else 99))
    return races


def _midprice_action(tier: str, vp: float, mds: float, imp: float) -> str:
    if tier == "A" and vp >= 0.40 and mds < 0.20 and imp < 0.20:
        return "MIDPRICE_SPLIT_RACE"
    if vp >= 0.30 and mds < 0.30:
        return "MIDPRICE_SUPPRESS_TOP"
    if 0.20 <= vp < 0.30 and mds < 0.05 and imp < 0.10:
        return "MIDPRICE_NO_EDGE"
    return "MIDPRICE_CLEAN"


def _field_band(field_size: int) -> str:
    if field_size <= 5:
        return "FS_2_5"
    if 6 <= field_size <= 8:
        return "FS_6_8"
    if 9 <= field_size <= 12:
        return "FS_9_12"
    return "FS_13_PLUS"


def build_rows() -> list[dict[str, Any]]:
    sigma = json.loads((ROOT / "data" / "sigma_results" / f"sigma_results_{TAG}.json").read_text())
    verdicts = json.loads((ROOT / "data" / f"velo_prime_verdicts_{TAG}.json").read_text())
    results = json.loads((ROOT / "data" / "results" / f"rp_results_{TAG}.json").read_text())
    snapshots = _load_snapshot_rows()

    verdict_by_race = {str(v.get("race_id")): v for v in verdicts}
    result_by_race = {str(r.get("race_id")): r for r in results.get("results", [])}
    rows: list[dict[str, Any]] = []

    for sigma_row in sigma.get("rows", []):
        race_id = str(sigma_row.get("race_id"))
        snap_rows = snapshots.get(race_id, [])
        verdict = verdict_by_race.get(race_id)
        result = result_by_race.get(race_id, {})
        if not snap_rows or not verdict:
            continue

        winner = sigma_row.get("actual_name") or result.get("winner_horse")
        winner_row = next((r for r in snap_rows if norm(r.get("horse")) == norm(winner)), None)
        if not winner_row:
            continue

        top = snap_rows[0]
        field_size = int(result.get("field_size") or len(snap_rows))
        action = _midprice_action(
            str(verdict.get("tier") or ""),
            float(top.get("velo_prime_prob") or 0),
            float(top.get("market_deception_score") or 0),
            float(top.get("improvement_score") or 0),
        )
        rows.append(
            {
                "race_id": race_id,
                "course": sigma_row.get("course"),
                "off": sigma_row.get("off"),
                "tier": verdict.get("tier"),
                "race_class": result.get("race_class"),
                "field_size": field_size,
                "field_band": _field_band(field_size),
                "outcome": sigma_row.get("outcome"),
                "miss_class": sigma_row.get("miss_class"),
                "winner": winner,
                "winner_sp": float(sigma_row.get("winner_sp") or result.get("winner_sp") or 0),
                "winner_rank": int(winner_row.get("rank") or 0) + 1,
                "winner_vp": float(winner_row.get("velo_prime_prob") or 0),
                "winner_mds": float(winner_row.get("market_deception_score") or 0),
                "winner_improvement": float(winner_row.get("improvement_score") or 0),
                "winner_place_prob": float(winner_row.get("place_prob") or 0),
                "top_pick": top.get("horse"),
                "top_vp": float(top.get("velo_prime_prob") or 0),
                "top_mds": float(top.get("market_deception_score") or 0),
                "top_improvement": float(top.get("improvement_score") or 0),
                "top_midprice_action": action,
            }
        )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mid = [r for r in rows if r["miss_class"] == "mid_priced_won"]
    by_action = {}
    for action in sorted({r["top_midprice_action"] for r in rows}):
        sub = [r for r in rows if r["top_midprice_action"] == action]
        by_action[action] = {
            "n": len(sub),
            "wins": sum(r["outcome"] == "WIN" for r in sub),
            "frames": sum(r["outcome"] in ("WIN", "PLACED") for r in sub),
            "midprice_misses": sum(r["miss_class"] == "mid_priced_won" for r in sub),
        }

    by_band = {}
    for band in ("FS_2_5", "FS_6_8", "FS_9_12", "FS_13_PLUS"):
        sub = [r for r in rows if r["field_band"] == band]
        by_band[band] = {
            "n": len(sub),
            "wins": sum(r["outcome"] == "WIN" for r in sub),
            "frames": sum(r["outcome"] in ("WIN", "PLACED") for r in sub),
            "midprice_misses": sum(r["miss_class"] == "mid_priced_won" for r in sub),
        }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "date": DATE,
        "races_joined": len(rows),
        "wins": sum(r["outcome"] == "WIN" for r in rows),
        "frames": sum(r["outcome"] in ("WIN", "PLACED") for r in rows),
        "midprice_misses": len(mid),
        "midprice_rank_distribution": dict(collections.Counter(r["winner_rank"] for r in mid)),
        "midprice_visible_top3": sum(r["winner_rank"] <= 3 for r in mid),
        "midprice_visible_top5": sum(r["winner_rank"] <= 5 for r in mid),
        "midprice_visible_top8": sum(r["winner_rank"] <= 8 for r in mid),
        "by_top_midprice_action": by_action,
        "by_field_band": by_band,
        "rule_pack": {
            "live_status": "SHADOW_ONLY",
            "snapshot_contract": "STORE_NO_RPR_NDS_CHAIN_MIDPRICE_FIELDS",
            "field_band_rule": "ANNOTATE_FS_6_8_AS_WIN_LIGHT_FRAME_HEAVY",
            "small_field_rule": "ANNOTATE_FS_2_5_AS_CLEAN_SIGNAL",
            "training_decision": "DO_NOT_RETRAIN_FROM_ONE_DAY; USE_FULL_HISTORICAL_RETRAIN_ALREADY_COMPLETED",
        },
    }


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "june19_midprice_deep_dive.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# June 19 Mid-Price Deep Dive",
        f"Generated: {summary['generated_at']}",
        "",
        f"- Races joined: {summary['races_joined']}",
        f"- Wins: {summary['wins']}",
        f"- Frames: {summary['frames']}",
        f"- Mid-price misses: {summary['midprice_misses']}",
        f"- Mid-price winners visible top 3: {summary['midprice_visible_top3']}",
        f"- Mid-price winners visible top 5: {summary['midprice_visible_top5']}",
        f"- Mid-price winners visible top 8: {summary['midprice_visible_top8']}",
        "",
        "## Field Bands",
        "| Band | n | Wins | Frames | Mid-price misses |",
        "|---|---:|---:|---:|---:|",
    ]
    for band, vals in summary["by_field_band"].items():
        lines.append(f"| {band} | {vals['n']} | {vals['wins']} | {vals['frames']} | {vals['midprice_misses']} |")

    lines.extend(["", "## Top Mid-Price Actions", "| Action | n | Wins | Frames | Mid-price misses |", "|---|---:|---:|---:|---:|"])
    for action, vals in summary["by_top_midprice_action"].items():
        lines.append(f"| {action} | {vals['n']} | {vals['wins']} | {vals['frames']} | {vals['midprice_misses']} |")

    lines.extend(["", "## Rule Pack", ""])
    for key, value in summary["rule_pack"].items():
        lines.append(f"- {key}: {value}")

    (out_dir / "june19_midprice_deep_dive.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = build_rows()
    summary = summarize(rows)
    write_outputs(rows, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
