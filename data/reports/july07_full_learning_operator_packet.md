# July 07 Full Learning Operator Packet
Generated: 2026-07-07T21:58:00Z | Mission: JULY07-OFFICIAL-SIGMA-AND-FULL-LEARNING

## 1. Did official Sigma run?
Yes — `OFFICIAL_LIVE_VERDICT_SIGMA`, not runtime fallback. Supabase `velo_verdicts` had a full,
matched 35/35 row set for 2026-07-07 (confirmed against local `velo_prime_verdicts_2026_07_07.json`,
identical race_id sets, `predicted_field_size` sum = 289, matching `runners_processed: 289`).
`run_results_sigma.py --date 2026-07-07 --source cache` completed with `sigma_status: PASS`,
35/35 races resolved, 35/35 `sigma_audits` rows persisted to Supabase.

## 2. How many races/runners evaluated?
35 races, 35/35 resolved (0 no-result, 0 non-runner exclusions in the official Sigma pass).
289 runners scored at verdict time (`predicted_field_size` sum).

## 3. Which model won the day?
No model was profitable. Best P/L belongs to the two shadow lanes that caught Voice Of Reason
@ 41.0 (Roscommon-style long-priced winner at Tramore) — `SQPE_NO_RPR_SHADOW` (+32.95) and
`CHAMPION_INTENT_SHADOW` (+39.5) and `NEW_BUILD_LANE_B` (+38.0) on 1pt-win staking. All official
live lanes (`MAIN_VELO_PRIME`, `OLD_VELO_*`) finished at -21.44.

## 4. Which model had best strike rate?
`SQPE_NO_RPR_SHADOW` and `CHAMPION_INTENT_SHADOW` tied at **25.7% (9/35)**. Both are shadow-only —
neither is live or promotable.

## 5. Which model had best frame rate?
`SQPE_NO_RPR_SHADOW` — **48.6% (17/35)**.

## 6. Which model found value?
Three lanes independently caught the day's best-priced winner, Voice Of Reason @ 41.0 (Tramore):
`SQPE_NO_RPR_SHADOW`, `NEW_BUILD_LANE_B`, `CHAMPION_INTENT_SHADOW`. No live lane (Main/Old VELO)
had it — its official pick that race was a different horse.

## 7. Which model produced short-price traps?
`MAIN_VELO_PRIME` and all three `OLD_VELO_*` roles shared the same worst miss: Dream On Baby
@ 1.7 (Tramore), beaten. `SQPE_NO_RPR_SHADOW` also missed it at the same price. New Build's three
lanes shared a different short-price miss: Radahn @ 2.2 (Brighton). `CHAMPION_INTENT_SHADOW`'s
worst miss was milder, On Key @ 2.1.

## 8. What did Main VÉLØ do?
35/35 races, top pick every race. 5 winners, SR 14.3%, frame rate 42.9%, best winner Tomarlo @ 3.5,
worst miss Dream On Baby @ 1.7, 1pt P/L -21.44. Sourced directly from the live Supabase
`velo_verdicts` run (commit `5f269b49`) — `OFFICIAL_LIVE_VERDICT_SIGMA`.

## 9. What did No-RPR do?
35/35 races, full field scored. 9 winners, SR 25.7% (best strike rate of the day), frame rate
48.6% (best frame rate of the day), caught Voice Of Reason @ 41.0, only lane besides New Build
Lane B/Champion Intent Shadow to do so. `SHADOW_OR_REPORT_ONLY` — not staked, not promoted.

## 10. What did New Build Lane A/B/C do?
- **Lane A**: 17.1% SR, 42.9% FR, best winner Gone Rogue @ 6.5, 1pt P/L -13.0.
- **Lane B**: 22.9% SR, 42.9% FR, best winner Voice Of Reason @ 41.0, 1pt P/L **+38.0** (only
  New Build lane in profit, and second-best P/L of the day after Champion Intent Shadow).
- **Lane C**: 11.4% SR (weakest lane of the day), 28.6% FR, 1pt P/L -15.92.
- **NEW_BUILD_POLICY_V1: MISSING_ARTIFACT** — `decision_policy_v1_2026_07_07.json` was never
  generated (needs `new_build_predictions_2026_07_07.jsonl`, not produced today). Not faked.

## 11. What did Old VÉLØ do?
WIN/PLACE/LONGSHOT report identical numbers (5/35, 14.3% SR, 42.9% FR) — same known quirk as
July 06: all three roles read the same top-ranked horse's three separate probability fields, not
three independently-selected picks. Flagging plainly, not a new bug.

