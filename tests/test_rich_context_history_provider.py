from __future__ import annotations

from datetime import UTC, date, datetime, timezone

import pytest

from app.services.rich_context_history_provider import (
    CanonicalHistoryProvider,
    HistoryPage,
    PostgresHistoricalRunRepository,
    ProvenIdentityBridge,
    SupabaseHistoricalRunRepository,
    resolve_rp_identity,
)


class _SupabaseResponse:
    data = [{"id": 1, "horse_id": "12345", "run_date": "2026-11-01"}]
    count = 1


class _SupabaseQuery:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return _SupabaseResponse() if name == "execute" else self
        return call


class _SupabaseClient:
    def __init__(self):
        self.query = _SupabaseQuery()

    def table(self, name):
        assert name == "racing_horse_runs"
        return self.query


def test_supabase_repository_requires_numeric_identity_and_exact_count():
    client = _SupabaseClient()
    repo = SupabaseHistoricalRunRepository(client)
    with pytest.raises(ValueError, match="numeric Racing Post"):
        repo.fetch_page(horse_id="hrs_1", before_date=date(2026, 11, 7), offset=0, limit=10)
    page = repo.fetch_page(horse_id="12345", before_date=date(2026, 11, 7), offset=0, limit=10)
    assert page.total_count == 1
    assert page.rows[0]["id"] == 1
    assert any(name == "select" and kwargs == {"count": "exact"} for name, _args, kwargs in client.query.calls)


def _row(row_id, run_date, *, horse_id="12345", position=2, course="Ascot", distance=8.0, **extra):
    row = {
        "id": row_id,
        "horse_id": horse_id,
        "race_id": f"race-{row_id}",
        "run_date": run_date,
        "course": course,
        "distance_f": distance,
        "going": "Good",
        "race_class": "2",
        "position_int": position,
        "is_win": position == 1,
        "is_place": position <= 3,
        "official_rating": 90 + row_id,
        "btn": float(position - 1),
        "jockey_id": "j1",
        "trainer_id": "t1",
    }
    row.update(extra)
    return row


class MemoryRepository:
    def __init__(self, rows, *, reported_total=None, leak_rows=False):
        self.rows = list(rows)
        self.reported_total = reported_total
        self.leak_rows = leak_rows
        self.calls = []

    def fetch_page(self, *, horse_id, before_date, offset, limit):
        self.calls.append((horse_id, before_date, offset, limit))
        eligible = [
            row for row in self.rows
            if row["horse_id"] == horse_id
            and (self.leak_rows or date.fromisoformat(str(row["run_date"])[:10]) < before_date)
        ]
        eligible.sort(key=lambda row: (str(row["run_date"]), row["id"]), reverse=True)
        total = len(eligible) if self.reported_total is None else self.reported_total
        return HistoryPage(tuple(eligible[offset : offset + limit]), offset, limit, total)


def test_identity_requires_numeric_rp_id_or_independently_proven_bridge():
    exact = resolve_rp_identity("12345")
    assert exact.eligible and exact.method == "EXACT_NUMERIC_RP_ID"

    unresolved = resolve_rp_identity("hrs_old")
    assert not unresolved.eligible and unresolved.reason == "UNPROVEN_LEGACY_ID"

    bridged = resolve_rp_identity(
        "hrs_old",
        bridges=[ProvenIdentityBridge("hrs_old", "12345", "audit:bridge-row-7")],
    )
    assert bridged.eligible and bridged.canonical_horse_id == "12345"
    assert bridged.method == "PROVEN_LEGACY_BRIDGE"


def test_name_suffix_and_country_like_ids_never_resolve_by_guess():
    for ambiguous in ("Thunder Road", "12345_AUS", "12345-GB", "rp_ASC_thunder-road"):
        result = resolve_rp_identity(ambiguous)
        assert not result.eligible
        assert result.canonical_horse_id is None


def test_conflicting_bridges_are_ineligible():
    result = resolve_rp_identity(
        "hrs_old",
        bridges=[
            ProvenIdentityBridge("hrs_old", "12345", "proof:a"),
            ProvenIdentityBridge("hrs_old", "67890", "proof:b"),
        ],
    )
    assert not result.eligible
    assert result.reason == "CONFLICTING_IDENTITY_BRIDGES"


def test_as_of_cutoff_excludes_same_day_and_future_rows():
    repo = MemoryRepository(
        [
            _row(1, "2026-11-05", position=1),
            _row(2, "2026-11-07", position=1),
            _row(3, "2026-11-08", position=1),
        ]
    )
    packet = CanonicalHistoryProvider(repo).build(
        horse_id="12345",
        as_of_cutoff=datetime(2026, 11, 7, 14, 0, tzinfo=UTC),
    )
    assert packet["eligible"] is True
    assert packet["source_row_ids"] == ["1"]
    assert packet["features"]["days_since_last_run"] == 2
    assert repo.calls[0][1] == date(2026, 11, 7)


def test_provider_rejects_temporal_leak_even_if_repository_violates_contract():
    repo = MemoryRepository([_row(1, "2026-11-07")], leak_rows=True)
    packet = CanonicalHistoryProvider(repo).build(
        horse_id="12345",
        as_of_cutoff=datetime(2026, 11, 7, 14, 0, tzinfo=UTC),
    )
    assert packet["eligible"] is False
    assert packet["ineligibility_reasons"] == ["SOURCE_ROW_CONFLICT"]
    assert packet["conflicts"] == ["TEMPORAL_LEAKAGE:1"]


