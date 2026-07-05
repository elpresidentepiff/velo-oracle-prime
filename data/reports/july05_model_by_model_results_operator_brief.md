# July 5 2026 — Model-by-Model Results — Operator Brief
Generated: 2026-07-05 | Mission: JULY05-MODEL-BY-MODEL-RESULTS-PACKET

> **AMENDED 2026-07-05** after operator Supabase verification found two errors: (1) New Build was wrongly reported as having no scorecard — `passport_strength_score` is a real, reconcilable field; (2) the No-RPR shadow's "1/22" hid an undisclosed tie in 4 of 22 races. Both corrected below. Full detail in `data/reports/july05_model_by_model_supabase_correction_note.md`.

---

## 1. Which models/lane outputs existed before this mission?
Main VELO Prime (`velo_verdicts`, `sigma_results`, `sigma_audits`, dashboard publish), New Build (`current_card_passport_feed`, `two_lane_readiness` — readiness only, no scorecard), and cumulative router-lane figures (`router_shadow_audit_latest.csv`, Innovation Protocol dataset). Old VELO, No-RPR shadow (as its own re-ranked pick), Radical Shadow, Tri-Lane, Deep Race Agent, and Course Master had **no dated 2026-07-05 artifact** before this mission.

## 2. Which sidecars were run now?
All 6 candidate report-only scripts, all confirmed safe first (no Supabase/Telegram references in source):
- `build_old_velo_three_option_card.py` → WIN/PLACE/LONGSHOT reconciled against results
- `run_radical_shadow_today.py`
- `run_tri_lane_stress_test.py --ruleset v2`
- `build_tri_lane_agent_review.py --packet <above>`
- `build_deep_race_agent_v1.py`
- `build_course_master.py`

## 3. Which sidecars could not be run and why?
None were skipped — all 6 ran successfully for 2026-07-05. New Build Lane B (intent features) is **not a sidecar gap** but a structural non-availability: intent features are historical (race_id, horse) pairs that never match a current/future card, so 0% coverage is expected for any morning read, not a missing run.

## 4. Main VELO Prime result
4/22 wins, SR 18.2%, 13/22 frames, frame rate 59.1%. (Unchanged from the earlier Sigma reconciliation — this mission did not re-run Sigma.)

## 5. New Build result [CORRECTED]
A real scorecard **does** exist and was missed in the original report. `data/new_build/current_cards/current_card_passport_feed_2026_07_05.jsonl` carries a `passport_strength_score` per runner, with real `race_id`/`rp_uid` (horse_id) fields that reconcile cleanly against results. Ranking each race by this score: **5/22 wins (22.7% SR), 14/22 frames (63.6% frame rate) — the best-performing reconcilable model of the day**, beating Main VELO Prime (18.2%/59.1%) and every Old VELO role. Caveat: this is a feature-engineering heuristic (passport strength), not the calibrated output of New Build's actual Lane A `.pkl` model — labeled as a proxy signal, not New Build's true model probability. `two_lane_readiness_2026_07_05.json` remains a separate feature-quality gate report (RPR clean, SP clean, passport coverage >50%, no leakage), not itself a scorecard.

## 6. Old VELO result
Reconciled directly from `old_velo_three_option_card_2026_07_05.json`'s `role_metrics`:
- **WIN role**: 4/22 wins, 13/22 frames — identical to Main VELO Prime, because the WIN role is built from the same top-ranked `velo_prime_prob` pick.
- **PLACE role**: 3/22 wins, 9/22 frames.
- **LONGSHOT role**: 3/22 wins, 6/22 frames.

