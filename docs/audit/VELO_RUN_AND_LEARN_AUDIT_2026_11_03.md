# Velo Run-and-Learn Audit — 2026-11-03

## Executive finding

Velo's primary constraint is not lack of models or lack of race volume. It is failure to
close predictions to canonical outcomes consistently, combined with contradictory gate
language that confuses *running*, *learning*, and *promotion*.

The safe simplification is:

1. **RUN every published UK/IRE race day.** Availability faults retry; optional sidecars
   may degrade; identity/source failures stop only the affected truth-dependent stage.
2. **SETTLE every completed race day.** Results identity and completeness remain hard
   gates because false labels poison every downstream experiment.
3. **LEARN in shadow from every truthfully settled day.** Poor performance and Council
   `WATCH_ONLY` are evidence, not integrity failures.
4. **PROMOTE nothing automatically.** Promotion retains chronological holdout, sample,
   leakage, calibration, and operator gates.

This removes operational paralysis without weakening result truth.

## Evidence audit

### Closure is the binding constraint

`scripts/audit/learning_loop_closure_audit.py`, run on 2026-11-03, reported:

- 6,942 Velo verdicts.
- The legacy-only audit initially found 1,038 verdicts joined to `runner_results` and
  5,904 without that obsolete join.
- After correcting the audit to use canonical `racing_horse_runs` plus legacy
  `runner_results`, 5,384 verdict races have outcomes and 1,558 remain unresolved.
- The corrected daily audit reports 120 closed days, 27 partial days, and 39 broken
  days across the audit universe.
- 76 local result files containing 3,236 races with positions.
- 5,302 Sigma rows.

The simultaneous presence of 3,236 locally settled races and only 1,038 legacy
verdict/result joins proved that the audit was reading the wrong modern result authority.
The canonical-source correction recovered 4,346 additional closed verdict races without
inventing outcomes. The remaining 1,558 unresolved rows still require identity/date
classification. Training directly
from the `runner_results` join therefore selects a non-random subset.

### Existing gate law contradicts itself

`docs/current/RACE_DAY_RUNBOOK.md` still says:

- degraded source evidence requires operator acknowledgement; and
- `WATCH_ONLY` means learning does not run.

`docs/current/ONE_TRUTH.md` contains the later operator ruling that:

- degraded performance days continue learning; and
- Council `WATCH_ONLY` blocks learning only for data-integrity reasons, not low strike
  rate.

Because One Truth wins, the runbook text is stale. The contradiction encourages false
stops and inconsistent automation.

### Repository/runtime sprawl is operational debt

The repository contains current orchestrators alongside retired source paths, dated
recovery scripts, overlapping audits, multiple `latest` artifacts, and legacy dashboard
consumers. The existing `SIMPLIFICATION_AUDIT.md` already identifies this, but most items
remain present. A rule may be valid while its evidence consumer is stale; the 3 November
dashboard is a live example (canonical New Build rows exist while the legacy panel reports
`MISSING`).

## Offline research performed

The existing constrained AutoResearch shadow board was run over every record it could
load from 2026-04-29 through 2026-11-01. It found 893 settled top-pick records:

| Shadow policy | n | Win SR | Frame rate | Flat win ROI |
|---|---:|---:|---:|---:|
| Baseline | 893 | 27.32% | 56.77% | -5.62% |
| Tier A only | 191 | 42.41% | 71.20% | +21.82% |
| VP30 base only | 291 | 38.49% | 68.04% | +14.84% |
| Tier A, VP>=0.30, exclude odds-on | 132 | 32.58% | 62.12% | +35.55% |
| VP30 base, exclude odds-on | 222 | 30.63% | 61.26% | +21.11% |

These are discovery results, **not promotion evidence**. A strict forward check from
2026-09-01 through 2026-11-01 returned zero records through this loader, despite canonical
Supabase scorecards existing in that period. That is a pipeline defect and prevents an
honest temporal validation of the apparent positive policies.

A second validation was therefore run directly against canonical Supabase rows, using
2026-05-27 to 2026-09-13 as discovery and 2026-09-15 to 2026-11-01 as forward evidence.
It rejected the local-loader profit story:

| Policy | Discovery n / ROI | Forward n / ROI |
|---|---:|---:|
| Main Velo baseline | 1,606 / -12.36% | 1,013 / -5.70% |
| VP>=0.30 | 1,144 / -8.92% | 719 / -9.66% |
| VP>=0.40 | 730 / -7.91% | 418 / -15.13% |
| VP>=0.30, exclude odds-on | 931 / -9.27% | 588 / -11.45% |
| VP>=0.40, exclude odds-on | 551 / -9.34% | 318 / -19.03% |

The apparent positive ROI in the 893-row local corpus is selection/corpus bias and must
not be used as a policy claim.

### Canonical model evidence

Read-only Supabase aggregation of rank-1 rows with settled positions found:

