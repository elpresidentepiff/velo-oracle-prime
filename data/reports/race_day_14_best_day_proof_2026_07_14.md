# RACE-DAY-14-BEST-DAY-PROOF-01 — 2026-07-14 Forensic Verdict

Read-only forensic mission. No scoring, learning, promotion, or model change
occurred. All figures below are traced to primary artifacts; see
`race_day_14_provenance_manifest_2026_07_14.json` for the full source
path/field/join-method table for every headline claim.

## Operator Dashboard

**1. Was this the best verified day?**
Statistically, yes — #1 by strike rate and win count in the recorded 37-day
ledger, and #1 by theoretical SP ROI among the two ledger dates that
actually carry usable SP data (2026-07-10 and 2026-07-14; every other date
is missing SP data, not tied or beaten on ROI). Formally, the verdict is
**BEST_VERIFIED_RECENT_DAY**, not BEST_VERIFIED_DAY_EVER. It falls short of
the unconditional "ever" claim for two proven reasons, not speculation: (a)
the code that actually produced the day's racecard artifact is **proven** to
differ from what's committed to git (an uncommitted GB/IRE region-tagging
fix in `src/velo/racecard_loader.py` was demonstrably active), so full
code-level reproducibility isn't currently possible from git history alone;
and (b) the day's result completeness depended on a manual, one-off operator
workaround (see Q7) rather than the pipeline's own canonical path.

**2. Which model won?**
Old VELO (live), by a wide margin. Old VELO: 23 wins / 42 eligible races
(54.8% SR), 31 total frames (73.8% frame rate). No-RPR (shadow): 10 wins / 42
(23.8% SR), 23 frames (54.8%). New Build and Champion Intent Shadow produced
no scoreable pre-race pick for this date (see Q7/Q8) and are excluded from
head-to-head comparison.

**3. How many winners and frames?**
Old VELO: **23 winners, 31 total frames** (23 wins + 8 placed-only).
No-RPR: 10 winners, 23 total frames (10 wins + 13 placed-only).

**4. Which horses won?**
23 Old VELO winners across 6 courses (Fast Track, What A Tahoo, Pendella,
Kitsune Power, The Sweet Escape at Beverley; Luker's Tipple, Tolka Row at
Downpatrick; Jaan Ki Tukri, Tallahassee Lassie, Star Velocity, Tokyo Joe,
Homeland, Liveinthelight at Ffos Las; Celtic Motif, Cause I Like You, Gaoth
Chuil, Eagle Fang at Killarney; Emerald Bay, Dottie Diamond, Melody De Vega
at Leicester; Maltese Cross at Longchamp; George Wickham, Classy Clarets at
Wolverhampton (AW)). Full list with SP and assigned product in
`race_day_14_old_velo_winners_2026_07_14.csv`.

**5. Which horses placed?**
8 placed-only selections: Cool Native (3rd), Playtime (3rd) at Downpatrick;
Dolly Hello (3rd) at Killarney; Musical Soldier (2nd) at Leicester; Pink
Panthera (2nd), Double Major (3rd) at Longchamp; Desert Belle (2nd), Wilbur
(2nd) at Wolverhampton (AW). Full list in
`race_day_14_old_velo_placed_only_2026_07_14.csv`.

**6. Which races were missed?**
11 misses, none of which any other lane in this evidence caught either
(10/11 "another_model_found_winner: NONE"; the one exception — Leicester
5.04, pick Marisitta, finished 5th, winner Manhattan Chute @ 6.5 — was found
by No-RPR). Full list with finishing positions and winner SP in
`race_day_14_old_velo_misses_2026_07_14.csv`.

**7. What remains unproven?**
- **Per-race prediction timing for the earliest race on the card** could
  not be fully proven from local artifacts: the verdict file was written
  ~14:07 UTC and the earliest race (Leicester 923082) is recorded with
  off_time "13:54" — this mission could not independently confirm whether
  that field is local BST or UTC, so exact minute-level leakage-safety for
  that specific race is not conclusively proven (file-level ordering across
  the whole day is otherwise clean: verdicts at ~14:07 UTC, results capture
  not until ~23:11 UTC).
- **The July 13 comparison the mission brief asked for could not be
  performed at all** — `data/model_comparison_ledger.csv` has no rows for
  2026-07-13.
- **The stale-manifest root cause is proven, but the exact sequence of
  collector invocations that produced it is not** — no shell history was
  available to confirm exactly when/why a smaller URL-list invocation
  overwrote the larger one.
- **New Build's specific missing scoring step** is identified only by
  elimination (readiness/feature layer completed; no scored card exists),
  not pinpointed to one exact skipped command.
