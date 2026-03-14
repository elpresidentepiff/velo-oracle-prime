"""
VÉLØ PRIME — Spotlight Comment Parser
======================================
NLP extraction pass for per-horse spotlight comments.

Reads raw spotlight text, detects trigger phrases, populates boolean signal flags,
calculates a sentiment score, and returns a structured dict ready for insertion
into the `horse_comments` Supabase table.

Architecture spec: docs/VELO_SPOTLIGHT_ARCHITECTURE.md
"""

import re
import os
import logging
from typing import Optional
from datetime import date

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FLAG TRIGGER PATTERNS
# Each key maps to a list of lowercase trigger phrases.
# Any match → flag set to True.
# ---------------------------------------------------------------------------

FLAG_PATTERNS: dict[str, list[str]] = {
    "flag_intent_today": [
        "brought here for this",
        "today is the day",
        "with this race in mind",
        "targeted at this",
        "connections have had this race in mind",
        "peaking today",
        "saved for this",
        "every chance of",
        "ideal opening",
        "found the ideal",
    ],
    "flag_excuse_last": [
        "forgiven",
        "excused",
        "unsuitable ground",
        "wrong trip",
        "not his true running",
        "slowly run",
        "hampered",
        "bad luck",
        "never travelled",
        "ignore last",
        "valid excuse",
        "swerving to avoid",
        "quicker conditions",
        "wrong ground",
        "not her true running",
    ],
    "flag_stamina_risk": [
        "stamina question",
        "may not stay",
        "short of stamina",
        "trip may stretch",
        "stamina unproven",
        "too keen",
        "pulls hard",
        "races freely",
        "can be too keen",
        "needs to settle",
        "settle better",
    ],
    "flag_stamina_pos": [
        "assured stayer",
        "loves the trip",
        "stays well",
        "suited by the distance",
        "proven stayer",
        "thorough stayer",
        "loves testing ground",
        "upped to 3m",
        "upped in trip",
        "suited by further",
        "thorough stayer",
        "stays this trip",
    ],
    "flag_behaviour": [
        "keen",
        "pulls hard",
        "races freely",
        "makes mistakes",
        "lazy",
        "can be wayward",
        "tends to idle",
        "rarely makes life easy",
        "all or nothing",
    ],
    "flag_jockey_note": [
        "jockey",
        "rider",
        "claim",
        "claimer",
        "booking",
        "first-choice",
        "retained",
        "returns to the saddle",
    ],
    "flag_trainer_note": [
        "trainer",
        "yard",
        "stable",
        "connections",
        "handler",
        "won this race last",
        "won here last",
        "strike rate",
    ],
    "flag_ground_suit": [
        "soft ground",
        "heavy ground",
        "good ground",
        "going suits",
        "loves soft",
        "loves heavy",
        "handles the ground",
        "ground in his favour",
        "ground suits",
        "in his element",
        "in her element",
    ],
    "flag_trip_suit": [
        "trip suits",
        "loves this trip",
        "suited by",
        "back to his best trip",
        "back to her best trip",
        "right distance",
        "ideal distance",
        "optimum trip",
        "best over",
    ],
    "flag_peak_timing": [
        "may well peak",
        "peaking now",
        "peak performance due",
        "right time",
        "conditions ideal",
        "everything in place",
        "found the ideal opening",
        "ideal conditions",
    ],
    "flag_danger": [
        "main danger",
        "could upset",
        "danger to all",
        "biggest threat",
        "not without a chance",
        "could spring a surprise",
        "capable of better",
    ],
    "flag_setup_run": [
        "come on for the run",
        "improve for the run",
        "needed the outing",
        "fitness run",
        "educational",
        "blow away the cobwebs",
        "needed that run",
        "will come on",
    ],
    "flag_market_note": [
        "well supported",
        "market support",
        "market confidence",
        "backed",
        "drifted",
        "firmed",
        "market move",
        "market will guide",
        "watch the market",
        "market suggests",
    ],
    "flag_course_form": [
        "course winner",
        "course and distance",
        "c&d",
        "c & d",
        "won here",
        "course form",
        "knows the track",
        "won at this track",
        "previous course win",
        "course record",
    ],
    "flag_pji_signal": [
        "better than the bare result",
        "shaped well",
        "showed promise",
        "more to offer",
        "not asked for everything",
        "hands and heels",
        "never knocked about",
        "went in snatches",
        "travelled strongly",
        "travelled well",
        "evidently felt capable",
        "capable of better",
        "not knocked about",
        "shaped better",
        "more in the locker",
    ],
}

