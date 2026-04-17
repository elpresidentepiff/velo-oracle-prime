# RPD-C DERIVATION MAP — 2025 & 2024
**Date:** 2026-03-21 | **Classification:** INTERNAL | **Prepared by:** VÉLØ VOX

---

## ENGINE: rpdc_rules.py

Deterministic. No LLM. No SQLite. All inputs from 5-layer intelligence stack.

---

## T — TARGET

**Definition:** Horse is being specifically deployed for this race. Stable intent is visible in the data.

| Input | Source Table | Threshold |
|---|---|---|
| `manual_review_priority` | `plot_candidate_flags` | ≥ 1 |
| `plot_pressure_flag` | `plot_candidate_flags` | TRUE |
| `plot_reason_codes` | `plot_candidate_flags` | ≥ 3 codes |
| `full_restore_live` | `plot_candidate_flags` | TRUE (strongest signal) |
| `compression_plus_restore` | `plot_candidate_flags` | TRUE (strong signal) |
| `post_drop_restore` | `plot_candidate_flags` | TRUE (moderate signal) |
| `identity_confidence` | `plot_candidate_flags` | = 'high' (required) |
| `career_peak_or_to_date` | `handicap_trajectory` | context — class validation |
| `trip_restore_flag` | `setup_restore_events` | TRUE — elevates evidence |
| `course_restore_flag` | `setup_restore_events` | TRUE — elevates evidence |

**Confidence logic:**
- `high`: `full_restore_live = TRUE` OR (`plot_reason_codes ≥ 4` AND identity = high)
- `medium`: `plot_reason_codes = 3` AND identity = high
- `low`: Never assigned to T (requires ≥ 2 evidence codes for T minimum)

**Blockers (prevent T):**
- Identity confidence ≠ high → S instead
- No plot pressure flag → degrades to H
- P or E evidence present and stronger

**Historical limitation:**
- Jockey quality (first-choice / top-tier) is live-only. Historical T tags cannot use jockey tier.
- This means some historical T-quality runs may be classified H or S.

---

## H — HONEST

**Definition:** Runs to its rating. No strong signal either way. The default for consistent, unremarkable profiles.

| Input | Source Table | Role |
|---|---|---|
| `plot_pressure_flag` | `plot_candidate_flags` | if TRUE → medium confidence |
| `manual_review_priority` | `plot_candidate_flags` | if ≥ 1 → medium |
| `mark_restore_candidate` | `plot_candidate_flags` | if TRUE → medium |
| `identity_confidence` | `plot_candidate_flags` | if = high → medium floor |

**Confidence logic:**
- `medium`: Any single positive signal (pressure, MR, restore candidate)
- `low`: All signals absent

**Blockers (prevent H):**
- Any `plot_reason_code` active → escalates to S
- Any restore signal (`full_restore_live`, `compression_plus_restore`) → escalates to T or S
- Long layoff (60+ days) → escalates to P

---

## S — SPECULATIVE

**Definition:** Insufficient data for clean classification. First-time conditions, no win reference, identity uncertainty.

| Input | Source Table | Evidence Code |
|---|---|---|
| `or_treadmill_flag = TRUE` AND no restore | `plot_candidate_flags` | `treadmill_no_restore` |
| `layoff_flag = TRUE` AND no restore | `plot_candidate_flags` | `layoff_no_restore` |
| `current_vs_last_winning_or` null/missing | `plot_candidate_flags` | `no_winning_reference` |
| `identity_confidence ≠ high` | `plot_candidate_flags` | `ambiguous_identity` |
| `ambiguity_flag = TRUE` | `plot_candidate_flags` | `ambiguous_long_absent` |

**Confidence logic:**
- `medium`: Restore signal present but insufficient for T (1 restore code, identity medium)
- `low`: No restore signals at all, no winning reference

**Blockers (prevent S):**
- Strong restore signal → T classification
- Plot pressure flag without restore → H

**Note on S dominance:**
- 2025: 67.7% classified S. Expected. Most runners in any season lack a within-year win reference.
- 2024: 60.3% classified S. Slightly lower — full-year data gives more horses a win reference.
- S does not mean bad. It means: unknown quality relative to today's conditions.

---

## P — PREP

**Definition:** Long absence, no restore signals, below-standard connections. Horse is likely being readied, not deployed.

| Input | Source Table | Threshold |
|---|---|---|
| `days_since_last_run` | `plot_candidate_flags` | ≥ 60 days |
| `long_layoff_flag` | `plot_candidate_flags` | TRUE |
| `layoff_flag` | `plot_candidate_flags` | TRUE |
| `or_rating_num` | `plot_candidate_flags` | context — class appropriateness |
| `no restore signals` | all | none of: full_restore, compression, post_drop, reactivation |

**Confidence logic:**
- `high`: `long_layoff_flag = TRUE` AND no restore AND no plot pressure
- `medium`: `layoff_flag = TRUE` AND no restore signals

**Blockers (prevent P, override to H or T):**
- Any restore signal present (horse returning WITH a plan)
- Market shortening (stable knows → not a passive prep)
- `full_restore_live = TRUE`

---

## E — EXHAUSTED

**Definition:** Horse is past its competitive peak or in physiological decline. Evidence-based, not narrative.

| Input | Source Table | Threshold |
|---|---|---|
| `is_win` | `horse_run_history` | FALSE across last 10+ runs |
| `current_vs_peak_or` | `handicap_trajectory` | OR > career peak (regressive) |
| `or_change` | `handicap_trajectory` | negative trend |
| `or_treadmill_flag` | `plot_candidate_flags` | TRUE |
| `plot_pressure_flag` | `plot_candidate_flags` | FALSE (no stable intent) |

**Confidence logic:**
- `high`: All three (losing streak + OR above peak + negative trajectory)
- `medium`: Two of three conditions
- `low`: Only one condition (weak evidence — default to H or S)

**Blockers (prevent E — strong override):**
- Won last time out → immediate disqualification from E
- Market shortening → horse is live, not exhausted
- Any restore signal → recategorise

**Note on E rarity:**
- 2025: 42 rows (0.1%). 2024: 180 rows (0.1%).
- Intentionally low. E requires physiological evidence, not narrative convenience. Most "seemingly exhausted" horses classify to S instead.

---

## LIVE-RACE-ONLY DATA (not available historically)

| Field | Use | Impact |
|---|---|---|
| Jockey tier (top/standard/below) | T confidence, P evidence | Historical T tags may be under-counted |
| Market movement (drift/shorten) | P/E blockers | Historical P/E may be over-counted |
| Same-day headgear change | T/false-favourite signals | Not retrospectively recoverable |
| Draw bias (live card) | Pace shape context | Not applicable to historical tagging |

These fields improve live accuracy. They do not invalidate historical backfill — they are contextual, not structural.
