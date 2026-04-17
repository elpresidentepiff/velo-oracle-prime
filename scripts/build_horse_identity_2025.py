"""
Build intelligence.horse_identity_resolution_2025 from public.raceform (2025 only).
DB-first. No Racing API calls. Read-only from raceform. No production tables touched.

Run: python scripts/build_horse_identity_2025.py
"""
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]


def sql(query: str, timeout: int = 120):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=timeout,
    )
    return r.status_code, r.json()


# ── Step 1: Schema ──────────────────────────────────────────────────────────────
print("Step 1: Create intelligence schema")
status, _ = sql("CREATE SCHEMA IF NOT EXISTS intelligence;")
print(f"  {status}")

# ── Step 2: Table ───────────────────────────────────────────────────────────────
print("Step 2: Create table")
status, result = sql("""
DROP TABLE IF EXISTS intelligence.horse_identity_resolution_2025;

CREATE TABLE intelligence.horse_identity_resolution_2025 (
    entity_id           UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    horse_name_raw      TEXT        NOT NULL,
    trainer_first_seen  TEXT,
    first_seen_date     DATE,
    last_seen_date      DATE,
    country             TEXT,
    sire                TEXT,
    dam                 TEXT,
    age_in_2025         SMALLINT,
    total_runs_2025     SMALLINT,
    trainer_count       SMALLINT,
    all_trainers        TEXT,
    identity_confidence TEXT        NOT NULL,
    ambiguity_flag      BOOLEAN     NOT NULL DEFAULT FALSE,
    ambiguity_reason    TEXT,
    resolved_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
""")
print(f"  {status} {result}")

# ── Step 3: Populate ────────────────────────────────────────────────────────────
# Build logic:
#   - One entity per horse_name in 2025
#   - Primary trainer = trainer with most runs
#   - trainer_first_seen = trainer on earliest date
#   - Country extracted from name suffix (IRE), (GB), etc.
#   - Ambiguity: horse with >1 trainer in 2025
#   - Confidence: ambiguous > medium > high
#   - Sire/dam conflicts = 0 (confirmed by probe), so first non-null value is safe
print("Step 3: Populate")