# ---------------------------------------------------------------------------
# SENTIMENT WORD LISTS
# Simple positive/negative word weighting for sentiment score (-2 to +2).
# ---------------------------------------------------------------------------

POSITIVE_WORDS = [
    "ideal", "dominant", "progressive", "won", "winner", "winning",
    "excellent", "impressive", "strong", "capable", "proven", "confirmed",
    "well", "suited", "loves", "thrives", "consistent", "reliable",
    "promising", "interesting", "chance", "danger", "could", "should",
    "best", "top", "leading", "favourite", "confident",
]

NEGATIVE_WORDS = [
    "concern", "question", "doubt", "risk", "unreliable", "weak",
    "poor", "failed", "pulled up", "fell", "unseated", "mistake",
    "errors", "inconsistent", "disappointing", "beaten", "outclassed",
    "too high", "overpriced", "copper", "trap", "fade", "avoid",
    "stamina question", "may not stay", "too keen", "pulls hard",
]


# ---------------------------------------------------------------------------
# CORE EXTRACTION FUNCTION
# ---------------------------------------------------------------------------

def extract_spotlight_signals(
    raw_text: str,
    horse_name: str,
    race_id: str,
    race_date: date,
    source: str = "Spotlight",
    horse_id: Optional[str] = None,
) -> dict:
    """
    Parse a raw spotlight comment and extract all VÉLØ signal flags.

    Args:
        raw_text:   The full unedited spotlight comment for this horse.
        horse_name: Horse name (used for logging and output).
        race_id:    Race identifier string e.g. "2026-03-14-FONTWELL-R3".
        race_date:  Date of the race.
        source:     Data source label e.g. "Spotlight", "Post", "RacingTV".
        horse_id:   Optional FK to horses table.

    Returns:
        dict ready for insertion into `horse_comments` Supabase table.
    """
    if not raw_text or not raw_text.strip():
        logger.warning(f"Empty spotlight text for {horse_name} in {race_id}")
        return _empty_record(horse_name, race_id, race_date, source, horse_id)

    text_lower = raw_text.lower()

    # --- Extract boolean flags ---
    flags = {}
    fired_flags = []
    for flag_name, phrases in FLAG_PATTERNS.items():
        matched = any(phrase in text_lower for phrase in phrases)
        flags[flag_name] = matched
        if matched:
            fired_flags.append(flag_name)

    # --- Calculate sentiment score ---
    sentiment = _calculate_sentiment(text_lower)

    # --- Build output record ---
    record = {
        "race_id": race_id,
        "horse_name": horse_name,
        "horse_id": horse_id,
        "race_date": str(race_date),
        "source": source,
        "raw_text": raw_text.strip(),
        **flags,
        "sentiment_score": sentiment,
    }

    # --- Log summary ---
    if fired_flags:
        logger.info(
            f"[{race_id}] {horse_name}: {len(fired_flags)} flags fired — "
            f"{', '.join(fired_flags)} | sentiment={sentiment}"
        )
    else:
        logger.debug(f"[{race_id}] {horse_name}: no flags fired | sentiment={sentiment}")

    return record


def _calculate_sentiment(text_lower: str) -> int:
    """
    Calculate a simple sentiment score from -2 to +2.
    Counts positive and negative word matches and normalises.
    """
    pos_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    neg_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)

    net = pos_count - neg_count

    if net >= 4:
        return 2
    elif net >= 2:
        return 1
    elif net <= -4:
        return -2
    elif net <= -2:
        return -1
    else:
        return 0


def _empty_record(horse_name, race_id, race_date, source, horse_id) -> dict:
    """Return an empty record with all flags False and sentiment 0."""
    return {
        "race_id": race_id,
        "horse_name": horse_name,
        "horse_id": horse_id,
        "race_date": str(race_date),
        "source": source,
        "raw_text": "",
        **{flag: False for flag in FLAG_PATTERNS},
        "sentiment_score": 0,
    }


# ---------------------------------------------------------------------------
# SCORE MODIFIERS
# Maps extracted flags to score adjustments in the VÉLØ engine layers.
# ---------------------------------------------------------------------------

def get_pji_modifiers(record: dict) -> dict:
    """
    Return PJI component adjustments based on spotlight flags.
    These are added to the relevant PJI component scores.
    """
    modifiers = {
        "concealed_effort_bonus": 0,
        "setup_mismatch_bonus": 0,
        "release_day_bonus": 0,
    }

    if record.get("flag_pji_signal"):
        modifiers["concealed_effort_bonus"] += 4   # "never knocked about" etc.

    if record.get("flag_excuse_last"):
        modifiers["setup_mismatch_bonus"] += 5     # valid excuse validates mismatch

    if record.get("flag_intent_today") and record.get("flag_trip_suit"):
        modifiers["release_day_bonus"] += 3        # intent + trip alignment

    if record.get("flag_peak_timing"):
        modifiers["release_day_bonus"] += 3        # peak timing signal

    return modifiers


