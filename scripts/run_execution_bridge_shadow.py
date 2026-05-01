"""
Run VeloExecutionBridge in shadow/paper mode for a given race date.

Loads VÉLØ verdicts from Supabase, optionally enriches with the Racing API
shadow ledger, generates ExecutionDirectives, writes the paper ledger, and
prints a summary.

GOVERNANCE:
  - Does NOT touch Betfair
  - Does NOT stake
  - Does NOT send Telegram
  - Does NOT call BetfairClient.place_order
  - Does NOT alter candidate_execution_allowed or any router logic
  - Does NOT use OracleAnalyzer random scoring
  - SIMULATION/PAPER ONLY

Usage:
    python scripts/run_execution_bridge_shadow.py --date 2026-04-30
    python scripts/run_execution_bridge_shadow.py --date 2026-04-30 --mode PAPER
    python scripts/run_execution_bridge_shadow.py --date 2026-04-30 --audit-results
    python scripts/run_execution_bridge_shadow.py --date 2026-04-30 --ledger data/racing_api_shadow_forward_ledger.csv
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Safety: ensure no LIVE mode leaks in before imports
os.environ.setdefault("VELO_EXECUTION_MODE", "SIM")
os.environ.setdefault("BETFAIR_MODE", "SIM")

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests

from src.velo.execution_bridge import (
    DEFAULT_PAPER_LEDGER,
    VeloExecutionBridge,
    enrich_from_shadow_ledger,
)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_headers() -> tuple[str, dict]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not set in environment")
    return url, {"apikey": key, "Authorization": f"Bearer {key}"}


def load_verdicts(date_str: str) -> list[dict]:
    """
    Load all velo_verdicts for date_str (YYYY-MM-DD).
    Filters by generated_at prefix so Railway-cron records are included.
    """
    url, hdrs = _sb_headers()
    resp = requests.get(
        f"{url}/rest/v1/velo_verdicts",
        headers=hdrs,
        params={
            "select": (
                "race_id,generated_at,decision_tier,velo_prime_prob,"
                "market_deception_score,improvement_score,rpdc_release_score,"
                "place_prob,race_archetype,archetype_suppression,"
                "execution_allowed,assigned_product,router_reasons,full_analysis"
            ),
            "generated_at": f"gte.{date_str}T00:00:00",
            "order": "generated_at.asc",
            "limit": "500",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        raise RuntimeError(f"Supabase error loading verdicts: {data}")
    filtered = [v for v in data if _s(v.get("generated_at")).startswith(date_str)]
    return filtered


def load_sigma_outcomes(date_str: str) -> dict[str, dict]:
    """
    Load sigma_audits for date_str, keyed by race_id.
    Fetches outcome, actual_winner fields, and SP for paper P&L.
    """
    url, hdrs = _sb_headers()
    resp = requests.get(
        f"{url}/rest/v1/sigma_audits",
        headers=hdrs,
        params={
            "select": "race_id,track,off_time,outcome,actual_winner_name,actual_winner_sp,top_pick_position",
            "date": f"eq.{date_str}",
            "limit": "500",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        return {}
    return {r["race_id"]: r for r in data if r.get("race_id")}


def _s(v, default: str = "") -> str:
    return str(v).strip() if v is not None else default


# ── Summary printer ───────────────────────────────────────────────────────────

def print_summary(
    date_str: str,
    verdicts: list[dict],
    directives,
    added: int,
    skipped: int,
    ledger_path: Path,
) -> None:
    n = len(directives)
    counts: Counter = Counter(d.directive_type for d in directives)
    blocked_reasons: Counter = Counter(
        d.execution_blocked_reason
        for d in directives
        if d.directive_type == "BLOCKED" and d.execution_blocked_reason
    )

    print()
    print("=" * 70)
    print(f"VELO EXECUTION BRIDGE SHADOW RUN — {date_str}")
    print("=" * 70)
    print(f"  Mode:            {os.getenv('VELO_EXECUTION_MODE', 'SIM')}")
    print(f"  Verdicts loaded: {len(verdicts)}")
    print(f"  Directives:      {n}")
    print()
    print("── DIRECTIVE COUNTS ───────────────────────────────────────────────")
    for dtype in [
        "POWER_ANCHOR_MODE", "FAVOURITE_LIABILITY_MODE",
        "MULTI_THREAT_ZONE_MODE", "WATCH_ONLY",
        "CHAOS_CONTAINMENT_MODE", "BLOCKED",
    ]:
        c = counts.get(dtype, 0)
        if c:
            print(f"  {dtype:<35s}  {c}")
    print()
    print("── PAPER LEDGER ───────────────────────────────────────────────────")
    print(f"  Path:    {ledger_path}")
    print(f"  Added:   {added}")
    print(f"  Skipped: {skipped} (idempotency — already written)")
    print()

    if blocked_reasons:
        print("── BLOCKED REASONS ────────────────────────────────────────────────")
        for reason, cnt in blocked_reasons.most_common():
            print(f"  {reason:<45s}  {cnt}")
        print()

    print("── DIRECTIVE DETAIL ───────────────────────────────────────────────")
    active_types = {"POWER_ANCHOR_MODE", "FAVOURITE_LIABILITY_MODE", "MULTI_THREAT_ZONE_MODE", "WATCH_ONLY"}
    for d in directives:
        if d.directive_type in active_types:
            print(
                f"  {d.off_time or '?':5s}  {d.course or '?':<16s}  "
                f"{d.horse:<28s}  {d.tier:<2s}  VP={d.velo_prime_prob:.3f}  "
                f"{d.directive_type}"
            )
    print()
    print("── GOVERNANCE CONFIRMATION ────────────────────────────────────────")
    print("  BetfairClient.place_order:  NOT CALLED")
    print("  Telegram:                   NOT SENT")
    print("  Staking:                    NONE")
    print("  Live execution:             BLOCKED")
    print("  OracleAnalyzer:             NOT USED")
    print("  candidate_execution_allowed: UNCHANGED (read-only)")
    print("  simulation_only flag:       True on all directives")
    print("=" * 70)


# ── Paper P&L calculator ──────────────────────────────────────────────────────

# Paper stake per active directive (£1 unit, simulation only)
_PAPER_STAKE = 1.0

_BETTING_DIRECTIVES = {"POWER_ANCHOR_MODE", "FAVOURITE_LIABILITY_MODE", "MULTI_THREAT_ZONE_MODE"}


def _paper_pnl(directive_type: str, outcome: str, sp: float | None) -> float | None:
    """
    Simulate paper P&L for a directive given a result outcome.

    POWER_ANCHOR_MODE     → WIN bet, 1pt stake
    MULTI_THREAT_ZONE_MODE→ EACH_WAY, 0.5pt win + 0.5pt place (1/4 odds)
    FAVOURITE_LIABILITY_MODE → not simulated as a back bet (LAY is complex, skip)
    WATCH_ONLY / BLOCKED  → no paper bet, P&L = 0
    """
    if directive_type not in _BETTING_DIRECTIVES:
        return 0.0
    if not outcome or sp is None:
        return None  # result not yet available

    if directive_type == "POWER_ANCHOR_MODE":
        if outcome == "WIN":
            return round((sp - 1) * _PAPER_STAKE, 2)
        return round(-_PAPER_STAKE, 2)

    if directive_type == "MULTI_THREAT_ZONE_MODE":
        half = _PAPER_STAKE / 2
        if outcome == "WIN":
            win_profit = (sp - 1) * half
            place_profit = ((sp / 4) - 1) * half
            return round(win_profit + place_profit, 2)
        if outcome == "PLACED":
            win_loss = -half
            place_profit = ((sp / 4) - 1) * half
            return round(win_loss + place_profit, 2)
        return round(-_PAPER_STAKE, 2)

    if directive_type == "FAVOURITE_LIABILITY_MODE":
        # LAY simulation skipped — complex liability calculation needs live odds
        return None

    return 0.0


# ── Audit results ─────────────────────────────────────────────────────────────

def run_audit_results(date_str: str, paper_path: Path, sigma_map: dict) -> None:
    """
    Match paper ledger rows for date_str against sigma outcomes.
    Updates result_position / won / placed / sp_decimal / paper_profit_loss in-place.
    Prints outcome audit table and comparative summary.
    """
    if not paper_path.exists():
        print(f"  Paper ledger not found: {paper_path}")
        return

    import csv as _csv

    rows = []
    with paper_path.open(encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))

    date_rows = [r for r in rows if r.get("date") == date_str]
    if not date_rows:
        print(f"  No paper ledger rows for {date_str}.")
        return

    updated = 0
    for r in rows:
        if r.get("date") != date_str:
            continue
        rid = r.get("race_id", "")
        sig = sigma_map.get(rid, {})
        if not sig:
            continue
        outcome = sig.get("outcome") or ""
        sp_raw = sig.get("actual_winner_sp")
        sp = float(sp_raw) if sp_raw is not None else None
        pos = sig.get("top_pick_position")

        r["result_position"] = str(pos) if pos else ""
        r["won"] = "1" if outcome == "WIN" else ("0" if outcome in ("PLACED", "MISS") else "")
        r["placed"] = "1" if outcome in ("WIN", "PLACED") else ("0" if outcome == "MISS" else "")
        r["sp_decimal"] = str(sp) if sp else ""

        pnl = _paper_pnl(r.get("directive_type", ""), outcome, sp)
        r["paper_profit_loss"] = str(pnl) if pnl is not None else ""
        updated += 1

    # Write back
    from src.velo.execution_bridge import _PAPER_LEDGER_HEADER
    with paper_path.open("w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=_PAPER_LEDGER_HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Updated {updated} rows with outcomes.")
    print()

    # ── Print outcome audit table ─────────────────────────────────────────────
    from collections import defaultdict

    dtype_buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("date") == date_str:
            dtype_buckets[r.get("directive_type", "UNKNOWN")].append(r)

    DTYPE_ORDER = [
        "POWER_ANCHOR_MODE", "FAVOURITE_LIABILITY_MODE",
        "MULTI_THREAT_ZONE_MODE", "WATCH_ONLY",
        "CHAOS_CONTAINMENT_MODE", "BLOCKED",
    ]

    print("=" * 80)
    print(f"EXECUTION BRIDGE PAPER OUTCOME AUDIT — {date_str}")
    print("=" * 80)

    total_pnl = 0.0
    total_bets = 0
    total_wins = 0
    total_placed = 0

    for dtype in DTYPE_ORDER:
        bucket = dtype_buckets.get(dtype, [])
        if not bucket:
            continue
        wins = sum(1 for r in bucket if r.get("won") == "1")
        placed = sum(1 for r in bucket if r.get("placed") == "1")
        with_result = sum(1 for r in bucket if r.get("won") != "")
        pnls = [float(r["paper_profit_loss"]) for r in bucket
                if r.get("paper_profit_loss") not in ("", "None")]
        bucket_pnl = sum(pnls) if pnls else 0.0
        total_pnl += bucket_pnl

        is_betting = dtype in _BETTING_DIRECTIVES
        if is_betting:
            total_bets += with_result
            total_wins += wins
            total_placed += placed

        sr_str = f"SR={wins/with_result*100:.0f}%" if with_result else "SR=n/a"
        fr_str = f"Frame={placed/with_result*100:.0f}%" if with_result else "Frame=n/a"
        pnl_str = f"P&L={bucket_pnl:+.2f}" if is_betting and pnls else ""

        print(f"\n  {dtype}")
        print(f"    n={len(bucket)}  results={with_result}  W={wins}  F={placed}  "
              f"{sr_str}  {fr_str}  {pnl_str}")
        for r in bucket:
            if r.get("won") != "" or dtype in _BETTING_DIRECTIVES:
                outcome_tag = (
                    "WIN   " if r.get("won") == "1" else
                    "PLACE " if r.get("placed") == "1" else
                    "MISS  " if r.get("won") == "0" else
                    "pending"
                )
                sp_tag = f"SP={r['sp_decimal']}" if r.get("sp_decimal") else ""
                pnl_tag = f"p&l={r['paper_profit_loss']}" if r.get("paper_profit_loss") else ""
                print(f"      {r.get('off_time','?'):5s}  {r.get('course','?'):<16s}  "
                      f"{r.get('horse','?'):<28s}  {outcome_tag}  {sp_tag}  {pnl_tag}")

    print()
    print("── COMPARATIVE SUMMARY ─────────────────────────────────────────────")
    pa_rows = dtype_buckets.get("POWER_ANCHOR_MODE", [])
    wo_rows = dtype_buckets.get("WATCH_ONLY", [])

    def _sr(bucket):
        with_r = [r for r in bucket if r.get("won") != ""]
        if not with_r:
            return None, 0
        return sum(1 for r in with_r if r.get("won") == "1") / len(with_r), len(with_r)

    pa_sr, pa_n = _sr(pa_rows)
    wo_sr, wo_n = _sr(wo_rows)

    print(f"  POWER_ANCHOR_MODE  n={pa_n}  SR={pa_sr*100:.0f}%  P&L={sum(float(r['paper_profit_loss']) for r in pa_rows if r.get('paper_profit_loss') not in ('','None')):+.2f}" if pa_sr is not None else f"  POWER_ANCHOR_MODE  n=0")
    print(f"  WATCH_ONLY         n={wo_n}  SR={wo_sr*100:.0f}%  (no paper bet — observe only)" if wo_sr is not None else f"  WATCH_ONLY         n=0")

    if pa_sr is not None and wo_sr is not None:
        delta = pa_sr - wo_sr
        verdict = "POWER_ANCHOR beat WATCH_ONLY" if delta > 0 else "No edge over WATCH_ONLY"
        print(f"  Delta: {delta*100:+.1f}pp  → {verdict}")
        gate_value = "GATE ADDED VALUE" if delta > 0 else "GATE NEUTRAL"
        print(f"  Bridge gate assessment: {gate_value}")
    else:
        print("  Insufficient results for comparative assessment.")

    print()
    print("── PAPER P&L TOTAL ─────────────────────────────────────────────────")
    print(f"  Active bets (POWER_ANCHOR + MULTI_THREAT): {total_bets}")
    print(f"  Wins: {total_wins}  Placed: {total_placed}")
    if total_bets:
        print(f"  Total paper P&L: {total_pnl:+.2f} pts")
        print(f"  Paper ROI:       {total_pnl/total_bets*100:+.1f}%")
    print()
    print("── FREEZE CHECK ────────────────────────────────────────────────────")
    print("  Freeze condition: ROI < 0 at n≥20 OR Frame < 70% at n≥20")
    if total_bets >= 20:
        roi = total_pnl / total_bets * 100
        frame_rate = total_placed / total_bets * 100 if total_bets else 0
        if roi < 0 or frame_rate < 70:
            print(f"  STATUS: REVIEW (ROI={roi:.1f}%, Frame={frame_rate:.1f}%)")
        else:
            print(f"  STATUS: NO_FREEZE (ROI={roi:.1f}%, Frame={frame_rate:.1f}%)")
    else:
        print(f"  STATUS: INSUFFICIENT_SAMPLE (n={total_bets}, need 20)")
    print()
    print("── GOVERNANCE ──────────────────────────────────────────────────────")
    print("  Live execution:   NOT OCCURRED")
    print("  Staking:          NONE")
    print("  Telegram:         NOT SENT")
    print("  Model changes:    NONE")
    print("  Router promotion: NONE")
    print("=" * 80)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="VeloExecutionBridge shadow run")
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument(
        "--mode", default="SIM", choices=["OFF", "SIM", "PAPER"],
        help="Execution mode (default: SIM). LIVE is not accepted."
    )
    parser.add_argument(
        "--ledger", default=None,
        help="Path to Racing API shadow forward ledger CSV (optional)"
    )
    parser.add_argument(
        "--paper-ledger", default=str(DEFAULT_PAPER_LEDGER),
        help="Output paper ledger path"
    )
    parser.add_argument(
        "--audit-results", action="store_true",
        help="Match paper ledger against sigma outcomes, update P&L, print audit table"
    )
    args = parser.parse_args()

    date_str = args.date

    # Hard safety: force ENV before bridge instantiation
    os.environ["VELO_EXECUTION_MODE"] = args.mode
    os.environ["BETFAIR_MODE"] = "SIM"  # never LIVE from this script

    print(f"\nVELO EXECUTION BRIDGE SHADOW — {date_str}")
    print(f"Mode: {args.mode}  |  Betfair: SIM (forced)")

    # 1. Load verdicts
    print(f"\nLoading verdicts for {date_str} ...")
    verdicts = load_verdicts(date_str)
    print(f"  Loaded: {len(verdicts)} verdicts")

    if not verdicts:
        print(f"  No verdicts found for {date_str}. Run run_prime_today.py first.")
        return

    # 2. Join sigma outcomes for display fields (off_time, track)
    print("Loading sigma outcomes for display enrichment ...")
    sigma_map = load_sigma_outcomes(date_str)
    print(f"  Sigma rows: {len(sigma_map)}")

    # Inject sigma display fields into verdicts (non-destructive)
    for v in verdicts:
        sig = sigma_map.get(_s(v.get("race_id")), {})
        if sig:
            if not v.get("off_time"):
                v["off_time"] = sig.get("off_time", "")
            if not v.get("course"):
                v["course"] = sig.get("track", "")

    # 3. Enrich from Racing API shadow ledger
    ledger_path = Path(args.ledger) if args.ledger else None
    print("Enriching from Racing API shadow ledger ...")
    verdicts = enrich_from_shadow_ledger(verdicts, ledger_path)

    # 4. Generate directives
    bridge = VeloExecutionBridge(mode=args.mode)
    directives = bridge.generate_directives(verdicts)
    print(f"  Directives generated: {len(directives)}")

    # 5. Write paper ledger
    paper_path = Path(args.paper_ledger)
    rows_before = 0
    if paper_path.exists():
        import csv as _csv
        with paper_path.open(encoding="utf-8") as f:
            rows_before = sum(1 for _ in _csv.DictReader(f))

    added, skipped = bridge.append_to_paper_ledger(directives, paper_path)

    rows_after = rows_before + added

    # 6. Print summary
    print_summary(date_str, verdicts, directives, added, skipped, paper_path)
    print(f"Paper ledger rows: {rows_before} → {rows_after}")

    # 7. Optional: audit results
    if args.audit_results:
        print("\nRunning outcome audit ...")
        # Reload sigma with SP for P&L
        sigma_with_sp = load_sigma_outcomes(date_str)
        run_audit_results(date_str, paper_path, sigma_with_sp)


if __name__ == "__main__":
    main()
