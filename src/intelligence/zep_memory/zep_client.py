"""
VÉLØ Zep Cloud Memory Client

Two roles:
  1. Session memory — per Telegram user.
     Zep auto-extracts facts from VOX conversations (horse names, trainer opinions,
     form notes). On next conversation the synthesised context is injected before the LLM,
     so VOX "remembers" what this user cares about.

  2. Entity graph — system-level knowledge store.
     After sigma closes race outcomes, facts are written as text nodes:
       "Magical Spirit won at Carlisle 2026-03-22 SP 9/2 OR 88 RPD-C PLOT_CANDIDATE"
     VOX can then search this graph for recent trainer/horse/course intelligence
     before falling back to Supabase.

Completely optional — if ZEP_API_KEY is not set (or zep_cloud is not installed)
every method is a silent no-op. Existing behaviour is unchanged.

Install:
    pip install zep-cloud

Env:
    ZEP_API_KEY=<your Zep Cloud project API key>
"""
import os
import logging
from typing import Any

log = logging.getLogger("velo.zep_memory")

_ZEP_API_KEY = os.getenv("ZEP_API_KEY", "")

# System-level user for the entity knowledge graph (shared across all VOX sessions)
_SYSTEM_USER_ID = "velo_racing_intelligence"


def _client():
    """Return a live Zep client, or None if not configured."""
    if not _ZEP_API_KEY:
        return None
    try:
        from zep_cloud.client import Zep
        return Zep(api_key=_ZEP_API_KEY)
    except ImportError:
        log.debug("[zep] zep-cloud not installed — memory disabled")
        return None
    except Exception as e:
        log.warning("[zep] client init failed: %s", e)
        return None


def _ensure_user(client, user_id: str):
    """Create user if not exists. Silently handles 'already exists' errors."""
    try:
        client.user.add(user_id=user_id)
    except Exception:
        pass  # user already exists


# ── Session memory ─────────────────────────────────────────────────────────────

def ensure_session(user_id: str) -> str | None:
    """
    Create or resume a Zep session for a Telegram user.
    Returns session_id (= user_id for simplicity) or None if Zep unavailable.
    """
    client = _client()
    if not client:
        return None

    session_id = f"vox_session_{user_id}"
    try:
        _ensure_user(client, f"vox_user_{user_id}")
        _ensure_user(client, _SYSTEM_USER_ID)
        try:
            client.memory.add_session(
                session_id=session_id,
                user_id=f"vox_user_{user_id}",
            )
        except Exception:
            pass  # session already exists
        log.debug("[zep] session ensured: %s", session_id)
        return session_id
    except Exception as e:
        log.warning("[zep] ensure_session failed: %s", e)
        return None


def get_memory_context(session_id: str | None) -> str:
    """
    Return Zep's synthesised memory context for this session.
    This is a ready-to-inject paragraph of facts Zep has extracted from prior conversations.
    Returns "" if unavailable.
    """
    if not session_id:
        return ""
    client = _client()
    if not client:
        return ""
    try:
        mem = client.memory.get(session_id=session_id)
        ctx = getattr(mem, "context", None) or ""
        if ctx:
            log.debug("[zep] memory context retrieved (%d chars)", len(ctx))
        return ctx
    except Exception as e:
        log.debug("[zep] get_memory_context: %s", e)
        return ""


def add_exchange(session_id: str | None, user_message: str, assistant_response: str):
    """
    Persist a user↔assistant exchange to Zep.
    Zep will auto-extract facts (horse names, form opinions, trainer assessments, etc.)
    and make them available as context in future sessions.
    """
    if not session_id:
        return
    client = _client()
    if not client:
        return
    try:
        from zep_cloud.types import Message
        client.memory.add(
            session_id=session_id,
            messages=[
                Message(role_type="user",      role="User",       content=user_message),
                Message(role_type="assistant", role="VÉLØ VOX",   content=assistant_response),
            ],
        )
        log.debug("[zep] exchange added to session %s", session_id)
    except Exception as e:
        log.warning("[zep] add_exchange failed: %s", e)


