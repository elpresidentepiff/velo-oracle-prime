-- migration: 20260412_005_rpdc_tables
-- RPDC campaign intelligence layer.
-- Depends on: racing_horses, racing_trainers, racing_jockeys, racing_owners, racing_courses

-- ── Individual horse run history ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_horse_runs (
    id              BIGSERIAL PRIMARY KEY,
    horse_id        TEXT NOT NULL,
    horse           TEXT,
    race_id         TEXT NOT NULL,
    run_date        DATE NOT NULL,
    course          TEXT,
    course_id       TEXT,
    region          TEXT,
    race_name       TEXT,
    race_type       TEXT,
    distance        TEXT,
    distance_f      NUMERIC(6,2),
    going           TEXT,
    race_class      TEXT,
    pattern         TEXT,
    position        TEXT,           -- '1','2','3','F','U','P' etc
    position_int    INTEGER,        -- numeric only, NULL for non-finishers
    is_win          BOOLEAN GENERATED ALWAYS AS (position = '1') STORED,
    is_place        BOOLEAN GENERATED ALWAYS AS (position IN ('1','2','3')) STORED,
    official_rating INTEGER,
    rpr             INTEGER,
    tsr             INTEGER,
    sp              TEXT,
    sp_dec          NUMERIC(10,2),
    btn             NUMERIC(8,2),   -- beaten lengths
    weight          TEXT,
    weight_lbs      INTEGER,
    headgear        TEXT,
    jockey_id       TEXT,
    jockey          TEXT,
    trainer_id      TEXT,
    trainer         TEXT,
    owner_id        TEXT,
    owner           TEXT,
    prize           NUMERIC(12,2),
    UNIQUE (horse_id, race_id)
);

