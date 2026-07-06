# July 5 2026 — Model-by-Model Results — Operator Brief
Generated: 2026-07-05 | Mission: JULY05-MODEL-BY-MODEL-RESULTS-PACKET

> **AMENDED THREE TIMES.** Amendment 1 (Supabase check) fixed the No-RPR tie disclosure but used the WRONG New Build field (`passport_strength_score`). Amendment 2 (dashboard forensic trace) corrected New Build to the real field (`lane_a_top3`) — confirmed rank 1 = Little Lady Rock, the 41.0 winner. Amendment 3 (hard-reset audit, `data/reports/july05_model_truth_reset_note.md` + `data/reports/july05_little_lady_rock_rank_policy_forensic.csv`) adds the missing distinction: **New Build's Lane A model ranked the winner #1, but its own `policy_v1` decision layer separately classified the pick `NO_EDGE`** — a model hit, not a governance/staking hit. Model rank, policy decision, dashboard display, and staking outcome are four different things and must never be collapsed into one word, "result," again — see `docs/current/VELO_MODEL_SOURCE_MAP.md`'s `MODEL_RESULT_REPORTING_LAW`.

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

## 5. New Build result [CORRECTED TWICE — this is the final version]
A real scorecard exists, and it is New Build's **actual operational Lane A model output** — `data/new_build/reports/two_lane_readiness_2026_07_05.json`, `race_day_scorecards[].lane_a_top3` (each entry: `rank`, `horse`, `prob`, `nb_decision_lane`). This is confirmed, by reading `new_build_dashboard_server.py`'s source code, to be exactly what the live dashboard displays as `new_build_top3`. Ranking each race by this field (rank 1 = highest `prob`): **6/22 wins (27.3% SR), 11/22 frames (50.0% frame rate) — the best strike rate of any model checked across both July 4 and July 5**, beating Main VELO Prime (18.2%/59.1%) and every Old VELO role.

