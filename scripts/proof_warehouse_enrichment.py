"""
VELO PRIME -- Warehouse Enrichment Live Proof
==============================================
Runs one real score+persist cycle on a known race from Supabase,
then queries the stored verdict to verify warehouse keys in full_analysis.

Race: rac_11876774  Lingfield (AW) 7f  2026-03-20
  - 10 runners, all 10 in horse_racecard_history
  - trainer_course_analysis and trainer_distance_analysis populated

Usage:
  python scripts/proof_warehouse_enrichment.py
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

RACE_ID = "rac_11876774"

# ── Supabase client ──────────────────────────────────────────────────────────

from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
if not url or not key:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    sys.exit(1)

db = create_client(url, key)

# ── Fetch race + runners from Supabase ───────────────────────────────────────

print(f"\nFetching race {RACE_ID} from Supabase...")

race_row = db.table("races").select("*").eq("race_id", RACE_ID).single().execute().data
if not race_row:
    print("ERROR: race not found")
    sys.exit(1)

runner_rows = (
    db.table("runners")
    .select("*")
    .eq("race_id", RACE_ID)
    .execute()
    .data or []
)
print(f"  Race: {race_row['course']}  distance_f: {race_row['distance_f']}  going: {race_row['going']}")
print(f"  Runners: {len(runner_rows)}")

# ── Assemble normalized race dict ────────────────────────────────────────────
# Map Supabase columns -> canonical normalizer output schema

def _sf(v, d=0.0):
    try:
        return float(v) if v is not None else d
    except (TypeError, ValueError):
        return d

def _si(v, d=0):
    try:
        return int(v) if v is not None else d
    except (TypeError, ValueError):
        return d

normalized_runners = []
for r in runner_rows:
    normalized_runners.append({
        "horse_name":       r.get("horse_name", ""),
        "horse_id":         r.get("horse_id", ""),
        "official_rating":  _sf(r.get("or_rating")),
        "or":               _sf(r.get("or_rating")),
        "rpr":              _sf(r.get("rpr")),
        "ts":               _sf(r.get("ts_rating")),
        "trainer_name":     r.get("trainer", ""),
        "trainer_id":       r.get("trainer_id", ""),
        "jockey_name":      r.get("jockey", ""),
        "jockey_id":        r.get("jockey_id", ""),
        "best_odds_decimal": 0.0,   # not stored in runners table
        "odds_available_flag": False,
        "age":              r.get("age", ""),
        "sex":              r.get("sex", ""),
        "weight_lbs":       _si(r.get("weight"), 126),
        "draw":             _si(r.get("draw")),
        "form_figures":     r.get("form", ""),
        "spotlight":        "",
        "comment":          "",
        "trainer_14_days":  {},
        "_raw":             {},
    })

# races.distance_f is stored as tenths-of-furlongs (70 = 7.0f, 80 = 8.0f = 1m, 160 = 2m).
# Convert to Racing API label to match trainer_distance_analysis.dist / horse_racecard_history.dist.
from app.services.velo_prime_service import _dist_tenths_to_label
dist_f = race_row.get("distance_f", 0)
dist_str = _dist_tenths_to_label(float(dist_f)) if dist_f else ""

normalized_race = {
    "race_id":    RACE_ID,
    "course":     race_row.get("course", ""),
    "date":       str(race_row.get("date", "")),
    "off_time":   race_row.get("time", ""),
    "distance":   dist_str,
    "distance_f": dist_f,
    "going":      race_row.get("going", ""),
    "race_class": race_row.get("class", ""),
    "race_name":  race_row.get("race_name", ""),
    "type":       race_row.get("race_type", "Flat"),
    "runners":    normalized_runners,
}

print(f"  Normalized dist string: {dist_str}")

# ── Score + persist ──────────────────────────────────────────────────────────

print("\nScoring through score_race_velo_prime...")
from app.services.velo_prime_service import score_race_velo_prime, persist_race_predictions

predictions = score_race_velo_prime(normalized_race)
print(f"  Predictions returned: {len(predictions)}")

if not predictions:
    print("ERROR: no predictions returned")
    sys.exit(1)

# Print ranking before persist (pre-enrichment)
print("\n  Pre-persist ranking (scores unchanged by enrichment):")
for i, p in enumerate(predictions, 1):
    print(f"    {i}. {p['horse']:<30}  velo_prime_prob={p.get('velo_prime_prob', 0):.4f}"
          f"  confidence={p.get('confidence_level')}")

top_before = {
    "horse":           predictions[0]["horse"],
    "velo_prime_prob": predictions[0].get("velo_prime_prob"),
    "top_rank_score":  predictions[0].get("velo_prime_prob"),
    "confidence_level":predictions[0].get("confidence_level"),
}
print(f"\n  Top pick: {top_before['horse']}  prob={top_before['velo_prime_prob']:.4f}")

print("\nPersisting via persist_race_predictions (triggers warehouse enrichment)...")
ok = persist_race_predictions(normalized_race, predictions, decision_tier="proof_run")
print(f"  Persist result: {'OK' if ok else 'FAILED'}")

if not ok:
    print("ERROR: persist failed")
    sys.exit(1)

# ── Query stored verdict ─────────────────────────────────────────────────────

print(f"\nQuerying stored verdict for {RACE_ID}...")
verdict = db.table("velo_verdicts").select("*").eq("race_id", RACE_ID).single().execute().data

if not verdict:
    print("ERROR: verdict not found after persist")
    sys.exit(1)

full_analysis = verdict.get("full_analysis") or []
print(f"  full_analysis runner blocks: {len(full_analysis)}")

# ── PROOF 1: Enriched runner block ───────────────────────────────────────────

WAREHOUSE_KEYS = [
    "horse_recent_runs_90d", "horse_recent_avg_pos",
    "horse_course_runs", "horse_distance_runs", "horse_avg_pos_all",
    "trainer_course_runners", "trainer_course_1st",
    "trainer_course_ae", "trainer_course_win_pct",
    "trainer_dist_runners", "trainer_dist_1st", "trainer_dist_ae",
]

# Find first runner with at least some non-null warehouse values
enriched_runner = None
null_runner = None

for r in full_analysis:
    has_data = any(r.get(k) is not None for k in WAREHOUSE_KEYS)
    if has_data and enriched_runner is None:
        enriched_runner = r
    if not has_data and null_runner is None:
        null_runner = r

print("\n" + "=" * 60)
print("PROOF 1 — Sample enriched runner block (warehouse data present):")
print("=" * 60)
if enriched_runner:
    print(f"  horse:               {enriched_runner.get('horse')}")
    print(f"  horse_id:            {enriched_runner.get('horse_id')}")
    print(f"  velo_prime_prob:     {enriched_runner.get('velo_prime_prob')}")
    print(f"  confidence_level:    {enriched_runner.get('confidence_level')}")
    print()
    print("  -- Horse history warehouse keys --")
    for k in WAREHOUSE_KEYS[:5]:
        print(f"  {k:<30} = {enriched_runner.get(k)}")
    print()
    print("  -- Trainer course warehouse keys --")
    for k in WAREHOUSE_KEYS[5:9]:
        print(f"  {k:<30} = {enriched_runner.get(k)}")
    print()
    print("  -- Trainer distance warehouse keys --")
    for k in WAREHOUSE_KEYS[9:]:
        print(f"  {k:<30} = {enriched_runner.get(k)}")
else:
    print("  WARNING: no enriched runner found — all warehouse values null")

# ── PROOF 2: Top-level verdict fields unchanged ───────────────────────────────

print("\n" + "=" * 60)
print("PROOF 2 — Top-level verdict fields (must match pre-persist values):")
print("=" * 60)
print(f"  top_rank_score:      {verdict.get('top_rank_score')}")
print(f"  velo_prime_prob:     {verdict.get('velo_prime_prob')}")
print(f"  confidence_level:    {verdict.get('confidence_level')}")
print(f"  decision_tier:       {verdict.get('decision_tier')}")
print(f"  top_rank_horse_id:   {verdict.get('top_rank_horse_id')}")
print()
print(f"  Pre-persist top prob:         {top_before['velo_prime_prob']:.4f}")
stored_prob = verdict.get("velo_prime_prob") or 0
print(f"  Stored  top prob:             {stored_prob:.4f}")
match = abs((top_before["velo_prime_prob"] or 0) - (stored_prob or 0)) < 1e-9
print(f"  Match:                        {'CONFIRMED' if match else 'MISMATCH - INVESTIGATE'}")

# ── PROOF 3: Ranking order unchanged ─────────────────────────────────────────

print("\n" + "=" * 60)
print("PROOF 3 — Ranking order (pre-persist vs stored full_analysis):")
print("=" * 60)
pre_order  = [p["horse"] for p in predictions]
post_order = [r.get("horse") for r in full_analysis]
print(f"  Pre-persist order:  {pre_order}")
print(f"  Stored order:       {post_order}")
print(f"  Order preserved:    {'CONFIRMED' if pre_order == post_order else 'MISMATCH - INVESTIGATE'}")

# ── PROOF 4: Warehouse keys in Supabase JSON ──────────────────────────────────

print("\n" + "=" * 60)
print("PROOF 4 — Warehouse keys present in Supabase-stored JSON:")
print("=" * 60)
present  = [k for k in WAREHOUSE_KEYS if k in (full_analysis[0] if full_analysis else {})]
missing  = [k for k in WAREHOUSE_KEYS if k not in (full_analysis[0] if full_analysis else {})]
print(f"  Keys present ({len(present)}/12): {present}")
if missing:
    print(f"  Keys missing: {missing}")
else:
    print("  All 12 warehouse keys confirmed in stored JSON")

# ── PROOF 5: Runner with all-null warehouse values ────────────────────────────

print("\n" + "=" * 60)
print("PROOF 5 — Runner with missing warehouse data (all-null fallback):")
print("=" * 60)
if null_runner:
    print(f"  horse:               {null_runner.get('horse')}")
    print(f"  horse_id:            {null_runner.get('horse_id')}")
    for k in WAREHOUSE_KEYS:
        v = null_runner.get(k)
        print(f"  {k:<30} = {v!r}  {'NULL OK' if v is None else 'HAS VALUE'}")
else:
    # All runners have some warehouse data — show one and confirm scoring fields present
    print("  All runners have some warehouse data (full coverage).")
    print("  Showing runner[0] scoring fields to confirm they are untouched:")
    r0 = full_analysis[0] if full_analysis else {}
    scoring_keys = ["velo_prime_prob", "sqpe_v17_prob", "improvement_score",
                    "market_deception_score", "place_prob", "confidence_level"]
    for k in scoring_keys:
        print(f"  {k:<30} = {r0.get(k)}")
    print()
    # Force-show null case from a runner with 0 course or dist runs
    for r in full_analysis:
        if r.get("trainer_course_runners") is None:
            print(f"  Null-trainer-course example — horse: {r.get('horse')}")
            for k in WAREHOUSE_KEYS[5:]:
                print(f"  {k:<30} = {r.get(k)!r}")
            break

print("\n" + "=" * 60)
print("PROOF COMPLETE")
print("=" * 60)
