# VÉLØ Plot Doctrine v1

**Status**: LOCKED
**Derived from**: 2025 intelligence stack analysis — 84,049 runs, five intelligence tables
**Date locked**: 2026-03-21
**Author**: VÉLØ Oracle Prime intelligence session

---

## The First Hard Law

> **A horse becomes a genuine candidate when the handicapper has moved the mark
> AND the trainer has restored the conditions.
> Either one alone is atmosphere. Both together is intent.**

This law was not invented. It was extracted from data.

---

## The Intelligence Stack

The doctrine is built on five read-only intelligence tables, in order:

| Layer | Table | What it answers |
|---|---|---|
| 1 — Identity | `horse_identity_resolution_2025` | Who is this horse? |
| 2 — Memory | `horse_run_history_2025` | What has it done this year? |
| 3 — Pressure | `handicap_trajectory_2025` | How has the handicapper treated it? |
| 4 — Restoration | `setup_restore_events_2025` | Has it been returned to a winning setup? |
| 5 — Intersection | `plot_candidate_flags_2025` | Where do pressure and restoration meet? |

Each layer is a necessary precondition for the next. You cannot assess restoration without memory. You cannot assess intent without both pressure and restoration together.

---

## Rule Hierarchy

### Rule 1 — Single-theme flags are not actionable

Flags that fire on a single theme describe **state**, not readiness:

| Dead alone | What it means | Why it's not enough |
|---|---|---|
| `mark_compressed` | Handicapper lowered the mark | Describes past event only |
| `post_drop` | First run after a mark drop | Describes timing, not conditions |
| `or_treadmill` | OR range ≤5 pts over 5+ runs | Describes campaign type, not readiness |
| `reactivation` | Back from ≥28 days off to known conditions | Incomplete without mark context |
| `full_restore_live` alone | Exact trip/course match | Incomplete without handicap movement |

Proven by data: `mark_compressed + post_drop + or_treadmill` fires on 886 rows with **0% manual_review_priority**. Single-theme chains are noise at scale.

---

### Rule 2 — Handicap-only combinations are state, not signal

Any combination built exclusively from handicap flags (mark_compressed, post_drop, or_treadmill, or_plateau) has **zero signal value** regardless of how many flags are stacked.

These tell you the handicapper has acted. They do not tell you the trainer has responded.

---

### Rule 3 — Restore-only combinations are incomplete unless context supports them

`full_restore_live` alone = 906 rows, 0% MR on turf.
`trip_restore` alone = 1,005 rows, 0% MR.

Restore flags without handicap context only say: "the horse is back at conditions where it won." They do not say the mark has created an opportunity.

**Exception**: On AW and HK circuits, restore-only combinations carry more structural weight because circuit geometry repeats reliably. Still not sufficient alone, but the prior probability is higher.

---

### Rule 4 — Signal begins at the intersection of handicap movement and condition restoration

The minimum viable signal is: **one handicap theme + one restore theme**.

Proven: every 2-code combination crossing these two theme types = **100% manual_review_priority** with no exceptions across 4,631 candidate rows.

| Intersection combo | Count | MR% |
|---|---|---|
| `reactivation + trip_restore` | 577 | 100% |
| `full_restore_live + reactivation` | 541 | 100% |
| `mark_restore + mark_compressed` | 163 | 100% |
| `post_drop_restore + full_restore_live` | 95 | 100% |

The pattern is absolute. The intersection is the law.

---

### Rule 5 — Highest-quality candidates are 3+ codes, high-confidence, near last winning OR

The **working candidate archetype**:

```
identity_confidence = 'high'
manual_review_priority = TRUE
ARRAY_LENGTH(plot_reason_codes, 1) >= 3
current_vs_last_winning_or BETWEEN -8 AND 5
```

This produces **1,530 rows** (1.8% of the full 84,049 dataset) — the serious intelligence queue.

The strongest structural fingerprint found in the data:

```
avg_or_change:       -1.0 to -2.0   (mark still being compressed or just bounced)
avg_vs_win_or:        0.0 to  3.0   (within striking range of last winning mark)
identity_confidence: 'high'         (clean entity, no trainer ambiguity)
restore flags:        trip or full   (exact conditions match)
```

