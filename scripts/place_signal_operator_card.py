"""
Place Signal Operator Card
===========================

Generates a daily operator card showing VÉLØ place-market intelligence.

This is LIVE OPERATOR VISIBILITY — not staking, not betting instruction,
not Betfair execution.

Usage:
    python scripts/place_signal_operator_card.py --date 2026-05-01

Outputs:
    data/place_signal_operator_card_YYYY_MM_DD.md

Read-only. No scoring, model, router, or staking changes.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from src.velo.place_signal_classifier import classify_from_verdict, PlaceSignal

load_dotenv(ROOT / ".env")
DATA = ROOT / "data"

STATUS_ORDER = [
    "LIVE_OPERATOR_PLACE_SIGNAL",
    "LIVE_OPERATOR_PLACE_WATCH",
    "BASE_PLACE_TRUST",
    "NO_SIGNAL",
    "SUPPRESS",
]

LABEL_HEADER = {
    "ELITE_PLACE_STACK":        "ELITE PLACE SIGNALS",
    "STRONG_PLACE_STACK_PLUS":  "STRONG PLACE SIGNALS (TRIPLE CONFLUENCE)",
    "STRONG_PLACE_STACK":       "STRONG PLACE SIGNALS",
    "IMPROVE_PLACE_WATCH":      "IMPROVE PLACE WATCH",
    "PLACE_SUPPORT_WATCH":      "PLACE SUPPORT WATCH",
    "BASE_PLACE_TRUST":         "BASE PLACE TRUST",
    "SUPPRESS":                 "SUPPRESS",
    "BELOW_VP30":               "BELOW VP30 — NO SIGNAL",
}

LABEL_ORDER = [
    "ELITE_PLACE_STACK",
    "STRONG_PLACE_STACK_PLUS",
    "STRONG_PLACE_STACK",
    "IMPROVE_PLACE_WATCH",
    "PLACE_SUPPORT_WATCH",
    "BASE_PLACE_TRUST",
    "SUPPRESS",
    "BELOW_VP30",
]


def _sb():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )


def load_verdicts(date_str: str) -> list[dict]:
    sb = _sb()
    rows = (
        sb.table("velo_verdicts")
        .select(
            "race_id,velo_prime_prob,improvement_score,market_deception_score,"
            "place_prob,decision_tier,full_analysis,generated_at"
        )
        .gte("generated_at", f"{date_str}T00:00:00")
        .lt("generated_at", f"{date_str}T23:59:59")
        .order("velo_prime_prob", desc=True)
        .execute()
        .data
    )
    return rows


def _extract_top(verdict: dict) -> dict:
    fa = verdict.get("full_analysis") or []
    if isinstance(fa, dict):
        fa = list(fa.values())
    return fa[0] if (fa and isinstance(fa[0], dict)) else {}


def build_card(date_str: str) -> tuple[str, dict]:
    """Returns (markdown_text, counts_dict)."""
    verdicts = load_verdicts(date_str)
    if not verdicts:
        raise ValueError(f"No verdicts found for {date_str}")

    # Classify each
    classified: list[tuple[dict, PlaceSignal]] = []
    missing_meta: list[str] = []

    for v in verdicts:
        top = _extract_top(v)
        horse = top.get("horse") or "?"
        race_id = v.get("race_id", "?")
        course = top.get("course") or top.get("venue") or "?"
        off_time = top.get("off_time") or "?"
        race_name = top.get("race_name") or ""

        sig = classify_from_verdict(v)

        # Merge display fields
        row = {
            "race_id": race_id,
            "horse": horse,
            "course": course,
            "off_time": off_time,
            "race_name": race_name,
            "vp": float(v.get("velo_prime_prob") or 0),
            "tier": v.get("decision_tier") or "?",
            "mds": float(v.get("market_deception_score") or 0),
            "imp": float(v.get("improvement_score") or 0),
            "place_p": float(v.get("place_prob") or 0),
            "signal": sig,
        }

        if course == "?" or off_time == "?":
            missing_meta.append(f"{race_id} / {horse}")

        classified.append((row, sig))

    # Group by label
    by_label: dict[str, list] = defaultdict(list)
    for row, sig in classified:
        by_label[sig.place_stack_label].append((row, sig))

    # Sort within each label by VP desc
    for label in by_label:
        by_label[label].sort(key=lambda x: -x[0]["vp"])

    # Counts
    counts = {lbl: len(rows) for lbl, rows in by_label.items()}

    # Build markdown
    lines = [
        f"# PLACE SIGNAL OPERATOR CARD — {date_str}",
        "",
        "```",
        "STATUS:             LIVE_OPERATOR_VISIBILITY_ONLY",
        "STAKING:            NO",
        "LIVE_EXECUTION:     NO",
        "BETFAIR:            NO",
        "PURPOSE:            Place-market operator intelligence",
        "```",
        "",
        "---",
        "",
        "## SIGNAL SUMMARY",
        "",
        "| Stack | Count | Status | Min Place Odds |",
        "|---|---:|---|---:|",
    ]
    for lbl in LABEL_ORDER:
        n = counts.get(lbl, 0)
        if n == 0:
            continue
        first_sig = by_label[lbl][0][1]
        status = first_sig.place_stack_status
        mpo = f"{first_sig.min_place_odds:.2f}" if first_sig.min_place_odds else "—"
        lines.append(f"| {lbl} | {n} | {status} | {mpo} |")

    lines += ["", "---", ""]

    # Detail by section
    for lbl in LABEL_ORDER:
        rows = by_label.get(lbl, [])
        if not rows:
            continue

        header = LABEL_HEADER.get(lbl, lbl)
        lines.append(f"## {header} ({len(rows)})")
        lines.append("")

        if lbl == "SUPPRESS":
            for row, sig in rows:
                lines.append(
                    f"- **{row['horse']}** | {row['course']} {row['off_time']} "
                    f"| VP={row['vp']:.3f} | Tier {row['tier']} "
                    f"| {sig.suppress_reason or 'suppressed'}"
                )
            lines.append("")
            continue

        if lbl == "BELOW_VP30":
            lines.append(f"*{len(rows)} horses below VP30 — no place signal.*")
            lines.append("")
            continue

        for row, sig in rows:
            badges = " ".join(f"[{b}]" for b in sig.badges)
            mpo = f"min odds {sig.min_place_odds:.2f}" if sig.min_place_odds else ""
            lines.append(
                f"| **{row['horse']}** | {row['course']} {row['off_time']} "
                f"| VP={row['vp']:.3f} | MDS={row['mds']:.3f} "
                f"| IMP={row['imp']:.3f} | PLACE={row['place_p']:.3f} "
                f"| Tier {row['tier']} | {badges} | {mpo} |"
            )
        lines.append("")

        # Evidence note once per section
        s = rows[0][1]
        lines.append(
            f"> Evidence: n={s.evidence_n} | Frame={s.evidence_frame_rate*100:.0f}% "
            f"| Win SR={s.evidence_win_sr*100:.0f}% | E/W 1/4 ROI={s.evidence_ew_1_4_roi*100:+.0f}%"
        )
        lines.append("")

    if missing_meta:
        lines += [
            "---",
            "",
            f"## MISSING METADATA ({len(missing_meta)} rows)",
            "",
        ]
        for m in missing_meta:
            lines.append(f"- {m}")
        lines.append("")

    lines += [
        "---",
        "",
        "## PLACE ECONOMICS REFERENCE",
        "",
        "| Stack | Frame | Min Place Odds | E/W 1/4 ROI |",
        "|---|---:|---:|---:|",
        "| ELITE_PLACE_STACK (TierA+VP30+MDS) | 100% | 1.05 | +170% |",
        "| STRONG_PLACE_STACK_PLUS (VP30+MDS+IMP) | 100% | 1.05 | +90% |",
        "| STRONG_PLACE_STACK (VP30+MDS) | 100% | 1.05 | +169% |",
        "| IMPROVE_PLACE_WATCH (VP30+IMP) | 87% | 1.20 | +51% |",
        "| PLACE_SUPPORT_WATCH (VP30+PLACE) | 75% | 1.40 | +59% |",
        "| BASE_PLACE_TRUST (VP30) | 70% | 1.50 | +52% |",
        "| SUPPRESS (B+VP<0.30) | 43% | never | — |",
        "",
        "*Operator must verify actual place odds before any action. These are signals, not instructions.*",
        "",
        "---",
        "",
        "**No scoring changes. No model changes. No staking. No live execution.**",
        "",
        "*PLACE SIGNAL OPERATOR CARD — operator intelligence only.*",
    ]

    return "\n".join(lines), counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Place signal operator card")
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()
    date_str = args.date

    print(f"PLACE SIGNAL OPERATOR CARD — {date_str}")
    print("=" * 50)

    try:
        md, counts = build_card(date_str)
    except ValueError as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    out = DATA / f"place_signal_operator_card_{date_str.replace('-', '_')}.md"
    out.write_text(md, encoding="utf-8")
    print(f"Output: {out}")
    print()
    print("Counts:")
    for lbl in LABEL_ORDER:
        n = counts.get(lbl, 0)
        if n:
            print(f"  {lbl:<30} {n}")

    print()
    print("K. No scoring/model/SQPE/router/staking/live execution changes.")
    print("   LIVE_OPERATOR_VISIBILITY_ONLY.")


if __name__ == "__main__":
    main()
