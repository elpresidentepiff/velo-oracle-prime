"""
refresh_racing_api_stat_cache.py

Manages the local Racing API stat cache (SQLite).
Makes Racing API trainer/jockey stats accessible any time without live API calls.

Usage:
    PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --full-refresh
    PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --incremental
    PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --runner-card 2026-05-08
    PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --stats
    PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --check-entity trn_12345

NO live VP effect — this is read-only enrichment.
Racing API stats remain TIER 1/TIER 2 (operator visibility + calibration only).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

_URL = os.getenv("SUPABASE_URL", "")
_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
_HEADERS = {"apikey": _KEY, "Authorization": f"Bearer {_KEY}"}
_DB_PATH = Path("data/racing_api_cache.db")

# Supabase table → local SQLite table mapping
_TABLE_MAP = {
    "racing_api_trainer_analysis_courses": "trainer_courses",
    "racing_api_trainer_analysis_distances": "trainer_distances",
    "racing_api_trainer_analysis_jockeys": "trainer_jockeys",
    "racing_api_jockey_analysis_courses": "jockey_courses",
    "racing_api_jockey_analysis_distances": "jockey_distances",
    "racing_api_jockey_analysis_trainers": "jockey_trainers",
}

# Column mappings: (source_field, local_field, type)
_TRAINER_COURSES_COLS = [
    ("entity_id", "entity_id", "TEXT"),
    ("entity_name", "entity_name", "TEXT"),
    ("course_id", "partner_id_or_name", "TEXT"),
    ("course", "course_name", "TEXT"),
    ("win_pct", "win_pct", "REAL"),
    ("pnl", "pnl", "REAL"),
    ("ae_ratio", "ae_ratio", "REAL"),
    ("runners_or_rides", "runs", "INTEGER"),
]
_TRAINER_DISTANCES_COLS = [
    ("entity_id", "entity_id", "TEXT"),
    ("entity_name", "entity_name", "TEXT"),
    ("dist_f", "partner_id_or_name", "TEXT"),
    ("win_pct", "win_pct", "REAL"),
    ("pnl", "pnl", "REAL"),
    ("ae_ratio", "ae_ratio", "REAL"),
    ("runners_or_rides", "runs", "INTEGER"),
]
_TRAINER_JOCKEYS_COLS = [
    ("entity_id", "entity_id", "TEXT"),
    ("entity_name", "entity_name", "TEXT"),
    ("jockey_id", "partner_id_or_name", "TEXT"),
    ("jockey_name", "partner_display_name", "TEXT"),
    ("win_pct", "win_pct", "REAL"),
    ("pnl", "pnl", "REAL"),
    ("ae_ratio", "ae_ratio", "REAL"),
    ("runners_or_rides", "runs", "INTEGER"),
]
_JOCKEY_COURSES_COLS = [
    ("entity_id", "entity_id", "TEXT"),
    ("entity_name", "entity_name", "TEXT"),
    ("course_id", "partner_id_or_name", "TEXT"),
    ("course", "course_name", "TEXT"),
    ("win_pct", "win_pct", "REAL"),
    ("pnl", "pnl", "REAL"),
    ("ae_ratio", "ae_ratio", "REAL"),
    ("runners_or_rides", "runs", "INTEGER"),
]
_JOCKEY_DISTANCES_COLS = [
    ("entity_id", "entity_id", "TEXT"),
    ("entity_name", "entity_name", "TEXT"),
    ("dist_f", "partner_id_or_name", "TEXT"),
    ("win_pct", "win_pct", "REAL"),
    ("pnl", "pnl", "REAL"),
    ("ae_ratio", "ae_ratio", "REAL"),
    ("runners_or_rides", "runs", "INTEGER"),
]
_JOCKEY_TRAINERS_COLS = [
    ("entity_id", "entity_id", "TEXT"),
    ("entity_name", "entity_name", "TEXT"),
    ("trainer_id", "partner_id_or_name", "TEXT"),
    ("trainer_name", "partner_display_name", "TEXT"),
    ("win_pct", "win_pct", "REAL"),
    ("pnl", "pnl", "REAL"),
    ("ae_ratio", "ae_ratio", "REAL"),
    ("runners_or_rides", "runs", "INTEGER"),
]

_SCHEMA = {
    "trainer_courses": _TRAINER_COURSES_COLS,
    "trainer_distances": _TRAINER_DISTANCES_COLS,
    "trainer_jockeys": _TRAINER_JOCKEYS_COLS,
    "jockey_courses": _JOCKEY_COURSES_COLS,
    "jockey_distances": _JOCKEY_DISTANCES_COLS,
    "jockey_trainers": _JOCKEY_TRAINERS_COLS,
}

_SUPABASE_SOURCE = {v: k for k, v in _TABLE_MAP.items()}


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    for table, cols in _SCHEMA.items():
        col_defs = ", ".join(f"{local} {t}" for _, local, t in cols)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {col_defs},
                last_updated TEXT
            )
        """)
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_entity ON {table}(entity_id)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_partner ON {table}(partner_id_or_name)")
    conn.commit()


