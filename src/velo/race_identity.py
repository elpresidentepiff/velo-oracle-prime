"""Canonical race identity for FormFav-sourced (World / US) races.

One race is identified by ``(country, LOCAL racing date, track slug, race number)``. The local
racing date is the calendar date of the off in the race's own timezone, never the UTC date:
Remington Park R4 off 01:54 UTC on 13 Nov 2026 is a 12 Nov 2026 race (19:54 America/Chicago).

Incident #189: the live worker keyed races by the UTC date of the meetings query but fetched
each racecard with the race's local timezone, so for every US race off after 00:00 UTC the
stored race clock (``metadata``) belonged to one race and the field (``form_meta`` + runners)
to the race with the same number one racing day later. Both models then published picks for a
field that was not the race shown on the dashboard.

Pure functions only (no I/O, no clock unless passed in). Every consumer that shows, freezes,
settles or learns from a FormFav race asks :func:`verify_race_identity` first. Anything it
cannot prove is ``RACECARD_MISMATCH``: a visible block, never a guessed match.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VERIFIED = "VERIFIED"
RACECARD_MISMATCH = "RACECARD_MISMATCH"
BLOCKED_LABEL = "RACECARD MISMATCH — NO VERIFIED SELECTION"

# Off times move by minutes (late changes, a delayed card), never by a day. A gap this large
# between two sources for the same race key means they describe different races.
START_TIME_TOLERANCE = timedelta(minutes=45)
# Scratchings are declared through the day. A racecard last checked longer than this before the
# off (or before now, for a race still to run) cannot certify the field or its non-runners.
RACECARD_MAX_AGE = timedelta(hours=3)

# Hard failures: any one blocks the race from display, freezing, settlement and learning.
HARD_REASONS = frozenset({
    "KEY_MALFORMED",
    "KEY_DATE_CONFLICT",
    "MISSING_START_TIME",
    "MISSING_TIMEZONE",
    "RACE_DATE_COLLISION",
    "START_TIME_CONFLICT",
    "FORM_DATE_CONFLICT",
    "RACE_NUMBER_CONFLICT",
    "RACECARD_MISSING",
    "RUNNERS_MISSING",
    "RUNNER_ID_COLLISION",
    "RACECARD_STALE",
})

_KEY = re.compile(r"^formfav:(?P<country>[a-z]{2,3}):(?P<date>\d{4}-\d{2}-\d{2}):(?P<slug>[a-z0-9_]+):r(?P<race>\d+)$")
_NAME_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def slugify(slug: Any) -> str:
    """The one slug normaliser (was duplicated in the worker, the cache client and the adapter)."""
    return re.sub(r"[^a-z0-9]+", "_", str(slug or "").lower()).strip("_")


def canonical_race_key(country: str, local_race_date: str, slug: str, race_no: int) -> str:
    return f"formfav:{str(country).lower()}:{local_race_date}:{slugify(slug)}:r{int(race_no)}"


def parse_race_key(key: Any) -> dict[str, Any] | None:
    m = _KEY.match(str(key or ""))
    if not m:
        return None
    return {"country": m["country"], "race_date": m["date"], "slug": m["slug"], "race_number": int(m["race"])}


def parse_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace(" ", "T", 1))
        except ValueError:
            return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)


def _zone(tz_name: Any) -> ZoneInfo | None:
    if not tz_name:
        return None
    try:
        return ZoneInfo(str(tz_name))
    except (ZoneInfoNotFoundError, ValueError):
        return None


def local_race_date(start_utc: Any, tz_name: Any) -> str | None:
    """Calendar date of the off in the race's own timezone (the racing date), or None."""
    off = parse_utc(start_utc)
    zone = _zone(tz_name)
    if off is None or zone is None:
        return None
    return off.astimezone(zone).date().isoformat()


def name_key(name: Any) -> str:
    """Match a horse across providers: drop a trailing country/state tag, keep letters and digits."""
    return re.sub(r"[^a-z0-9]+", "", _NAME_SUFFIX.sub("", str(name or "")).lower())


