#!/usr/bin/env python3
"""
BUILD_NAMED_LANE_OPERATOR_CARD_V1

Generates a daily operator war board — one card per candidate horse,
enriched with lane classification, signal profile, RP/CASHRUN context,
and action label.

Action labels (advisory only — no execution impact):
  PRIORITY_WATCH   — high-conviction lane (MDS_HIGH, IMPROVER, VP40_TierA)
  WATCH            — proven lane (VP40, SHORTFAV_VP30, MIDPRICE_ROUTER_QUAL)
  SUPPRESS_ADVISORY — weak lane (MIDPRICE no-router, LONGSHOT)
  HOLD_MORE_DATA   — no lane qualified or insufficient signal

Governance:
  No scoring change | No model change | No router change | No staking | Advisory only

Outputs:
    data/reports/named_lane_operator_card_latest.md
    data/reports/named_lane_operator_card_latest.json

Usage:
    python scripts/build_named_lane_operator_card.py [--date YYYY-MM-DD]
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ── Lane definitions ──────────────────────────────────────────────────────────

LANE_PRIORITY = {
    "MDS_HIGH_LANE": ("PRIORITY_WATCH", 1),
    "IMPROVER_LANE": ("PRIORITY_WATCH", 2),
    "VP40_TIER_A_LANE": ("PRIORITY_WATCH", 3),
    "VP40_LANE": ("WATCH", 4),
    "SHORTFAV_VP30": ("WATCH", 5),
    "MIDPRICE_ROUTER_QUAL": ("WATCH", 6),
    "MIDPRICE_SUPPRESS": ("SUPPRESS_ADVISORY", 7),
    "LONGSHOT_SUPPRESS": ("SUPPRESS_ADVISORY", 8),
}

# Historical SR for each lane (from 2026-05-17 1310-row corpus)
LANE_HISTORICAL_SR = {
    "MDS_HIGH_LANE": 69.2,
    "IMPROVER_LANE": 42.1,
    "VP40_TIER_A_LANE": 44.7,
    "VP40_LANE": 45.3,
    "SHORTFAV_VP30": 52.2,
    "MIDPRICE_ROUTER_QUAL": 33.3,
    "MIDPRICE_SUPPRESS": 16.0,
    "LONGSHOT_SUPPRESS": 6.3,
}

ACTION_ICONS = {
    "PRIORITY_WATCH": "🔴",
    "WATCH": "🟡",
    "SUPPRESS_ADVISORY": "⬇️",
    "HOLD_MORE_DATA": "⬜",
}


def _sp_band(sp: float) -> str:
    if sp <= 0:
        return "UNKNOWN"
    if sp < 2.0:
        return "ODDS_ON"
    if sp < 3.0:
        return "SHORT_PRICE"
    if sp <= 8.5:
        return "MID_PRICE"
    if sp <= 16.0:
        return "OUTSIDER"
    return "LONGSHOT"


def _classify_lanes(top: dict) -> list[str]:
    vp = float(top.get("velo_prime_prob") or 0.0)
    mds = float(top.get("market_deception_score") or 0.0)
    imp = float(top.get("improvement_score") or 0.0)
    sp = float(top.get("sp_decimal") or 0.0)
    tier = str(top.get("decision_tier") or top.get("confidence_level") or "").upper()

    router_flags = (
        top.get("router_v1_shadow_pass") is True or
        top.get("router_v2_class4_shadow_pass") is True or
        top.get("router_v6_gold_seam_watchlist") is True
    )
    exec_lane = str(top.get("candidate_execution_lane") or "")
    router_q = router_flags or (exec_lane not in {"", "NO_BET", "ATTACK_LANE_MISS"})

    lanes = []
    if vp >= 0.30 and mds > 0.50:
        lanes.append("MDS_HIGH_LANE")
    if vp >= 0.30 and imp > 0.40:
        lanes.append("IMPROVER_LANE")
    if vp >= 0.40 and tier == "A":
        lanes.append("VP40_TIER_A_LANE")
    if vp >= 0.40:
        lanes.append("VP40_LANE")
    if 0 < sp < 3.0 and vp >= 0.30:
        lanes.append("SHORTFAV_VP30")
    if 3.0 <= sp <= 8.5 and router_q:
        lanes.append("MIDPRICE_ROUTER_QUAL")
    if 3.0 <= sp <= 8.5 and not router_q:
        lanes.append("MIDPRICE_SUPPRESS")
    if sp > 8.5:
        lanes.append("LONGSHOT_SUPPRESS")
    return lanes


def _best_action(lanes: list[str]) -> str:
    if not lanes:
        return "HOLD_MORE_DATA"
    best_priority = 999
    best_action = "HOLD_MORE_DATA"
    for lane in lanes:
        if lane in LANE_PRIORITY:
            action, pri = LANE_PRIORITY[lane]
            if pri < best_priority:
                best_priority = pri
                best_action = action
    return best_action


def _get_router_lane(top: dict) -> str:
    lane = str(top.get("candidate_execution_lane") or "")
    if lane and lane not in {"", "NO_BET", "ATTACK_LANE_MISS"}:
        return lane
    lanes = []
    if top.get("router_v1_shadow_pass") is True:
        lanes.append("V1_BASE")
    if top.get("router_v2_class4_shadow_pass") is True:
        lanes.append("V2_CLASS4")
    if top.get("router_v6_gold_seam_watchlist") is True:
        lanes.append("V6_GOLD_SEAM")
    return ",".join(lanes) if lanes else "NONE"


def _load_convergence(date: str) -> dict[str, dict]:
    """Load RP/VELO convergence data — keyed by normalised horse name."""
    path = REPORTS_DIR / f"rp_velo_convergence_{date}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        watchlist = (data.get("summary") or {}).get("top_operator_watchlist") or []
        result = {}
        for row in watchlist:
            horse = str(row.get("velo_horse") or row.get("horse") or "").strip().lower()
            if horse:
                result[horse] = {
                    "convergence": row.get("convergence_score"),
                    "rp_pick": row.get("rp_pick"),
                    "classification": row.get("classification"),
                    "cashrun_status": row.get("cashrun_status"),
                }
        return result
    except Exception:
        return {}


def _load_cashrun_report(date: str) -> dict[str, str]:
    """Parse CASHRUN report for horse → class mapping."""
    date_str = date.replace("-", "_")
    path = DATA / f"cashrun_report_{date_str}.md"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        result = {}
        current_class = ""
        for line in text.splitlines():
            if line.startswith("## CASHRUN_READY"):
                current_class = "CASHRUN_READY"
            elif line.startswith("## CASHRUN_WATCH"):
                current_class = "CASHRUN_WATCH"
            elif line.startswith("## WEAK_SIGNAL"):
                current_class = "WEAK_SIGNAL"
            elif line.startswith("## SUPPRESS"):
                current_class = "SUPPRESS"
            elif line.startswith("### ") and current_class:
                horse_raw = line[4:].split(" - ", 1)[0].strip()
                result[horse_raw.lower()] = current_class
        return result
    except Exception:
        return {}


def _build_card(verdict: dict, top: dict, lanes: list[str], action: str,
                convergence_data: dict, cashrun_data: dict) -> dict:
    horse = top.get("horse", "?")
    horse_norm = horse.strip().lower()

    vp = float(top.get("velo_prime_prob") or 0.0)
    mds = float(top.get("market_deception_score") or 0.0)
    imp = float(top.get("improvement_score") or 0.0)
    sp = float(top.get("sp_decimal") or 0.0)
    tier = str(top.get("decision_tier") or top.get("confidence_level") or "?")
    router_lane = _get_router_lane(top)
    sp_band = _sp_band(sp)

    conv = convergence_data.get(horse_norm, {})
    rp_support = conv.get("classification", "UNKNOWN")
    convergence_score = conv.get("convergence")
    cashrun_class = cashrun_data.get(horse_norm, "UNKNOWN")

    lane_srs = {lane: LANE_HISTORICAL_SR.get(lane) for lane in lanes}
    best_lane_sr = max(lane_srs.values(), default=None)

    return {
        "horse": horse,
        "race": f"{verdict.get('course', '?')} {verdict.get('off_time', '?')}",
        "course": verdict.get("course", "?"),
        "off_time": verdict.get("off_time", "?"),
        "lanes": lanes,
        "primary_lane": lanes[0] if lanes else None,
        "action": action,
        "vp": round(vp, 3),
        "mds": round(mds, 3),
        "improvement": round(imp, 3),
        "sp": sp if sp > 0 else None,
        "sp_band": sp_band,
        "tier": tier,
        "router_lane": router_lane,
        "rp_classification": rp_support,
        "convergence_score": round(convergence_score, 3) if convergence_score else None,
        "cashrun_class": cashrun_class,
        "lane_historical_sr": best_lane_sr,
    }


def _build_md(cards: list[dict], date: str, run_ts: str) -> str:
    action_order = {"PRIORITY_WATCH": 0, "WATCH": 1, "SUPPRESS_ADVISORY": 2, "HOLD_MORE_DATA": 3}
    cards_sorted = sorted(cards, key=lambda c: (action_order.get(c["action"], 99),
                                                 -(c.get("lane_historical_sr") or 0)))
    lines = [
        "# VELO OPERATOR WAR BOARD",
        f"**Date:** {date}",
        f"**Run:** {run_ts}",
        "",
        "Advisory only. No execution. No scoring change. No staking.",
        "",
        "---",
        "",
    ]

    for action_label in ("PRIORITY_WATCH", "WATCH", "SUPPRESS_ADVISORY", "HOLD_MORE_DATA"):
        batch = [c for c in cards_sorted if c["action"] == action_label]
        if not batch:
            continue
        icon = ACTION_ICONS.get(action_label, "")
        lines.append(f"## {icon} {action_label} ({len(batch)})")
        lines.append("")
        lines.append("| Horse | Race | Lanes | VP | MDS | IMP | SP | SP Band | Tier | Router | RP | CASHRUN | Lane SR |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for c in batch:
            lanes_str = " + ".join(c["lanes"]) if c["lanes"] else "—"
            sp_str = str(c["sp"]) if c["sp"] else "?"
            lr_sr = f"{c['lane_historical_sr']}%" if c["lane_historical_sr"] else "?"
            rp = c.get("rp_classification") or "?"
            cr = c.get("cashrun_class") or "?"
            lines.append(
                f"| **{c['horse']}** | {c['race']} | {lanes_str} | {c['vp']} | {c['mds']} | {c['improvement']} "
                f"| {sp_str} | {c['sp_band']} | {c['tier']} | {c['router_lane']} | {rp} | {cr} | {lr_sr} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Lane Reference SR (historical corpus at 1310 rows)",
        "",
        "| Lane | SR | Status |",
        "|---|---|---|",
        "| MDS_HIGH_LANE | 69.2% | PROVEN (n=39, sample warning) |",
        "| IMPROVER_LANE | 42.1% | PROVEN (n=38, sample warning) |",
        "| VP40_TIER_A_LANE | 44.7% | PROVEN |",
        "| VP40_LANE | 45.3% | PROVEN |",
        "| SHORTFAV_VP30 | 52.2% | PROVEN |",
        "| MIDPRICE_ROUTER_QUAL | 33.3% | INSUFFICIENT_SAMPLE (n=18) |",
        "| MIDPRICE_SUPPRESS | 16.0% | SUPPRESS_CONFIRMED |",
        "| LONGSHOT_SUPPRESS | 6.3% | SUPPRESS_CONFIRMED |",
        "",
        "---",
        "",
        "*BUILD_NAMED_LANE_OPERATOR_CARD_V1 — advisory only, no execution impact*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    date = args.date

    print(f"BUILD NAMED LANE OPERATOR CARD V1 — {date}")
    print("=" * 60)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    # Load verdict JSON
    date_str = date.replace("-", "_")
    verdict_path = DATA / f"velo_prime_verdicts_{date_str}.json"
    if not verdict_path.exists():
        print(f"  No verdict file for {date} — {verdict_path}")
        cards = []
    else:
        verdicts = json.loads(verdict_path.read_text(encoding="utf-8"))
        convergence_data = _load_convergence(date)
        cashrun_data = _load_cashrun_report(date)

        cards = []
        for verdict in verdicts:
            top = verdict.get("top") or {}
            if not top:
                continue
            lanes = _classify_lanes(top)
            action = _best_action(lanes)
            card = _build_card(verdict, top, lanes, action, convergence_data, cashrun_data)
            cards.append(card)

    # Summary counts
    action_counts = {}
    for c in cards:
        action_counts[c["action"]] = action_counts.get(c["action"], 0) + 1

    print(f"  Total verdicts: {len(cards)}")
    for action, count in sorted(action_counts.items()):
        icon = ACTION_ICONS.get(action, "")
        names = [c["horse"] for c in cards if c["action"] == action]
        print(f"  {icon} {action}: {count} — {', '.join(names[:5])}")

    output = {
        "run_ts": run_ts,
        "date": date,
        "total_candidates": len(cards),
        "action_summary": action_counts,
        "cards": cards,
        "governance": {
            "scoring_change": False,
            "model_change": False,
            "router_change": False,
            "staking_change": False,
            "telegram": False,
            "classification": "OPERATOR_ADVISORY_CARD_ONLY",
        },
    }

    json_path = REPORTS_DIR / "named_lane_operator_card_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(cards, date, run_ts)
    md_path = REPORTS_DIR / "named_lane_operator_card_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return output


if __name__ == "__main__":
    main()
