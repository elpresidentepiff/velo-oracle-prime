"""
Build intelligence.handicap_trajectory_2024.
Source: intelligence.horse_run_history_2024 (read-only).
Run: python scripts/build_handicap_trajectory_2024.py
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
DROP TABLE IF EXISTS intelligence.handicap_trajectory_2024;
CREATE TABLE intelligence.handicap_trajectory_2024 (
    traj_id                     BIGSERIAL   PRIMARY KEY,
    entity_id                   UUID        NOT NULL,
    run_id                      BIGINT      NOT NULL,
    race_id                     TEXT,
    date                        DATE        NOT NULL,
    horse_name_raw              TEXT        NOT NULL,
    trainer                     TEXT,
    course                      TEXT,
    dist                        TEXT,
    or_rating_raw               TEXT,
    or_rating_num               SMALLINT,
    prev_or                     SMALLINT,
    or_change                   SMALLINT,
    career_peak_or_to_date      SMALLINT,
    current_vs_peak_or          SMALLINT,
    last_winning_or_to_date     SMALLINT,
    current_vs_last_winning_or  SMALLINT,
    mark_compression_flag       BOOLEAN     NOT NULL DEFAULT FALSE,
    mark_restored_flag          BOOLEAN     NOT NULL DEFAULT FALSE,
    first_run_after_drop_flag   BOOLEAN     NOT NULL DEFAULT FALSE,
    or_plateau_flag             BOOLEAN     NOT NULL DEFAULT FALSE,
    or_treadmill_flag           BOOLEAN     NOT NULL DEFAULT FALSE,
    identity_confidence         TEXT,
    ambiguity_flag              BOOLEAN
);""")
print(f"  {status}")

print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.handicap_trajectory_2024 (
    entity_id, run_id, race_id, date, horse_name_raw, trainer, course, dist,
    or_rating_raw, or_rating_num, prev_or, or_change,
    career_peak_or_to_date, current_vs_peak_or,
    last_winning_or_to_date, current_vs_last_winning_or,
    mark_compression_flag, mark_restored_flag, first_run_after_drop_flag,
    or_plateau_flag, or_treadmill_flag, identity_confidence, ambiguity_flag)
WITH base AS (
    SELECT run_id, entity_id, race_id, date, horse AS horse_name_raw, trainer, course, dist,
        or_rating AS or_rating_raw,
        CASE WHEN or_rating ~ '^\\d+$' THEN or_rating::SMALLINT ELSE NULL END AS or_rating_num,
        is_win, identity_confidence, ambiguity_flag
    FROM intelligence.horse_run_history_2024
),
lagged AS (
    SELECT *,
        LAG(or_rating_num) OVER w                            AS prev_or,
        LAG(or_rating_num, 1) OVER w                         AS prev_or_1,
        LAG(or_rating_num, 2) OVER w                         AS prev_or_2,
        MAX(or_rating_num) OVER (PARTITION BY entity_id ORDER BY date, race_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS career_peak_or_to_date,
        MAX(CASE WHEN is_win THEN or_rating_num END) OVER (PARTITION BY entity_id ORDER BY date, race_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS last_winning_or_to_date,
        MAX(or_rating_num) OVER (PARTITION BY entity_id) AS entity_max_or,
        MIN(or_rating_num) OVER (PARTITION BY entity_id) AS entity_min_or,
        COUNT(or_rating_num) OVER (PARTITION BY entity_id) AS entity_or_count
    FROM base WINDOW w AS (PARTITION BY entity_id ORDER BY date, race_id)
),
derived AS (
    SELECT *, (or_rating_num - prev_or)::SMALLINT AS or_change,
        (or_rating_num - career_peak_or_to_date)::SMALLINT AS current_vs_peak_or,
        (or_rating_num - last_winning_or_to_date)::SMALLINT AS current_vs_last_winning_or
    FROM lagged
),
flagged AS (
    SELECT *, LAG(or_change) OVER (PARTITION BY entity_id ORDER BY date, race_id) AS prev_or_change
    FROM derived
)
SELECT entity_id, run_id, race_id, date, horse_name_raw, trainer, course, dist,
    or_rating_raw, or_rating_num, prev_or, or_change,
    career_peak_or_to_date, current_vs_peak_or, last_winning_or_to_date, current_vs_last_winning_or,
    COALESCE(or_change < 0, FALSE) AS mark_compression_flag,
    COALESCE(or_change > 0 AND current_vs_peak_or >= 0, FALSE) AS mark_restored_flag,
    COALESCE(prev_or_change < 0 AND or_change IS NOT NULL, FALSE) AS first_run_after_drop_flag,
    COALESCE(or_rating_num IS NOT NULL AND or_rating_num = prev_or_1 AND or_rating_num = prev_or_2, FALSE) AS or_plateau_flag,
    COALESCE(entity_or_count >= 5 AND (entity_max_or - entity_min_or) <= 5, FALSE) AS or_treadmill_flag,
    identity_confidence, ambiguity_flag
FROM flagged;
""", timeout=420)
print(f"  INSERT status: {status}")
if status != 201: print(f"  ERROR: {result}")

print("Step 3: Indexes")
for idx in [
    "CREATE INDEX ON intelligence.handicap_trajectory_2024 (entity_id);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2024 (date);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2024 (mark_compression_flag);",
    "CREATE INDEX ON intelligence.handicap_trajectory_2024 (or_treadmill_flag);",]:
    sql(idx, 30)
print("  done")

print("\nStep 4: Summary")
_, rows = sql("""
    SELECT COUNT(*) AS total, COUNT(DISTINCT entity_id) AS entities,
        COUNT(*) FILTER (WHERE or_rating_num IS NOT NULL) AS has_or,
        COUNT(*) FILTER (WHERE mark_compression_flag) AS compressed,
        COUNT(*) FILTER (WHERE first_run_after_drop_flag) AS post_drop,
        COUNT(*) FILTER (WHERE or_treadmill_flag) AS treadmill,
        MIN(or_rating_num) AS min_or, MAX(or_rating_num) AS max_or
    FROM intelligence.handicap_trajectory_2024""")
for row in rows:
    for k,v in row.items(): print(f"  {k}: {v}")
print("\nDone.")
