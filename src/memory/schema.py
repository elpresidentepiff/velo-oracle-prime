"""
VÉLØ PRIME — Persistent Intelligence Database Schema
=====================================================
SQLite schema for velo_memory.db — the backbone of VÉLØ's
cross-session learning and pattern recognition system.

Tables:
  races, runners, predictions, results, sigma_evaluations,
  trainer_patterns, jockey_patterns, course_bias,
  rpd_validation, market_behaviour
"""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = "1.0.0"

SCHEMA_SQL = """
-- ─────────────────────────────────────────────
-- VÉLØ PRIME Persistent Memory Schema v1.0
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ── Core Race Data ──────────────────────────

CREATE TABLE IF NOT EXISTS races (
    race_id        TEXT PRIMARY KEY,
    date           TEXT NOT NULL,
    course         TEXT NOT NULL,
    time           TEXT,
    race_type      TEXT,
    class          TEXT,
    distance       TEXT,
    going          TEXT,
    field_size     INTEGER,
    prize          TEXT,
    rail_position  TEXT,
    weather        TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_races_date ON races(date);
CREATE INDEX IF NOT EXISTS idx_races_course ON races(course);
CREATE INDEX IF NOT EXISTS idx_races_course_date ON races(course, date);

CREATE TABLE IF NOT EXISTS runners (
    runner_id       TEXT PRIMARY KEY,
    race_id         TEXT NOT NULL,
    horse_name      TEXT NOT NULL,
    trainer         TEXT,
    jockey          TEXT,
    age             INTEGER,
    weight          TEXT,
    "OR"            INTEGER,
    RPR             INTEGER,
    TS              INTEGER,
    form_figures    TEXT,
    draw            INTEGER,
    headgear        TEXT,
    days_since_run  INTEGER,
    spotlight_notes TEXT,
    rpd_tag         TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_runners_race ON runners(race_id);
CREATE INDEX IF NOT EXISTS idx_runners_horse ON runners(horse_name);
CREATE INDEX IF NOT EXISTS idx_runners_trainer ON runners(trainer);
CREATE INDEX IF NOT EXISTS idx_runners_jockey ON runners(jockey);

-- ── Predictions ─────────────────────────────

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id      TEXT PRIMARY KEY,
    race_id            TEXT NOT NULL,
    date               TEXT NOT NULL,
    top_strike         TEXT,
    value_pick         TEXT,
    danger_horse       TEXT,
    confidence_band    TEXT,
    scenario_primary   TEXT,
    scenario_secondary TEXT,
    threat_flags       TEXT,  -- JSON array
    full_analysis_text TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_race ON predictions(race_id);
CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(date);

-- ── Results ─────────────────────────────────

CREATE TABLE IF NOT EXISTS results (
    result_id     TEXT PRIMARY KEY,
    race_id       TEXT NOT NULL,
    date          TEXT NOT NULL,
    positions     TEXT,  -- JSON: [{horse_name, position, bsp, isp, place_bsp}]
    winning_time  TEXT,
    non_runners   TEXT,  -- JSON array
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_results_race ON results(race_id);
CREATE INDEX IF NOT EXISTS idx_results_date ON results(date);

-- ── Sigma Evaluations ───────────────────────

CREATE TABLE IF NOT EXISTS sigma_evaluations (
    eval_id            TEXT PRIMARY KEY,
    race_id            TEXT NOT NULL,
    date               TEXT NOT NULL,
    top_strike_result  TEXT,  -- hit / place / miss
    value_result       TEXT,  -- hit / place / miss
    danger_result      TEXT,  -- hit / place / miss
    signal_quality     REAL,  -- 0.0 – 1.0
    narrative_traps    TEXT,
    bias_adjustments   TEXT,  -- JSON
    weight_changes     TEXT,  -- JSON
    lessons_learned    TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_sigma_race ON sigma_evaluations(race_id);
CREATE INDEX IF NOT EXISTS idx_sigma_date ON sigma_evaluations(date);

-- ── Pattern Tables ──────────────────────────

CREATE TABLE IF NOT EXISTS trainer_patterns (
    trainer        TEXT NOT NULL,
    course         TEXT NOT NULL DEFAULT '_ALL_',
    going          TEXT NOT NULL DEFAULT '_ALL_',
    race_type      TEXT NOT NULL DEFAULT '_ALL_',
    runs           INTEGER DEFAULT 0,
    wins           INTEGER DEFAULT 0,
    places         INTEGER DEFAULT 0,
    strike_rate    REAL DEFAULT 0.0,
    avg_or         REAL DEFAULT 0.0,
    intent_signals TEXT,  -- JSON
    last_updated   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (trainer, course, going, race_type)
);

CREATE INDEX IF NOT EXISTS idx_tp_trainer ON trainer_patterns(trainer);
CREATE INDEX IF NOT EXISTS idx_tp_course ON trainer_patterns(course);

CREATE TABLE IF NOT EXISTS jockey_patterns (
    jockey           TEXT NOT NULL,
    course           TEXT NOT NULL DEFAULT '_ALL_',
    going            TEXT NOT NULL DEFAULT '_ALL_',
    race_type        TEXT NOT NULL DEFAULT '_ALL_',
    runs             INTEGER DEFAULT 0,
    wins             INTEGER DEFAULT 0,
    places           INTEGER DEFAULT 0,
    strike_rate      REAL DEFAULT 0.0,
    booking_upgrades INTEGER DEFAULT 0,
    last_updated     TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (jockey, course, going, race_type)
);

CREATE INDEX IF NOT EXISTS idx_jp_jockey ON jockey_patterns(jockey);
CREATE INDEX IF NOT EXISTS idx_jp_course ON jockey_patterns(course);

CREATE TABLE IF NOT EXISTS course_bias (
    course         TEXT NOT NULL,
    going          TEXT NOT NULL DEFAULT '_ALL_',
    distance       TEXT NOT NULL DEFAULT '_ALL_',
    rail_position  TEXT,
    pace_bias      TEXT,
    draw_bias      TEXT,
    sample_size    INTEGER DEFAULT 0,
    last_updated   TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (course, going, distance)
);

CREATE INDEX IF NOT EXISTS idx_cb_course ON course_bias(course);

-- ── RPD-C Validation ────────────────────────

CREATE TABLE IF NOT EXISTS rpd_validation (
    rpd_id           TEXT PRIMARY KEY,
    runner_id        TEXT NOT NULL,
    race_id          TEXT NOT NULL,
    rpd_tag          TEXT,
    predicted_intent TEXT,
    actual_position  INTEGER,
    actual_bsp       REAL,
    tag_validated    BOOLEAN,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (runner_id) REFERENCES runners(runner_id),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_rpd_runner ON rpd_validation(runner_id);
CREATE INDEX IF NOT EXISTS idx_rpd_race ON rpd_validation(race_id);
CREATE INDEX IF NOT EXISTS idx_rpd_tag ON rpd_validation(rpd_tag);

-- ── Market Behaviour ────────────────────────

CREATE TABLE IF NOT EXISTS market_behaviour (
    market_id     TEXT PRIMARY KEY,
    runner_id     TEXT NOT NULL,
    race_id       TEXT NOT NULL,
    morning_price REAL,
    sp            REAL,
    bsp           REAL,
    drift_pct     REAL,
    drift_type    TEXT,  -- noise / informative
    steam_flag    BOOLEAN DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (runner_id) REFERENCES runners(runner_id),
    FOREIGN KEY (race_id) REFERENCES races(race_id)
);

CREATE INDEX IF NOT EXISTS idx_mb_runner ON market_behaviour(runner_id);
CREATE INDEX IF NOT EXISTS idx_mb_race ON market_behaviour(race_id);
"""


def init_database(db_path: str = "data/velo_memory.db") -> sqlite3.Connection:
    """
    Initialize the VÉLØ memory database.
    Creates all tables if they don't exist.
    Returns a connection object.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    conn.executescript(SCHEMA_SQL)

    # Store schema version
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
        ("schema_version", SCHEMA_VERSION),
    )
    conn.commit()
    return conn


def get_schema_version(conn: sqlite3.Connection) -> str:
    """Return the current schema version."""
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    return row["value"] if row else "unknown"


if __name__ == "__main__":
    conn = init_database()
    print(f"VÉLØ Memory DB initialized — schema v{get_schema_version(conn)}")
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    for t in tables:
        print(f"  ✓ {t['name']}")
    conn.close()
