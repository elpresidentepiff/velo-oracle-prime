"""
Build intelligence.horse_run_history_2024.
Joins public.raceform (2024) to intelligence.horse_identity_resolution_2024.
Run: python scripts/build_horse_run_history_2024.py
"""
import os, requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]

def sql(query, timeout=240):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": query}, timeout=timeout)
    return r.status_code, r.json()

print("Step 1: Table")
status, result = sql("""
DROP TABLE IF EXISTS intelligence.horse_run_history_2024;
CREATE TABLE intelligence.horse_run_history_2024 (
    run_id              BIGSERIAL   PRIMARY KEY,
    entity_id           UUID        NOT NULL,
    identity_confidence TEXT        NOT NULL,
    ambiguity_flag      BOOLEAN     NOT NULL,
    ambiguity_reason    TEXT,
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
    is_win              BOOLEAN     NOT NULL DEFAULT FALSE,
    is_place            BOOLEAN     NOT NULL DEFAULT FALSE,
    run_number_2024     SMALLINT,
    days_since_last_run SMALLINT,
    layoff_flag         BOOLEAN     NOT NULL DEFAULT FALSE,
    long_layoff_flag    BOOLEAN     NOT NULL DEFAULT FALSE
);""")
print(f"  {status}")

print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.horse_run_history_2024 (
    entity_id, identity_confidence, ambiguity_flag, ambiguity_reason,
    date, race_id, horse, trainer, jockey, course, dist, going,
    class_raw, or_rating, rpr, ts, sp, sp_decimal, draw, wgt,
    headgear, pos, ran, comment,
    is_win, is_place, run_number_2024, days_since_last_run, layoff_flag, long_layoff_flag)
WITH joined AS (
    SELECT h.entity_id, h.identity_confidence, h.ambiguity_flag, h.ambiguity_reason,
        rf.date, rf.race_id, rf.horse, rf.trainer, rf.jockey, rf.course, rf.dist, rf.going,
        rf.class_raw, rf.or_rating, rf.rpr, rf.ts, rf.sp,
        CASE
            WHEN rf.sp IN ('EvensF', 'EvsJ', 'Evs') THEN 2.00
            WHEN rf.sp LIKE '%/%' THEN
                ROUND((SPLIT_PART(REGEXP_REPLACE(rf.sp, '[A-Za-z]+$', ''), '/', 1)::numeric
                       / NULLIF(SPLIT_PART(REGEXP_REPLACE(rf.sp, '[A-Za-z]+$', ''), '/', 2)::numeric, 0)) + 1, 2)
            ELSE NULL
        END AS sp_decimal,
        rf.draw, rf.wgt, rf.hg AS headgear, rf.pos, rf.ran, rf.comment,
        (rf.pos = '1')               AS is_win,
        (rf.pos IN ('1','2','3'))    AS is_place,
        ROW_NUMBER() OVER (PARTITION BY h.entity_id ORDER BY rf.date, rf.race_id) AS run_number_2024,
        rf.date - LAG(rf.date) OVER (PARTITION BY h.entity_id ORDER BY rf.date, rf.race_id) AS days_since_last_run
    FROM public.raceform rf
    JOIN intelligence.horse_identity_resolution_2024 h ON h.horse_name_raw = rf.horse
    WHERE rf.date >= '2024-01-01' AND rf.date < '2025-01-01'
)
SELECT entity_id, identity_confidence, ambiguity_flag, ambiguity_reason,
    date, race_id, horse, trainer, jockey, course, dist, going,
    class_raw, or_rating, rpr, ts, sp, sp_decimal, draw, wgt,
    headgear, pos, ran, comment, is_win, is_place,
    run_number_2024::SMALLINT,
    days_since_last_run::SMALLINT,
    COALESCE(days_since_last_run >= 28, FALSE) AS layoff_flag,
    COALESCE(days_since_last_run >= 90, FALSE) AS long_layoff_flag
FROM joined;
""", timeout=360)
print(f"  INSERT status: {status}")
if status != 201: print(f"  ERROR: {result}")

print("Step 3: Indexes")
for idx in [
    "CREATE INDEX ON intelligence.horse_run_history_2024 (entity_id);",
    "CREATE INDEX ON intelligence.horse_run_history_2024 (date);",
    "CREATE INDEX ON intelligence.horse_run_history_2024 (horse);",
    "CREATE INDEX ON intelligence.horse_run_history_2024 (trainer);",
    "CREATE INDEX ON intelligence.horse_run_history_2024 (is_win);",]:
    sql(idx, 30)
print("  done")

print("\nStep 4: Summary")
_, rows = sql("""
    SELECT COUNT(*) AS total_rows, COUNT(DISTINCT entity_id) AS entities,
           COUNT(*) FILTER (WHERE is_win) AS wins, COUNT(*) FILTER (WHERE layoff_flag) AS layoffs,
           ROUND(COUNT(*) FILTER (WHERE is_win)::numeric/COUNT(*)*100,2) AS win_pct,
           MIN(date) AS earliest, MAX(date) AS latest
    FROM intelligence.horse_run_history_2024""")
for row in rows:
    for k,v in row.items(): print(f"  {k}: {v}")
print("\nDone.")
