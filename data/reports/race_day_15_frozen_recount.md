# Race Day 15 (2026-07-15) — Frozen Model Recount and Control-Plane Report

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. Read-only forensic proof. No rescoring, no production repairs, no merges. All findings independently re-verified against fresh SHA-256 hashes and a fresh Supabase `.select()` query this session, not taken on the orchestrating session's word.

## Phase 1 — Authoritative morning run

**Classification: `MORNING_RUN_PROVEN`** for Old VÉLØ. The immutable, run-scoped file `data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784105122721.jsonl` (SHA-256 `e2a80cc7...6d44da`, 400 rows, 47 unique race_ids, every row's `created_at="2026-07-15T08:46:03.598813+00:00"`) is independently cross-verified against three sources that all agree exactly: Supabase `pipeline_runs` row `54fee6ec-d1b3-4a9c-8c07-d4af813405f4` (started 08:45:22Z, finished 08:46:04Z, 47 races / 400 runners, PASS); `data/velo_run_observability_2026_07_15_b8ba4b61.json` (timestamp 08:46:04.619530Z, same counts); and the file's own internal consistency (single `run_id`, single `created_at` across all 400 rows).

The afternoon file (`..._1784124491047.jsonl`, SHA-256 `d6935d7c...5a62a`, 454 rows, 54 races, `created_at="2026-07-15T14:08:55.167617+00:00"`) is classified **`POST_MORNING_DIAGNOSTIC_RUN`**, matching Supabase `pipeline_runs` row `a96235ce-9899-4773-bc0d-0aaf276f3cfd` (started 14:08:10Z, finished 14:08:55Z, 54/454, PASS) and `velo_run_observability_2026_07_15_0e131abc.json`.

**No-RPR, New Build, and Champion Intent are classified `MORNING_RUN_UNPROVEN`.** None of the three has a run-scoped immutable morning file — each exists only as a single mutable artifact last generated in the 14:08-14:09 UTC window (`radical_shadow_2026_07_15.json` at 14:09:20Z; `two_lane_readiness_2026_07_15.json` at 14:09:30Z; `intent_shadow_scorecard_2026_07_15.csv` sharing the same pipeline step per `run_full_raceday_cron.log`, mtime 14:09Z). 23 of the day's 47 races (all of Happy Valley plus the early Catterick/Bath card) had already gone off before these files were even generated — they cannot serve as pre-race evidence for those races under any interpretation.

## Identity-scheme drift found inside the afternoon run

The afternoon run scored the **same 7 Uttoxeter races twice**, once under the pre-existing numeric RP id (e.g. `922990`) and once under a newly-introduced string scheme (`rp_UTT_20260715_2.48`), with byte-identical off-times for each pair. This is a live identity bug that any downstream joiner keyed to a single scheme will silently miss half of.

## Phase 2/5 — Morning vs afternoon: one changed pick

Of 47 races present in both runs, exactly **one** pick changed: race `924613`, Killarney 6.30.

| | Morning (08:46, sealed) | Afternoon (14:08, diagnostic) |
|---|---|---|
| Pick | **Transcript** | **Kalir** |
| Probability | 0.4087 | 0.4442 |
| Scoring-time price | 1.75 | 3.0 |
| Product | WIN_ONLY | WIN_ONLY |

**Actual winner: Kalir, final SP 4.0** (confirmed directly against `rp_results_2026_07_15.json`, runner-level `sp_dec` field — the operator's reported 4.0 is correct; the afternoon row's `sp_dec=3.0` was only the market price at 14:08, roughly 4 hours before the 18:30 off, not the final SP). Transcript did not win. The afternoon rescore therefore **manufactured a credited winner that did not exist in the sealed morning prediction** — this is the single point of divergence between the honest morning count and every inflated figure reported downstream.

Full race-by-race diff: `race_day_15_morning_vs_afternoon_verdict_diff.csv`.

## Phase 6 — Honest Old VÉLØ recount (strict, timing-proven, morning-only)

Computed directly from the 400-row immutable morning snapshot, joined against the canonical results file:

| Metric | Value |
|---|---|
| Eligible races scored pre-race | 47 |
| Non-runners | 1 |
| **Wins** | **14** |
| Placed only (2nd/3rd) | 13 |
| Misses | 19 |
| Timing-unproven / result-missing | 16 |
| **Strike rate** | **29.8%** |
| Frame rate | 57.5% |
| Average winner SP | 4.18 |
| Median winner SP | 3.13 |
| One-unit SP return | +12.45 |
| ROI | +27.1% |

**Honest result: 14/47 (29.8%), not the reported 15/46 (32.6%).** The difference is exactly the manufactured Kalir hit above.

## Phase 6b — Why Sigma's 15/46 cannot be trusted

`sigma_results_2026_07_15.json` was generated at **22:28:32Z**, over 8 hours after the 14:08 rescore. All 46 evaluated rows carry `vp_source="supabase_velo_verdicts"` — Sigma reads the live mutable table, not a frozen run. Independently re-queried this session: **100% of the live `velo_verdicts` rows for today's 54 races carry `generated_at` in the 14:08 window; zero carry 08:46** — the morning run's rows were completely overwritten (upsert-by-`race_id`, no run-scoped key). The Sigma row schema itself contains **no `verdict_id`, `doctrine_event_id`, or `pick_sp` field at all** (not merely null — absent from the schema), so Sigma cannot, even in principle, prove which prediction run it evaluated. **The 15/46 figure must not be repeated as a verified Old VÉLØ result.**

## Phase 3/5 — Four-model winners (see `race_day_15_four_model_winners.md`/`.csv` for full detail)

| Model | Winners | Eligible | Strike rate | Provenance |
|---|---|---|---|---|
| Old VÉLØ | 14 | 47 | 29.8% | `MORNING_RUN_PROVEN` |
| No-RPR Shadow | 15 | 46 | 32.6% | `MORNING_RUN_UNPROVEN` (single mutable file; also inherits the Kalir manufactured hit) |
| New Build | 8 | 46 | 17.4% | `MORNING_RUN_UNPROVEN`; many rows are `SUPPRESS`/`LOW_DATA`, not live picks |
| Champion Intent Shadow | 11 | 45 | 24.4% | `MORNING_RUN_UNPROVEN`; display-only shadow signal, `velo_scoring_allowed=False` |

Winners found by all four models: 4 races. Races found by none: 26. Full convergence matrix: `race_day_15_winner_convergence_matrix.csv`.

## Phase 7 — New Build / Champion Intent join failure

**Classification: `SCORECARD_GENERATED_NOT_PERSISTED`.** Both lanes produced real, populated, 47-race local scorecards on 2026-07-15. Independently re-queried this session: `canonical_model_scorecards` has 2,511 total rows, most recent `run_date = 2026-07-07`, **zero rows for `2026-07-15`**. `run_full_raceday.py`'s 19-step sequence (all 19 passed) never calls the canonical-scorecard build/persist scripts — persistence was simply never one of the steps. Multi-Model Sigma correctly reports `NO_DATA` because there is genuinely nothing in the table it joins against. The Uttoxeter ID-scheme drift (numeric vs. `rp_UTT_*` string) is a related but secondary risk, not today's root cause — both local lanes used the numeric scheme exclusively.

Full detail: `race_day_15_scorecard_join_autopsy.md`.

## Phase 8 — Cron / control-plane root cause

The GitHub Actions scheduler (`score-daily.yml`, the repo's own designated "source-controlled scheduler") is **`state: disabled_manually`**, disabled 2026-06-10, over five weeks before this incident, with zero runs since. The local WSL crontab (`0 7 * * *` Europe/London = 06:00 UTC) produced exactly one logged `run_full_raceday.py` execution for 2026-07-15, ending 14:09:41 UTC — matching the **afternoon** run, not the scheduled 06:00 UTC time; consistent with a missed/late firing (WSL not running at the scheduled instant; cron does not catch up missed jobs). The 08:45 morning run has no corresponding entry in the cron log at all, meaning it came from a third, distinct invocation path outside both known schedulers. Both `pipeline_runs` rows self-report `trigger_source=manual` — **no automated scheduler produced either run**; two uncoordinated manual triggers collided on the same date, five and a half hours apart, with no locking anywhere to prevent it. Separately, `app/main.py:1249` still queries `pipeline_runs?target_date=eq...` against a table whose real column is `source_date` — confirmed live at commit `aef6305`, a genuine schema-drift bug that silently degrades a health-check read (not the trigger mechanism itself).

Full detail: `race_day_15_cron_control_plane_autopsy.md`.

## Phase 9 — Manifest truncation recurrence

**Not reproduced on 2026-07-15.** Today's Happy Valley capture (9 races, race_ids 924710-924718) is complete and consistent across every counter checked: manifest `url_count=9`, `captures=9` (all PASS), and `rp_results_2026_07_15.json`'s `html_files_seen=racecard_indexed=readiness_indexed=races_parsed=47`, `parse_errors=0`. The PR #150-documented filtering defect was not found firing today for this specific example; this should be read as "not observed today," not "proven fixed" — the underlying code path was not independently re-audited in this mission. Full detail and regression-test spec: `race_day_15_manifest_recurrence.md`.

## Phase 10 — Dashboard truth failure

`app/main.py:2468`'s `verdict_count_today` logic (`race_id=like.*{date}*`) assumes `race_id` embeds the date, which it never does — confirmed still present at `aef6305`. Combined with the `velo_verdicts` upsert-by-`race_id` overwrite behavior, the dashboard has no reliable way to distinguish "today's sealed morning count" from "whatever the mutable table currently holds." Folded into the Race Day Controller design (Phase 11) as the replacement contract.

## Phase 11 — Race Day Controller (design summary)

A single deterministic 17-stage state machine (`DAY_CREATED` → ... → `DAY_SEALED`) per `source_date`, with a per-stage `run_id`, source/output hashes, and a one-way `MORNING_RUN_SEALED` gate that prevents any later write from overwriting a sealed run's artifacts (requiring `run_id`, not just `race_id`, as the upsert key). A manual rerun mints a new `run_id` and writes to a clearly non-authoritative namespace. Exactly one scheduler is allowed to own the daily `DAY_CREATED` trigger. Full design: `race_day_controller_design.md`.

## Phase 12 — Deep Race Agent contract and benchmark plan

A sealed-packet-in, structured-analysis-out contract (`deep_race_agent_contract.json`) with a provider-neutral adapter and a blind benchmark plan (`deep_race_agent_model_benchmark_plan.md`) scoring GLM, Qwen, and Kimi on structured-JSON validity, citation accuracy, field coverage, contradiction-detection recall (via planted synthetic conflicts), hallucination rate, latency, cost, and run-to-run consistency — with a hard structured-JSON-validity floor that disqualifies a provider regardless of other scores, and no pre-selected "recommended" winner.

## Evidence integrity

28 evidence files copied from the primary dirty repo into `evidence_staging/2026-07-15/` with byte-for-byte SHA-256 equality confirmed for every file, zero mismatches (`evidence_staging/2026-07-15/COPY_HASH_LOG.txt`). Primary repo untouched throughout — see `provenance/` for before/after status snapshots and the byte-identity classification.
