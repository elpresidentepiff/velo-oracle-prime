"""
Racing Post PDF Parser - Merge Logic & Conviction Engine
Merge runners across XX/OR/TS/PM/Spotlight/Postdata and calculate conviction.
"""

from .normalize import normalize_horse_name
from .types import Race, Runner


def merge_and_score(
    races: list[Race],
    or_ratings: dict[str, dict[str, dict]],
    ts_ratings: dict[str, dict[str, dict]],
    pm_prices: dict[str, dict[str, float]],
    spotlight_data: dict[str, dict[str, dict]],
    postdata_data: dict[str, dict[str, dict]],
) -> list[Race]:
    """
    Merge all RP sources and calculate final plot conviction score.
    """
    for race in races:
        race_or = or_ratings.get(race.race_id, {})
        race_ts = ts_ratings.get(race.race_id, {})
        race_pm = pm_prices.get(race.race_id, {})
        race_spot = spotlight_data.get(race.race_id, {})
        race_post = postdata_data.get(race.race_id, {})

        for runner in race.runners:
            name_key = normalize_horse_name(runner.name)

            # 1. Merge OR
            if name_key in race_or:
                or_payload = race_or[name_key]
                runner.or_rating = or_payload.get("or_or_current")
                runner.best_winning_life = or_payload.get("best_winning_life")
                runner.or_delta_to_best_win = or_payload.get("or_delta_to_best_win")
                runner.raw["or_history"] = or_payload.get("or_history_tokens", [])

            # 2. Merge TS
            if name_key in race_ts:
                ts_payload = race_ts[name_key]
                runner.ts = ts_payload.get("ts_or_current")
                runner.raw["ts_history"] = ts_payload.get("ts_history_tokens", [])
                runner.raw["ts_master"] = ts_payload.get("ts_master")

            # 3. Merge PM
            if name_key in race_pm:
                runner.raw["pm_price"] = race_pm[name_key]

            # 4. Merge Spotlight
            if name_key in race_spot:
                spot_payload = race_spot[name_key]
                runner.comment = spot_payload.get("comment")
                race.spotlight_verdict = spot_payload.get("spotlight_race_verdict")

            # 5. Merge Postdata
            if name_key in race_post:
                post_payload = race_post[name_key]
                runner.postdata_pick = post_payload.get("postdata_pick", False)
                runner.topspeed_pick = post_payload.get("topspeed_pick", False)
                runner.raw["postdata_rating"] = post_payload.get("postdata_latest_rating")
                runner.raw["postdata_pos_flags"] = post_payload.get("postdata_positive_count", 0)
                runner.raw["postdata_neg_flags"] = post_payload.get("postdata_negative_count", 0)

            # 6. CALCULATE CONVICTION
            runner.plot_conviction = _calculate_conviction(runner)
            runner.star_rating = _calculate_stars(runner.plot_conviction)

    return races


def _calculate_conviction(runner: Runner) -> float:
    """
    Weighted conviction scoring (0.0 to 1.0).
    """
    score = 0.0

    # A. OR Compression (40%)
    if runner.or_delta_to_best_win is not None:
        delta = runner.or_delta_to_best_win
        if delta <= 0:
            # Horse is at or below its winning mark
            score += 0.40
            # Bonus for major compression
            if delta <= -10:
                score += 0.10
        elif delta <= 5:
            # Within striking distance
            score += 0.20

    # B. Confirmation Signals (40%)
    if runner.postdata_pick:
        score += 0.20
    if runner.topspeed_pick:
        score += 0.20
    
    # C. Intent / Physical (20%)
    # Cash run flag in raw (if extracted earlier by XX parser)
    if runner.raw.get("cash_run_flag"):
        score += 0.10
    
    # Positive spotlight sentiment (basic check for now)
    if runner.comment and any(word in runner.comment.lower() for word in ["well treated", "major player", "big chance"]):
        score += 0.10

    return min(1.0, score)


def _calculate_stars(score: float) -> int:
    if score >= 0.85:
        return 3
    if score >= 0.70:
        return 2
    if score >= 0.50:
        return 1
    return 0
