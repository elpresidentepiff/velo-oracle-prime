"""
VÉLØ Signal Tracker
====================

Daily signal tracker for the VÉLØ learning loop.

For each target date:
1. Reads velo_post_race_reviews from Supabase
2. Matches results against the day's sidecar stacks (ELITE, STRONG, VP30_IMPROVE, etc.)
3. Reports per-stack: n_fired, n_won, n_placed, SR, frame_rate
4. Appends to rolling ledger CSV
5. Flags if any signal class is diverging from audit baseline

Baseline SRs (49-day audit, 2026-04-28):
    MDS>0.50:        SR=54.8%   — ALERT if <30% at n≥10
    IMP>0.40:        SR=43.5%   — ALERT if <25% at n≥10
    VP30+TierA:      SR=40.1%   — ALERT if <20% at n≥10

Usage:
    python scripts/velo_signal_tracker.py --date 2026-05-02

Outputs:
    data/velo_signal_tracker_{date}.md
    data/velo_signal_tracker_ledger.csv   (append)
    stdout

Classification:
    OPERATOR VISIBILITY ONLY
    NO STAKING. NO EXECUTION.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

DATA = ROOT / "data"

DISCLAIMER = (
    "OPERATOR VISIBILITY ONLY — Signal tracker is intelligence and audit output. "
    "No scoring, model, SQPE, or router changes. No staking. No live execution."
)

# ── Baseline SRs from 49-day unified audit ────────────────────────────────────

BASELINES = {
    "MDS_HIGH": {
        "label":   "Market deception score > 0.50",
        "sr":       0.548,
        "frame":    0.968,
        "n_audit":  31,
        "alert_sr": 0.30,
        "alert_n":  10,
    },
    "IMP_HIGH": {
        "label":   "Improvement score > 0.40",
        "sr":       0.435,
        "frame":    0.823,
        "n_audit":  62,
        "alert_sr": 0.25,
        "alert_n":  10,
    },
    "VP30_TIER_A": {
        "label":   "VP≥0.30 + Tier A",
        "sr":       0.401,
        "frame":    0.772,
        "n_audit":  162,
        "alert_sr": 0.20,
        "alert_n":  10,
    },
    "ELITE_STACK": {
        "label":   "Tier A + VP≥0.30 + MDS>0.50",
        "sr":       0.401,
        "frame":    0.772,
        "n_audit":  28,
        "alert_sr": 0.15,
        "alert_n":  8,
    },
    "STRONG_STACK": {
        "label":   "VP≥0.30 + MDS>0.50",
        "sr":       0.548,
        "frame":    0.968,
        "n_audit":  35,
        "alert_sr": 0.20,
        "alert_n":  8,
    },
    "VP30_IMPROVE": {
        "label":   "VP≥0.30 + IMP>0.40",
        "sr":       0.435,
        "frame":    0.870,
        "n_audit":  46,
        "alert_sr": 0.20,
        "alert_n":  8,
    },
    "VP30_BASE": {
        "label":   "VP≥0.30 only",
        "sr":       0.322,
        "frame":    0.693,
        "n_audit":  345,
        "alert_sr": 0.15,
        "alert_n":  15,
    },
}

LEDGER_HEADER = ["date", "stack_label", "n_fired", "n_won", "n_placed", "sr", "frame_rate", "alert_flag"]


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_headers() -> dict:
    sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    return {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Accept": "application/json",
    }


def _sb_get(path: str, params: str = "") -> list:
    sb_url = os.getenv("SUPABASE_URL", "")
    if not sb_url:
        return []
    url = f"{sb_url}/rest/v1{path}"
    if params:
        url += "?" + params
    req = urllib.request.Request(url, method="GET", headers=_sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data if isinstance(data, list) else []
    except Exception:
        return []


def load_sigma_reviews(date_str: str) -> list[dict]:
    """Load velo_post_race_reviews for the target date."""
    params = (
        f"review_date=gte.{date_str}T00:00:00"
        f"&review_date=lt.{date_str}T23:59:59"
        f"&select=race_id,horse,outcome,velo_prime_prob,market_deception_score,"
        f"improvement_score,place_prob,decision_tier,sigma_hit,sigma_frame"
    )
    rows = _sb_get("/velo_post_race_reviews", params)
    if not rows:
        # Fallback: try by race_date or generated_at field names
        params2 = (
            f"generated_at=gte.{date_str}T00:00:00"
            f"&generated_at=lt.{date_str}T23:59:59"
            f"&select=race_id,horse,outcome,velo_prime_prob,market_deception_score,"
            f"improvement_score,place_prob,decision_tier,sigma_hit,sigma_frame"
        )
        rows = _sb_get("/velo_post_race_reviews", params2)
    return rows


def load_sidecar(date_str: str) -> dict | None:
    """Load sidecar_stack_operator_card JSON for the date."""
    path = DATA / f"sidecar_stack_operator_card_{date_str.replace('-', '_')}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback to dashboard latest
    latest = ROOT / "app" / "static" / "dashboard" / "sidecar_stack_latest.json"
    if latest.exists():
        try:
            d = json.loads(latest.read_text(encoding="utf-8"))
            if d.get("date") == date_str:
                return d
        except Exception:
            pass
    return None


# ── Matching and classification ───────────────────────────────────────────────

def _is_won(row: dict) -> bool:
    """Determine if a sigma review row is a WIN."""
    outcome = str(row.get("outcome") or "").upper()
    sigma_hit = row.get("sigma_hit")
    if sigma_hit is True:
        return True
    return any(w in outcome for w in ["WIN", "WON", "1ST", "WINNER"])


def _is_placed(row: dict) -> bool:
    """Determine if a sigma review row is PLACED (frame)."""
    if _is_won(row):
        return True
    outcome = str(row.get("outcome") or "").upper()
    sigma_frame = row.get("sigma_frame")
    if sigma_frame is True:
        return True
    return any(p in outcome for p in ["PLACE", "2ND", "3RD", "4TH", "FRAME"])


def classify_row_stacks(r: dict) -> list[str]:
    """Classify a sigma review row into stack membership."""
    vp  = float(r.get("velo_prime_prob") or 0)
    mds = float(r.get("market_deception_score") or 0)
    imp = float(r.get("improvement_score") or 0)
    tier = str(r.get("decision_tier") or "").strip().upper()

    stacks = []

    # MDS_HIGH signal
    if mds > 0.50:
        stacks.append("MDS_HIGH")

    # IMP_HIGH signal
    if imp > 0.40:
        stacks.append("IMP_HIGH")

    # VP30_TIER_A signal
    if vp >= 0.30 and tier == "A":
        stacks.append("VP30_TIER_A")

    # Sidecar stacks
    vp30     = vp  >= 0.30
    mds_high = mds >  0.50
    imp_high = imp >  0.40
    tier_a   = tier == "A"
    tier_b   = tier == "B"

    if tier_a and vp30 and mds_high:
        stacks.append("ELITE_STACK")

    if vp30 and mds_high and imp_high:
        stacks.append("STRONG_STACK_PLUS")

    if vp30 and mds_high and not imp_high:
        stacks.append("STRONG_STACK")

    if vp30 and imp_high and not mds_high:
        stacks.append("VP30_IMPROVE")

    if vp30 and not mds_high and not imp_high:
        stacks.append("VP30_BASE")

    return stacks


# ── Core computation ──────────────────────────────────────────────────────────

def compute_signal_stats(sigma_rows: list[dict]) -> dict[str, dict]:
    """For each stack label, compute n_fired, n_won, n_placed, SR, frame_rate."""
    buckets: dict[str, list[dict]] = {k: [] for k in BASELINES}

    for row in sigma_rows:
        for stack in classify_row_stacks(row):
            if stack in buckets:
                buckets[stack].append(row)

    stats = {}
    for stack_label, rows in buckets.items():
        n = len(rows)
        n_won    = sum(1 for r in rows if _is_won(r))
        n_placed = sum(1 for r in rows if _is_placed(r))
        sr       = round(n_won / n, 4) if n > 0 else 0.0
        frame    = round(n_placed / n, 4) if n > 0 else 0.0

        baseline = BASELINES[stack_label]
        alert = False
        alert_msg = ""
        if n >= baseline["alert_n"] and sr < baseline["alert_sr"]:
            alert = True
            alert_msg = (
                f"DIVERGENCE — {stack_label} SR={sr:.1%} below alert threshold "
                f"{baseline['alert_sr']:.0%} at n={n}"
            )

        stats[stack_label] = {
            "label":        baseline["label"],
            "n_fired":      n,
            "n_won":        n_won,
            "n_placed":     n_placed,
            "sr":           sr,
            "frame_rate":   frame,
            "alert":        alert,
            "alert_msg":    alert_msg,
            "baseline_sr":  baseline["sr"],
            "baseline_frame": baseline["frame"],
            "baseline_n":   baseline["n_audit"],
        }

    return stats


# ── Reporting ─────────────────────────────────────────────────────────────────

def build_markdown(date_str: str, stats: dict, sigma_count: int, sidecar: dict | None) -> str:
    lines = [
        f"# VÉLØ SIGNAL TRACKER — {date_str}",
        "",
        "```",
        "STATUS:          OPERATOR_VISIBILITY_ONLY",
        "SCORING_CHANGES: NO",
        "MODEL_CHANGES:   NO",
        "SQPE_CHANGES:    NO",
        "ROUTER_CHANGES:  NO",
        "STAKING:         NO",
        "LIVE_EXECUTION:  NO",
        f"DATE:            {date_str}",
        f"GENERATED:       {datetime.now(timezone.utc).isoformat()}",
        "```",
        "",
        "---",
        "",
        f"## Signal Performance — {date_str}",
        "",
        f"Sigma review rows loaded: **{sigma_count}**",
        "",
        "| Stack | n fired | n won | n placed | SR | Frame | Baseline SR | Alert |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    alerts = []
    for stack_label, s in stats.items():
        alert_flag = "🔴 DIVERGE" if s["alert"] else "OK"
        lines.append(
            f"| {stack_label} | {s['n_fired']} | {s['n_won']} | {s['n_placed']} "
            f"| {s['sr']:.1%} | {s['frame_rate']:.1%} "
            f"| {s['baseline_sr']:.1%} | {alert_flag} |"
        )
        if s["alert"]:
            alerts.append(s["alert_msg"])

    lines.append("")

    if alerts:
        lines.append("## ⚠ DIVERGENCE ALERTS")
        lines.append("")
        for a in alerts:
            lines.append(f"- **{a}**")
        lines.append("")
    else:
        lines.append("## Signal Status: NO DIVERGENCE ALERTS TODAY")
        lines.append("")

    lines.append("## Baseline Reference (49-day audit, 2026-04-28)")
    lines.append("")
    lines.append("| Signal | Baseline SR | Baseline Frame | n_audit | Alert threshold |")
    lines.append("|---|---:|---:|---:|---|")
    for stack_label, b in BASELINES.items():
        lines.append(
            f"| {stack_label} | {b['sr']:.1%} | {b['frame']:.1%} "
            f"| {b['n_audit']} | SR<{b['alert_sr']:.0%} at n≥{b['alert_n']} |"
        )

    if sidecar:
        lines.append("")
        lines.append("## Today's Sidecar Stack Counts")
        lines.append("")
        c = sidecar.get("counts", {})
        lines.append(f"- Total scored: {c.get('total_races', '—')}")
        lines.append(f"- VP30: {c.get('vp30_count', '—')}")
        lines.append(f"- ELITE_STACK: {c.get('elite_stack_count', '—')}")
        lines.append(f"- STRONG_STACK: {c.get('strong_stack_count', '—')}")
        lines.append(f"- VP30_IMPROVE: {c.get('vp30_improve_count', '—')}")
        lines.append(f"- SUPPRESS: {c.get('suppress_count', '—')}")

    lines += [
        "",
        "---",
        "",
        f"*{DISCLAIMER}*",
    ]
    return "\n".join(lines)


def append_ledger(date_str: str, stats: dict) -> Path:
    """Append today's stats to the rolling ledger CSV."""
    ledger = DATA / "velo_signal_tracker_ledger.csv"
    DATA.mkdir(exist_ok=True)

    # Write header if new file
    write_header = not ledger.exists()
    with open(ledger, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(LEDGER_HEADER)
        for stack_label, s in stats.items():
            writer.writerow([
                date_str,
                stack_label,
                s["n_fired"],
                s["n_won"],
                s["n_placed"],
                round(s["sr"], 4),
                round(s["frame_rate"], 4),
                "ALERT" if s["alert"] else "",
            ])
    return ledger


def print_summary(date_str: str, stats: dict, sigma_count: int) -> None:
    """Print stdout summary."""
    print()
    print("=" * 64)
    print(f"  VÉLØ SIGNAL TRACKER — {date_str}")
    print(f"  Sigma review rows:  {sigma_count}")
    print("=" * 64)
    print(f"  {'Stack':<20} {'n':>4} {'W':>4} {'P':>4} {'SR':>7} {'Frame':>7} {'Base SR':>8}  Alert")
    print("  " + "-" * 62)
    for stack_label, s in stats.items():
        alert = " ⚠ ALERT" if s["alert"] else ""
        print(
            f"  {stack_label:<20} "
            f"{s['n_fired']:>4} {s['n_won']:>4} {s['n_placed']:>4} "
            f"{s['sr']:>6.1%} {s['frame_rate']:>6.1%} "
            f"{s['baseline_sr']:>7.1%}  "
            f"{alert}"
        )
    print("=" * 64)

    alerts = [s["alert_msg"] for s in stats.values() if s["alert"]]
    if alerts:
        print()
        print("  DIVERGENCE ALERTS:")
        for a in alerts:
            print(f"  ⚠  {a}")
    else:
        print("  No divergence alerts today.")
    print()
    print(f"  {DISCLAIMER}")
    print("=" * 64)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="VÉLØ Signal Tracker — daily learning loop")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD race date")
    args = parser.parse_args()
    date_str = args.date

    print(f"[signal_tracker] Loading sigma reviews for {date_str}...")
    sigma_rows = load_sigma_reviews(date_str)
    print(f"[signal_tracker] Loaded {len(sigma_rows)} sigma review rows.")

    if not sigma_rows:
        print(f"[signal_tracker] WARN: No sigma reviews found for {date_str}.")
        print("                 Check velo_post_race_reviews table in Supabase.")
        print("                 Signal tracker will output zeros — run sigma first.")

    sidecar = load_sidecar(date_str)
    if sidecar:
        print(f"[signal_tracker] Sidecar data loaded ({sidecar.get('counts', {}).get('total_races', '?')} races).")
    else:
        print("[signal_tracker] Sidecar data not found — sidecar counts will be skipped.")

    # Compute stats
    stats = compute_signal_stats(sigma_rows)

    # Print stdout
    print_summary(date_str, stats, len(sigma_rows))

    # Write markdown
    DATA.mkdir(exist_ok=True)
    md = build_markdown(date_str, stats, len(sigma_rows), sidecar)
    md_path = DATA / f"velo_signal_tracker_{date_str}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"[signal_tracker] Markdown: {md_path}")

    # Append to ledger
    ledger_path = append_ledger(date_str, stats)
    print(f"[signal_tracker] Ledger:   {ledger_path}")

    print()
    print("[signal_tracker] CONFIRMATION: No scoring/model/SQPE/router/staking/live execution changed.")
    print("[signal_tracker] STATUS: OPERATOR_VISIBILITY_ONLY")


if __name__ == "__main__":
    main()
