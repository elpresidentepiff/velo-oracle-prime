"""Pre-trade risk gate for real Betfair orders. Fail-closed.

Nothing in the repo is allowed to place a live order unless this gate says yes.
It is a pure function of (order, state, limits): no network, no env reads, no
clock, so every rule is unit-testable. The caller supplies ``state`` (kill
switch, operator approval, today's exposure, bankroll, seen order refs) from
durable storage; a missing or malformed state denies.

Default posture is DENY. ``deny_all`` is what ``BetfairClient`` uses until
someone deliberately wires a configured gate in; building that wiring is a
separate, operator-approved change (see docs/engineering/BETFAIR_LIVE_READINESS_V1.md).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Betfair price ladder: (upper bound exclusive, tick)
_LADDER = (
    (2.0, 0.01), (3.0, 0.02), (4.0, 0.05), (6.0, 0.1), (10.0, 0.2),
    (20.0, 0.5), (30.0, 1.0), (50.0, 2.0), (100.0, 5.0), (1000.01, 10.0),
)


@dataclass(frozen=True)
class RiskLimits:
    max_stake: float                 # per order, currency units
    max_liability_per_race: float
    max_daily_liability: float
    daily_loss_stop: float           # stop once realised loss today >= this (positive number)
    bankroll_floor: float            # never let bankroll after worst case drop below this
    min_price: float = 1.5
    max_price: float = 30.0


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def _deny(reason: str) -> Decision:
    return Decision(False, reason)


def liability(side: str, size: float, price: float) -> float:
    return size if side == "BACK" else size * (price - 1.0)


def on_ladder(price: float) -> bool:
    lo = 1.01
    for hi, tick in _LADDER:
        if price < hi:
            steps = round((price - lo) / tick, 6)
            return abs(steps - round(steps)) < 1e-6 and price >= 1.01
        lo = hi
    return False


def deny_all(order: Mapping[str, Any]) -> Decision:  # noqa: ARG001
    return _deny("NO_RISK_GATE_CONFIGURED")


def authorize(order: Mapping[str, Any], state: Mapping[str, Any] | None, limits: RiskLimits | None) -> Decision:
    """Return the first failed rule, or allow. Any missing input denies."""
    if not state or limits is None:
        return _deny("STATE_OR_LIMITS_MISSING")
    try:
        side = str(order["side"]).upper()
        size = float(order["size"])
        price = float(order["price"])
        market_id = str(order["market_id"])
        ref = str(order.get("customer_order_ref") or "")
        if side not in ("BACK", "LAY"):
            return _deny("BAD_SIDE")
        if state.get("kill_switch") is not False:
            return _deny("KILL_SWITCH_ON_OR_UNKNOWN")
        approval = state.get("operator_approval") or {}
        if not approval.get("approved") or market_id not in set(approval.get("market_ids") or []):
            return _deny("NO_OPERATOR_APPROVAL_FOR_MARKET")
        if state.get("market_status") != "OPEN" or state.get("market_in_play") is not False:
            return _deny("MARKET_NOT_OPEN_PREPLAY")
        if not ref:
            return _deny("NO_CUSTOMER_ORDER_REF")
        if ref in set(state.get("seen_order_refs") or []):
            return _deny("DUPLICATE_ORDER_REF")
        if not (size > 0 and size <= limits.max_stake):
            return _deny("STAKE_OUT_OF_RANGE")
        if not (limits.min_price <= price <= limits.max_price) or not on_ladder(price):
            return _deny("PRICE_OUT_OF_RANGE_OR_OFF_LADDER")
        liab = liability(side, size, price)
        if float(state["race_liability"]) + liab > limits.max_liability_per_race:
            return _deny("RACE_LIABILITY_CAP")
        if float(state["daily_liability"]) + liab > limits.max_daily_liability:
            return _deny("DAILY_LIABILITY_CAP")
        if float(state["daily_realised_pnl"]) <= -abs(limits.daily_loss_stop):
            return _deny("DAILY_LOSS_STOP")
        if float(state["bankroll"]) - liab < limits.bankroll_floor:
            return _deny("BANKROLL_FLOOR")
    except (KeyError, TypeError, ValueError):
        return _deny("MALFORMED_ORDER_OR_STATE")
    return Decision(True, "OK")