def get_stamina_modifiers(record: dict) -> int:
    """
    Return stamina score adjustment based on spotlight flags.
    Positive = stayer confirmation. Negative = stamina risk.
    """
    modifier = 0

    if record.get("flag_stamina_pos"):
        modifier += 10   # confirmed stayer language

    if record.get("flag_stamina_risk"):
        modifier -= 10   # stamina question raised

    if record.get("flag_behaviour"):
        # "too keen" / "pulls hard" is a stamina risk in staying races
        modifier -= 5

    return modifier


def get_day_type_push(record: dict) -> str:
    """
    Return a push signal for the Day Classification Engine.
    Returns: "CASH", "SETUP", "DISGUISE", or "NEUTRAL"
    """
    cash_signals = (
        record.get("flag_intent_today", False) +
        record.get("flag_peak_timing", False) +
        record.get("flag_ground_suit", False) +
        record.get("flag_trip_suit", False)
    )

    setup_signals = (
        record.get("flag_setup_run", False) +
        (record.get("sentiment_score", 0) < 0)
    )

    if cash_signals >= 2:
        return "CASH"
    elif setup_signals >= 2:
        return "SETUP"
    else:
        return "NEUTRAL"


def get_survivability_modifier(record: dict) -> int:
    """
    Return survivability score adjustment based on spotlight flags.
    """
    modifier = 0

    if record.get("flag_stamina_pos"):
        modifier += 5

    if record.get("flag_behaviour"):
        modifier -= 5   # erratic behaviour reduces survivability

    if record.get("flag_stamina_risk"):
        modifier -= 5

    if record.get("flag_course_form"):
        modifier += 5   # course experience is a survivability positive

    return modifier


def format_output_tags(record: dict) -> list[str]:
    """
    Generate the VÉLØ output tags for a horse based on fired flags.
    These are appended to the horse's entry in the Strike Recommendations report.
    """
    tags = []

    if record.get("flag_pji_signal"):
        tags.append("[SPOTLIGHT FLAG: flag_pji_signal — concealed effort language detected]")

    if record.get("flag_excuse_last"):
        tags.append("[SPOTLIGHT FLAG: flag_excuse_last — valid excuse for last run]")

    if record.get("flag_stamina_risk"):
        tags.append("[SPOTLIGHT FLAG: flag_stamina_risk — stamina question raised, Stamina Score -10]")

    if record.get("flag_stamina_pos"):
        tags.append("[SPOTLIGHT FLAG: flag_stamina_pos — stayer confirmation, Stamina Score +10]")

    if record.get("flag_peak_timing"):
        tags.append("[SPOTLIGHT FLAG: flag_peak_timing — peak timing signal, DAY_TYPE pushed toward CASH]")

    if record.get("flag_setup_run"):
        tags.append("[SPOTLIGHT FLAG: flag_setup_run — setup run language, DAY_TYPE pushed toward SETUP]")

    if record.get("flag_intent_today"):
        tags.append("[SPOTLIGHT FLAG: flag_intent_today — intent confirmation, TIE engine boost]")

    if record.get("flag_behaviour"):
        tags.append("[SPOTLIGHT FLAG: flag_behaviour — behavioural concern noted, Survivability -5]")

    if record.get("flag_trainer_note"):
        tags.append("[SPOTLIGHT FLAG: flag_trainer_note — trainer pattern signal detected]")

    if record.get("flag_course_form"):
        tags.append("[SPOTLIGHT FLAG: flag_course_form — course/distance evidence confirmed]")

    if record.get("flag_danger"):
        tags.append("[SPOTLIGHT FLAG: flag_danger — danger signal, Chaos Engine widening trigger]")

    sentiment = record.get("sentiment_score", 0)
    if sentiment <= -2:
        tags.append("[SPOTLIGHT SENTIMENT: -2 — strong negative. Structural warning on short-priced horse.]")
    elif sentiment == -1:
        tags.append("[SPOTLIGHT SENTIMENT: -1 — negative lean.]")

    return tags


# ---------------------------------------------------------------------------
# BATCH PROCESSING
# ---------------------------------------------------------------------------

