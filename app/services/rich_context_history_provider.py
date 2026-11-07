"""Canonical, time-safe historical facts for the Rich Context shadow lane.

This module deliberately does not import the retired Racing API extractor or a
network client.  A caller must inject a repository backed by the canonical
``racing_horse_runs`` table.  The provider then enforces identity, temporal and
pagination completeness before it derives any feature.

Production Prime must not import this module.  Its output is evidence for an
isolated challenger only.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

SCHEMA_VERSION = "rich_context_history_v1"
CANONICAL_TABLE = "racing_horse_runs"
_NUMERIC_RP_ID = re.compile(r"^[1-9][0-9]*$")


@dataclass(frozen=True)
class HistoryPage:
    """One explicitly bounded repository page.

    ``total_count`` is the repository's count for the exact horse/cutoff query,
    not the table total.  Requiring it lets the provider reject a silently
    truncated history instead of treating a partial response as evidence.
    """

    rows: tuple[dict[str, Any], ...]
    offset: int
    limit: int
    total_count: int


class HistoricalRunRepository(Protocol):
    """Injected canonical repository; implementations must read one snapshot."""

    def fetch_page(
        self,
        *,
        horse_id: str,
        before_date: date,
        offset: int,
        limit: int,
    ) -> HistoryPage: ...


class PostgresHistoricalRunRepository:
    """DB-API adapter for ``public.racing_horse_runs``.

    The connection is injected by the governed runtime.  This adapter opens no
    socket and reads no credentials.  Callers should provide a repeatable-read,
    read-only transaction so the count and pages share one database snapshot.
    """

    _COLUMNS = (
        "id,horse_id,race_id,run_date,course,course_id,region,race_type,"
        "distance_f,going,race_class,position,position_int,is_win,is_place,"
        "official_rating,sp_dec,btn,weight_lbs,jockey_id,jockey,trainer_id,trainer"
    )

    def __init__(self, connection: Any):
        self._connection = connection

    def fetch_page(
        self,
        *,
        horse_id: str,
        before_date: date,
        offset: int,
        limit: int,
    ) -> HistoryPage:
        if offset < 0 or limit <= 0:
            raise ValueError("offset must be >= 0 and limit must be > 0")
        canonical_horse_id = str(horse_id).strip()
        if not _NUMERIC_RP_ID.fullmatch(canonical_horse_id):
            raise ValueError("horse_id must be an exact numeric Racing Post identity")
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.racing_horse_runs "
                "WHERE horse_id = %s AND run_date < %s",
                (canonical_horse_id, before_date),
            )
            total_count = int(cursor.fetchone()[0])
            cursor.execute(
                f"SELECT {self._COLUMNS} FROM public.racing_horse_runs "
                "WHERE horse_id = %s AND run_date < %s "
                "ORDER BY run_date DESC, id DESC LIMIT %s OFFSET %s",
                (canonical_horse_id, before_date, limit, offset),
            )
            names = [column[0] for column in cursor.description]
            rows = tuple(dict(zip(names, values, strict=True)) for values in cursor.fetchall())
        return HistoryPage(rows=rows, offset=offset, limit=limit, total_count=total_count)


class SupabaseHistoricalRunRepository:
    """Supabase-client adapter with exact count and bounded pagination.

    The authenticated client is injected by the governed runtime. This class
    owns no credentials and never falls back to another racing-data source.
    """

    _COLUMNS = (
        "id,horse_id,race_id,run_date,course,course_id,region,race_type,"
        "distance_f,going,race_class,position,position_int,is_win,is_place,"
        "official_rating,sp_dec,btn,weight_lbs,jockey_id,jockey,trainer_id,trainer"
    )

    def __init__(self, client: Any):
        self._client = client

    def fetch_page(
        self,
        *,
        horse_id: str,
        before_date: date,
        offset: int,
        limit: int,
    ) -> HistoryPage:
        if offset < 0 or limit <= 0:
            raise ValueError("offset must be >= 0 and limit must be > 0")
        canonical_horse_id = str(horse_id).strip()
        if not _NUMERIC_RP_ID.fullmatch(canonical_horse_id):
            raise ValueError("horse_id must be an exact numeric Racing Post identity")
        response = (
            self._client.table(CANONICAL_TABLE)
            .select(self._COLUMNS, count="exact")
            .eq("horse_id", canonical_horse_id)
            .lt("run_date", before_date.isoformat())
            .order("run_date", desc=True)
            .order("id", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        total_count = getattr(response, "count", None)
        if total_count is None:
            raise RuntimeError("Supabase history query did not return an exact count")
        rows = tuple(dict(row) for row in (getattr(response, "data", None) or []))
        return HistoryPage(rows=rows, offset=offset, limit=limit, total_count=int(total_count))


@dataclass(frozen=True)
class ProvenIdentityBridge:
    """Independently proven legacy-to-RP identity mapping.

    A bridge without a non-empty evidence reference is not proof and is ignored.
    Horse names are intentionally absent: they are never an identity key here.
    """

    legacy_horse_id: str
    rp_horse_id: str
    evidence_ref: str
    verified: bool = True


@dataclass(frozen=True)
class IdentityResolution:
    requested_horse_id: str | None
    canonical_horse_id: str | None
    method: str
    eligible: bool
    reason: str | None = None
    evidence_ref: str | None = None


def resolve_rp_identity(
    horse_id: Any,
    *,
    bridges: Sequence[ProvenIdentityBridge] = (),
) -> IdentityResolution:
    requested = str(horse_id).strip() if horse_id not in (None, "") else None
    if requested and _NUMERIC_RP_ID.fullmatch(requested):
        return IdentityResolution(requested, requested, "EXACT_NUMERIC_RP_ID", True)
    if not requested:
        return IdentityResolution(None, None, "UNRESOLVED", False, "MISSING_HORSE_ID")

    matches = [
        bridge
        for bridge in bridges
        if bridge.legacy_horse_id == requested
        and bridge.verified
        and bridge.evidence_ref.strip()
        and _NUMERIC_RP_ID.fullmatch(str(bridge.rp_horse_id).strip())
    ]
    canonical_ids = {str(item.rp_horse_id).strip() for item in matches}
    if len(canonical_ids) == 1:
        match = matches[0]
        return IdentityResolution(
            requested,
            next(iter(canonical_ids)),
            "PROVEN_LEGACY_BRIDGE",
            True,
            evidence_ref=match.evidence_ref,
        )
    if len(canonical_ids) > 1:
        return IdentityResolution(requested, None, "UNRESOLVED", False, "CONFLICTING_IDENTITY_BRIDGES")
    reason = "UNPROVEN_LEGACY_ID" if requested.startswith("hrs_") else "NON_NUMERIC_OR_AMBIGUOUS_ID"
    return IdentityResolution(requested, None, "UNRESOLVED", False, reason)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("as_of_cutoff must be timezone-aware")
    return value.astimezone(UTC)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError, ArithmeticError):
        return None


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _context_text(value: Any) -> str | None:
    """Normalize blank/whitespace text to missing, never to a matchable value."""
    text = " ".join(str(value or "").strip().split())
    return text or None


def _rate(rows: Sequence[dict[str, Any]], key: str) -> float | None:
    return (sum(bool(row.get(key)) for row in rows) / len(rows)) if rows else None


class CanonicalHistoryProvider:
    """Build auditable historical facts without silent defaults or leakage."""

    def __init__(self, repository: HistoricalRunRepository, *, page_size: int = 250):
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        self._repository = repository
        self._page_size = page_size

    def build(
        self,
        *,
        horse_id: Any,
        as_of_cutoff: datetime,
        current_course: str | None = None,
        current_distance_f: float | None = None,
        current_going: str | None = None,
        current_race_class: str | None = None,
        current_jockey_id: str | None = None,
        current_trainer_id: str | None = None,
        bridges: Sequence[ProvenIdentityBridge] = (),
    ) -> dict[str, Any]:
        cutoff = _as_utc(as_of_cutoff)
        current_course = _context_text(current_course)
        current_distance_f = _number(current_distance_f)
        current_going = _context_text(current_going)
        current_race_class = _context_text(current_race_class)
        current_jockey_id = _context_text(current_jockey_id)
        current_trainer_id = _context_text(current_trainer_id)
        identity = resolve_rp_identity(horse_id, bridges=bridges)
        base: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source_table": CANONICAL_TABLE,
            "as_of_cutoff": cutoff.isoformat().replace("+00:00", "Z"),
            "identity": {
                "requested_horse_id": identity.requested_horse_id,
                "canonical_horse_id": identity.canonical_horse_id,
                "method": identity.method,
                "evidence_ref": identity.evidence_ref,
            },
            "eligible": False,
            "ineligibility_reasons": [],
            "source_row_ids": [],
            "history_depth": 0,
            "coverage": {},
            "conflicts": [],
            "missingness": {},
            "features": {},
        }
        if not identity.eligible or not identity.canonical_horse_id:
            base["ineligibility_reasons"] = [identity.reason or "UNRESOLVED_IDENTITY"]
            return base

        # racing_horse_runs is date-granular. Excluding the whole race day is
        # the only truthful way to prove a run did not occur after an intraday
        # race cutoff.
        before_date = cutoff.date()
        rows: list[dict[str, Any]] = []
        offset = 0
        expected_total: int | None = None
        while True:
            page = self._repository.fetch_page(
                horse_id=identity.canonical_horse_id,
                before_date=before_date,
                offset=offset,
                limit=self._page_size,
            )
            if page.offset != offset or page.limit != self._page_size or page.total_count < 0:
                base["ineligibility_reasons"] = ["INVALID_REPOSITORY_PAGE_METADATA"]
                return base
            if expected_total is None:
                expected_total = page.total_count
            elif expected_total != page.total_count:
                base["ineligibility_reasons"] = ["HISTORY_CHANGED_DURING_PAGINATION"]
                return base
            rows.extend(dict(row) for row in page.rows)
            offset += len(page.rows)
            if offset >= page.total_count:
                break
            if not page.rows:
                base["ineligibility_reasons"] = ["PAGINATION_INCOMPLETE"]
                return base

        if expected_total != len(rows):
            base["ineligibility_reasons"] = ["PAGINATION_INCOMPLETE"]
            return base

        conflicts: list[str] = []
        valid_rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            row_horse_id = str(row.get("horse_id") or "").strip()
            try:
                run_date = date.fromisoformat(str(row.get("run_date"))[:10])
            except (TypeError, ValueError):
                conflicts.append(f"INVALID_RUN_DATE:{row_id or 'UNKNOWN'}")
                continue
            if not row_id or row_id in seen_ids:
                conflicts.append(f"MISSING_OR_DUPLICATE_SOURCE_ROW_ID:{row_id or 'UNKNOWN'}")
                continue
            if row_horse_id != identity.canonical_horse_id:
                conflicts.append(f"HORSE_ID_MISMATCH:{row_id}")
                continue
            if run_date >= before_date:
                conflicts.append(f"TEMPORAL_LEAKAGE:{row_id}")
                continue
            seen_ids.add(row_id)
            normalized = dict(row)
            normalized["_run_date"] = run_date
            valid_rows.append(normalized)

        valid_rows.sort(key=lambda row: (row["_run_date"], int(row["id"])), reverse=True)
        base["source_row_ids"] = [str(row["id"]) for row in valid_rows]
        base["history_depth"] = len(valid_rows)
        base["conflicts"] = conflicts
        if conflicts:
            base["ineligibility_reasons"] = ["SOURCE_ROW_CONFLICT"]
            return base
        if not valid_rows:
            base["ineligibility_reasons"] = ["NO_PRE_CUTOFF_HISTORY"]
            base["missingness"] = {"history": True}
            return base

        features, coverage, missingness = self._derive(
            valid_rows,
            cutoff_date=before_date,
            current_course=current_course,
            current_distance_f=current_distance_f,
            current_going=current_going,
            current_race_class=current_race_class,
            current_jockey_id=current_jockey_id,
            current_trainer_id=current_trainer_id,
        )
        base.update(
            eligible=True,
            coverage=coverage,
            missingness=missingness,
            features=features,
        )
        return base

    @staticmethod
    def _derive(
        rows: Sequence[dict[str, Any]],
        *,
        cutoff_date: date,
        current_course: str | None,
        current_distance_f: float | None,
        current_going: str | None,
        current_race_class: str | None,
        current_jockey_id: str | None,
        current_trainer_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, bool]]:
        recent = rows[0]
        days = [(cutoff_date - row["_run_date"]).days for row in rows]
        course_rows = [row for row in rows if current_course and _norm(row.get("course")) == _norm(current_course)]
        distance_rows = [
            row
            for row in rows
            if current_distance_f is not None
            and _number(row.get("distance_f")) is not None
            and abs(_number(row.get("distance_f")) - float(current_distance_f)) <= 0.5
        ]
        going_rows = [row for row in rows if current_going and _norm(row.get("going")) == _norm(current_going)]
        class_rows = [
            row for row in rows if current_race_class and _norm(row.get("race_class")) == _norm(current_race_class)
        ]
        jockey_pair_rows = [
            row for row in rows if current_jockey_id and str(row.get("jockey_id") or "") == str(current_jockey_id)
        ]
        trainer_rows = [
            row for row in rows if current_trainer_id and str(row.get("trainer_id") or "") == str(current_trainer_id)
        ]
        numeric_positions = [_number(row.get("position_int")) for row in rows]
        numeric_positions = [value for value in numeric_positions if value is not None]
        ratings = [_number(row.get("official_rating")) for row in rows]
        ratings = [value for value in ratings if value is not None]
        margins = [_number(row.get("btn")) for row in rows]
        margins = [value for value in margins if value is not None]

        features = {
            "days_since_last_run": days[0],
            "runs_30d": sum(day <= 30 for day in days),
            "runs_90d": sum(day <= 90 for day in days),
            "runs_365d": sum(day <= 365 for day in days),
            "career_history_rows": len(rows),
            "win_rate": _rate(rows, "is_win"),
            "place_rate": _rate(rows, "is_place"),
            "last_position": _number(recent.get("position_int")),
            "average_position": (sum(numeric_positions) / len(numeric_positions)) if numeric_positions else None,
            "latest_official_rating": _number(recent.get("official_rating")),
            "best_official_rating": max(ratings) if ratings else None,
            "average_beaten_margin": (sum(margins) / len(margins)) if margins else None,
            "course_runs": len(course_rows) if current_course else None,
            "course_win_rate": _rate(course_rows, "is_win") if current_course else None,
            "course_place_rate": _rate(course_rows, "is_place") if current_course else None,
            "distance_runs": len(distance_rows) if current_distance_f is not None else None,
            "distance_win_rate": _rate(distance_rows, "is_win") if current_distance_f is not None else None,
            "distance_place_rate": _rate(distance_rows, "is_place") if current_distance_f is not None else None,
            "going_runs": len(going_rows) if current_going else None,
            "going_win_rate": _rate(going_rows, "is_win") if current_going else None,
            "class_runs": len(class_rows) if current_race_class else None,
            "class_win_rate": _rate(class_rows, "is_win") if current_race_class else None,
            "current_jockey_pair_runs": len(jockey_pair_rows) if current_jockey_id else None,
            "current_jockey_pair_win_rate": _rate(jockey_pair_rows, "is_win") if current_jockey_id else None,
            "current_trainer_runs": len(trainer_rows) if current_trainer_id else None,
            "current_trainer_win_rate": _rate(trainer_rows, "is_win") if current_trainer_id else None,
            "jockey_changed_from_last_run": (
                str(recent.get("jockey_id") or "") != str(current_jockey_id)
                if current_jockey_id and recent.get("jockey_id")
                else None
            ),
            "trainer_changed_from_last_run": (
                str(recent.get("trainer_id") or "") != str(current_trainer_id)
                if current_trainer_id and recent.get("trainer_id")
                else None
            ),
        }
        contexts = {
            "course": current_course,
            "distance": current_distance_f,
            "going": current_going,
            "race_class": current_race_class,
            "jockey": current_jockey_id,
            "trainer": current_trainer_id,
        }
        coverage = {
            "history_rows": len(rows),
            "families": {
                "recency": {"available": True, "matching_rows": len(rows)},
                "course": {"available": current_course is not None, "matching_rows": len(course_rows)},
                "distance": {"available": current_distance_f is not None, "matching_rows": len(distance_rows)},
                "going": {"available": current_going is not None, "matching_rows": len(going_rows)},
                "class": {"available": current_race_class is not None, "matching_rows": len(class_rows)},
                "jockey_pair": {"available": current_jockey_id is not None, "matching_rows": len(jockey_pair_rows)},
                "trainer_continuity": {"available": current_trainer_id is not None, "matching_rows": len(trainer_rows)},
            },
        }
        missingness = {
            f"context_{key}": value is None for key, value in contexts.items()
        }
        missingness.update({key: value is None for key, value in features.items()})
        return features, coverage, missingness