def _fetch_all_supabase(supabase_table: str, verbose: bool = True) -> list:
    rows, offset = [], 0
    if verbose:
        print(f"  Fetching {supabase_table}...", end="", flush=True)
    while True:
        req = urllib.request.Request(
            f"{_URL}/rest/v1/{supabase_table}?offset={offset}&limit=1000",
            headers={**_HEADERS, "Range": f"{offset}-{offset+999}"},
        )
        with urllib.request.urlopen(req) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    if verbose:
        print(f" {len(rows)}")
    return rows


def _load_table(conn: sqlite3.Connection, local_table: str,
                supabase_rows: list, drop_first: bool = True) -> int:
    cols_map = _SCHEMA[local_table]
    local_cols = [local for _, local, _ in cols_map]
    src_cols = [src for src, _, _ in cols_map]

    if drop_first:
        conn.execute(f"DELETE FROM {local_table}")

    now = datetime.now().isoformat()
    inserted = 0
    for r in supabase_rows:
        vals = []
        for src, local, _ in cols_map:
            v = r.get(src)
            # handle missing partner_display_name gracefully
            vals.append(v)
        vals.append(now)
        placeholders = ",".join("?" * (len(cols_map) + 1))
        conn.execute(
            f"INSERT INTO {local_table} ({','.join(local_cols)}, last_updated) VALUES ({placeholders})",
            vals
        )
        inserted += 1
    conn.commit()
    return inserted


def cmd_full_refresh() -> None:
    print("=== Racing API Stat Cache — Full Refresh ===")
    conn = _get_conn()
    _init_db(conn)
    total = 0
    for supabase_table, local_table in _TABLE_MAP.items():
        rows = _fetch_all_supabase(supabase_table)
        n = _load_table(conn, local_table, rows, drop_first=True)
        print(f"  Loaded {n} rows into {local_table}")
        total += n
    conn.close()
    print(f"\nTotal rows cached: {total}")
    print(f"Cache location: {_DB_PATH}")
    print("Status: TIER 1/TIER 2 — operator visibility + calibration only. NO live VP effect.")


