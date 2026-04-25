"""
Build intelligence.horse_run_history_2025.

Joins public.raceform (2025) to intelligence.horse_identity_resolution_2025.
One row per raceform runner entry.
Adds derived fields: days_since_last_run, run_number_lifetime_2025,
is_win, is_place, layoff_flag, long_layoff_flag, sp_decimal.

Source:  public.raceform + intelligence.horse_identity_resolution_2025
Output:  intelligence.horse_run_history_2025
No production tables touched. No API calls.

Run: python scripts/build_horse_run_history_2025.py
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
DROP TABLE IF EXISTS intelligence.horse_run_history_2025;

CREATE TABLE intelligence.horse_run_history_2025 (
    run_id              BIGSERIAL   PRIMARY KEY,

    -- Entity linkage
    entity_id           UUID        NOT NULL,
    identity_confidence TEXT        NOT NULL,
    ambiguity_flag      BOOLEAN     NOT NULL,
    ambiguity_reason    TEXT,

    -- Core race fields
    date                DATE        NOT NULL,
    race_id             TEXT,
    horse               TEXT        NOT NULL,
    trainer             TEXT,
    jockey              TEXT,
    course              TEXT,
    dist                TEXT,
    going               TEXT,
    class_raw           TEXT,
    or_rating           TEXT,
    rpr                 TEXT,
    ts                  TEXT,
    sp                  TEXT,
    sp_decimal          NUMERIC(8,2),
    draw                SMALLINT,
    wgt                 TEXT,
    headgear            TEXT,
    pos                 TEXT,
    ran                 SMALLINT,
    comment             TEXT,

    -- Derived fields
    is_win              BOOLEAN     NOT NULL DEFAULT FALSE,
    is_place            BOOLEAN     NOT NULL DEFAULT FALSE,
    run_number_2025     SMALLINT,
    days_since_last_run SMALLINT,
    layoff_flag         BOOLEAN     NOT NULL DEFAULT FALSE,
    long_layoff_flag    BOOLEAN     NOT NULL DEFAULT FALSE
);
""")
print(f"  {status} {result}")

# ── Step 2: Populate ────────────────────────────────────────────────────────────
# SP decimal conversion:
#   "12/1"    -> 13.0   (numerator/denominator + 1)
#   "9/2"     -> 5.5
#   "EvensF"  -> 2.0    (favourite at evens)
#   "EvsJ"    -> 2.0    (joint favourite at evens)
#   "Evs"     -> 2.0
#   NULL/other -> NULL
#
# days_since_last_run: LAG(date) within entity, ordered by date then race_id.
#   NULL on first run in 2025 (no prior run in this dataset).
#
# layoff_flag     : days_since_last_run >= 28
# long_layoff_flag: days_since_last_run >= 90
# is_win          : pos = '1'
# is_place        : pos IN ('1','2','3')
# run_number_2025 : ROW_NUMBER() within entity ordered by date, race_id

print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.horse_run_history_2025 (
    entity_id, identity_confidence, ambiguity_flag, ambiguity_reason,
    date, race_id, horse, trainer, jockey, course, dist, going,
    class_raw, or_rating, rpr, ts, sp, sp_decimal, draw, wgt,
    headgear, pos, ran, comment,
    is_win, is_place, run_number_2025,
    days_since_last_run, layoff_flag, long_layoff_flag
)
WITH joined AS (
    SELECT
        h.entity_id,
        h.identity_confidence,
        h.ambiguity_flag,
        h.ambiguity_reason,
        rf.date,
        rf.race_id,
        rf.horse,
        rf.trainer,
        rf.jockey,
        rf.course,
        rf.dist,
        rf.going,
        rf.class_raw,
        rf.or_rating,
        rf.rpr,
        rf.ts,
        rf.sp,
        -- SP decimal conversion
        -- Strip trailing suffix letters (F=favourite, J=joint) before numeric cast.
        -- e.g. "9/2F" -> "9/2", "100/30J" -> "100/30", "EvensF" -> handled above.
        CASE
            WHEN rf.sp IN ('EvensF', 'EvsJ', 'Evs') THEN 2.00
            WHEN rf.sp LIKE '%/%' THEN
                ROUND(
                    (SPLIT_PART(REGEXP_REPLACE(rf.sp, '[A-Za-z]+$', ''), '/', 1)::numeric
                     / NULLIF(SPLIT_PART(REGEXP_REPLACE(rf.sp, '[A-Za-z]+$', ''), '/', 2)::numeric, 0)
                    ) + 1,
                    2
                )
            ELSE NULL
        END                                                         AS sp_decimal,
        rf.draw,
        rf.wgt,
        rf.hg                                                       AS headgear,
        rf.pos,
        rf.ran,
        rf.comment,
        -- Derived: win / place
        (rf.pos = '1')                                              AS is_win,
        (rf.pos IN ('1', '2', '3'))                                 AS is_place,
        -- Derived: run sequence within entity in 2025
        ROW_NUMBER() OVER (
            PARTITION BY h.entity_id
            ORDER BY rf.date ASC, rf.race_id ASC
        )                                                           AS run_number_2025,
        -- Derived: days gap from prior run within entity
        rf.date - LAG(rf.date) OVER (
            PARTITION BY h.entity_id
            ORDER BY rf.date ASC, rf.race_id ASC
        )                                                           AS days_since_last_run
    FROM public.raceform rf
    JOIN intelligence.horse_identity_resolution_2025 h
        ON h.horse_name_raw = rf.horse
    WHERE rf.date >= '2025-01-01'
)
SELECT
    entity_id, identity_confidence, ambiguity_flag, ambiguity_reason,
    date, race_id, horse, trainer, jockey, course, dist, going,
    class_raw, or_rating, rpr, ts, sp, sp_decimal, draw, wgt,
    headgear, pos, ran, comment,
    is_win,
    is_place,
    run_number_2025::SMALLINT,
    days_since_last_run::SMALLINT,
    COALESCE(days_since_last_run >= 28, FALSE)   AS layoff_flag,
    COALESCE(days_since_last_run >= 90, FALSE)   AS long_layoff_flag
