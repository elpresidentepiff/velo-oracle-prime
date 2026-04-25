"""
Build intelligence.plot_candidate_flags_2024.
Rules-based candidate queue. Identical logic to 2025 version.
Run: python scripts/build_plot_candidate_flags_2024.py
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
DROP TABLE IF EXISTS intelligence.plot_candidate_flags_2024;
CREATE TABLE intelligence.plot_candidate_flags_2024 (
    candidate_id                BIGSERIAL   PRIMARY KEY,
    entity_id                   UUID        NOT NULL,
    run_id                      BIGINT      NOT NULL,
    race_id                     TEXT,
    date                        DATE        NOT NULL,
    horse_name_raw              TEXT        NOT NULL,
    trainer                     TEXT,
    identity_confidence         TEXT,
    ambiguity_flag              BOOLEAN,
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
    mark_restore_candidate      BOOLEAN     NOT NULL DEFAULT FALSE,
    setup_restore_candidate     BOOLEAN     NOT NULL DEFAULT FALSE,
    reactivation_candidate      BOOLEAN     NOT NULL DEFAULT FALSE,
    compression_plus_restore    BOOLEAN     NOT NULL DEFAULT FALSE,
    post_drop_restore           BOOLEAN     NOT NULL DEFAULT FALSE,
    course_specialist_return    BOOLEAN     NOT NULL DEFAULT FALSE,
    full_restore_live           BOOLEAN     NOT NULL DEFAULT FALSE,
    plot_pressure_flag          BOOLEAN     NOT NULL DEFAULT FALSE,
    manual_review_priority      BOOLEAN     NOT NULL DEFAULT FALSE,
    plot_reason_codes           TEXT[]
);""")
print(f"  {status}")

