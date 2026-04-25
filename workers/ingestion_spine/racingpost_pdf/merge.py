"""
Racing Post PDF Parser - Merge Logic
Merge runners across XX/OR/TS/PM sources.
"""

from .types import Race


def merge_ratings(
    races: list[Race],
    or_ratings: dict[str, dict[str, dict]],
    ts_ratings: dict[str, dict[str, dict]],
    pm_prices: dict[str, dict[str, dict]],
    spotlight_comments: dict[str, dict[str, dict]] | None = None,
    postdata_signals: dict[str, dict[str, dict]] | None = None,
) -> list[Race]:
    """
    Merge OR/TS/PM data into races.

    Match by (race_id, runner_name) - fuzzy matching on names.

    Args:
        races: List of races from XX parser
        or_ratings: OR ratings map {race_id: {runner_name: rating}}
        ts_ratings: TS ratings map {race_id: {runner_name: rating}}
        pm_prices: PM prices map {race_id: {runner_name: price}}

    Returns:
        Updated races with merged data
    """
    for race in races:
        race_or = or_ratings.get(race.race_id, {})
        race_ts = ts_ratings.get(race.race_id, {})
        race_pm = pm_prices.get(race.race_id, {})
        race_spotlight = (spotlight_comments or {}).get(race.race_id, {})
        race_postdata = (postdata_signals or {}).get(race.race_id, {})

        for runner in race.runners:
            # Try exact match first
            runner_name = runner.name.upper()

            # Merge OR rating
            if runner_name in race_or:
                payload = race_or[runner_name]
                if payload.get("or_current") is not None:
                    runner.or_rating = payload["or_current"]
                runner.raw.update({k: v for k, v in payload.items() if v is not None})

            # Merge TS rating
            if runner_name in race_ts:
                payload = race_ts[runner_name]
                if runner.ts is None and payload.get("ts_latest") is not None:
                    runner.ts = payload["ts_latest"]
                runner.raw.update({k: v for k, v in payload.items() if v is not None})

            # Merge PM / Racing Post ratings (store in raw for now)
            if runner_name in race_pm:
                payload = race_pm[runner_name]
                runner.raw.update({k: v for k, v in payload.items() if v is not None})

            if runner_name in race_spotlight:
                payload = race_spotlight[runner_name]
                runner.raw.update({k: v for k, v in payload.items() if v is not None})

            if runner_name in race_postdata:
                payload = race_postdata[runner_name]
                runner.raw.update({k: v for k, v in payload.items() if v is not None})

    return races
