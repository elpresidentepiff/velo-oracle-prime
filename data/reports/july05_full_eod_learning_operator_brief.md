# July 5 2026 — Full EOD Learning Packet — Operator Brief
Generated: 2026-07-05 | Mission: JULY05-FULL-EOD-LEARNING-PACKET-PR

---

## 1. Is July 05 connected end-to-end?
Yes. Results (22/22) → Sigma (22/22 matched) → Step 13 horse-run ingest (193 runners) → Step 14 corpus (date_max=2026-07-05) → Step 15 Mission Control → Step 16A VP30 → Step 16B Council → Step 17 Execution Bridge → Step 18 Innovation Protocol → Step 19 Router Audit → Step 20 Nightly Learning. All 22 races (Ayr/Market Rasen/Southwell AW) flow through cleanly with real numeric race_ids and horse_ids throughout (per PR #122/#123/#124).

## 2. Did Sigma complete 22/22?
Yes. `sigma_results_2026_07_05.json`: `evaluated_count: 22`, `wins: 4`, `sr: 0.1818`, `frame_rate: 0.5909`.

## 3. Why sigma_audits has 21 rows, not 22
One race (921917) was tier X and blocked from sigma audit persistence by design — the Sigma script's own tier-X exclusion rule, not a data or identity failure. Confirmed: 21/21 rows unique, no duplicates, matches the console log's `[BLOCK] 921917: tier X blocked from sigma audit`.

## 4. What did Step 13 ingest?
193 runners across 22 races into `racing_horse_runs` (run_date=2026-07-05). Feeds tomorrow's RPDC release-tag computation, same as July 4's Step 13 fed today's RPDC.

## 5. Did corpus include July 05?
Yes. `build_sigma_retrieval_corpus.py --require-through-date 2026-07-05` → `freshness_gate_passed: true`, `date_max: 2026-07-05`, `date_count: 107` (up from 106 the day before).

## 6. What did Mission Control say?
`source_truth: RP_MERGED_CLEAN` (clean — no override needed, unlike the mid-mission `[OVERRIDE]` seen before PR #123's fix). `sigma_artifact: PRESENT (sr=0.1818, wins=4, n=22)`. `learning_gate: BLOCKED`, `promotion_gate: BLOCKED`. `council_verdict: WATCH_ONLY`.

## 7. What did Council say?
Verdict: `WATCH_ONLY`, status `EVIDENCE_INCOMPLETE`. Watch flag: `SIGMA COVERAGE: SR_BELOW_BASELINE`.

## 8. Why is Council WATCH_ONLY?
Because today's strike rate (18.2%) sits below the working baseline, not because of any data/identity/snapshot gap. This is a different reason than July 4's `MISSING_SNAPSHOTS` flag — today's scoring run wrote runner snapshots normally (no `--verdicts-only`), so the snapshot gap that blocked July 4 doesn't apply here. Council is correctly withholding learning-consume on a below-baseline day regardless.

## 9. Did Execution Bridge run paper-only?
Yes. 1 active paper bet, 0 wins, 1 placed, +0.00 pts / +0.0% ROI. Governance: live execution NOT OCCURRED, staking NONE, Telegram NOT SENT (by the bridge itself), model changes NONE, router promotion NONE. Freeze check: `INSUFFICIENT_SAMPLE (n=1, need 20)`.

## 10. What did Innovation Protocol say?
22 new verdict rows deduped into the router dataset (1,976 total, 0 duplicates). Router summary: V1_BASE_SHADOW n=10 ROI=-20.2%, V2_CLASS4_SHADOW n=130 ROI=-5.1%, V6_GOLD_SEAM_WATCHLIST n=86 ROI=+9.3% (up from +1.2% the day before).

## 11. What did Router Shadow Audit say?
V1_BASE: `LANE_FROZEN` (n=226, SR=34.5%, Frame=73.5%). V2_CLASS4_ONLY: moved from `LANE_FROZEN` to **`WATCHLIST`** (n=216, SR=34.7%, Frame=72.7%, ROI=+0.6%) — improved but still not promotion-eligible. V6_GOLD_SEAM: `LANE_FROZEN` (n=86, SR=30.2%, Frame=60.5%, ROI=+9.3% — ROI-positive but frame still below the 70% threshold). No lane promoted.

## 12. Did Nightly Learning run?
Yes. `nightly_eod_learning_runner.py --date 2026-07-05`. Matched: 22/22. Events created: 22. `engine_updates_applied_first_run: 22`, 0 duplicates on this first run (expected — first run for this date). Verdicts: `PASS` / `PASS_EVOLVED` / `PASS_IDEMPOTENT`. Study layer: `PASS_WITH_WARNINGS` (expected on a below-baseline day — not a failure). `live_sentient_state_touched: false`, `shadow_state_touched: true`, `supabase_writes_attempted: false`.

## 13. What did VÉLØ learn today?
A lower win-conversion day than July 4 (18.2% vs 29.4% SR) but a *stronger* frame rate (59.1% vs 52.9%). The model is still correctly narrowing the field to the right contenders — it's failing to pick the single winner within that narrowed group, not failing to identify the group at all.

## 14. What did VÉLØ learn compared with July 04?
| Metric | July 04 | July 05 |
|---|---|---|
| Wins/n | 15/51 | 4/22 |
| Strike rate | 29.4% | 18.2% |
| Frame rate | 52.9% | 59.1% |
| mid_priced_won misses | 18 | 7 |

Combined lesson: across two consecutive days with different win rates, the frame rate stayed strong or improved while mid-price discrimination remained the dominant failure mode both times. This is now a two-day pattern, not a one-off.

## 15. What did VÉLØ learn about wins?
Only 4 wins today, too small a sample to draw a confidence-calibration conclusion on its own — but consistent with July 4's finding that hit probability separates real winners reasonably well (this day's small n doesn't contradict that).

## 16. What did VÉLØ learn about frames?
Frame rate (59.1%) was the strongest single number of the day — actually higher than July 4's 52.9%. VÉLØ is finding the right small group of contenders reliably even when it isn't picking the outright winner.

## 17. What did VÉLØ learn about misses?
9 misses total (of 22 non-tier-X evaluated... actually 18 losses per the nightly runner's broader non-win accounting, 9 Sigma "true misses" outside the frame). Split 7 mid_priced_won / 2 short_fav_won — no outsider_won misses today at all.

## 18. What did VÉLØ learn about mid-priced winners?
7 of 9 true misses (78%) were mid_priced_won — an even higher concentration than July 4's 75%. This reconfirms `MIDPRICE_TRAP` as the dominant, recurring failure mode across both days now on record.

## 19. What did VÉLØ learn about short favourites?
2 short_fav_won misses today (vs 2 on July 4 too) — a small, stable, non-dominant failure mode on both days. Not the priority.

## 20. Did data quality fail?
No. 0 parse errors, 22/22 races matched, 0 non-runners excluded unexpectedly, 0 identity failures reported by Mission Control.

## 21. Did identity/RPDC fail?
No. `data_error_count: 0` in the nightly learning status (down from 1 on July 4, before that day's Leicester recovery). Real race_ids and horse_ids held throughout, thanks to PR #122/#123/#124 landing before today's scoring.

## 22. Which signals are memory-only?
The retrieval corpus update and Innovation Protocol dedup (now 1,976 rows) — evidence accumulation for future retrieval/router-shadow work, no live-scoring effect today.

## 23. Which signals are failure-learning?
The `mid_priced_won` dominance (now confirmed across two consecutive days) and `loss_count_by_type` (WRONG_HORSE=8, CALIBRATION_ERROR=10) from the nightly runner.

## 24. Which signals are promotion-gated?
Everything, as always. `promotion_gate: BLOCKED`, V1_BASE and V6_GOLD_SEAM still `LANE_FROZEN`, V2_CLASS4_ONLY moved to `WATCHLIST` but explicitly not eligible (target thresholds not yet met). Council `WATCH_ONLY` blocks learning-consume.

## 25. What is tomorrow's preflight gate?
Unchanged from July 4's finding: `verify_raceday_universe.py` race-ID agreement gate, plus the standing question of whether to authorize a scoring run without `--verdicts-only` so Council can move past its snapshot-dependency on days when SR happens to be at/above baseline (today's WATCH_ONLY was SR-driven, not snapshot-driven, since snapshots were written normally).

## 26. What is tomorrow's research priority?
`MIDPRICE_TRAP` — now reconfirmed on two consecutive raceday's as the dominant, recurring failure mode (18/24 misses July 4, 7/9 misses July 5). This should be the next research lane prioritized over any other signal work, per the operator's own read.

## 27. What remains blocked?
Everything under the hard laws: model promotion, live scoring changes, live staking. Router lanes: 2 of 3 frozen, 1 on watchlist. Learning-consume blocked by Council `WATCH_ONLY`.

---

## Required learning statement
July 05 was a lower win-conversion day than July 04, but frame rate remained strong. This means VÉLØ is still identifying plausible contenders but failing to convert top-ranked selections into winners. Mid-price discrimination remains the recurring failure mode across both days. Data-error was zero, so the failure is model/ranking/calibration, not source identity.

## Classifications
JULY05_FULL_EOD_CHAIN_CONFIRMED · SIGMA_22_OF_22_CONFIRMED · STEP_13_RESULTS_INGEST_CONFIRMED · MISSION_CONTROL_UPDATED · VP30_UPDATED_IF_PRESENT · LLM_COUNCIL_WATCH_ONLY_CONFIRMED · EXECUTION_BRIDGE_SHADOW_COMPLETE · INNOVATION_PROTOCOL_COMPLETE · ROUTER_SHADOW_AUDIT_COMPLETE · NIGHTLY_EOD_SHADOW_LEARNING_COMPLETE · MIDPRICE_TRAP_RECONFIRMED · FRAME_RATE_HEALTHY_WIN_CONVERSION_WEAK · MEMORY_CAPTURE_OPEN · FAILURE_LEARNING_OPEN · PROMOTION_LEARNING_GATED · NO_MODEL_PROMOTION · NO_LIVE_SCORING_CHANGE · NO_VERDICT_REWRITE · NO_RPDC_REWRITE · NO_RUNNER_SNAPSHOT_WRITE · NO_TELEGRAM_SEND_IN_THIS_REPORT_MISSION · REPORT_ONLY_EOD_PACKET
