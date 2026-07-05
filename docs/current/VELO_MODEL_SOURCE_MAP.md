# VÉLØ Model & Dashboard Source Map

Written 2026-07-05 after a chain of reconciliation mistakes on race 922118 (Little Lady Rock, 41.0)
where a feature-engineering input was mistaken for a model's real output. This document exists so
that mistake cannot happen again: for every model/lane VÉLØ can show a picture on, it states the
exact file, the exact field, the sort direction, and any known gotcha — verified by reading the
actual scoring code, not by inspecting a JSON file and guessing.

**Rule going forward: no model comparison report may cite a number without stating the file path
and field name it came from, in the report itself, next to the number.**

---

## Main VELO Prime (the live scoring engine)

- **Scoring code:** `scripts/ops/run_prime_today.py` → `score_race_velo_prime()`. Persists to Supabase
  `velo_verdicts` (one row per race, `full_analysis` JSON blob with a `predictions` list, one dict
  per runner, keyed by `horse_id`/`race_id`).
- **Real field:** `velo_prime_prob` per runner in `full_analysis.predictions[]`. Top pick per race =
  highest `velo_prime_prob` (this is also `top_rank_horse_id` at the race level).
- **Result truth:** `data/results/rp_results_{date}.json`, matched by `race_id`/`horse_id`.
- **Race-type/field-size/RPDC fields:** persisted alongside via `_build_race_type_fields()` in
  `app/services/velo_prime_service.py` (added SIGMA-26) — this file must be kept in sync between the
  dirty operational repo and `main`; it was found stale once (2026-07-05) and had to be re-synced.

## Old VELO (WIN / PLACE / LONGSHOT roles)

- **Scoring code:** `scripts/ops/build_old_velo_three_option_card.py`. Reads the **local runner
  snapshot file** (`data/runner_snapshots_{date}_{run_id}.jsonl` — written by `run_prime_today.py`
  when NOT run with `--verdicts-only`/`--no-runner-snapshots`), not `velo_verdicts` directly.
- **WIN role** = highest `velo_prime_prob` in the race → **identical pick to Main VELO Prime**, always.
  If Old VELO WIN and Main VELO ever show different picks for the same race, that is a bug, not a
  distinct signal.
- **PLACE role** = highest `place_prob`, excluding the WIN horse.
- **LONGSHOT role** = highest `_longshot_score()` (a weighted blend of `longshot_prob`,
  `market_deception_score`, `improvement_score`, `sqpe_no_rpr_shadow_prob`, plus an SP-band bonus),
  restricted to `sp_dec >= 4.5` when possible, excluding WIN/PLACE horses.
- **Requires a runner snapshot to exist for the date** — if scoring ran with `--verdicts-only`, this
  script cannot run at all (`OLD_VELO_THREE_OPTION_BLOCKED`).

## New Build — Lane A, Lane B, Lane C (THIS is where the mistake happened)

- **Scoring code:** `scripts/ops/new_build_two_lane_score.py` → `score_date()`. Loads three real,
  trained model bundles from `.pkl` files:
  - Lane A: `data/new_build/models/core_v0_or_passport/core_v0_or_passport_model.pkl` (30 features,
    Core+Passport — **the operational lane whenever intent coverage is below 80%**, which is every
    morning read, since intent features are historical (race_id, horse) pairs that never match a
    future card).
  - Lane B: `data/new_build/models/core_v0_or_passport_intent/model.pkl` (45 features, adds Intent —
    paper-only unless intent coverage clears the 80% gate).
  - Lane C: `data/new_build/models/soft_label_challenger/champion_model.pkl` (a separate challenger
    model, not operational).
  - Each is scored via `model.predict_proba(X)[:, 1]` (or a sigmoid over a native LightGBM booster
    for `lgb_native_booster` type) — **these are real, calibrated model probabilities**, not feature
    heuristics.
- **Real field, per race, written to `data/new_build/reports/two_lane_readiness_{date}.json`:**
  `race_day_scorecards[].lane_a_top3` / `.lane_b_top3` / `.lane_c_top3` — each entry
  `{rank, horse, prob, nb_decision_lane}`. **`rank` is ascending, `prob` is descending — rank 1 is
  the model's actual top selection.**
- **`nb_decision_lane`** (`WIN_TRUST` / `FRAME_TRUST` / `SUPPRESS` / `LOW_DATA` / `NO_EDGE`) comes from
  `new_build_velo/policy_v1.py::apply_policy_v1()`, anchored to **Lane B's** probability plus
  `passport_strength_score` as a secondary confidence check. A rank-1 pick can still be classified
  `NO_EDGE` if it doesn't clear the policy's confidence thresholds — this happened for Little Lady
  Rock on 2026-07-05 (Lane B prob 0.168, just under the 0.17 `FRAME_TRUST` threshold), meaning New
  Build's own governance did **not** flag it as an executable-confidence pick even though its raw
  ranking had it first. Do not conflate "rank 1" with "the policy would have staked it."