def _int(value: Any) -> int | None:
    try:
        return None if value is None or value == "" else int(value)
    except (TypeError, ValueError):
        return None


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _runner_rows(runners: Any) -> list[dict[str, Any]]:
    """Accept ``formfav_runner_form`` rows or raw provider runner dicts."""
    out = []
    for r in runners or []:
        if not isinstance(r, dict):
            continue
        payload = _obj(r.get("form_payload"))
        number = _int(r.get("runner_number", r.get("number", payload.get("number"))))
        name = r.get("horse_name") or r.get("name") or payload.get("name")
        scratched = r.get("scratched", payload.get("scratched"))
        out.append({
            "number": number,
            "name": str(name) if name else None,
            "scratched": bool(scratched),
            "updated_at": r.get("updated_at"),
        })
    return out


def verify_race_identity(
    race: dict[str, Any],
    runners: Any = None,
    *,
    now: datetime | None = None,
    require_fresh_racecard: bool = True,
) -> dict[str, Any]:
    """Prove that a stored race's clock, racecard and runner list all describe one race.

    ``race`` is a ``formfav_races`` row (``provider_race_key``, ``race_date``, ``start_time``,
    ``timezone``, ``race_number``, ``metadata`` = meetings entry, ``form_meta`` = racecard header,
    optionally ``racecard_checked_at``). ``runners`` are ``formfav_runner_form`` rows.

    Returns ``status`` VERIFIED or RACECARD_MISMATCH, every reason found (hard reasons block,
    warnings do not), the local racing date and UTC off the race is identified by, the active
    field and the non-runners.
    """
    now = now or datetime.now(UTC)
    reasons: list[str] = []
    warnings: list[str] = []
    key = race.get("provider_race_key")
    parsed = parse_race_key(key)
    meta = _obj(race.get("metadata"))
    meta = _obj(meta.get("meeting_race")) or meta  # older rows nested the meeting race
    form = _obj(race.get("form_meta"))

    if parsed is None:
        reasons.append("KEY_MALFORMED")
    key_date = parsed["race_date"] if parsed else None
    if parsed and race.get("race_date") and str(race.get("race_date"))[:10] != key_date:
        reasons.append("KEY_DATE_CONFLICT")

    if not form:
        reasons.append("RACECARD_MISSING")

    form_start = parse_utc(form.get("startTime"))
    meta_start = parse_utc(meta.get("startTime"))
    col_start = parse_utc(race.get("start_time"))
    off = form_start or meta_start or col_start
    if off is None:
        reasons.append("MISSING_START_TIME")
    starts = [s for s in (form_start, meta_start, col_start) if s is not None]
    if starts and max(starts) - min(starts) > START_TIME_TOLERANCE:
        reasons.append("START_TIME_CONFLICT")
    elif starts and max(starts) != min(starts):
        warnings.append("OFF_TIME_MOVED")

    tz = form.get("timezone") or race.get("timezone") or meta.get("timezone")
    local_date = local_race_date(off, tz)
    if _zone(tz) is None:
        reasons.append("MISSING_TIMEZONE")
    elif key_date and local_date and local_date != key_date:
        reasons.append("RACE_DATE_COLLISION")
    # Each source's own clock must land on the key's racing date too.
    if key_date and _zone(tz) is not None:
        for s in (meta_start, col_start):
            d = local_race_date(s, tz)
            if d and d != key_date and "RACE_DATE_COLLISION" not in reasons:
                reasons.append("RACE_DATE_COLLISION")

    form_date = form.get("date")
    if form_date and key_date and str(form_date)[:10] != key_date:
        reasons.append("FORM_DATE_CONFLICT")
    key_race = parsed["race_number"] if parsed else _int(race.get("race_number"))
    for n in (_int(form.get("raceNumber")), _int(meta.get("raceNumber")), _int(race.get("race_number"))):
        if n is not None and key_race is not None and n != key_race:
            reasons.append("RACE_NUMBER_CONFLICT")
            break

    # Class and runner count differ between the meetings list and the racecard even for the same
    # race (abbreviated class names, scratchings), so they are recorded, not used to block.
    if meta.get("numberOfRunners") is not None and form.get("numberOfRunners") is not None \
            and _int(meta.get("numberOfRunners")) != _int(form.get("numberOfRunners")):
        warnings.append("RUNNER_COUNT_DIFFERS")
    if meta.get("raceClass") and form.get("raceClass") and meta.get("raceClass") != form.get("raceClass"):
        warnings.append("RACE_CLASS_DIFFERS")

    rows = _runner_rows(runners if runners is not None else form.get("runners"))
    if not rows:
        reasons.append("RUNNERS_MISSING")
    numbers = [r["number"] for r in rows]
    names = [name_key(r["name"]) for r in rows]
    if rows and (None in numbers or not all(names)
                 or len(set(numbers)) != len(numbers) or len(set(names)) != len(names)):
        reasons.append("RUNNER_ID_COLLISION")
    active = [{"number": r["number"], "name": r["name"]} for r in rows if not r["scratched"]]
    non_runners = [{"number": r["number"], "name": r["name"]} for r in rows if r["scratched"]]
    if rows and not active:
        reasons.append("RUNNERS_MISSING")

    checked = [t for t in (parse_utc(race.get("racecard_checked_at")),
                           *(parse_utc(r["updated_at"]) for r in rows)) if t is not None]
    checked_at = max(checked) if checked else None
    if require_fresh_racecard and off is not None:
        ref = min(now, off)
        if checked_at is None or ref - checked_at > RACECARD_MAX_AGE:
            reasons.append("RACECARD_STALE")

    reasons = list(dict.fromkeys(reasons))
    hard = [r for r in reasons if r in HARD_REASONS]
    return {
        "provider_race_key": key,
        "status": RACECARD_MISMATCH if hard else VERIFIED,
        "reasons": reasons,
        "warnings": warnings,
        "local_race_date": local_date,
        "start_time_utc": off.isoformat() if off else None,
        "timezone": tz,
        "race_number": key_race,
        "field_size": len(rows),
        "active_runners": active,
        "non_runners": non_runners,
        "racecard_checked_at": checked_at.isoformat() if checked_at else None,
        "label": BLOCKED_LABEL if hard else None,
    }


