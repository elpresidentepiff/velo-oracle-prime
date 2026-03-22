"""
Agent Tools — all callable actions the VOX agent can take.

Each tool returns a clean string result that gets fed back into the agent context.
The agent decides which tool to call based on the conversation.
"""
import os
import sys
import json
import requests
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_RAPI_USER = os.getenv("RACING_API_USERNAME", "")
_RAPI_PASS = os.getenv("RACING_API_PASSWORD", "")
_RAPI_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")
_SB_TOKEN  = os.getenv("SUPABASE_ACCESS_TOKEN", "")
_SB_REF    = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]


def _rapi(endpoint: str, params: dict | None = None) -> dict | list:
    r = requests.get(
        f"{_RAPI_BASE}/{endpoint.lstrip('/')}",
        auth=(_RAPI_USER, _RAPI_PASS),
        params=params or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _sql(query: str) -> list:
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{_SB_REF}/database/query",
        headers={"Authorization": f"Bearer {_SB_TOKEN}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=30,
    )
    result = r.json()
    if isinstance(result, dict) and "message" in result:
        raise ValueError(result["message"])
    return result


# ── Tool 1: List today's races ────────────────────────────────────────────────

def list_todays_races(venue_filter: str = "") -> str:
    """Returns today's races grouped by venue. Optionally filtered."""
    data = _rapi("racecards")
    races = data if isinstance(data, list) else data.get("racecards", [])

    venues: dict[str, list] = {}
    for r in races:
        v = r.get("course", "Unknown")
        if venue_filter and venue_filter.lower() not in v.lower():
            continue
        venues.setdefault(v, []).append(r)

    if not venues:
        return f"No races found{' for ' + venue_filter if venue_filter else ' today'}."

    lines = [f"RACES TODAY — {date.today()}\n"]
    for venue, vr in venues.items():
        lines.append(f"{venue}:")
        for r in vr:
            runners = r.get("runners", [])
            going   = r.get("going_detailed") or r.get("going", "")
            lines.append(
                f"  {r.get('off_time','')} | {r.get('race_id','')} | "
                f"{r.get('race_name','')[:45]} | Class {r.get('race_class','')} | "
                f"{r.get('distance','')} | {going} | {len(runners)} runners"
            )
        lines.append("")
    return "\n".join(lines)


# ── Tool 2: Full race briefing ─────────────────────────────────────────────────

def get_race_briefing(race_id: str) -> str:
    """Generate and return a full VOX briefing for a race ID."""
    from workers.velo_vox.velo_vox_agent import generate_briefing
    return generate_briefing(race_id, dry_run=False)


# ── Tool 3: Race evidence (no LLM — raw data only) ───────────────────────────

def get_race_evidence(race_id: str) -> str:
    """Return the raw evidence packet for a race (no synthesis)."""
    from workers.velo_vox.velo_vox_agent import generate_briefing
    return generate_briefing(race_id, dry_run=True)


# ── Tool 4: Horse profile from intelligence stack ─────────────────────────────

def get_horse_profile(horse_name: str) -> str:
    """Return full profile and RPD-C history for a named horse."""
    lines = [f"HORSE PROFILE: {horse_name}\n"]

    # RPD-C history (2025 then 2024)
    for year in [2025, 2024]:
        try:
            rows = _sql(f"""
                SELECT date, rpdc_tag_base, rpdc_confidence, rpdc_evidence, rpdc_explanation
                FROM intelligence.rpdc_tags_{year}
                WHERE lower(horse_name_raw) LIKE lower('%{horse_name}%')
                ORDER BY date DESC
                LIMIT 10
            """)
            if rows:
                lines.append(f"RPD-C History ({year}):")
                for r in rows:
                    ev = r.get("rpdc_evidence") or []
                    ev_str = ", ".join(ev) if isinstance(ev, list) else str(ev)
                    lines.append(
                        f"  {r['date']} | {r['rpdc_tag_base']} ({r['rpdc_confidence']}) | {ev_str}"
                    )
                    if r.get("rpdc_explanation"):
                        lines.append(f"    → {r['rpdc_explanation']}")
        except Exception as e:
            lines.append(f"  [{year} lookup error: {e}]")

    # Runner race facts (recent runs)
    try:
        rows = _sql(f"""
            SELECT date, course, distance, going, pos, sp_decimal,
                   or_rating, trainer, jockey, rpdc_tag_base, rpdc_confidence
            FROM public.runner_race_facts
            WHERE lower(horse_name) LIKE lower('%{horse_name}%')
            ORDER BY date DESC
            LIMIT 10
        """)
        if rows:
            lines.append(f"\nRecent Runs (runner_race_facts):")
            for r in rows:
                lines.append(
                    f"  {r.get('date','')} {r.get('course','')} {r.get('distance','')} "
                    f"{r.get('going','')} | pos:{r.get('pos','')} SP:{r.get('sp_decimal','')} "
                    f"OR:{r.get('or_rating','')} | {r.get('trainer','')} / {r.get('jockey','')} "
                    f"| RPD-C: {r.get('rpdc_tag_base','')}"
                )
    except Exception as e:
        lines.append(f"\n[runner_race_facts error: {e}]")

    # Horse comments / spotlight
    try:
        rows = _sql(f"""
            SELECT flag_type, comment_text, created_at
            FROM public.horse_comments
            WHERE lower(horse_name) LIKE lower('%{horse_name}%')
            ORDER BY created_at DESC
            LIMIT 5
        """)
        if rows:
            lines.append(f"\nSpotlight Flags:")
            for r in rows:
                lines.append(f"  [{r.get('flag_type','')}] {r.get('comment_text','')[:120]}")
    except Exception as e:
        lines.append(f"\n[comments error: {e}]")

    return "\n".join(lines) if len(lines) > 2 else f"No data found for horse: {horse_name}"


# ── Tool 5: Trainer profile ───────────────────────────────────────────────────

def get_trainer_profile(trainer_name: str) -> str:
    """Return trainer stats and current form."""
    lines = [f"TRAINER PROFILE: {trainer_name}\n"]

    try:
        rows = _sql(f"""
            SELECT *
            FROM public.trainer_profiles
            WHERE lower(trainer) LIKE lower('%{trainer_name}%')
            LIMIT 3
        """)
        if rows:
            for r in rows:
                for k, v in r.items():
                    lines.append(f"  {k}: {v}")
        else:
            lines.append("  Not found in trainer_profiles.")
    except Exception as e:
        lines.append(f"  [error: {e}]")

    # Recent runners under this trainer from runner_race_facts
    try:
        rows = _sql(f"""
            SELECT date, horse_name, course, pos, sp_decimal, rpdc_tag_base
            FROM public.runner_race_facts
            WHERE lower(trainer) LIKE lower('%{trainer_name}%')
            ORDER BY date DESC
            LIMIT 10
        """)
        if rows:
            lines.append("\nRecent runners:")
            for r in rows:
                lines.append(
                    f"  {r.get('date','')} {r.get('course','')} | "
                    f"{r.get('horse_name','')} | pos:{r.get('pos','')} "
                    f"SP:{r.get('sp_decimal','')} RPD-C:{r.get('rpdc_tag_base','')}"
                )
    except Exception as e:
        lines.append(f"\n[recent runners error: {e}]")

    return "\n".join(lines)


# ── Tool 6: RPD-C tag summary for a venue/date ───────────────────────────────

def get_rpdc_summary(venue: str, race_date: str = "") -> str:
    """Return all RPD-C tags for a venue's runners from intelligence stack."""
    if not race_date:
        race_date = str(date.today())

    lines = [f"RPD-C SUMMARY: {venue} {race_date}\n"]

    for year in [2025, 2024]:
        try:
            rows = _sql(f"""
                SELECT t.horse_name_raw, t.rpdc_tag_base, t.rpdc_confidence,
                       t.rpdc_evidence, t.date, t.trainer
                FROM intelligence.rpdc_tags_{year} t
                WHERE lower(t.horse_name_raw) IN (
                    SELECT lower(horse_name)
                    FROM public.runner_race_facts
                    WHERE lower(course) LIKE lower('%{venue}%')
                      AND date = '{race_date}'
                )
                ORDER BY t.rpdc_tag_base, t.date DESC
                LIMIT 50
            """)
            if rows:
                lines.append(f"From {year} intelligence stack:")
                for r in rows:
                    ev = r.get("rpdc_evidence") or []
                    ev_str = ", ".join(ev[:3]) if isinstance(ev, list) else ""
                    lines.append(
                        f"  {r['horse_name_raw']} | {r['rpdc_tag_base']} ({r['rpdc_confidence']}) "
                        f"| {ev_str}"
                    )
        except Exception as e:
            lines.append(f"  [{year} error: {e}]")

    return "\n".join(lines) if len(lines) > 2 else f"No RPD-C data found for {venue} {race_date}"


# ── Tool 7: Query the intelligence stack directly ─────────────────────────────

def query_intelligence(question: str) -> str:
    """
    Run a natural-language style query against what we know from the intelligence stack.
    Returns a summary of relevant data.
    Covers: plot candidate flags, handicap trajectory, setup restore events.
    """
    # This is deliberately simple — it returns structured context for the agent to reason over
    lines = [f"INTELLIGENCE QUERY: {question}\n"]
    lines.append("(Agent should use other tools to answer specific horse/race/trainer queries)")
    lines.append("Available data sources:")
    lines.append("  - intelligence.rpdc_tags_2025 / 2024 — 84k and 170k rows of deterministic RPD-C tags")
    lines.append("  - public.runner_race_facts — recent run-level data with rpdc_tag_base")
    lines.append("  - public.trainer_profiles / horse_profiles / jockey_profiles")
    lines.append("  - public.horse_comments — NLP spotlight flags")
    lines.append("  - bha_yearly_summary / bha_macro_specialty_metrics — macro regime context")
    return "\n".join(lines)


# ── Tool 8: Trigger sigma → doctrine feed (VOX bridge) ───────────────────────

def trigger_sigma_feed(race_date: str = "") -> str:
    """
    Trigger the Sigma → Playbook G doctrine ingestion path for a given date.

    VOX calls this after confirming sigma debrief records exist in Supabase.
    Idempotent — safe to re-call for the same date (dedup in learned_patterns).

    Returns a status summary string for the agent to relay.
    """
    if not race_date:
        from datetime import date as _date
        race_date = str(_date.today())

    try:
        from scripts.feed_sigma_loop import feed
        result = feed(race_date)
        status = result.get("status", "unknown")
        fed    = result.get("fed", 0)
        reviews = result.get("reviews", 0)
        wins   = result.get("wins", 0)
        msg    = result.get("message", "")

        return (
            f"SIGMA FEED — {race_date}\n"
            f"Status  : {status}\n"
            f"Reviews : {reviews}\n"
            f"Fed     : {fed} races ingested into Playbook G\n"
            f"Wins    : {wins}\n"
            f"Detail  : {msg}"
        )
    except Exception as e:
        return f"SIGMA FEED FAILED — {race_date}\nError: {e}"


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS = {
    "list_races": {
        "fn": list_todays_races,
        "description": "List today's races. Args: venue_filter (optional string, e.g. 'carlisle')",
        "args": ["venue_filter (optional)"],
    },
    "get_briefing": {
        "fn": get_race_briefing,
        "description": "Generate a full VOX briefing for a race. Args: race_id (e.g. rac_11875292)",
        "args": ["race_id (required)"],
    },
    "get_evidence": {
        "fn": get_race_evidence,
        "description": "Get raw evidence packet for a race (no LLM synthesis). Args: race_id",
        "args": ["race_id (required)"],
    },
    "get_horse": {
        "fn": get_horse_profile,
        "description": "Get full profile and RPD-C history for a horse. Args: horse_name",
        "args": ["horse_name (required)"],
    },
    "get_trainer": {
        "fn": get_trainer_profile,
        "description": "Get trainer stats and recent runners. Args: trainer_name",
        "args": ["trainer_name (required)"],
    },
    "get_rpdc_summary": {
        "fn": get_rpdc_summary,
        "description": "Get RPD-C tag summary for all runners at a venue. Args: venue, date (optional)",
        "args": ["venue (required)", "date (optional, YYYY-MM-DD)"],
    },
    "trigger_sigma_feed": {
        "fn": trigger_sigma_feed,
        "description": (
            "Trigger Sigma → Playbook G doctrine ingestion for a date. "
            "Call after sigma debrief is confirmed in Supabase. "
            "Idempotent — safe to re-call. Args: race_date (optional, YYYY-MM-DD, default today)"
        ),
        "args": ["race_date (optional, YYYY-MM-DD)"],
    },
}


def execute_tool(name: str, args: dict) -> str:
    """Execute a named tool with given args. Returns result string."""
    if name not in TOOLS:
        return f"Unknown tool: {name}. Available: {list(TOOLS.keys())}"
    try:
        fn = TOOLS[name]["fn"]
        return fn(**args)
    except Exception as e:
        return f"Tool {name} failed: {e}"


def tools_description() -> str:
    """Return formatted tool list for the system prompt."""
    lines = []
    for name, info in TOOLS.items():
        lines.append(f'  "{name}": {info["description"]}')
    return "\n".join(lines)
