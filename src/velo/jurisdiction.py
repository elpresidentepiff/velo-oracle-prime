"""Canonical fail-closed race-jurisdiction resolution.

Race-level ``region`` and ``country`` fields are authoritative.  Aliases are
normalised before comparison, and conflicting non-empty fields deliberately
resolve to unknown rather than allowing either value to cross a scoring gate.
Venue inference is intentionally not part of this module; the legacy RP merged
loader owns its small, explicit fallback for records with no jurisdiction
metadata at all.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

UK_IRE_JURISDICTIONS = frozenset({"GB", "IRE"})

_JURISDICTION_ALIASES = {
    "GB": "GB",
    "GBR": "GB",
    "UK": "GB",
    "IE": "IRE",
    "IRL": "IRE",
    "IRE": "IRE",
    "IRELAND": "IRE",
}


def normalize_jurisdiction_code(value: Any) -> str:
    """Normalise a jurisdiction code while preserving foreign codes."""
    if value is None:
        return ""
    code = str(value).strip().upper()
    return _JURISDICTION_ALIASES.get(code, code)


def resolve_jurisdiction_values(values: Iterable[Any]) -> str:
    """Return one agreed code, or ``""`` for missing/conflicting metadata."""
    codes = {code for value in values if (code := normalize_jurisdiction_code(value))}
    if len(codes) != 1:
        return ""
    return next(iter(codes))


def resolve_race_jurisdiction(race: Mapping[str, Any]) -> str:
    """Resolve a flat race record's authoritative region/country pair."""
    return resolve_jurisdiction_values((race.get("region"), race.get("country")))


def is_uk_ire_race(race: Mapping[str, Any]) -> bool:
    """Whether a flat race record proves an unconflicted UK/IRE jurisdiction."""
    return resolve_race_jurisdiction(race) in UK_IRE_JURISDICTIONS
