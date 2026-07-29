# VFU-22 — False-GREEN Feature Autopsy

**Former ID:** VFU-13 (retired 2026-07-06 by operator ruling — never reuse that number)
**Status:** DRY_RUN / REPORT_ONLY. No live scoring change, no Supabase write, no Telegram send, no model promotion, no VP Gatekeeper criteria change.
**Evidence base:** `data/sigma_results/sigma_results_*.json` — 31 dates on disk in this worktree, 2026-05-23 to 2026-06-30 (not full system history; see Limitations).

## 1. What "false green" means here

Per `docs/current/VP_GATEKEEPER_PROMOTION_V1.md`, a day is classified **GREEN** when:
avg VP >= 0.35, at least 5 picks VP >= 0.40, at least 2 picks VP >= 0.45. The doc's own
"MANDATORY CAVEAT" already names one confirmed false-green day (2026-06-09, SR 13.8%).
This autopsy re-derives the GREEN/AMBER/RED classification independently from each day's
`velo_prime_prob` field in `sigma_results_*.json` `rows[]`, cross-checks it against that
day's actual strike rate (`sr`), and looks for a repeatable pattern across every
GREEN-classified day that beat baseline versus every GREEN-classified day that didn't.

**False-green definition used:** gate says GREEN, but day SR < 24.3% (the VP Gatekeeper's
own documented current-era baseline SR).

## 2. Scan result across all 31 available dates

| Gate | Count | Dates |
|---|---|---|
| GREEN | 16 | 06-03, 06-04\*, 06-05, 06-06, 06-08, 06-09, 06-11, 06-12, 06-13, 06-14, 06-16, 06-18, 06-19, 06-20, 06-23, 06-30 |
| RED | 9 | 05-23, 05-24, 05-25, 05-29, 05-30, 05-31\*, 06-01, 06-17 |
| AMBER | 1 | 06-02 |
| UNCLASSIFIED (falls between documented AMBER/RED bands) | 5 | 05-26, 05-27, 06-07, 06-10 |

\* `sigma_status: PARTIAL_RESULTS_DIAGNOSTIC_ONLY` — lower-confidence capture, included but flagged.

**6 of 16 GREEN days (37.5%) were false-green** (SR < 24.3% baseline):

| Date | avg VP | picks>=0.40 | picks>=0.45 | Day SR | Verdict |
|---|---|---|---|---|---|
| 2026-06-09 | 0.3546 | 10 | 7 | **13.8%** | FALSE GREEN (documented precedent) |
| 2026-06-16 | 0.3502 | 11 | 5 | **21.2%** | FALSE GREEN |
| 2026-06-18 | 0.4332 | 17 | 13 | **21.2%** | FALSE GREEN |
| 2026-06-19 | 0.4711 | 35 | 32 | **19.6%** | FALSE GREEN |
| 2026-06-23 | 0.4801 | 11 | 10 | **17.6%** | FALSE GREEN |
| 2026-06-30 | 0.3983 | 21 | 14 | **23.9%** | FALSE GREEN |

vs. 10 true-green days (SR range 25.0%-39.1%, mean 32.5%).

## 3. False-green feature class identified: `CONFIDENCE_FLOOD_FALSE_GREEN`

Comparing the two groups on fields already present in `sigma_results_*.json`
(`avg_hit_prob`, `avg_miss_prob` — the mean VP among winning vs. losing picks that day):

| Metric | False-green (n=6) | True-green (n=10) |
|---|---|---|
| Mean discrimination gap (avg_hit_prob − avg_miss_prob) | **+0.039** | **+0.116** (~3x higher) |
| Days with *negative* gap (VP higher on losers than winners) | **2 of 6** (06-23: −0.093, 06-30: −0.050) | **0 of 10** |
| Mean share of field flagged VP>=0.40 (`n_40 / n_races`) | **48.0%** | **40.5%** |

**Reading:** on false-green days, VP was elevated broadly across the field — pushing more
picks over the action threshold — without a matching rise in the model's actual ability
to separate that day's winners from that day's losers. On two of the six false-green days,
VP was on average *higher for horses that lost* than for horses that won — the clearest
possible warning signal, and one the current gate cannot see at all, because the gate
formula only reads the VP *level* and *count*, never VP's *discrimination power* for that
day. This never happened on any of the 10 true-green days in this sample.

## 4. Ruled out (checked, not differentiating)

