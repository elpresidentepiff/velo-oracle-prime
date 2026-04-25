"""
Build intelligence.setup_restore_events_2024.
Source: intelligence.horse_run_history_2024 (read-only).
Run: python scripts/build_setup_restore_events_2024.py
"""
import os, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]

def sql(query, timeout=300):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": query}, timeout=timeout)
    return r.status_code, r.json()

print("Step 1: Table")
status, result = sql("""
DROP TABLE IF EXISTS intelligence.setup_restore_events_2024;
CREATE TABLE intelligence.setup_restore_events_2024 (
    restore_id                BIGSERIAL   PRIMARY KEY,
    entity_id                 UUID        NOT NULL,
    run_id                    BIGINT      NOT NULL,
    race_id                   TEXT,
    date                      DATE        NOT NULL,
    horse_name_raw            TEXT        NOT NULL,
    trainer                   TEXT,
    course                    TEXT,
    surface                   TEXT,
    dist                      TEXT,
    identity_confidence       TEXT,
    ambiguity_flag            BOOLEAN,
    prior_win_at_course_flag  BOOLEAN     NOT NULL DEFAULT FALSE,
    prior_win_at_surface_flag BOOLEAN     NOT NULL DEFAULT FALSE,
    prior_win_at_dist_flag    BOOLEAN     NOT NULL DEFAULT FALSE,
    trip_restore_flag         BOOLEAN     NOT NULL DEFAULT FALSE,
    surface_restore_flag      BOOLEAN     NOT NULL DEFAULT FALSE,
    course_restore_flag       BOOLEAN     NOT NULL DEFAULT FALSE,
    full_setup_restore_flag   BOOLEAN     NOT NULL DEFAULT FALSE,
    best_dist_to_date         TEXT,
    best_surface_to_date      TEXT,
    best_course_to_date       TEXT
);""")
print(f"  {status}")

print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.setup_restore_events_2024 (
    entity_id, run_id, race_id, date, horse_name_raw, trainer,
    course, surface, dist, identity_confidence, ambiguity_flag,
    prior_win_at_course_flag, prior_win_at_surface_flag, prior_win_at_dist_flag,
    trip_restore_flag, surface_restore_flag, course_restore_flag, full_setup_restore_flag,
    best_dist_to_date, best_surface_to_date, best_course_to_date)
WITH base AS (
    SELECT run_id, entity_id, race_id, date, horse AS horse_name_raw, trainer,
        course, dist, is_win, identity_confidence, ambiguity_flag,
        CASE WHEN going IN ('Standard','Standard To Slow','Fast','Slow') OR course ILIKE '%(AW)%' THEN 'AW'
             WHEN going IN ('Sloppy','Muddy') THEN 'Dirt'
             ELSE 'Turf' END AS surface
    FROM intelligence.horse_run_history_2024
),
wins_agg AS (
    SELECT *,
        array_remove(array_agg(CASE WHEN is_win THEN course  END) OVER w_prev, NULL) AS win_courses,
        array_remove(array_agg(CASE WHEN is_win THEN surface END) OVER w_prev, NULL) AS win_surfaces,
        array_remove(array_agg(CASE WHEN is_win THEN dist    END) OVER w_prev, NULL) AS win_dists
    FROM base
    WINDOW w_prev AS (PARTITION BY entity_id ORDER BY date, race_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
),
restore_flags AS (
    SELECT *,
        COALESCE(course  = ANY(win_courses),  FALSE) AS prior_win_at_course_flag,
        COALESCE(surface = ANY(win_surfaces), FALSE) AS prior_win_at_surface_flag,
        COALESCE(dist    = ANY(win_dists),    FALSE) AS prior_win_at_dist_flag,
        win_courses[array_length(win_courses,  1)]   AS best_course_to_date,
        win_surfaces[array_length(win_surfaces,1)]   AS best_surface_to_date,
        win_dists[array_length(win_dists,    1)]     AS best_dist_to_date
    FROM wins_agg
)
SELECT entity_id, run_id, race_id, date, horse_name_raw, trainer,
    course, surface, dist, identity_confidence, ambiguity_flag,
    prior_win_at_course_flag, prior_win_at_surface_flag, prior_win_at_dist_flag,
    COALESCE(prior_win_at_dist_flag AND prior_win_at_surface_flag, FALSE) AS trip_restore_flag,
    prior_win_at_surface_flag AS surface_restore_flag,
    prior_win_at_course_flag  AS course_restore_flag,
    COALESCE(prior_win_at_course_flag AND prior_win_at_surface_flag AND prior_win_at_dist_flag, FALSE) AS full_setup_restore_flag,
    best_dist_to_date, best_surface_to_date, best_course_to_date
FROM restore_flags;
""", timeout=420)
print(f"  INSERT status: {status}")
if status != 201: print(f"  ERROR: {result}")

print("Step 3: Indexes")
for idx in [
    "CREATE INDEX ON intelligence.setup_restore_events_2024 (entity_id);",
    "CREATE INDEX ON intelligence.setup_restore_events_2024 (date);",
    "CREATE INDEX ON intelligence.setup_restore_events_2024 (full_setup_restore_flag);",
    "CREATE INDEX ON intelligence.setup_restore_events_2024 (trip_restore_flag);",]:
    sql(idx, 30)
print("  done")

print("\nStep 4: Summary")
_, rows = sql("""
    SELECT COUNT(*) AS total, COUNT(DISTINCT entity_id) AS entities,
        COUNT(*) FILTER (WHERE full_setup_restore_flag) AS full_restore,
        COUNT(*) FILTER (WHERE trip_restore_flag) AS trip_restore,
        COUNT(*) FILTER (WHERE course_restore_flag) AS course_restore,
        COUNT(*) FILTER (WHERE best_course_to_date IS NOT NULL) AS has_any_prior_win
    FROM intelligence.setup_restore_events_2024""")
for row in rows:
    for k,v in row.items(): print(f"  {k}: {v}")
print("\nDone.")
