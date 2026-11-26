"""Pure PAPER/SIM candidate validation and bounded accumulator enumeration.

No data acquisition, prediction generation, betting, persistence, or learning.
Caller-supplied identity and timestamps are claims: they require independent
verification by a future adapter before operational use.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from math import isfinite


@dataclass(frozen=True)
class Leg:
    race_id: str
    horse_id: str
    horse: str
    model: str
    off_at: datetime
    evidence_at: datetime
    evidence_source: str
    roster_checked_at: datetime
    roster_source: str
    in_field: bool
    market: str  # WIN or PLACE; EACH_WAY must be represented as separate bets
    decimal_odds: float
    odds_at: datetime
    odds_source: str
    place_count: int | None = None
    place_terms_source: str | None = None
    place_terms_at: datetime | None = None


@dataclass(frozen=True)
class Ticket:
    legs: tuple[Leg, ...]
    frozen_at: datetime
    combined_decimal_odds: float
    label: str = "PAPER_ONLY_UNVERIFIED_SOURCE_CLAIMS"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("all timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def validate_leg(leg: Leg, *, cutoff: datetime, max_roster_age_seconds: int = 900) -> tuple[str, ...]:
    """Return fail-closed reasons; cutoff is the actual proposed freeze time."""
    reasons: list[str] = []
    try:
        freeze, off = _utc(cutoff), _utc(leg.off_at)
        observed = [_utc(leg.evidence_at), _utc(leg.roster_checked_at), _utc(leg.odds_at)]
    except (ValueError, TypeError):
        return ("INVALID_TIMESTAMP",)
    if not all(isinstance(x, str) and x.strip() for x in (leg.race_id, leg.horse_id, leg.horse, leg.model)):
        reasons.append("IDENTITY_MISSING")
    if isinstance(leg.model, str) and any(term in leg.model.casefold() for term in ("formfav", "provider", "tipster")):
        reasons.append("PROVIDER_MODEL_FORBIDDEN")
    if not all(isinstance(x, str) and x.strip() for x in (leg.evidence_source, leg.roster_source, leg.odds_source)):
        reasons.append("PROVENANCE_MISSING")
    if leg.in_field is not True:
        reasons.append("NOT_VERIFIED_IN_FIELD")
    if freeze >= off:
        reasons.append("RACE_ALREADY_OFF")
    if any(t > freeze or t >= off for t in observed):
        reasons.append("LATE_OR_FUTURE_EVIDENCE")
    if max_roster_age_seconds < 0 or (freeze - observed[1]).total_seconds() > max_roster_age_seconds:
        reasons.append("STALE_ROSTER")
    if leg.market not in ("WIN", "PLACE"):
        reasons.append("UNSUPPORTED_MARKET")
    if isinstance(leg.decimal_odds, bool) or not isinstance(leg.decimal_odds, (int, float)) or not isfinite(leg.decimal_odds) or leg.decimal_odds <= 1:
        reasons.append("INVALID_ODDS")
    if leg.market == "PLACE" and (isinstance(leg.place_count, bool) or not isinstance(leg.place_count, int) or leg.place_count < 1 or not isinstance(leg.place_terms_source, str) or not leg.place_terms_source.strip()):
        reasons.append("PLACE_TERMS_MISSING")
    if leg.market == "PLACE":
        try:
            terms_at = _utc(leg.place_terms_at)  # type: ignore[arg-type]
            if terms_at > freeze or terms_at >= off:
                reasons.append("LATE_OR_FUTURE_PLACE_TERMS")
        except (ValueError, TypeError):
            reasons.append("PLACE_TERMS_TIME_MISSING")
    return tuple(reasons)


def build_tickets(legs: list[Leg], *, leg_count: int, max_tickets: int = 100, now: datetime | None = None) -> tuple[Ticket, ...]:
    """Enumerate a deterministic bounded set, all-or-nothing; no optimisation claim.

    Production callers must omit ``now``. Explicit ``now`` is solely a clock
    injection for offline tests and cannot establish a historical freeze.
    """
    if not 2 <= leg_count <= 7 or not 1 <= max_tickets <= 1000:
        raise ValueError("leg_count must be 2..7 and max_tickets 1..1000")
    freeze = _utc(now if now is not None else datetime.now(timezone.utc))
    errors = [(leg.horse, validate_leg(leg, cutoff=freeze)) for leg in legs]
    errors = [(horse, reasons) for horse, reasons in errors if reasons]
    if errors:
        raise ValueError(f"candidate validation failed: {errors}")
    keys = [(leg.race_id, leg.horse_id, leg.market) for leg in legs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate candidate")
    ordered = sorted(legs, key=lambda leg: (leg.race_id, leg.horse_id, leg.market))
    tickets: list[Ticket] = []
    for group in combinations(ordered, leg_count):
        if len({leg.race_id for leg in group}) != leg_count:
            continue
        if len(tickets) >= max_tickets:
            raise ValueError("ticket limit exceeded; narrow the candidate set")
        odds = 1.0
        for leg in group:
            odds *= leg.decimal_odds
        if not isfinite(odds):
            raise ValueError("combined odds overflow")
        label = "OFFLINE_SIMULATION_NOT_FORWARD_EVIDENCE" if now is not None else "PAPER_ONLY_UNVERIFIED_SOURCE_CLAIMS"
        tickets.append(Ticket(group, freeze, odds, label))
    return tuple(tickets)
