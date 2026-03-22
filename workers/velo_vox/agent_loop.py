"""
VOX Agent Loop — full intelligence, Python-first architecture.

Python handles ALL data fetching. MiniMax handles ALL synthesis and conversation.
The model never answers from thin air — if data is needed, Python fetches it first.

Intent detection covers:
  - Race listing (venue mentions, "what's on", "card today")
  - Specific race by time reference ("3:17", "the 3:52")
  - Specific race by ID (rac_xxx)
  - Full briefing requests ("tell me about", "brief", "analyse", "what do you think")
  - Horse name mentions → profile + RPD-C history + gear events + comments
  - Trainer name mentions → profile + recent runners
  - Jockey name mentions → profile
  - Best bet / value queries → full card analysis
  - Follow-up references ("that horse", "the favourite", "him", "her")
  - Any capitalised multi-word that could be a horse/trainer/jockey
"""
import re
import os
import sys
import json
import requests
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workers.velo_vox.providers.openrouter_client import OpenRouterClient

_SYSTEM_TEMPLATE = (Path(__file__).parent / "templates" / "vox_agent_system.txt").read_text()
_MAX_HISTORY = 40

_RAPI_USER = os.getenv("RACING_API_USERNAME", "")
_RAPI_PASS = os.getenv("RACING_API_PASSWORD", "")
_RAPI_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1")
_SB_TOKEN  = os.getenv("SUPABASE_ACCESS_TOKEN", "")
_SB_REF    = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]


# ── Supabase helper ────────────────────────────────────────────────────────────

def _sql(query: str, timeout: int = 20) -> list:
    try:
        r = requests.post(
            f"https://api.supabase.com/v1/projects/{_SB_REF}/database/query",
            headers={"Authorization": f"Bearer {_SB_TOKEN}", "Content-Type": "application/json"},
            json={"query": query},
            timeout=timeout,
        )
        result = r.json()
        if isinstance(result, dict) and "message" in result:
            return []
        return result or []
    except Exception:
        return []


