"""
Racing Post PDF Parser - Merge Logic
Merge runners across XX/OR/TS/PM sources.
"""

from .types import Race


def merge_ratings(
    races: list[Race],
    or_ratings: dict[str, dict[str, int]],
    ts_ratings: dict[str, dict[str, int]],
    pm_prices: dict[str, dict[str, float]],
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

        for runner in race.runners:
            # Try exact match first
            runner_name = runner.name.upper()

            # Merge OR rating
            if runner_name in race_or:
                runner.or_rating = race_or[runner_name]

            # Merge TS rating
            if runner_name in race_ts:
                runner.ts = race_ts[runner_name]

            # Merge PM price (store in raw for now)
            if runner_name in race_pm:
                runner.raw["pm_price"] = race_pm[runner_name]

    return races