def test_pagination_is_complete_and_derived_features_recompute_from_source_rows():
    rows = [
        _row(1, "2026-10-01", position=1),
        _row(2, "2026-10-15", position=2),
        _row(3, "2026-10-30", position=5, course="York", distance=10.0),
    ]
    repo = MemoryRepository(rows)
    packet = CanonicalHistoryProvider(repo, page_size=2).build(
        horse_id="12345",
        as_of_cutoff=datetime(2026, 11, 7, 10, 0, tzinfo=UTC),
        current_course="Ascot",
        current_distance_f=8.0,
        current_going="Good",
        current_race_class="2",
        current_jockey_id="j1",
        current_trainer_id="t1",
    )
    assert packet["eligible"] is True
    assert packet["history_depth"] == 3
    assert packet["source_row_ids"] == ["3", "2", "1"]
    assert len(repo.calls) == 2
    assert packet["features"]["win_rate"] == 1 / 3
    assert packet["features"]["place_rate"] == 2 / 3
    assert packet["features"]["course_runs"] == 2
    assert packet["features"]["course_win_rate"] == 0.5
    assert packet["features"]["distance_runs"] == 2
    assert packet["coverage"]["families"]["course"]["matching_rows"] == 2


def test_incomplete_pagination_is_ineligible_not_silently_truncated():
    repo = MemoryRepository([_row(1, "2026-10-01")], reported_total=2)
    packet = CanonicalHistoryProvider(repo, page_size=1).build(
        horse_id="12345",
        as_of_cutoff=datetime(2026, 11, 7, 10, 0, tzinfo=UTC),
    )
    assert packet["eligible"] is False
    assert packet["ineligibility_reasons"] == ["PAGINATION_INCOMPLETE"]


def test_unresolved_identity_never_calls_repository():
    repo = MemoryRepository([])
    packet = CanonicalHistoryProvider(repo).build(
        horse_id="Same Horse",
        as_of_cutoff=datetime(2026, 11, 7, 10, 0, tzinfo=UTC),
    )
    assert packet["eligible"] is False
    assert packet["source_row_ids"] == []
    assert repo.calls == []


def test_naive_cutoff_is_rejected():
    repo = MemoryRepository([])
    provider = CanonicalHistoryProvider(repo)
    try:
        provider.build(horse_id="12345", as_of_cutoff=datetime(2026, 11, 7, 10, 0))
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive cutoff should fail closed")


def test_postgres_repository_queries_numeric_identity_and_strict_cutoff_only():
    columns = [
        "id", "horse_id", "race_id", "run_date", "course", "course_id", "region",
        "race_type", "distance_f", "going", "race_class", "position", "position_int",
        "is_win", "is_place", "official_rating", "sp_dec", "btn", "weight_lbs",
        "jockey_id", "jockey", "trainer_id", "trainer",
    ]

    class Cursor:
        def __init__(self):
            self.calls = []
            self.description = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params):
            self.calls.append((sql, params))
            if sql.startswith("SELECT id"):
                self.description = [(name,) for name in columns]

        def fetchone(self):
            return (1,)

        def fetchall(self):
            return [tuple(_row(1, "2026-11-01").get(name) for name in columns)]

    class Connection:
        def __init__(self):
            self.last_cursor = None

        def cursor(self):
            self.last_cursor = Cursor()
            return self.last_cursor

    connection = Connection()
    page = PostgresHistoricalRunRepository(connection).fetch_page(
        horse_id="12345", before_date=date(2026, 11, 7), offset=0, limit=100
    )
    assert page.total_count == 1 and page.rows[0]["horse_id"] == "12345"
    calls = connection.last_cursor.calls
    assert all("horse_id = %s AND run_date < %s" in sql for sql, _ in calls)
    assert all(params[:2] == ("12345", date(2026, 11, 7)) for _, params in calls)
    assert all("WHERE horse =" not in sql and "OR horse =" not in sql for sql, _ in calls)


@pytest.mark.parametrize(
    ("argument", "family", "feature"),
    [
        ("current_course", "course", "course_runs"),
        ("current_distance_f", "distance", "distance_runs"),
        ("current_going", "going", "going_runs"),
        ("current_race_class", "class", "class_runs"),
        ("current_jockey_id", "jockey_pair", "current_jockey_pair_runs"),
        ("current_trainer_id", "trainer_continuity", "current_trainer_runs"),
    ],
)
def test_blank_context_is_missing_and_cannot_match_absent_history(argument, family, feature):
    row = _row(1, "2026-11-01")
    field_by_argument = {
        "current_course": "course",
        "current_going": "going",
        "current_race_class": "race_class",
        "current_jockey_id": "jockey_id",
        "current_trainer_id": "trainer_id",
    }
    if argument in field_by_argument:
        row[field_by_argument[argument]] = None
    kwargs = {argument: "   \t "}
    packet = CanonicalHistoryProvider(MemoryRepository([row])).build(
        horse_id="12345",
        as_of_cutoff=datetime(2026, 11, 7, 10, 0, tzinfo=UTC),
        **kwargs,
    )
    assert packet["eligible"] is True
    assert packet["coverage"]["families"][family] == {"available": False, "matching_rows": 0}
    assert packet["features"][feature] is None
    assert packet["missingness"][feature] is True


def test_postgres_adapter_rejects_non_numeric_identity_before_opening_cursor():
    class Connection:
        def cursor(self):
            raise AssertionError("cursor must not open for an ambiguous identity")

    repository = PostgresHistoricalRunRepository(Connection())
    for invalid in ("hrs_123", "123_AUS", "Same Horse", "  "):
        with pytest.raises(ValueError, match="numeric Racing Post identity"):
            repository.fetch_page(
                horse_id=invalid,
                before_date=date(2026, 11, 7),
                offset=0,
                limit=100,
            )