My first amendment used the wrong field (`passport_strength_score`, a feature-engineering input from the passport feed, not New Build's model output) and reported New Build ranking Little Lady Rock 2nd for race 922118. **That was wrong.** The dashboard-forensic trace proves New Build's real model ranked Little Lady Rock (the actual 41.0 winner) **#1**, exactly as the operator's dashboard showed. Full trace in `data/reports/july05_dashboard_newbuild_little_lady_rock_forensic_note.md`.

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

## 13. Which model beat Main VELO today? [CORRECTED THREE TIMES — see full row-level proof in `data/reports/july05_little_lady_rock_rank_policy_forensic.csv`]
**New Build Lane A's model rank beat Main VELO decisively today**: 27.3% SR / 50.0% frame rate vs Main VELO's 18.2% / 59.1%. Old VELO's WIN role tied Main VELO exactly (same pick). PLACE and LONGSHOT roles were both below on wins. No-RPR shadow was clearly worse under every framing. Router lanes went 0-for-today across all three.

### The 41.0 winner, traced (race 922118, Little Lady Rock) — model rank, policy decision, and result kept separate
| Layer | Value |
|---|---|
| New Build Lane A **model rank** (`lane_a_top3[].prob`, descending) | **Rank 1 — Little Lady Rock — 0.2179** |
| New Build Lane B **model rank** (`lane_b_top3[].prob`) | Rank 1 — Little Lady Rock — 0.1679 |
| New Build **policy_v1 decision** (`new_build_velo/policy_v1.py`, anchored to Lane B prob) | **`NO_EDGE`** — 0.1679 misses `FRAME_TRUST_VP_MIN=0.17` by ~0.002 and `WIN_TRUST_VP_MIN=0.22` |
| **Dashboard-visible row** | Yes — this is the exact `lane_a_top3` field the dashboard renders |
| Main VELO / Old VELO WIN / Radical Shadow **pick** | Way Maker, prob 0.53, SP 1.1 — lost (3rd) |
| Old VELO LONGSHOT **pick** | Brosna Town, SP 10.0 — placed 2nd |
| No-RPR shadow **pick** (race 922118 has no tie, unlike 922122) | Brosna Town, 0.15 — placed 2nd |
| `passport_strength_score` (superseded proxy — NOT a model or dashboard field) | Way Maker 1st (2.95), Little Lady Rock 2nd (2.90) |
| **Actual result** | Little Lady Rock, SP 41.0, WON |

**Corrected classification: `NEW_BUILD_LANE_A_MODEL_HIT_41_TO_1` + `NEW_BUILD_POLICY_NO_EDGE_BLOCKED_STAKE`.** New Build's model rank correctly identified the actual winner. Its own policy layer separately did not clear it for any authorized action — this is not a realized-profit event, it is model-level evidence only. Main VELO, Old VELO WIN, and Radical Shadow all converged on the same short-priced favourite (Way Maker, SP 1.1) and lost together. Full row-level detail with every source path and field name: `data/reports/july05_little_lady_rock_rank_policy_forensic.csv`.

## 14. Which model framed best?
Main VELO Prime / Old VELO WIN, tied at 59.1% (13/22).

## 15. Which model avoided mid-price trap best?
Cannot be fully isolated per-model without a full re-classification of every model's own misses into mid_priced_won/outsider_won/short_fav_won categories — that classification currently only exists for Main VELO's Sigma reconciliation. Given Old VELO WIN shares Main VELO's exact picks, it shares the exact same mid-price vulnerability. This is flagged as a genuine analysis gap (see Q19 below), not something invented here.

## 16. Which model failed worst?
SQPE_NO_RPR_SHADOW — weakest under every tie-break framing (5.6%/4.5%/9.1% SR depending on framing, all well below the field), and additionally the least trustworthy of all models today since 4 of its 22 races produce no real signal (tied/flatlined probabilities).

## 17. Did any model show promotion-grade evidence?
No. Nothing here changes the router-lane promotion picture from the EOD packet (PR #126): V1_BASE and V6_GOLD_SEAM `LANE_FROZEN`, V2_CLASS4_ONLY `WATCHLIST` but not eligible. New Build's Lane A 41.0 rank-1 pick is genuine model-level evidence, not promotion-grade — its own policy layer (`NO_EDGE`) didn't clear it either, and one race is not multi-day validation.

## 18. What remains WATCH_ONLY?
Everything under the standing hard laws — no promotion, no live scoring change, no model training. Council's `WATCH_ONLY` verdict from the EOD packet is unchanged by this report-only mission.

## 19. What should be built next so every model has a proper daily scorecard?
1. **A permanent, dated New Build scorecard script that reads `lane_a_top3` directly** (not a feature-proxy field) and reconciles it against results every day, going forward — today's forensic trace should become a standing report, not a one-off correction. New Build's Lane A may already be VÉLØ's best signal (27.3% SR, caught a genuine 41.0 winner) and it deserves dedicated daily tracking, not rediscovery under operator pressure each time.
2. A per-model mid-price-trap breakdown (not just Main VELO's Sigma reconciliation) so Q15 can be answered properly next time.
3. A tri-lane/deep-race-agent/course-master "verdict accuracy" layer — today these tools only produce governance classifications, not scored predictions, so there's no way to ask "did the tri-lane governance call turn out to be right?"
4. A documented, single tie-break rule for `sqpe_no_rpr_shadow_prob` ties (or a fix to whatever produces flatlined values in some races), so this metric stops requiring three different framings to report honestly.
5. **A standing rule for future model-comparison reports**: every row must carry model name, source path, race_id, horse_id, rank, odds, and result — and any dashboard-adjacent claim must be traced to the exact server code that renders it, not assumed from the nearest-looking local artifact.

---

## Classifications
PR_127_HARD_HOLD · PREVIOUS_MODEL_REPORTS_NOT_TRUSTED · LITTLE_LADY_ROCK_MODEL_RANK_PROVEN · NEW_BUILD_LANE_A_MODEL_HIT_41_TO_1 · NEW_BUILD_POLICY_DECISION_PROVEN · MODEL_RANK_POLICY_STAKING_SEPARATED · ODDS_INCLUDED · SOURCE_PATHS_INCLUDED · PR_126_MERGED · JULY05_MODEL_BY_MODEL_RESULTS_COMPLETE · MAIN_VELO_SIGMA_RESULT_INCLUDED · NEW_BUILD_SCORECARD_CHECKED · NEW_BUILD_SCORECARD_CORRECTED · NEW_BUILD_SCORECARD_DASHBOARD_TRACED · DASHBOARD_SOURCE_OUTRANKS_LOCAL_REPORT · MAIN_VELO_SHORT_PRICE_TRAP · OLD_VELO_SCORECARD_CHECKED · NO_RPR_SHADOW_CHECKED · NO_RPR_RESULT_CORRECTED · NO_RPR_TIE_BREAK_BUG_FOUND · SIDECAR_OVERLAYS_CHECKED · ROUTER_LANES_INCLUDED_WITH_TODAY_VS_CUMULATIVE_SPLIT · NO_SUPABASE_WRITES · NO_SCORING_RUN · NO_SIGMA_RUN · NO_VERDICT_REWRITE · NO_RUNNER_SNAPSHOT_WRITE · NO_TELEGRAM_SEND · NO_MODEL_TRAINING · NO_PROMOTION · REPORT_ONLY_MODEL_COMPARISON
