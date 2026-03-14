#!/usr/bin/env python3
"""
VELO ORACLE - Value Betting System
Uses TS/RPR/OR ratings to identify value bets vs market odds
"""

import json
from pathlib import Path
from datetime import datetime
import numpy as np


# -----------------------------
# Utility Functions
# -----------------------------

def odds_to_probability(odds_str):
    """Convert fractional odds (e.g. '5/2') to (probability, decimal_odds)."""
    try:
        if isinstance(odds_str, str) and "/" in odds_str:
            num, den = odds_str.split("/")
            decimal = (float(num) / float(den)) + 1.0
            prob = 1.0 / decimal
            return prob, decimal

        # If already decimal
        if isinstance(odds_str, str):
            dec = float(odds_str)
            if dec > 1:
                return 1.0 / dec, dec
    except Exception:
        pass

    return 0.5, 2.0


def safe_float(value):
    try:
        if value is None:
            return 0.0
        s = str(value).strip()
        if s in ("", "-", "None"):
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def rating_to_probability(rating, max_rating):
    if rating <= 0 or max_rating <= 0:
        return 0.0

    norm = rating / max_rating
    return norm * 0.4


# -----------------------------
# Core Engine
# -----------------------------

def analyze_race(race):
    print("\n" + "=" * 70)
    print(f"RACE: {race.get('course', '?')} {race.get('time', '?')}")
    print("=" * 70)

    runners = race.get("runners", [])
    if not runners:
        print("⚠️ No runners found. Skipping.")
        return []

    # Parse ratings + market
    for r in runners:
        r["ts_num"] = safe_float(r.get("ts"))
        r["rpr_num"] = safe_float(r.get("rpr"))
        r["or_num"] = safe_float(r.get("or"))
        r["market_prob"], r["decimal_odds"] = odds_to_probability(r.get("odds", ""))

    max_ts = max((r["ts_num"] for r in runners if r["ts_num"] > 0), default=100)
    max_rpr = max((r["rpr_num"] for r in runners if r["rpr_num"] > 0), default=100)
    max_or = max((r["or_num"] for r in runners if r["or_num"] > 0), default=100)

    value_bets = []

    for r in runners:
        ts_prob = rating_to_probability(r["ts_num"], max_ts)
        rpr_prob = rating_to_probability(r["rpr_num"], max_rpr)
        or_prob = rating_to_probability(r["or_num"], max_or)

        probs = [p for p in (ts_prob, rpr_prob, or_prob) if p > 0]
        model_prob = np.mean(probs) if probs else 0.10

        edge = model_prob - r["market_prob"]
        edge_pct = edge * 100

        if edge > 0 and (r["decimal_odds"] - 1) > 0:
            kelly = edge / (r["decimal_odds"] - 1)
            kelly_pct = max(0.0, min(kelly * 100.0, 10.0))
        else:
            kelly_pct = 0.0

        ev = (model_prob * (r["decimal_odds"] - 1)) - (1 - model_prob)
        ev_pct = ev * 100

        r["model_prob"] = model_prob
        r["edge_pct"] = edge_pct
        r["ev_pct"] = ev_pct
        r["kelly_pct"] = kelly_pct

        if edge_pct > 3.0 or ev_pct > 10.0:
            value_bets.append(r)

    runners_sorted = sorted(runners, key=lambda x: x.get("edge_pct", 0), reverse=True)

    print(f"\n{'#':<3} {'Horse':<25} {'Odds':<8} {'Mkt%':<7} {'Mod%':<7} {'Edge%':<7} {'EV%':<7}")
    print("-" * 80)

    for i, r in enumerate(runners_sorted, 1):
        marker = "🎯" if r in value_bets else "  "
        print(
            f"{marker}{i:<2} {str(r.get('horse',''))[:25]:<25} "
            f"{str(r.get('odds','')):<8} "
            f"{r['market_prob']*100:<7.1f} "
            f"{r['model_prob']*100:<7.1f} "
            f"{r['edge_pct']:<7.1f} "
            f"{r['ev_pct']:<7.1f}"
        )

    return value_bets


# -----------------------------
# JSON Loader
# -----------------------------

def extract_races(payload):
    if isinstance(payload, dict):
        if "races" in payload and isinstance(payload["races"], list):
            return payload["races"]
        raise ValueError("JSON dict missing 'races' list.")

    if isinstance(payload, list):
        if payload and "runners" in payload[0]:
            return payload
        raise ValueError("JSON is list but does not contain structured race objects.")

    raise ValueError("Unsupported JSON structure.")


# -----------------------------
# Main
# -----------------------------

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    race_file = Path(f"data/velo_races_{today}.json")
    output_file = Path(f"data/value_bets_{today}.json")

    print("\n" + "#" * 70)
    print("VELO ORACLE - Value Betting System")
    print("#" * 70)

    payload = json.loads(race_file.read_text(encoding="utf-8"))
    races = extract_races(payload)

    all_value_bets = []

    for race in races:
        bets = analyze_race(race)
        if bets:
            all_value_bets.append({
                "race": f"{race.get('course','?')} {race.get('time','?')}",
                "url": race.get("url", ""),
                "bets": bets
            })

    result = {
        "date": today,
        "generated_at": datetime.now().isoformat(),
        "races_analyzed": len(races),
        "races_with_value_bets": len(all_value_bets),
        "value_bets": all_value_bets
    }

    output_file.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print("\nResults saved to:", output_file)
    print("#" * 70)


if _name_ == "_main_":
    main()