- **Brier/log-loss calibration metrics** could not be computed — only the
  top pick's probability per race was available in the copied evidence, not
  a full-field probability distribution.
- **Causal attribution of Old VELO's edge over No-RPR specifically to RPR
  access** is plausible but not proven — the two lanes differ in more than
  just RPR presence/absence (see Phase 5 causation note in the JSON report).

**8. What must not change because of one day?**
Live model weights remain FROZEN. No promotion occurred and none is
recommended by this mission. V6_GOLD_SEAM remains LANE_FROZEN (07-14 added 5
rows to its cumulative count — n 89→94 — but did not move its frame rate
above the 70% floor: still 62.8%). No live staking occurred (Step 17 was
SIM/PAPER only). No router unfreeze, no HFS mutation, no scorer change, no
Playbook G rerun, and no LEARNING-LOOP-01B work took place as part of this
mission or as part of the 2026-07-14 nightly run itself (see Phase 8). One
exceptional day does not, on its own, justify loosening any of these gates.

---

## Phase 1 — Race universe reconciliation

**Classification: `RACE_UNIVERSE_RECONCILED`**

| Metric | Count |
|---|---|
| Morning racecard races | 43 |
| Old VELO verdicts | 43 |
| Raw racecard HTML files | 45 (43 races + 2 course/index pages) |
| Manifest.json captures recorded | 3 (bug — see Phase 10) |
| RP results parsed | 43 |
| Sigma evaluated rows | 42 |
| Nightly learning matched races | 43 |

- **Why 45 HTML files = 43 races**: 2 of the 45 files are course/index
  listing pages incidentally captured during the browse session, not
  individual race pages.
- **Why manifest had only 3 entries**: proven code bug in
  `racing_post_account_collector.py`'s batch `capture()` — the manifest
  write filters merged captures down to the *current invocation's* URL list
  only, so a later, smaller invocation (3 Longchamp URLs) silently
  overwrote the larger manifest. Full autopsy in
  `race_day_14_manifest_gap_autopsy_2026_07_14.md`.
- **How the 43 URLs were reconstructed**: regex extraction of `<link
  rel="canonical">` from all 45 raw HTML files, `/racecards/`→`/results/`
  substitution, 2 index-page URLs correctly excluded.
- **Why Sigma has 42 races**: race 923388 (Wolverhampton (AW), 19:55) — Old
  VELO's specific top pick "Wonderful Wendy" was declared a non-runner
  before the off. The race itself ran (won by Luan, SP 2.62); Sigma
  correctly excludes races where the *predicted* horse never ran from its
  evaluated denominator.