CREATE INDEX IF NOT EXISTS idx_hruns_horse_date  ON racing_horse_runs (horse_id, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_hruns_trainer      ON racing_horse_runs (trainer_id, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_hruns_jockey       ON racing_horse_runs (jockey_id, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_hruns_course       ON racing_horse_runs (course, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_hruns_date         ON racing_horse_runs (run_date DESC);

-- ── A. horse_mark_profile ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS horse_mark_profile (
    horse_id                    TEXT PRIMARY KEY,
    horse                       TEXT,
    trainer_id                  TEXT,
    trainer                     TEXT,
    current_or                  INTEGER,
    last_winning_or             INTEGER,
    best_place_or               INTEGER,
    or_delta_to_win             INTEGER,    -- current_or - last_winning_or (negative = below)
    or_delta_to_place           INTEGER,
    runs_since_win              INTEGER,
    runs_since_place            INTEGER,
    campaign_run_no             INTEGER,    -- runs in current campaign (since last 30d+ break)
    days_since_run              INTEGER,
    last_run_date               DATE,
    last_win_date               DATE,
    last_place_date             DATE,
    best_course                 TEXT,
    best_distance_band          TEXT,
    preferred_going_code        TEXT,
    mark_ready_flag             BOOLEAN DEFAULT FALSE,  -- current_or <= last_winning_or
    mark_near_flag              BOOLEAN DEFAULT FALSE,  -- within 3lb
    below_last_win_mark_flag    BOOLEAN DEFAULT FALSE,  -- strictly below
    place_mark_ready_flag       BOOLEAN DEFAULT FALSE,
    handicap_relief_active_flag BOOLEAN DEFAULT FALSE,  -- OR dropped materially over last 3 runs
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ── B. trainer_campaign_profile ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trainer_campaign_profile (
    trainer_id                  TEXT PRIMARY KEY,
    trainer                     TEXT,
    runs_180d                   INTEGER DEFAULT 0,
    wins_180d                   INTEGER DEFAULT 0,
    places_180d                 INTEGER DEFAULT 0,
    win_rate_180d               NUMERIC(5,1),
    place_rate_180d             NUMERIC(5,1),
    win_rate_run1               NUMERIC(5,1),   -- first run after 30d+ break
    win_rate_run2               NUMERIC(5,1),
    win_rate_run3               NUMERIC(5,1),
    win_rate_mark_ready         NUMERIC(5,1),   -- when horse at/below winning mark
    win_rate_class_drop         NUMERIC(5,1),   -- when class drops
    win_rate_days_8_21          NUMERIC(5,1),   -- quick returns
    win_rate_days_22_45         NUMERIC(5,1),   -- standard spacing
    win_rate_days_46_plus       NUMERIC(5,1),   -- fresh returns
    preferred_release_run_no    INTEGER,        -- run number with highest strike rate
    release_style               TEXT,           -- 'immediate','second_up','third_up','variable'
    stable_heat_14d             NUMERIC(5,1),   -- win% in last 14 days
    stable_heat_30d             NUMERIC(5,1),   -- win% in last 30 days
    stable_warming              BOOLEAN DEFAULT FALSE,  -- heat_14d > heat_30d
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ── C. trainer_owner_patterns ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trainer_owner_patterns (
    id                          BIGSERIAL PRIMARY KEY,
    trainer_id                  TEXT,
    trainer                     TEXT,
    owner_id                    TEXT,
    owner                       TEXT,
    runs_180d                   INTEGER DEFAULT 0,
    wins_180d                   INTEGER DEFAULT 0,
    places_180d                 INTEGER DEFAULT 0,
    win_rate_180d               NUMERIC(5,1),
    avg_runs_before_win         NUMERIC(5,1),
    avg_or_drop_before_win      NUMERIC(5,1),
    favoured_courses            TEXT[],
    favoured_distance_band      TEXT,
    favoured_rest_bucket        TEXT,
    pair_release_bias           TEXT,           -- 'immediate','prep_needed','variable'
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (trainer_id, owner_id)
);

-- ── D. runner_release_candidates ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runner_release_candidates (
    id                          BIGSERIAL PRIMARY KEY,
    run_date                    DATE NOT NULL,
    race_id                     TEXT NOT NULL,
    horse_id                    TEXT NOT NULL,
    horse                       TEXT,
    trainer_id                  TEXT,
    trainer                     TEXT,
    owner_id                    TEXT,
    owner                       TEXT,
    jockey_id                   TEXT,
    jockey                      TEXT,
    current_or                  INTEGER,
    or_delta_to_win             INTEGER,
    runs_since_win              INTEGER,
    runs_since_place            INTEGER,
    campaign_run_no             INTEGER,
    days_since_run              INTEGER,
    class_delta                 INTEGER,        -- today class vs last run class (negative = drop)
    distance_revert_flag        BOOLEAN DEFAULT FALSE,
    course_return_flag          BOOLEAN DEFAULT FALSE,
    jockey_upgrade_flag         BOOLEAN DEFAULT FALSE,
    stable_heat                 NUMERIC(5,1),
    market_position             INTEGER,        -- draw/number as proxy (SP not avail pre-race)
    rpdc_tag_count              INTEGER DEFAULT 0,
    rpdc_release_score          NUMERIC(6,2) DEFAULT 0,
    rpdc_suppression_score      NUMERIC(6,2) DEFAULT 0,
    rpdc_cash_window_flag       BOOLEAN DEFAULT FALSE,
    rpdc_trap_flag              BOOLEAN DEFAULT FALSE,
    rpdc_tags                   JSONB DEFAULT '[]',
    generated_at                TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (run_date, race_id, horse_id)
);

CREATE INDEX IF NOT EXISTS idx_rrc_date           ON runner_release_candidates (run_date DESC);
CREATE INDEX IF NOT EXISTS idx_rrc_cash_window    ON runner_release_candidates (run_date, rpdc_cash_window_flag);
CREATE INDEX IF NOT EXISTS idx_rrc_release_score  ON runner_release_candidates (run_date, rpdc_release_score DESC);

-- ── E. today_rpdc_tags ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS today_rpdc_tags (
    id              BIGSERIAL PRIMARY KEY,
    run_date        DATE NOT NULL,
    race_id         TEXT NOT NULL,
    horse_id        TEXT NOT NULL,
    horse           TEXT,
    tag             TEXT NOT NULL,
    tag_value       TEXT,
    tag_strength    NUMERIC(4,2) DEFAULT 1.0,   -- 0.0 to 1.0
    evidence        TEXT,
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rpdc_tags_date     ON today_rpdc_tags (run_date DESC);
CREATE INDEX IF NOT EXISTS idx_rpdc_tags_tag      ON today_rpdc_tags (tag, run_date DESC);
CREATE INDEX IF NOT EXISTS idx_rpdc_tags_horse    ON today_rpdc_tags (horse_id, run_date DESC);
