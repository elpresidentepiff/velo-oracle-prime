# Velo World — One Truth

**Status:** PAPER/SHADOW only. UK/IRE remains a separate governed system.

## Durable evidence spine

World scorecards are isolated from UK/Irish canonical scorecards in
`world_model_scorecards`. Only the first complete scorecard generated before a
race's scheduled off is retained. Provider predictions, ranks, probabilities,
confidence and tips are excluded from Velo inputs. Raw results remain retained
even when identity or finality blocks learning; a blocked row must never be
relabeled as eligible evidence.

## Provider boundary

FormFav supplies cards, runner form/statistics, scratchings, captured prices and
results. Its prediction ranks, probabilities, confidence and model opinion are
not Velo World inputs. They remain an isolated benchmark used only after Velo's
own timestamped scorecard is frozen.

## Data retention law

Every observed card, runner payload, market snapshot and result is retained even
when an integrity or learning gate fails. A failed gate blocks consumption; it
does not delete evidence. Provisional results remain stored and visible but are
ineligible for learning until the provider marks them final.

## Jurisdictions

WORLD excludes GB and IE. Initial lanes are AU, CA, FR, HK, JP and US. Evidence,
calibration, Sigma and learning status are reported per jurisdiction and are
never blended into UK learning or UK model weights.

## Operational sequence

1. The 24/7 FormFav worker stores provider data in Supabase.
2. Velo World reads the stored data cache and freezes its own shadow scorecard.
3. Provider results are stored regardless of gate status.
4. World Sigma reconciles Velo's frozen selections independently from the
   separate FormFav benchmark.
5. Final identity-grade rows enter the world learning ledger. Provisional,
   unmatched and timestamp-invalid rows are retained with an ineligible reason.
6. No world evidence changes model weights without jurisdiction-specific forward
   validation, Council review and explicit approval.

## Freeze completeness

"First complete" means complete with its price provenance, not merely first. Every frozen row
carries `price_state` (`REAL` or `MISSING`), the quote's capture time, the race's freeze state and
the deployed commit in `feature_payload`. `captured_price` is NULL unless a dated, pre-off market
price existed. The scorer's `sp_dec = 10.0` default for a runner with no price is a model input,
never a market price, and is never stored as one. A price with no capture time is not a price.

A race whose country has a live price feed but no price yet is not frozen (`AWAITING_PRICES`) until
only one hourly run remains before the off; it then freezes as `PARTIAL_MARKET` or `NO_MARKET`.
Countries with no price feed freeze `NO_MARKET` at first sight. A tie for rank 1 is recorded
(`top_tie_size`); a tied top pick is not a skill sample. Rows frozen before 2026-11-05 predate
this: they are retained, never edited, and reported `PRICE_BLIND`.

## Settlement

World Sigma (`scripts/ops/run_world_sigma.py`, logic in `src/velo/world_sigma.py`) grades Velo's
own frozen rank-1 pick against `formfav_results`. It is not `formfav_global_eod`, which grades
FormFav's predictions. It writes `world_sigma_audits`, `world_learning_events` and
`world_pipeline_runs` only, runs after every hourly freeze, and is a dry run unless `--execute`.

* Matching is by race key and normalised horse name. A pick that is not in the result, or whose
  name matches twice, is `identity_blocked`: never counted as a miss.
* A scratched pick is a void stake, not a loss. A dead heat divides the return.
* Profit is computed only from a `REAL` price. Otherwise it is NULL, never a guess.
* A row is learning-eligible only with a final result, an identity grade above D, a real price,
  no tie for rank 1, a pre-off freeze and no provider opinion consumed. Today every row is blocked
  by identity grade D, which is the law above, and the reason is recorded.
* A final result is never downgraded. A blocked row is never relabelled eligible. A changed
  final result gets a new retained event; the old one stays.

## Aftercare

The living status register is two read-only views, `world_status_register` (day x country) and
`world_status_summary` (one row), which hold the deployed commit, last complete world date,
coverage by country, unresolved results and learning admission counts. The next safe action, and
what each agent changed and left open, are written in `docs/current/DIARY.md`; every session
appends an entry before it stops. Branch recovery is performed before deletion; long-lived
branches are limited to `main`, `research/evo2-challenger-lab`, and one temporary
`ops/recovery` integration branch.
