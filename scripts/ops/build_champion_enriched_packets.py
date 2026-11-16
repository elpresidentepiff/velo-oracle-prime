#!/usr/bin/env python3
"""Join Champion Intent and factual FormFav pre-race features into a NON-SCORING shadow dataset.

This deliberately does not train, rank, persist to Supabase, or alter Prime. It is a
reproducible input boundary for a future separately fitted enriched challenger.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Explicit factual allowlist; never ingest provider picks, results or post-off data.
FF_FIELDS = (
    "ff_form_present", "ff_overall_present", "ff_track_present",
    "ff_distance_present", "ff_condition_present", "ff_speedmap_present",
    "ff_class_fit_present", "ff_quality_score", "ff_training_eligible",
    "ff_recent_win_rate_3", "ff_recent_win_rate_5", "ff_race_class_rating",
    "ff_track_starts", "ff_distance_starts", "ff_condition_starts",
    "ff_style_l", "ff_style_p", "ff_style_m", "ff_style_b", "ff_style_x",
    "ff_pace_slow", "ff_pace_moderate", "ff_pace_fast", "ff_pace_very_fast",
)
SCHEMA = "CHAMPION_INTENT_ENRICHED_PACKET_V1"

def norm(value):
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)

def make_packets(champion_rows, formfav_report, *, pre_off_verified=False):
    """Fail closed on identity ambiguity; never imply timestamp verification."""
    by_race = {}
    for race in formfav_report.get("races", []):
        rid = str(race.get("race_id", ""))
        for runner in race.get("runners", []):
            key = (rid, norm(runner.get("horse_name")))
            by_race.setdefault(key, []).append(runner)
    packets, counts = [], Counter()
    for row in champion_rows:
        key = (str(row.get("race_id", "")), norm(row.get("horse")))
        candidates = by_race.get(key, [])
        status = "MATCHED" if len(candidates) == 1 else ("AMBIGUOUS" if candidates else "MISSING")
        ff = candidates[0] if status == "MATCHED" else {}
        # No timestamp provenance is present in the existing daily FormFav artifact.
        # A joined feature row is NOT automatically training-eligible.
        eligible = bool(pre_off_verified and status == "MATCHED" and ff.get("ff_training_eligible") == 1.0)
        values = {name: ff.get(name) if status == "MATCHED" else None for name in FF_FIELDS}
        values.update({name + "_missing": int(values[name] is None) for name in FF_FIELDS})
        packet = {
            "schema": SCHEMA, "race_id": row.get("race_id"),
            "horse": row.get("horse"), "rp_uid": row.get("rp_uid"),
            "original_champion_prob": row.get("champion_intent_shadow_prob"),
            "original_champion_rank": row.get("rank_in_race"),
            "identity_status": status,
            "pre_off_verified": bool(pre_off_verified),
            "eligible_for_fit": eligible,
            "ineligibility_reason": None if eligible else ("PRE_OFF_PROVENANCE_UNVERIFIED" if not pre_off_verified else status),
            "production_influence": False, "stake_authorised": False,
            "promotion_eligible": False, "provider_predictions_consumed": False,
            "feature_values": values,
        }
        packet["input_sha256"] = hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest()
        packets.append(packet)
        counts[status] += 1
    return packets, dict(counts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    date_tag = args.date.replace("-", "_")
    base = ROOT / "data" / "reports"
    champion = base / f"intent_shadow_scorecard_{date_tag}.csv"
    formfav = base / f"formfav_uk_shadow_features_{date_tag}.json"
    if not champion.is_file() or not formfav.is_file():
        ap.error(f"Missing input: {champion} or {formfav}")
    with champion.open(newline="", encoding="utf-8") as f:
        champion_rows = list(csv.DictReader(f))
    ff = json.loads(formfav.read_text(encoding="utf-8"))
    if ff.get("date") != args.date:
        ap.error("FormFav artifact date does not match requested date")
    packets, counts = make_packets(champion_rows, ff, pre_off_verified=False)
    output = args.output or base / f"champion_intent_enriched_packets_{date_tag}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "date": args.date, "schema": SCHEMA, "status": "FEATURE_PACKETS_ONLY_NO_FIT",
        "pre_off_provenance_verified": False, "eligible_for_fit": 0,
        "join_counts": counts, "packets": packets,
    }, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "runners": len(packets), "join_counts": counts, "eligible_for_fit": 0}))

if __name__ == "__main__":
    main()