- **Why nightly learning has 43 races**: its `OUTCOME_ONLY_EOD_REPLAY` logic
  is a binary WIN/LOSS classifier with no non-runner exclusion and no
  separate PLACE/frame bucket — it counts 923388 as one of its 20 "losses"
  (20 = Sigma's 8 PLACED + 11 MISS + this 1 non-runner). This is a taxonomy
  difference between the two systems, not a data defect in either.
- **Duplicates / exclusions / void races**: none found beyond the single
  non-runner case above.

Full row-by-row table: `race_day_14_race_universe_2026_07_14.csv`

## Phase 2 — Result and timing truth

See `race_day_14_provenance_manifest_2026_07_14.json` for the complete
provenance table (source path, field, race ID join method) behind every
headline number. Key findings:

- No duplicate prediction runs (43 verdict rows, 43 unique race_ids).
- No cross-date contamination detected in the joins performed.
- No omitted race silently improved the denominator (the 42-vs-43 gap has a
  specific, artifact-proven cause — see Phase 1).
- Post-result-rescoring check is file-mtime-level PROVEN for the day as a
  whole (predictions ~14:07 UTC, results ~23:11 UTC, >9hr gap) but not
  minute-level proven for the single earliest race on the card (see Q7).

## Phase 3 — Four-model result book

Summary (full detail in `race_day_14_four_model_summary_2026_07_14.csv`):

| Model | Eligible | Wins | Placed-only | Frames | Misses | SR | Frame Rate | Avg Winner SP | Theoretical 1u ROI |
|---|---|---|---|---|---|---|---|---|---|
| Old VELO (live) | 42 | 23 | 8 | 31 | 11 | 54.8% | 73.8% | 4.15 | +127.4% |
| No-RPR (shadow) | 42 | 10 | 13 | 23 | 19 | 23.8% | 54.8% | 2.53 | -39.7% |
| New Build | — | — | — | — | — | — | — | — | NO_PRE_RACE_SCORECARD |
| Champion Intent Shadow | — | — | — | — | — | — | — | — | NO_PRE_RACE_SCORECARD |

Winners/placed/misses CSVs:
`race_day_14_old_velo_winners_2026_07_14.csv`,
`race_day_14_old_velo_placed_only_2026_07_14.csv`,
`race_day_14_old_velo_misses_2026_07_14.csv`,
`race_day_14_no_rpr_winners_2026_07_14.csv`,
`race_day_14_no_rpr_placed_only_2026_07_14.csv`,
`race_day_14_no_rpr_misses_2026_07_14.csv`.

New Build / Champion Intent gap explanations:
`race_day_14_new_build_NO_DATA_2026_07_14.md`,
`race_day_14_champion_intent_NO_DATA_2026_07_14.md`.

## Phase 4 — Old VELO product breakdown

| Product | n | Wins | Placed-only | Frames | Misses | SR | Frame Rate | Avg Winner SP | Theoretical SP ROI |
|---|---|---|---|---|---|---|---|---|---|
| WIN_ONLY | 6 | 3 | 2 | 5 | 1 | 50.0% | 83.3% | 1.29 | -35.5% |
| EW_CANDIDATE | 2 | 2 | 0 | 2 | 0 | 100.0% | 100.0% | 17.91 | +1691.5% |
| VISION_ONLY | 22 | 14 | 2 | 16 | 6 | 63.6% | 72.7% | 2.90 | +84.7% |
| PASS | 12 | 4 | 4 | 8 | 4 | 33.3% | 66.7% | 3.79 | +26.5% |

**Verified: WIN_ONLY = 3/6 wins ✓ (direct match). EW_CANDIDATE = 2/2 placed,
2/2 won ✓ (direct match).** No FRAME_ONLY, VISION_ONLY-distinct-from-PASS
ambiguity, or UNKNOWN category rows were present — all 42 eligible races
fall into exactly one of these four `velo_assigned_product` values (sums to
42).

## Phase 5 — Old VELO vs No-RPR

- Both won: 8 races. Old VELO won / No-RPR missed: 15 races. No-RPR won /
  Old VELO missed: 2 races. Neither won: 17 races.
- Same top pick: 12 races. Different top pick: 30 races.
- Old VELO wins (23) − No-RPR wins (10) = **+13 win advantage**; SR gap
  +31.0pp; frame-rate gap +19.0pp.
- **Causation**: NOT proven to be specifically an "RPR access" effect. The
  No-RPR lane's `sqpe_no_rpr_shadow_prob` is a structurally distinct model
  output, not Old VELO with a single feature removed — the two lanes differ
  in more than RPR presence/absence, and this evidence cannot isolate which
  part of the difference is doing the work. Do not repeat "Old VELO wins
  because of RPR" as a proven fact from this mission's evidence.

## Phase 6 — "Best day ever" verdict

**Final verdict: `BEST_VERIFIED_RECENT_DAY`**

- 23/42 = 54.8% SR. Wilson 95% CI: **[39.9%, 68.8%]**, entirely above the
  ~17.1% EXPLICITLY ASSUMED null baseline strike rate. **This 17.1% baseline
  was carried over from prior session memory, not independently
  reconstructed from 2026-07-13 in this mission** — the ledger has zero
  rows for that date, so it could not be re-derived from primary evidence
  this pass.
- **One-sided exact binomial p ≈ 3.45×10⁻⁸** (P(X≥23 | n=42, p=0.171)) under
  that explicitly assumed null baseline — precise, extremely small, but
  explicitly **not zero**. Still a statistically extreme result, not a
  small-sample fluke.
- 14 July ranks **#1 by strike rate and #1 by win count in the recorded
  37-day ledger** (also #1 of 32 days with ≥20 races and #1 of 28 days with
  ≥30 races on the same strike-rate measure). It ranks **#1 by theoretical
  SP ROI among the two ledger dates containing usable SP data** (2026-07-10
  and 2026-07-14 only — every other ledger date is missing `winner_sp`
  entirely, which is a data gap, not a 0%/-100% ROI, and must not be read
  as "14 July beat 35 other days on ROI").
- **Frame rate rank: 5th**, not #1 — 2026-07-14 is not uniformly dominant
  on every single metric.
- **Previous dates were read from ledger aggregates, not fully
  re-forensically verified during this mission.** Every row of
  `race_day_14_historical_day_ranking_2026_07_14.csv` other than
  2026-07-14 itself is marked `timing_proof_status =
  NOT_RE_VERIFIED_THIS_MISSION`. This ranking is ledger-derived context,
  not a full 37-day forensic re-audit.
- **July 13 comparison could not be performed** — the ledger has no rows
  for that date at all.
- **Why not "EVER"**: (1) committed HEAD is *proven* not to equal the code
  that produced the day's racecard artifact (uncommitted
  `racecard_loader.py` region-tagging fix was demonstrably active — see
  `provenance/UNCOMMITTED_RUNTIME_CODE_PROVENANCE.json`); (2) result
  completeness depended on a manual, undocumented operator workaround, not
  the canonical pipeline path (see Phase 10).

