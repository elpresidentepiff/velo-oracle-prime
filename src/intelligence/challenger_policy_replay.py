"""Read-only top-pick policy replay for New Build and Mid-Price Hunter.

NOT probability calibration: readiness reports expose top-three, not full fields.
No network, Supabase writes, executable bets, training or model promotion.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from math import isfinite
from typing import Any

from src.intelligence.historical_runner_crosswalk import (
    STATUS_COMPLETE,
    CrosswalkRecord,
    CrosswalkReport,
    canonical_sha256,
)
from src.velo.learning.identity_resolver import normalise_name

LANES = ("lane_a", "lane_b", "lane_c")
MIDPRICE_ACTIONS = frozenset(
    {
        "MIDPRICE_CLEAN",
        "MIDPRICE_SUPPRESS_TOP",
        "MIDPRICE_NO_EDGE",
        "MIDPRICE_SPLIT_RACE",
    }
)


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo is not None and dt.utcoffset() is not None else None


def _verified_races(report: CrosswalkReport) -> dict[tuple[str, str], list[CrosswalkRecord]]:
    grouped: dict[tuple[str, str], list[CrosswalkRecord]] = defaultdict(list)
    for row in report.records:
        if row.race_date:
            grouped[(row.race_date, row.race_id)].append(row)
    verified = {}
    for key, all_rows in grouped.items():
        starters = [row for row in all_rows if not row.non_runner]
        if (
            len(starters) > 1
            and len({row.horse_id for row in starters}) == len(starters)
            and all(row.status == STATUS_COMPLETE and row.outcome in (0, 1) for row in starters)
            and sum(row.outcome == 1 for row in starters) == 1
            and all(
                _aware(row.prediction_time) is not None
                and _aware(row.race_time) is not None
                and _aware(row.prediction_time) < _aware(row.race_time)
                for row in starters
            )
        ):
            verified[key] = starters
    return verified


def _match_pick(horse: Any, horse_id: Any, starters: list[CrosswalkRecord]) -> CrosswalkRecord | None:
    label = normalise_name(horse) if isinstance(horse, str) else ""
    if not label:
        return None
    matched = [row for row in starters if normalise_name(row.horse) == label]
    if len(matched) != 1:
        return None
    if horse_id is not None and str(horse_id) != matched[0].horse_id:
        return None
    return matched[0]


def _prime_pick(starters: list[CrosswalkRecord]) -> CrosswalkRecord | None:
    if any(row.velo_prime_prob is None or not isfinite(row.velo_prime_prob) for row in starters):
        return None
    probabilities = [float(row.velo_prime_prob) for row in starters]
    if probabilities.count(max(probabilities)) != 1:
        return None
    return max(starters, key=lambda row: float(row.velo_prime_prob))


def _price(row: CrosswalkRecord) -> float | None:
    p = row.market_decimal_price
    return float(p) if p is not None and isfinite(p) and p > 1 else None


def audit_new_build(reports: list[dict[str, Any]], crosswalk: CrosswalkReport) -> dict[str, Any]:
    """Evaluate only explicit rank-one choices; never extrapolate top-three to full field."""
    races = _verified_races(crosswalk)
    excluded: dict[str, Counter[str]] = {lane: Counter() for lane in LANES}
    stats: dict[str, Counter[str]] = {lane: Counter() for lane in LANES}
    examples: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("readiness report must be an object")
        generated = _aware(report.get("generated_at"))
        day = report.get("target_date")
        if not isinstance(day, str):
            raise ValueError("readiness target_date required")
        cards = report.get("race_day_scorecards")
        if not isinstance(cards, list):
            raise ValueError("readiness race_day_scorecards required")
        for card in cards:
            if not isinstance(card, dict):
                raise ValueError("invalid readiness race")
            race_id = str(card.get("race_id") or "")
            card_date = str(card.get("race_date") or "")
            key = (day, race_id)
            for lane in LANES:
                identity = (day, race_id, lane)
                if identity in seen:
                    excluded[lane]["DUPLICATE_READINESS_RACE"] += 1
                    continue
                seen.add(identity)
                starters = races.get(key)
                if not race_id or card_date != day or starters is None:
                    excluded[lane]["NO_VERIFIED_MATCHING_RACE"] += 1
                    continue
                race_time = _aware(starters[0].race_time)
                if generated is None or race_time is None or generated >= race_time:
                    excluded[lane]["NOT_PROVED_PRE_RACE"] += 1
                    continue
                top3 = card.get(lane + "_top3")
                if not isinstance(top3, list):
                    excluded[lane]["TOP3_ABSENT"] += 1
                    continue
                leaders = [
                    item
                    for item in top3
                    if isinstance(item, dict) and type(item.get("rank")) is int and item["rank"] == 1
                ]
                if len(leaders) != 1:
                    excluded[lane]["AMBIGUOUS_RANK_ONE"] += 1
                    continue
                pick = leaders[0]
                try:
                    prob = float(pick["prob"])
                except (KeyError, TypeError, ValueError):
                    excluded[lane]["INVALID_CAPTURED_PROBABILITY"] += 1
                    continue
                if not isfinite(prob) or not 0 <= prob <= 1:
                    excluded[lane]["INVALID_CAPTURED_PROBABILITY"] += 1
                    continue
                challenger = _match_pick(pick.get("horse"), pick.get("horse_id"), starters)
                prime = _prime_pick(starters)
                if challenger is None or prime is None:
                    excluded[lane]["UNMATCHED_OR_AMBIGUOUS_PICK"] += 1
                    continue
                stats[lane]["races"] += 1
                stats[lane]["wins"] += int(challenger.outcome == 1)
                stats[lane]["prime_wins"] += int(prime.outcome == 1)
                stats[lane]["disagreements"] += int(challenger.horse_id != prime.horse_id)
                cp, bp = _price(challenger), _price(prime)
                if cp is not None and bp is not None:
                    stats[lane]["paired_priced_races"] += 1
                    stats[lane]["challenger_return_cents"] += round(100 * cp) if challenger.outcome else 0
                    stats[lane]["prime_return_cents"] += round(100 * bp) if prime.outcome else 0
                examples.append(
                    {
                        "race_date": day,
                        "race_id": race_id,
                        "lane": lane,
                        "selected_horse_id": challenger.horse_id,
                        "prime_horse_id": prime.horse_id,
                        "selected_win": challenger.outcome,
                        "source_report_sha256": canonical_sha256(report),
                    }
                )
    return {
        "lanes": {lane: dict(stats[lane]) for lane in LANES},
        "exclusions": {lane: dict(excluded[lane]) for lane in LANES},
        "selections": examples,
        "input_reports_sha256": canonical_sha256(reports),
        "comparison": "TOP_PICK_ONLY_NOT_FULL_FIELD_PROBABILITY",
        "price_status": "PRE_RACE_ROW_NOT_INDEPENDENT_MARKET_TIMESTAMP",
        "independent_validation": False,
        "promotion": "NOT_AUTHORISED",
    }


def audit_midprice_actions(ledger: list[dict[str, Any]], crosswalk: CrosswalkReport) -> dict[str, Any]:
    """Describe real shadow action groups without converting categories into probabilities.

    Counterfactual abstention is explicitly hypothetical, NOT an execution rule.
    """
    races = _verified_races(crosswalk)
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    exclusions: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for entry in ledger:
        if not isinstance(entry, dict):
            raise ValueError("ledger entry must be an object")
        day, race_id = str(entry.get("race_date") or ""), str(entry.get("race_id") or "")
        key = (day, race_id)
        if key in seen:
            exclusions["DUPLICATE_ACTION_FOR_RACE"] += 1
            continue
        seen.add(key)
        starters = races.get(key)
        if starters is None:
            exclusions["NO_VERIFIED_MATCHING_RACE"] += 1
            continue
        created = _aware(entry.get("created_at"))
        race_time = _aware(starters[0].race_time)
        if created is None or race_time is None or created >= race_time:
            exclusions["ACTION_NOT_PROVED_PRE_RACE"] += 1
            continue
        if entry.get("live_scoring_changed") is not False or entry.get("execution_allowed") is not False:
            exclusions["VIOLATES_SHADOW_ONLY_CONTRACT"] += 1
            continue
        action = entry.get("shadow_action")
        if action not in MIDPRICE_ACTIONS or not entry.get("rule_version"):
            exclusions["UNKNOWN_ACTION_OR_RULE"] += 1
            continue
        prime = _prime_pick(starters)
        if prime is None or _match_pick(entry.get("top_pick"), entry.get("top_horse_id"), starters) != prime:
            exclusions["TOP_PICK_NOT_CANONICAL_PRIME"] += 1
            continue
        s = stats[action]
        s["races"] += 1
        s["prime_wins"] += int(prime.outcome == 1)
        p = _price(prime)
        if p is not None:
            s["priced_races"] += 1
            s["prime_return_cents"] += round(100 * p) if prime.outcome else 0
        if action != "MIDPRICE_CLEAN":
            s["hypothetical_abstentions"] += 1
    return {
        "action_groups": {action: dict(count) for action, count in sorted(stats.items())},
        "exclusions": dict(exclusions),
        "ledger_sha256": canonical_sha256(ledger),
        "hypothetical_policy": "ABSTAIN_ON_NON_CLEAN_ACTION_FOR_RESEARCH_ONLY",
        "metric_type": "SELECTION_CONDITIONAL_OUTCOMES_NOT_BRIER",
        "independent_validation": False,
        "promotion": "NOT_AUTHORISED",
    }
