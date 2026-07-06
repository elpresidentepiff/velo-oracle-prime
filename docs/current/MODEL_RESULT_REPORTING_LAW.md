# MODEL RESULT REPORTING LAW

Adopted 2026-07-05 after a chain of contradictory corrections on race 922118 (Little Lady Rock,
SP 41.0, 2026-07-05, Market Rasen) that repeatedly collapsed distinct truth layers into one word,
"result." PR #127 was frozen as an incident record rather than merged because its own correction
history became internally inconsistent. This law exists so no future report repeats that failure.

A single horse, in a single race, can simultaneously be:
- rank #1 by a calibrated model,
- classified `NO_EDGE` (or any other non-executable class) by a decision-policy layer,
- not authorized for any stake,
- the actual race winner,
- absent from any Supabase-persisted scorecard table,
- and visible on the operator dashboard.

All six can be true at once. None contradicts another. Reporting only one of them as "the result"
is how the July 05 model-comparison report went through three rounds of correction.

## The law

1. **Model rank is not policy decision.** A model's own `predict_proba`/`prob` ranking is a
   different fact from what a decision-policy layer (e.g. `new_build_velo/policy_v1.py`)
   classifies that rank as. Report both, explicitly, never one standing in for the other.

2. **Policy decision is not staking result.** A `NO_EDGE`/`SUPPRESS`/`WIN_TRUST`/`FRAME_TRUST`
   classification is a paper classification only. Nothing in this system is ever staked live.
   Do not describe a policy-suppressed pick's race outcome as a "loss" or "win" in staking
   terms — describe it only in model-rank-vs-result terms.

3. **Dashboard display is not proof unless source path and field are named.** Any claim about
   "what the dashboard shows" must cite the exact function and field in
   `scripts/ops/new_build_dashboard_server.py` (or whichever server renders the operator's actual
   view) that produces it — never assumed from the nearest-looking local artifact.

4. **A proxy score is not calibrated model output.** Feature-engineering inputs that feed a model
   (e.g. `passport_strength_score`, an input to New Build's Lane A/B/C models, not their output)
   must never be ranked and reported as if they were the model's own prediction.

5. **No model "hit" claim without all seven of:** source path, race_id, horse_id, rank, score,
   odds (SP decimal), result, and policy decision — named together, for that specific pick, in the
   same sentence or table row.

6. **Every model-result report must print odds (SP decimal)** next to every pick. Strike rate
   alone hides value-discovery events — a single long-priced winner can outweigh several
   short-priced ones economically, even in a report that is not itself a staking/ROI analysis.

7. **Ties must be explicit and cannot be silently resolved by Python/default ordering.** If a
   field's maximum value is shared by more than one runner in a race, the report must say so and
   state the tie-break rule used — never let `sorted()`/`max()`'s incidental behavior on ties stand
   in as if it were a meaningful pick. (Confirmed real-world case: `sqpe_no_rpr_shadow_prob` produced
   an 11-way tie across an entire field in race 922122 on 2026-07-05, and three different code paths
   in this same repository resolved that tie three different ways, none of them a designed rule.)

8. **Supabase is canonical for persisted VÉLØ/Sigma/results, but not for local New Build dashboard
   rank unless New Build's output is actually persisted there.** As of 2026-07-05, `velo_verdicts`
   stores Main VÉLØ's own prediction and the `sqpe_no_rpr_shadow_prob` shadow field, but New Build's
   Lane A/B/C ranks and `policy_v1` decisions exist only in local files
   (`data/new_build/reports/two_lane_readiness_{date}.json`). Checking Supabase alone cannot settle
   a New Build claim — the local artifact must be traced and named.

9. **Dashboard-visible rows must be traced to the exact artifact/API**, not inferred from a
   plausible-looking file. Confirm by reading the server code that actually serves the operator's
   browser, not by pattern-matching a JSON file that happens to have similar-looking fields.

## Required table schema for any model-comparison report

`date, race_id, course, off_time, model_name, lane_name, source_path, source_field, sort_direction,
rank, horse, horse_id, score, sp_dec, result_position, win, frame, policy_decision,
stake_authorised, dashboard_visible, learning_class, tie_status, notes`

A row missing any of these fields is not accepted into a report. See
`scripts/ops/build_canonical_model_scorecard.py` for the reference implementation and
`data/reports/canonical_model_scorecard_{date}.csv` for its output.