- **THE FIELD THAT IS NOT NEW BUILD'S MODEL OUTPUT:** `passport_strength_score`, found in
  `data/new_build/current_cards/current_card_passport_feed_{date}.jsonl`. This is a feature-
  engineering heuristic (career runs, win/place rate, jockey continuity, OR trajectory — see
  `passport_summary`/`passport_live_features` in the same row) fed **into** Lane A/B/C as one of many
  input columns. It is not itself a model prediction, has no dashboard-facing "rank" semantics, and
  is not what `new_build_dashboard_server.py` reads for its New Build panel. **Do not rank races by
  this field and call it "New Build's result."** This was the exact mistake made on 2026-07-05.
- **Dashboard rendering:** `scripts/ops/new_build_dashboard_server.py`,
  `_build_governed_card_from_two_lane_readiness()`, ~line 345: reads `card.get("lane_a_top3")`
  directly and exposes it via the verdict's `champion_probability`/`velo_prime_prob`/`rank` fields
  (confusingly reusing Main-VELO-style key names for New Build data on this code path — read the
  `new_build_lane` field to know which model actually produced the row). A second render path,
  `_build_governed_card_from_live_snapshots()` (~line 553+), exposes a separate `new_build_top3` field
  built the same way, from the same `lane_a_top3` source.

## SQPE No-RPR shadow — KNOWN BROKEN TIE-BREAK, do not trust a single number without checking for ties

- **Field:** `sqpe_no_rpr_shadow_prob`, present per runner in `velo_verdicts.full_analysis.predictions[]`
  (computed inside Main VELO's own scoring pass, not a separate script).
- **Problem, confirmed by direct testing (2026-07-05):** this probability sometimes flatlines to an
  identical value across an entire field (e.g., race 922122 on 2026-07-05: all 11 runners at exactly
  0.0975 — the shadow model produced zero discriminating signal for that race). **Nobody has written
  a deterministic tie-break rule**, and different code paths in the same repo disagree:
  - A naive first-in-list sort → picks whichever horse the API happened to return first.
  - `new_build_dashboard_server.py::_build_no_rpr_race_map()` → sorts `(prob, horse)` tuples with
    `reverse=True`, which on ties falls back to **reverse-alphabetical horse name** (an accident of
    Python tuple sorting, not a designed rule) — confirmed to pick "Zandahar" for race 922122, a
    horse nobody would call the "real" no-RPR pick by any principled standard.
  - `radical_shadow_{date}.json`'s `old_velo_top.sqpe_no_rpr_shadow_prob` isn't even a race-wide
    ranking — it's just the no-RPR value attached to Main VELO's own top pick, a different concept
    entirely from "what would the no-RPR model pick on its own."
- **Before reporting any No-RPR strike rate, check for ties first** (`max()` count > 1 in a race) and
  either exclude tied races or explicitly disclose the tie-break used. **This needs an actual code
  fix** (a documented, single tie-break rule, or fixing whatever produces flatlined probabilities) —
  tracked as an open item, not fixed as part of this documentation pass.

## Radical Shadow, Tri-Lane, Deep Race Agent, Course Master

- All four are **governance/context overlays that read the same top pick Main VELO already made** —
  none of them independently rank runners. `radical_shadow_{date}.json`'s `decisions[]` and
  `tri_lane_stress_test_{date}_v2.json`'s per-race `tri_lane` object attach diagnostic flags
  (midprice-shadow action, passport-strength context, execution-lane gating) to the existing Main
  VELO/Old-VELO-WIN pick. They cannot "beat" or "lose to" Main VELO on strike rate because they are
  not making a different selection — asking "did Radical Shadow pick better than Main VELO" is a
  category error, not a metric.
- Deep Race Agent covers a curated subset of races (not full-field) and Course Master operates at
  course level, not runner level — neither produces a per-runner reconcilable pick at all.

## Router lanes (V1_BASE, V2_CLASS4_ONLY, V6_GOLD_SEAM)

- **Source:** `data/router_shadow_audit_latest.csv` (cumulative, whole shadow-tracking history) and
  `data/velo_innovation_protocol_1k_deduped.csv` (per-row candidate/win/placed flags, filterable by
  `date` column for a single day's figure).
- **Never present a cumulative router SR as if it were today's SR** — filter by `date` first for a
  daily figure, and always report both numbers side by side with the distinction stated explicitly.

## The one rule that would have prevented all three mistakes on 2026-07-05

Before citing any model's "result," answer three questions in the report itself:
1. What file and field, exactly, did this number come from?
2. Is that field the same one `new_build_dashboard_server.py` (or whichever server renders the
   operator's actual view) reads for the panel being discussed?
3. If the field can tie, what happens on a tie, and did this race hit one?

If any of the three isn't answered in writing, the number does not go in the report.
