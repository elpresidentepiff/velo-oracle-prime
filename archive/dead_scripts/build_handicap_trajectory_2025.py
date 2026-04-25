"""
Build intelligence.handicap_trajectory_2025.

Per-horse, per-run handicap trajectory layer for 2025.
Source: intelligence.horse_run_history_2025 (read-only).
Output: intelligence.handicap_trajectory_2025.
No production tables touched. No API calls.

OR coverage:
  52,070 rows have a numeric OR  (or_rating ~ '^\\d+$')
  31,979 rows have or_rating = '–' (en dash) → NULL numeric

Flag definitions:
  mark_compression_flag      : or_change < 0 (handicapper lowered the mark)
  mark_restored_flag         : or_change > 0 AND current mark >= career peak to date
  first_run_after_drop_flag  : previous run had a mark drop (prev or_change < 0)
  or_plateau_flag            : same mark for 3 consecutive runs
  or_treadmill_flag          : 5+ runs with OR data, full-year range <= 5 points

last_winning_or_to_date:
  Highest OR at which the horse has won in 2025, before this run.
  (Peak winning mark, not strictly "most recent" — most useful for
   trajectory context; see comments in CTE for rationale.)

Run: python scripts/build_handicap_trajectory_2025.py
"""
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]


def sql(query: str, timeout: int = 180):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=timeout,
    )
    return r.status_code, r.json()


# ── Step 1: Create table ────────────────────────────────────────────────────────
print("Step 1: Create table")
status, result = sql("""
DROP TABLE IF EXISTS intelligence.handicap_trajectory_2025;

CREATE TABLE intelligence.handicap_trajectory_2025 (
    traj_id                     BIGSERIAL   PRIMARY KEY,

    -- Entity linkage
    entity_id                   UUID        NOT NULL,
    run_id                      BIGINT      NOT NULL,

    -- Run reference
    race_id                     TEXT,
    date                        DATE        NOT NULL,

    -- Horse context
    horse_name_raw              TEXT        NOT NULL,
    trainer                     TEXT,
    course                      TEXT,
    dist                        TEXT,

    -- OR fields: raw preserved, numeric parsed
    or_rating_raw               TEXT,
    or_rating_num               SMALLINT,

    -- Trajectory fields
    prev_or                     SMALLINT,
    or_change                   SMALLINT,
    career_peak_or_to_date      SMALLINT,
    current_vs_peak_or          SMALLINT,
    last_winning_or_to_date     SMALLINT,
    current_vs_last_winning_or  SMALLINT,

    -- Flags
    mark_compression_flag       BOOLEAN     NOT NULL DEFAULT FALSE,
    mark_restored_flag          BOOLEAN     NOT NULL DEFAULT FALSE,
    first_run_after_drop_flag   BOOLEAN     NOT NULL DEFAULT FALSE,
    or_plateau_flag             BOOLEAN     NOT NULL DEFAULT FALSE,
    or_treadmill_flag           BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Identity
    identity_confidence         TEXT,
    ambiguity_flag              BOOLEAN
);
""")
print(f"  {status} {result}")


# ── Step 2: Populate ─────────────────────────────────────────────────────────────
print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.handicap_trajectory_2025 (
    entity_id, run_id, race_id, date, horse_name_raw, trainer, course, dist,
    or_rating_raw, or_rating_num,
    prev_or, or_change,
    career_peak_or_to_date, current_vs_peak_or,
    last_winning_or_to_date, current_vs_last_winning_or,
    mark_compression_flag, mark_restored_flag,
    first_run_after_drop_flag, or_plateau_flag, or_treadmill_flag,
    identity_confidence, ambiguity_flag
)

-- CTE 1: Parse OR, keep raw
WITH base AS (
    SELECT
        run_id,
        entity_id,
        race_id,
        date,
        horse                   AS horse_name_raw,
        trainer,
        course,
        dist,
        or_rating               AS or_rating_raw,
        -- Numeric OR: pure digit strings only; en-dash ('–') and blanks → NULL
        CASE
            WHEN or_rating ~ '^\\d+$' THEN or_rating::SMALLINT
            ELSE NULL
        END                     AS or_rating_num,
        is_win,
        identity_confidence,
        ambiguity_flag
    FROM intelligence.horse_run_history_2025
),

-- CTE 2: All window computations in one pass
lagged AS (
    SELECT
        *,
        -- Previous OR within entity (chronological)
        LAG(or_rating_num) OVER w                               AS prev_or,
        -- Preceding OR values for plateau detection
        LAG(or_rating_num, 1) OVER w                            AS prev_or_1,
        LAG(or_rating_num, 2) OVER w                            AS prev_or_2,
        -- Career peak OR *before* this run (ROWS 1 PRECEDING excludes current)
        MAX(or_rating_num) OVER (
            PARTITION BY entity_id
            ORDER BY date, race_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )                                                        AS career_peak_or_to_date,
        -- Highest OR at which horse has won in 2025, before this run
        -- (MAX of winning-run ORs — conservative, auditable, no IGNORE NULLS needed)
        MAX(CASE WHEN is_win THEN or_rating_num END) OVER (
            PARTITION BY entity_id
            ORDER BY date, race_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        )                                                        AS last_winning_or_to_date,
        -- Entity-level OR stats for treadmill detection (full 2025 partition)
        MAX(or_rating_num) OVER (PARTITION BY entity_id)        AS entity_max_or,
        MIN(or_rating_num) OVER (PARTITION BY entity_id)        AS entity_min_or,
        COUNT(or_rating_num) OVER (PARTITION BY entity_id)      AS entity_or_count
    FROM base
    WINDOW w AS (PARTITION BY entity_id ORDER BY date, race_id)
),

