"""Read-only historical runner crosswalk and frozen Evo² replay preparation.

This module never writes to a database and never changes model state.  It joins
the four existing evidence streams, retains record-level SHA256 provenance, and
fails closed when identity, timing, or official-result evidence is incomplete.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo

from src.intelligence.challenger_lab import MarketObservation, Observation
from src.velo.learning.identity_resolver import normalise_name, parse_time_to_minutes
from src.velo.learning.prediction_run_selector import (
    PROOF_PRE_RACE,
    course_timezone,
    select_canonical_run,
)

SOURCE_SNAPSHOT = "runner_prediction_snapshots"
SOURCE_SNAPSHOT_LOCAL = "runner_prediction_snapshots.local_jsonl"
SOURCE_VERDICT = "velo_verdicts.full_analysis.predictions"
STATUS_COMPLETE = "COMPLETE_VERIFIED"
STATUS_INCOMPLETE = "INCOMPLETE"
PROBABILITY_FIELDS = ("sqpe_v17_prob", "sqpe_no_rpr_shadow_prob")


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible source record without changing it."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _race_time_utc(race_date: Any, off_time: Any, course: Any) -> datetime | None:
    minutes = parse_time_to_minutes(off_time)
    timezone_name = course_timezone(str(course or ""))
    if not race_date or minutes is None or timezone_name is None:
        return None
    try:
        day = datetime.fromisoformat(str(race_date)).date()
    except ValueError:
        return None
    local = datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(timezone_name))
    return (local + timedelta(minutes=minutes)).astimezone(UTC)


def _one(values: Iterable[Any]) -> Any | None:
    distinct = {str(value) for value in values if value is not None and str(value) != ""}
    return next(iter(distinct)) if len(distinct) == 1 else None


def _bool(value: Any) -> bool:
    return value is True or str(value).lower() in {"true", "1", "yes"}


@dataclass(frozen=True)
class SourceBundle:
    runner_prediction_snapshots: list[dict[str, Any]]
    velo_verdicts: list[dict[str, Any]]
    canonical_model_scorecards: list[dict[str, Any]]
    velo_race_truth: list[dict[str, Any]]
    local_runner_prediction_snapshots: list[dict[str, Any]] = field(default_factory=list)
    local_snapshot_file_hashes: dict[str, str] = field(default_factory=dict)


@dataclass
class CrosswalkRecord:
    race_date: str | None
    race_id: str
    horse_id: str
    horse: str | None
    prediction_source: str
    prediction_time: str | None
    race_time: str | None
    rank: int | None
    source_ordinal: int | None
    velo_prime_prob: float | None
    sqpe_v17_prob: float | None
    model_probabilities: dict[str, float | None]
    market_decimal_price: float | None
    market_price_field: str | None
    result_position: str | None
    outcome: int | None
    non_runner: bool
    status: str = STATUS_INCOMPLETE
    evidence_issues: list[str] = field(default_factory=list)
    evidence_hashes: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class CrosswalkReport:
    records: list[CrosswalkRecord]
    counts_by_date: dict[str, dict[str, int]]
    source_counts: dict[str, int]
    source_hashes: dict[str, str]
    duplicate_snapshot_entries: int
    duplicate_verdict_entries: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "velo_historical_crosswalk_v1",
            "mode": "READ_ONLY_OFFLINE",
            "records": [asdict(row) for row in self.records],
            "counts_by_date": self.counts_by_date,
            "source_counts": self.source_counts,
            "source_hashes": self.source_hashes,
            "duplicate_snapshot_entries": self.duplicate_snapshot_entries,
            "duplicate_verdict_entries": self.duplicate_verdict_entries,
        }


def _date_index(bundle: SourceBundle) -> tuple[dict[str, str], set[str]]:
    by_race: dict[str, set[str]] = defaultdict(set)
    for row in bundle.runner_prediction_snapshots:
        if row.get("race_id") and row.get("race_date"):
            by_race[str(row["race_id"])].add(str(row["race_date"]))
    for row in bundle.canonical_model_scorecards:
        if row.get("race_id") and row.get("run_date"):
            by_race[str(row["race_id"])].add(str(row["run_date"]))
    for row in bundle.velo_race_truth:
        if row.get("race_id") and row.get("race_date"):
            by_race[str(row["race_id"])].add(str(row["race_date"]))
    conflicts = {race_id for race_id, dates in by_race.items() if len(dates) != 1}
    return {race_id: next(iter(dates)) for race_id, dates in by_race.items() if len(dates) == 1}, conflicts


def _verdict_predictions(verdict: dict[str, Any]) -> list[dict[str, Any]]:
    full_analysis = verdict.get("full_analysis")
    if not isinstance(full_analysis, dict):
        return []
    predictions = full_analysis.get("predictions")
    return predictions if isinstance(predictions, list) else []


def _prediction_rows(bundle: SourceBundle) -> tuple[list[dict[str, Any]], int, int]:
    """Return one prediction cohort per race; snapshots take precedence.

    Verdict-array position is retained only as ``source_ordinal``.  It is never
    promoted to a model rank because the historical JSON has no explicit rank.
    """
    date_by_race, date_conflicts = _date_index(bundle)
    snapshot_source = (
        bundle.local_runner_prediction_snapshots
        if bundle.local_runner_prediction_snapshots
        else bundle.runner_prediction_snapshots
    )
    snapshot_source_name = SOURCE_SNAPSHOT_LOCAL if bundle.local_runner_prediction_snapshots else SOURCE_SNAPSHOT
    snapshots_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    snapshot_keys: Counter[tuple[str, str, str]] = Counter()
    for row in snapshot_source:
        race_id = str(row.get("race_id") or "")
        if race_id:
            snapshots_by_race[race_id].append(row)
            snapshot_keys[(str(row.get("run_id") or ""), race_id, str(row.get("horse_id") or ""))] += 1

    predictions: list[dict[str, Any]] = []
    snapshot_races: set[str] = set()
    for race_id, rows in snapshots_by_race.items():
        selection = select_canonical_run(race_id, rows)
        if not selection.resolved:
            continue
        snapshot_races.add(race_id)
        for row in selection.selected_rows:
            predictions.append(
                {
                    **row,
                    "_prediction_source": snapshot_source_name,
                    "_prediction_time": row.get("created_at"),
                    "_pre_race_proof": selection.pre_race_proof,
                    "_source_ordinal": None,
                    "_record_hash": canonical_sha256(row),
                    "_race_date_conflict": race_id in date_conflicts,
                }
            )

    verdict_keys: Counter[tuple[str, str]] = Counter()
    for verdict in bundle.velo_verdicts:
        race_id = str(verdict.get("race_id") or "")
        rows = _verdict_predictions(verdict)
        if not race_id or race_id in snapshot_races or not isinstance(rows, list):
            continue
        for ordinal, prediction in enumerate(rows, start=1):
            if not isinstance(prediction, dict):
                continue
            horse_id = str(prediction.get("horse_id") or "")
            verdict_keys[(race_id, horse_id)] += 1
            predictions.append(
                {
                    **prediction,
                    "race_id": race_id,
                    "race_date": date_by_race.get(race_id),
                    "course": verdict.get("course") or prediction.get("course"),
                    "off_time": verdict.get("off_time") or prediction.get("off_time"),
                    "rank": None,
                    "_prediction_source": SOURCE_VERDICT,
                    "_prediction_time": verdict.get("generated_at"),
                    "_pre_race_proof": None,
                    "_source_ordinal": ordinal,
                    "_record_hash": canonical_sha256({"verdict": verdict.get("id"), "prediction": prediction}),
                    "_race_date_conflict": race_id in date_conflicts,
                }
            )
    snapshot_excess = sum(count - 1 for count in snapshot_keys.values() if count > 1)
    verdict_excess = sum(count - 1 for count in verdict_keys.values() if count > 1)
    return predictions, snapshot_excess, verdict_excess


def build_crosswalk(bundle: SourceBundle) -> CrosswalkReport:
    """Crosswalk the four immutable source exports, classifying every row."""
    predictions, duplicate_snapshots, duplicate_verdicts = _prediction_rows(bundle)
    scorecards: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in bundle.canonical_model_scorecards:
        scorecards[(str(row.get("race_id") or ""), str(row.get("horse_id") or ""))].append(row)
    truths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in bundle.velo_race_truth:
        truths[str(row.get("race_id") or "")].append(row)

    records: list[CrosswalkRecord] = []
    identity_counts = Counter((str(row.get("race_id") or ""), str(row.get("horse_id") or "")) for row in predictions)
    for prediction in predictions:
        race_id = str(prediction.get("race_id") or "")
        horse_id = str(prediction.get("horse_id") or "")
        official_rows = scorecards.get((race_id, horse_id), [])
        eligible = [
            row
            for row in official_rows
            if _bool(row.get("official_evaluation_eligible"))
            and _bool(row.get("result_source_complete"))
            and row.get("result_source_hash")
        ]
        issues: list[str] = []
        if not race_id or not horse_id:
            issues.append("MISSING_IDENTITY")
        if prediction.get("_race_date_conflict"):
            issues.append("CONTRADICTORY_RACE_DATE")
        if identity_counts[(race_id, horse_id)] > 1:
            issues.append("DUPLICATE_OR_CONTRADICTORY_IDENTITY")

        names = {normalise_name(row.get("horse")) for row in official_rows if row.get("horse")}
        pred_name = normalise_name(prediction.get("horse"))
        if len(names) > 1 or (names and pred_name and pred_name not in names):
            issues.append("CONTRADICTORY_HORSE_IDENTITY")

        race_date = str(prediction.get("race_date") or _one(row.get("run_date") for row in official_rows) or "") or None
        course = prediction.get("course") or _one(row.get("course") for row in official_rows)
        off_time = prediction.get("off_time") or _one(row.get("off_time") for row in official_rows)
        prediction_dt = _utc(prediction.get("_prediction_time"))
        race_dt = _race_time_utc(race_date, off_time, course)
        if prediction_dt is None or race_dt is None or prediction_dt >= race_dt:
            issues.append("MISSING_PRE_RACE_TIMESTAMP_EVIDENCE")
        if (
            prediction.get("_prediction_source") in {SOURCE_SNAPSHOT, SOURCE_SNAPSHOT_LOCAL}
            and prediction.get("_pre_race_proof") != PROOF_PRE_RACE
        ):
            if "MISSING_PRE_RACE_TIMESTAMP_EVIDENCE" not in issues:
                issues.append("MISSING_PRE_RACE_TIMESTAMP_EVIDENCE")

        positions = {str(row.get("result_position")) for row in eligible if row.get("result_position") is not None}
        wins = {_bool(row.get("win")) for row in eligible if row.get("win") is not None}
        non_runners = {_bool(row.get("subject_is_non_runner")) for row in eligible}
        hashes = {str(row.get("result_source_hash")) for row in eligible if row.get("result_source_hash")}
        if not eligible or len(positions) > 1 or len(wins) > 1 or len(non_runners) > 1 or len(hashes) > 1:
            issues.append("MISSING_OR_UNVERIFIED_OFFICIAL_RESULT")

        truth_rows = truths.get(race_id, [])
        truth_winners = {str(row.get("actual_winner_id")) for row in truth_rows if row.get("actual_winner_id")}
        official_winner_ids = {str(row.get("horse_id")) for row in eligible if _bool(row.get("win"))}
        if not truth_winners:
            issues.append("MISSING_OR_UNVERIFIED_OFFICIAL_RESULT")
        elif len(truth_winners) > 1 or (official_winner_ids and truth_winners != official_winner_ids):
            issues.append("CONTRADICTORY_WINNER_TRUTH")

        non_runner = next(iter(non_runners)) if len(non_runners) == 1 else False
        result_position = next(iter(positions)) if len(positions) == 1 else None
        outcome = (1 if next(iter(wins)) else 0) if len(wins) == 1 and not non_runner else None
        baseline = prediction.get("velo_prime_prob")
        challenger = prediction.get("sqpe_v17_prob")
        try:
            baseline = float(baseline) if baseline is not None else None
            challenger = float(challenger) if challenger is not None else None
        except (TypeError, ValueError):
            baseline = challenger = None
        if baseline is None or challenger is None or not (0 <= baseline <= 1 and 0 <= challenger <= 1):
            issues.append("MISSING_OR_INVALID_PROBABILITY")
        model_probabilities: dict[str, float | None] = {}
        for field_name in PROBABILITY_FIELDS:
            try:
                value = float(prediction[field_name]) if prediction.get(field_name) is not None else None
            except (TypeError, ValueError):
                value = None
            model_probabilities[field_name] = value if value is not None and 0 <= value <= 1 else None
        try:
            market_price = float(prediction["sp_dec"]) if prediction.get("sp_dec") is not None else None
        except (TypeError, ValueError):
            market_price = None
        if market_price is not None and market_price <= 1:
            market_price = None

        status = STATUS_COMPLETE if not issues and not non_runner and outcome is not None else STATUS_INCOMPLETE
        records.append(
            CrosswalkRecord(
                race_date=race_date,
                race_id=race_id,
                horse_id=horse_id,
                horse=prediction.get("horse"),
                prediction_source=str(prediction.get("_prediction_source")),
                prediction_time=prediction_dt.isoformat().replace("+00:00", "Z") if prediction_dt else None,
                race_time=race_dt.isoformat().replace("+00:00", "Z") if race_dt else None,
                rank=prediction.get("rank") if isinstance(prediction.get("rank"), int) else None,
                source_ordinal=prediction.get("_source_ordinal"),
                velo_prime_prob=baseline,
                sqpe_v17_prob=challenger,
                model_probabilities=model_probabilities,
                market_decimal_price=market_price,
                market_price_field="sp_dec" if market_price is not None else None,
                result_position=result_position,
                outcome=outcome,
                non_runner=non_runner,
                status=status,
                evidence_issues=sorted(set(issues)),
                evidence_hashes={
                    "prediction": [str(prediction.get("_record_hash"))],
                    "canonical_model_scorecards": sorted(canonical_sha256(row) for row in official_rows),
                    "velo_race_truth": sorted(canonical_sha256(row) for row in truth_rows),
                    "official_result_source": sorted(hashes),
                },
            )
        )

    by_date: dict[str, Counter[str]] = defaultdict(Counter)
    for row in records:
        day = row.race_date or "UNKNOWN"
        by_date[day]["complete_verified_runner_records" if row.status == STATUS_COMPLETE else "incomplete_records"] += 1
        if any(
            issue
            in {
                "DUPLICATE_OR_CONTRADICTORY_IDENTITY",
                "CONTRADICTORY_HORSE_IDENTITY",
                "CONTRADICTORY_RACE_DATE",
            }
            for issue in row.evidence_issues
        ):
            by_date[day]["duplicate_or_contradictory_identities"] += 1
        if "MISSING_PRE_RACE_TIMESTAMP_EVIDENCE" in row.evidence_issues:
            by_date[day]["missing_pre_race_timestamp_evidence"] += 1
        if any(
            issue in {"MISSING_OR_UNVERIFIED_OFFICIAL_RESULT", "CONTRADICTORY_WINNER_TRUTH"}
            for issue in row.evidence_issues
        ):
            by_date[day]["missing_or_unverified_official_results"] += 1
        if row.non_runner:
            by_date[day]["non_runners"] += 1

    raw_snapshots = (
        bundle.local_runner_prediction_snapshots
        if bundle.local_runner_prediction_snapshots
        else bundle.runner_prediction_snapshots
    )
    raw_snapshot_keys: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in raw_snapshots:
        key = (str(row.get("run_id") or ""), str(row.get("race_id") or ""), str(row.get("horse_id") or ""))
        raw_snapshot_keys[key].append(row)
    for duplicate_rows in raw_snapshot_keys.values():
        if len(duplicate_rows) > 1:
            day = str(duplicate_rows[0].get("race_date") or "UNKNOWN")
            by_date[day]["duplicate_or_contradictory_identities"] += len(duplicate_rows) - 1
    count_fields = (
        "complete_verified_runner_records",
        "incomplete_records",
        "duplicate_or_contradictory_identities",
        "missing_pre_race_timestamp_evidence",
        "missing_or_unverified_official_results",
        "non_runners",
    )
    counts_by_date = {day: {key: counts.get(key, 0) for key in count_fields} for day, counts in sorted(by_date.items())}
    source_counts = {
        SOURCE_SNAPSHOT: len(bundle.runner_prediction_snapshots),
        SOURCE_SNAPSHOT_LOCAL: len(bundle.local_runner_prediction_snapshots),
        "velo_verdicts": len(bundle.velo_verdicts),
        SOURCE_VERDICT: sum(len(_verdict_predictions(row)) for row in bundle.velo_verdicts),
        "canonical_model_scorecards": len(bundle.canonical_model_scorecards),
        "velo_race_truth": len(bundle.velo_race_truth),
        "crosswalk_records": len(records),
        "crosswalk.sqpe_v17_prob": sum(row.model_probabilities["sqpe_v17_prob"] is not None for row in records),
        "crosswalk.sqpe_no_rpr_shadow_prob": sum(
            row.model_probabilities["sqpe_no_rpr_shadow_prob"] is not None for row in records
        ),
        "crosswalk.pre_race_decimal_price": sum(row.market_decimal_price is not None for row in records),
    }
    source_hashes = {
        name: canonical_sha256(getattr(bundle, name))
        for name in (
            "runner_prediction_snapshots",
            "velo_verdicts",
            "canonical_model_scorecards",
            "velo_race_truth",
        )
    }
    if bundle.local_runner_prediction_snapshots:
        source_hashes[SOURCE_SNAPSHOT_LOCAL] = canonical_sha256(bundle.local_runner_prediction_snapshots)
        source_hashes["runner_prediction_snapshots.local_jsonl.file_manifest"] = canonical_sha256(
            bundle.local_snapshot_file_hashes
        )
    return CrosswalkReport(
        records,
        counts_by_date,
        source_counts,
        source_hashes,
        duplicate_snapshots,
        duplicate_verdicts,
    )


def frozen_holdout(
    report: CrosswalkReport, *, holdout_start: str, holdout_end: str | None = None
) -> tuple[list[Observation], dict[str, Any]]:
    """Build an identical paired cohort on a frozen chronological holdout."""
    races: dict[str, list[CrosswalkRecord]] = defaultdict(list)
    for row in report.records:
        if (
            row.race_date is not None
            and row.race_date >= holdout_start
            and (holdout_end is None or row.race_date <= holdout_end)
        ):
            races[row.race_id].append(row)
    selected: list[CrosswalkRecord] = []
    excluded_races: Counter[str] = Counter()
    for rows in races.values():
        starters = [row for row in rows if not row.non_runner]
        if any(row.status != STATUS_COMPLETE for row in starters):
            excluded_races["INCOMPLETE_STARTER_EVIDENCE"] += 1
            continue
        if sum(row.outcome == 1 for row in starters) != 1:
            excluded_races["WINNER_CARDINALITY_NOT_ONE"] += 1
            continue
        selected.extend(starters)
    selected.sort(key=lambda row: (row.race_date or "", row.race_id, row.horse_id))
    observations = [
        Observation(
            race_id=row.race_id,
            runner_id=row.horse_id,
            race_time=str(row.race_time),
            prediction_time=str(row.prediction_time),
            outcome=int(row.outcome),
            baseline_prob=float(row.velo_prime_prob),
            challenger_prob=float(row.sqpe_v17_prob),
        )
        for row in selected
    ]
    cohort_identity = [
        {"race_date": row.race_date, "race_id": row.race_id, "horse_id": row.horse_id} for row in selected
    ]
    manifest = {
        "holdout_start": holdout_start,
        "holdout_end": holdout_end,
        "runner_count": len(observations),
        "race_count": len({row.race_id for row in selected}),
        "cohort_sha256": canonical_sha256(cohort_identity),
        "comparison_cohort": "IDENTICAL_PAIRED_RUNNERS",
        "chronology": "FROZEN_DATE_RANGE",
        "baseline_model": "velo_prime_prob",
        "challenger_model": "sqpe_v17_prob",
        "source_hashes": report.source_hashes,
        "excluded_races": dict(excluded_races),
        "promotion_authority": False,
    }
    return observations, manifest


def frozen_model_holdout(
    report: CrosswalkReport,
    *,
    challenger_field: str,
    holdout_start: str,
    holdout_end: str | None = None,
    require_market_price: bool = False,
) -> tuple[list[Observation], list[MarketObservation], dict[str, Any]]:
    """Build a complete paired cohort for one captured historical model field."""
    if challenger_field not in PROBABILITY_FIELDS:
        raise ValueError(f"unsupported historical probability field: {challenger_field}")
    races: dict[str, list[CrosswalkRecord]] = defaultdict(list)
    for row in report.records:
        if (
            row.race_date is not None
            and row.race_date >= holdout_start
            and (holdout_end is None or row.race_date <= holdout_end)
        ):
            races[row.race_id].append(row)
    selected: list[CrosswalkRecord] = []
    excluded_races: Counter[str] = Counter()
    for rows in races.values():
        starters = [row for row in rows if not row.non_runner]
        if any(row.status != STATUS_COMPLETE for row in starters):
            excluded_races["INCOMPLETE_STARTER_EVIDENCE"] += 1
            continue
        if sum(row.outcome == 1 for row in starters) != 1:
            excluded_races["WINNER_CARDINALITY_NOT_ONE"] += 1
            continue
        if any(row.model_probabilities.get(challenger_field) is None for row in starters):
            excluded_races["MISSING_CHALLENGER_PROBABILITY"] += 1
            continue
        if require_market_price and any(row.market_decimal_price is None for row in starters):
            excluded_races["INCOMPLETE_MARKET_PRICE_COHORT"] += 1
            continue
        selected.extend(starters)
    selected.sort(key=lambda row: (row.race_date or "", row.race_id, row.horse_id))
    observations = [
        Observation(
            race_id=row.race_id,
            runner_id=row.horse_id,
            race_time=str(row.race_time),
            prediction_time=str(row.prediction_time),
            outcome=int(row.outcome),
            baseline_prob=float(row.velo_prime_prob),
            challenger_prob=float(row.model_probabilities[challenger_field]),
        )
        for row in selected
    ]
    market_observations = [
        MarketObservation(
            race_id=row.race_id,
            runner_id=row.horse_id,
            race_time=str(row.race_time),
            prediction_time=str(row.prediction_time),
            outcome=int(row.outcome),
            baseline_prob=float(row.velo_prime_prob),
            challenger_prob=float(row.model_probabilities[challenger_field]),
            decimal_price=float(row.market_decimal_price),
        )
        for row in selected
        if row.market_decimal_price is not None
    ]
    identity = [{"race_date": row.race_date, "race_id": row.race_id, "horse_id": row.horse_id} for row in selected]
    manifest = {
        "holdout_start": holdout_start,
        "holdout_end": holdout_end,
        "runner_count": len(observations),
        "race_count": len({row.race_id for row in selected}),
        "cohort_sha256": canonical_sha256(identity),
        "comparison_cohort": "IDENTICAL_PAIRED_COMPLETE_RACES",
        "chronology": "FROZEN_DATE_RANGE",
        "baseline_model": "velo_prime_prob",
        "challenger_model": challenger_field,
        "market_price_required": require_market_price,
        "market_price_field": "sp_dec" if require_market_price else None,
        "source_hashes": report.source_hashes,
        "excluded_races": dict(excluded_races),
        "promotion_authority": False,
    }
    return observations, market_observations, manifest
