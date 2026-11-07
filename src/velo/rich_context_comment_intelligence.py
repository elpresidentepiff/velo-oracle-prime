"""Time-safe Racing Post Spotlight facts for the Rich Context shadow lane.

This module deliberately does *not* score, rank, route, or select a runner.  It
turns pre-off Spotlight prose into versioned factual evidence that a separate
shadow challenger may consume later.  Tip/verdict language is rejected at the
sentence boundary so an opinion cannot leak through a neighbouring factual
phrase.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

FEATURE_SCHEMA_VERSION = "rp_spotlight_facts_v1"
PARSER_VERSION = "rich_context_comment_v1"
SOURCE = "racing_post_spotlight"

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\s+[|]\s+")

# An entire sentence is excluded when it contains any of these expressions.
# This is intentionally conservative: losing a factual phrase is preferable to
# allowing a Racing Post opinion/selection to become a model feature.
_OPINION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:the )?selection\b",
        r"\bnap\b|\bnext best\b|\bbest bet\b",
        r"\bgets? the vote\b|\bis preferred\b|\bpreference is\b",
        r"\bshould win\b|\bcan win\b|\bcould win\b|\blikely winner\b",
        r"\bone to beat\b|\bmain danger\b|\bleading contender\b",
        r"\b(?:strongly )?fancied\b|\bexpected to (?:win|score|go close)\b",
        r"\bappeals most\b|\bbig chance\b|\bworth a bet\b",
        r"\bforecast\b|\bprediction\b|\brecommend(?:ed|ation)?\b",
        r"\bclaims?\b|\bshould go well\b|\bshortlist(?:ed)?\b",
        r"\b(?:respected|feared|a player|player in this)\b",
        r"\b(?:likely|likeliest|probable) winner\b|\bmost likely\b",
        r"\b(?:each[ -]way|place) (?:chance|claims?|bet)\b",
        r"\b(?:may|might) win\b|\bhas (?:a |every )?chance\b",
        r"\binteresting\b|\bwell[ -]treated\b|\bconsider(?:ed|ation)?\b",
        r"\bnot ruled out\b|\bcannot be ruled out\b|\bnot without a chance\b",
    )
)

# Only explicitly enumerated factual families are emitted.  Matching is kept
# narrow and evidence text is retained so every derived flag is auditable.
_FACT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "pace_and_running_style": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bmade (?:all|the running)\b", r"\bled\b", r"\bprominent\b",
            r"\btracked (?:the )?(?:leader|pace)\b", r"\bheld up\b",
            r"\bslowly away\b", r"\bmissed the break\b", r"\braced (?:freely|keenly)\b",
            r"\btravelled (?:strongly|well)\b",
        )
    ),
    "interference_and_trip": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bhampered\b", r"\b(?:short of|denied a) clear run\b",
            r"\bblocked\b", r"\bbumped\b", r"\bstumbled\b",
            r"\b(?:ran|hung) (?:wide|left|right)\b", r"\bswitched\b",
        )
    ),
    "jumping_and_behaviour": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bmade (?:a |several )?mistakes?\b", r"\bblundered\b",
            r"\bjumped (?:left|right|poorly|well)\b", r"\brefused\b",
            r"\bpulled hard\b", r"\bidled\b", r"\bhung (?:left|right)\b",
        )
    ),
    "finish_profile": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bstayed on\b", r"\bkept on\b", r"\bran on\b",
            r"\bweakened\b", r"\bfaded\b", r"\bfinished strongly\b",
            r"\bno extra\b",
        )
    ),
    "conditions_and_course": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bcourse winner\b", r"\bcourse-and-distance winner\b",
            r"\bwon here\b", r"\bproven (?:at|over|on)\b",
            r"\b(?:acts|effective) on (?:soft|heavy|good|firm|all-weather)\b",
            r"\b(?:up|down|back) in trip\b", r"\b(?:up|down) in class\b",
            r"\bfirst run (?:at|on|over)\b",
        )
    ),
    "fitness_and_recency": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\breappearance\b", r"\breturn(?:ed|ing)? from (?:a )?break\b",
            r"\bafter \d+ days? off\b", r"\bseasonal debut\b",
            r"\bsecond run after (?:a )?break\b",
        )
    ),
    "equipment_and_procedure": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bfirst-time (?:blinkers|visor|cheekpieces|hood|tongue-tie)\b",
            r"\b(?:blinkers|visor|cheekpieces|hood|tongue-tie) (?:retained|removed|return)\b",
            r"\bwind (?:operation|surgery)\b", r"\bgelded\b",
        )
    ),
    "connections_and_campaign": tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bfirst run for (?:the )?(?:yard|trainer)\b",
            r"\bdebut for (?:the )?(?:yard|trainer)\b",
            r"\b(?:jockey|rider) (?:returns|back aboard)\b",
            r"\bmaking (?:his|her|their) handicap debut\b",
        )
    ),
}


def _as_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def resolve_race_off_time_utc(race: dict[str, Any]) -> datetime | None:
    """Resolve canonical off time without guessing from a different date."""
    raw = race.get("_raw") if isinstance(race.get("_raw"), dict) else {}
    for key in ("off_time_utc", "scheduled_off", "off_dt", "start_time"):
        parsed = _as_utc(race.get(key) or raw.get(key))
        if parsed is not None:
            return parsed

    race_date = str(race.get("date") or raw.get("date") or "").strip()
    clock = _london_clock(str(race.get("off_time") or raw.get("off_time") or ""))
    if not race_date or clock is None:
        return None
    try:
        local = datetime.combine(
            date.fromisoformat(race_date[:10]), clock, tzinfo=ZoneInfo("Europe/London")
        )
    except ValueError:
        return None
    return local.astimezone(UTC)


_OFF_CLOCK_RE = re.compile(r"(\d{1,2})[:.](\d{2})")


def _london_clock(text: str) -> time | None:
    """Parse a card off time such as ``11.55``, ``3.25`` or ``15:25``.

    Racing Post prints afternoon and evening off times in 12-hour form with no
    am/pm (``3.25`` is 15:25) and no leading zero. UK and Irish cards never
    start before 10:00, so a one-digit hour is always pm. A two-digit hour is
    already on the 24-hour clock (``10``-``12`` are morning/noon, ``13``+ pm).
    """
    match = _OFF_CLOCK_RE.fullmatch(text.strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if len(match.group(1)) == 1:
        hour += 12
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _sentences(raw_text: str) -> Iterable[str]:
    for sentence in _SENTENCE_SPLIT_RE.split(raw_text.strip()):
        cleaned = " ".join(sentence.split()).strip()
        if cleaned:
            yield cleaned


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_factual_comment_evidence(raw_text: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return allowlisted factual spans and hashed rejection diagnostics."""
    facts: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for sentence in _sentences(raw_text):
        if any(pattern.search(sentence) for pattern in _OPINION_PATTERNS):
            rejected.append({"reason": "OPINION_OR_SELECTION", "span_sha256": _sha256(sentence)})
            continue
        for family, patterns in _FACT_PATTERNS.items():
            matches = sorted({m.group(0).lower() for pattern in patterns for m in pattern.finditer(sentence)})
            if matches:
                facts.append(
                    {
                        "family": family,
                        "evidence_text": sentence,
                        "matched_phrases": matches,
                        "evidence_sha256": _sha256(sentence),
                    }
                )
    return facts, rejected


