"""
Build intelligence.setup_restore_events_2025.

Per-horse, per-run setup restoration layer for 2025.
Detects when a horse is returned to conditions under which it has previously won.

Source tables (read-only):
  intelligence.horse_run_history_2025      — per-run history + is_win flag
  (intelligence.handicap_trajectory_2025 not needed — OR joins omitted for simplicity)

Output: intelligence.setup_restore_events_2025.
No production tables touched. No API calls.

Surface derivation (from going field):
  'Standard', 'Standard To Slow', 'Fast', 'Slow' OR course ILIKE '%(AW)%'  → 'AW'
  'Sloppy', 'Muddy'                                                          → 'Dirt'
  All other going values                                                      → 'Turf'

Dist matching: exact string match (e.g. '6f' = '6f', '2m4f' = '2m4f').
  Half-furlong variants ('2m4f' vs '2m4½f') are treated as different distances.
  This is honest — do not collapse distances unless the data warrants it.

Prior win scope: 2025 only (only data available in horse_run_history_2025).
  This means setup restore can only fire if the horse has won earlier in 2025
  at the same conditions. It will not fire on the first win at any course.

best_X_to_date: most recent prior winning condition (last element of chronological
  winning-conditions array before this run). NULL if no prior wins.

Flag definitions:
  prior_win_at_course_flag  : entity won at this exact course in 2025, before this run
  prior_win_at_surface_flag : entity won on this surface in 2025, before this run
  prior_win_at_dist_flag    : entity won at this exact dist in 2025, before this run
  surface_restore_flag      : alias for prior_win_at_surface_flag (readability)
  course_restore_flag       : alias for prior_win_at_course_flag
  trip_restore_flag         : prior_win_at_dist_flag AND prior_win_at_surface_flag
  full_setup_restore_flag   : all three (course + surface + dist) match a prior win

Run: python scripts/build_setup_restore_events_2025.py
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


# ── Step 1: Create table ─────────────────────────────────────────────────────────
print("Step 1: Create table")
status, result = sql("""
DROP TABLE IF EXISTS intelligence.setup_restore_events_2025;

CREATE TABLE intelligence.setup_restore_events_2025 (
    restore_id                BIGSERIAL   PRIMARY KEY,

    -- Entity linkage
    entity_id                 UUID        NOT NULL,
    run_id                    BIGINT      NOT NULL,

    -- Run reference
    race_id                   TEXT,
    date                      DATE        NOT NULL,

    -- Horse context
    horse_name_raw            TEXT        NOT NULL,
    trainer                   TEXT,
    course                    TEXT,
    surface                   TEXT,       -- 'AW' | 'Turf' | 'Dirt'
    dist                      TEXT,

    -- Identity
    identity_confidence       TEXT,
    ambiguity_flag            BOOLEAN,

    -- Prior win flags (scope: 2025 wins before this run)
    prior_win_at_course_flag  BOOLEAN     NOT NULL DEFAULT FALSE,
    prior_win_at_surface_flag BOOLEAN     NOT NULL DEFAULT FALSE,
    prior_win_at_dist_flag    BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Composite restore flags
    trip_restore_flag         BOOLEAN     NOT NULL DEFAULT FALSE,
    surface_restore_flag      BOOLEAN     NOT NULL DEFAULT FALSE,
    course_restore_flag       BOOLEAN     NOT NULL DEFAULT FALSE,
    full_setup_restore_flag   BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Best conditions to date (most recent prior winning conditions)
    best_dist_to_date         TEXT,
    best_surface_to_date      TEXT,
    best_course_to_date       TEXT
);
""")
print(f"  {status} {result}")


# ── Step 2: Populate ─────────────────────────────────────────────────────────────
print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.setup_restore_events_2025 (
    entity_id, run_id, race_id, date, horse_name_raw, trainer,
    course, surface, dist,
    identity_confidence, ambiguity_flag,
    prior_win_at_course_flag, prior_win_at_surface_flag, prior_win_at_dist_flag,
    trip_restore_flag, surface_restore_flag, course_restore_flag, full_setup_restore_flag,
    best_dist_to_date, best_surface_to_date, best_course_to_date
)

-- CTE 1: Source data with surface derived from going + course name
WITH base AS (
    SELECT
        run_id,
        entity_id,
        race_id,
        date,
        horse               AS horse_name_raw,
        trainer,
        course,
        dist,
        is_win,
        identity_confidence,
        ambiguity_flag,
        -- Surface: AW going descriptors OR explicit (AW) in course name
        CASE
            WHEN going IN ('Standard', 'Standard To Slow', 'Fast', 'Slow')
                 OR course ILIKE '%(AW)%'  THEN 'AW'
            WHEN going IN ('Sloppy', 'Muddy')                              THEN 'Dirt'
            ELSE                                                                 'Turf'
        END                 AS surface
    FROM intelligence.horse_run_history_2025
),

-- CTE 2: Window-aggregate winning conditions before each run.
--   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING:
--   collects all prior runs within the entity, ordered chronologically.
--   array_remove(..., NULL) strips non-winning (NULL) entries so only
--   winning conditions appear in each array.
wins_agg AS (
    SELECT
        *,
        -- Chronological arrays of winning course/surface/dist before this run
        array_remove(
            array_agg(CASE WHEN is_win THEN course  END) OVER w_prev, NULL
        )   AS win_courses,
        array_remove(
            array_agg(CASE WHEN is_win THEN surface END) OVER w_prev, NULL
        )   AS win_surfaces,
        array_remove(
            array_agg(CASE WHEN is_win THEN dist    END) OVER w_prev, NULL
        )   AS win_dists
    FROM base
    WINDOW w_prev AS (
        PARTITION BY entity_id
        ORDER BY date, race_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    )
),

-- CTE 3: Derive flags and best-conditions from array membership
restore_flags AS (
    SELECT
        *,
        -- Prior win flags: is current course/surface/dist in the winning arrays?
        COALESCE(course  = ANY(win_courses),   FALSE) AS prior_win_at_course_flag,
        COALESCE(surface = ANY(win_surfaces),  FALSE) AS prior_win_at_surface_flag,
        COALESCE(dist    = ANY(win_dists),     FALSE) AS prior_win_at_dist_flag,
        -- Best conditions = most recent prior winning conditions
        -- (last element of chronological array = most recent win)
        win_courses[array_length(win_courses,  1)]    AS best_course_to_date,
        win_surfaces[array_length(win_surfaces,1)]    AS best_surface_to_date,
        win_dists[array_length(win_dists,    1)]      AS best_dist_to_date
    FROM wins_agg
)

SELECT
    entity_id, run_id, race_id, date, horse_name_raw, trainer,
    course, surface, dist,
    identity_confidence, ambiguity_flag,
    prior_win_at_course_flag,
    prior_win_at_surface_flag,
    prior_win_at_dist_flag,
    -- trip = dist + surface match
    COALESCE(prior_win_at_dist_flag AND prior_win_at_surface_flag, FALSE)
        AS trip_restore_flag,
    -- surface and course aliases (explicit for readability in queries)
    prior_win_at_surface_flag   AS surface_restore_flag,
    prior_win_at_course_flag    AS course_restore_flag,
    -- full = course + surface + dist all match a prior 2025 win
    COALESCE(
        prior_win_at_course_flag
        AND prior_win_at_surface_flag
        AND prior_win_at_dist_flag,
        FALSE
    )                           AS full_setup_restore_flag,
    best_dist_to_date,
    best_surface_to_date,
    best_course_to_date
FROM restore_flags;
""", timeout=300)
print(f"  INSERT status: {status}")
if status != 201:
    print(f"  ERROR: {result}")


