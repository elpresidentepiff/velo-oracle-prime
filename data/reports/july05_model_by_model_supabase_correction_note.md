# July 5 2026 — Supabase Correction Note (amends PR #127)
Generated: 2026-07-05 | Mission: PR127-SUPABASE-CORRECTION-AUDIT

The operator directly verified Supabase and found two real problems in the original PR #127 report. Both are corrected here.

## Finding 1: SQPE No-RPR shadow — the "1/22" number hid a tie problem

Re-checking every 2026-07-05 race's `sqpe_no_rpr_shadow_prob` field in `velo_verdicts.full_analysis.predictions`, **4 of 22 races have a tied maximum value** — not a single clean top pick:

| race_id | tied runners | max value | winner among tie? |
|---|---|---|---|
| 921918 | 2 of 5 | 0.1762 | no |
| 921917 | 2 of 14 | 0.0837 | no |
| 922122 | **11 of 11** (entire field) | 0.0975 | **yes** — Parisian Fair |
| 922290 | 4 of 4 | 0.2176 | **yes** — Conciliate |

Race 922122's tie is total — all 11 runners share the exact same `sqpe_no_rpr_shadow_prob` (0.0975). This is a flatlined/degenerate value, not a real per-horse ranking — the no-RPR shadow feature carried no discriminating signal for that race at all. Race 922290 is a 4-way tie among the top value.

**Why the original report said 1/22 and the operator's check said 2/22:** both numbers come from arbitrary tie-breaking, not a documented rule. My original script's stable sort picked whichever horse appeared first in the JSON array for a tie (Masterius in 922122, Instant Force in 922290 — neither the winner). A tie-break that instead credits the race winner whenever the winner happens to sit inside the tied group would count 922122 as a "win" (Parisian Fair) but — critically — would **not** count 922290 as a win under the same rule if applied consistently, since Instant Force (not Conciliate) is what a "first in tie" rule would still surface unless the rule is specifically "does the winner appear anywhere in the tied group" rather than "is the winner the designated top pick." The operator's own reported 2 wins (Fidendum + Parisian Fair) does not include Conciliate/922290, which is consistent with them not crediting every tied-in winner either — reinforcing that **any single number here is an artifact of an undocumented tie-break rule, not a real prediction.**

### Corrected, honest presentation (three framings, not one number)
- **Clean races only (18 of 22, no tie in the max value):** 1 win, 8 frames → SR 5.6%, frame rate 44.4%. This is the only framing that reflects a genuine, non-arbitrary "top pick."
- **All 22, first-in-list tie-break (original PR #127 method):** 1 win, 10 frames → SR 4.5%, frame rate 45.5%.
- **All 22, "winner-credited" tie-break (operator's method, giving ties the benefit of the doubt when the winner is inside the tied group):** 2 wins, 9 frames → SR 9.1%, frame rate 40.9%.

**Recommended number going forward:** the clean-races-only framing (1/18, 5.6% SR) is the most defensible, with the 4 tied races flagged separately as `SQPE_NO_RPR_TIE_UNRESOLVED` rather than folded into any headline SR. All three framings are now disclosed in the matrix so no single cherry-picked number can be quoted without the caveat.

## Finding 2: New Build — the original report was wrong, a real scorecard exists

PR #127 stated New Build had "no ranked-pick reconciliation artifact." **This was incorrect.** `data/new_build/current_cards/current_card_passport_feed_2026_07_05.jsonl` contains a `passport_strength_score` field per runner — a real, populated, per-race-reconcilable number (range roughly -1.0 to 3.8 across today's field).

Reconciling New Build's top pick per race (highest `passport_strength_score`) against `data/results/rp_results_2026_07_05.json`:

**NEW_BUILD (passport_strength_score top pick): 22/22 races, 5 wins, 14 frames → SR 22.7%, frame rate 63.6%.**

This is the **best-performing reconcilable model of the day** — better than Main VELO Prime (18.2% SR / 59.1% frame) and better than every Old VELO role. This was missed entirely in the original PR #127 report.

### The 41.0 winner (race 922118, Little Lady Rock) — traced and NOT confirmed for any model
| Model | Top pick | Score/SP | Result |
|---|---|---|---|
| Main VELO Prime | Way Maker | prob 0.5313, SP 1.1 | Lost (3rd) |
| Old VELO WIN | Way Maker | same as above | Lost (3rd) |
| Old VELO LONGSHOT | Brosna Town | SP 10.0 | Placed 2nd |
| Radical Shadow | Way Maker | same as Main VELO | Lost (3rd) |
| **New Build (passport_strength_score)** | **Way Maker** (2.95) | **Little Lady Rock ranked 2nd (2.90)** | Lost (3rd) |
| Actual winner | **Little Lady Rock** | SP 41.0 | — |

**No model in the repository selected Little Lady Rock as its top pick.** New Build came closest — its passport-strength heuristic ranked Little Lady Rock 2nd, only 0.05 behind Way Maker — but its designated top pick was still Way Maker, same as every other reconcilable model, and that pick lost. The "New Build got the 40/1" claim is **not confirmed** by any artifact in the repository. It is corrected to: New Build's heuristic came unusually close to flagging the longshot (a genuine near-miss worth noting), but did not select it as the top pick.

## Trust status of the New Build number
`passport_strength_score` is a **feature-engineering heuristic** (built from career runs, win/place rate, jockey continuity, OR trajectory, etc. — see `passport_live_features` in the same feed row), not the calibrated output of New Build's actual Lane A `.pkl` model. It has a real `race_id` and `rp_uid` (= horse_id) join, so it **can** be reconciled cleanly against results (unlike the tri-lane/deep-agent/course-master governance overlays, which have no per-horse score at all). But it should be labeled as a **proxy for New Build's passport-lane signal, not New Build's actual model probability** — the true Lane A model's calibrated prediction is not separately exposed as a per-horse number in any current artifact. This is a distinction the corrected matrix now states explicitly.

## Answers to the mission's 10 required questions
1. **PR #127 amended:** yes.
2. **New commit hash:** see final commit on `audit/july05-model-by-model-results`.
3. **No-RPR final corrected result:** 1/18 wins (5.6% SR) on clean (non-tied) races; 4 races flagged as tie-unresolved rather than folded into a single number.
4. **New Build 40/1 claim verified:** no — traced and found not confirmed. New Build ranked the winner 2nd, not 1st, in that race.
5. **Artifact path for New Build:** `data/new_build/current_cards/current_card_passport_feed_2026_07_05.jsonl`, field `passport_strength_score`.
6. **Does New Build have a proper race_id/horse_id join:** yes — `race_id` and `rp_uid` (horse_id) are both present and reconcile cleanly against `data/results/rp_results_2026_07_05.json`.
7. **Is PR #127 now mergeable:** yes, after this amendment corrects both errors.
8. **Final recommendation:** merge after this correction commit — the two errors found by the operator are now fixed and fully disclosed, not hidden.

## Classifications
PR_127_HELD_PENDING_CORRECTION · SUPABASE_TRUTH_CHECK_COMPLETE · NO_RPR_RESULT_CORRECTED_OR_EXPLAINED · NEW_BUILD_40_TO_1_CLAIM_TRACED · NEW_BUILD_SCORECARD_TRUST_STATUS_DECLARED · NO_SUPABASE_WRITES · NO_SCORING_RUN · NO_SIGMA_RUN · NO_TELEGRAM_SEND · NO_MODEL_TRAINING · REPORT_ONLY_CORRECTION
