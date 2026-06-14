# VFU Race Autopsy Schema V1

**Status**: SCHEMA ONLY — no autopsy execution in Phase 1
**Created**: 2026-06-14
**Owner**: VÉLØ Forensics Unit

---

## Purpose

A Race Autopsy is a per-race forensic record created by the VFU after results close.

It captures everything VÉLØ knew, what happened, why the pick succeeded or failed, and what should be investigated further.

One autopsy per race per VÉLØ pick. Not per-race-field — per-race-where-VÉLØ-had-a-verdict.

---

## Schema

```json
{
  "autopsy_id":               "string — {race_date}_{course_short}_{off_time_hhmm}",
  "race_id":                  "string — canonical race identifier",
  "race_date":                "YYYY-MM-DD",
  "course":                   "string",
  "off_time":                 "HH:MM",
  "race_type":                "Flat | Hurdle | Chase | NH Flat | AW",
  "surface":                  "Turf | AW | All-Weather",
  "race_class":               "string or null",
  "field_size":               "integer",
  "going":                    "string",
  "distance_furlongs":        "float",

  "velo_top_pick":            "horse_name",
  "velo_top_pick_id":         "integer or null — rp_uid if available",
  "velo_top3":                ["horse_name", ...],
  "velo_top4":                ["horse_name", ...],

  "vp_score":                 "float — velo_prime_prob of top pick",
  "vp_gate_label":            "GREEN | AMBER | RED",
  "vp_day_avg":               "float — day-level avg VP",
  "improvement_score":        "float or null",
  "mds_score":                "float or null",
  "rpdc_tag":                 "string or null",

  "course_tier":              "EXCELLING | NEUTRAL | DRAIN | OBSERVATION_ONLY",
  "odds_band":                "SP_1.5_4.0 | SP_4.0_6.0 | SP_6.0_PLUS | UNKNOWN",
  "pick_sp":                  "float or null",

  "predicted_horse":          "horse_name — same as velo_top_pick",
  "predicted_horse_id":       "integer or null",
  "actual_winner":            "horse_name",
  "actual_winner_id":         "integer or null",
  "actual_winner_sp":         "float or null",

  "predicted_finish_position": "integer or null — where top pick actually finished",
  "predicted_outcome":        "WIN | PLACED | MISS",

  "winner_in_velo_frame":     "boolean — was winner inside top3/top4?",
  "winner_rank_in_velo":      "integer or null — 1=top pick, 2=2nd pick, etc.",

  "miss_classification":      "string — from failure taxonomy",
  "failure_class":            "string or null — from failure taxonomy",
  "secondary_failure_class":  "string or null",

  "source_quality":           "FULL_ENGINE_RUN | FULL_ENGINE_RUN_RP_SOURCED | PARTIAL | FAILED",
  "data_gaps":                ["list of missing fields or null"],

  "investigation_questions":  ["string — open forensic questions"],

  "passport_update_candidate":  "boolean",
  "pattern_update_candidate":   "boolean",
  "human_review_required":      "boolean",

  "sigma_row_id":             "string or null — link to sigma_audits row",
  "innovation_protocol_row":  "string or null",

  "generated_at":             "ISO8601 UTC timestamp",
  "generated_by":             "VFU_AUTOPSY_V1",
  "phase":                    "CURRENT_ERA | PRE_SURGERY | ARCHIVE"
}
```

---

## Field Notes

### vp_gate_label
Inherited from day-level VP gate at race time. Forensic context only — does not alter gate logic.

### winner_in_velo_frame
True if the actual winner was any of velo_top4. Tracks whether VÉLØ had the winner in view even when it didn't win the pick.

### miss_classification / failure_class
From VFU failure taxonomy (see `VELO_FORENSICS_UNIT_FAILURE_TAXONOMY_V1.md`).

### passport_update_candidate
True when the race contains evidence that should update the horse's current-state profile — improvement trajectory, setup learning, reliability note, etc.

### pattern_update_candidate
True when the race contains evidence that Pattern Prosecutor should review across the full universe.

### human_review_required
True for unusual outcomes: SP anomalies, identity questions, source degraded, repeat failure on same horse, very high VP with catastrophic miss.

---

## Storage

Phase 1: `data/reports/vfu_autopsies/` (JSONL, one file per race date)  
Phase 2+: Operator decision on Supabase `vfu_race_autopsies` table.

---

## Autopsy is READ-ONLY of source data

The autopsy process reads:
- sigma result rows
- VÉLØ verdict files
- rp_results JSON files
- Horse Passport (to check prior contact)

The autopsy process does NOT write:
- Supabase
- Sigma rows
- Live scoring files
- Model weights

In Phase 2 (dry-run), autopsy output writes only to `data/reports/vfu_autopsies/` local files.