# ── Step 3: Indexes ──────────────────────────────────────────────────────────────
print("Step 3: Indexes")
for idx_sql in [
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (entity_id);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (date);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (horse_name_raw);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (trainer);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (course);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (surface);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (full_setup_restore_flag);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (trip_restore_flag);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (course_restore_flag);",
    "CREATE INDEX ON intelligence.setup_restore_events_2025 (identity_confidence);",
]:
    sql(idx_sql, timeout=30)
print("  done")


# ── Step 4: Summary stats ────────────────────────────────────────────────────────
print("\nStep 4: Summary")
_, rows = sql("""
    SELECT
        COUNT(*)                                                AS total_rows,
        COUNT(DISTINCT entity_id)                              AS distinct_entities,
        COUNT(*) FILTER (WHERE prior_win_at_course_flag)       AS prior_win_at_course,
        COUNT(*) FILTER (WHERE prior_win_at_surface_flag)      AS prior_win_at_surface,
        COUNT(*) FILTER (WHERE prior_win_at_dist_flag)         AS prior_win_at_dist,
        COUNT(*) FILTER (WHERE trip_restore_flag)              AS trip_restore,
        COUNT(*) FILTER (WHERE course_restore_flag)            AS course_restore,
        COUNT(*) FILTER (WHERE full_setup_restore_flag)        AS full_setup_restore,
        COUNT(*) FILTER (WHERE best_course_to_date IS NOT NULL) AS has_any_prior_win
    FROM intelligence.setup_restore_events_2025
""")
for row in rows:
    for k, v in row.items():
        print(f"  {k}: {v}")

print("\nSurface distribution:")
_, rows = sql("""
    SELECT surface, COUNT(*) AS total,
           COUNT(*) FILTER (WHERE prior_win_at_surface_flag) AS restore_fires
    FROM intelligence.setup_restore_events_2025
    GROUP BY surface ORDER BY total DESC
""")
for row in rows:
    print(f"  {row}")

print("\nTop courses by restore events (full_setup):")
_, rows = sql("""
    SELECT course, COUNT(*) AS full_restores
    FROM intelligence.setup_restore_events_2025
    WHERE full_setup_restore_flag = TRUE
    GROUP BY course ORDER BY full_restores DESC LIMIT 10
""")
for row in rows:
    print(f"  {row}")

print("\nDone.")