- Main Velo Prime: n=2,619, win SR 26.61%, frame 57.81%, flat win ROI -9.78%.
- Old Velo win role: n=1,803, win SR 25.62%, frame 57.02%, ROI -9.59%.
- MDS Heavy: n=819, win SR 26.25%, frame 58.49%, ROI -8.18%.
- Market-Blind Core: n=488, win SR 27.25%, frame 61.07%, ROI -8.87%.
- New Build A: n=2,435, win SR 18.23%, frame 47.84%, ROI -15.14%.
- Champion Intent: n=1,804, win SR 20.62%, frame 50.83%, ROI -17.84%.

No broad rank-1 model is profitable at settled SP across the full canonical sample. The
edge, if real, is conditional: tier, price band, course/surface, race shape, and model
agreement/disagreement.

## Out-of-the-box research direction

Stop asking one model to be best everywhere. Build a **chronological race-context router**
in shadow:

- The input is available before the off: course, surface, race type, field size, price
  band, pace/shape, and model disagreement.
- The candidates are existing frozen lanes; no weights are changed.
- Training chooses which existing lane, abstention, or frame-only policy is appropriate
  for a context.
- Evaluation uses expanding-window folds and same-race comparisons, never each model's
  unmatched historical universe.
- The router must beat both Main Velo and the market favourite on the exact same races,
  after minimum-sample and calibration checks.

Recent canonical data supplies promising hypotheses but not conclusions: Main Velo was
strong at Wolverhampton AW (26/71 wins, 36.6% SR, +11.2% settled-SP ROI), while MDS Heavy
led at Southwell AW (19/60, 31.7%, +10.8%). These must be retested on later, untouched
races before use.

### One-dissenter consensus hypothesis

On races from 2026-09-15 where Prime and all five comparison lanes were present, maximum
agreement was not the best commercial signal:

- Prime plus all five agreeing: n=43, 41.86% win SR, 81.40% frame, -19.05% ROI.
- Prime plus exactly four of five agreeing: n=29, 58.62% win SR, 72.41% frame,
  +66.21% ROI.

The exactly-one-dissenter hypothesis also survived a simple chronological split:

- 2026-09-15 to 2026-10-01: 6/11 wins, +74.09% ROI.
- 2026-10-02 to 2026-11-01: 11/18 wins, +61.39% ROI.

This is still a tiny, post-selected sample. It is not authorised for staking or model
promotion. It is, however, a sharper forward shadow hypothesis than a generic six-model
consensus: one independent disagreement may preserve price while four confirmations
retain predictive strength. Freeze its definition now and monitor the next 100 eligible
races without alteration.

## Gate classification

### Hard integrity gates — retain

- Authenticated RP source identity.
- Race/horse identity and date matching.
- Complete result settlement before supervised learning.
- Pre-off timestamp/provenance for evaluation prices and predictions.
- No live staking; PAPER/SIM guard.
- Leakage, chronological holdout, and promotion approval.

### Availability failures — retry/degrade, do not cancel the whole day

- Optional PDF/passport enrichment missing.
- FormFav optional feature families missing after core readiness is truthful.
- Dashboard publication failure after canonical persistence succeeds.
- Non-critical shadow/sidecar model failure.
- Council performance `WATCH_ONLY` where integrity is otherwise sound.

### Stale/duplicated checks — consolidate

- Legacy local artifact panels that contradict canonical Supabase rows.
- Multiple `latest` files used as authority for a requested historical date.
- Retired source-path checks after RP canonical capture has already passed.
- Rules that block scoring because a post-scoring visualization artifact is absent.

## Immediate work order

1. Make one date-level closure manifest the sole handoff from morning to EOD to learning.
2. Reconcile canonical scorecards, Sigma, `racing_horse_runs`, and `runner_results` into
   one outcome view without destructive backfill.
3. Repair the AutoResearch loader so September-November canonical rows are eligible for
   a real forward check.
4. Run the frozen-policy Tier-A/VP30 hypotheses on expanding chronological folds.
5. Build a same-race context-router research table; keep it shadow-only.
6. Update the stale runbook language only after tests demonstrate the intended gate
   separation.

## Remediation update — 2026-11-03

- Commit `375187ea` was fast-forwarded to `main`; CI, GX, CodeQL, and the governed
  safety perimeter passed; Railway built the repaired `velo-rp-capture` image.
- 2 November cannot be back-scored because no pre-race verdict was frozen. Its RP
  results were recaptured: 30 real races / 282 runners were persisted to
  `racing_horse_runs`; six Fakenham entries were verified as an abandoned meeting and
  are not missing results.
- AutoResearch now defaults to canonical settled scorecards and paginates the complete
  requested window instead of silently stopping at a selected local-file subset.
- The closure audit now treats `racing_horse_runs` as the modern authority and retains
  `runner_results` only as additive legacy evidence.
- `monitor_one_dissenter_cohort.py` freezes the hypothesis after 2026-11-03 and refuses
  in-sample starts. It is paper/shadow-only and has no promotion or staking path.
- The runbook and learning-admission contract now distinguish availability,
  integrity, shadow learning, and promotion states.

## Safety and mutation statement

No production model, live weight, execution mode, credential, or browser profile was
changed. The cloud orchestration fix and clarified gate documentation were deployed;
verified 2 November RP outcomes were upserted into the existing canonical horse-run
table. No historical predictions were fabricated, no model was promoted, and no bets
or messages were sent.