# ── Entity graph ───────────────────────────────────────────────────────────────

def add_graph_fact(fact_text: str):
    """
    Write a racing intelligence fact to the system-level Zep knowledge graph.

    Facts are free-text sentences. Zep parses them into entity nodes and edges.
    Examples:
      "Magical Spirit won at Carlisle on 2026-03-22 at SP 9/2 OR 88 RPD-C PLOT_CANDIDATE"
      "John Smith trained 3 winners at northern tracks this week — 14-day strike rate 21%"
      "Ascot 2026-03-22 heavy going — draw bias towards high numbers confirmed"
    """
    client = _client()
    if not client:
        return
    try:
        _ensure_user(client, _SYSTEM_USER_ID)
        client.graph.add(user_id=_SYSTEM_USER_ID, data=fact_text, type="text")
        log.debug("[zep] graph fact added: %s", fact_text[:80])
    except Exception as e:
        log.warning("[zep] add_graph_fact failed: %s", e)


def search_graph(query: str, limit: int = 5) -> str:
    """
    Search the system-level Zep knowledge graph.
    Returns a formatted string of matching facts, or "" if none.

    The agent can call this before hitting Supabase for recent trainer/horse/course context.
    """
    client = _client()
    if not client:
        return ""
    try:
        results = client.graph.search(
            user_id=_SYSTEM_USER_ID,
            query=query,
            scope="edges",
            limit=limit,
        )
        edges = getattr(results, "edges", []) or []
        if not edges:
            return ""
        lines = [f"[ZEP GRAPH — {query}]"]
        for e in edges:
            fact = getattr(e, "fact", None) or str(e)
            lines.append(f"  {fact}")
        return "\n".join(lines)
    except Exception as e:
        log.debug("[zep] search_graph failed: %s", e)
        return ""


# ── Outcome writer (called by sigma path) ──────────────────────────────────────

def write_race_outcome(
    horse_name: str,
    trainer: str,
    jockey: str,
    course: str,
    race_date: str,
    position: str | int | None,
    sp_decimal: float | None,
    or_rating: int | None,
    rpdc_tag: str | None,
    velo_verdict: str | None = None,
):
    """
    Write a race outcome as a graph fact.
    Called from scripts/close_sigma_loops.py after sigma review closes.

    The fact is a human-readable sentence that Zep parses into entity + relationship nodes.
    """
    parts = []

    pos_str = str(position) if position is not None else "?"
    sp_str  = f"SP {sp_decimal}" if sp_decimal is not None else ""
    or_str  = f"OR {or_rating}" if or_rating is not None else ""
    rpd_str = f"RPD-C {rpdc_tag}" if rpdc_tag else ""
    velo_str = f"VELO verdict {velo_verdict}" if velo_verdict else ""

    fact = (
        f"{horse_name} finished {pos_str} at {course} on {race_date}"
        + (f" {sp_str}" if sp_str else "")
        + (f" {or_str}" if or_str else "")
        + (f" trained by {trainer}" if trainer else "")
        + (f" ridden by {jockey}" if jockey else "")
        + (f" {rpd_str}" if rpd_str else "")
        + (f" — {velo_str}" if velo_str else "")
    )

    add_graph_fact(fact)


def write_trainer_session_summary(
    trainer: str,
    race_date: str,
    wins: int,
    runs: int,
    courses: list[str],
    notes: str = "",
):
    """
    Write a trainer session summary as a graph fact.
    Useful for VOX to recall trainer form across a day's racing without re-querying.
    """
    course_str = ", ".join(courses) if courses else "various"
    fact = (
        f"{trainer} had {wins} wins from {runs} runners on {race_date} "
        f"at {course_str}"
        + (f" — {notes}" if notes else "")
    )
    add_graph_fact(fact)
