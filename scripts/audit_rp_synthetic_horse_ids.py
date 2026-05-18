"""
RP Synthetic Horse ID Audit
==============================
Audits the use of synthetic horse IDs (RP_{horse_norm}) introduced when
Racing API horse_id is absent in RP-profile-sourced runs.

Reports:
  - Count of synthetic IDs in shadow predictions and verdicts
  - horse_norm collisions (same norm, different horse names)
  - Cross-date recurrence (same horse appearing on multiple days)
  - Missing trainer/jockey on synthetic-ID runners
  - Alias table candidates (synthetic ID + known Racing API ID for same horse)

Usage:
    python scripts/audit_rp_synthetic_horse_ids.py
    python scripts/audit_rp_synthetic_horse_ids.py --date 2026-05-18
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _load_rp_profile_history() -> list[dict]:
    """Load all RP runner profiles (latest only for now)."""
    rows = []
    profile_path = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"
    if not profile_path.exists():
        return rows
    try:
        import pandas as pd
        rp = pd.read_parquet(profile_path)
        for _, row in rp.iterrows():
            rows.append({
                "date": str(row.get("race_date") or ""),
                "horse": str(row.get("horse") or ""),
                "horse_norm": str(row.get("horse_norm") or "").lower(),
                "trainer": str(row.get("trainer") or ""),
                "jockey": str(row.get("jockey") or ""),
                "horse_id": row.get("horse_id"),
                "synthetic_id": f"RP_{str(row.get('horse_norm') or '').lower()}",
            })
    except Exception as e:
        print(f"  WARN: Could not load RP profile: {e}")
    return rows


def _load_shadow_predictions() -> list[dict]:
    """Load all shadow prediction parquets from data/shadow/."""
    rows = []
    shadow_dir = ROOT / "data" / "shadow"
    if not shadow_dir.exists():
        return rows
    try:
        import pandas as pd
        for f in sorted(shadow_dir.glob("runner_master_shadow_predictions_*.parquet")):
            df = pd.read_parquet(f)
            for _, row in df.iterrows():
                horse_id = str(row.get("horse_id") or "")
                if horse_id.startswith("RP_"):
                    rows.append({
                        "date": str(row.get("race_date") or f.stem.split("_")[-1]),
                        "horse": str(row.get("horse") or ""),
                        "horse_id": horse_id,
                        "synthetic": True,
                        "course": str(row.get("course") or ""),
                        "trainer": str(row.get("trainer") or ""),
                        "jockey": str(row.get("jockey") or ""),
                    })
    except Exception as e:
        print(f"  WARN: Could not load shadow predictions: {e}")
    return rows


def _load_local_verdicts() -> list[dict]:
    """Load local verdict JSON files for synthetic ID presence."""
    rows = []
    data_dir = ROOT / "data"
    for f in sorted(data_dir.glob("velo_prime_verdicts_*.json")):
        try:
            verdicts = json.loads(f.read_text())
            if isinstance(verdicts, list):
                for v in verdicts:
                    hid = str(v.get("top_rank_horse_id") or "")
                    if hid.startswith("RP_"):
                        rows.append({
                            "date": str(v.get("date") or f.stem.replace("velo_prime_verdicts_", "").replace("_", "-")),
                            "horse_id": hid,
                            "race_id": v.get("race_id", ""),
                        })
        except Exception:
            pass
    return rows


def main():
    parser = argparse.ArgumentParser(description="Audit RP synthetic horse IDs")
    parser.add_argument("--date", default=None, help="Focus on specific date YYYY-MM-DD (default: all)")
    args = parser.parse_args()

    print("RP Synthetic Horse ID Audit")
    print("=" * 62)

    rp_rows = _load_rp_profile_history()
    shadow_rows = _load_shadow_predictions()
    verdict_rows = _load_verdicts() if False else _load_local_verdicts()

    # Filter by date if specified
    if args.date:
        rp_rows = [r for r in rp_rows if r["date"] == args.date]
        shadow_rows = [r for r in shadow_rows if r["date"] == args.date]
        verdict_rows = [r for r in verdict_rows if r["date"] == args.date]

    print(f"\n1. SYNTHETIC ID INVENTORY")
    print(f"   RP profile rows: {len(rp_rows)}")
    synthetic_rp = [r for r in rp_rows if not r["horse_id"]]
    print(f"   Rows with no Racing API horse_id (will get synthetic): {len(synthetic_rp)}")
    print(f"   Shadow prediction rows with RP_ id: {len(shadow_rows)}")
    print(f"   Verdict rows with RP_ top_rank_horse_id: {len(verdict_rows)}")

    print(f"\n2. HORSE_NORM COLLISION CHECK")
    norm_to_names: dict[str, set] = defaultdict(set)
    for r in rp_rows:
        hn = r["horse_norm"]
        horse_name = r["horse"]
        if hn:
            norm_to_names[hn].add(horse_name)
    collisions = {norm: names for norm, names in norm_to_names.items() if len(names) > 1}
    if collisions:
        print(f"   COLLISION WARNING: {len(collisions)} horse_norm values map to multiple horse names:")
        for norm, names in sorted(collisions.items())[:10]:
            print(f"     RP_{norm} → {sorted(names)}")
    else:
        print(f"   No collisions found ({len(norm_to_names)} unique horse_norms)")

    print(f"\n3. CROSS-DATE RECURRENCE (same synthetic ID, multiple dates)")
    id_to_dates: dict[str, set] = defaultdict(set)
    for r in rp_rows:
        sid = r["synthetic_id"]
        if sid and r["date"]:
            id_to_dates[sid].add(r["date"])
    multi_date = {sid: dates for sid, dates in id_to_dates.items() if len(dates) > 1}
    print(f"   Synthetic IDs appearing on 2+ dates: {len(multi_date)}")
    for sid, dates in sorted(multi_date.items())[:10]:
        print(f"     {sid}: {sorted(dates)}")

    print(f"\n4. MISSING TRAINER/JOCKEY ON SYNTHETIC-ID RUNNERS")
    missing_trainer = [r for r in rp_rows if not r["trainer"] or r["trainer"] == "None"]
    missing_jockey  = [r for r in rp_rows if not r["jockey"]  or r["jockey"]  == "None"]
    print(f"   Missing trainer: {len(missing_trainer)}")
    print(f"   Missing jockey:  {len(missing_jockey)}")
    if missing_trainer[:5]:
        for r in missing_trainer[:5]:
            print(f"     {r['synthetic_id']} — {r['horse']} ({r['date']})")

    print(f"\n5. ALIAS TABLE CANDIDATES")
    print(f"   Horses with RP synthetic ID AND known Racing API horse_id (from any source):")
    has_real_id = [r for r in rp_rows if r.get("horse_id") and not str(r["horse_id"]).startswith("RP_")]
    if has_real_id:
        print(f"   {len(has_real_id)} candidates ready for alias table:")
        for r in has_real_id[:10]:
            print(f"     {r['synthetic_id']}  →  racing_api_id={r['horse_id']}  ({r['horse']})")
    else:
        print(f"   0 candidates (no Racing API horse_ids in current RP profile)")
        print(f"   Alias table will be populated when Racing API auth is restored")

    print(f"\n6. GOVERNANCE NOTE")
    print(f"   Synthetic IDs are auditable: RP_ prefix marks them as derived from RP profile")
    print(f"   They are stable within a single RP profile ingestion run")
    print(f"   They may differ if horse_norm changes between RP file versions")
    print(f"   Alias table: scripts/build_rp_horse_alias_table.py (not yet built)")
    print(f"   Priority: build when Racing API auth is restored (cross-link real IDs)")
    print()
    print("=" * 62)


if __name__ == "__main__":
    main()
