"""
Racing API Shadow Forward Audit — Phase 5 Evidence Accumulation
================================================================
Reads data/racing_api_shadow_forward_ledger.csv and reports:
  - When no outcomes exist: coverage stats, score distributions, missing-data profile
  - When outcomes exist: top-half vs bottom-half SR/frame/ROI, correlation with won,
    impact inside V2_CLASS4_ONLY lane, freeze/no-freeze recommendation

GOVERNANCE: Read-only. Never alters any live files.

Usage:
    python scripts/racing_api_shadow_forward_audit.py
    python scripts/racing_api_shadow_forward_audit.py --ledger path/to/other.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_LEDGER = ROOT / "data" / "racing_api_shadow_forward_ledger.csv"

SCORE_COLS = [
    "racing_api_connection_shadow_score",
    "racing_api_course_shadow_score",
    "racing_api_distance_shadow_score",
    "racing_api_enrichment_shadow_score",
]
COVERAGE_COLS = [
    "racing_api_connection_coverage",
    "racing_api_course_coverage",
    "racing_api_distance_coverage",
    "racing_api_enrichment_coverage",
]


def _f(v: str) -> float | None:
    try:
        return float(v) if v.strip() not in ("", "None", "null") else None
    except (ValueError, AttributeError):
        return None


def _b(v: str) -> bool | None:
    s = v.strip().lower()
    if s in ("1", "true", "yes"):
        return True
    if s in ("0", "false", "no"):
        return False
    return None


def _has_coverage(row: dict, col: str) -> bool:
    v = row.get(col, "")
    if not v or v.strip() in ("", "None", "null", "[]"):
        return False
    return True


def _corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 5:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


_DEDUP_KEY = ("date", "race_id", "horse_id", "shadow_version")


def _dedup_key(row: dict) -> tuple:
    return tuple(str(row.get(k) or "") for k in _DEDUP_KEY)


def load_ledger(path: Path) -> tuple[list[dict], int]:
    """Return (deduped_rows, raw_row_count).

    Deduplicates by (date, race_id, horse_id, shadow_version).
    Keeps the last occurrence per key so outcome backfills overwrite blanks.
    """
    if not path.exists():
        return [], 0
    with path.open(encoding="utf-8") as f:
        raw = list(csv.DictReader(f))
    raw_count = len(raw)
    seen: dict[tuple, dict] = {}
    for row in raw:
        seen[_dedup_key(row)] = row  # last write wins
    return list(seen.values()), raw_count


def coverage_report(rows: list[dict], raw_count: int) -> str:
    n = len(rows)
    dup_count = raw_count - n
    lines = [
        f"RACING API SHADOW FORWARD AUDIT",
        f"Ledger: {DEFAULT_LEDGER.name}",
        f"Raw rows:    {raw_count}",
        f"Deduped rows:{n}  (removed {dup_count} duplicate{'s' if dup_count != 1 else ''})",
        f"",
        f"── COVERAGE ─────────────────────────────",
    ]
    for col in SCORE_COLS:
        cov = sum(1 for r in rows if _f(r.get(col, "")) is not None)
        lines.append(f"  {col:<45s}  {cov:4d} / {n}  ({100*cov/n:.1f}%)" if n else f"  {col}  0 / 0")

    lines += ["", "── SCORE DISTRIBUTIONS ──────────────────"]
    for col in SCORE_COLS:
        vals = [_f(r.get(col, "")) for r in rows]
        vals = [v for v in vals if v is not None]
        if not vals:
            lines.append(f"  {col:<45s}  no data")
            continue
        mn = min(vals)
        mx = max(vals)
        avg = sum(vals) / len(vals)
        lines.append(f"  {col:<45s}  n={len(vals)}  min={mn:.4f}  max={mx:.4f}  mean={avg:.4f}")

    lines += ["", "── MISSING DATA PROFILE ─────────────────"]
    for col in SCORE_COLS:
        missing = sum(1 for r in rows if _f(r.get(col, "")) is None)
        lines.append(f"  {col:<45s}  {missing:4d} missing ({100*missing/n:.1f}%)" if n else "")

    lines += ["", "── OUTCOME STATUS ───────────────────────"]
    with_outcome = sum(1 for r in rows if _b(r.get("won", "")) is not None)
    lines.append(f"  Rows with outcome recorded: {with_outcome} / {n}")
    if with_outcome == 0:
        lines.append("  NOTE: No outcomes yet — run sigma to backfill result_position/won/placed.")

    return "\n".join(lines)


def outcome_report(rows: list[dict]) -> str:
    outcome_rows = [r for r in rows if _b(r.get("won", "")) is not None]
    n = len(outcome_rows)
    lines = [
        f"RACING API SHADOW FORWARD AUDIT — OUTCOME ANALYSIS",
        f"Rows with outcomes: {n}",
        f"",
    ]

    for score_col in SCORE_COLS:
        scored = [(r, _f(r.get(score_col, "")), _b(r.get("won", ""))) for r in outcome_rows]
        scored = [(r, s, w) for r, s, w in scored if s is not None and w is not None]
        if len(scored) < 10:
            lines.append(f"  {score_col}: insufficient data (n={len(scored)})")
            continue

        scored.sort(key=lambda x: x[1], reverse=True)
        half = len(scored) // 2
        top_half = scored[:half]
        bot_half = scored[half:]

        top_sr = sum(1 for _, _, w in top_half if w) / len(top_half) if top_half else 0
        bot_sr = sum(1 for _, _, w in bot_half if w) / len(bot_half) if bot_half else 0

        # Placed rate
        top_frame = sum(1 for r, _, _ in top_half if _b(r.get("placed", "")) is True) / len(top_half) if top_half else 0
        bot_frame = sum(1 for r, _, _ in bot_half if _b(r.get("placed", "")) is True) / len(bot_half) if bot_half else 0

        # Correlation
        score_vals = [s for _, s, _ in scored]
        won_vals = [float(w) for _, _, w in scored]
        r_val = _corr(score_vals, won_vals)

        lines += [
            f"  {score_col}:",
            f"    n={len(scored)}  top-half SR={top_sr:.3f}  bot-half SR={bot_sr:.3f}  delta={top_sr-bot_sr:+.3f}",
            f"    top-half frame={top_frame:.3f}  bot-half frame={bot_frame:.3f}",
            f"    corr(score, won)={r_val}",
            f"",
        ]

    # V2_CLASS4_ONLY lane impact
    v2_rows = [(r, _b(r.get("won", ""))) for r in outcome_rows if r.get("router_shadow_lane") == "V2_CLASS4_ONLY"]
    if v2_rows:
        v2_n = len(v2_rows)
        v2_sr = sum(1 for _, w in v2_rows if w) / v2_n
        lines += [
            f"  V2_CLASS4_ONLY lane: n={v2_n}  SR={v2_sr:.3f}",
        ]

        enr_col = "racing_api_enrichment_shadow_score"
        v2_scored = [(r, _f(r.get(enr_col, "")), w) for r, w in v2_rows]
        v2_scored = [(r, s, w) for r, s, w in v2_scored if s is not None and w is not None]
        if len(v2_scored) >= 6:
            v2_scored.sort(key=lambda x: x[1], reverse=True)
            h = len(v2_scored) // 2
            v2_top_sr = sum(1 for _, _, w in v2_scored[:h] if w) / h
            v2_bot_sr = sum(1 for _, _, w in v2_scored[h:] if w) / (len(v2_scored) - h)
            lines.append(f"    enrichment score top-half SR={v2_top_sr:.3f}  bot-half SR={v2_bot_sr:.3f}")

    # Freeze recommendation
    lines += ["", "── FREEZE RECOMMENDATION ────────────────"]
    enr_col = "racing_api_enrichment_shadow_score"
    enr_scored = [(r, _f(r.get(enr_col, "")), _b(r.get("won", ""))) for r in outcome_rows]
    enr_scored = [(r, s, w) for r, s, w in enr_scored if s is not None and w is not None]
    if len(enr_scored) < 20:
        lines.append(f"  INSUFFICIENT_SAMPLE (n={len(enr_scored)}) — continue accumulating")
    else:
        enr_scored.sort(key=lambda x: x[1], reverse=True)
        half = len(enr_scored) // 2
        top_sr = sum(1 for _, _, w in enr_scored[:half] if w) / half
        bot_sr = sum(1 for _, _, w in enr_scored[half:] if w) / (len(enr_scored) - half)
        if top_sr > bot_sr + 0.03:
            lines.append(f"  NO_FREEZE — enrichment score discriminating (delta={top_sr-bot_sr:+.3f})")
        elif top_sr < bot_sr - 0.02:
            lines.append(f"  REVIEW — enrichment score inverted (delta={top_sr-bot_sr:+.3f})")
        else:
            lines.append(f"  CONTINUE — enrichment score weak signal so far (delta={top_sr-bot_sr:+.3f})")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Racing API Shadow Forward Audit")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    args = parser.parse_args()

    path = Path(args.ledger)
    rows, raw_count = load_ledger(path)

    if not rows:
        print(f"No ledger found at {path} — run run_prime_today.py first to populate it.")
        return

    with_outcome = sum(1 for r in rows if _b(r.get("won", "")) is not None)

    print(coverage_report(rows, raw_count))
    print()

    if with_outcome >= 5:
        print(outcome_report(rows))
    else:
        print("Outcome analysis skipped — fewer than 5 rows have outcomes recorded.")
        print("After sigma runs populate result_position/won/placed, re-run this script.")


if __name__ == "__main__":
    main()