## 7. No-RPR shadow result [CORRECTED]
4 of 22 races have a **tied** maximum `sqpe_no_rpr_shadow_prob` (921918: 2-way, 921917: 2-way, 922122: **11-way, the entire field, a flatlined value with zero discriminating signal**, 922290: 4-way) — meaning no principled single top pick exists in those races. Original report's 1/22 used an undisclosed first-in-list tie-break; the operator's own check found 2/22 using a different, equally undisclosed tie-break. Neither is more "correct." Honest framings:
- **Clean races only (n=18, no tie):** 1 win, 8 frames → SR 5.6%, frame rate 44.4% — the recommended headline number.
- All 22, first-in-list tie-break: 1 win, 10 frames → 4.5% SR.
- All 22, winner-credited tie-break: 2 wins, 9 frames → 9.1% SR.
Still the weakest reconcilable model under any framing — removing RPR-derived features costs signal, and on top of that, several races produce no real signal at all (the ties).

## 8. Radical shadow result if available
`radical_shadow_2026_07_05.json` tracks the *same* top pick as Main VELO/Old-VELO-WIN (it overlays passport/sigma/midprice-shadow context onto the existing top pick, it does not produce an independent ranking) — so its reconciled win/frame numbers are identical to Main VELO's (4/22, 13/22). Its value today is diagnostic context (midprice-shadow-action flags, passport-strength scores), not a distinct scorecard.

## 9. Tri-lane result if available
`tri_lane_stress_test_2026_07_05_v2.json`: action counts across 22 races — `TRI_PASS`: 19, `TRI_WIN`: 1, `TRI_CASH_RUN`: 2. These are governance/execution-lane classifications (whether a race clears tri-lane stress conditions), not independent horse picks, so they aren't directly win/loss-reconcilable the way Old VELO's roles are.

## 10. Deep Race Agent result if available
`deep_race_agent_v1_2026_07_05_v2.json`: 14 cards produced (not full 22-race coverage — expected, this is a curated review tool, not a full-field scorer, same behavior seen on July 4). Verdicts: `NO_BET`: 8, `CASH_RUN_REVIEW`: 2, `PASS_WITH_SUPPORT_REVIEW`: 4. `ratings_rows=0`, `race_pdf_sets=0` — it ran without the optional `--downloads`/raceform PDF cross-reference, using only the data already in Supabase/racecard files.

## 11. Course Master result if available
`course_master_2026_07_05.json`: course-level (not runner-level) actions across the 3 courses — 1 `COURSE_SUPPRESS`, 1 `COURSE_BOOST`, 1 `COURSE_NEUTRAL`. Not reconcilable to a per-race win/loss figure.