This is not a model. It is a structured description of a horse in a specific campaign phase.

---

### Rule 6 — AW and HK restore patterns are structurally stronger than turf reactivation alone

**AW / HK — why restore logic is reliable:**
- Circuit geometry repeats (same oval, same straights, same trip options)
- Surfaces are fixed (no going variation on AW)
- Trip matching is precise (5f at Wolves AW = 5f at Wolves AW, always)
- Trainer familiarity with track is established

On AW, `full_restore_live + reactivation` converts at **100% MR** — the most reliable 2-theme combination in the dataset.

**Turf — why reactivation alone is weak:**
- `reactivation` alone on turf: 51% MR (noise floor)
- Turf going varies: "Good" ≠ "Good to Soft" ≠ "Soft"
- Course trips vary: Ascot 1m can be run on different tracks
- Reactivation without mark context is just "horse returned after a break"

**On turf, require a second theme**:
- `reactivation + restore` = 100% MR ✓
- `reactivation + mark pressure` = 100% MR ✓
- `reactivation` alone = incomplete

---

### Rule 7 — Dossier horses are strategic assets — they reveal stable playbooks

A horse with 20+ manual_review_priority appearances across a season is not just a candidate.
It is a **case study** in how its trainer operates.

**Identified archetypes (2025 evidence):**

| Archetype | Signature | Example |
|---|---|---|
| **Treadmill horse** | OR band ≤5pts all year, multiple wins at compressed marks | Red Walls (GB) |
| **Drop-and-strike** | Wins only off dropped marks, not off raised marks | Muscika (GB) |
| **Repeat-restore** | Trainer systematically returns to same circuit/trip | Heavenly Fire (GB) |
| **Campaign-shift** | Trainer finds a new winning circuit mid-season, campaigns it hard | River Wharfe (GB) |
| **Multi-signal active** | Multiple flag types active simultaneously, full doctrine convergence | Bantz (IRE) |

These archetypes are teachable. Once identified, the trainer's operational logic becomes partially predictable.

---

## The Candidate Tiers

```
TIER 0  — Background
  plot_pressure_flag = TRUE, single theme
  32,057 rows — atmosphere, not signal

TIER 1  — Signal starts
  Two themes intersecting (handicap + restore)
  ~4,631 manual_review_priority rows — meaningful queue

TIER 2  — Working candidates
  High confidence + MR + 3+ codes
  1,530 rows — serious intelligence book

TIER 3  — Dossier material
  4+ codes + near last winning OR + ongoing compression
  ~200-400 rows per year — highest-quality individual cases
```

---

## Track Archetype Reference

| Track type | Signal strength | Notes |
|---|---|---|
| AW GB (Wolves, Newcastle, Southwell, Kempton, Lingfield, Chelmsford) | Strongest restore | Geometry fixed, trips precise |
| HK (Sha Tin, Happy Valley) | Strongest restore | Fixed oval, limited trip options |
| Turf GB (Ascot, York, Doncaster, Haydock) | Reactivation dominant | Needs second theme |
| Turf IRE (Curragh, Leopardstown, Punchestown) | Mixed | Course restore valid, going varies |
| France (Chantilly, Longchamp, Deauville) | Pure reactivation | AW at Deauville valid for restore |

---

## What This Is Not

- This is **not a prediction model**. It is a candidate identification system.
- These flags do not say a horse will win. They say the conditions are structurally aligned in a way that matches prior winning campaigns.
- The output is a **review queue**, not a verdict.
- The step from candidate flag to betting verdict requires the full live pipeline (SQPE, VeloPrime, sigma, market context).

---

## Versioning

This is Doctrine v1, derived exclusively from 2025 data.
When 2026 data is available, the flag definitions and thresholds should be re-validated against the new dataset before the doctrine is carried forward.

The law itself — *handicap movement + condition restoration = intent* — is expected to hold.
The specific thresholds (e.g., -8 to +5 OR range for mark_restore) are 2025-calibrated and may shift.
