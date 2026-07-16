# Race Day 15 (2026-07-15) — Frozen Model Recount and Control-Plane Report (v2, CORRECTED)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. Read-only forensic proof. No rescoring, no production repairs, no merges.

**Revision v2** — issued after the operator's REQUEST CHANGES review of PR #151 v1. v1's evidence discovery (immutable morning snapshot identity, the Transcript→Kalir manufactured hit, Sigma's contamination) is **retained and accepted**. v1's performance/classification calculations contained material errors, corrected below (P0-19 through P0-24). Every number in this revision was independently recomputed from the evidence bundle by a portable, path-independent script — not copied from the operator's own expected figures — and the recomputation happens to match the operator's own independent estimate (12/38) exactly, which is treated as convergent confirmation, not as the reason for accepting the number.

## What changed from v1, and why

| # | v1 defect | v2 fix |
|---|---|---|
| P0-19 | `14/47` timing logic incremented the denominator before checking timing safety, and the `H.MM` off-string parser misclassified evening races (e.g. would have read `7.20` as `07:20`) | Three explicit views computed from canonical `race_time_raw` + a per-course UTC offset table (Happy Valley UTC+8, GB/IRE UTC+1 in July): `FULL_SNAPSHOT_REPLAY` (informational only), `STRICT_PRE_RACE` (the only view that may be called a strike rate), `TIMING_UNPROVEN` |
| P0-20 | `radical_shadow_2026_07_15.json` was mislabelled `NO_RPR_SHADOW` — it is a different, mutable, afternoon-generated decision layer built around Old VÉLØ's own top pick | Genuine No-RPR reconstructed from the immutable morning snapshot's own `sqpe_no_rpr_shadow_prob` field, ranked per race, horse_id-matched to results, with fail-closed exclusion of 5 races with tied top scores. Radical Shadow retained separately, correctly labelled `RADICAL_SHADOW` |
| P0-21 | New Build / Champion Intent were blanket-labelled `MORNING_RUN_UNPROVEN` with no per-race distinction | Each race classified individually: `POST_RACE_GENERATED` / `AFTERNOON_PRE_RACE_PROVEN` / `TIMING_UNPROVEN`, using each artifact's own `generated_at` against canonical `off_dt` |
| P0-22 | Phase 9 concluded `NOT_RECURRED_ON_2026-07-15` using the post-fallback `races_parsed=47` counter as if it proved the original manifest was complete — logically reversed | Reopened, root cause located directly in code (`racing_post_account_collector.py:329-334`); classification corrected to `MANIFEST_TRUNCATION_CONFIRMED_RECURRING_ROOT_CAUSE_LOCATED` |
| P0-23 | Claimed the WSL cron "fired late" at 14:08 while also stating cron does not catch up missed jobs — self-contradictory, and not supported by the evidence (a wrapper log proves the wrapper ran, not that cron triggered it) | Both trigger origins reclassified `MORNING_TRIGGER_ORIGIN_UNPROVEN` / `AFTERNOON_TRIGGER_ORIGIN_UNPROVEN`; the structural finding (`NO_SINGLE_DAILY_RUN_OWNER_AND_NO_RUN_LOCK`) is retained, since it does not depend on resolving origin |
| P0-24 | Scripts hardcoded an absolute worktree path, joined on horse name strings, hashed re-serialized JSON instead of raw JSONL bytes, and read a `decision_tier` field that doesn't exist in the snapshot (leaving Old VÉLØ tiers blank) | Scripts resolve repo root from their own location (or accept `--repo-root`), join on `horse_id` with name fallback explicitly flagged, hash the raw JSONL line bytes, and read the snapshot's actual `tier` field |

## Phase 1 — Authoritative morning run (unchanged, accepted in v1)

**Classification: `MORNING_RUN_PROVEN`** for Old VÉLØ. `data/runner_snapshots_2026_07_15_2026_07_15_aef63056_1784105122721.jsonl` (400 rows, 47 races, every row's `created_at="2026-07-15T08:46:03.598813+00:00"`), cross-verified against Supabase `pipeline_runs` row `54fee6ec-d1b3-4a9c-8c07-d4af813405f4` and `velo_run_observability_..._b8ba4b61.json`. The afternoon file (454 rows, 54 races, `created_at="2026-07-15T14:08:55.167617+00:00"`) remains `POST_MORNING_DIAGNOSTIC_RUN`.

## Phase 2/5 — Killarney 924613 anchor (unchanged, accepted in v1)

Morning sealed pick **Transcript** (VP 0.4087) did not win. The 14:08 rescore changed the pick to **Kalir** (VP 0.4442), which won at final SP **4.0** (confirmed against `rp_results_2026_07_15.json`). Transcript's race off-time (18:30 local, 17:30 UTC) was well after the 08:46 UTC morning snapshot, so this was a genuinely timing-safe morning pick that the afternoon rescore silently overwrote and replaced with a pick that went on to win.

## Phase 6 — CORRECTED Old VÉLØ recount

| View | Wins | Eligible | Strike rate | Frame rate | Avg winner SP | ROI | Status |
|---|---|---|---|---|---|---|---|
| **STRICT_PRE_RACE** | **12** | **38** | **31.6%** | 65.8% | 3.64 | +14.9% | The only view that may be called a strike rate |
| FULL_SNAPSHOT_REPLAY | 14 | 46 | 30.4% | 58.7% | 4.18 | +27.1% | Informational only — includes all 9 post-race Happy Valley races; never a predictive-performance figure |

9 races excluded from the strict denominator, all Happy Valley (off-times 11:30-15:50 local = 03:30-07:50 UTC, all before the 08:46:03 UTC morning snapshot). Two of these are the specific races the operator flagged: **Winning Champion** (1.30 HV, off_dt_utc 05:30) and **Thriving Brothers** (2.35 HV, off_dt_utc 06:35) — both correctly excluded in this revision.

**Regression tests confirming the timing parser fix** (all independently recomputed against canonical `race_time_raw`, not the ambiguous `off` string):

| Race | Off (local) | `race_time_raw` | Course offset | off_dt_utc | vs. 08:46:03Z morning gen |
|---|---|---|---|---|---|
| Happy Valley 924714 | 1.30 | 13:30:00 | UTC+8 | 05:30 | POST-RACE (correctly excluded) |
| Happy Valley 924716 | 2.35 | 14:35:00 | UTC+8 | 06:35 | POST-RACE (correctly excluded) |
| Lingfield 923096 | 7.20 | 19:20:00 | UTC+1 | 18:20 | PRE-RACE (v1's `h<7` heuristic would have wrongly read this as 07:20 and excluded it as post-race — now correctly included) |
| Yarmouth 923107 | 7.10 | 19:10:00 | UTC+1 | 18:10 | PRE-RACE (same fix) |
| Killarney 924616 | 8.00 | 20:00:00 | UTC+1 | 19:00 | PRE-RACE |

## Phase 6, continued — genuine No-RPR (P0-20)

| View | Wins | Eligible | Strike rate | Frame rate | Avg winner SP | ROI |
|---|---|---|---|---|---|---|
| **STRICT_PRE_RACE** | **8** | **33** | **24.2%** | 60.6% | 6.50 | +57.6% |

Source: the immutable morning snapshot's own `sqpe_no_rpr_shadow_prob` field (present alongside `velo_prime_prob` on every one of the 400 runner rows), ranked descending per race, matched to results by `horse_id`. 5 races (of the 38 timing-safe races) have an exact tie for the top `sqpe_no_rpr_shadow_prob` score and are fail-closed excluded from the strict denominator (38 − 5 = 33, exact reconciliation) rather than resolved by an undocumented arbitrary tiebreak. Full tie ledger in `race_day_15_frozen_recount.json` → `phase6_no_rpr_genuine.tie_ledger`.

`radical_shadow_2026_07_15.json` is **not** No-RPR and is never labelled as such in this revision. It is retained separately as `RADICAL_SHADOW` — a mutable, afternoon-generated (14:09:20Z), `status=SHADOW_ONLY_NOT_LIVE` decision layer that reads the mutable `velo_prime_verdicts` table and is built around Old VÉLØ's own top horse (which is why its v1-mislabelled "No-RPR" scores exactly repeated Old VÉLØ's probabilities — a strong internal-consistency signal the operator correctly caught).

## Phase 6b — Sigma invalidation (unchanged, accepted in v1)

`sigma_results_2026_07_15.json` (generated 22:28:32Z) reads 100% from the live, mutable `velo_verdicts` table, 8+ hours after the 14:08 overwrite; its row schema has no `verdict_id`/`doctrine_event_id`/`pick_sp` field. The reported 15/46 remains invalid, and this revision's own v1 figure of 14/47 (also invalid, for the P0-19 reasons above) must not be quoted either. **The only strike rate that may be reported for Old VÉLØ from 2026-07-15 is 12/38 (31.6%), STRICT_PRE_RACE.**

## Phase 3/5 — Four-model comparison (CORRECTED)

| Model | Wins | Eligible | Strike rate | Provenance |
|---|---|---|---|---|
| Old VÉLØ | 12 | 38 | 31.6% | `STRICT_PRE_RACE_PROVEN`, 08:46 UTC morning snapshot |
| No-RPR (genuine) | 8 | 33 | 24.2% | `STRICT_PRE_RACE_PROVEN`, 08:46 UTC morning snapshot, 5 races tie-excluded |
| New Build (Lane A) | 7 | 32 | 21.9% | `AFTERNOON_PRE_RACE_PROVEN` only — 15 of 47 races were already post-race at the 14:09:30Z generation instant and are excluded |
| Champion Intent Shadow | 9 | 32 | 28.1% | `AFTERNOON_PRE_RACE_PROVEN` shadow-only, `velo_scoring_allowed=False` on every row regardless of timing |

Because Old VÉLØ/No-RPR and New Build/Champion Intent are proven against **different race universes** (38/33 races timing-safe at 08:46Z vs. 32 races timing-safe at ~14:09Z), the convergence/shared-winner comparison in `race_day_15_winner_convergence_matrix.csv` is computed strictly within each model's own proven population and explicitly marks which population each cell belongs to — it is not a naive like-for-like race-by-race comparison across all four models on identical footing, because no such footing exists in the underlying evidence.

## Phase 7 — New Build / Champion Intent per-race timing (P0-21)

| Model | POST_RACE_GENERATED (excluded) | AFTERNOON_PRE_RACE_PROVEN | Strike rate (proven subset) |
|---|---|---|---|
| New Build | 15 of 47 | 32 | 7/32 = 21.9% |
| Champion Intent Shadow | 15 of 47 | 32 | 9/32 = 28.1% |

Neither lane has a run-scoped immutable morning artifact (unchanged finding from v1) — even their `AFTERNOON_PRE_RACE_PROVEN` subset is proven only against a single mutable file, not a sealed run. New Build's proven wins additionally include rows whose own `nb_decision_lane`/`top_pick_lane` is `SUPPRESS` or `LOW_DATA` — these are shown in the CSV export with their policy status explicit and must not be read as live recommendations regardless of whether the underlying pick happened to win.

## Phase 7 — New Build / Champion Intent join failure (unchanged, accepted in v1)

**`SCORECARD_GENERATED_NOT_PERSISTED`.** `canonical_model_scorecards` independently re-queried: 2,511 total rows, most recent `run_date=2026-07-07`, zero for `2026-07-15`. `run_full_raceday.py`'s 19-step sequence never calls the canonical-scorecard persist scripts.

## Phase 8 — Cron / control-plane (CORRECTED, P0-23)

GitHub Actions `score-daily.yml` confirmed `state=disabled_manually` since 2026-06-10 (unchanged, accepted). Both trigger origins are now correctly classified as **unproven**: `MORNING_TRIGGER_ORIGIN_UNPROVEN` (08:45 run — no matching log entry anywhere, no attribution evidence) and `AFTERNOON_TRIGGER_ORIGIN_UNPROVEN` (14:08 run — `run_full_raceday_cron.log` proves the wrapper script executed and was redirected into that log file; it does NOT prove the cron daemon itself triggered it, since a manual invocation of the identical command would leave an identical log signature). The structural finding is unaffected by this correction: `NO_SINGLE_DAILY_RUN_OWNER_AND_NO_RUN_LOCK` — two runs fired 5.5 hours apart against the same `source_date`, both self-reporting `trigger_source=manual`, with no locking or duplicate-run guard anywhere in the pipeline.

`app/main.py:1249`'s `target_date`/`source_date` schema drift remains confirmed live at `aef6305` (unchanged, accepted).

## Phase 9 — Manifest truncation recurrence (CORRECTED, P0-22)

**Classification corrected from `NOT_RECURRED_ON_2026-07-15` to `MANIFEST_TRUNCATION_CONFIRMED_RECURRING_ROOT_CAUSE_LOCATED`.**

`data/racing_post_account_raw/2026-07-15/manifest.json`'s final on-disk state has exactly 9 entries, all Happy Valley — but all 49 raw HTML files (40 non-Happy-Valley + 9 Happy Valley) remain present on disk untouched. Root cause located directly in code: `scripts/ops/racing_post_account_collector.py`, function `capture_urls()`, lines 329-334. Step 3 (UK/IRE, 40 URLs) and Step 3.5 (Happy Valley, 9 URLs) both write to the identical `manifest.json`; Step 3.5's own manifest-rebuild step filters the merged capture list down to only URLs present in **its own** 9-URL input list, silently discarding Step 3's 40 prior entries from the file written to disk. This is the same class of defect PR #150 documented for 2026-07-14, recurring at a different call site. The final `rp_results_2026_07_15.json`'s 47-race, 7-course universe did not come from this truncated manifest via the standard automated path (`build_rp_results_url_list.py` could only have resolved to the same 9-entry manifest) — it required an unlogged manual reconstruction from the raw HTML files' own canonical URLs, consistent with the operator's own firsthand account of directly observing this happen. Full detail: `race_day_15_manifest_recurrence.md`.

## Phase 10/11/12 — unchanged from v1

Dashboard truth failure (`app/main.py:2468`), Race Day Controller design, and Deep Race Agent contract/benchmark plan are unaffected by the P0-19..P0-24 corrections and are retained as-is from v1 (see `race_day_controller_design.md`, `deep_race_agent_contract.json`, `deep_race_agent_model_benchmark_plan.md`).

## Evidence integrity

37 evidence files now copied from the primary dirty repo into `evidence_staging/2026-07-15/` (28 from v1 + 9 new in v2: racecard/intl/results URL lists, both racecard/results manifests, the collector script itself, the champion-intent audit file, and the cron log), all with byte-for-byte SHA-256 equality confirmed, zero mismatches. Primary repo untouched throughout this revision as well — see `provenance/` for the updated before/after status snapshots.