def process_race_comments(
    comments: list[dict],
    race_id: str,
    race_date: date,
    source: str = "Spotlight",
) -> list[dict]:
    """
    Process a list of per-horse comment dicts for a single race.

    Each input dict must have:
        - horse_name: str
        - raw_text: str
        - horse_id: str (optional)

    Returns a list of extracted signal records ready for Supabase insertion.
    """
    results = []
    for comment in comments:
        record = extract_spotlight_signals(
            raw_text=comment.get("raw_text", ""),
            horse_name=comment.get("horse_name", "Unknown"),
            race_id=race_id,
            race_date=race_date,
            source=source,
            horse_id=comment.get("horse_id"),
        )
        results.append(record)
    return results


# ---------------------------------------------------------------------------
# SUPABASE WRITE (requires SUPABASE_URL and SUPABASE_KEY env vars)
# ---------------------------------------------------------------------------

def write_to_supabase(records: list[dict]) -> bool:
    """
    Write extracted spotlight records to the horse_comments Supabase table.
    Returns True on success, False on failure.
    """
    try:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            logger.error("SUPABASE_URL or SUPABASE_KEY not set. Cannot write spotlight records.")
            return False

        client = create_client(url, key)
        response = client.table("horse_comments").insert(records).execute()

        if response.data:
            logger.info(f"Wrote {len(response.data)} spotlight records to Supabase.")
            return True
        else:
            logger.error(f"Supabase insert returned no data: {response}")
            return False

    except Exception as e:
        logger.error(f"Failed to write spotlight records to Supabase: {e}")
        return False


# ---------------------------------------------------------------------------
# CLI ENTRY POINT (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # Example: Rip Wheeler from Fontwell R3 14 March 2026
    test_comments = [
        {
            "horse_name": "Rip Wheeler",
            "raw_text": (
                "Never travelled after swerving to avoid a faller at Wincanton. "
                "Prior to that he won at Leicester on soft ground and had a valid excuse at Sandown. "
                "First-time cheekpieces today. Moore yard won this race last spring with a 6yo. "
                "Every chance of bouncing back."
            ),
        },
        {
            "horse_name": "Godot",
            "raw_text": (
                "Always tended to be all or nothing but has often run well on soft ground. "
                "Last two pulls-up were on unsuitable ground — not his true running. "
                "Waited for Godot to tackle this sort of trip on soft ground. "
                "Blinkers switch from cheekpieces. Capable of popping up."
            ),
        },
        {
            "horse_name": "Cayman Dancer",
            "raw_text": (
                "Pulls hard in both hurdle runs. Needs to settle better. "
                "Stamina question on soft ground at this trip. "
                "Talented but can be too keen for his own good."
            ),
        },
    ]

    results = process_race_comments(
        comments=test_comments,
        race_id="2026-03-14-FONTWELL-R3",
        race_date=date(2026, 3, 14),
    )

    for r in results:
        print(f"\n=== {r['horse_name']} ===")
        fired = [k for k, v in r.items() if k.startswith("flag_") and v is True]
        print(f"Flags fired: {fired}")
        print(f"Sentiment: {r['sentiment_score']}")
        print(f"Day type push: {get_day_type_push(r)}")
        print(f"PJI modifiers: {get_pji_modifiers(r)}")
        print(f"Stamina modifier: {get_stamina_modifiers(r)}")
        print("Output tags:")
        for tag in format_output_tags(r):
            print(f"  {tag}")


# ---------------------------------------------------------------------------
# SPOTLIGHT GATE
# Enforces the hard architectural rule:
#   "A spotlight comment cannot generate a selection. It can only modify one."
#
# Doctrine: docs/VELO_SPOTLIGHT_HARD_LIMITS.md
# ---------------------------------------------------------------------------

# Minimum structural score a runner must achieve before spotlight modifiers
# are permitted to apply. Runners below this threshold are structurally
# unqualified and spotlight flags are discarded entirely.
STRUCTURAL_GATE_THRESHOLD = 40  # out of 100

# Regime block tags that permanently suppress spotlight modifier application.
# These blocks cannot be lifted by any spotlight signal.
REGIME_BLOCK_TAGS = {
    "TS_DISTANCE_INVALID",
    "STAMINA: LIKELY NON-STAYER",
    "DISGUISE",
    "QUARANTINE",
}


