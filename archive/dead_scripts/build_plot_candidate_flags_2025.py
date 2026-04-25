"""
Build intelligence.plot_candidate_flags_2025.

Rules-based candidate queue. Not a predictive engine.
Surfaces horses whose 2025 pattern suggests hidden readiness, restored setup,
handicap release, or reactivation. All flags are deterministic boolean rules —
no weights, no scores, no model outputs.

Source tables (read-only):
  intelligence.horse_run_history_2025
  intelligence.handicap_trajectory_2025
  intelligence.setup_restore_events_2025
  (horse_identity_resolution_2025 fields already in horse_run_history)

All three sources join on run_id with 100% coverage (verified pre-build).

Flag definitions
────────────────
Individual candidate flags (rule combinations):

  mark_restore_candidate:
    first_run_after_drop_flag = TRUE
    AND last_winning_or_to_date IS NOT NULL
    AND current_vs_last_winning_or BETWEEN -8 AND 5
    → First run after handicapper dropped the mark, now running within 8 points
      below or 5 above the mark they last won at. The OR ceiling has been
      partially released.

  setup_restore_candidate:
    trip_restore_flag OR course_restore_flag OR full_setup_restore_flag
    → Returned to any condition where they have previously won in 2025.

  reactivation_candidate:
    layoff_flag AND (prior_win_at_course_flag OR prior_win_at_surface_flag
                     OR prior_win_at_dist_flag)
    → Coming back from ≥28 days off to conditions matching a prior 2025 win.

  compression_plus_restore:
    mark_compression_flag AND (trip_restore_flag OR full_setup_restore_flag)
    → Mark actively lowered by handicapper AND simultaneously returned to
      a winning trip or full setup. Classic plot pressure pattern.

  post_drop_restore:
    first_run_after_drop_flag AND (trip_restore_flag OR course_restore_flag
                                    OR full_setup_restore_flag)
    → First start after a mark drop, in a known winning environment.
      Strongest raw combination.

  course_specialist_return:
    prior_win_at_course_flag AND identity_confidence != 'ambiguous'
    → Horse has won at this exact course in 2025, running there again.
      Requires clean identity (no ambiguous entity).

  full_restore_live:
    full_setup_restore_flag AND identity_confidence = 'high'
    → All three restore dimensions match a prior win AND the entity is
      high-confidence. Maximum restore signal.

Composite flags:
  plot_pressure_flag:
    ANY of: mark_compression_flag, first_run_after_drop_flag,
            or_treadmill_flag, trip_restore_flag, full_setup_restore_flag,
            reactivation_candidate
    → Entry gate to the candidate queue.

  manual_review_priority:
    2+ independent THEMES firing (see theme definitions in SQL).
    Themes are grouped to avoid double-counting overlapping flags:
      handicap_theme, restore_theme, reactivation_theme, mark_restore_theme

  plot_reason_codes (TEXT[]):
    Array of short string codes for all active conditions on this run.
    Use 'code' = ANY(plot_reason_codes) to query.

Run: python scripts/build_plot_candidate_flags_2025.py
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


# ── Step 1: Create table ──────────────────────────────────────────────────────────
print("Step 1: Create table")
status, result = sql("""
DROP TABLE IF EXISTS intelligence.plot_candidate_flags_2025;

