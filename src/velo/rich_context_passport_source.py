"""Fail-closed factual passport evidence for the Rich Context shadow lane.

This module deliberately exposes a small, factual allow-list from the
``new_build_horse_passports`` archive.  The archive also contains free-text
and derived material; copying its opaque payload into a packet would make the
packet's provenance and as-of guarantees unclear.  A row without a durable
``persisted_at`` timestamp, or persisted after the race's pre-off cutoff, is
not eligible evidence.

Nothing here is imported by production Prime.  The returned payload is for
immutable Rich Context shadow packets only, and whether a fitted shadow model
uses that family is declared separately by its artifact metadata.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_FACTUAL_FIELDS = (
    "horse_rp_uid",
    "career_runs",
    "wins",
    "win_rate",
    "last_run_date",
    "source_sha256",
    "persisted_at",
)


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse a persisted timestamp as UTC, returning None for unknown forms."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def factual_passport_before_cutoff(
    row: Mapping[str, Any] | None, *, as_of_cutoff: datetime | None
) -> dict[str, Any] | None:
    """Return timestamp-safe factual evidence, or ``None`` when not provable.

    ``persisted_at`` is the durable point at which this archive row became
    available.  Requiring it to precede the race cutoff prevents a later
    archive refresh from being treated as pre-race knowledge.
    """
    if not row or as_of_cutoff is None:
        return None
    persisted_at = _parse_timestamp(row.get("persisted_at"))
    if persisted_at is None:
        return None
    if as_of_cutoff.tzinfo is None:
        return None
    # Evidence available exactly at the advertised off time is not demonstrably
    # pre-off.  Keep the boundary strict so it cannot enter a future fit.
    if persisted_at >= as_of_cutoff.astimezone(UTC):
        return None

    facts = {field: row.get(field) for field in _FACTUAL_FIELDS if row.get(field) is not None}
    if not facts.get("horse_rp_uid"):
        return None
    # Explicit source identity makes coverage reviewable without importing the
    # archive's text/derived payload or any provider prediction.
    return {"source": "new_build_horse_passports", **facts}