## 12. Router lane results — TODAY-ONLY vs CUMULATIVE (kept strictly separate)
**Today-only (2026-07-05's 22 rows only, isolated from the innovation-protocol dataset):**
| Lane | Today's candidates | Today's wins | Today's placed |
|---|---|---|---|
| ROUTER_V1_BASE | 5 | 0 | 0 |
| ROUTER_V2_CLASS4_ONLY | 5 | 0 | 0 |
| ROUTER_V6_GOLD_SEAM | 4 | 0 | 0 |

**Cumulative-to-date (all history, NOT today's number):**
| Lane | n (cumulative) | SR | Frame | ROI | State |
|---|---|---|---|---|---|
| V1_BASE | 226 | 34.5% | 73.5% | -0.3% | LANE_FROZEN |
| V2_CLASS4_ONLY | 216 | 34.7% | 72.7% | +0.6% | WATCHLIST |
| V6_GOLD_SEAM | 86 | 30.2% | 60.5% | +9.3% | LANE_FROZEN |

All 3 router lanes had 0 wins from today's small candidate pools — a bad day for the router lanes specifically, masked by the strong cumulative history if the two aren't kept separate (which is exactly why the operator asked for this split).

## 13. Which model beat Main VELO today? [CORRECTED]
**New Build (passport_strength_score proxy) beat Main VELO today**: 22.7% SR / 63.6% frame rate vs Main VELO's 18.2% / 59.1%. This was missed in the original report. Old VELO's WIN role tied Main VELO exactly (same pick). PLACE and LONGSHOT roles were both below on wins, LONGSHOT's frame rate (27.3%) well below. No-RPR shadow was clearly worse under every framing. Router lanes went 0-for-today across all three.

### The 41.0 winner, traced (race 922118, Little Lady Rock) — not confirmed for any model
| Model | Top pick | Result |
|---|---|---|
| Main VELO / Old VELO WIN / Radical Shadow | Way Maker (prob 0.53, SP 1.1) | Lost (3rd) |
| Old VELO LONGSHOT | Brosna Town (SP 10.0) | Placed 2nd |
| New Build (passport_strength_score) | Way Maker (2.95) — Little Lady Rock ranked 2nd (2.90) | Lost (3rd) |
No model selected Little Lady Rock as its top pick. New Build came within 0.05 of ranking it 1st (a genuine near-miss) but its designated top pick lost, same as every other model.

## 14. Which model framed best?
Main VELO Prime / Old VELO WIN, tied at 59.1% (13/22).

## 15. Which model avoided mid-price trap best?
Cannot be fully isolated per-model without a full re-classification of every model's own misses into mid_priced_won/outsider_won/short_fav_won categories — that classification currently only exists for Main VELO's Sigma reconciliation. Given Old VELO WIN shares Main VELO's exact picks, it shares the exact same mid-price vulnerability. This is flagged as a genuine analysis gap (see Q19 below), not something invented here.

## 16. Which model failed worst?
SQPE_NO_RPR_SHADOW — weakest under every tie-break framing (5.6%/4.5%/9.1% SR depending on framing, all well below the field), and additionally the least trustworthy of all models today since 4 of its 22 races produce no real signal (tied/flatlined probabilities).

## 17. Did any model show promotion-grade evidence?
No. Nothing here changes the router-lane promotion picture from the EOD packet (PR #126): V1_BASE and V6_GOLD_SEAM `LANE_FROZEN`, V2_CLASS4_ONLY `WATCHLIST` but not eligible.

## 18. What remains WATCH_ONLY?
Everything under the standing hard laws — no promotion, no live scoring change, no model training. Council's `WATCH_ONLY` verdict from the EOD packet is unchanged by this report-only mission.

## 19. What should be built next so every model has a proper daily scorecard?
1. A proper New Build scorecard script that reconciles Lane A's **actual calibrated `.pkl` model output** against daily results — `passport_strength_score` is a usable proxy (and today it outperformed everything else) but it is a feature heuristic, not the real model probability. Building the genuine Lane A scorecard is now the top priority, not a "gap" to wave at — it may already be VÉLØ's best signal.
2. A per-model mid-price-trap breakdown (not just Main VELO's Sigma reconciliation) so Q15 can be answered properly next time.
3. A tri-lane/deep-race-agent/course-master "verdict accuracy" layer — today these tools only produce governance classifications, not scored predictions, so there's no way to ask "did the tri-lane governance call turn out to be right?"
4. A documented, single tie-break rule for `sqpe_no_rpr_shadow_prob` ties (or a fix to whatever produces flatlined values in some races), so this metric stops requiring three different framings to report honestly.

---

## Classifications
PR_126_MERGED · JULY05_MODEL_BY_MODEL_RESULTS_COMPLETE · MAIN_VELO_SIGMA_RESULT_INCLUDED · NEW_BUILD_SCORECARD_CHECKED · NEW_BUILD_SCORECARD_CORRECTED · OLD_VELO_SCORECARD_CHECKED · NO_RPR_SHADOW_CHECKED · NO_RPR_RESULT_CORRECTED · SIDECAR_OVERLAYS_CHECKED · ROUTER_LANES_INCLUDED_WITH_TODAY_VS_CUMULATIVE_SPLIT · NO_SUPABASE_WRITES · NO_VERDICT_REWRITE · NO_SIGMA_REWRITE · NO_RUNNER_SNAPSHOT_WRITE · NO_TELEGRAM_SEND · NO_MODEL_TRAINING · NO_MODEL_PROMOTION · REPORT_ONLY_MODEL_COMPARISON
