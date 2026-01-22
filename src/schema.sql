-- VÉLØ PRIME Schema
-- Canonical database: /home/ubuntu/velo-oracle-prime/velo.db

CREATE TABLE IF NOT EXISTS races (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL,
  race_date TEXT NOT NULL,
  race_time TEXT NOT NULL,
  race_name TEXT NOT NULL,
  distance TEXT,
  going TEXT,
  prize_money TEXT,
  track_type TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(venue, race_date, race_time)
);

CREATE TABLE IF NOT EXISTS runners (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  race_id INTEGER NOT NULL,
  number INTEGER NOT NULL,
  name TEXT NOT NULL,
  age INTEGER,
  weight TEXT,
  form TEXT,
  jockey TEXT,
  trainer TEXT,
  official_rating INTEGER,
  topspeed INTEGER,
  rpr INTEGER,
  sire TEXT,
  dam TEXT,
  owner TEXT,
  commentary TEXT,
  is_postdata_selection BOOLEAN DEFAULT 0,
  is_topspeed_selection BOOLEAN DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(race_id) REFERENCES races(id),
  UNIQUE(race_id, number)
);

CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY,
  venue TEXT NOT NULL,
  race_date TEXT NOT NULL,
  race_id INTEGER NOT NULL,
  verdict_layer_x TEXT,
  verdict_confidence REAL,
  verdict_rationale TEXT,
  verdict_generated_at TIMESTAMP,
  result_winner TEXT,
  result_winner_in_top4 BOOLEAN,
  result_scraped_at TIMESTAMP,
  status TEXT DEFAULT 'PENDING',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(race_id) REFERENCES races(id)
);

CREATE TABLE IF NOT EXISTS integrity_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode_id TEXT,
  event_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  message TEXT NOT NULL,
  details TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_races_venue_date ON races(venue, race_date);
CREATE INDEX IF NOT EXISTS idx_runners_race_id ON runners(race_id);
CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
CREATE INDEX IF NOT EXISTS idx_episodes_venue_date ON episodes(venue, race_date);
CREATE INDEX IF NOT EXISTS idx_integrity_episode ON integrity_events(episode_id);