def _rapi(endpoint: str, params: dict | None = None) -> dict | list:
    r = requests.get(
        f"{_RAPI_BASE}/{endpoint.lstrip('/')}",
        auth=(_RAPI_USER, _RAPI_PASS),
        params=params or {},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── System prompt ──────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    return (
        _SYSTEM_TEMPLATE
        .replace("{TOOLS_DESCRIPTION}", "")
        .replace("{TODAY}", str(date.today()))
    )


# ── Data fetchers ──────────────────────────────────────────────────────────────

def _fetch_todays_races(venue_filter: str = "") -> tuple[list, dict]:
    """Returns (races_list, time_index). time_index maps off_time → race_id."""
    data = _rapi("racecards")
    all_races = data if isinstance(data, list) else data.get("racecards", [])
    if venue_filter:
        all_races = [r for r in all_races if venue_filter.lower() in r.get("course", "").lower()]
    time_index = {}
    for r in all_races:
        t   = r.get("off_time", "")
        rid = r.get("race_id", "")
        if t and rid:
            time_index[t] = rid
    return all_races, time_index


def _format_race_list(races: list) -> str:
    if not races:
        return "No races found."
    venues: dict[str, list] = {}
    for r in races:
        venues.setdefault(r.get("course", "Unknown"), []).append(r)
    lines = [f"RACES TODAY — {date.today()}\n"]
    for venue, vr in venues.items():
        lines.append(f"{venue}:")
        for r in vr:
            going = r.get("going_detailed") or r.get("going", "")
            lines.append(
                f"  {r.get('off_time','')} | {r.get('race_id','')} | "
                f"{r.get('race_name','')[:50]} | Class {r.get('race_class','')} | "
                f"{r.get('distance','')} | {going} | {len(r.get('runners',[]))} runners"
            )
        lines.append("")
    return "\n".join(lines)


def _fetch_horse_intelligence(horse_name: str) -> str:
    """Full profile: RPD-C history, recent runs, gear events, spotlight flags."""
    lines = [f"HORSE INTELLIGENCE: {horse_name}\n"]

    # RPD-C history across both years
    for year in [2025, 2024]:
        rows = _sql(f"""
            SELECT date, rpdc_tag_base, rpdc_confidence, rpdc_evidence, rpdc_explanation
            FROM intelligence.rpdc_tags_{year}
            WHERE lower(horse_name_raw) LIKE lower('%{horse_name.replace("'", "''")}%')
            ORDER BY date DESC LIMIT 8
        """)
        if rows:
            lines.append(f"RPD-C History ({year}):")
            for r in rows:
                ev = r.get("rpdc_evidence") or []
                ev_str = ", ".join(ev) if isinstance(ev, list) else str(ev)
                lines.append(f"  {r['date']} | {r['rpdc_tag_base']} ({r['rpdc_confidence']}) | {ev_str}")
                if r.get("rpdc_explanation"):
                    lines.append(f"    {r['rpdc_explanation']}")

    # Recent runs from runner_race_facts
    rows = _sql(f"""
        SELECT date, course, distance, going, pos, sp_decimal,
               or_rating, trainer, jockey, rpdc_tag_base, rpdc_confidence
        FROM public.runner_race_facts
        WHERE lower(horse_name) LIKE lower('%{horse_name.replace("'", "''")}%')
        ORDER BY date DESC LIMIT 8
    """)
    if rows:
        lines.append("\nRecent Runs:")
        for r in rows:
            lines.append(
                f"  {r.get('date','')} {r.get('course','')} {r.get('distance','')} "
                f"{r.get('going','')} | pos:{r.get('pos','')} SP:{r.get('sp_decimal','')} "
                f"OR:{r.get('or_rating','')} | {r.get('trainer','')} / {r.get('jockey','')} "
                f"| RPD-C:{r.get('rpdc_tag_base','?')}"
            )

    # Gear and medical events
    rows = _sql(f"""
        SELECT event_date, event_type, headgear_added, headgear_removed, notes
        FROM public.gear_medical_events
        WHERE lower(horse_name) LIKE lower('%{horse_name.replace("'", "''")}%')
        ORDER BY event_date DESC LIMIT 5
    """)
    if rows:
        lines.append("\nGear/Medical Events:")
        for r in rows:
            lines.append(
                f"  {r.get('event_date','')} | {r.get('event_type','')} | "
                f"added:{r.get('headgear_added','')} removed:{r.get('headgear_removed','')} "
                f"| {r.get('notes','')}"
            )

    # Spotlight/NLP flags from horse_comments
    rows = _sql(f"""
        SELECT flag_type, comment_text, created_at
        FROM public.horse_comments
        WHERE lower(horse_name) LIKE lower('%{horse_name.replace("'", "''")}%')
        ORDER BY created_at DESC LIMIT 5
    """)
    if rows:
        lines.append("\nSpotlight Flags:")
        for r in rows:
            lines.append(f"  [{r.get('flag_type','')}] {r.get('comment_text','')[:150]}")

    if len(lines) <= 2:
        return f"No Supabase data found for: {horse_name}. May not have run in tracked period."
    return "\n".join(lines)


def _fetch_trainer_intelligence(trainer_name: str) -> str:
    """Trainer profile + recent strike rate + recent runners with RPD-C."""
    lines = [f"TRAINER INTELLIGENCE: {trainer_name}\n"]

    rows = _sql(f"""
        SELECT *
        FROM public.trainer_profiles
        WHERE lower(trainer) LIKE lower('%{trainer_name.replace("'", "''")}%')
        LIMIT 3
    """)
    if rows:
        for r in rows:
            for k, v in r.items():
                if v is not None:
                    lines.append(f"  {k}: {v}")
    else:
        lines.append("  Not in trainer_profiles.")

    rows = _sql(f"""
        SELECT date, horse_name, course, distance, pos, sp_decimal,
               or_rating, jockey, rpdc_tag_base
        FROM public.runner_race_facts
        WHERE lower(trainer) LIKE lower('%{trainer_name.replace("'", "''")}%')
        ORDER BY date DESC LIMIT 12
    """)
    if rows:
        lines.append("\nRecent Runners:")
        for r in rows:
            lines.append(
                f"  {r.get('date','')} {r.get('course','')} | "
                f"{r.get('horse_name','')} | pos:{r.get('pos','')} "
                f"SP:{r.get('sp_decimal','')} OR:{r.get('or_rating','')} "
                f"RPD-C:{r.get('rpdc_tag_base','?')} | J:{r.get('jockey','')}"
            )
    return "\n".join(lines)


def _fetch_jockey_intelligence(jockey_name: str) -> str:
    """Jockey profile + recent rides."""
    lines = [f"JOCKEY INTELLIGENCE: {jockey_name}\n"]

    rows = _sql(f"""
        SELECT *
        FROM public.jockey_profiles
        WHERE lower(jockey) LIKE lower('%{jockey_name.replace("'", "''")}%')
        LIMIT 2
    """)
    if rows:
        for r in rows:
            for k, v in r.items():
                if v is not None:
                    lines.append(f"  {k}: {v}")
    else:
        lines.append("  Not in jockey_profiles.")

    rows = _sql(f"""
        SELECT date, horse_name, course, trainer, pos, sp_decimal, rpdc_tag_base
        FROM public.runner_race_facts
        WHERE lower(jockey) LIKE lower('%{jockey_name.replace("'", "''")}%')
        ORDER BY date DESC LIMIT 10
    """)
    if rows:
        lines.append("\nRecent Rides:")
        for r in rows:
            lines.append(
                f"  {r.get('date','')} {r.get('course','')} | "
                f"{r.get('horse_name','')} | pos:{r.get('pos','')} "
                f"SP:{r.get('sp_decimal','')} RPD-C:{r.get('rpdc_tag_base','?')} "
                f"| T:{r.get('trainer','')}"
            )
    return "\n".join(lines)


def _fetch_race_briefing(race_id: str) -> str:
    """Full VOX briefing for a race."""
    from workers.velo_vox.velo_vox_agent import generate_briefing
    return generate_briefing(race_id, dry_run=False)


def _fetch_race_evidence(race_id: str) -> str:
    """Raw evidence packet for a race (no LLM synthesis)."""
    from workers.velo_vox.velo_vox_agent import generate_briefing
    return generate_briefing(race_id, dry_run=True)


def _fetch_full_card_intelligence(venue: str, races: list) -> str:
    """
    For 'best bet / top pick / value today' queries — pull evidence for all races
    at a venue, identify T-tagged horses, summarise the card for VOX to reason over.
    """
    venue_races = [r for r in races if venue.lower() in r.get("course", "").lower()] if venue else races
    if not venue_races:
        venue_races = races[:8]  # fallback: first 8 races

    lines = [f"FULL CARD INTELLIGENCE — {venue or 'All Venues'} {date.today()}\n"]

    for race in venue_races[:7]:  # cap at 7 to stay within token budget
        race_id   = race.get("race_id", "")
        off_time  = race.get("off_time", "")
        race_name = race.get("race_name", "")
        lines.append(f"\n{'='*60}")
        lines.append(f"{off_time} | {race_name} | {race_id}")

        for runner in race.get("runners", []):
            from src.rpd.rpdc_rules import tag_from_live_runner
            tag = tag_from_live_runner(runner, race)

            # Try historical tag for higher confidence
            horse = runner.get("horse", "")
            hist_rows = _sql(f"""
                SELECT rpdc_tag_base, rpdc_confidence, rpdc_evidence
                FROM intelligence.rpdc_tags_2025
                WHERE lower(horse_name_raw) LIKE lower('%{horse.replace("'", "''")}%')
                ORDER BY date DESC LIMIT 1
            """)
            if hist_rows:
                htag = hist_rows[0]
                rpdc = f"{htag['rpdc_tag_base']} ({htag['rpdc_confidence']}/historical)"
            else:
                rpdc = f"{tag.rpdc_tag_base} ({tag.rpdc_confidence}/live)"

            t14 = runner.get("trainer_14_days") or {}
            lines.append(
                f"  {runner.get('number','')}.{horse} | OR:{runner.get('ofr','')} "
                f"RPR:{runner.get('rpr','')} | {runner.get('trainer','')} "
                f"[14d: {t14.get('wins','?')}/{t14.get('runs','?')} {t14.get('percent','?')}%] "
                f"| J:{runner.get('jockey','')} | RPD-C:{rpdc} | "
                f"last:{runner.get('last_run','')}d | hg:{runner.get('headgear','') or 'none'}"
            )
            if runner.get("spotlight"):
                lines.append(f"    Spotlight: {runner['spotlight'][:120]}")

    return "\n".join(lines)


# ── Intent detection ───────────────────────────────────────────────────────────

_RACE_LIST_PATTERNS = [
    r"what races", r"races (today|on today|are on|at)", r"what'?s on",
    r"card today", r"meetings? today", r"show.{0,10}races", r"list.{0,10}races",
    r"today'?s? (card|meeting|races|fixture)", r"racing today",
]

_BRIEFING_PATTERNS = [
    r"brief(ing)?", r"full analysis", r"tell me (about|more)", r"break it down",
    r"run me through", r"analys[ei]", r"what (do you think|are we look)",
    r"give me (the|a|your)", r"full card", r"race report", r"what'?s? the (story|picture|crack)",
    r"thoughts on", r"looking at", r"assess", r"walk me through",
]

_BEST_BET_PATTERNS = [
    r"best bet", r"top pick", r"best (race|opportunity|play)", r"where'?s? (the )?value",
    r"what (should|would) (i|you) back", r"what('?s| is) worth", r"strongest (case|play|bet)",
    r"most confident", r"highest conviction", r"where do you (like|fancy)",
    r"any (value|standouts|bets|plays) today", r"pick (of the day|of the card)",
]

_KNOWN_VENUES = [
    "carlisle", "cheltenham", "newmarket", "ascot", "goodwood", "sandown",
    "kempton", "haydock", "york", "chester", "doncaster", "nottingham",
    "lingfield", "wolverhampton", "southwell", "windsor", "leicester",
    "leopardstown", "curragh", "punchestown", "fairyhouse", "galway",
    "naas", "navan", "thurles", "tipperary", "cork", "killarney",
    "musselburgh", "perth", "ayr", "hamilton", "edinburgh",
    "exeter", "taunton", "wincanton", "fontwell", "plumpton", "brighton",
    "newbury", "bath", "chepstow", "hereford", "ludlow", "stratford",
    "huntingdon", "market rasen", "catterick", "ripon", "redcar",
    "pontefract", "beverley", "thirsk", "wetherby", "hexham",
]

# Words that are almost certainly NOT horse/trainer/jockey names when capitalised
_NOT_ENTITY = {
    "I", "The", "A", "An", "And", "But", "For", "Or", "Nor", "So", "Yet",
    "At", "By", "For", "In", "Of", "On", "To", "Up", "As", "Is", "It",
    "He", "She", "We", "You", "They", "This", "That", "These", "Those",
    "What", "Which", "Who", "Whose", "When", "Where", "Why", "How",
    "All", "Any", "Both", "Each", "Few", "More", "Most", "Other",
    "Some", "Such", "No", "Not", "Only", "Same", "Than", "Too",
    "Very", "Just", "Race", "Horse", "Trainer", "Jockey", "Today",
    "Class", "Going", "Good", "Soft", "Firm", "Heavy", "Standard",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "VELO", "VOX", "RPD", "BHA", "OR", "RPR", "SP", "TS",
    "Tell", "Give", "Show", "Get", "Run", "Let", "Can", "Will",
    "Full", "Card", "Meet", "Race", "Run", "Last", "Next", "First",
    "True", "False", "Yes", "No", "OK", "Hi", "Hello",
}


def _is_match(text: str, patterns: list[str]) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in patterns)


