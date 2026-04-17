"""
VÉLØ VOX — Briefing Agent

Generates a full race-card intelligence briefing in Carlisle format.

Architecture (3 layers, strict order):
  1. Evidence: deterministic intelligence (rpdc_rules + Racing API + Supabase)
  2. Synthesis: MiniMax via OpenRouter fills the RIGID template — narration only
  3. Output: markdown briefing written to reports/briefings/<date>_<venue>.md

LLM role: NARRATE deterministic facts. Never classify. Never invent.

CLI usage:
    python workers/velo_vox/velo_vox_agent.py --race-id 856450
    python workers/velo_vox/velo_vox_agent.py --race-id 856450 --dry-run
    python workers/velo_vox/velo_vox_agent.py --card YRKE --date 2026-03-21
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workers.velo_vox.evidence_builder import build_race_evidence
from workers.velo_vox.providers.openrouter_client import OpenRouterClient

_TEMPLATE_DIR  = Path(__file__).parent / "templates"
_SYSTEM_PROMPT = (_TEMPLATE_DIR / "vox_system_prompt.txt").read_text()

_REPORTS_DIR = Path(__file__).parent.parent.parent / "reports" / "briefings"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Evidence → user prompt ────────────────────────────────────────────────────

def _format_evidence_for_prompt(evidence: dict) -> str:
    """
    Serialise the evidence packet into a structured block for the model.
    Keeps it dense but unambiguous — the model reads this, not the user.
    """
    race = evidence["race"]
    runners = evidence["runners"]

    lines = [
        "## EVIDENCE PACKET",
        "",
        "### RACE METADATA",
        f"- Venue: {race['venue']}",
        f"- Date: {race['date']}",
        f"- Time: {race['time']}",
        f"- Race: {race['race_name']}",
        f"- Class: {race['class']}",
        f"- Distance: {race['distance']}",
        f"- Going: {race['going']}",
        f"- Prize: {race['prize']}",
        f"- Type: {race['type']}",
        f"- Field: {race['num_runners']} runners",
        "",
        "### RUNNERS (deterministic RPD-C tags — DO NOT RECLASSIFY)",
    ]

    for r in runners:
        lines.append("")
        lines.append(f"**{r['number']}. {r['name']}**")
        lines.append(f"  - Trainer: {r['trainer']}  (RTF: {r['trainer_rtf']}  |  14d: {r['trainer_14d_wins']}/{r['trainer_14d_runs']} {r['trainer_14d_pct']}%)")
        lines.append(f"  - Jockey: {r['jockey']}")
        lines.append(f"  - Age: {r['age']}  |  Weight: {r['weight_lbs']}lbs  |  Draw: {r['draw']}  |  Headgear: {r['headgear'] or 'none'}")
        lines.append(f"  - Form: {r['form']}  |  OR: {r['or_rating']}  |  RPR: {r['rpr']}  |  TS: {r['ts']}")
        lines.append(f"  - Days since last run: {r['days_since_last_run']}")
        lines.append(f"  - Past results flags: {', '.join(r['past_results_flags']) if r['past_results_flags'] else 'none'}")
        if r["spotlight"]:
            lines.append(f"  - Spotlight: {r['spotlight']}")
        # RPD-C — intelligence stack tag, override, and trend history
        rpdc_ev = r["rpdc_evidence"]
        if isinstance(rpdc_ev, list):
            ev_str = ", ".join(str(e) for e in rpdc_ev) if rpdc_ev else "none"
        else:
            ev_str = str(rpdc_ev) if rpdc_ev else "none"

        lines.append(f"  - **RPD-C: {r['rpdc_tag_base']} ({r['rpdc_confidence']})** — source: {r['rpdc_source']}")
        lines.append(f"  - RPD-C evidence: {ev_str}")
        if r.get("rpdc_override_tag"):
            lines.append(f"  - ⚠️ OPERATOR OVERRIDE: {r['rpdc_override_tag']} — reason: {r.get('rpdc_override_reason','')}")
        if r.get("rpdc_explanation"):
            lines.append(f"  - RPD-C explanation: {r['rpdc_explanation']}")
        if r.get("rpdc_history"):
            hist_parts = []
            for h in r["rpdc_history"]:
                ev_h = h.get("rpdc_evidence_json") or []
                ev_h_str = ", ".join(str(e) for e in ev_h) if ev_h else ""
                hist_parts.append(f"{h.get('date','')}:{h.get('rpdc_tag_base','')}({h.get('rpdc_confidence','')}){' ['+ev_h_str+']' if ev_h_str else ''}")
            lines.append(f"  - RPD-C history: {' | '.join(hist_parts)}")

    lines += [
        "",
        "---",
        "",
        "## YOUR TASK",
        "Using ONLY the evidence above, produce the complete race briefing in the VÉLØ VOX format.",
        "- Reproduce RPD-C tags exactly as shown. Do not change them.",
        "- Fill every section of the template (Race Context, Pace Shape, Intent Layer, Form Integrity, Bias, Market, Threat Matrix, Scenarios, Conviction).",
        "- Threat Matrix: only activate (⚠️/🔴) when evidence supports it.",
        "- Conviction Output must include Top Strike, Value, Danger, and Confidence Band.",
        "- End with: *Information only — independent decision required.*",
    ]

    return "\n".join(lines)


# ── Main briefing generation ──────────────────────────────────────────────────

def generate_briefing(race_id: str, dry_run: bool = False) -> str:
    """
    Build evidence + call MiniMax + return briefing markdown string.
    If dry_run=True, skip the LLM call and return the formatted evidence only.
    """
    evidence = build_race_evidence(race_id)

    race = evidence["race"]
    venue_slug = race["venue"].lower().replace(" ", "_")
    date_str   = race["date"] or str(date.today())

    user_prompt = _format_evidence_for_prompt(evidence)

    if dry_run:
        print("[VOX] DRY RUN — evidence packet only (no LLM call)")
        return user_prompt

    print(f"[VOX] Calling MiniMax via OpenRouter for {race['race_name']}...")
    client = OpenRouterClient()
    briefing = client.chat(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=4096,
        temperature=0.25,
    )

    return briefing


def generate_card_briefing(course_id: str, race_date: str, dry_run: bool = False) -> str:
    """
    Generate a full-card briefing for all races at a venue on a date.
    Fetches race IDs from the Racing API, then generates per-race + summary.
    """
    import requests as _req

    rapi_user = os.getenv("RACING_API_USERNAME", "")
    rapi_pass = os.getenv("RACING_API_PASSWORD", "")
    rapi_base = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")

    print(f"[VOX] Fetching race list for course={course_id} date={race_date}")
    r = _req.get(
        f"{rapi_base}/racecards",
        auth=(rapi_user, rapi_pass),
        params={"region_codes": course_id, "date": race_date},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    races = data if isinstance(data, list) else data.get("racecards", [])
    if not races:
        return f"No races found for course={course_id} date={race_date}"

    briefings = []
    for race in races:
        race_id = race.get("race_id") or race.get("id")
        if not race_id:
            continue
        print(f"  [VOX] Race {race_id} — {race.get('off_time','')} {race.get('race_name','')}")
        try:
            b = generate_briefing(str(race_id), dry_run=dry_run)
            briefings.append(b)
        except Exception as e:
            briefings.append(f"*[VOX ERROR for race {race_id}: {e}]*")

    venue_name = races[0].get("course", course_id)
    header = (
        f"# VÉLØ PRIME — ORACLE INTELLIGENCE BRIEFING\n"
        f"## {venue_name} | {race_date} | {len(races)}-Race Card\n\n"
        f"**Classification**: Full-Spectrum Strategic Analysis\n\n"
        f"---\n\n"
    )
    return header + "\n\n---\n\n".join(briefings)


# ── Persistence ───────────────────────────────────────────────────────────────

def save_briefing(briefing: str, filename: str) -> Path:
    out = _REPORTS_DIR / filename
    out.write_text(briefing, encoding="utf-8")
    print(f"[VOX] Briefing saved → {out}")
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VÉLØ VOX Briefing Agent")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--race-id", help="Single race ID")
    group.add_argument("--card",    help="Course code for full card (use with --date)")
    parser.add_argument("--date",     default=str(date.today()), help="Race date YYYY-MM-DD")
    parser.add_argument("--dry-run",  action="store_true", help="Skip LLM — show evidence packet only")
    parser.add_argument("--no-save",  action="store_true", help="Print to stdout, do not save file")
    args = parser.parse_args()

    if args.race_id:
        briefing = generate_briefing(args.race_id, dry_run=args.dry_run)
        filename = f"{args.date}_race_{args.race_id}.md"
    else:
        briefing = generate_card_briefing(args.card, args.date, dry_run=args.dry_run)
        filename = f"{args.date}_{args.card.lower()}_card.md"

    if args.no_save:
        print(briefing)
    else:
        save_briefing(briefing, filename)
        print(briefing)


if __name__ == "__main__":
    main()
