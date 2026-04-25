"""
Phase A3: Bulk load BHA macro data from data/bha_industry_stats.json into Supabase.
Populates: bha_industry_stats, bha_yearly_summary, bha_macro_specialty_metrics
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in .env")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

with open(ROOT / "data" / "bha_industry_stats.json", encoding="utf-8") as f:
    bha = json.load(f)

# ─── Helpers ───────────────────────────────────────────────────────────────────

def upsert_batch(table: str, rows: list[dict], conflict_col: str = None):
    if not rows:
        return
    if conflict_col:
        sb.table(table).upsert(rows, on_conflict=conflict_col).execute()
    else:
        # Delete all and re-insert (small tables, safe)
        sb.table(table).delete().neq("id", 0).execute()
        # Insert in chunks of 500
        for i in range(0, len(rows), 500):
            sb.table(table).insert(rows[i:i+500]).execute()
    print(f"  {table}: {len(rows)} rows loaded")


# ─── bha_industry_stats (atomic metric rows) ───────────────────────────────────

rows_stats = []

def push_stat(year, category, name, value, race_code=None, race_type=None,
              ambiguity=False, ambiguity_note=None, section=None, text_val=None):
    rows_stats.append({
        "year": year,
        "metric_category": category,
        "metric_name": name,
        "metric_value": float(value) if value is not None else None,
        "metric_value_text": text_val,
        "race_code": race_code,
        "race_type": race_type,
        "ambiguity_flag": ambiguity,
        "ambiguity_note": ambiguity_note,
        "source_section": section,
    })

# fixtures_scheduled
for row in bha["fixtures_scheduled"]["data"]:
    y = row["year"]
    af = row.get("ambiguity_flag", False)
    an = row.get("note") if af else None
    for code, val in [("flat_turf", row.get("flat_turf")), ("flat_awt", row.get("flat_awt")),
                       ("jump", row.get("jump")), ("total", row.get("total"))]:
        push_stat(y, "fixtures_scheduled", code, val, ambiguity=af, ambiguity_note=an, section="fixtures_scheduled")

# fixtures_ran
for row in bha["fixtures_ran"]["data"]:
    y = row["year"]
    for code, val in [("flat_turf", row.get("flat_turf")), ("flat_awt", row.get("flat_awt")),
                       ("jump", row.get("jump")), ("total", row.get("total"))]:
        push_stat(y, "fixtures_ran", code, val, section="fixtures_ran")

# abandonments
for row in bha.get("abandonments", {}).get("data", []):
    y = row["year"]
    af = row.get("ambiguity_flag", False)
    an = row.get("note") if af else None
    for key in ["weather", "waterlogging", "frost", "snow", "other", "total"]:
        if key in row:
            push_stat(y, "abandonments", key, row[key], ambiguity=af, ambiguity_note=an, section="abandonments")

# avg_field_size_by_code
for row in bha.get("avg_field_size_by_code", {}).get("data", []):
    y = row["year"]
    for code in ["flat", "jump", "aw"]:
        if code in row:
            push_stat(y, "avg_field_size", f"by_code_{code}", row[code], race_code=code, section="avg_field_size_by_code")

# avg_field_size_by_race_type
for row in bha.get("avg_field_size_by_race_type", {}).get("data", []):
    y = row["year"]
    for rtype in ["handicap", "non_handicap", "maiden", "pattern_group", "listed"]:
        if rtype in row:
            push_stat(y, "avg_field_size", f"by_type_{rtype}", row[rtype], race_type=rtype, section="avg_field_size_by_race_type")

# runners
runners_data = bha.get("runners", {})
for row in runners_data.get("total_starts", {}).get("data", []):
    y = row["year"]
    push_stat(y, "runners", "total_starts", row.get("total"), section="runners")
for row in runners_data.get("individual_runners", {}).get("data", []):
    y = row["year"]
    push_stat(y, "runners", "individual_runners", row.get("total"), section="runners")
for row in runners_data.get("avg_runs_per_horse", {}).get("data", []):
    y = row["year"]
    push_stat(y, "runners", "avg_runs_per_horse", row.get("value") or row.get("avg"), section="runners")

# non_runners
for row in bha.get("non_runners", {}).get("data", []):
    y = row["year"]
    for key in ["total", "per_race", "rate_pct"]:
        if key in row:
            push_stat(y, "non_runners", key, row[key], section="non_runners")

# favourite_market
fav_data = bha.get("favourite_market", {})
for row in fav_data.get("data", []):
    y = row["year"]
    for key in ["win_pct", "placed_pct", "sp_favourite_win_pct"]:
        if key in row:
            push_stat(y, "favourite_market", key, row[key], section="favourite_market")

# prize_money
prize_data = bha.get("prize_money", {})
for row in prize_data.get("data", []):
    y = row["year"]
    for key in ["flat_total_gbp", "jump_total_gbp", "aw_total_gbp", "total_gbp", "avg_per_race_gbp"]:
        if key in row:
            push_stat(y, "prize_money", key, row[key], section="prize_money")

# horses_in_training
hit_data = bha.get("horses_in_training", {})
for row in hit_data.get("data", []):
    y = row["year"]
    af = row.get("ambiguity_flag", False)
    an = hit_data.get("methodology_note") if af else None
    for key in ["flat", "jump", "dual_purpose", "total"]:
        if key in row:
            push_stat(y, "horses_in_training", key, row[key], ambiguity=af, ambiguity_note=an, section="horses_in_training")

# race_structure / races_run_by_type
for section_key in ["races_run_by_type", "race_structure"]:
    sec = bha.get(section_key, {})
    for row in sec.get("data", []):
        y = row["year"]
        for key, val in row.items():
            if key not in ("year", "note", "ambiguity_flag") and val is not None:
                push_stat(y, section_key, key, val, section=section_key)

# race_card_structure
for row in bha.get("race_card_structure", {}).get("data", []):
    y = row["year"]
    for key, val in row.items():
        if key not in ("year", "note") and val is not None:
            push_stat(y, "race_card_structure", key, val, section="race_card_structure")

print(f"Total atomic stat rows: {len(rows_stats)}")
upsert_batch("bha_industry_stats", rows_stats)


# ─── bha_yearly_summary ────────────────────────────────────────────────────────

# Build one row per year from key sections
years = sorted(set(r["year"] for r in bha["fixtures_ran"]["data"]))

yearly_rows = []
for y in years:
    def get_stat(section_data, year, field):
        for r in section_data:
            if r["year"] == year:
                return r.get(field)
        return None

    sched = get_stat(bha["fixtures_scheduled"]["data"], y, "total")
    ran   = get_stat(bha["fixtures_ran"]["data"], y, "total")
    aband_rows = bha.get("abandonments", {}).get("data", [])
    aband_total = get_stat(aband_rows, y, "total")
    aband_flag  = any(r["year"] == y and r.get("ambiguity_flag") for r in aband_rows)

    aband_rate = round((aband_total / sched * 100), 2) if sched and aband_total else None

    fav_rows = bha.get("favourite_market", {}).get("data", [])
    fav_win  = get_stat(fav_rows, y, "win_pct")
    fav_plc  = get_stat(fav_rows, y, "placed_pct")

    fs_rows = bha.get("avg_field_size_by_code", {}).get("data", [])
    fs_flat = get_stat(fs_rows, y, "flat")
    fs_jump = get_stat(fs_rows, y, "jump")
    fs_aw   = get_stat(fs_rows, y, "aw")

    run_rows = bha.get("runners", {})
    total_starts = get_stat(run_rows.get("total_starts", {}).get("data", []), y, "total")
    ind_runners  = get_stat(run_rows.get("individual_runners", {}).get("data", []), y, "total")
    avg_runs     = get_stat(run_rows.get("avg_runs_per_horse", {}).get("data", []), y, "value") or \
                   get_stat(run_rows.get("avg_runs_per_horse", {}).get("data", []), y, "avg")

    ambig = aband_flag
    ambig_note = "2024 abandonment count unreliable (column misalignment in source PDF)" if y == 2024 and aband_flag else None

    yearly_rows.append({
        "year": y,
        "fixtures_scheduled": sched,
        "fixtures_ran": ran,
        "fixtures_abandoned": aband_total,
        "abandonment_rate_pct": aband_rate,
        "avg_field_size_flat": fs_flat,
        "avg_field_size_jump": fs_jump,
        "avg_field_size_aw": fs_aw,
        "total_starts": total_starts,
        "individual_runners": ind_runners,
        "avg_runs_per_horse": avg_runs,
        "fav_win_pct": fav_win,
        "fav_placed_pct": fav_plc,
        "ambiguity_flag": ambig,
        "ambiguity_note": ambig_note,
    })

upsert_batch("bha_yearly_summary", yearly_rows, conflict_col="year")


# ─── bha_macro_specialty_metrics ──────────────────────────────────────────────

spec_rows = []

def push_spec(year, mtype, sub_key, numeric=None, pct=None, method=None, ambig=False, ambig_note=None):
    spec_rows.append({
        "year": year,
        "metric_type": mtype,
        "sub_key": sub_key,
        "value_numeric": float(numeric) if numeric is not None else None,
        "value_pct": float(pct) if pct is not None else None,
        "methodology_note": method,
        "ambiguity_flag": ambig,
        "ambiguity_note": ambig_note,
    })

# Going distribution (turf)
going_data = bha.get("turf_going_distribution", {})
method_note = going_data.get("methodology_note")
for row in going_data.get("data", []):
    y = row["year"]
    for going_key in ["hard", "firm", "good_to_firm", "good", "good_to_soft", "soft", "heavy"]:
        if going_key in row:
            push_spec(y, "going_distribution_turf", going_key, pct=row[going_key], method=method_note)

# Races run by type (speciality split)
for row in bha.get("races_run_by_type", {}).get("data", []):
    y = row["year"]
    total = row.get("total")
    for key, val in row.items():
        if key not in ("year", "total") and val is not None and total:
            push_spec(y, "race_type_mix", key, numeric=val, pct=round(val/total*100, 3) if total else None)

# Horses in training breakdown
hit_method = bha.get("horses_in_training", {}).get("methodology_note")
hit_ambig_note = "HIT methodology changed ~2016/2017: pre-2016 = monthly averages, post-2016 = YTD counts"
for row in bha.get("horses_in_training", {}).get("data", []):
    y = row["year"]
    af = row.get("ambiguity_flag", False)
    for key in ["flat", "jump", "dual_purpose", "total"]:
        if key in row:
            push_spec(y, "hit_breakdown", key, numeric=row[key],
                      method=hit_method, ambig=af, ambig_note=hit_ambig_note if af else None)

# Prize money breakdown
for row in bha.get("prize_money", {}).get("data", []):
    y = row["year"]
    total = row.get("total_gbp")
    for key in ["flat_total_gbp", "jump_total_gbp", "aw_total_gbp"]:
        if key in row and total:
            push_spec(y, "prize_money_distribution", key.replace("_gbp",""),
                      numeric=row[key], pct=round(row[key]/total*100, 3))

# Specialty metrics (if present)
for row in bha.get("specialty_metrics", {}).get("data", []):
    y = row["year"]
    for key, val in row.items():
        if key != "year" and val is not None:
            push_spec(y, "specialty", key, numeric=val if isinstance(val, (int, float)) else None,
                      method=None)

print(f"Total specialty metric rows: {len(spec_rows)}")
upsert_batch("bha_macro_specialty_metrics", spec_rows)

print("\n=== Phase A3 COMPLETE ===")
print(f"bha_industry_stats:       {len(rows_stats)} rows")
print(f"bha_yearly_summary:       {len(yearly_rows)} rows ({min(years)}-{max(years)})")
print(f"bha_macro_specialty_metrics: {len(spec_rows)} rows")
print("\nAmbiguity flags preserved. Provenance intact.")
