"""
safe_blend_v3_forward_audit.py

Compares the V3 SHADOW_SAFE_BLEND top selection against the current live top
selection using the forward shadow ledger.  Reads only — no production effect.

Input:  data/safe_blend_v3_shadow_ledger.csv
Output: stdout summary + data/safe_blend_v3_forward_audit_latest.json

Gate logic:
  n < 30             → OBSERVE_ONLY
  n >= 30, V3 ROI > live ROI, V3 SR >= 24%   → SHADOW_SAFE_BLEND_CONFIRMED
  n >= 60, still better                       → LIVE_WEIGHT_REVIEW_CANDIDATE
  n >= 100                                    → formal co-founder discussion only
  automatic promotion                         → NEVER

Usage:
  python scripts/safe_blend_v3_forward_audit.py [--ledger PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LEDGER = ROOT / "data" / "safe_blend_v3_shadow_ledger.csv"
OUTPUT_JSON    = ROOT / "data" / "safe_blend_v3_forward_audit_latest.json"


def _safe_float(val: str | None, default: float = 0.0) -> float:
    try:
        return float(val) if val not in (None, "", "None") else default
    except (ValueError, TypeError):
        return default


def _safe_bool(val: str | None) -> bool:
    return str(val).strip().lower() in ("true", "1", "yes")


def _gate(n: int, v3_roi: float, live_roi: float, v3_sr: float) -> str:
    if n < 30:
        return "OBSERVE_ONLY"
    if n >= 100:
        return "FORMAL_CO_FOUNDER_DISCUSSION_ONLY"
    v3_better = v3_roi > live_roi and v3_sr >= 24.0
    if n >= 60 and v3_better:
        return "LIVE_WEIGHT_REVIEW_CANDIDATE"
    if n >= 30 and v3_better:
        return "SHADOW_SAFE_BLEND_CONFIRMED"
    if n >= 30 and not v3_better:
        return "SHADOW_SAFE_BLEND_NOT_YET_CONFIRMED"
    return "OBSERVE_ONLY"


def _max_drawdown(pl_series: list[float]) -> float:
    peak = max_dd = 0.0
    for v in pl_series:
        peak = max(peak, v)
        max_dd = max(max_dd, peak - v)
    return round(max_dd, 3)


def _longest_losing_run(results: list[bool]) -> int:
    cur = max_run = 0
    for w in results:
        cur = 0 if w else cur + 1
        max_run = max(max_run, cur)
    return max_run


def run(ledger_path: Path | None = None) -> dict:
    path = ledger_path or DEFAULT_LEDGER

    if not path.exists():
        print(f"Ledger not found: {path}", file=sys.stderr)
        print("Run run_prime_today.py first to populate the ledger.")
        return {}

    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    total_rows = len(rows)

    # Only rows with result data (won/sp fields populated)
    closed = [r for r in rows
              if r.get("won_live_top", "") not in ("", "None")
              and r.get("sp_live_top", "") not in ("", "None")]
    n = len(closed)

    # --- Metrics helper -------------------------------------------------
    def _metrics(won_key: str, sp_key: str, placed_key: str) -> dict:
        wins = placed = 0
        pl = 0.0
        sps: list[float] = []
        pl_series: list[float] = []
        won_flags: list[bool] = []

        for r in closed:
            won    = _safe_bool(r.get(won_key))
            placed_flag = _safe_bool(r.get(placed_key))
            sp     = _safe_float(r.get(sp_key))
            pl_this = (sp - 1.0) if won else -1.0
            pl += pl_this
            pl_series.append(pl)
            if sp > 0:
                sps.append(sp)
            if won:
                wins += 1
            if placed_flag or won:
                placed += 1
            won_flags.append(won)

        nn = len(closed)
        sps_s = sorted(sps)
        return {
            "n":            nn,
            "wins":         wins,
            "sr":           round(wins / nn * 100, 2) if nn else 0.0,
            "fr":           round(placed / nn * 100, 2) if nn else 0.0,
            "pl":           round(pl, 3),
            "roi":          round(pl / nn * 100, 2) if nn else 0.0,
            "avg_sp":       round(sum(sps) / len(sps), 2) if sps else 0.0,
            "med_sp":       round(sps_s[len(sps_s) // 2], 2) if sps_s else 0.0,
            "max_drawdown": _max_drawdown(pl_series),
            "longest_losing_run": _longest_losing_run(won_flags),
        }

    live_m = _metrics("won_live_top",  "sp_live_top",  "placed_live_top")
    v3_m   = _metrics("won_safe_v3",   "sp_safe_v3",   "placed_safe_v3")

    changed_rows = [r for r in rows if _safe_bool(r.get("changed_top_selection"))]
    changed_closed = [r for r in closed if _safe_bool(r.get("changed_top_selection"))]

    gate_verdict = _gate(n, v3_m["roi"], live_m["roi"], v3_m["sr"])

    result = {
        "ledger_path":      str(path),
        "total_ledger_rows": total_rows,
        "closed_rows":      n,
        "changed_top_selections_total": len(changed_rows),
        "changed_top_selections_closed": len(changed_closed),
        "live": live_m,
        "v3":   v3_m,
        "v3_beats_live_roi":  v3_m["roi"] > live_m["roi"],
        "v3_beats_live_sr":   v3_m["sr"]  > live_m["sr"],
        "v3_beats_live_fr":   v3_m["fr"]  > live_m["fr"],
        "roi_delta":   round(v3_m["roi"] - live_m["roi"], 2),
        "sr_delta":    round(v3_m["sr"]  - live_m["sr"],  2),
        "fr_delta":    round(v3_m["fr"]  - live_m["fr"],  2),
        "gate":        gate_verdict,
        "freeze":      gate_verdict in ("OBSERVE_ONLY", "SHADOW_SAFE_BLEND_NOT_YET_CONFIRMED"),
        "governance":  {
            "production_unchanged":    True,
            "live_weights_unchanged":  True,
            "no_staking":              True,
            "no_telegram_betting":     True,
            "no_router_effect":        True,
            "automatic_promotion":     "NEVER",
        },
    }

    OUTPUT_JSON.write_text(json.dumps(result, indent=2))

    # ── Print summary ──────────────────────────────────────────────────────────
    print("╔══ V3 SHADOW SAFE BLEND — FORWARD AUDIT ═══════════════════════╗")
    print(f"  Ledger rows total:   {total_rows}")
    print(f"  Closed (with result): {n}")
    print(f"  Changed top picks:   {len(changed_rows)} total  {len(changed_closed)} closed")
    print()
    print(f"  {'Metric':<25} {'LIVE':>12} {'V3':>12} {'Delta':>10}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
    for metric in ["n","sr","fr","pl","roi","avg_sp","med_sp","max_drawdown","longest_losing_run"]:
        lv = live_m.get(metric, "—")
        v3 = v3_m.get(metric, "—")
        delta = ""
        if isinstance(lv, (int, float)) and isinstance(v3, (int, float)) and metric != "n":
            delta = f"{v3 - lv:+.2f}"
        print(f"  {metric:<25} {str(lv):>12} {str(v3):>12} {delta:>10}")
    print()
    print(f"  V3 beats LIVE ROI:  {result['v3_beats_live_roi']}")
    print(f"  V3 beats LIVE SR:   {result['v3_beats_live_sr']}")
    print()
    print(f"  GATE VERDICT: {gate_verdict}")
    print(f"  FREEZE:       {result['freeze']}")
    print(f"  Production weights: UNCHANGED — SHADOW_ONLY")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"\nOutput: {OUTPUT_JSON}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=None,
                        help="Path to shadow ledger CSV (default: data/safe_blend_v3_shadow_ledger.csv)")
    args = parser.parse_args()
    run(ledger_path=args.ledger)