def _extract_time_ref(text: str, time_index: dict) -> str | None:
    """Find a race time reference in text and return the race_id."""
    times = re.findall(r'\b(\d{1,2}[:.]?\d{2})\b', text)
    for t in times:
        t_norm = t.replace('.', ':')
        if t_norm in time_index:
            return time_index[t_norm]
        for key, rid in time_index.items():
            if key.split(':')[0].lstrip('0') == t_norm.split(':')[0].lstrip('0') and \
               key.split(':')[-1] == t_norm.split(':')[-1]:
                return rid
    return None


def _extract_race_id(text: str) -> str | None:
    m = re.search(r'\brac_\d+\b', text)
    return m.group(0) if m else None


def _extract_venue(text: str) -> str | None:
    lower = text.lower()
    for v in _KNOWN_VENUES:
        if v in lower:
            return v.title()
    return None


def _extract_capitalised_entities(text: str, known_horses: list[str] = None) -> list[str]:
    """
    Extract potential horse/trainer/jockey names.

    Strategy (priority order):
    1. Quoted strings — always treated as entity names
    2. Any word/phrase that fuzzy-matches a known horse on today's card (catches
       short names like "Make", "Fox", "Jet" that the capitalisation rules miss)
    3. Unquoted capitalised multi-word phrases not in the stop-word list
    4. Single capitalised words that partially match known horses
    """
    found: list[str] = []

    # 1. Quoted strings
    quoted = re.findall(r'"([^"]{2,40})"', text)
    found.extend(quoted)

    # 2. Match against known horses from today's card — case-insensitive substring
    if known_horses:
        text_lower = text.lower()
        for horse in known_horses:
            if not horse:
                continue
            # Check if any meaningful part of the horse name appears in the text
            # Use the base name (strip country suffix like "(GB)", "(IRE)")
            base = re.sub(r'\s*\([A-Z]+\)\s*$', '', horse).strip()
            if len(base) >= 3 and base.lower() in text_lower:
                found.append(horse)

    # 3. Unquoted capitalised multi-word phrases
    unquoted = re.findall(r'\b([A-Z][a-z]+(?:[\s\'-][A-Z][a-z]+)+)\b', text)
    unquoted = [u for u in unquoted if u not in _NOT_ENTITY and len(u) > 4]
    found.extend(unquoted)

    # 4. Single capitalised words matching known horses
    if known_horses:
        single_caps = re.findall(r'\b([A-Z][a-zA-Z]{2,})\b', text)
        for w in single_caps:
            if w in _NOT_ENTITY:
                continue
            for h in known_horses:
                if w.lower() == h.lower().split()[0] and w not in found:
                    found.append(h)
                    break

    # Deduplicate preserving order, prefer full horse names over fragments
    seen_lower: set[str] = set()
    result: list[str] = []
    for f in found:
        key = f.lower()
        if key not in seen_lower:
            seen_lower.add(key)
            result.append(f)
    return result