print("Step 2: Populate")
status, result = sql("""
INSERT INTO intelligence.plot_candidate_flags_2024 (
    entity_id, run_id, race_id, date, horse_name_raw, trainer,
    identity_confidence, ambiguity_flag,
    days_since_last_run, layoff_flag, long_layoff_flag,
    mark_compression_flag, mark_restored_flag, first_run_after_drop_flag,
    or_treadmill_flag, or_rating_num, or_change,
    current_vs_last_winning_or, current_vs_peak_or,
    trip_restore_flag, surface_restore_flag, course_restore_flag, full_setup_restore_flag,
    mark_restore_candidate, setup_restore_candidate, reactivation_candidate,
    compression_plus_restore, post_drop_restore, course_specialist_return, full_restore_live,
    plot_pressure_flag, manual_review_priority, plot_reason_codes)
WITH joined AS (
    SELECT h.entity_id, h.run_id, h.race_id, h.date, h.horse AS horse_name_raw, h.trainer,
        h.identity_confidence, h.ambiguity_flag, h.days_since_last_run, h.layoff_flag, h.long_layoff_flag,
        t.mark_compression_flag, t.mark_restored_flag, t.first_run_after_drop_flag,
        t.or_treadmill_flag, t.or_plateau_flag, t.or_rating_num, t.or_change,
        t.last_winning_or_to_date, t.current_vs_last_winning_or, t.current_vs_peak_or,
        s.prior_win_at_course_flag, s.prior_win_at_surface_flag, s.prior_win_at_dist_flag,
        s.trip_restore_flag, s.surface_restore_flag, s.course_restore_flag, s.full_setup_restore_flag
    FROM intelligence.horse_run_history_2024 h
    LEFT JOIN intelligence.handicap_trajectory_2024 t ON t.run_id = h.run_id
    LEFT JOIN intelligence.setup_restore_events_2024 s ON s.run_id = h.run_id
),
derived AS (
    SELECT *,
        COALESCE(first_run_after_drop_flag AND last_winning_or_to_date IS NOT NULL AND current_vs_last_winning_or BETWEEN -8 AND 5, FALSE) AS mark_restore_candidate,
        COALESCE(trip_restore_flag OR course_restore_flag OR full_setup_restore_flag, FALSE) AS setup_restore_candidate,
        COALESCE(layoff_flag AND (prior_win_at_course_flag OR prior_win_at_surface_flag OR prior_win_at_dist_flag), FALSE) AS reactivation_candidate,
        COALESCE(mark_compression_flag AND (trip_restore_flag OR full_setup_restore_flag), FALSE) AS compression_plus_restore,
        COALESCE(first_run_after_drop_flag AND (trip_restore_flag OR course_restore_flag OR full_setup_restore_flag), FALSE) AS post_drop_restore,
        COALESCE(prior_win_at_course_flag AND identity_confidence != 'ambiguous', FALSE) AS course_specialist_return,
        COALESCE(full_setup_restore_flag AND identity_confidence = 'high', FALSE) AS full_restore_live
    FROM joined
),
flagged AS (
    SELECT *,
        COALESCE(mark_compression_flag OR first_run_after_drop_flag OR or_treadmill_flag OR trip_restore_flag OR full_setup_restore_flag OR reactivation_candidate, FALSE) AS plot_pressure_flag,
        CASE WHEN (
            (CASE WHEN mark_compression_flag OR first_run_after_drop_flag OR or_treadmill_flag THEN 1 ELSE 0 END)
          + (CASE WHEN trip_restore_flag OR course_restore_flag OR full_setup_restore_flag THEN 1 ELSE 0 END)
          + (CASE WHEN reactivation_candidate THEN 1 ELSE 0 END)
          + (CASE WHEN mark_restore_candidate THEN 1 ELSE 0 END)
        ) >= 2 THEN TRUE ELSE FALSE END AS manual_review_priority,
        ARRAY_REMOVE(ARRAY[
            CASE WHEN post_drop_restore         THEN 'post_drop_restore'  END,
            CASE WHEN compression_plus_restore  THEN 'compress_restore'   END,
            CASE WHEN full_restore_live         THEN 'full_restore_live'  END,
            CASE WHEN mark_restore_candidate    THEN 'mark_restore'       END,
            CASE WHEN reactivation_candidate    THEN 'reactivation'       END,
            CASE WHEN full_setup_restore_flag AND NOT full_restore_live   THEN 'full_setup_restore' END,
            CASE WHEN trip_restore_flag AND NOT full_setup_restore_flag   THEN 'trip_restore'       END,
            CASE WHEN course_restore_flag AND NOT full_setup_restore_flag THEN 'course_restore'     END,
            CASE WHEN course_specialist_return AND NOT course_restore_flag THEN 'course_specialist' END,
            CASE WHEN mark_compression_flag     THEN 'mark_compressed'    END,
            CASE WHEN first_run_after_drop_flag AND NOT mark_restore_candidate AND NOT post_drop_restore THEN 'post_drop' END,
            CASE WHEN or_treadmill_flag         THEN 'or_treadmill'       END,
            CASE WHEN or_plateau_flag           THEN 'or_plateau'         END
        ], NULL) AS plot_reason_codes
    FROM derived
)
SELECT entity_id, run_id, race_id, date, horse_name_raw, trainer,
    identity_confidence, ambiguity_flag,
    days_since_last_run, layoff_flag, long_layoff_flag,
    mark_compression_flag, mark_restored_flag, first_run_after_drop_flag,
    or_treadmill_flag, or_rating_num, or_change, current_vs_last_winning_or, current_vs_peak_or,
    trip_restore_flag, surface_restore_flag, course_restore_flag, full_setup_restore_flag,
    mark_restore_candidate, setup_restore_candidate, reactivation_candidate,
    compression_plus_restore, post_drop_restore, course_specialist_return, full_restore_live,
    plot_pressure_flag, manual_review_priority, plot_reason_codes
FROM flagged;
""", timeout=480)
print(f"  INSERT status: {status}")
if status != 201: print(f"  ERROR: {result}")

print("Step 3: Indexes")
for idx in [
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 (entity_id);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 (date);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 (plot_pressure_flag);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 (manual_review_priority);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 (full_restore_live);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 (post_drop_restore);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 (identity_confidence);",
    "CREATE INDEX ON intelligence.plot_candidate_flags_2024 USING GIN (plot_reason_codes);",]:
    sql(idx, 30)
print("  done")

print("\nStep 4: Summary")
_, rows = sql("""
    SELECT COUNT(*) AS total_rows,
        COUNT(*) FILTER (WHERE plot_pressure_flag) AS plot_pressure,
        COUNT(*) FILTER (WHERE manual_review_priority) AS manual_review,
        COUNT(*) FILTER (WHERE mark_restore_candidate) AS mark_restore,
        COUNT(*) FILTER (WHERE post_drop_restore) AS post_drop_restore,
        COUNT(*) FILTER (WHERE full_restore_live) AS full_restore_live,
        COUNT(*) FILTER (WHERE reactivation_candidate) AS reactivation,
        COUNT(*) FILTER (WHERE identity_confidence='high' AND manual_review_priority AND ARRAY_LENGTH(plot_reason_codes,1)>=3) AS tier2_clean,
        COUNT(*) FILTER (WHERE identity_confidence='high' AND manual_review_priority AND ARRAY_LENGTH(plot_reason_codes,1)>=4) AS tier3_clean
    FROM intelligence.plot_candidate_flags_2024""")
for row in rows:
    for k,v in row.items(): print(f"  {k}: {v}")
print("\nDone.")
