"""Evidence-first handicap-release classification for a paper/shadow lane.

This module does not predict a winner, generate odds, consume provider
predictions, write data, or affect Prime.  It turns dated, caller-supplied
factual history into an explicit *review card*: why a runner may be better
treated by the handicap than recent finishes suggest, and what is missing or
contradictory.  A candidate is never a claim of trainer intent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class HistoricalRun:
    run_date: date
    official_rating: float | None
    position: int | None
    course: str | None = None
    distance_furlongs: float | None = None
    going_bucket: str | None = None


@dataclass(frozen=True)
class RaceContext:
    race_id: str
    runner_id: str
    race_date: date
    is_handicap: bool
    official_rating: float | None
    course: str | None = None
    distance_furlongs: float | None = None
    going_bucket: str | None = None


@dataclass(frozen=True)
class ReleaseReview:
    """An evidence card; ``status`` is deliberately not a betting instruction."""

    race_id: str
    runner_id: str
    status: str  # CANDIDATE_FOR_REVIEW, NOT_SUPPORTED, or INSUFFICIENT_EVIDENCE
    evidence: tuple[str, ...]
    contradictions: tuple[str, ...]
    missing: tuple[str, ...]
    history_runs_used: int
    current_or: float | None
    last_win_or: float | None
    best_prior_or: float | None
    days_since_run: int | None
    corroborator_count: int
    classification: str = "SHADOW_ONLY_NO_LIVE_SCORING_CHANGE"


def _same_text(left: str | None, right: str | None) -> bool:
    return bool(left and right and left.strip().casefold() == right.strip().casefold())


def _same_trip(left: float | None, right: float | None) -> bool:
    return left is not None and right is not None and abs(left - right) <= 0.5


def review_handicap_release(context: RaceContext, history: Iterable[HistoricalRun]) -> ReleaseReview:
    """Return a conservative, as-of-date factual release review.

    The function rejects any post-card history rather than silently treating it
    as pre-race evidence.  It requires a handicap, a current official rating,
    at least three dated prior runs, a prior winning mark at/above today's
    rating, and at least two independent corroborators:

    * return to a previous winning course, trip or going bucket;
    * a 2nd--10th run since the latest win (a campaign window, not intent);
    * today's mark is below the horse's best recorded prior mark.

    Those are review criteria only.  They do not prove a trainer plan and must
    remain separate from Prime until a forward, same-race evaluation exists.
    """
    if not context.race_id or not context.runner_id:
        raise ValueError("race_id and runner_id are required")
    observed = tuple(history)
    future = [run for run in observed if run.run_date >= context.race_date]
    if future:
        raise ValueError("history contains same-day or future runs")
    prior = sorted(observed, key=lambda run: run.run_date)
    missing: list[str] = []
    evidence: list[str] = []
    contradictions: list[str] = []

    if not context.is_handicap:
        return ReleaseReview(context.race_id, context.runner_id, "NOT_SUPPORTED", (), ("NOT_A_HANDICAP",), (), len(prior), context.official_rating, None, None, None, 0)
    if context.official_rating is None:
        missing.append("CURRENT_OFFICIAL_RATING_MISSING")
    if len(prior) < 3:
        missing.append("INSUFFICIENT_PRIOR_RUNS")
    if missing:
        return ReleaseReview(context.race_id, context.runner_id, "INSUFFICIENT_EVIDENCE", (), (), tuple(missing), len(prior), context.official_rating, None, None, None, 0)

    assert context.official_rating is not None
    rating_runs = [run for run in prior if run.official_rating is not None]
    if not rating_runs:
        missing.append("PRIOR_OFFICIAL_RATINGS_MISSING")
    wins_with_marks = [run for run in prior if run.position == 1 and run.official_rating is not None]
    if not wins_with_marks:
        missing.append("PRIOR_WINNING_MARK_MISSING")
    if missing:
        return ReleaseReview(context.race_id, context.runner_id, "INSUFFICIENT_EVIDENCE", (), (), tuple(missing), len(prior), context.official_rating, None, None, None, 0)

    last_win = wins_with_marks[-1]
    last_win_or = last_win.official_rating
    best_or = max(run.official_rating for run in rating_runs if run.official_rating is not None)
    days_since_run = (context.race_date - prior[-1].run_date).days
    runs_since_win = len(prior) - 1 - prior.index(last_win)
    corroborators = 0

    if context.official_rating <= last_win_or:  # type: ignore[operator]
        evidence.append("AT_OR_BELOW_LAST_WINNING_MARK")
    else:
        contradictions.append("ABOVE_LAST_WINNING_MARK")

    condition_hits = 0
    if _same_text(context.course, last_win.course):
        condition_hits += 1
        evidence.append("RETURN_TO_WINNING_COURSE")
    if _same_trip(context.distance_furlongs, last_win.distance_furlongs):
        condition_hits += 1
        evidence.append("RETURN_TO_WINNING_TRIP")
    if _same_text(context.going_bucket, last_win.going_bucket):
        condition_hits += 1
        evidence.append("RETURN_TO_WINNING_GOING_BUCKET")
    if condition_hits:
        corroborators += 1

    if 2 <= runs_since_win <= 10:
        corroborators += 1
        evidence.append("CAMPAIGN_WINDOW_2_TO_10_RUNS_SINCE_WIN")
    elif runs_since_win < 2:
        contradictions.append("TOO_SOON_AFTER_WIN_FOR_RELEASE_PATTERN")
    else:
        contradictions.append("LONG_WINLESS_SEQUENCE")

    if context.official_rating < best_or:
        corroborators += 1
        evidence.append("BELOW_BEST_PRIOR_MARK")
    else:
        contradictions.append("NOT_BELOW_BEST_PRIOR_MARK")

    if days_since_run > 180:
        contradictions.append("LONG_ABSENCE_OVER_180_DAYS")
    elif days_since_run >= 21:
        evidence.append("MEANINGFUL_RECOVERY_INTERVAL")

    candidate = "AT_OR_BELOW_LAST_WINNING_MARK" in evidence and corroborators >= 2
    return ReleaseReview(
        context.race_id,
        context.runner_id,
        "CANDIDATE_FOR_REVIEW" if candidate else "NOT_SUPPORTED",
        tuple(evidence),
        tuple(contradictions),
        (),
        len(prior),
        context.official_rating,
        last_win_or,
        best_or,
        days_since_run,
        corroborators,
    )