CREATE TABLE intelligence.plot_candidate_flags_2025 (
    candidate_id                BIGSERIAL   PRIMARY KEY,

    -- Entity linkage
    entity_id                   UUID        NOT NULL,
    run_id                      BIGINT      NOT NULL,

    -- Run reference
    race_id                     TEXT,
    date                        DATE        NOT NULL,

    -- Horse context
    horse_name_raw              TEXT        NOT NULL,
    trainer                     TEXT,

    -- Identity
    identity_confidence         TEXT,
    ambiguity_flag              BOOLEAN,

    -- Raw inputs (carried through for context)
    days_since_last_run         SMALLINT,
    layoff_flag                 BOOLEAN,
    long_layoff_flag            BOOLEAN,
    mark_compression_flag       BOOLEAN,
    mark_restored_flag          BOOLEAN,
    first_run_after_drop_flag   BOOLEAN,
    or_treadmill_flag           BOOLEAN,
    or_rating_num               SMALLINT,
    or_change                   SMALLINT,
    current_vs_last_winning_or  SMALLINT,
    current_vs_peak_or          SMALLINT,
    trip_restore_flag           BOOLEAN,
    surface_restore_flag        BOOLEAN,
    course_restore_flag         BOOLEAN,
    full_setup_restore_flag     BOOLEAN,

    -- Individual candidate flags
    mark_restore_candidate      BOOLEAN     NOT NULL DEFAULT FALSE,
    setup_restore_candidate     BOOLEAN     NOT NULL DEFAULT FALSE,
    reactivation_candidate      BOOLEAN     NOT NULL DEFAULT FALSE,
    compression_plus_restore    BOOLEAN     NOT NULL DEFAULT FALSE,
    post_drop_restore           BOOLEAN     NOT NULL DEFAULT FALSE,
    course_specialist_return    BOOLEAN     NOT NULL DEFAULT FALSE,
    full_restore_live           BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Composite flags
    plot_pressure_flag          BOOLEAN     NOT NULL DEFAULT FALSE,
    manual_review_priority      BOOLEAN     NOT NULL DEFAULT FALSE,
    plot_reason_codes           TEXT[]
);
""")
print(f"  {status} {result}")


# ── Step 2: Populate ──────────────────────────────────────────────────────────────
print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.plot_candidate_flags_2025 (
    entity_id, run_id, race_id, date, horse_name_raw, trainer,
    identity_confidence, ambiguity_flag,
    days_since_last_run, layoff_flag, long_layoff_flag,
    mark_compression_flag, mark_restored_flag, first_run_after_drop_flag,
    or_treadmill_flag, or_rating_num, or_change,
    current_vs_last_winning_or, current_vs_peak_or,
    trip_restore_flag, surface_restore_flag, course_restore_flag, full_setup_restore_flag,
    mark_restore_candidate, setup_restore_candidate, reactivation_candidate,
    compression_plus_restore, post_drop_restore, course_specialist_return, full_restore_live,
    plot_pressure_flag, manual_review_priority, plot_reason_codes
)

-- CTE 1: Join all three intelligence tables on run_id
WITH joined AS (
    SELECT
        h.entity_id,
        h.run_id,
        h.race_id,
        h.date,
        h.horse                         AS horse_name_raw,
        h.trainer,
        h.identity_confidence,
        h.ambiguity_flag,
        h.days_since_last_run,
        h.layoff_flag,
        h.long_layoff_flag,
        -- Handicap trajectory fields
        t.mark_compression_flag,
        t.mark_restored_flag,
        t.first_run_after_drop_flag,
        t.or_treadmill_flag,
        t.or_plateau_flag,
        t.or_rating_num,
        t.or_change,
        t.last_winning_or_to_date,
        t.current_vs_last_winning_or,
        t.current_vs_peak_or,
        -- Setup restore fields
        s.prior_win_at_course_flag,
        s.prior_win_at_surface_flag,
        s.prior_win_at_dist_flag,
        s.trip_restore_flag,
        s.surface_restore_flag,
        s.course_restore_flag,
        s.full_setup_restore_flag
    FROM intelligence.horse_run_history_2025 h
    LEFT JOIN intelligence.handicap_trajectory_2025 t ON t.run_id = h.run_id
    LEFT JOIN intelligence.setup_restore_events_2025 s ON s.run_id = h.run_id
),

-- CTE 2: Derive the individual candidate flags
derived AS (
    SELECT
        *,

        -- mark_restore_candidate:
        --   First run after mark drop, now within striking range of last winning OR.
        --   -8 to +5 range: forgiving of one more point of compression above the win mark.
        COALESCE(
            first_run_after_drop_flag
            AND last_winning_or_to_date IS NOT NULL
            AND current_vs_last_winning_or BETWEEN -8 AND 5,
            FALSE
        )   AS mark_restore_candidate,

        -- setup_restore_candidate:
        --   Returned to any dimension of a previously winning setup.
        COALESCE(
            trip_restore_flag OR course_restore_flag OR full_setup_restore_flag,
            FALSE
        )   AS setup_restore_candidate,

        -- reactivation_candidate:
        --   Back from ≥28 days absence to conditions matching a prior 2025 win.
        COALESCE(
            layoff_flag
            AND (prior_win_at_course_flag
                 OR prior_win_at_surface_flag
                 OR prior_win_at_dist_flag),
            FALSE
        )   AS reactivation_candidate,

        -- compression_plus_restore:
        --   Handicapper dropped the mark AND horse returned to a winning trip/full setup.
        COALESCE(
            mark_compression_flag
            AND (trip_restore_flag OR full_setup_restore_flag),
            FALSE
        )   AS compression_plus_restore,

        -- post_drop_restore:
        --   First start after mark drop, in a known winning environment.
        --   Strongest raw compound — handicapper has released; conditions are right.
        COALESCE(
            first_run_after_drop_flag
            AND (trip_restore_flag OR course_restore_flag OR full_setup_restore_flag),
            FALSE
        )   AS post_drop_restore,

        -- course_specialist_return:
        --   Won at this exact course in 2025, running there again. Clean entity only.
        COALESCE(
            prior_win_at_course_flag
            AND identity_confidence != 'ambiguous',
            FALSE
        )   AS course_specialist_return,

        -- full_restore_live:
        --   All three restore dimensions + high identity confidence.
        COALESCE(
            full_setup_restore_flag
            AND identity_confidence = 'high',
            FALSE
        )   AS full_restore_live
    FROM joined
),

-- CTE 3: Composite flags and reason codes
flagged AS (
    SELECT
        *,

        -- plot_pressure_flag: any meaningful plot condition present
        COALESCE(
            mark_compression_flag
            OR first_run_after_drop_flag
            OR or_treadmill_flag
            OR trip_restore_flag
            OR full_setup_restore_flag
            OR reactivation_candidate,
            FALSE
        )   AS plot_pressure_flag,

        -- manual_review_priority:
        --   2+ independent themes firing. Themes are grouped to avoid double-counting.
        --   handicap_theme : mark pressure (compression / post-drop / treadmill)
        --   restore_theme  : returned to a winning setup (trip / course / full)
        --   reactivation_t : layoff + prior win conditions
        --   mark_restore_t : post-drop AND near last winning OR
        CASE WHEN (
            (CASE WHEN mark_compression_flag
                    OR first_run_after_drop_flag
                    OR or_treadmill_flag          THEN 1 ELSE 0 END)
          + (CASE WHEN trip_restore_flag
                    OR course_restore_flag
                    OR full_setup_restore_flag    THEN 1 ELSE 0 END)
          + (CASE WHEN reactivation_candidate     THEN 1 ELSE 0 END)
          + (CASE WHEN mark_restore_candidate     THEN 1 ELSE 0 END)
        ) >= 2 THEN TRUE ELSE FALSE END
            AS manual_review_priority,

        -- plot_reason_codes: text array of all active conditions
        -- Ordered roughly by signal strength (strongest first).
        -- ARRAY_REMOVE strips NULLs from CASE WHEN non-matches.
        ARRAY_REMOVE(ARRAY[
            CASE WHEN post_drop_restore           THEN 'post_drop_restore'   END,
            CASE WHEN compression_plus_restore    THEN 'compress_restore'    END,
            CASE WHEN full_restore_live           THEN 'full_restore_live'   END,
            CASE WHEN mark_restore_candidate      THEN 'mark_restore'        END,
            CASE WHEN reactivation_candidate      THEN 'reactivation'        END,
            CASE WHEN full_setup_restore_flag
                  AND NOT full_restore_live       THEN 'full_setup_restore'  END,
            CASE WHEN trip_restore_flag
                  AND NOT full_setup_restore_flag THEN 'trip_restore'        END,
            CASE WHEN course_restore_flag
                  AND NOT full_setup_restore_flag THEN 'course_restore'      END,
            CASE WHEN course_specialist_return
                  AND NOT course_restore_flag     THEN 'course_specialist'   END,
            CASE WHEN mark_compression_flag       THEN 'mark_compressed'     END,
            CASE WHEN first_run_after_drop_flag
                  AND NOT mark_restore_candidate
                  AND NOT post_drop_restore       THEN 'post_drop'           END,
            CASE WHEN or_treadmill_flag           THEN 'or_treadmill'        END,
            CASE WHEN or_plateau_flag             THEN 'or_plateau'          END
        ], NULL)    AS plot_reason_codes
    FROM derived
)

SELECT
    entity_id, run_id, race_id, date, horse_name_raw, trainer,
    identity_confidence, ambiguity_flag,
    days_since_last_run, layoff_flag, long_layoff_flag,
    mark_compression_flag, mark_restored_flag, first_run_after_drop_flag,
    or_treadmill_flag, or_rating_num, or_change,
    current_vs_last_winning_or, current_vs_peak_or,
    trip_restore_flag, surface_restore_flag, course_restore_flag, full_setup_restore_flag,
    mark_restore_candidate, setup_restore_candidate, reactivation_candidate,
    compression_plus_restore, post_drop_restore, course_specialist_return, full_restore_live,
    plot_pressure_flag, manual_review_priority, plot_reason_codes
FROM flagged;
""", timeout=300)
print(f"  INSERT status: {status}")
if status != 201:
    print(f"  ERROR: {result}")