class SpotlightGate:
    """
    Enforces the spotlight hard limits rule at the code level.

    Usage in orchestrator (Step 3 of integration sequence):

        gate = SpotlightGate()
        for runner in preliminary_chassis:
            spotlight_record = spotlight_records.get(runner["horse_name"])
            if spotlight_record:
                gate.apply_modifiers(runner, spotlight_record)
    """

    def __init__(self, threshold: int = STRUCTURAL_GATE_THRESHOLD):
        self.threshold = threshold
        self._blocked_count = 0
        self._applied_count = 0

    def is_structurally_qualified(self, runner: dict) -> tuple[bool, str]:
        """
        Check whether a runner has passed the structural gate.

        Args:
            runner: Dict containing at minimum:
                - structural_score (int, 0-100): combined score from structural layers
                - regime_blocks (list[str]): any active regime block tags
                - in_preliminary_chassis (bool): whether runner qualified in Steps 1-2

        Returns:
            (qualified: bool, reason: str)
        """
        # Hard check 1: must be in the preliminary chassis from structural layers
        if not runner.get("in_preliminary_chassis", False):
            return False, "NOT_IN_STRUCTURAL_CHASSIS"

        # Hard check 2: no active regime blocks
        active_blocks = set(runner.get("regime_blocks", []))
        blocking = active_blocks & REGIME_BLOCK_TAGS
        if blocking:
            return False, f"REGIME_BLOCK_ACTIVE: {', '.join(blocking)}"

        # Hard check 3: structural score must meet minimum threshold
        structural_score = runner.get("structural_score", 0)
        if structural_score < self.threshold:
            return False, f"STRUCTURAL_SCORE_BELOW_GATE: {structural_score} < {self.threshold}"

        return True, "QUALIFIED"

    def apply_modifiers(self, runner: dict, spotlight_record: dict) -> dict:
        """
        Apply spotlight flag modifiers to a runner's scores — but ONLY if
        the runner passes the structural gate.

        If the runner does not qualify, modifiers are silently discarded
        and a SPOTLIGHT_BLOCKED log entry is written.

        Args:
            runner:           The runner dict (modified in-place).
            spotlight_record: Output from extract_spotlight_signals().

        Returns:
            The runner dict, potentially with modified scores and spotlight_tags.
        """
        qualified, reason = self.is_structurally_qualified(runner)

        if not qualified:
            self._blocked_count += 1
            logger.info(
                f"[SPOTLIGHT_BLOCKED] {runner.get('horse_name', 'Unknown')} — "
                f"spotlight modifiers discarded. Reason: {reason}"
            )
            runner.setdefault("spotlight_tags", [])
            runner["spotlight_tags"].append(
                f"[SPOTLIGHT_GATE: BLOCKED — {reason} — modifiers discarded]"
            )
            return runner

        # Runner is qualified — apply modifiers
        self._applied_count += 1

        # Apply PJI modifiers
        pji_mods = get_pji_modifiers(spotlight_record)
        runner["pji_concealed_effort"] = (
            runner.get("pji_concealed_effort", 0) + pji_mods["concealed_effort_bonus"]
        )
        runner["pji_setup_mismatch"] = (
            runner.get("pji_setup_mismatch", 0) + pji_mods["setup_mismatch_bonus"]
        )
        runner["pji_release_day"] = (
            runner.get("pji_release_day", 0) + pji_mods["release_day_bonus"]
        )

        # Apply stamina modifier
        stamina_mod = get_stamina_modifiers(spotlight_record)
        runner["stamina_score"] = runner.get("stamina_score", 0) + stamina_mod

        # Apply survivability modifier
        surv_mod = get_survivability_modifier(spotlight_record)
        runner["survivability_score"] = runner.get("survivability_score", 0) + surv_mod

        # Apply day type push (cannot SET day type — only push)
        day_push = get_day_type_push(spotlight_record)
        if day_push != "NEUTRAL":
            current_day_type = runner.get("day_type", "NEUTRAL")
            # Only push — do not override a DISGUISE classification
            if current_day_type not in ("DISGUISE",):
                runner["day_type_spotlight_push"] = day_push
                logger.debug(
                    f"[SPOTLIGHT_PUSH] {runner.get('horse_name')} — "
                    f"day_type push: {day_push} (current: {current_day_type})"
                )

        # Attach output tags (structural case must be written first — tags are annotations)
        output_tags = format_output_tags(spotlight_record)
        runner.setdefault("spotlight_tags", [])
        runner["spotlight_tags"].extend(output_tags)

        logger.info(
            f"[SPOTLIGHT_APPLIED] {runner.get('horse_name', 'Unknown')} — "
            f"{len(output_tags)} tags | stamina_mod={stamina_mod:+d} | "
            f"surv_mod={surv_mod:+d} | day_push={day_push}"
        )

        return runner

    def summary(self) -> dict:
        """Return a summary of gate activity for the current race."""
        return {
            "applied": self._applied_count,
            "blocked": self._blocked_count,
            "total": self._applied_count + self._blocked_count,
        }

    def reset(self):
        """Reset counters for a new race."""
        self._blocked_count = 0
        self._applied_count = 0
