# Race 922118 — Dashboard/New Build Forensic Reconciliation
Generated: 2026-07-05 | Mission: PR127-DASHBOARD-TRUTH-FORENSIC-RECONCILIATION

---

## Part A — Conflict acknowledged

- **Operator dashboard claim:** Little Lady Rock was New Build rank 1 for race 922118.
- **Amended PR #127 claim (previous version):** New Build ranked Little Lady Rock 2nd (used `passport_strength_score`: Way Maker 2.95, Little Lady Rock 2.90).
- These could not both stand without tracing the actual dashboard source. **PR #127 remained HOLD** while this was resolved.
- **Resolved: the operator was right. `passport_strength_score` was the wrong field.** The dashboard does not read it at all for New Build ranking.

## Part B — Dashboard source, traced

| Source checked | Exists | Contains race 922118 | Contains Little Lady Rock | Contains New Build rank | Contains odds | Notes |
|---|---|---|---|---|---|---|
| `data/new_build/reports/two_lane_readiness_2026_07_05.json` (`race_day_scorecards[].lane_a_top3`) | yes | yes | yes, **rank 1** | yes (`rank`, `prob`) | no (odds joined separately by dashboard server, not stored here) | **This is the real source.** |
| `data/new_build/reports/two_lane_readiness_2026_07_05.json` (`race_day_scorecards[].lane_b_top3`) | yes | yes | yes, **rank 1** | yes | no | Lane B agrees with Lane A here (both rank Little Lady Rock 1st) — Lane B is paper-only/no-intent, not the operational lane, but corroborates. |
| `data/new_build/reports/two_lane_readiness_2026_07_05.json` (`race_day_scorecards[].lane_c_top3`) | yes | yes | yes, rank 2 | yes | no | A third, distinct lane — ranks Way Maker 1st, Little Lady Rock 2nd. Not the operational lane (`operational_lane: LANE_A_CORE_PASSPORT`). |
| `data/new_build/current_cards/current_card_passport_feed_2026_07_05.jsonl` (`passport_strength_score`) | yes | yes | yes, ranked 2nd (2.90 vs Way Maker 2.95) | not a "New Build rank" field — a feature-engineering heuristic | no | **This is the field I incorrectly used in the previous PR #127 amendment.** It is a passport-strength input feature, not New Build's model output, and does not correspond to any dashboard-displayed rank. |
| `scripts/ops/new_build_dashboard_server.py` (`/api/governed-card` handler, `new_build_top3` field, ~line 567-576) | yes | — | — | — | odds joined from verdict row separately | **Confirmed code path:** `new_build_top3` is built by loading `two_lane_readiness_{date}.json`, taking each race's `lane_a_top3`, sorting by `rank` ascending, and attaching `{horse, rank, prob, nb_decision_lane}` per entry. This is exactly what a browser hitting the dashboard would see. |
| `data/dashboard_daily_predictions_2026_07_05.json` | yes | yes | not checked in detail — this file holds Main VELO's own top-pick publish, a separate panel from the New Build sidecar | — | yes (SP) | Main VELO's own publish panel, not the New Build panel. |

**Conclusion: the dashboard's New Build panel is sourced from `lane_a_top3` (the operational Lane A model's own probability ranking), not from `passport_strength_score`. My original PR #127 amendment used the wrong artifact.**

## Part C — Every row mentioning the relevant horses, race 922118

