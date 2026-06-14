# Horse Passport Forensic Extension V1

**Status**: SCHEMA ONLY — no passport mutation in Phase 1
**Created**: 2026-06-14
**Owner**: VÉLØ Forensics Unit

---

## Purpose

The Horse Passport (`new_build_velo/horse_passport.py`) is the canonical life file for each horse.

This document defines the forensic extension — the additional fields VFU writes into the Passport after autopsy. The base Passport handles career form, SP history, and rolling performance metrics. The forensic extension adds VÉLØ-specific intelligence: what the system thought, where it was right, where it was wrong, and what the horse is becoming in VÉLØ's eyes.

The forensic extension does NOT replace the base Passport. It lives alongside it.

---

## Canonical Passport Path

```
data/new_build/passports/horse_passports_v1.jsonl   ← base passport (existing)
data/reports/vfu_passport_extensions/               ← forensic extension (Phase 2+)
```

In Phase 4+, forensic extensions are merged into the main passport file. Not before.

---

## Forensic Extension Schema

```json
{
  "horse_id":           "integer — rp_uid",
  "horse_name":         "string",
  "normalized_name":    "string",

  "velo_appearances": [
    {
      "race_date":        "YYYY-MM-DD",
      "race_id":          "string",
      "course":           "string",
      "off_time":         "HH:MM",
      "race_type":        "string",
      "going":            "string",
      "distance_f":       "float",
      "field_size":       "integer",
      "vp_score":         "float",
      "pick_sp":          "float or null",
      "pick_rank":        "integer — 1 = top pick",
      "actual_finish":    "integer or null",
      "outcome":          "WIN | PLACED | MISS",
      "vp_gate_label":    "GREEN | AMBER | RED",
      "failure_class":    "string or null",
      "autopsy_id":       "string — link to race autopsy"
    }
  ],

  "velo_summary": {
    "total_appearances":    "integer",
    "as_top_pick":          "integer",
    "wins_as_top_pick":     "integer",
    "placed_as_top_pick":   "integer",
    "miss_as_top_pick":     "integer",
    "in_frame_count":       "integer — appeared in top3/top4",
    "win_sr_as_top_pick":   "float",
    "avg_vp_all":           "float",
    "avg_vp_wins":          "float or null",
    "avg_vp_misses":        "float or null",
    "avg_pick_sp":          "float or null"
  },

  "velo_right_wrong_history": [
    {
      "race_date":        "YYYY-MM-DD",
      "verdict":          "RIGHT | WRONG | PARTIAL",
      "vp_score":         "float",
      "failure_class":    "string or null",
      "note":             "string or null"
    }
  ],

  "missed_winner_history": [
    {
      "race_date":        "YYYY-MM-DD",
      "race_id":          "string",
      "velo_top_pick":    "string",
      "actual_winner":    "string — this horse",
      "actual_winner_sp": "float",
      "velo_vp_of_winner":"float or null",
      "failure_class":    "string"
    }
  ],

  "setup_profile": {
    "best_course":          ["string"],
    "worst_course":         ["string"],
    "best_going":           ["string"],
    "worst_going":          ["string"],
    "best_distance_band":   "string or null",
    "best_class_band":      "string or null",
    "jockey_continuity":    "boolean or null",
    "notes":                ["string"]
  },

  "current_state": {
    "label":            "string — from current-state label taxonomy",
    "confidence":       "LOW | MEDIUM | HIGH",
    "evidence_count":   "integer",
    "last_updated":     "YYYY-MM-DD",
    "notes":            ["string"]
  },

  "progression_label":  "IMPROVING | PLATEAUING | DECLINING | UNKNOWN",
  "reliability_label":  "RELIABLE | INCONSISTENT | UNRELIABLE | UNKNOWN",

  "trap_intent_labels": ["string — from intent/trap taxonomy"],

  "next_time_note":     "string or null — what VÉLØ should remember",
  "upgrade_flag":       "boolean — horse is improving beyond official rating",
  "downgrade_flag":     "boolean — horse is declining or exposed",

  "provenance":         "VFU_FORENSIC_EXTENSION_V1",
  "last_updated":       "ISO8601 UTC timestamp",
  "autopsy_count":      "integer — number of autopsies contributing to this profile"
}
```

---

## Current-State Labels

| Label | Meaning |
|---|---|
| `IMPROVING` | Recent runs show upward trajectory — form, SP, or VP signal improving |
| `DECLINING` | Form deteriorating, OR/TS falling, consistent misses |
| `EXPOSED` | Thoroughly handicapped, opponents have full read on this horse |
| `HIDDEN` | Unexposed profile — limited runs, unknown ceiling |
| `SETUP_DEPENDENT` | Only performs when specific conditions align |
| `COURSE_DEPENDENT` | Strong positive or negative course pattern |
| `TRIP_DEPENDENT` | Distance sensitivity confirmed in evidence |
| `SURFACE_DEPENDENT` | Turf/AW performance split confirmed |
| `MARKET_DEPENDENT` | Only fires when well-backed — intent signal |
| `UNRELIABLE` | Inconsistent, no repeatable setup pattern |
| `READY_NEXT_TIME` | Setup run confirmed — expected next-time bounce |
| `TRAP_LEAD_CANDIDATE` | Suspected of being set up to lose / trap lead indicator |
| `INTENT_ANOMALY` | Jockey/trainer combination shows suspicious pattern |
| `NEEDS_REVIEW` | Multiple conflicting signals — human review required |

---

## Phase Rules

- **Phase 1**: Schema only. No passport mutations.
- **Phase 2**: Forensic extension dry-run on 20 current-era races. Local files only.
- **Phase 3**: Extension dry-run for horses appearing 2+ times. Merge logic tested.
- **Phase 4**: Full current-era 1,263-row extension pass. Operator approval required before write.
- **Phase 5+**: Passport merge and live wiring. Operator decision only.
