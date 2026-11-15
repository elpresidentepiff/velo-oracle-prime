"""Prime, FormFav and the starting price compared on identical UK/Irish races.

Pure functions only: no network, no files. The caller supplies rows; this module pairs races,
keeps only what was known before the off, and scores each source on the same runners.

Rules that keep the comparison honest:

* A prediction counts only if it was made before the race's scheduled off. A Prime verdict
  generated after the off, or a FormFav prediction whose ``predictedAt`` is missing or after the
  off, is dropped.
* A race counts only when every runner with a result and a starting price is present in both
  Prime and FormFav, there are at least three such runners, and exactly one winner. Otherwise
  one source would be scored on a different field from the other.
* Results and starting prices come from Racing Post (``racing_horse_runs``), not from FormFav.
* The blend is the equal-weight geometric mean of the two normalised probabilities. It has no
  fitted parameter, so there is nothing to overfit on a five-week sample.

FormFav's own predictions are a provider opinion. ``formfav_feature_contract`` bans them from
VELO feature packets, and nothing here changes that: this module measures, it does not feed
any model.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
MIN_RUNNERS = 3
_TRACK_IGNORED = {"aw", "park", "racecourse", "race", "course"}
# FormFav names that differ from Racing Post's by more than a dropped suffix.
_TRACK_ALIASES = {
    "catterickbridge": "catterick",
    "chelmsfordcity": "chelmsford",
    "greatyarmouth": "yarmouth",
    "stratfordavon": "stratford",
    "newcastleupon": "newcastle",
}


def horse_key(name: Any) -> str:
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s*\([^)]*\)", "", text))


def track_key(name: Any) -> str:
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    tokens = re.findall(r"[a-z0-9]+", re.sub(r"\([^)]*\)", " ", text))
    key = "".join(token for token in tokens if token not in _TRACK_IGNORED)
    return _TRACK_ALIASES.get(key, key)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _clock(value: Any) -> str | None:
    match = re.match(r"^(\d{1,2}):(\d{2})", str(value or ""))
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else None


def pair_races(velo_races: list[dict], formfav_races: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """Match each FormFav race to a Racing Post race by date, course and London off time.

    Returns ``({race_id: formfav_race}, unmatched)``. Each unmatched FormFav race carries the
    reason: no VELO card that day, the course missing from that day's card, or the off time
    not found at that course.
    """
    by_slot: dict[tuple[str, str, str], str] = {}
    days: set[str] = set()
    day_courses: set[tuple[str, str]] = set()
    for race in velo_races:
        day, course, clock = str(race.get("date")), track_key(race.get("course")), _clock(race.get("time"))
        days.add(day)
        day_courses.add((day, course))
        if clock:
            by_slot[(day, course, clock)] = str(race["race_id"])

    paired: dict[str, dict] = {}
    unmatched: list[dict] = []
    for race in formfav_races:
        day, course = str(race.get("race_date")), track_key(race.get("track"))
        start = _parse_ts(race.get("start_time"))
        clock = start.astimezone(LONDON).strftime("%H:%M") if start else None
        race_id = by_slot.get((day, course, clock or ""))
        if race_id and race_id not in paired:
            paired[race_id] = race
            continue
        if day not in days:
            reason = "NO_VELO_CARD_THAT_DAY"
        elif (day, course) not in day_courses:
            reason = "COURSE_NOT_ON_VELO_CARD"
        else:
            reason = "OFF_TIME_NOT_FOUND"
        unmatched.append({"provider_race_key": race.get("provider_race_key"), "track": race.get("track"),
                          "race_date": day, "reason": reason})
    return paired, unmatched


def pre_off_verdict(verdicts: list[dict], off: datetime) -> dict | None:
    """The newest Prime verdict generated strictly before the off, or None."""
    best: tuple[datetime, dict] | None = None
    for verdict in verdicts:
        generated = _parse_ts(verdict.get("generated_at"))
        if generated is None or generated >= off:
            continue
        if best is None or generated > best[0]:
            best = (generated, verdict)
    return best[1] if best else None


def prime_probabilities(verdict: dict | None) -> dict[str, float]:
    predictions = ((verdict or {}).get("full_analysis") or {}).get("predictions") or []
    out: dict[str, float] = {}
    for row in predictions:
        prob = row.get("velo_prime_prob")
        if prob is not None and float(prob) > 0:
            out[horse_key(row.get("horse"))] = float(prob)
    return out


def formfav_probabilities(prediction: dict | None, off: datetime) -> dict[str, float]:
    """FormFav win probabilities, only when the prediction was made before the off."""
    payload = (prediction or {}).get("predictions_payload") or {}
    predicted_at = _parse_ts(payload.get("predictedAt"))
    if predicted_at is None or predicted_at >= off:
        return {}
    out: dict[str, float] = {}
    for row in payload.get("predictions") or []:
        prob = row.get("winProb")
        if prob is not None and float(prob) > 0:
            out[horse_key(row.get("name"))] = float(prob)
    return out


def build_race(
    results: list[dict], prime: dict[str, float], formfav: dict[str, float], prices: dict[str, dict] | None = None
) -> list[dict] | None:
    """Runners of one eligible race with each source's normalised probability, or None.

    ``prices`` is ``{horse_key: {open, t10, close}}`` from ``obtainable_prices.race_prices``.
    Each runner gets its entry under ``prices`` when one exists.
    """
    field = [r for r in results if r.get("sp_dec") is not None and float(r["sp_dec"]) > 1]
    if len(field) < MIN_RUNNERS or len(field) != len(results):
        return None
    if sum(1 for r in field if r.get("position_int") == 1) != 1:
        return None
    keys = [horse_key(r.get("horse")) for r in field]
    if len(set(keys)) != len(keys) or any(k not in prime or k not in formfav for k in keys):
        return None
    sum_p, sum_f = sum(prime[k] for k in keys), sum(formfav[k] for k in keys)
    sum_m = sum(1 / float(r["sp_dec"]) for r in field)
    runners = [
        {
            "horse": k, "won": r.get("position_int") == 1, "sp": float(r["sp_dec"]),
            "PRIME": prime[k] / sum_p, "FORMFAV": formfav[k] / sum_f, "MARKET_SP": (1 / float(r["sp_dec"])) / sum_m,
        }
        for k, r in zip(keys, field, strict=True)
    ]
    for runner in runners:
        runner["prices"] = (prices or {}).get(runner["horse"])
    blend_total = sum(math.sqrt(r["PRIME"] * r["FORMFAV"]) for r in runners)
    for r in runners:
        r["PRIME_x_FORMFAV"] = math.sqrt(r["PRIME"] * r["FORMFAV"]) / blend_total
    return runners


MODELS = ("PRIME", "FORMFAV", "PRIME_x_FORMFAV", "MARKET_SP")


def _ranked(runners: list[dict], model: str) -> list[dict]:
    return sorted(runners, key=lambda r: (-r[model], r["horse"]))


def score(races: list[list[dict]]) -> dict[str, dict]:
    """Top pick strike rate, winner-in-top-three, level-stake return at SP and winner log loss."""
    out: dict[str, dict] = {}
    for model in MODELS:
        hits = top3 = 0
        returned = log_loss = 0.0
        for runners in races:
            ranked = _ranked(runners, model)
            winner = next(r for r in runners if r["won"])
            if ranked[0]["won"]:
                hits += 1
                returned += ranked[0]["sp"]
            top3 += int(any(r["won"] for r in ranked[:3]))
            log_loss -= math.log(max(winner[model], 1e-9))
        n = len(races)
        out[model] = {
            "races": n,
            "top1_pct": round(100 * hits / n, 1) if n else None,
            "winner_in_top3_pct": round(100 * top3 / n, 1) if n else None,
            "roi_at_sp_pct": round(100 * (returned / n - 1), 1) if n else None,
            "winner_log_loss": round(log_loss / n, 4) if n else None,
        }
    return out


def paired_top1(races: list[list[dict]], a: str, b: str) -> dict:
    """Races where exactly one of two models picked the winner, with a two-sided sign test."""
    only_a = only_b = 0
    for runners in races:
        hit_a, hit_b = _ranked(runners, a)[0]["won"], _ranked(runners, b)[0]["won"]
        only_a += int(hit_a and not hit_b)
        only_b += int(hit_b and not hit_a)
    n, k = only_a + only_b, min(only_a, only_b)
    p_value = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n) if n else 1.0
    return {f"only_{a}": only_a, f"only_{b}": only_b, "sign_test_p": round(p_value, 4)}


def agreement(races: list[list[dict]]) -> dict:
    """Races where Prime and FormFav pick the same horse, against the favourite in those races.

    The favourite is the control: agreement mostly selects races with a strong favourite, so a
    high strike rate on agreed picks is not evidence of skill unless it beats the favourite there.
    """
    agreed = [r for r in races if _ranked(r, "PRIME")[0]["horse"] == _ranked(r, "FORMFAV")[0]["horse"]]

    def _line(subset: list[list[dict]], model: str) -> dict:
        n = len(subset)
        wins = [_ranked(r, model)[0] for r in subset if _ranked(r, model)[0]["won"]]
        return {
            "races": n,
            "top1_pct": round(100 * len(wins) / n, 1) if n else None,
            "roi_at_sp_pct": round(100 * (sum(w["sp"] for w in wins) / n - 1), 1) if n else None,
        }

    not_fav = [r for r in agreed if _ranked(r, "PRIME")[0]["horse"] != _ranked(r, "MARKET_SP")[0]["horse"]]
    return {
        "agreed_pick": _line(agreed, "PRIME"),
        "favourite_in_the_same_races": _line(agreed, "MARKET_SP"),
        "agreed_pick_when_it_is_not_the_favourite": _line(not_fav, "PRIME"),
    }


def score_at_obtainable_prices(races: list[list[dict]]) -> dict:
    """Each source's top pick at the best price on offer ten minutes before the off.

    Only races where every runner has an open, decision and closing price are used, so all
    sources are judged on the same races and the bookmakers' margin can be stated.
    """
    from src.velo import obtainable_prices as op

    priced = [r for r in races if all(runner.get("prices") for runner in r)]
    out: dict[str, Any] = {
        "races_with_full_prices": len(priced),
        "avg_book_at_t10": round(sum(op.book({x["horse"]: x["prices"] for x in r}) for r in priced) / len(priced), 3)
        if priced
        else None,
    }
    for model in MODELS:
        picks, at_sp = [], 0.0
        for runners in priced:
            top = _ranked(runners, model)[0]
            picks.append(op.pick_outcome(top["won"], top["prices"]))
            at_sp += (top["sp"] - 1) if top["won"] else -1.0
        summary = op.summarise(picks)
        summary["roi_at_sp_pct_same_races"] = round(100 * at_sp / len(priced), 1) if priced else None
        out[model] = summary
    return out


def evaluate(
    velo_races: list[dict],
    formfav_races: list[dict],
    verdicts: list[dict],
    predictions: list[dict],
    results: list[dict],
    snapshots: list[dict] | None = None,
) -> dict:
    """Run the whole comparison from raw rows. Returns coverage, metrics and exclusions.

    ``snapshots`` are market rows (``provider_race_key``, ``captured_at``, ``horse_name``,
    ``best_win``). When given, each source is also measured at obtainable pre-off prices.
    """
    from src.velo import obtainable_prices as op

    snapshots_by_key: dict[Any, list[dict]] = defaultdict(list)
    for row in snapshots or []:
        snapshots_by_key[row.get("provider_race_key")].append(row)
    paired, unmatched = pair_races(velo_races, formfav_races)
    verdicts_by_race: dict[str, list[dict]] = defaultdict(list)
    for verdict in verdicts:
        verdicts_by_race[str(verdict.get("race_id"))].append(verdict)
    predictions_by_key = {p.get("provider_race_key"): p for p in predictions}
    results_by_race: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        results_by_race[str(row.get("race_id"))].append(row)

    races: list[list[dict]] = []
    excluded: dict[str, int] = defaultdict(int)
    for race_id, ff_race in paired.items():
        off = _parse_ts(ff_race.get("start_time"))
        if off is None:
            excluded["NO_OFF_TIME"] += 1
            continue
        prime = prime_probabilities(pre_off_verdict(verdicts_by_race.get(race_id, []), off))
        formfav = formfav_probabilities(predictions_by_key.get(ff_race.get("provider_race_key")), off)
        if not prime:
            excluded["NO_PRE_OFF_PRIME_VERDICT"] += 1
        elif not formfav:
            excluded["NO_PRE_OFF_FORMFAV_PREDICTION"] += 1
        elif not results_by_race.get(race_id):
            excluded["NO_RACING_POST_RESULT"] += 1
        else:
            prices = op.race_prices(
                snapshots_by_key.get(ff_race.get("provider_race_key"), []), off, key=lambda r: horse_key(r.get("horse_name"))
            )
            runners = build_race(results_by_race[race_id], prime, formfav, prices)
            if runners is None:
                excluded["FIELD_NOT_IDENTICAL_OR_NOT_SETTLED"] += 1
            else:
                races.append(runners)

    reasons: dict[str, int] = defaultdict(int)
    for row in unmatched:
        reasons[row["reason"]] += 1
    return {
        "coverage": {
            "velo_races": len(velo_races), "formfav_races": len(formfav_races), "paired": len(paired),
            "unpaired_formfav_races": dict(reasons), "excluded_after_pairing": dict(excluded), "eligible": len(races),
        },
        "metrics": score(races),
        "prime_vs_blend": paired_top1(races, "PRIME", "PRIME_x_FORMFAV"),
        "prime_vs_formfav": paired_top1(races, "PRIME", "FORMFAV"),
        "agreement": agreement(races),
        "obtainable_prices": score_at_obtainable_prices(races) if snapshots is not None else None,
    }
