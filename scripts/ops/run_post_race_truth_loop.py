#!/usr/bin/env python3
"""
run_post_race_truth_loop.py — Layer 4 of the VÉLØ organism.

Runs post-race (after sigma reconciliation) to record how the organism
performed against reality: core miss type, state tag truth, gate truth,
archetype truth per race.

Outputs per date:
  data/truth_loop/truth_loop_{date_tag}.jsonl       — one JSON record per race
  data/truth_loop/truth_loop_{date_tag}_summary.json — daily aggregates

Usage:
    python scripts/ops/run_post_race_truth_loop.py --date 2026-07-27
    python scripts/ops/run_post_race_truth_loop.py --date 2026-07-27 --rollup
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRUTH_DIR = ROOT / "data" / "truth_loop"

# ------------------------------------------------------------------
# Verdict loading  (Schema A: flat per-runner list; Schema B: per-race
# dict with top{} object, current from 2026-07-27+)
# ------------------------------------------------------------------

def _load_verdicts(date_tag: str) -> dict[str, dict]:
    """Return {race_id: merged_top_dict} from the verdict file."""
    path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
    if not path.exists():
        return {}
    try:
        verdicts = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    out: dict[str, dict] = {}
    for race in verdicts:
        if not isinstance(race, dict):
            continue
        top = race.get("top")
        # Schema B — per-race dict with top{}
        if isinstance(top, dict) and top:
            rid = str(race.get("race_id") or top.get("race_id") or "")
            if rid:
                out[rid] = {
                    **top,
                    "_race_tier": race.get("tier"),
                    "_race_course": race.get("course"),
                    "_race_off_time": race.get("off_time"),
                }
        # Schema A — flat per-runner; pick row matching top_rank_horse_id
        elif "full_analysis" in race:
            rid = str(race.get("race_id") or "")
            top_rank_id = str(race.get("top_rank_horse_id") or "")
            preds = (race.get("full_analysis") or {}).get("predictions") or []
            for p in preds:
                if str(p.get("horse_id") or "") == top_rank_id:
                    out[rid] = {
                        **p,
                        "_race_tier": race.get("tier"),
                        "_race_course": race.get("course"),
                        "_race_off_time": race.get("off_time"),
                    }
                    break
    return out


def _load_sigma_rows(date_tag: str) -> dict[str, dict]:
    """Return {race_id: sigma_row} from the sigma results file."""
    path = ROOT / "data" / "sigma_results" / f"sigma_results_{date_tag}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        str(r["race_id"]): r
        for r in data.get("rows", [])
        if r.get("race_id")
    }


# ------------------------------------------------------------------
# State-tag polarity maps
# ------------------------------------------------------------------

_BULLISH_READINESS = {"peak", "ready"}
_BEARISH_READINESS = {"stale", "unfit", "tired"}
_BULLISH_RELEASE   = {"live", "primed"}
_BEARISH_RELEASE   = {"hidden", "concealed"}
_BULLISH_MARKET    = {"quietly_backed", "shortening", "firming"}
_BEARISH_MARKET    = {"drifting"}  # "ignored" = market indifferent, not a directional signal
_BULLISH_FIT       = {"strong", "improving"}
_BEARISH_FIT       = {"weak", "declining"}


# ------------------------------------------------------------------
# Classification helpers
# ------------------------------------------------------------------

def _classify_core_miss(top: dict, outcome: str) -> str | None:
    """Return miss type label, or None on WIN."""
    if outcome == "WIN":
        return None
    if outcome == "PLACED":
        if top.get("archetype_suppression"):
            return "wrong_suppression"
        return "right_horse_wrong_tier"
    # MISS
    if top.get("archetype_trap_flag"):
        return "wrong_trap_read"
    hs = top.get("horse_state") or {}
    if hs.get("release_state") in _BEARISH_RELEASE:
        return "wrong_release_read"
    if hs.get("chaos_exposure") in ("high", "extreme"):
        return "wrong_chaos_read"
    return "wrong_top_horse"


def _state_tag_truths(top: dict, top_horse_placed: bool) -> dict[str, bool | None]:
    """
    Return truth booleans for each state tag.
    None = tag was neutral (no signal), can't score.
    """
    hs = top.get("horse_state") or {}

    def bullish_correct(bullish_vals: set, bearish_vals: set, field: str) -> bool | None:
        val = hs.get(field)
        if val in bullish_vals:
            return top_horse_placed
        if val in bearish_vals:
            return not top_horse_placed
        return None

    chaos = hs.get("chaos_exposure")
    if chaos in ("high", "extreme"):
        state_truth_chaos: bool | None = not top_horse_placed
    elif chaos == "low":
        state_truth_chaos = top_horse_placed
    else:
        state_truth_chaos = None

    return {
        "state_truth_readiness": bullish_correct(_BULLISH_READINESS, _BEARISH_READINESS, "readiness_state"),
        "state_truth_release":   bullish_correct(_BULLISH_RELEASE,   _BEARISH_RELEASE,   "release_state"),
        "state_truth_market":    bullish_correct(_BULLISH_MARKET,    _BEARISH_MARKET,    "market_state"),
        "state_truth_race_fit":  bullish_correct(_BULLISH_FIT,       _BEARISH_FIT,       "race_fit_state"),
        "state_truth_chaos":     state_truth_chaos,
    }


def _classify_archetype(top: dict, outcome: str, miss_class: str | None) -> bool:
    """Was the archetype classification broadly correct?"""
    trap = top.get("archetype_trap_flag", False)
    archetype = (top.get("race_archetype") or "").lower()

    if outcome == "WIN":
        return True
    if outcome == "PLACED":
        return not trap
    # MISS
    if trap:
        return True  # flagged trap, horse missed — trap read was accurate
    if archetype == "chaos" and miss_class == "outsider_won":
        return True  # chaos archetype predicts unpredictable outsider
    return False


def _classify_gate(top: dict, top_horse_placed: bool) -> str:
    if not top.get("tie_gate_fires"):
        return "not_triggered"
    return "helped" if top_horse_placed else "overfired"


def _classify_ew(top: dict, ew_outcome: str | None) -> str:
    if not top.get("tie_gate_ew_flag"):
        return "not_triggered"
    return "helped" if ew_outcome in ("EW_WIN", "EW_PLACE") else "missed"


# ------------------------------------------------------------------
# Core truth record builder
# ------------------------------------------------------------------

def build_truth_record(race_id: str, top: dict, sigma_row: dict, race_date: str) -> dict:
    outcome      = sigma_row.get("outcome", "MISS")
    miss_class   = sigma_row.get("miss_class") if outcome == "MISS" else None
    ew_outcome   = sigma_row.get("ew_outcome")

    top_horse_won    = outcome == "WIN"
    top_horse_placed = outcome in ("WIN", "PLACED")

    hs = top.get("horse_state") or {}

    notes: list[str] = []
    if not top_horse_placed and top.get("tie_gate_fires"):
        notes.append(f"gate_overfired:upgrade={top.get('tie_gate_tier_upgrade')}")
    if top.get("archetype_trap_flag") and top_horse_placed:
        notes.append("trap_flagged_but_horse_placed")
    if outcome == "WIN" and (top.get("velo_prime_prob") or 0.0) < 0.35:
        notes.append("low_confidence_winner:VP<0.35")

    return {
        "race_id":              race_id,
        "race_date":            race_date,
        "course":               top.get("_race_course") or sigma_row.get("course"),
        "off":                  top.get("_race_off_time") or sigma_row.get("off"),
        "tier":                 top.get("_race_tier"),
        "predicted_horse":      top.get("horse") or sigma_row.get("predicted"),
        "actual_winner":        sigma_row.get("actual_name"),
        "winner_sp":            sigma_row.get("winner_sp"),
        "sp_dec":               top.get("sp_dec"),
        "velo_prime_prob":      top.get("velo_prime_prob"),
        "outcome":              outcome,
        "miss_class":           miss_class,
        "ew_outcome":           ew_outcome,
        "top_horse_won":        top_horse_won,
        "top_horse_placed":     top_horse_placed,
        "core_miss_type":       _classify_core_miss(top, outcome),
        "gate_upgrade_result":  _classify_gate(top, top_horse_placed),
        "ew_flag_result":       _classify_ew(top, ew_outcome),
        "archetype_correct":    _classify_archetype(top, outcome, miss_class),
        "assigned_archetype":   top.get("race_archetype"),
        "archetype_label":      top.get("archetype_label"),
        "archetype_confidence": top.get("archetype_confidence"),
        "archetype_trap_flag":  top.get("archetype_trap_flag"),
        "archetype_suppression":top.get("archetype_suppression"),
        "tie_gate_fires":       top.get("tie_gate_fires"),
        "tie_gate_tier_upgrade":top.get("tie_gate_tier_upgrade"),
        "tie_gate_signal_count":top.get("tie_gate_signal_count"),
        "readiness_state":      hs.get("readiness_state"),
        "release_state":        hs.get("release_state"),
        "market_state":         hs.get("market_state"),
        "race_fit_state":       hs.get("race_fit_state"),
        "chaos_exposure":       hs.get("chaos_exposure"),
        **_state_tag_truths(top, top_horse_placed),
        "learning_notes":       notes,
    }


# ------------------------------------------------------------------
# Daily summary
# ------------------------------------------------------------------

def build_summary(records: list[dict], race_date: str) -> dict:
    n = len(records)
    if n == 0:
        return {"race_date": race_date, "races_evaluated": 0}

    wins   = sum(1 for r in records if r["top_horse_won"])
    placed = sum(1 for r in records if r["top_horse_placed"])

    miss_types = Counter(r["core_miss_type"] for r in records if r["core_miss_type"])

    archetype_stats: dict[str, dict] = {}
    for r in records:
        a = r.get("assigned_archetype") or "UNKNOWN"
        if a not in archetype_stats:
            archetype_stats[a] = {"n": 0, "wins": 0, "placed": 0, "archetype_correct": 0}
        archetype_stats[a]["n"] += 1
        archetype_stats[a]["wins"]             += int(r["top_horse_won"])
        archetype_stats[a]["placed"]           += int(r["top_horse_placed"])
        archetype_stats[a]["archetype_correct"] += int(r.get("archetype_correct") or False)

    gate_results = Counter(r["gate_upgrade_result"] for r in records)
    ew_results   = Counter(r["ew_flag_result"] for r in records)

    _STATE_TAGS = [
        "state_truth_readiness", "state_truth_release",
        "state_truth_market", "state_truth_race_fit", "state_truth_chaos",
    ]
    state_truth_rates: dict[str, dict] = {}
    for tag in _STATE_TAGS:
        vals = [r[tag] for r in records if r.get(tag) is not None]
        if vals:
            state_truth_rates[tag] = {
                "n": len(vals),
                "correct": sum(1 for v in vals if v),
                "rate": round(sum(1 for v in vals if v) / len(vals), 4),
            }
        else:
            state_truth_rates[tag] = {"n": 0, "correct": 0, "rate": None}

    return {
        "race_date":       race_date,
        "races_evaluated": n,
        "sr":              round(wins / n, 4),
        "place_rate":      round(placed / n, 4),
        "wins":            wins,
        "placed":          placed,
        "miss_type_breakdown":  dict(miss_types.most_common()),
        "archetype_stats":      archetype_stats,
        "gate_results":         dict(gate_results),
        "ew_results":           dict(ew_results),
        "state_truth_rates":    state_truth_rates,
    }


# ------------------------------------------------------------------
# Weekly rollup
# ------------------------------------------------------------------

def build_weekly_rollup(as_of: date) -> dict:
    """Read last 7 days of truth JSONL and aggregate."""
    all_records: list[dict] = []
    dates_loaded: list[str] = []

    for i in range(7):
        d = as_of - timedelta(days=i)
        tag  = d.strftime("%Y_%m_%d")
        path = TRUTH_DIR / f"truth_loop_{tag}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    all_records.append(json.loads(line))
                except Exception:
                    pass
        dates_loaded.append(str(d))

    n = len(all_records)
    if n == 0:
        return {"period_end": str(as_of), "dates_loaded": dates_loaded, "races_evaluated": 0}

    wins   = sum(1 for r in all_records if r["top_horse_won"])
    placed = sum(1 for r in all_records if r["top_horse_placed"])

    miss_types = Counter(r["core_miss_type"] for r in all_records if r["core_miss_type"])

    archetype_sr: dict[str, dict] = defaultdict(lambda: {"n": 0, "wins": 0, "placed": 0})
    for r in all_records:
        a = r.get("assigned_archetype") or "UNKNOWN"
        archetype_sr[a]["n"]      += 1
        archetype_sr[a]["wins"]   += int(r["top_horse_won"])
        archetype_sr[a]["placed"] += int(r["top_horse_placed"])

    archetype_ranked = sorted(
        {k: {**v, "sr": round(v["wins"] / v["n"], 4) if v["n"] else 0.0}
         for k, v in archetype_sr.items()}.items(),
        key=lambda x: -x[1]["sr"],
    )

    _STATE_TAGS = [
        "state_truth_readiness", "state_truth_release",
        "state_truth_market", "state_truth_race_fit", "state_truth_chaos",
    ]
    state_reliability: dict[str, dict] = {}
    for tag in _STATE_TAGS:
        vals = [r[tag] for r in all_records if r.get(tag) is not None]
        state_reliability[tag] = {
            "n": len(vals),
            "rate": round(sum(1 for v in vals if v) / len(vals), 4) if vals else None,
        }

    gate_fired  = sum(1 for r in all_records if r["gate_upgrade_result"] != "not_triggered")
    gate_helped = sum(1 for r in all_records if r["gate_upgrade_result"] == "helped")
    ew_fired    = sum(1 for r in all_records if r["ew_flag_result"] != "not_triggered")
    ew_helped   = sum(1 for r in all_records if r["ew_flag_result"] == "helped")

    reliable_tag   = max(state_reliability.items(), key=lambda x: x[1]["rate"] or 0.0)[0]
    unreliable_tag = min(state_reliability.items(), key=lambda x: x[1]["rate"] if x[1]["rate"] is not None else 1.0)[0]

    return {
        "period_end":             str(as_of),
        "dates_loaded":           dates_loaded,
        "races_evaluated":        n,
        "overall_sr":             round(wins / n, 4),
        "overall_place_rate":     round(placed / n, 4),
        "most_common_miss_type":  miss_types.most_common(1)[0] if miss_types else None,
        "miss_type_breakdown":    dict(miss_types.most_common()),
        "best_archetype":         archetype_ranked[0] if archetype_ranked else None,
        "worst_archetype":        archetype_ranked[-1] if archetype_ranked else None,
        "archetype_breakdown":    dict(archetype_ranked),
        "state_reliability":      state_reliability,
        "most_reliable_state_tag":   reliable_tag,
        "least_reliable_state_tag":  unreliable_tag,
        "gate_precision": {
            "fired":     gate_fired,
            "helped":    gate_helped,
            "precision": round(gate_helped / gate_fired, 4) if gate_fired else None,
        },
        "ew_precision": {
            "fired":     ew_fired,
            "helped":    ew_helped,
            "precision": round(ew_helped / ew_fired, 4) if ew_fired else None,
        },
    }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Post-race truth loop — Layer 4")
    parser.add_argument("--date",   required=True, help="Race date YYYY-MM-DD")
    parser.add_argument("--rollup", action="store_true",
                        help="Also generate 7-day weekly rollup")
    args = parser.parse_args()

    race_date = args.date
    date_tag  = race_date.replace("-", "_")

    TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    verdicts   = _load_verdicts(date_tag)
    sigma_rows = _load_sigma_rows(date_tag)

    if not verdicts:
        print(f"ERROR: no verdict file for {date_tag}", file=sys.stderr)
        return 1
    if not sigma_rows:
        print(f"ERROR: no sigma rows for {date_tag}", file=sys.stderr)
        return 1

    records: list[dict] = []
    unmatched_verdict = 0

    for race_id, top in verdicts.items():
        if race_id not in sigma_rows:
            unmatched_verdict += 1
            continue
        records.append(build_truth_record(race_id, top, sigma_rows[race_id], race_date))

    unmatched_sigma = len(sigma_rows) - len(records)

    jsonl_path = TRUTH_DIR / f"truth_loop_{date_tag}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")

    summary = build_summary(records, race_date)
    summary["unmatched_verdict_races"] = unmatched_verdict
    summary["unmatched_sigma_races"]   = unmatched_sigma

    summary_path = TRUTH_DIR / f"truth_loop_{date_tag}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    n          = len(records)
    wins       = summary.get("wins", 0)
    placed     = summary.get("placed", 0)
    arch_right = sum(1 for r in records if r.get("archetype_correct"))

    print(f"Truth loop complete: {n} races evaluated ({race_date})")
    print(f"  SR: {summary.get('sr', 0):.3f}  Place rate: {summary.get('place_rate', 0):.3f}  ({wins}W / {placed}P)")
    print(f"  Archetype correct: {arch_right}/{n}")
    print(f"  Miss types: {summary.get('miss_type_breakdown', {})}")
    print(f"  Gate: {summary.get('gate_results', {})}")
    print(f"  JSONL:   {jsonl_path}")
    print(f"  Summary: {summary_path}")
    if unmatched_verdict:
        print(f"  WARN: {unmatched_verdict} verdict races had no sigma row")

    if args.rollup:
        as_of   = date.fromisoformat(race_date)
        rollup  = build_weekly_rollup(as_of)
        rp_path = TRUTH_DIR / f"truth_loop_weekly_rollup_{date_tag}.json"
        rp_path.write_text(json.dumps(rollup, indent=2), encoding="utf-8")
        print(f"\nWeekly rollup ({rollup['races_evaluated']} races, {len(rollup['dates_loaded'])} dates):")
        print(f"  Most common miss: {rollup.get('most_common_miss_type')}")
        print(f"  Best archetype:   {rollup.get('best_archetype')}")
        print(f"  Most reliable tag: {rollup.get('most_reliable_state_tag')}")
        print(f"  Rollup: {rp_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