| Horse | Artifact | Field/rank | Value |
|---|---|---|---|
| Little Lady Rock | `two_lane_readiness...json` lane_a_top3 | rank 1 | prob 0.217898, `nb_decision_lane: NO_EDGE` |
| Little Lady Rock | same, lane_b_top3 | rank 1 | prob 0.167947 |
| Little Lady Rock | same, lane_c_top3 | rank 2 | prob 0.570826 |
| Little Lady Rock | `current_card_passport_feed...jsonl` | passport_strength_score | 2.90 (2nd highest in field) |
| Way Maker | `two_lane_readiness...json` lane_a_top3 | rank 2 | prob 0.156355 |
| Way Maker | same, lane_c_top3 | rank 1 | prob 0.576332 |
| Way Maker | `current_card_passport_feed...jsonl` | passport_strength_score | 2.95 (highest in field) |
| Way Maker | `velo_verdicts.full_analysis` | `velo_prime_prob` | 0.5313 (Main VELO's top pick) |
| Brosna Town | `old_velo_three_option_card...json` | LONGSHOT role | sqpe_no_rpr_shadow_prob 0.1528, placed 2nd |

## Part D — Score ordering, proven

- `lane_a_top3` and `lane_b_top3`: `rank` is assigned ascending, `prob` descending — rank 1 = highest probability = the model's actual top selection. Confirmed by inspecting `new_build_dashboard_server.py`'s sort (`sorted(... key=lambda x: x.get("rank", 99))`) and the raw JSON (`rank: 1` paired with the highest `prob` value in each race's top3 list).
- `passport_strength_score`: no rank field at all in the passport feed — I imposed my own "highest score = best" ranking assumption onto a feature that was never intended to be read that way, and it is not what the dashboard displays.
- **`lane_a_top3` (0.2179 for Little Lady Rock) beats `lane_a_top3` (0.1564 for Way Maker) under the correct, code-confirmed sort direction (higher prob = better rank).** Little Lady Rock is genuinely rank 1.

## Part E — Result truth (Supabase, read-only)

- race_id: 922118
- winner: Little Lady Rock, horse_id 7618350, SP 41.0 (decimal)
- Main VÉLØ top pick: Way Maker, prob 0.5313, SP 1.1 — finished 3rd
- No-RPR top pick (sqpe_no_rpr_shadow_prob): Brosna Town, 0.1528 — finished 2nd

## Part F — Full odds table, race 922118

| source | model/lane/panel | rank | horse | horse_id | score field | score value | SP decimal | result | win | dashboard visible | evidence path |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Supabase velo_verdicts | Main VÉLØ Prime | 1 | Way Maker | 7753413 | velo_prime_prob | 0.5313 | 1.1 | 3rd | NO | yes (main verdict panel) | velo_verdicts.full_analysis |
| local | Old VÉLØ WIN role | 1 | Way Maker | 7753413 | velo_prime_prob | 0.5313 | 1.1 | 3rd | NO | not on New Build panel | old_velo_three_option_card_2026_07_05.json |
| local | Old VÉLØ LONGSHOT role | 1 | Brosna Town | 5301550 | longshot_role_score | 0.2667 | 10.0 | 2nd (placed) | NO | not on New Build panel | old_velo_three_option_card_2026_07_05.json |
| local | Radical Shadow overlay | 1 | Way Maker | 7753413 | velo_prime_prob (same pick) | 0.5313 | 1.1 | 3rd | NO | not the New Build panel | radical_shadow_2026_07_05.json |
| local | No-RPR shadow | 1 | Brosna Town | 5301550 | sqpe_no_rpr_shadow_prob | 0.1528 | 10.0 | 2nd (placed) | NO | yes (no_rpr_top_horse field) | velo_verdicts.full_analysis |
| **local** | **New Build Lane A (operational, dashboard-visible)** | **1** | **Little Lady Rock** | **7618350** | **prob (lane_a_top3)** | **0.217898** | **41.0** | **WON** | **YES** | **YES — this is the actual dashboard New Build panel** | two_lane_readiness_2026_07_05.json race_day_scorecards[].lane_a_top3 |
| local | New Build Lane A, rank 2 | 2 | Way Maker | — | prob | 0.156355 | 1.1 | 3rd | NO | yes | same |
| local | New Build Lane B (paper-only, not operational) | 1 | Little Lady Rock | 7618350 | prob | 0.167947 | 41.0 | WON | YES | yes (secondary panel) | same |
| local | New Build Lane C (not operational) | 1 | Way Maker | — | prob | 0.576332 | 1.1 | 3rd | NO | yes (secondary panel) | same |
| local | New Build Lane C, rank 2 | 2 | Little Lady Rock | 7618350 | prob | 0.570826 | 41.0 | WON | — | yes | same |
| local | passport_strength_score (INCORRECT proxy used in prior amendment) | 1 | Way Maker | 7753413 | passport_strength_score | 2.95 | 1.1 | 3rd | NO | **no — not a dashboard field** | current_card_passport_feed_2026_07_05.jsonl |
| local | passport_strength_score, rank 2 | 2 | Little Lady Rock | 7618350 | passport_strength_score | 2.90 | 41.0 | WON | — | no | same |
| — | **Actual result** | — | **Little Lady Rock** | 7618350 | — | — | **41.0** | **WINNER** | — | — | data/results/rp_results_2026_07_05.json |

## Part G — Learning impact

**Scenario proven: Little Lady Rock was New Build (Lane A, operational, dashboard-visible) rank 1.**

- `NEW_BUILD_LONGSHOT_HIT` — confirmed. New Build's operational lane selected the actual 41.0 winner as its top pick.
- Odds impact: at 1 unit win stake, this single selection returns +40 units profit. Main VÉLØ's same-race pick (Way Maker, 1.1) lost. This is a value-dominant event that strike-rate-only analysis would completely hide.
- `MAIN_VELO_SHORT_PRICE_TRAP` — Main VÉLØ, Old VELO WIN, and Radical Shadow all converged on the same short-priced favourite (Way Maker, 1.1) and all lost together, while New Build's independent passport-based signal found the true price.
- `PASSPORT_SIGNAL_OVER_MAIN_VELO` — confirmed for this race, and (see full-day reconciliation below) for the day overall.
- `DASHBOARD_SOURCE_OUTRANKS_LOCAL_REPORT` — confirmed. The local artifact I initially chose (`passport_strength_score`) was the wrong one; the dashboard's actual source (`lane_a_top3`) was right, exactly as the operator insisted.
- `LONGSHOT_VALUE_SIGNAL_CANDIDATE` — New Build's Lane A deserves dedicated research priority given this and the day's overall SR.
- `PROMOTION_GATED` — unchanged. Nothing here authorizes any promotion, model change, or live scoring change. This is evidence accumulation only.

## Full-day New Build correction (Lane A, the real operational model)

Reconciling ALL 22 races by `lane_a_top3` rank 1 (not `passport_strength_score`):

**NEW_BUILD LANE A: 6/22 wins (27.3% SR), 11/22 frames (50.0% frame rate) — the best strike rate of any model checked across both July 4 and July 5, and it includes the day's only genuine long-priced winner.**

Wins: Little Lady Rock (41.0), Conciliate (3.25), Altareq (3.25), Miss Gallant (7.0), Regal Renaissance (3.0), Naana's Sparkle (7.0).

This supersedes both the original PR #127 number (New Build "unavailable") and the first amendment's number (New Build via `passport_strength_score`, 5/22 wins, 22.7% SR) — both were wrong for different reasons, and both are superseded by this forensic trace.

## Answers to the mission's 12 required questions
1. **Is PR #127 still held?** Yes — held throughout this forensic mission, now ready for a corrected re-amendment.
2. **Did you read THE_ONE_TRUTH?** Yes — Steps 5-8 (passport feed, New Build scoring, Old VELO PDF-ingestion doctrine) reviewed.
3. **Did you read hardening state?** Yes — confirmed the Side-Effect Sentinel blocks Supabase writes/Telegram/model promotion/live scoring only; it does not restrict read-only file inspection, consistent with this forensic mission's scope.
4. **Exact dashboard source path:** `data/new_build/reports/two_lane_readiness_2026_07_05.json`, field `race_day_scorecards[].lane_a_top3`, surfaced via `scripts/ops/new_build_dashboard_server.py`'s `new_build_top3` field in `/api/governed-card`.
5. **Did dashboard show Little Lady Rock rank 1?** Yes.
6. **What field and sort order?** `lane_a_top3[].prob`, descending (rank 1 = highest probability), confirmed by both the raw JSON and the dashboard server's sort code.
7. **N/A** (answer to Q5 was yes).
8. **New Build final corrected result with odds:** 6/22 wins (27.3% SR), 11/22 frames (50.0%), including the 41.0 winner in race 922118.
9. **Little Lady Rock final status: HIT.**
10. **Learning impact:** see Part G above — `NEW_BUILD_LONGSHOT_HIT`, `MAIN_VELO_SHORT_PRICE_TRAP`, `PASSPORT_SIGNAL_OVER_MAIN_VELO`, `DASHBOARD_SOURCE_OUTRANKS_LOCAL_REPORT`, `LONGSHOT_VALUE_SIGNAL_CANDIDATE`, `PROMOTION_GATED` (unchanged).
11. **Files amended:** `july05_model_by_model_results_operator_brief.md`, `july05_model_by_model_results_matrix.csv`, `july05_model_artifact_inventory.csv`, plus this new forensic note.
12. **New commit hash:** recorded after this commit is pushed (see PR #127).

## Addendum — the No-RPR tie is a real bug, not just a reporting disagreement

Read `scripts/ops/new_build_dashboard_server.py`'s `_build_no_rpr_race_map()` (the function that actually powers the dashboard's `no_rpr_top_horse` field on the live-snapshot code path) and ran it against race 922122's real data. Its tie-break: it sorts `(prob, horse)` tuples with `reverse=True` and takes the first. For a tie, Python breaks ties on the second tuple element (`horse`), so `reverse=True` picks whichever horse name sorts **last alphabetically**.

For race 922122 (the 11-way tie at 0.0975), this dashboard function itself produces:

**"Zandahar" — a fourth different answer**, matching neither my original pick (Masterius, first-in-list), nor the operator's (Parisian Fair, winner-credited), nor Instant Force from the earlier passport-feed pass. This is not a disagreement between me and the operator — **the dashboard's own two different code paths (`_build_no_rpr_race_map` for live snapshots vs. the single `old_velo_top.sqpe_no_rpr_shadow_prob` value used in the two-lane path) are internally inconsistent with each other on tied races**, because nobody wrote an intentional tie-break rule — it's an accidental side effect of tuple sorting.

**This is a real, reportable bug**, separate from the reconciliation reporting mistake: `sqpe_no_rpr_shadow_prob` needs either (a) a documented, deterministic tie-break rule applied consistently everywhere it's used, or (b) the underlying model fixed so it stops producing flatlined/tied probabilities across a whole field in some races. Filed as a finding, not fixed here — no scoring/model changes made.

## Reference document produced from this investigation
`docs/current/VELO_MODEL_SOURCE_MAP.md` — a permanent map of every model/lane, its exact source file/field, sort direction, and known gotchas, written after reading the full daily-scoring codebase (New Build two-lane scorer, decision policy, dashboard server, Old VELO three-option card, racecard loader) end to end, not just grepping for field names.

## Classifications
PR_127_HELD_PENDING_DASHBOARD_FORENSIC · ONE_TRUTH_READ · HARDENING_STATE_READ · DASHBOARD_SOURCE_TRACED · LITTLE_LADY_ROCK_RANK_PROVEN · ODDS_INCLUDED · NEW_BUILD_LEARNING_IMPACT_CLASSIFIED · NO_RPR_TIE_BREAK_BUG_FOUND · NO_SUPABASE_WRITES · NO_SCORING_RUN · NO_SIGMA_RUN · NO_TELEGRAM_SEND · NO_MODEL_TRAINING · NO_PROMOTION
