# July 06 Full Learning Operator Packet

Generated: 2026-07-06T21:54:32Z
Mission: JULY06-SIGMA-LEARNING-NOW

## 1. What won today?

35/36 races parsed (1 parse error). Full winner list, sorted by off time:

| Race | Course | Off | Winner | SP |
|---|---|---|---|---|
| 922460 | Lingfield (AW) | 14:15 | Mister Daydream | 5.0 |
| 922456 | Lingfield (AW) | 14:45 | Perfect Nation | 2.2 |
| 922300 | Ayr | 15:00 | Royal Blaze | 12.0 |
| 924389 | Lingfield (AW) | 15:15 | Victory Gold | 1.91 |
| 922298 | Ayr | 15:30 | Native Honey | 11.0 |
| 922459 | Lingfield (AW) | 15:45 | Home Secretary | 4.5 |
| 922301 | Ayr | 16:00 | Ey Up He's A Star | 5.5 |
| 922457 | Lingfield (AW) | 16:15 | Law Of Average | 7.0 |
| 922295 | Ayr | 16:30 | Manila Scouse | 8.5 |
| 924276 | Roscommon | 16:38 | Rocky's Howya | 2.88 |
| 924390 | Lingfield (AW) | 16:50 | Tan Rapido | 7.0 |
| 922299 | Ayr | 17:00 | White Ladder | 5.0 |
| 924277 | Roscommon | 17:13 | Take The Free | 3.0 |
| 922458 | Lingfield (AW) | 17:20 | Rogue Defence | 2.2 |
| 922297 | Ayr | 17:30 | Ebony Maw | 11.0 |
| 924278 | Roscommon | 17:48 | Cocofred | 7.0 |
| 922461 | Lingfield (AW) | 17:55 | Fallacious Promise | 1.73 |
| 922305 | Ripon | 18:09 | Lady Rosalind | 5.0 |
| 924387 | Roscommon | 18:18 | Like An Ocean | 41.0 |
| 924398 | Lingfield (AW) | 18:25 | Ashj'Aa (Gb) | 11.0 |
| 922466 | Wolverhampton (AW) | 18:30 | South Shore | 2.62 |
| 922304 | Ripon | 18:39 | Alterity | 2.2 |
| 924279 | Roscommon | 18:48 | Lizzie Twigg | 2.38 |
| 922462 | Wolverhampton (AW) | 19:00 | Roxelina | 1.22 |
| 922303 | Ripon | 19:09 | Jesmond Dawn | 4.0 |
| 924280 | Roscommon | 19:18 | Del Boys Diva | 19.0 |
| 922463 | Wolverhampton (AW) | 19:30 | Style King | 13.0 |
| 922302 | Ripon | 19:40 | Reigning Profit | 4.33 |
| 924281 | Roscommon | 19:50 | Western Model | 5.5 |
| 922465 | Wolverhampton (AW) | 20:00 | Suggy | 3.5 |
| 922306 | Ripon | 20:15 | Riddikulus | 12.0 |
| 924282 | Roscommon | 20:22 | Goodgollymissholly | 5.5 |
| 922467 | Wolverhampton (AW) | 20:30 | Midnight Media | 2.88 |
| 922307 | Ripon | 20:52 | Lamlash Bay | 5.5 |
| 922464 | Wolverhampton (AW) | 21:00 | Primo Lara | 7.5 |

(1 race — Ayr 924296 not in the raceform confirmed list above, see parse error note in §12.)

## 2. What did each model pick?

Full model-by-model results table: `data/reports/july06_model_results_by_lane.csv` /
`_summary.md`. See §3–11 below for headline numbers per lane.

## 3. Which model had the best top-pick strike rate?

**NEW_BUILD_LANE_B** — 25.0% (9/36 winners), also best frame rate (44.4%, 16/36).

## 4. Which model had the best frame rate?

**NEW_BUILD_LANE_B** — 44.4% (16/36 top picks placed top-3).

## 5. Which model found value?

Two lanes tied for best single winning SP found: **NEW_BUILD_LANE_A** (Cocofred @ 7.0)
and **NEW_BUILD_LANE_B** (Tan Rapido @ 7.0). NEW_BUILD_LANE_B is the only lane with a
positive 1pt-win P/L for the day (+2.39pts) — every other lane finished negative.
SQPE_NO_RPR_SHADOW found the single best-priced winner of any lane at 7.5 (Primo Lara).

## 6. Which model missed short-price traps?

**Vietnorm (SP 1.53, lost)** was the shared worst miss across MAIN_VELO_PRIME,
NEW_BUILD_LANE_A, OLD_VELO_WIN/PLACE/LONGSHOT, and CHAMPION_INTENT_SHADOW — six of
nine populated lanes all shortlisted the same beaten short-priced favourite in that
race. NEW_BUILD_LANE_B's worst miss was milder (Heart Sign @ 2.62). This is the
day's clearest shared blind spot across lanes.