def build_runner_comment_shadow(
    *,
    raw_text: str,
    race_id: str,
    horse_id: str,
    horse_name: str,
    captured_at: datetime | str | None,
    off_time_utc: datetime | str | None,
) -> dict[str, Any]:
    """Build one immutable-in-shape shadow feature packet for a runner."""
    raw_source_text = str(raw_text or "")
    text = " ".join(raw_source_text.split()).strip()
    captured = _as_utc(captured_at)
    off = _as_utc(off_time_utc)
    captured_before_off = bool(captured and off and captured < off)
    identity_eligible = bool(str(race_id).strip() and str(horse_id).strip())
    facts, rejected = extract_factual_comment_evidence(text) if text else ([], [])
    families = sorted({fact["family"] for fact in facts})

    reasons: list[str] = []
    if not text:
        reasons.append("MISSING_COMMENT")
    if captured is None:
        reasons.append("MISSING_CAPTURE_TIME")
    if off is None:
        reasons.append("MISSING_OFF_TIME")
    elif captured is not None and not captured_before_off:
        reasons.append("NOT_CAPTURED_PRE_OFF")
    if not identity_eligible:
        reasons.append("UNPROVEN_IDENTITY")
    if text and not facts:
        reasons.append("NO_ALLOWLISTED_FACTS")

    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "source": SOURCE,
        "race_id": str(race_id or ""),
        "horse_id": str(horse_id or ""),
        "horse_name": str(horse_name or ""),
        "captured_at": captured.isoformat() if captured else None,
        "off_time_utc": off.isoformat() if off else None,
        "captured_before_off": captured_before_off,
        "identity_eligible": identity_eligible,
        "raw_text_sha256": _sha256(raw_source_text) if raw_source_text else None,
        "normalized_text_sha256": _sha256(text) if text else None,
        "factual_spans": facts,
        "rejected_spans": rejected,
        "feature_families": families,
        "family_counts": {family: sum(1 for fact in facts if fact["family"] == family) for family in families},
        "training_eligible": not reasons,
        "ineligibility_reasons": reasons,
        "production_prime_consumed": False,
        "provider_prediction_consumed": False,
    }