To avoid overclaiming, these were checked and found **not** to distinguish false-green
from true-green days in this sample:

- **Frame rate:** false-green mean 56.8% vs. true-green mean 59.7% — essentially the same.
- **Miss-class mix:** `MID_PRICE_WALL`-equivalent (`mid_priced_won`) tag dominates both
  groups almost identically (69.3% of tagged misses in false-green days, 68.1% in
  true-green days) — consistent with `docs/current/VFU_FAILURE_TAXONOMY_V1.md` calling
  `MID_PRICE_WALL` "the most common miss class in VÉLØ history" regardless of gate
  correctness. This is not a false-green-specific signal.
- **Winner SP:** median 2.38 (false-green) vs. 2.20 (true-green) — not meaningfully different.

## 5. Feature push/pull summary

| Direction | Feature | Effect |
|---|---|---|
| **Push toward false GREEN** | Broad/elevated VP across the field (more of the field crossing 0.40/0.45 than on a genuinely strong day) | Inflates `avg VP` and pick-count criteria without inflating accuracy |
| **Missing pull (latent gap)** | VP discrimination gap (`avg_hit_prob − avg_miss_prob`) | Currently not read by the gate at all — this is the field that would have caught 6/6 false-green days retrospectively (all 6 show a compressed or inverted gap vs. every true-green day) |

## 6. Why the gap exists structurally, not as an oversight

The VP Gatekeeper (`docs/current/VP_GATEKEEPER_PROMOTION_V1.md`) is explicitly a
**pre-race** classifier — it only has access to that day's VP distribution before results
exist. `avg_hit_prob` / `avg_miss_prob` are necessarily post-hoc (they require knowing
which picks won). So this is not a case of an available pre-race feature being ignored;
it is a structural blind spot: **a pre-race-only confidence gate cannot, by construction,
detect a "confidence flood" day**, because the flood and the lack of discrimination look
identical to the gate until results land. This matches the gate doc's own caveat
("The gate identifies opportunity conditions. It does not guarantee outcomes") — this
autopsy adds the specific, named mechanism (`CONFIDENCE_FLOOD_FALSE_GREEN`) and confirms
it is repeatable (6 of 6 false-green days fit the pattern), not a one-off.

## 7. Recommendation (not implemented — dry-run finding only)

A same-day, results-based `VP Discrimination Gap` diagnostic (computed after Sigma closes,
alongside the existing `high_conf_sr` metric already in `sigma_results_*.json`) could serve
as a **retrospective** false-green detector for the day just closed — useful for pattern
tracking and VFU learning, but it cannot prevent a same-day false green since it needs
results. No change to the live VP Gatekeeper criteria is proposed or made here — this
task contract (`ops/task_contracts/VFU-22.json`) explicitly forbids `vp_gate_criteria_change`.
Any such diagnostic would need its own operator-approved mission.

## 8. Limitations (disclosed, not papered over)

- Evidence base is the 31 `sigma_results_*.json` files present in this worktree
  (2026-05-23 to 2026-06-30). This is not the full system history — dates outside this
  range were not scanned because no local sigma_results artifact exists for them in this
  worktree. Re-running this scan after future dates accumulate would extend the sample.
- 3 dates carry `sigma_status: PARTIAL_RESULTS_DIAGNOSTIC_ONLY` rather than `PASS`
  (05-23, 05-31 excluded from the GREEN/AMBER/RED comparison groups by virtue of being
  RED; 06-04 included in the true-green set — flagged with an asterisk above).
- 5 dates fell into neither the documented GREEN, AMBER, nor RED band under strict
  criteria and are reported as `UNCLASSIFIED` rather than forced into a bucket.
- This is a feature-pattern autopsy, not a proposed change to any live gate, model, or
  scoring path.

## Final classifications

- `FALSE_GREEN_AUTOPSY_COMPLETE`
- `FALSE_GREEN_CLASSES_IDENTIFIED` — `CONFIDENCE_FLOOD_FALSE_GREEN` (6/6 false-green days fit; 0/10 true-green days show the same discrimination-gap collapse)
- `FEATURE_PUSH_PULL_REPORTED` — push: broad/elevated field-wide VP; missing pull: VP discrimination gap (not read by current gate)
- `LATENT_WARNING_GAPS_REPORTED` — structural: pre-race gate cannot see post-hoc discrimination collapse
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_TELEGRAM_SEND`
- `NO_MODEL_PROMOTION`