## 7. What did Champion Intent Shadow do?

36/36 races covered, 405 runners scored (full field, not just top-3).
Top-pick strike rate **22.2%** (8/36), frame rate 36.1% (13/36), best winner
Western Model @ 5.5, worst miss Vietnorm @ 1.53. Third-best strike rate of the
day behind NEW_BUILD_LANE_B and NEW_BUILD_LANE_A. `suggestion_status=SHADOW_ONLY`
on every row; not staked, not promoted — this is the `INTENT_ADDS_SIGNAL` research
verdict continuing to accumulate day-after evidence, as planned in PR #133/#134.

## 8. What did Old VÉLØ do?

WIN/PLACE/LONGSHOT all report **identical** numbers today: 16.7% SR (6/36),
41.7% FR (15/36), best winner Goodgollymissholly @ 5.5. This is not a bug in
today's join — `data/velo_prime_verdicts_2026_07_06.json` stores a single "top"
runner object per race with three separate probability fields
(`velo_prime_prob`, `place_prob`, `longshot_prob`), not three independently
selected picks. All three Old VELO roles are currently reading the *same*
top-ranked horse, just different score fields on it. Flagging this plainly
rather than presenting three roles as if they diverged when they don't.

## 9. What did No-RPR do?

36/36 races, full field scored. Strike rate 13.9% (5/36) — the weakest of the
five non-missing "primary" lanes (excluding New Build's three variants) — but
found the single best-priced winner of the day among fully-populated lanes,
Primo Lara @ 7.5. Frame rate 27.8% (10/36).

## 10. What did New Build do?

Three lanes, three different pictures from the same passport pipeline:
- **Lane A**: 19.4% SR, 33.3% FR — solid middle performer.
- **Lane B**: 25.0% SR, 44.4% FR — best lane of the day on both strike rate and
  frame rate, and the only lane in profit (1pt win P/L +2.39).
- **Lane C**: 5.6% SR, 27.8% FR — clearly the weakest lane today (-29.21pts on
  1pt stakes), consistent with Lane C's known status as a stress-test /
  velocity-candidate sidecar rather than a primary pick engine.
- **NEW_BUILD_POLICY_V1**: **MISSING_ARTIFACT** — `decision_policy_v1_2026_07_06.json`
  was never generated (it needs `new_build_predictions_2026_07_06.jsonl`, a
  further prerequisite not chased in the earlier dashboard mission). Not faked.

## 11. What did Main VÉLØ do?

36/36 races, full field. 16.7% SR (6/36), 41.7% FR (15/36) — identical to
Old VELO WIN, since both read the top of the same `score_race_velo_prime()`
output generated by the report-only scorer built earlier today
(`build_report_only_legacy_verdicts_2026_07_06.py`). Best winner
Goodgollymissholly @ 5.5, worst miss Vietnorm @ 1.53.

## 12. Why Sigma had to use runtime artifacts instead of velo_verdicts

Confirmed live: Supabase's `velo_verdicts` table has **zero** rows for
2026-07-06, and `racing_horse_runs` has zero rows too — no live production
scorer (`run_prime_today.py`) ran today. Rather than stop learning or wait for
tomorrow, Sigma was run in classification
`SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS` (not
`OFFICIAL_LIVE_VERDICT_SIGMA`): joining the day's already-generated runtime
model-suggestion rows (report-only Main/Old VÉLØ scorer, New Build two-lane
readiness, Champion Intent Shadow scorecard) against parsed RP results by
race_id + horse_id (ID_MATCH: 1,215 rows; name-fallback NAME_FALLBACK_MATCH:
301 rows, audited; NO_RESULT_MATCH: 131 rows — mostly the one parse-error race
plus non-runners/debutants with no result row). This is valid learning
evidence, not live-staking proof.

## 13. Whether full learning artifacts were generated

Yes. All of: per-lane results (CSV/MD/JSON), Sigma runtime learning
(summary/audit/events CSV), canonical model scorecard runtime candidate
(1,647 rows), canonical learning events runtime candidate (325 rows). File
list in the final response.

## 14. Why promotion remains blocked

Every row across every output in this mission carries
`promotion_eligible=false` and, on learning events,
`promotion_block_reason=JULY06_RUNTIME_ARTIFACT_LEARNING_NOT_PROMOTION_GRADE`.
This is runtime-artifact learning, not a canonical live-verdict Sigma run —
it is real evidence but not the promotion-grade evidence bar this system
requires (per Little Lady Rock precedent and the operator's standing rule
that promotion needs canonical proof accumulated across multiple days under
the normal live pipeline, not a single backfilled runtime day). No Supabase
writes have been made; this stays local pending explicit operator
authorisation for persistence.