def cmd_incremental(date_str: str | None = None) -> None:
    """Load only entities missing from cache."""
    print("=== Racing API Stat Cache — Incremental ===")
    conn = _get_conn()
    _init_db(conn)

    # Find entity_ids present in verdicts backup for the date
    if date_str:
        verdict_file = Path(f"data/velo_prime_verdicts_{date_str.replace('-','_')}.json")
    else:
        verdict_files = sorted(Path("data").glob("velo_prime_verdicts_*.json"))
        verdict_file = verdict_files[-1] if verdict_files else None

    missing_trainers: set = set()
    missing_jockeys: set = set()

    if verdict_file and verdict_file.exists():
        with open(verdict_file) as f:
            verdicts = json.load(f)
        for race in verdicts:
            top = race.get("top") or {}
            t = top.get("trainer_id") or top.get("trainer")
            j = top.get("jockey_id") or top.get("jockey")
            if t: missing_trainers.add(t)
            if j: missing_jockeys.add(j)

        # Remove already-cached
        cached_t = set(r[0] for r in conn.execute("SELECT DISTINCT entity_id FROM trainer_courses"))
        cached_j = set(r[0] for r in conn.execute("SELECT DISTINCT entity_id FROM jockey_courses"))
        missing_trainers -= cached_t
        missing_jockeys -= cached_j
        print(f"  New trainers to cache: {len(missing_trainers)}")
        print(f"  New jockeys to cache: {len(missing_jockeys)}")
    else:
        print("  No verdict file found — running full refresh instead.")
        conn.close()
        cmd_full_refresh()
        return

    if not missing_trainers and not missing_jockeys:
        print("  Cache already current. Nothing to do.")
        conn.close()
        return

    # Fetch and insert for missing entities
    def _filter_and_insert(supabase_table: str, local_table: str, entity_ids: set) -> None:
        if not entity_ids:
            return
        for eid in entity_ids:
            req = urllib.request.Request(
                f"{_URL}/rest/v1/{supabase_table}?entity_id=eq.{eid}&limit=1000",
                headers=_HEADERS,
            )
            try:
                with urllib.request.urlopen(req) as r:
                    rows = json.loads(r.read())
                if rows:
                    _load_table(conn, local_table, rows, drop_first=False)
            except Exception as e:
                print(f"    WARN: failed to fetch {eid}: {e}")

    for t_table, l_table in [
        ("racing_api_trainer_analysis_courses", "trainer_courses"),
        ("racing_api_trainer_analysis_distances", "trainer_distances"),
        ("racing_api_trainer_analysis_jockeys", "trainer_jockeys"),
    ]:
        _filter_and_insert(t_table, l_table, missing_trainers)

    for t_table, l_table in [
        ("racing_api_jockey_analysis_courses", "jockey_courses"),
        ("racing_api_jockey_analysis_distances", "jockey_distances"),
        ("racing_api_jockey_analysis_trainers", "jockey_trainers"),
    ]:
        _filter_and_insert(t_table, l_table, missing_jockeys)

    conn.close()
    print("Incremental cache update complete.")


def cmd_runner_card(date_str: str) -> None:
    """Pre-load stats for all trainers/jockeys in tomorrow's card."""
    cmd_incremental(date_str)


def cmd_stats() -> None:
    """Print cache coverage stats."""
    print("=== Racing API Stat Cache — Stats ===")
    conn = _get_conn()
    _init_db(conn)
    print(f"\nCache file: {_DB_PATH}")
    for local_table in _SCHEMA.keys():
        try:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {local_table}").fetchone()[0]
            entities = conn.execute(f"SELECT COUNT(DISTINCT entity_id) FROM {local_table}").fetchone()[0]
            updated = conn.execute(f"SELECT MAX(last_updated) FROM {local_table}").fetchone()[0]
            print(f"  {local_table:<22}: {cnt:>8} rows | {entities:>6} entities | updated: {updated or 'never'}")
        except Exception as e:
            print(f"  {local_table}: ERR ({e})")
    conn.close()
    print("\nStatus: TIER 1/TIER 2 — operator visibility + calibration only. NO live VP effect.")


def cmd_check_entity(entity_id: str) -> None:
    """Look up a single entity across all cache tables."""
    conn = _get_conn()
    _init_db(conn)
    print(f"\n=== Entity lookup: {entity_id} ===")
    found = False
    for local_table in _SCHEMA.keys():
        rows = conn.execute(
            f"SELECT * FROM {local_table} WHERE entity_id=? ORDER BY runs DESC LIMIT 5",
            (entity_id,)
        ).fetchall()
        if rows:
            found = True
            print(f"\n{local_table}:")
            for r in rows:
                print(f"  partner={r['partner_id_or_name']} win%={r['win_pct']} pnl={r['pnl']} runs={r['runs']}")
    if not found:
        print(f"  Not found in cache — run --full-refresh or --incremental to populate.")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--full-refresh", action="store_true")
    group.add_argument("--incremental", action="store_true")
    group.add_argument("--runner-card", metavar="YYYY-MM-DD")
    group.add_argument("--stats", action="store_true")
    group.add_argument("--check-entity", metavar="ENTITY_ID")
    args = parser.parse_args()

    if args.full_refresh:
        cmd_full_refresh()
    elif args.incremental:
        cmd_incremental()
    elif args.runner_card:
        cmd_runner_card(args.runner_card)
    elif args.stats:
        cmd_stats()
    elif args.check_entity:
        cmd_check_entity(args.check_entity)


if __name__ == "__main__":
    main()