BUILD_SQL = """
INSERT INTO intelligence.horse_identity_resolution_2025 (
    horse_name_raw,
    trainer_first_seen,
    first_seen_date,
    last_seen_date,
    country,
    sire,
    dam,
    age_in_2025,
    total_runs_2025,
    trainer_count,
    all_trainers,
    identity_confidence,
    ambiguity_flag,
    ambiguity_reason,
    resolved_at
)
WITH base AS (
    SELECT
        horse,
        trainer,
        date,
        sire,
        dam,
        age,
        CASE
            WHEN horse LIKE '%(IRE)%' THEN 'IRE'
            WHEN horse LIKE '%(GB)%'  THEN 'GB'
            WHEN horse LIKE '%(FR)%'  THEN 'FR'
            WHEN horse LIKE '%(USA)%' THEN 'USA'
            WHEN horse LIKE '%(GER)%' THEN 'GER'
            WHEN horse LIKE '%(AUS)%' THEN 'AUS'
            WHEN horse LIKE '%(NZ)%'  THEN 'NZ'
            WHEN horse LIKE '%(SAF)%' THEN 'SAF'
            WHEN horse LIKE '%(ARG)%' THEN 'ARG'
            ELSE 'GB'
        END AS country_derived,
        COUNT(*) OVER (PARTITION BY horse, trainer) AS trainer_runs
    FROM public.raceform
    WHERE date >= '2025-01-01'
),
first_trainer AS (
    SELECT DISTINCT ON (horse)
        horse,
        trainer AS trainer_on_first_run
    FROM base
    ORDER BY horse, date ASC
),
horse_agg AS (
    SELECT
        b.horse,
        COUNT(*)                                                            AS total_runs,
        COUNT(DISTINCT b.trainer)                                           AS trainer_count,
        MIN(b.date)                                                         AS first_seen,
        MAX(b.date)                                                         AS last_seen,
        (array_agg(b.country_derived ORDER BY b.trainer_runs DESC))[1]     AS country,
        (array_agg(b.sire ORDER BY b.date)
            FILTER (WHERE b.sire IS NOT NULL AND b.sire <> ''))[1]         AS sire,
        (array_agg(b.dam  ORDER BY b.date)
            FILTER (WHERE b.dam  IS NOT NULL AND b.dam  <> ''))[1]         AS dam,
        MODE() WITHIN GROUP (ORDER BY b.age)                               AS age_mode,
        STRING_AGG(DISTINCT b.trainer, ' | ' ORDER BY b.trainer)           AS all_trainers
    FROM base b
    GROUP BY b.horse
),
classified AS (
    SELECT
        h.horse,
        ft.trainer_on_first_run                                             AS trainer_first_seen,
        h.first_seen,
        h.last_seen,
        h.country,
        h.sire,
        h.dam,
        h.age_mode::SMALLINT                                                AS age_in_2025,
        h.total_runs::SMALLINT                                              AS total_runs_2025,
        h.trainer_count::SMALLINT                                           AS trainer_count,
        h.all_trainers,
        CASE WHEN h.trainer_count > 1 THEN TRUE ELSE FALSE END             AS ambiguity_flag,
        CASE
            WHEN h.trainer_count > 1
            THEN 'multi_trainer:count=' || h.trainer_count::text
            ELSE NULL
        END                                                                  AS ambiguity_reason,
        CASE
            WHEN h.trainer_count > 1                THEN 'ambiguous'
            WHEN h.sire IS NOT NULL
             AND h.dam  IS NOT NULL                 THEN 'high'
            ELSE                                         'medium'
        END                                                                  AS identity_confidence
    FROM horse_agg h
    JOIN first_trainer ft ON ft.horse = h.horse
)
SELECT
    horse,
    trainer_first_seen,
    first_seen,
    last_seen,
    country,
    sire,
    dam,
    age_in_2025,
    total_runs_2025,
    trainer_count,
    all_trainers,
    identity_confidence,
    ambiguity_flag,
    ambiguity_reason,
    NOW()
FROM classified;
"""

status, result = sql(BUILD_SQL, timeout=180)
print(f"  INSERT status: {status}")
if status != 201:
    print(f"  ERROR: {result}")

# ── Step 4: Add indexes ─────────────────────────────────────────────────────────
print("Step 4: Indexes")
sql("CREATE INDEX ON intelligence.horse_identity_resolution_2025 (horse_name_raw);")
sql("CREATE INDEX ON intelligence.horse_identity_resolution_2025 (identity_confidence);")
sql("CREATE INDEX ON intelligence.horse_identity_resolution_2025 (ambiguity_flag);")
sql("CREATE INDEX ON intelligence.horse_identity_resolution_2025 (first_seen_date);")
print("  done")

# ── Step 5: Summary stats ───────────────────────────────────────────────────────
print("\nStep 5: Summary")
_, rows = sql("""
    SELECT
        COUNT(*)                                                AS total_entities,
        COUNT(*) FILTER (WHERE identity_confidence = 'high')   AS high_conf,
        COUNT(*) FILTER (WHERE identity_confidence = 'medium') AS medium_conf,
        COUNT(*) FILTER (WHERE identity_confidence = 'ambiguous') AS ambiguous_conf,
        COUNT(*) FILTER (WHERE ambiguity_flag = TRUE)          AS ambiguity_true,
        MIN(first_seen_date)                                   AS earliest,
        MAX(last_seen_date)                                    AS latest
    FROM intelligence.horse_identity_resolution_2025
""")
for row in rows:
    for k, v in row.items():
        print(f"  {k}: {v}")

_, amb = sql("""
    SELECT ambiguity_reason, COUNT(*) AS n
    FROM intelligence.horse_identity_resolution_2025
    WHERE ambiguity_flag = TRUE
    GROUP BY ambiguity_reason
    ORDER BY n DESC
    LIMIT 10
""")
print("\nTop ambiguity reasons:")
for row in amb:
    print(f"  {row}")

print("\nDone.")
