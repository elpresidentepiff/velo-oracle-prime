#!/usr/bin/env python3
"""
VP40_TIER_A_TRIGGER_WATCH_V1

Daily monitor for VP40_TIER_A sub-lane trigger thresholds.
Reads current training corpus and reports n vs trigger for each tracked sub-lane.
Writes a delta artifact showing change since previous run.

No modelling. No mutation. Trigger discipline only.

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Tracked lanes:
  VP40_TIER_A_SP_2X       trigger: n>=50  (forensic review)
  VP40_TIER_A_SHORTPRICE  trigger: n>=150 (full promotion gate rerun)

Inputs:
    data/training/sigma_2k_training_dataset_latest.parquet
    data/reports/vp40_tier_a_trigger_watch_latest.json  (previous run for delta)

Outputs:
    data/reports/vp40_tier_a_trigger_watch_latest.json
    data/reports/vp40_tier_a_trigger_watch_latest.md

Usage:
    python scripts/vp40_tier_a_trigger_watch.py [--date YYYY-MM-DD]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
TRAINING_PATH = DATA / "training" / "sigma_2k_training_dataset_latest.parquet"
PREVIOUS_PATH = REPORTS_DIR / "vp40_tier_a_trigger_watch_latest.json"
REPORTS_DIR.mkdir(exist_ok=True)

LANES = [
    {
        "name": "VP40_TIER_A_SP_2X",
        "label": "embryo lane — healthiest sub-band",
        "definition": "VP>=0.40 AND Tier A AND 2.0<=SP<3.0",
        "trigger_n": 50,
        "trigger_action": "run vp40_tier_a_sp_2x_review.py — forensic review per PROTOCOL_V1",
        "filter": lambda df: (
            (df["velo_prime_prob"] >= 0.40) &
            (df["decision_tier"] == "A") &
            (df["sp_decimal"] >= 2.0) &
            (df["sp_decimal"] < 3.0)
        ),
    },
    {
        "name": "VP40_TIER_A_SHORTPRICE",
        "label": "outlier-clean lane — UNDER_REVIEW",
        "definition": "VP>=0.40 AND Tier A AND SP<3.0",
        "trigger_n": 150,
        "trigger_action": "rerun vp40_tier_a_shortprice_review.py — full promotion gate assessment",
        "filter": lambda df: (
            (df["velo_prime_prob"] >= 0.40) &
            (df["decision_tier"] == "A") &
            (df["sp_decimal"] < 3.0)
        ),
    },
]


def _load_data() -> pd.DataFrame:
    df = pd.read_parquet(TRAINING_PATH)
    return df[df["result_matched"] == True].copy()


def _lane_stats(df: pd.DataFrame, lane_filter) -> dict:
    lane = df[lane_filter(df)]
    n = len(lane)
    if n == 0:
        return {"n": 0, "wins": 0, "sr": 0.0, "frame_rate": 0.0, "roi": 0.0,
                "avg_sp": None, "top_winner": None, "top_winner_sp": None,
                "top1_pct": None}
    wins = int(lane["won"].sum())
    frames = int(lane["placed"].sum()) if "placed" in lane.columns else 0
    sr = round(wins / n * 100, 1)
    frame_rate = round(frames / n * 100, 1) if frames > 0 else 0.0
    roi = round(((lane["sp_decimal"] * lane["won"]) - 1).mean() * 100, 1)
    avg_sp = round(float(lane["sp_decimal"].mean()), 2)

    winners = lane[lane["won"] == True].sort_values("sp_decimal", ascending=False)
    total_return = float((lane["sp_decimal"] * lane["won"]).sum())
    top_winner = None
    top_winner_sp = None
    top1_pct = None
    if len(winners) > 0:
        tw = winners.iloc[0]
        top_winner = str(tw.get("horse", "?"))
        top_winner_sp = round(float(tw["sp_decimal"]), 1)
        top1_pct = round(float(tw["sp_decimal"]) / total_return * 100, 1) if total_return > 0 else 0.0

    return {
        "n": n, "wins": wins, "frames": frames,
        "sr": sr, "frame_rate": frame_rate, "roi": roi,
        "avg_sp": avg_sp,
        "top_winner": top_winner, "top_winner_sp": top_winner_sp, "top1_pct": top1_pct,
    }


def _load_previous() -> dict:
    if not PREVIOUS_PATH.exists():
        return {}
    try:
        return json.loads(PREVIOUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _delta(prev_lanes: list, lane_name: str, key: str, current_val) -> str:
    if not prev_lanes:
        return "—"
    prev = next((l for l in prev_lanes if l.get("name") == lane_name), {})
    prev_val = prev.get("stats", {}).get(key)
    if prev_val is None or current_val is None:
        return "—"
    d = current_val - prev_val
    if d == 0:
        return "±0"
    return f"+{d}" if d > 0 else str(d)


def _build_md(lanes_out: list, date: str, run_ts: str, prev_date: str | None) -> str:
    lines = [
        "# VP40_TIER_A TRIGGER WATCH",
        f"**Date:** {date}",
        f"**Run:** {run_ts}",
        f"**Previous run:** {prev_date or 'none'}",
        "",
        "Monitoring sub-lane n vs trigger thresholds. No modelling. No mutation.",
        "",
        "---",
        "",
    ]

    trigger_fired = []
    for lane in lanes_out:
        s = lane["stats"]
        trigger_n = lane["trigger_n"]
        status = lane["status"]
        delta_n = lane["delta_n"]
        delta_n_str = f"({delta_n:+d} since last run)" if delta_n != 0 else "(no change)"

        lines += [
            f"## {lane['name']}",
            f"*{lane['label']}*",
            f"`{lane['definition']}`",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| n | **{s['n']}** / {trigger_n} — {lane['pct_to_trigger']:.0f}% to trigger |",
            f"| n delta | {delta_n_str} |",
            f"| SR | {s['sr']}% |",
            f"| Frame | {s['frame_rate']}% |",
            f"| ROI | {s['roi']:+.1f}% |",
            f"| Avg SP | {s['avg_sp']} |",
            f"| Top winner | {s['top_winner']} SP={s['top_winner_sp']} ({s['top1_pct']}% of return) |",
            f"| Status | **{status}** |",
            "",
        ]

        if status == "TRIGGER_FIRED":
            trigger_fired.append(lane)
            lines += [
                f"**⚠️ TRIGGER FIRED — n={s['n']} >= {trigger_n}**",
                f"Action required: {lane['trigger_action']}",
                "",
            ]
        elif status == "APPROACHING":
            remaining = trigger_n - s['n']
            lines += [
                f"Approaching trigger — {remaining} more selections needed.",
                "",
            ]
        else:
            remaining = trigger_n - s['n']
            lines += [
                f"Waiting — {remaining} more selections needed.",
                "",
            ]

        lines.append("---")
        lines.append("")

    if trigger_fired:
        lines += [
            "## ACTION REQUIRED",
            "",
        ]
        for lane in trigger_fired:
            lines += [
                f"- **{lane['name']}**: {lane['trigger_action']}",
            ]
        lines.append("")
    else:
        lines += [
            "## Status: WAIT",
            "",
            "No trigger has fired. Continue daily accumulation.",
            "",
        ]

    lines += [
        "## Lane Policy Summary",
        "",
        "| Lane | Status | Note |",
        "|---|---|---|",
        "| VP40_LANE | WATCH_ONLY | Gate 4+7 FAIL — Roysse SP=34 |",
        "| VP40_TIER_A | WATCH_ONLY | Gate 4+7 FAIL — Roysse is Tier A |",
        "| VP40_TIER_A_SHORTPRICE | UNDER_REVIEW | n=85/150 — outlier resolved |",
        f"| VP40_TIER_A_SP_2X | WATCHING | embryo lane — n={lanes_out[0]['stats']['n']}/50 |",
        "",
        "```",
        "NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE",
        "NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION",
        "NO_LIVE_STATE_MUTATION | TRIGGER_DISCIPLINE_ONLY",
        "```",
        "",
        "*VP40_TIER_A_TRIGGER_WATCH_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"VP40_TIER_A TRIGGER WATCH V1 — {date}")
    print("=" * 60)
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    df = _load_data()
    prev = _load_previous()
    prev_lanes = prev.get("lanes", [])
    prev_date = prev.get("date")

    lanes_out = []
    any_trigger = False

    for lane_def in LANES:
        name = lane_def["name"]
        trigger_n = lane_def["trigger_n"]
        stats = _lane_stats(df, lane_def["filter"])
        n = stats["n"]
        delta_n_val = n - (next((l for l in prev_lanes if l.get("name") == name), {}).get("stats", {}).get("n") or n)

        if n >= trigger_n:
            status = "TRIGGER_FIRED"
            any_trigger = True
        elif n >= int(trigger_n * 0.8):
            status = "APPROACHING"
        else:
            status = "WAIT"

        pct_to_trigger = round(n / trigger_n * 100, 1)

        print(f"  {name:<42} n={n:>3}/{trigger_n}  "
              f"SR={stats['sr']:>5}%  ROI={stats['roi']:>+6.1f}%  "
              f"[{status}]")

        if status == "TRIGGER_FIRED":
            print(f"    *** ACTION: {lane_def['trigger_action']}")

        lanes_out.append({
            "name": name,
            "label": lane_def["label"],
            "definition": lane_def["definition"],
            "trigger_n": trigger_n,
            "trigger_action": lane_def["trigger_action"],
            "status": status,
            "pct_to_trigger": pct_to_trigger,
            "delta_n": delta_n_val,
            "stats": stats,
        })

    if not any_trigger:
        print("\n  Status: WAIT — no trigger fired. Continue accumulation.")
    else:
        print("\n  *** TRIGGER FIRED — run review script immediately")

    output = {
        "run_ts": run_ts,
        "date": date,
        "prev_date": prev_date,
        "any_trigger_fired": any_trigger,
        "lanes": lanes_out,
        "governance": {
            "scoring_change": False, "model_change": False, "router_change": False,
            "staking_change": False, "telegram": False,
            "classification": "TRIGGER_DISCIPLINE_ONLY",
        },
    }

    json_path = REPORTS_DIR / "vp40_tier_a_trigger_watch_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(lanes_out, date, run_ts, prev_date)
    md_path = REPORTS_DIR / "vp40_tier_a_trigger_watch_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return output


if __name__ == "__main__":
    main()
