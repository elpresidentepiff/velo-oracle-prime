"""
Runner Notes Parser — Stewards Reports / Post-Race Explanations
===============================================================
Parses two distinct signal families from RP post-race text:
  1. NDS_FADE tags — "why they ran badly" (bled, lame, hampered, etc.), from
     comment_intel_score already in velo_prime_verdicts (existing, live).
  2. TRAINER_INTENT tags — "why the yard ran it at all" (schooling/educational
     run, needed the run, not fully tried), from RP's per-horse in-running
     comment on the raceday RESULTS page. This is internal, rule-based
     classification — no external NLP/sentiment service — precisely so it can
     be audited and extended the same way NDS_FADE is.

DATA SOURCE STATUS:
  comment_intel_score: LIVE — already in verdict pipeline via NDS/chain layers
  RP in-running comment: LIVE (2026-07-10) — parse_rp_results_capture.py
    extracts it into runner["in_running_comment"], persisted to Supabase
    racing_horse_runs.in_running_comment via ingest_results_to_horse_runs.py.

To extend either vocabulary: add a regex → tag entry below. Internal tags
only — never call an external classification/LLM service for this.

Output:
  data/runner_notes_YYYY_MM_DD.json  — per-horse explanations + intent tags
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

# RP in-running comment keywords → TRAINER_INTENT tags.
# These describe deliberate yard intent (schooling / not fully tried / needed
# the run) rather than misfortune — a distinct family from FADE_PATTERNS.
TRAINER_INTENT_PATTERNS: dict[str, str] = {
    r"\beducational\b|\bschooling\b": "EDUCATIONAL_RUN",
    r"\bin need of (the |this )?run\b|\bunderdone\b|\bneeded the run\b"
    r"|\bwill (come on|improve|do better) for (this|the run)\b": "NEEDED_THE_RUN",
    r"\bvalue of (the )?experience\b|\bfor experience\b|\bgaining experience\b"
    r"|\bexperience gained\b": "EXPERIENCE_RUN",
    r"\bnever (knocked about|off the bit|asked (for effort|to go quicker))\b"
    r"|\beased down without (an )?(argument|being (knocked about|asked))\b"
    r"|\bnot (knocked about|fully tried|extended|fully tested)\b": "NOT_FULLY_TRIED",
    r"\beased\b.{0,25}\b(once|when)\b.{0,15}\b(beaten|held|no chance|no impression)\b": "EASED_WHEN_BEATEN",
    r"\bjockey said\b|\btrainer said\b": "CONNECTIONS_QUOTE_PRESENT",
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


def parse_intent_text(text: str) -> list[str]:
    """Extract TRAINER_INTENT tags from an RP in-running comment."""
    text_lower = text.lower()
    tags = []
    for pattern, tag in TRAINER_INTENT_PATTERNS.items():
        if re.search(pattern, text_lower):
            tags.append(tag)
    return tags


def parse_from_results_json(results_path: Path) -> list[dict[str, Any]]:
    """Extract TRAINER_INTENT tags from RP in-running comments in a parsed
    results file (data/results/rp_results_YYYY_MM_DD.json)."""
    if not results_path.exists():
        return []
    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    rows = []
    for race in data.get("results", []):
        race_id = race.get("race_id")
        for runner in race.get("runners", []):
            comment = runner.get("in_running_comment") or ""
            if not comment:
                continue
            rows.append({
                "race_id": race_id,
                "horse": runner.get("horse"),
                "horse_rp_uid": runner.get("horse_rp_uid"),
                "in_running_comment": comment,
                "intent_tags": parse_intent_text(comment),
                "source": "rp_results_comment",
            })
    return rows


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
    results_path = DATA / "results" / f"rp_results_{date_slug}.json"

    fade_rows = parse_from_verdict_json(verdict_path)
    intent_rows = parse_from_results_json(results_path)

    result = {
        "date": today,
        "generated_at": _utc_now(),
        "source": "verdict_json_comment_intel + rp_results_comment",
        "status": "OK" if (fade_rows or intent_rows) else "NO_INPUT_FILES",
        "fade_rows": len(fade_rows),
        "fade_count": sum(1 for r in fade_rows if r["fade_tags"]),
        "intent_rows": len(intent_rows),
        "intent_tag_count": sum(1 for r in intent_rows if r["intent_tags"]),
        "notes": fade_rows,
        "trainer_intent": intent_rows,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
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
    print(f"Status: {r['status']}  fade_rows={r['fade_rows']} fades={r['fade_count']}"
          f"  intent_rows={r['intent_rows']} intent_tags={r['intent_tag_count']}")
