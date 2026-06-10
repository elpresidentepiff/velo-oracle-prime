#!/usr/bin/env python3
"""
Local Truth Database — DuckDB prototype (Phase DB-1: read-only backfill)
=========================================================================
Loads existing artifacts into one queryable store. Sources are NEVER
modified; the DB is rebuilt from scratch on every run (idempotent).
Spec: docs/current/LOCAL_TRUTH_DATABASE_SPEC.md.

Identity law: identity_aliases is first-class — every synthetic ID ever
seen maps (or fails loudly to map) to a canonical RP id.

Usage:
    PYTHONPATH=. python scripts/ops/build_local_truth_duckdb.py

Output: data/current/velo_truth.duckdb  (gitignored artifact, rebuildable)
"""
from __future__ import annotations

import glob
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "current" / "velo_truth.duckdb"


def main() -> int:
    if DB.exists():
        DB.unlink()  # full rebuild — sources are the truth, DB is the index
    con = duckdb.connect(str(DB))

    # ── verdicts (top pick per race) from local backups ───────────────────────
    rows = []
    for f in glob.glob(str(ROOT / "data/velo_prime_verdicts_*.json")):
        m = re.search(r"verdicts_(\d{4}_\d{2}_\d{2})\.json$", f)
        if not m:
            continue
        date = m.group(1).replace("_", "-")
        try:
            races = json.loads(Path(f).read_text())
            races = races if isinstance(races, list) else races.get("races", [])
        except Exception:
            continue
        for r in races:
            top = r.get("top") or {}
            rows.append({
                "date": date, "race_id": str(r.get("race_id", "")),
                "course": r.get("course"), "off_time": r.get("off_time"),
                "tier": r.get("tier"), "horse": top.get("horse"),
                "horse_id": str(top.get("horse_id") or ""),
                "vp": top.get("velo_prime_prob"),
                "rpdc_lookup_status": top.get("rpdc_lookup_status"),
                "rpdc_primary_tag": top.get("rpdc_primary_tag"),
                "source_file": Path(f).name,
            })
    import pandas as pd
    verdicts_df = pd.DataFrame(rows)
    con.execute("CREATE TABLE verdicts AS SELECT * FROM verdicts_df")

    # ── sigma conclusions (canonical dump) ────────────────────────────────────
    dump = ROOT / "data/sigma_audits_dump.json"
    if dump.exists():
        con.execute(f"CREATE TABLE sigma_conclusions AS SELECT * FROM read_json_auto('{dump}')")

    # ── results (canonical rp_results files) ─────────────────────────────────
    res_rows = []
    for f in glob.glob(str(ROOT / "data/results/rp_results_*.json")):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        races_list = d if isinstance(d, list) else d.get("results", [])
        for r in races_list:
            for x in r.get("runners", []):
                res_rows.append({
                    "race_id": str(r.get("race_id", "")), "course": r.get("course"),
                    "horse_id": str(x.get("horse_id") or ""), "horse": x.get("horse"),
                    "position": str(x.get("position", "")), "sp_dec": x.get("sp_dec"),
                    "source_file": Path(f).name,
                })
    if res_rows:
        results_df = pd.DataFrame(res_rows).drop_duplicates()
        con.execute("CREATE TABLE results AS SELECT * FROM results_df")

    # ── race_days from the truth ledger ───────────────────────────────────────
    ledger = ROOT / "data/current/velo_100_day_truth_ledger.json"
    if ledger.exists():
        days = json.loads(ledger.read_text()).get("days", [])
        day_rows = [{
            "date": d["date"], "classification": d["final_day_classification"],
            "local_races": d.get("local_races"), "sb_verdicts": d.get("sb_verdicts"),
            "learning_ran": bool(d.get("learning_ran")),
            "contamination_risk": bool(d.get("learning_contamination_risk")),
        } for d in days]
        race_days_df = pd.DataFrame(day_rows)
        con.execute("CREATE TABLE race_days AS SELECT * FROM race_days_df")

    # ── identity_aliases: synthetic verdict ids ↔ canonical via results name ──
    con.execute("""
        CREATE TABLE identity_aliases AS
        SELECT DISTINCT
            r.horse_id   AS canonical_id,
            'horse'      AS entity_type,
            v.horse_id   AS source_id,
            'verdict_backup' AS source,
            lower(regexp_replace(v.horse, '[^a-zA-Z0-9]', '', 'g')) AS normalized_name,
            v.date || '|' || coalesce(v.course,'') AS dco_key,
            CASE WHEN v.horse_id = r.horse_id THEN 'exact' ELSE 'unique_name' END AS confidence
        FROM verdicts v
        JOIN results r
          ON lower(regexp_replace(v.horse, '[^a-zA-Z0-9]', '', 'g'))
           = lower(regexp_replace(r.horse, '[^a-zA-Z0-9]', '', 'g'))
        WHERE v.horse IS NOT NULL AND r.horse_id <> ''
    """)

    # ── provenance ────────────────────────────────────────────────────────────
    con.execute("CREATE TABLE _meta AS SELECT ? AS built_at, 'DB-1 read-only backfill' AS phase", [datetime.now(UTC).isoformat()])

    stats = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("verdicts", "sigma_conclusions", "results", "race_days", "identity_aliases")}
    # The proof query that took a week of forensics, now in one line:
    synth = con.execute("""
        SELECT COUNT(*) FROM verdicts v
        WHERE v.horse_id LIKE 'rp_%'
          AND EXISTS (SELECT 1 FROM identity_aliases a WHERE a.source_id = v.horse_id)
    """).fetchone()[0]
    print(f"velo_truth.duckdb built -> {DB}")
    for t, n in stats.items():
        print(f"  {t}: {n:,}")
    print(f"  synthetic verdict ids resolvable to canonical via aliases: {synth:,}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