-- CTE 3: Compute derived delta fields (requires lagged values from CTE 2)
derived AS (
    SELECT
        *,
        (or_rating_num - prev_or)::SMALLINT                     AS or_change,
        (or_rating_num - career_peak_or_to_date)::SMALLINT      AS current_vs_peak_or,
        (or_rating_num - last_winning_or_to_date)::SMALLINT     AS current_vs_last_winning_or
    FROM lagged
),

-- CTE 4: Add prev_or_change for first_run_after_drop_flag
flagged AS (
    SELECT
        *,
        LAG(or_change) OVER (
            PARTITION BY entity_id ORDER BY date, race_id
        )                                                        AS prev_or_change
    FROM derived
)

SELECT
    entity_id, run_id, race_id, date, horse_name_raw, trainer, course, dist,
    or_rating_raw,
    or_rating_num,
    prev_or,
    or_change,
    career_peak_or_to_date,
    current_vs_peak_or,
    last_winning_or_to_date,
    current_vs_last_winning_or,
    -- mark_compression: mark was lowered by handicapper from previous run
    COALESCE(or_change < 0, FALSE)                                          AS mark_compression_flag,
    -- mark_restored: mark raised AND now at or above previous career peak
    COALESCE(or_change > 0 AND current_vs_peak_or >= 0, FALSE)             AS mark_restored_flag,
    -- first_run_after_drop: the immediately preceding run had a mark reduction
    COALESCE(prev_or_change < 0 AND or_change IS NOT NULL, FALSE)          AS first_run_after_drop_flag,
    -- or_plateau: same mark for 3 consecutive runs
    COALESCE(
        or_rating_num IS NOT NULL
        AND or_rating_num = prev_or_1
        AND or_rating_num = prev_or_2,
        FALSE
    )                                                                        AS or_plateau_flag,
    -- or_treadmill: 5+ runs with OR data, full-year OR range <= 5 points
    COALESCE(
        entity_or_count >= 5 AND (entity_max_or - entity_min_or) <= 5,
        FALSE
    )                                                                        AS or_treadmill_flag,
    identity_confidence,
    ambiguity_flag
FROM flagged;
""", timeout=300)
print(f"  INSERT status: {status}")
if status != 201:
    print(f"  ERROR: {result}")


# ── Step 3: Indexes ──────────────────────────────────────────────────────────────
print("Step 3: Indexes")
for idx_sql in [
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (entity_id);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (date);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (horse_name_raw);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (trainer);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (or_rating_num);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (mark_compression_flag);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (mark_restored_flag);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (or_treadmill_flag);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2025 (identity_confidence);",
]:
    sql(idx_sql, timeout=30)
print("  done")


# ── Step 4: Summary stats ────────────────────────────────────────────────────────
print("\nStep 4: Summary")
_, rows = sql("""
    SELECT
        COUNT(*)                                                AS total_rows,
        COUNT(DISTINCT entity_id)                              AS distinct_entities,
        COUNT(*) FILTER (WHERE or_rating_num IS NOT NULL)      AS rows_with_numeric_or,
        COUNT(*) FILTER (WHERE or_rating_num IS NULL)          AS rows_no_numeric_or,
        COUNT(*) FILTER (WHERE or_change IS NOT NULL)          AS rows_with_or_change,
        COUNT(*) FILTER (WHERE mark_compression_flag)          AS mark_compressed,
        COUNT(*) FILTER (WHERE mark_restored_flag)             AS mark_restored,
        COUNT(*) FILTER (WHERE first_run_after_drop_flag)      AS first_after_drop,
        COUNT(*) FILTER (WHERE or_plateau_flag)                AS on_plateau,
        COUNT(*) FILTER (WHERE or_treadmill_flag)              AS on_treadmill,
        COUNT(*) FILTER (WHERE career_peak_or_to_date IS NOT NULL) AS has_career_peak,
        COUNT(*) FILTER (WHERE last_winning_or_to_date IS NOT NULL) AS has_winning_or,
        MIN(or_rating_num)                                     AS min_or,
        MAX(or_rating_num)                                     AS max_or
    FROM intelligence.handicap_trajectory_2025
""")
for row in rows:
    for k, v in row.items():
        print(f"  {k}: {v}")


# ── Step 5: OR completeness by confidence tier ──────────────────────────────────
print("\nOR completeness by confidence tier:")
_, rows = sql("""
    SELECT
        identity_confidence,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE or_rating_num IS NOT NULL) AS with_or,
        ROUND(
            COUNT(*) FILTER (WHERE or_rating_num IS NOT NULL)::numeric
            / COUNT(*) * 100, 1
        ) AS pct_with_or
    FROM intelligence.handicap_trajectory_2025
    GROUP BY identity_confidence
    ORDER BY identity_confidence
""")
for row in rows:
    print(f"  {row}")


print("\nDone.")