def build_race_comment_shadow_packet(
    race: dict[str, Any],
    *,
    captured_at: datetime | str | None,
    off_time_utc: datetime | str | None = None,
) -> dict[str, Any]:
    """Build runner packets without mutating the canonical Prime race input."""
    race_id = str(race.get("race_id") or "")
    resolved_off = _as_utc(off_time_utc) or resolve_race_off_time_utc(race)
    runners = []
    for runner in race.get("runners") or []:
        runners.append(
            build_runner_comment_shadow(
                raw_text=runner.get("spotlight") or "",
                race_id=race_id,
                horse_id=str(runner.get("horse_id") or ""),
                horse_name=str(runner.get("horse_name") or ""),
                captured_at=captured_at,
                off_time_utc=resolved_off,
            )
        )
    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "parser_version": PARSER_VERSION,
        "source": SOURCE,
        "race_id": race_id,
        "captured_at": _as_utc(captured_at).isoformat() if _as_utc(captured_at) else None,
        "off_time_utc": resolved_off.isoformat() if resolved_off else None,
        "runners": runners,
        "runner_count": len(runners),
        "eligible_runner_count": sum(1 for item in runners if item["training_eligible"]),
        "production_prime_consumed": False,
    }


def attach_comment_shadow_by_horse_id(
    predictions: list[dict[str, Any]],
    race_packet: dict[str, Any],
) -> int:
    """Attach packets after Prime returns using prediction horse IDs only.

    Missing or duplicate packet identities fail closed to ``None``.  Horse names
    are never consulted, so duplicate and punctuation-variant names cannot bind
    evidence to the wrong prediction.
    """
    by_id: dict[str, dict[str, Any]] = {}
    duplicate_ids: set[str] = set()
    for item in race_packet.get("runners") or []:
        horse_id = str(item.get("horse_id") or "").strip()
        if not horse_id:
            continue
        if horse_id in by_id:
            duplicate_ids.add(horse_id)
            continue
        by_id[horse_id] = item
    for horse_id in duplicate_ids:
        by_id.pop(horse_id, None)

    attached = 0
    for prediction in predictions:
        horse_id = str(prediction.get("horse_id") or "").strip()
        packet = by_id.get(horse_id) if horse_id else None
        prediction["rich_context_comment_shadow"] = packet
        attached += int(packet is not None)
    return attached