# ── Session state ──────────────────────────────────────────────────────────────

class SessionState:
    def __init__(self):
        self.races: list[dict] = []
        self.time_index: dict[str, str] = {}
        self.venues: list[str] = []
        self.known_horses: list[str] = []   # horses seen in this session
        self.last_race_id: str = ""
        self.last_venue: str = ""

    def refresh_races(self, venue_filter: str = ""):
        data = _rapi("racecards")
        all_races = data if isinstance(data, list) else data.get("racecards", [])
        if venue_filter:
            all_races = [r for r in all_races if venue_filter.lower() in r.get("course", "").lower()]
        self.races      = all_races
        self.time_index = {}
        self.venues     = sorted(set(r.get("course", "") for r in all_races))
        for r in all_races:
            t   = r.get("off_time", "")
            rid = r.get("race_id", "")
            if t and rid:
                self.time_index[t] = rid
        # Index all horse names
        self.known_horses = [
            runner.get("horse", "")
            for r in all_races
            for runner in r.get("runners", [])
        ]


# ── Zep memory (optional) ──────────────────────────────────────────────────────

try:
    from src.intelligence.zep_memory import zep_client as _zep
    _ZEP_AVAILABLE = True
except Exception:
    _zep = None
    _ZEP_AVAILABLE = False