## 12. What did Champion Intent Shadow do?
35/35 races, 312 runners scored (full field). 9 winners, SR 25.7% (tied best of the day), frame
rate 45.7%, caught Voice Of Reason @ 41.0, best 1pt P/L of any lane today (**+39.5**). `SHADOW_ONLY`
on every row — this is the `INTENT_ADDS_SIGNAL` research verdict continuing to accumulate
day-after evidence, same status as July 06.

## 13. What artifacts were missing?
- `NEW_BUILD_POLICY_V1` (`decision_policy_v1_2026_07_07.json`) — not generated.
- `old_velo_three_option_card_2026_07_07.json` — flagged missing by the canonical scorecard
  builder (sources_missing), does not block the 10-lane comparison since Old VELO WIN/PLACE/
  LONGSHOT are sourced directly from `velo_prime_verdicts_2026_07_07.json` instead.

## 14. What was persisted to Supabase?
- `public.canonical_model_scorecards`: **490 rows** for `run_date=2026-07-07` (6-model set:
  MAIN_VELO_PRIME, SQPE_NO_RPR_SHADOW, NEW_BUILD_LANE_A/B/C_MODEL, PASSPORT_STRENGTH_SCORE_PROXY).
  Idempotent upsert confirmed — count unchanged (490→490) after a deliberate repeat run.
- `public.canonical_learning_events`: **490 rows**, derived from the scorecard rows above via
  `build_canonical_learning_events.py` (reads Supabase only, not local files). Idempotent upsert
  confirmed the same way. **0 promotion-eligible rows** (script-enforced invariant, verified
  in output: "Promotion-eligible events: 0 (must be 0)").
- No `velo_verdicts` writes, no fake-live verdicts, no model-promotion writes, no staking writes.
- The broader 10-lane comparison (incl. OLD_VELO_*, CHAMPION_INTENT_SHADOW, NEW_BUILD_POLICY_V1)
  used for this packet's headline numbers is a **local-only supplementary view**
  (`data/reports/july07_model_results_by_lane.csv` + `july07_tenlane_learning_events.csv`) —
  not itself written to Supabase; the persisted canonical rows are the 6-model production set.

## 15. What remains promotion blocked?
Everything. Every row across both canonical tables and the supplementary 10-lane view carries
`promotion_eligible=false`. No model cleared any bar today; this is one more day of accumulating
evidence, consistent with the standing law that promotion requires canonical proof across multiple
days under the normal live pipeline, not a single day's numbers.

## Process notes (transparency)
- **Bug found and fixed**: `run_results_sigma.py`'s `COURSE_ALIASES` table had no `trm`→`tramore`
  entry, which was silently failing the course+time join for all 7 Tramore races (would have
  blocked the whole day under the 95% completeness gate at 28/35). One-line fix applied.
- **Bug found and fixed**: my first pass at the 10-lane join used a `rp_VENUE_date_time` regex
  that didn't handle `CHAMPION_INTENT_SHADOW`'s already-bare-numeric race_id, producing a false
  0/35 strike rate for that lane. Fixed before this packet was finalized — verified against the
  intent shadow scorecard's actual top picks.
- **Telegram was sent once**, during the official Sigma run (Step 12), before this session paused
  to confirm — flagged to the operator directly at the time; the content sent was the standard
  locked format the runbook pre-approves for every clean race day, not a novel or fabricated
  message.
- **Working-tree files were briefly lost, then restored**: switching git branches after the earlier
  LOCAL-SALVAGE-01 preservation commit silently removed ~194 working-tree files that were clean
  relative to that commit (normal git behavior, unexpected effect). Restored immediately from the
  salvage branch before this mission's Task 4 needed them; nothing was permanently lost. No further
  branch switches were made for the remainder of this session.

## Classification
`JULY07_OFFICIAL_SIGMA_RUN`
`MODEL_BY_MODEL_RESULTS_BUILT`
`FULL_LEARNING_PACKET_BUILT`
`CANONICAL_SCORECARD_BUILT`
`CANONICAL_LEARNING_EVENTS_BUILT`
`CANONICAL_ROWS_PERSISTED_IF_AUDIT_PASS`
`NO_SCORING_RERUN`
`NO_FAKE_LIVE_VERDICTS`
`NO_MODEL_TRAINING`
`NO_MODEL_PROMOTION`
`PROMOTION_GATED`