Full historical ranking: `race_day_14_historical_day_ranking_2026_07_14.csv`

## Phase 7 — Confidence-flood and leakage check

- WIN avg VP 0.504 (n=23) vs MISS avg VP 0.405 (n=11) vs PLACED avg VP 0.413
  (n=8) — real discrimination exists between winners and losers, not a flat
  distribution.
- Expected wins from summed probabilities: 19.36 vs actual 23 wins — the
  model was mildly *underconfident* in aggregate, the opposite of an
  overfitting/leakage signal.
- 36/42 races (85.7%) cleared the 0.30 "high confidence" bar — this
  specific threshold is a low bar and shows a mild flood pattern at that cut,
  even though the WIN/MISS averages above show genuine underlying
  discrimination.
- Brier/log-loss: not computed (full-field probability distribution not
  present in copied evidence, only top-pick probabilities).
- No-leakage check: file-mtime ordering is clean for the day as a whole;
  not conclusively proven at the single-race level for the earliest race
  (see Q7).

## Phase 8 — Learning containment

43/43 matched, 23 wins / 20 losses confirmed directly from
`nightly_eod_learning_status_2026_07_14.json`. First run applied 43 engine
updates; second (idempotence) run applied 0 and skipped 43 duplicates.
`live_sentient_state_touched: false`, `shadow_state_touched: true`,
`supabase_writes_attempted: false` (in that file — the separate Step 13
`racing_horse_runs` write happened earlier and is a different, already-known
write). No scorer weights changed, no model files changed, no promotion, no
HFS mutation, and no LEARNING-LOOP-01B evidence found anywhere in this
mission's trail. This mission did **not** rerun the nightly learning script.

## Phase 9 — Router and missing-lane truth

V6_GOLD_SEAM: cumulative n=94 (up from 89 pre-07-14, +5 rows contributed
today), wins=29, SR=30.85%, frame rate=**62.77%**, required floor=70% at
n≥20 → **LANE_FROZEN** (reason: `FRAME_BELOW_70_AT_N20+`). 07-14 changed the
cumulative figures but did not unfreeze the lane; `freeze=True` is recorded
in the same 23:13 UTC snapshot that includes today's rows — no unfreeze or
promotion event occurred.

New Build: readiness/feature layer (Lane A Core+Passport, 43 races/368
runners) completed and gated READY, but no per-race scored prediction card
was produced — operational gap, exact missing invocation not pinpointed
with certainty. Champion Intent Shadow: no execution trace at all for
07-14. See the two NO_DATA reports for full detail. Neither gap was
retrospectively "fixed" or backfilled by this mission.

## Phase 10 — Manifest gap autopsy

Full writeup: `race_day_14_manifest_gap_autopsy_2026_07_14.md`. Summary: the
truncation bug is proven from code (both committed and — critically — the
still-uncommitted 2026-07-08 "fix", which added atomic writes but left the
truncation logic itself unchanged) and recurs across at least 4 other
capture directories with varying severity, worst on 2026-07-13 (18-file gap)
and 2026-07-14 (42-file gap). Repair and regression-test specifications are
recorded but **not implemented** in this mission.

---

## Evidence and reproducibility

- Clean worktree: `/mnt/c/Users/puror/velo-race-day-14-proof`, branch
  `evidence/race-day-14-best-day-proof`, branched from primary repo HEAD
  `aef6305` (`audit/local-01-truth-reconciliation`).
- All primary 2026-07-14 evidence copied into `evidence_staging/2026-07-14/`
  with SHA-256 verification (25/25 files copied and hash-matched; see
  `evidence_staging/2026-07-14/_evidence_import_manifest.json`).
- Raw HTML captures were **not** copied (per Preservation instructions) —
  hashed in place from the primary repo and inventoried instead (178
  entries covering both the racecard and results capture directories).
- Uncommitted runtime code that was actually invoked in today's pipeline is
  preserved as diffs + materiality analysis in
  `provenance/UNCOMMITTED_RUNTIME_CODE_PROVENANCE.json` and the four
  accompanying `.diff` files — this is the basis for the "committed HEAD ≠
  runtime code" finding that constrains the Phase 6 verdict.
- The primary worktree (`/mnt/c/Users/puror/velo-oracle-prime`) was **not**
  modified, branched, reset, stashed, cleaned, or checked out at any point
  during this mission — it was read from exclusively via `git diff`,
  `git status`, and file copies.