FROM joined;
""", timeout=240)
print(f"  INSERT status: {status}")
if status != 201:
    print(f"  ERROR: {result}")

# ── Step 3: Indexes ─────────────────────────────────────────────────────────────
print("Step 3: Indexes")
for idx_sql in [
    "CREATE INDEX ON intelligence.horse_run_history_2025 (entity_id);",
    "CREATE INDEX ON intelligence.horse_run_history_2025 (date);",
    "CREATE INDEX ON intelligence.horse_run_history_2025 (horse);",
    "CREATE INDEX ON intelligence.horse_run_history_2025 (trainer);",
    "CREATE INDEX ON intelligence.horse_run_history_2025 (course);",
    "CREATE INDEX ON intelligence.horse_run_history_2025 (identity_confidence);",
    "CREATE INDEX ON intelligence.horse_run_history_2025 (ambiguity_flag);",
    "CREATE INDEX ON intelligence.horse_run_history_2025 (is_win);",
]:
    sql(idx_sql, timeout=30)
print("  done")

# ── Step 4: Summary stats ───────────────────────────────────────────────────────
print("\nStep 4: Summary")
_, rows = sql("""
    SELECT
        COUNT(*)                                                AS total_rows,
        COUNT(DISTINCT entity_id)                              AS distinct_entities,
        COUNT(*) FILTER (WHERE is_win)                         AS wins,
        COUNT(*) FILTER (WHERE is_place)                       AS places,
        COUNT(*) FILTER (WHERE layoff_flag)                    AS layoff_flags,
        COUNT(*) FILTER (WHERE long_layoff_flag)               AS long_layoff_flags,
        COUNT(*) FILTER (WHERE days_since_last_run IS NULL)    AS first_runs_in_2025,
        COUNT(*) FILTER (WHERE ambiguity_flag)                 AS ambiguous_rows,
        COUNT(*) FILTER (WHERE sp_decimal IS NULL)             AS null_sp_decimal,
        MIN(date)                                              AS earliest,
        MAX(date)                                              AS latest
    FROM intelligence.horse_run_history_2025
""")
for row in rows:
    for k, v in row.items():
        print(f"  {k}: {v}")

# Null profile for key fields
print("\nNull profile:")
_, nulls = sql("""
    SELECT
        COUNT(*) FILTER (WHERE or_rating IS NULL OR or_rating = '-')  AS null_or,
        COUNT(*) FILTER (WHERE rpr IS NULL OR rpr = '-')              AS null_rpr,
        COUNT(*) FILTER (WHERE draw IS NULL)                           AS null_draw,
        COUNT(*) FILTER (WHERE headgear IS NULL)                       AS null_headgear,
        COUNT(*) FILTER (WHERE trainer IS NULL)                        AS null_trainer,
        COUNT(*) FILTER (WHERE jockey IS NULL)                         AS null_jockey,
        COUNT(*) FILTER (WHERE comment IS NULL)                        AS null_comment
    FROM intelligence.horse_run_history_2025
""")
for row in nulls:
    for k, v in row.items():
        print(f"  {k}: {v}")

print("\nDone.")