# ── Agent ──────────────────────────────────────────────────────────────────────

class VoxAgent:

    def __init__(self, user_id: int | str | None = None):
        self.history: list[dict] = []
        self.client  = OpenRouterClient()
        self.system  = _build_system_prompt()
        self.session = SessionState()
        # Zep session — created once per user, persists across conversations
        self._zep_session_id: str | None = None
        if _ZEP_AVAILABLE and _zep and user_id is not None:
            try:
                self._zep_session_id = _zep.ensure_session(str(user_id))
            except Exception:
                pass

    def reset(self):
        self.history = []
        self.session = SessionState()

    def _trim(self):
        while len(self.history) > _MAX_HISTORY:
            self.history.pop(0)

    def chat(self, user_message: str) -> str:
        injected: list[str] = []

        # ── Ensure we always have today's races loaded ─────────────────────
        if not self.session.races:
            try:
                self.session.refresh_races()
            except Exception:
                pass

        # ── Extract venue ──────────────────────────────────────────────────
        venue = _extract_venue(user_message)
        if venue:
            self.session.last_venue = venue

        # ── Intent: race list ──────────────────────────────────────────────
        wants_list = _is_match(user_message, _RACE_LIST_PATTERNS)
        if wants_list:
            try:
                if venue:
                    self.session.refresh_races(venue)
                formatted = _format_race_list(
                    [r for r in self.session.races
                     if not venue or venue.lower() in r.get("course","").lower()]
                )
                injected.append(f"[RACES DATA]\n{formatted}")
            except Exception as e:
                injected.append(f"[RACES DATA — fetch error: {e}]")

        # ── Intent: specific race ──────────────────────────────────────────
        race_id = (
            _extract_race_id(user_message)
            or _extract_time_ref(user_message, self.session.time_index)
        )

        wants_brief = _is_match(user_message, _BRIEFING_PATTERNS)

        if race_id:
            self.session.last_race_id = race_id
            if wants_brief:
                try:
                    brief = _fetch_race_briefing(race_id)
                    injected.append(f"[RACE BRIEFING]\n{brief}")
                except Exception as e:
                    injected.append(f"[RACE BRIEFING — error: {e}]")
            else:
                try:
                    evidence = _fetch_race_evidence(race_id)
                    injected.append(f"[RACE EVIDENCE]\n{evidence}")
                except Exception as e:
                    injected.append(f"[RACE EVIDENCE — error: {e}]")

        elif wants_brief and self.session.last_race_id:
            # "brief it" / "full analysis" with no new race ref — use last race
            try:
                brief = _fetch_race_briefing(self.session.last_race_id)
                injected.append(f"[RACE BRIEFING — continuation]\n{brief}")
            except Exception as e:
                injected.append(f"[RACE BRIEFING — error: {e}]")

        # ── Intent: best bet / full card value query ───────────────────────
        if _is_match(user_message, _BEST_BET_PATTERNS):
            try:
                target_venue = venue or self.session.last_venue or ""
                card_intel = _fetch_full_card_intelligence(target_venue, self.session.races)
                injected.append(f"[FULL CARD INTELLIGENCE]\n{card_intel}")
            except Exception as e:
                injected.append(f"[FULL CARD INTELLIGENCE — error: {e}]")

        # ── Intent: horse / trainer / jockey entity lookups ───────────────
        entities = _extract_capitalised_entities(user_message, self.session.known_horses)

        for entity in entities[:3]:  # cap at 3 lookups per message
            # Try horse first
            horse_data = _fetch_horse_intelligence(entity)
            if "No Supabase data found" not in horse_data and "RPD-C History" in horse_data:
                injected.append(f"[HORSE INTELLIGENCE: {entity}]\n{horse_data}")
                continue

            # Try trainer
            trainer_data = _fetch_trainer_intelligence(entity)
            if "Not in trainer_profiles" not in trainer_data and len(trainer_data) > 80:
                injected.append(f"[TRAINER INTELLIGENCE: {entity}]\n{trainer_data}")
                continue

            # Try jockey
            jockey_data = _fetch_jockey_intelligence(entity)
            if "Not in jockey_profiles" not in jockey_data and len(jockey_data) > 80:
                injected.append(f"[JOCKEY INTELLIGENCE: {entity}]\n{jockey_data}")

        # ── Zep graph search — recent entity intelligence ──────────────────
        # Only runs if Zep is configured. Searches the system knowledge graph
        # for recent facts about any entities mentioned (horse, trainer, course).
        # Injects results before Supabase data so LLM has cross-session context.
        if _ZEP_AVAILABLE and _zep:
            try:
                # Build a focused graph query from entities and venue
                graph_query = user_message[:120]
                if entities:
                    graph_query = entities[0] + " " + graph_query
                if venue:
                    graph_query = venue + " " + graph_query
                graph_context = _zep.search_graph(graph_query, limit=5)
                if graph_context:
                    injected.insert(0, graph_context)
            except Exception:
                pass

        # ── Zep session memory — synthesised prior-conversation context ────
        # Only fires if Zep has data from prior sessions (first conversation = empty).
        if _ZEP_AVAILABLE and _zep and self._zep_session_id:
            try:
                zep_ctx = _zep.get_memory_context(self._zep_session_id)
                if zep_ctx:
                    # Prepend as a system-level note, not as fetched data
                    injected.insert(0, f"[ZEP MEMORY — prior sessions]\n{zep_ctx}")
            except Exception:
                pass

        # ── Build messages ─────────────────────────────────────────────────
        if injected:
            augmented = user_message + "\n\n---\n" + "\n\n".join(injected)
        else:
            augmented = user_message

        self.history.append({"role": "user", "content": augmented})
        self._trim()

        messages = [{"role": "system", "content": self.system}] + self.history

        response = self.client.chat(messages=messages, max_tokens=4096, temperature=0.3)

        self.history.append({"role": "assistant", "content": response})
        self._trim()

        # ── Persist exchange to Zep session memory ─────────────────────────
        # Zep auto-extracts facts: horse opinions, trainer notes, form assessments.
        # Available as context in the user's NEXT conversation.
        if _ZEP_AVAILABLE and _zep and self._zep_session_id:
            try:
                _zep.add_exchange(self._zep_session_id, user_message, response)
            except Exception:
                pass

        return response