def verify_selection(identity: dict[str, Any], pick_name: Any, pick_number: Any = None) -> dict[str, Any]:
    """Decide whether one model's pick may be shown as a selection for the verified race.

    A pick on an unverified race, a non-runner, or a horse not in the verified field is blocked.
    The original pick is returned under ``original_pick`` for audit and learning, never shown.
    """
    original = {"name": pick_name, "number": _int(pick_number)}
    if not pick_name:
        return {"status": "NO_PICK", "selection": None, "original_pick": original, "label": None}
    if identity.get("status") != VERIFIED:
        return {"status": RACECARD_MISMATCH, "selection": None, "original_pick": original,
                "reasons": identity.get("reasons") or [], "label": BLOCKED_LABEL}
    want = name_key(pick_name)
    number = _int(pick_number)

    def same(r: dict[str, Any]) -> bool:
        return name_key(r.get("name")) == want and (number is None or r.get("number") == number)

    if any(same(r) for r in identity.get("non_runners") or []):
        return {"status": "NON_RUNNER", "selection": None, "original_pick": original,
                "reasons": ["PICK_IS_NON_RUNNER"], "label": BLOCKED_LABEL}
    match = [r for r in identity.get("active_runners") or [] if same(r)]
    if len(match) != 1:
        return {"status": "NOT_IN_FIELD", "selection": None, "original_pick": original,
                "reasons": ["PICK_NOT_IN_VERIFIED_FIELD"], "label": BLOCKED_LABEL}
    return {"status": VERIFIED, "selection": match[0], "original_pick": original, "reasons": [], "label": None}
