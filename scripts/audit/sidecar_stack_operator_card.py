"""
Sidecar Stack Operator Card
============================

Generates a daily sidecar stack operator visibility card for the VÉLØ dashboard.

This is OPERATOR VISIBILITY ONLY — not staking, not betting instruction,
not Betfair execution, not live scoring.

Usage:
    python scripts/sidecar_stack_operator_card.py --date 2026-05-01
    python scripts/sidecar_stack_operator_card.py          # auto-detects latest date

Outputs:
    data/sidecar_stack_operator_card_YYYY_MM_DD.json
    data/sidecar_stack_operator_card_YYYY_MM_DD.md
    app/static/dashboard/sidecar_stack_latest.json

Read-only. No scoring, model, SQPE, router, or staking changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from src.velo.place_signal_classifier import VP30_T, MDS_HIGH_T, IMPROVE_HIGH_T
from src.velo.race_metadata_resolver import RaceMetadataResolver

load_dotenv(ROOT / ".env")

DATA = ROOT / "data"
DASHBOARD = ROOT / "app" / "static" / "dashboard"

DISCLAIMER = (
    "OPERATOR VISIBILITY ONLY — These are sidecar stack signals. "
    "They do not change live scoring, do not trigger staking, "
    "and are not betting instructions."
)

# Stack definitions — documented once here for clarity
STACK_DEFS = {
    "ELITE_STACK": "Tier A + VP≥0.30 + MDS>0.50",
    "STRONG_STACK_PLUS": "VP≥0.30 + MDS>0.50 + IMP>0.40",
    "STRONG_STACK": "VP≥0.30 + MDS>0.50 (no IMP)",
    "VP30_IMPROVE": "VP≥0.30 + IMP>0.40 (no MDS)",
    "VP30_BASE": "VP≥0.30 only (no MDS, no IMP)",
    "SUPPRESS": "Tier B + VP<0.30",
}

STACK_ORDER = [
    "ELITE_STACK",
    "STRONG_STACK_PLUS",
    "STRONG_STACK",
    "VP30_IMPROVE",
    "VP30_BASE",
    "SUPPRESS",
]


def _sb():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )


def detect_latest_date(sb) -> str:
    """Find the most recent date that has verdicts in velo_verdicts."""
    rows = (
        sb.table("velo_verdicts")
        .select("generated_at")
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise ValueError("No verdicts found in velo_verdicts table.")
    return rows[0]["generated_at"][:10]


def load_verdicts(sb, date_str: str) -> list[dict]:
    """Load all verdicts for a given date from velo_verdicts."""
    rows = (
        sb.table("velo_verdicts")
        .select(
            "race_id,decision_tier,velo_prime_prob,market_deception_score,"
            "improvement_score,place_prob,full_analysis,execution_allowed,generated_at"
        )
        .gte("generated_at", f"{date_str}T00:00:00")
        .lt("generated_at", f"{date_str}T23:59:59")
        .order("velo_prime_prob", desc=True)
        .execute()
        .data
    )
    return rows


def extract_top_runner(verdict: dict) -> dict:
    """Pull horse/horse_id/scores from the top prediction in full_analysis."""
    fa = verdict.get("full_analysis") or []
    if isinstance(fa, dict):
        preds = fa.get("predictions")
        if isinstance(preds, list) and preds and isinstance(preds[0], dict):
            return preds[0]
        fa = list(fa.values())
    if isinstance(fa, list) and fa:
        if isinstance(fa[0], dict):
            return fa[0]
        if isinstance(fa[0], list) and fa[0] and isinstance(fa[0][0], dict):
            return fa[0][0]
    return {}


def classify_runner(v: dict, meta) -> dict:
    """
    Build a complete runner entry with stack membership.

    Uses thresholds imported directly from place_signal_classifier.py:
      VP30_T         = 0.30
      MDS_HIGH_T     = 0.50   (strict > used for MDS_HIGH)
      IMPROVE_HIGH_T = 0.40   (strict > used for IMP_HIGH)
    """
    top = extract_top_runner(v)

    vp   = float(v.get("velo_prime_prob") or top.get("velo_prime_prob") or 0)
    mds  = float(v.get("market_deception_score") or top.get("market_deception_score") or 0)
    imp  = float(v.get("improvement_score") or top.get("improvement_score") or 0)
    pp   = float(v.get("place_prob") or top.get("place_prob") or 0)
    tier = str(v.get("decision_tier") or "").strip().upper()

    vp30     = vp  >= VP30_T           # >= 0.30
    mds_high = mds >  MDS_HIGH_T       # >  0.50
    imp_high = imp >  IMPROVE_HIGH_T   # >  0.40
    tier_a   = tier == "A"
    tier_b   = tier == "B"

    # ── Badges ────────────────────────────────────────────────────────
    badges: list[str] = []
    if tier_a:  badges.append("TIER_A")
    if vp30:    badges.append("VP30")
    if mds_high: badges.append("MDS_HIGH")
    if imp_high: badges.append("IMP_HIGH")

    # ── Stack membership (runner can appear in multiple stacks) ───────
    stacks: list[str] = []

    # ELITE_STACK: Tier A + VP30 + MDS
    if tier_a and vp30 and mds_high:
        stacks.append("ELITE_STACK")

    # STRONG_STACK_PLUS: VP30 + MDS + IMPROVE
    if vp30 and mds_high and imp_high:
        stacks.append("STRONG_STACK_PLUS")

    # STRONG_STACK: VP30 + MDS (and NOT IMPROVE — separate from PLUS)
    if vp30 and mds_high and not imp_high:
        stacks.append("STRONG_STACK")

    # VP30_IMPROVE: VP30 + IMPROVE (and NOT MDS)
    if vp30 and imp_high and not mds_high:
        stacks.append("VP30_IMPROVE")

    # VP30_BASE: VP30 only (no MDS, no IMPROVE)
    if vp30 and not mds_high and not imp_high:
        stacks.append("VP30_BASE")

    # SUPPRESS: Tier B + VP < 0.30
    if tier_b and not vp30:
        stacks.append("SUPPRESS")

    # ── Race metadata ─────────────────────────────────────────────────
    course    = meta.course    if meta and meta.course    else (top.get("course") or "—")
    off_time  = meta.off_time  if meta and meta.off_time  else (top.get("off_time") or "—")
    race_name = meta.race_name if meta and meta.race_name else (top.get("race_name") or "")

    metadata_complete = bool(course and course != "—" and off_time and off_time != "—")

    # candidate_execution_allowed: use execution_allowed from verdict as proxy
    exec_allowed = bool(v.get("execution_allowed"))

    return {
        "race_id":                v.get("race_id", ""),
        "horse":                  top.get("horse") or "?",
        "horse_id":               top.get("horse_id") or "",
        "course":                 course,
        "off_time":               off_time,
        "race_name":              race_name,
        "metadata_complete":      metadata_complete,
        "missing_metadata":       not metadata_complete,
        "tier":                   tier,
        "velo_prime_prob":        round(vp, 4),
        "market_deception_score": round(mds, 4),
        "improvement_score":      round(imp, 4),
        "place_prob":             round(pp, 4),
        "stack_badges":           badges,
        "stacks":                 stacks,
        "candidate_execution_allowed": exec_allowed,
        "status": "OPERATOR_VISIBILITY_ONLY",
    }


def _dedupe_alias_runners(runners: list[dict]) -> list[dict]:
    """Collapse duplicate race identities while preferring resolved RP metadata."""
    deduped: dict[tuple[str, str], dict] = {}
    for runner in runners:
        horse_key = str(runner.get("horse_id") or runner.get("horse") or "").strip().upper()
        date_key = str(runner.get("date") or "")
        key = (date_key, horse_key)
        if not horse_key:
            key = (date_key, str(runner.get("race_id") or ""))

        current = deduped.get(key)
        if current is None:
            deduped[key] = runner
            continue

        def _metadata_score(row: dict) -> int:
            return sum(
                bool(row.get(field) and row.get(field) != "—")
                for field in ("course", "off_time", "race_name")
            )

        if _metadata_score(runner) > _metadata_score(current):
            deduped[key] = runner
    return list(deduped.values())


def build_card(date_str: str) -> dict:
    """Build the full operator card for a given date."""
    sb = _sb()
    verdicts = load_verdicts(sb, date_str)
    if not verdicts:
        raise ValueError(f"No verdicts found for {date_str}")

    # Build metadata resolver once for the batch
    resolver = RaceMetadataResolver(date=date_str, sb_client=sb)

    # Classify each runner
    runners: list[dict] = []
    for v in verdicts:
        meta = resolver.resolve(v.get("race_id", ""))
        runner = classify_runner(v, meta)
        runners.append(runner)
    runners = _dedupe_alias_runners(runners)

    # ── Sort each stack by off_time (chronological) ───────────────────
    def _to_minutes(t_str: str) -> int:
        if not t_str or t_str == "—": return 9999
        try:
            # Handle HH:MM
            p = t_str.split(":")
            return int(p[0]) * 60 + int(p[1])
        except Exception:
            return 9999

    stacks: dict[str, list[dict]] = {k: [] for k in STACK_ORDER}
    for runner in runners:
        for stack in runner["stacks"]:
            if stack in stacks:
                stacks[stack].append(runner)

    for stack in STACK_ORDER:
        stacks[stack].sort(key=lambda r: (_to_minutes(r["off_time"]), r["course"], -r["velo_prime_prob"]))

    # ── Counts ─────────────────────────────────────────────────────────
    vp30_count = sum(1 for r in runners if "VP30" in r["stack_badges"])
    metadata_complete_count = sum(1 for r in runners if r["metadata_complete"])
    metadata_coverage = metadata_complete_count / len(runners) if runners else 0.0
    counts = {
        "total_races": len(runners),
        "metadata_complete_count": metadata_complete_count,
        "metadata_missing_count": len(runners) - metadata_complete_count,
        "metadata_coverage": metadata_coverage,
        "vp30_count": vp30_count,
        "elite_stack_count":       len(stacks["ELITE_STACK"]),
        "strong_stack_plus_count": len(stacks["STRONG_STACK_PLUS"]),
        "strong_stack_count":      len(stacks["STRONG_STACK"]),
        "vp30_improve_count":      len(stacks["VP30_IMPROVE"]),
        "vp30_base_count":         len(stacks["VP30_BASE"]),
        "suppress_count":          len(stacks["SUPPRESS"]),
    }

    card = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OPERATOR_VISIBILITY_ONLY",
        "thresholds": {
            "vp30":         VP30_T,
            "mds_high":     MDS_HIGH_T,
            "improve_high": IMPROVE_HIGH_T,
        },
        "threshold_source": "place_signal_classifier.py",
        "stacks": stacks,
        "counts": counts,
        "metadata_audit": {
            "metadata_coverage": metadata_coverage,
            "metadata_complete_count": metadata_complete_count,
            "metadata_missing_count": len(runners) - metadata_complete_count,
        },
        "disclaimer": DISCLAIMER,
    }
    return card


def build_markdown(card: dict) -> str:
    """Render the operator card as Markdown."""
    date_str = card["date"]
    counts   = card["counts"]
    stacks   = card["stacks"]
    thresh   = card["thresholds"]

    lines = [
        f"# SIDECAR STACK OPERATOR CARD — {date_str}",
        "",
        "```",
        "STATUS:             OPERATOR_VISIBILITY_ONLY",
        "SCORING_CHANGES:    NO",
        "MODEL_CHANGES:      NO",
        "SQPE_CHANGES:       NO",
        "ROUTER_CHANGES:     NO",
        "STAKING:            NO",
        "LIVE_EXECUTION:     NO",
        "TELEGRAM_ALERTS:    NO",
        "PURPOSE:            Sidecar stack operator intelligence panel",
        "```",
        "",
        "---",
        "",
        "## THRESHOLDS",
        "",
        f"| Threshold | Value | Source |",
        f"|---|---:|---|",
        f"| VP30 (velo_prime_prob >=) | {thresh['vp30']:.2f} | place_signal_classifier.py |",
        f"| MDS_HIGH (market_deception_score >) | {thresh['mds_high']:.2f} | place_signal_classifier.py |",
        f"| IMPROVE_HIGH (improvement_score >) | {thresh['improve_high']:.2f} | place_signal_classifier.py |",
        "",
        "---",
        "",
        "## STACK SUMMARY",
        "",
        f"| Stack | Definition | Count |",
        f"|---|---|---:|",
    ]
    for stack in STACK_ORDER:
        n   = len(stacks.get(stack, []))
        defn = STACK_DEFS.get(stack, "")
        lines.append(f"| {stack} | {defn} | {n} |")

    lines += [
        "",
        f"**Total races scanned:** {counts['total_races']}  ",
        f"**VP30 selections:** {counts['vp30_count']}",
        "",
        "---",
        "",
    ]

    # ── Sections A–F ─────────────────────────────────────────────────
    section_labels = {
        "ELITE_STACK":       ("A", "ELITE STACK — Tier A + VP30 + MDS"),
        "STRONG_STACK_PLUS": ("B", "STRONG STACK PLUS — VP30 + MDS + IMP"),
        "STRONG_STACK":      ("C", "STRONG STACK — VP30 + MDS"),
        "VP30_IMPROVE":      ("D", "VP30 + IMPROVE — VP30 + IMP (no MDS)"),
        "VP30_BASE":         ("E", "VP30 BASE — VP30 only"),
        "SUPPRESS":          ("F", "SUPPRESS — Tier B + VP<0.30"),
    }

    TABLE_HEADER = "| Time | Course | Race | Horse | Tier | VP | MDS | IMP | PlaceP | Badges |"
    TABLE_DIV    = "|---|---|---|---|---|---:|---:|---:|---:|---|"

    for stack in STACK_ORDER:
        letter, heading = section_labels[stack]
        rows = stacks.get(stack, [])
        lines.append(f"## {letter}. {heading} ({len(rows)})")
        lines.append("")

        if not rows:
            lines.append(f"*No signals for this stack today.*")
            lines.append("")
            continue

        lines.append(TABLE_HEADER)
        lines.append(TABLE_DIV)

        for r in rows:
            badges_str = " ".join(r["stack_badges"])
            lines.append(
                f"| {r['off_time']} "
                f"| {r['course']} "
                f"| {r['race_name'][:35] if r['race_name'] else '—'} "
                f"| **{r['horse']}** "
                f"| {r['tier']} "
                f"| {r['velo_prime_prob']:.3f} "
                f"| {r['market_deception_score']:.3f} "
                f"| {r['improvement_score']:.3f} "
                f"| {r['place_prob']:.3f} "
                f"| {badges_str} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "**No scoring changes. No model changes. No SQPE changes. No router changes. "
        "No staking. No live execution. No Telegram betting alerts.**",
        "",
        f"*Generated: {card['generated_at']}*",
        "",
        f"*{DISCLAIMER}*",
    ]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sidecar stack operator card")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: latest available)")
    args = parser.parse_args()

    sb = _sb()

    if args.date:
        date_str = args.date
        print(f"SIDECAR STACK OPERATOR CARD — {date_str}")
    else:
        date_str = detect_latest_date(sb)
        print(f"SIDECAR STACK OPERATOR CARD — auto-detected date: {date_str}")

    print("=" * 60)

    try:
        card = build_card(date_str)
    except ValueError as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    counts = card["counts"]

    # ── Write data/sidecar_stack_operator_card_YYYY_MM_DD.json ────────
    DATA.mkdir(exist_ok=True)
    json_out = DATA / f"sidecar_stack_operator_card_{date_str.replace('-', '_')}.json"
    json_out.write_text(json.dumps(card, indent=2, default=str), encoding="utf-8")
    print(f"JSON:     {json_out}")

    # ── Write data/sidecar_stack_operator_card_YYYY_MM_DD.md ─────────
    md = build_markdown(card)
    md_out = DATA / f"sidecar_stack_operator_card_{date_str.replace('-', '_')}.md"
    md_out.write_text(md, encoding="utf-8")
    print(f"Markdown: {md_out}")

    # ── Write app/static/dashboard/sidecar_stack_latest.json ─────────
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    dash_out = DASHBOARD / "sidecar_stack_latest.json"
    dash_out.write_text(json.dumps(card, indent=2, default=str), encoding="utf-8")
    print(f"Dashboard:{dash_out}")

    print()
    print("COUNTS:")
    print(f"  Total races scanned:    {counts['total_races']}")
    print(f"  VP30 count:             {counts['vp30_count']}")
    print(f"  ELITE_STACK:            {counts['elite_stack_count']}")
    print(f"  STRONG_STACK_PLUS:      {counts['strong_stack_plus_count']}")
    print(f"  STRONG_STACK:           {counts['strong_stack_count']}")
    print(f"  VP30_IMPROVE:           {counts['vp30_improve_count']}")
    print(f"  VP30_BASE:              {counts['vp30_base_count']}")
    print(f"  SUPPRESS:               {counts['suppress_count']}")

    print()
    print("THRESHOLDS (from place_signal_classifier.py):")
    t = card["thresholds"]
    print(f"  VP30_T         = {t['vp30']}")
    print(f"  MDS_HIGH_T     = {t['mds_high']}")
    print(f"  IMPROVE_HIGH_T = {t['improve_high']}")

    print()
    print("STACK SAMPLE (ELITE + STRONG first):")
    for stack in ["ELITE_STACK", "STRONG_STACK_PLUS", "STRONG_STACK"]:
        rows = card["stacks"].get(stack, [])
        for r in rows[:3]:
            print(
                f"  [{stack}] {r['off_time']} {r['course']:15s} "
                f"{r['horse']:25s} T={r['tier']} "
                f"VP={r['velo_prime_prob']:.3f} MDS={r['market_deception_score']:.3f} "
                f"IMP={r['improvement_score']:.3f} | badges={r['stack_badges']}"
            )

    print()
    print("CONFIRMATION: No scoring/model/SQPE/router/staking/Telegram/live execution changed.")
    print("STATUS: OPERATOR_VISIBILITY_ONLY")


if __name__ == "__main__":
    main()
