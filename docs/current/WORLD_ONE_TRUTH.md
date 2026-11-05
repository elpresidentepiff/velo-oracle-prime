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

## Aftercare

One living status register must record the current deployed commit, last complete
world date, coverage by country, unresolved results, learning admission counts
and next safe action. Branch recovery is performed before deletion; long-lived
branches are limited to `main`, `research/evo2-challenger-lab`, and one temporary
`ops/recovery` integration branch.
