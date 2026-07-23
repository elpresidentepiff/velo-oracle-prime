"""Real-database proof of the atomic active-run lock (SCORING-RUN-ADMISSION-HARDENING-01,
P0-4). A mocked Supabase client cannot prove database-level atomicity -- this test runs
two genuinely concurrent transactions against a real temporary Postgres instance and
asserts the partial unique index (service_name, source_date) WHERE run_state='running'
actually rejects the second one. Skips cleanly if no test Postgres is reachable (e.g. in
an environment without Docker) rather than failing the suite."""
import os
import threading
import uuid

import pytest

psycopg2 = pytest.importorskip("psycopg2")

_TEST_DSN = os.environ.get(
    "VELO_TEST_PG_DSN",
    "host=localhost port=55432 dbname=testdb user=postgres password=test",
)


def _pg_available():
    try:
        conn = psycopg2.connect(_TEST_DSN, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_available(), reason="no reachable test Postgres instance (set VELO_TEST_PG_DSN or run one locally)"
)


@pytest.fixture()
def pg_conn():
    conn = psycopg2.connect(_TEST_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_runs (
          id uuid PRIMARY KEY,
          service_name text NOT NULL,
          run_type text,
          source_date text NOT NULL,
          run_state text NOT NULL,
          status text,
          trigger_source text,
          started_at timestamptz,
          finished_at timestamptz,
          environment text,
          commit_sha text,
          error_message text
        );
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_runs_active_service_date
        ON pipeline_runs (service_name, source_date)
        WHERE run_state = 'running';
        """
    )
    yield conn
    conn.close()


def _insert_running_row(dsn, service_name, source_date, barrier, results, index):
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        barrier.wait(timeout=5)  # force both transactions to attempt insert at the same instant
        cur.execute(
            "INSERT INTO pipeline_runs (id, service_name, source_date, run_state, status, started_at) "
            "VALUES (%s, %s, %s, 'running', NULL, now())",
            (str(uuid.uuid4()), service_name, source_date),
        )
        conn.commit()
        results[index] = "OK"
    except Exception as e:
        conn.rollback()
        results[index] = f"REJECTED: {e.__class__.__name__}: {e}"
    finally:
        conn.close()


def test_two_concurrent_running_inserts_for_same_service_date_one_is_rejected(pg_conn):
    service_name = "velo-prime-scoring"
    source_date = f"concurrency-test-{uuid.uuid4().hex[:8]}"  # unique per test run, no cross-test interference

    barrier = threading.Barrier(2)
    results = [None, None]
    t1 = threading.Thread(target=_insert_running_row, args=(_TEST_DSN, service_name, source_date, barrier, results, 0))
    t2 = threading.Thread(target=_insert_running_row, args=(_TEST_DSN, service_name, source_date, barrier, results, 1))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    oks = [r for r in results if r == "OK"]
    rejected = [r for r in results if r and r.startswith("REJECTED")]

    assert len(oks) == 1, f"expected exactly one successful insert, got: {results}"
    assert len(rejected) == 1, f"expected exactly one rejected insert, got: {results}"
    assert "unique" in rejected[0].lower() or "duplicate" in rejected[0].lower(), (
        f"rejection should be the uniqueness constraint, got: {rejected[0]}"
    )

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pipeline_runs WHERE service_name=%s AND source_date=%s AND run_state='running'",
            (service_name, source_date),
        )
        (count,) = cur.fetchone()
    assert count == 1, "exactly one running row should exist after the race, regardless of which thread won"


def test_after_completing_first_run_a_second_running_insert_is_allowed(pg_conn):
    """Proves the atomic lock's scope precisely: it only blocks concurrent RUNNING rows.
    Once a row transitions to completed, the unique index no longer applies -- this is
    exactly why sequential re-scoring (the separate problem the admission gate in P0-1
    solves at the application layer) was possible even with this constraint in place."""
    service_name = "velo-prime-scoring"
    source_date = f"sequential-test-{uuid.uuid4().hex[:8]}"
    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())

    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO pipeline_runs (id, service_name, source_date, run_state, status, started_at) "
            "VALUES (%s, %s, %s, 'running', NULL, now())",
            (run_id_1, service_name, source_date),
        )
        cur.execute(
            "UPDATE pipeline_runs SET run_state='completed', status='PASS', finished_at=now() WHERE id=%s",
            (run_id_1,),
        )
        # Second insert for the same service+date must succeed now that the first is completed --
        # the DB constraint alone does not prevent this; only the application-level admission
        # gate (P0-1, tested in test_run_prime_today_admission.py) does.
        cur.execute(
            "INSERT INTO pipeline_runs (id, service_name, source_date, run_state, status, started_at) "
            "VALUES (%s, %s, %s, 'running', NULL, now())",
            (run_id_2, service_name, source_date),
        )
        cur.execute(
            "SELECT count(*) FROM pipeline_runs WHERE service_name=%s AND source_date=%s",
            (service_name, source_date),
        )
        (count,) = cur.fetchone()
    assert count == 2, "the DB constraint alone permits a second run once the first has completed"
