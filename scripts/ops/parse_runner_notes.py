"""
Runner Notes Parser — Stewards Reports / Post-Race Explanations
===============================================================
Parses "why they ran badly" signals from:
  1. comment_intel_score already in velo_prime_verdicts (existing, live)
  2. RP race result pages — stewards inquiry notes, official explanations (stub)

DATA SOURCE STATUS:
  comment_intel_score: LIVE — already in verdict pipeline via NDS/chain layers
  RP stewards reports: NOT YET SCRAPED — requires RP result page capture
    → Run `scripts/ops/capture_rp_results.py` first to get result pages
    → Then look for 'Explanation' / 'Stewards' sections in HTML
    → Tags to emit: BLED, LAME, UNSEAT, INTERFERENCE, HAMPERED, NEVER_DANGEROUS

To extend: add RP result page HTML → parse_stewards_section() → RPDC NDS_FADE tags.

Output:
  data/runner_notes_YYYY_MM_DD.json  — per-horse explanations
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Stewards report keywords → NDS_FADE tags
FADE_PATTERNS: dict[str, str] = {
    r"\bbled\b": "BLED",
    r"\blame\b|\binjur": "LAME",
    r"\bunseat\b": "UNSEAT",
    r"\binterfer": "INTERFERENCE",
    r"\bhamper": "HAMPERED",
    r"\bnever danger": "NEVER_DANGEROUS",
    r"\blost.{0,15}action\b": "LOST_ACTION",
    r"\bslip\b|\bfall\b": "FELL",
    r"\brefuse": "REFUSED",
    r"\bbehind.{0,20}gate\b": "SLOW_START",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_explanation_text(text: str) -> list[str]:
    """Extract NDS_FADE tags from a free-text stewards explanation."""
    text_lower = text.lower()
    tags = []
    for pattern, tag in FADE_PATTERNS.items():
        if re.search(pattern, text_lower):
            tags.append(tag)
    return tags


def parse_from_verdict_json(verdict_path: Path) -> list[dict[str, Any]]:
    """Extract existing comment_intel signals from a local verdict JSON."""
    if not verdict_path.exists():
        return []
    try:
        verdicts = json.loads(verdict_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    rows = []
    for v in verdicts:
        top = v.get("top") or {}
        horse = top.get("horse") or v.get("horse")
        race_id = v.get("race_id") or top.get("race_id")
        comment_score = top.get("comment_intel_score")
        nds_narrative = top.get("nds_narrative")
        nds_is_fade = top.get("nds_is_fade")

        if not horse:
            continue

        fade_tags = []
        if nds_narrative:
            fade_tags = parse_explanation_text(nds_narrative)
        if nds_is_fade:
            if "NDS_FADE" not in fade_tags:
                fade_tags.append("NDS_FADE")

        rows.append({
            "race_id": race_id,
            "horse": horse,
            "comment_intel_score": comment_score,
            "nds_narrative": nds_narrative,
            "nds_is_fade": nds_is_fade,
            "fade_tags": fade_tags,
            "source": "verdict_json",
        })
    return rows


def run(today: str | None = None) -> dict[str, Any]:
    today = today or date.today().isoformat()
    date_slug = today.replace("-", "_")
    verdict_path = DATA / f"velo_prime_verdicts_{date_slug}.json"

    rows = parse_from_verdict_json(verdict_path)

    result = {
        "date": today,
        "generated_at": _utc_now(),
        "source": "verdict_json_comment_intel",
        "status": "OK" if rows else "NO_VERDICT_FILE",
        "rows": len(rows),
        "fade_count": sum(1 for r in rows if r["fade_tags"]),
        "notes": rows,
        "todo": (
            "RP stewards report scraping not yet implemented. "
            "Add RP result page HTML → parse_stewards_section() to extend NDS_FADE tags."
        ),
    }

    out_path = DATA / f"runner_notes_{date_slug}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    r = run(args.date)
    print(f"Status: {r['status']}  rows={r['rows']}  fades={r['fade_count']}")
    print(f"TODO: {r['todo']}")
