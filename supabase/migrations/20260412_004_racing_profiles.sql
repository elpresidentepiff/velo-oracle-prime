-- migration: 20260412_004_racing_profiles
-- Racing API profile tables: jockeys, trainers, horses, owners, courses,
-- today's racecards and runners.
-- All tables use Racing API IDs as primary key (text).
-- Upsert-safe: all columns have ON CONFLICT DO UPDATE via service role.

-- ── Courses ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_courses (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    region_code  TEXT,
    region       TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Jockeys ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_jockeys (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    runs         INTEGER DEFAULT 0,
    wins         INTEGER DEFAULT 0,
    places       INTEGER DEFAULT 0,
    win_pct      NUMERIC(5,1),
    place_pct    NUMERIC(5,1),
    regions      TEXT[],
    courses      TEXT[],
    last_seen    DATE,
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Trainers ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_trainers (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    runs         INTEGER DEFAULT 0,
    wins         INTEGER DEFAULT 0,
    places       INTEGER DEFAULT 0,
    win_pct      NUMERIC(5,1),
    place_pct    NUMERIC(5,1),
    regions      TEXT[],
    courses      TEXT[],
    last_seen    DATE,
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Horses ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_horses (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    age          TEXT,
    sex          TEXT,
    sire         TEXT,
    sire_id      TEXT,
    dam          TEXT,
    dam_id       TEXT,
    trainer_id   TEXT REFERENCES racing_trainers(id) ON DELETE SET NULL,
    trainer      TEXT,
    runs         INTEGER DEFAULT 0,
    wins         INTEGER DEFAULT 0,
    places       INTEGER DEFAULT 0,
    win_pct      NUMERIC(5,1),
    last_seen    DATE,
    last_or      INTEGER,
    last_rpr     INTEGER,
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Owners ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_owners (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    runs         INTEGER DEFAULT 0,
    wins         INTEGER DEFAULT 0,
    win_pct      NUMERIC(5,1),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Today's racecards ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_today_cards (
    race_id         TEXT PRIMARY KEY,
    date            DATE,
    course          TEXT,
    course_id       TEXT,
    off_time        TEXT,
    off_dt          TIMESTAMPTZ,
    race_name       TEXT,
    distance        TEXT,
    race_class      TEXT,
    type            TEXT,
    going           TEXT,
    region          TEXT,
    pattern         TEXT,
    age_band        TEXT,
    sex_restriction TEXT,
    field_size      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Today's runners ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS racing_today_runners (
    id              BIGSERIAL PRIMARY KEY,
    race_id         TEXT REFERENCES racing_today_cards(race_id) ON DELETE CASCADE,
    horse_id        TEXT,
    horse           TEXT,
    number          TEXT,
    draw            TEXT,
    age             TEXT,
    sex             TEXT,
    weight          TEXT,
    headgear        TEXT,
    jockey_id       TEXT,
    jockey          TEXT,
    jockey_claim    INTEGER,
    trainer_id      TEXT,
    trainer         TEXT,
    owner_id        TEXT,
    owner           TEXT,
    sire            TEXT,
    dam             TEXT,
    form            TEXT,
    official_rating TEXT,
    rpr             TEXT,
    ts              TEXT,
    lbs_carried     TEXT,
    silk_url        TEXT,
    UNIQUE (race_id, horse_id)
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_racing_jockeys_name    ON racing_jockeys (name);
CREATE INDEX IF NOT EXISTS idx_racing_trainers_name   ON racing_trainers (name);
CREATE INDEX IF NOT EXISTS idx_racing_horses_name     ON racing_horses (name);
CREATE INDEX IF NOT EXISTS idx_racing_horses_trainer  ON racing_horses (trainer_id);
CREATE INDEX IF NOT EXISTS idx_racing_today_runners_race ON racing_today_runners (race_id);
CREATE INDEX IF NOT EXISTS idx_racing_today_runners_jockey ON racing_today_runners (jockey_id);
CREATE INDEX IF NOT EXISTS idx_racing_today_runners_trainer ON racing_today_runners (trainer_id);