# ── Step 3: Indexes ───────────────────────────────────────────────────────────────
print("Step 3: Indexes")
for idx_sql in [
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (entity_id);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (date);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (horse_name_raw);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (trainer);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (plot_pressure_flag);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (manual_review_priority);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (full_restore_live);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (post_drop_restore);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 (identity_confidence);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2025 USING GIN (plot_reason_codes);",
]:
    sql(idx_sql, timeout=30)
print("  done")


# ── Step 4: Summary stats ─────────────────────────────────────────────────────────
print("\nStep 4: Summary")
_, rows = sql("""
    SELECT
        COUNT(*)                                                        AS total_rows,
        COUNT(*) FILTER (WHERE plot_pressure_flag)                     AS plot_pressure,
        COUNT(*) FILTER (WHERE manual_review_priority)                 AS manual_review,
        COUNT(*) FILTER (WHERE mark_restore_candidate)                 AS mark_restore,
        COUNT(*) FILTER (WHERE setup_restore_candidate)                AS setup_restore,
        COUNT(*) FILTER (WHERE reactivation_candidate)                 AS reactivation,
        COUNT(*) FILTER (WHERE compression_plus_restore)               AS compress_restore,
        COUNT(*) FILTER (WHERE post_drop_restore)                      AS post_drop_restore,
        COUNT(*) FILTER (WHERE course_specialist_return)               AS course_specialist,
        COUNT(*) FILTER (WHERE full_restore_live)                      AS full_restore_live,
        COUNT(*) FILTER (WHERE plot_reason_codes = '{}')               AS no_reason_codes,
        COUNT(*) FILTER (WHERE ARRAY_LENGTH(plot_reason_codes,1) >= 3) AS three_plus_reasons
    FROM intelligence.plot_candidate_flags_2025
""")
for row in rows:
    for k, v in row.items():
        print(f"  {k}: {v}")

print("\nTop plot_reason_codes combinations (manual_review candidates):")
_, rows = sql("""
    SELECT plot_reason_codes, COUNT(*) AS n
    FROM intelligence.plot_candidate_flags_2025
    WHERE manual_review_priority = TRUE
    GROUP BY plot_reason_codes
    ORDER BY n DESC
    LIMIT 12
""")
for row in rows:
    print(f"  {row['n']:>5}  {row['plot_reason_codes']}")

print("\nDone.")
