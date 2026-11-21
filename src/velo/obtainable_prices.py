"""The price a pick could really have been backed at, from timestamped market snapshots.

The starting price is only known after the off, so a return "at SP" is a return nobody could
lock in. VELO's one timestamped pre-off price source for UK and Irish races is the market feed
(``formfav_market_snapshots``: best price across bookmakers, polled from about two hours before
the off). This module turns those rows into three prices per runner:

* ``open``   the first price seen at least 60 minutes before the off
* ``t10``    the last price seen at least 10 minutes before the off (the decision price)
* ``close``  the last price seen before the off

and measures each pick two ways: the level-stake return at the decision price, and whether the
price then shortened (``beat_close``): a pick that the market later moves towards was bought
below where the market ended up. Beating the close is the skill signal that does not need
hundreds of winners to show up.

Prices are facts, not provider opinions, so nothing here conflicts with the rule that VELO must
not see FormFav's predictions. Nothing here is fed to a model either: this is measurement.

A snapshot at or after the off is never used.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

OPEN_MINUTES = 60
DECISION_MINUTES = 10


def _ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else None
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def runner_prices(snapshots: list[dict], off: datetime) -> dict[str, float] | None:
    """Open, decision and closing price of one runner, or None if any of the three is missing.

    ``snapshots`` are that runner's rows (``captured_at``, ``best_win``) in any order.
    """
    rows = sorted(
        (ts, float(row["best_win"]))
        for row in snapshots
        if (ts := _ts(row.get("captured_at"))) is not None
        and ts < off
        and row.get("best_win") is not None
        and float(row["best_win"]) > 1
    )
    if not rows:
        return None
    opening = [price for ts, price in rows if ts <= off - timedelta(minutes=OPEN_MINUTES)]
    decision = [price for ts, price in rows if ts <= off - timedelta(minutes=DECISION_MINUTES)]
    if not opening or not decision:
        return None
    return {"open": opening[0], "t10": decision[-1], "close": rows[-1][1]}


def race_prices(snapshots: list[dict], off: datetime, key=lambda row: row.get("horse_name")) -> dict[Any, dict[str, float]]:
    """``{runner key: {open, t10, close}}`` for every runner of a race that has all three."""
    by_runner: dict[Any, list[dict]] = defaultdict(list)
    for row in snapshots:
        by_runner[key(row)].append(row)
    out = {}
    for runner, rows in by_runner.items():
        prices = runner_prices(rows, off)
        if prices is not None:
            out[runner] = prices
    return out


def book(prices: dict[Any, dict[str, float]], at: str = "t10") -> float:
    """Sum of implied probabilities: 1.0 is a fair book, above it is the bookmakers' margin."""
    return sum(1 / p[at] for p in prices.values())


def pick_outcome(won: bool, prices: dict[str, float]) -> dict[str, float]:
    """One pick: profit to a 1-point stake at the decision price, and how the price moved after.

    ``beat_close`` is log(decision price / closing price): positive when the price shortened
    after the decision time, so the pick was taken at better than the market's final view.
    """
    return {
        "profit_at_t10": (prices["t10"] - 1) if won else -1.0,
        "beat_close": math.log(prices["t10"] / prices["close"]),
        "shortened_from_open": math.log(prices["open"] / prices["t10"]),
    }


def summarise(picks: list[dict]) -> dict:
    """Aggregate picks from ``pick_outcome``. Reports the count so a small sample is visible."""
    n = len(picks)
    if n == 0:
        return {"picks": 0, "roi_at_t10_pct": None, "avg_beat_close_pct": None, "beat_close_share_pct": None}
    beat = [p["beat_close"] for p in picks]
    return {
        "picks": n,
        "roi_at_t10_pct": round(100 * sum(p["profit_at_t10"] for p in picks) / n, 1),
        # exp(mean log ratio) - 1: the average percentage by which the decision price beat the close
        "avg_beat_close_pct": round(100 * (math.exp(sum(beat) / n) - 1), 2),
        "beat_close_share_pct": round(100 * sum(1 for b in beat if b > 0) / n, 1),
        "worse_than_close_share_pct": round(100 * sum(1 for b in beat if b < 0) / n, 1),
    }
