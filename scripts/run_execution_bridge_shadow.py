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
    Used to inject off_time, track, outcome into verdicts for display.
    """
    url, hdrs = _sb_headers()
    resp = requests.get(
        f"{url}/rest/v1/sigma_audits",
        headers=hdrs,
        params={
            "select": "race_id,track,off_time,outcome,actual_winner_name",
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


if __name__ == "__main__":
    main()
