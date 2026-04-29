# VELO Telegram Signal Visibility Audit V1

Generated: 2026-04-29 01:25 UTC

## Verdict

Current Telegram output does **not** surface the candidate-lane badges.
The live sender shows Tier and MDS, but VP is not consistently rendered and
VP30_TIER_A / MDS_HIGH / IMPROVE_HIGH / PLACE_HIGH / B_LOW_VP / MID_PRICE_FORENSICS
are all absent from the operator-facing message.

## Yes / No Matrix

| Check | Answer | Note |
|---|---|---|
| does current telegram output show vp | NO | The live governed A/B card does not print a dedicated VP line. Only the C-WATCH grouped list prints 'prob', so VP is not consistently surfaced to the operator. |
| does current telegram output show tier | YES | Tier is explicitly rendered in the governed card and also implied by the A/B/C/D/X bucketed Telegram flow. |
| does current telegram output show vp30 tier a badge | NO | The live Telegram sender never computes or renders the VP30_TIER_A badge. |
| does current telegram output show mds high badge | NO | The live card prints a numeric MDS value but does not promote it to the MDS_HIGH lane badge. |
| does current telegram output show improve high badge | NO | Improvement score is present in the verdict payload but is not rendered in the current Telegram message. |
| does current telegram output show place prob high badge | NO | Place probability appears only in the C-WATCH grouped list and is never surfaced as the PLACE_PROB_HIGH badge. |
| does current telegram output show b low vp suppress warning | NO | No suppress-zone warning exists in the live day-of Telegram formatter. |
| does current telegram output show mid price forensics warning | NO | The live formatter does not mention mid-price miss forensics or danger-zone warnings. |

## Live Sender

- Script: `scripts/run_prime_today.py`
- Formatter: `build_governed_card() for A/B governed cards, plus inline formatters for C-WATCH and D/X summaries.`

## Formatter Fields Currently Rendered

- `horse`
- `tier`
- `confidence_level`
- `prob_gap` (derived from `velo_prime_prob`)
- `market_deception_score`
- `assigned_product`
- `execution_allowed`
- `reasons`

## Fields Available But Not Surfaced

- `velo_prime_prob`
- `improvement_score`
- `place_prob`
- `g_shadow_multiplier`
- `horse_state`
- `candidate_execution_allowed`
- `race_archetype`
- `cash_run_flag`
- `setup_run_flag`
- `doctrines_fired`

## Missing Code Path

A display-only patch is required in `scripts/run_prime_today.py`.
The missing path is the lack of any signal-stack render call inside the live day-of Telegram flow.

Patch shape:
- compute lane badges from existing top-pick fields only
- append shadow evidence lines (n / SR / frame / status)
- do not change ranking, routing, candidate execution, or staking

## Proof References

- `build_governed_card`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:623`
- `tier_line`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:648`
- `mds_line`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:651`
- `prob_gap_line`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:650`
- `c_watch_prob`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:1426`
- `step5_live_sender`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:1311`
- `a_bucket_sender`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:1393`
- `b_bucket_sender`: `C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py:1406`
