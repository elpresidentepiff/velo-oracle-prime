# VFU Failure Taxonomy V1

**Status**: ACTIVE
**Created**: 2026-06-14
**Owner**: VÉLØ Forensics Unit

Every Race Autopsy must carry at least one failure class when outcome is MISS.
WIN autopsies carry failure_class = null. PLACED autopsies may carry a failure class.

---

## Primary Failure Classes

### VP Signal Failures

| Code | Meaning |
|---|---|
| `VP_FALSE_POSITIVE` | High VP, MISS result. Model overconfident. |
| `VP_FALSE_NEGATIVE` | Low VP, horse won or placed. Model undervalued this horse. |

### Frame Failures

| Code | Meaning |
|---|---|
| `WINNER_OUTSIDE_FRAME` | Actual winner was not in VÉLØ top3/top4. Completely missed. |
| `WINNER_INSIDE_FRAME_BUT_WRONG_TOP_PICK` | Winner was in frame but ranked 2nd-4th. Correct intelligence, wrong priority. |

### Course Failures

| Code | Meaning |
|---|---|
| `COURSE_DRAIN_CONFIRMED` | Race run at a DRAIN course. Loss consistent with course intelligence. |
| `COURSE_STRENGTH_CONFIRMED` | Win at an EXCELLING course. VP signal confirmed by course intelligence. |

### Odds / Price Failures

| Code | Meaning |
|---|---|
| `SP_DEAD_ZONE_FAILURE` | MISS where pick was SP 6.0+. Dead-zone confirmed. |
| `MID_PRICE_WALL` | MISS where winner was SP 3.0-8.5. The most common miss class in VÉLØ history. |
| `FAVOURITE_TRAP` | VÉLØ followed the market favourite who lost. |

### Intent / Trap Failures

| Code | Meaning |
|---|---|
| `INTENT_OVERRIDE_MISSED` | Horse or connections showed intent signals VÉLØ did not read. |
| `TRAP_LEAD_PATTERN_MISSED` | Horse was a trap leader — set to lose, win went elsewhere. |

### Setup Failures

| Code | Meaning |
|---|---|
| `SETUP_MISREAD` | Horse needed specific conditions (going/trip/surface) that were not present. VÉLØ scored regardless. |
| `TRIP_SURFACE_MISMATCH` | Distance or surface was wrong for this horse's profile. |
| `PACE_SETUP_WRONG` | Pace dynamics were wrong for this horse's running style. |
| `LONGSHOT_RELEASE_MISSED` | Horse was a compressed market release at a long SP — VÉLØ did not detect the signal. |

### Market Failures

| Code | Meaning |
|---|---|
| `MARKET_SIGNAL_IGNORED` | Market moved significantly but VÉLØ scoring did not reflect it. |

### Horse Profile Failures

| Code | Meaning |
|---|---|
| `HORSE_PROFILE_OUTDATED` | Passport profile was stale or based on old form patterns no longer relevant. |
| `REPEAT_HORSE_MEMORY_MISSED` | VÉLØ has missed this horse in the same way before. Repeating failure. |
| `HORSE_IDENTITY_MISMATCH` | Horse name / ID reconciliation error in sigma or verdict file. |

### Data / Source Failures

| Code | Meaning |
|---|---|
| `DATA_MISSING` | Key field (SP, OR, going, form) was absent at scoring time. |
| `SOURCE_DEGRADED` | Source quality was PARTIAL or FAILED — scoring was incomplete. |
| `RESULT_RECONCILIATION_ERROR` | Sigma result did not reconcile with official result cleanly. |

---

## Secondary Failure Classes

Any miss may carry a `secondary_failure_class` from the same taxonomy when two failure classes apply.

Example: A SP_DEAD_ZONE_FAILURE may also be a REPEAT_HORSE_MEMORY_MISSED if this horse has repeatedly won at long SP against VÉLØ picks.

---

## Failure Class Hierarchy

Not all failures are equal. Priority for investigation:

1. `REPEAT_HORSE_MEMORY_MISSED` — immediate passport update candidate
2. `WINNER_OUTSIDE_FRAME` — full miss, highest severity
3. `VP_FALSE_POSITIVE` with high VP (>=0.50) — signal integrity question
4. `INTENT_OVERRIDE_MISSED` + `TRAP_LEAD_PATTERN_MISSED` — doctrine question
5. `MID_PRICE_WALL` — known systemic miss, track for Pattern Prosecutor
6. All others — pattern accumulation

---

## Failure Class → Action Map

| Failure Class | passport_update_candidate | pattern_update_candidate | human_review_required |
|---|---|---|---|
| REPEAT_HORSE_MEMORY_MISSED | TRUE | TRUE | TRUE |
| VP_FALSE_POSITIVE (VP>=0.50) | TRUE | TRUE | TRUE |
| WINNER_OUTSIDE_FRAME | FALSE | TRUE | FALSE |
| INTENT_OVERRIDE_MISSED | TRUE | TRUE | TRUE |
| TRAP_LEAD_PATTERN_MISSED | TRUE | TRUE | TRUE |
| SETUP_MISREAD | TRUE | FALSE | FALSE |
| HORSE_PROFILE_OUTDATED | TRUE | FALSE | FALSE |
| MID_PRICE_WALL | FALSE | TRUE | FALSE |
| SP_DEAD_ZONE_FAILURE | FALSE | TRUE | FALSE |
| COURSE_DRAIN_CONFIRMED | FALSE | TRUE | FALSE |
| SOURCE_DEGRADED | FALSE | FALSE | FALSE |
| All others | FALSE | FALSE | FALSE |
