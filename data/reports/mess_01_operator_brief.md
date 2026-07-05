# MESS-01 — Raceday Pipeline Truth Audit — Operator Brief
Generated: 2026-07-04 | READ-ONLY FORENSIC AUDIT | no scoring, no Supabase writes, no file deletion in this mission

---

This audit does not fix anything. It maps exactly where the "truth planes" you described
(GitHub, Supabase, dirty-repo local data, clean-repo code, dashboard JSON, dashboard server
API, ONE_TRUTH doctrine, actual code behavior, Sigma/results, New Build passport data, Old
VELO RP PDF data, RPDC) actually diverge, with file:line evidence. Sixteen questions,
answered in order.

---

## 1. What is the canonical daily path, and does the actual code match it?

`THE_ONE_TRUTH.md` (root, 1035 lines) defines Steps 1-20: RP index capture → URL list →
race-page capture → parse (`__NEXT_DATA__` → injection JSON + standard cache) → preflight
gate (`validate_rp_injection.py`) → New Build passport feed → New Build two-lane score →
Old VELO RP-newspaper PDF ingestion (hard gate) → **Step 8.5 RPDC build** → **Step 9
`run_prime_today.py` scoring** → Steps 9.1-9.6 paper-intelligence overlays → evening
Steps 10-20 (results capture, Sigma, horse-run ingest, retrieval corpus, Mission Control,
Council, execution bridge, router audit, Playbook G nightly learning).

`docs/current/ONE_TRUTH.md` (154 lines) is the shorter doctrine layer; it explicitly
defers to root `THE_ONE_TRUTH.md` for step detail and claims to supersede all other docs.
Both documents agree on the shape of the daily path and both are current in intent — this
is not itself a broken seam. The seam is that **neither document is verified against CI**
(see Q8) and one operational script (`velo_race_day_button.py`) exists that bundles many of
these steps together while `THE_ONE_TRUTH.md` explicitly says "NO RACE-DAY BUTTON — do not
use `velo_race_day_button.py` as the operational authority" (line 571). The button script
still exists, still runs `run_prime_today.py` with a hardcoded environment override
(`extra_env={"VELO_FORCE_CARD": "1"}`, `scripts/ops/velo_race_day_button.py:312`) that
silently downgrades the cache/RPDC completeness gate to warn-only on every invocation
regardless of whether the card actually is small/genuine — see Q13.

Every script named in the Steps 1-20 table (`scripts/ops/*.py`) exists on disk and was
confirmed present. The documented order (RPDC before scoring, results before Sigma, etc.)
matches what `build_rpdc_daily.py` and `run_prime_today.py` actually expect as inputs
(`build_rpdc_daily.py` reads the exact injection JSON from Step 4, not runner_snapshots —
`scripts/ops/build_rpdc_daily.py:474-478` comment block documents this explicitly).

## 2. Which scripts are live daily (run every raceday)?

Steps 1-9 core: `racing_post_account_collector.py`, `build_racing_post_racecard_url_list.py`,
`parse_racing_post_racecard_capture.py`, `validate_rp_injection.py`,
`new_build_current_card_feed.py`, `new_build_two_lane_score.py`,
`ensure_old_velo_rp_newspaper_files.py`, `build_rpdc_daily.py`, `run_prime_today.py`.
Evening Steps 10-20: `build_rp_results_url_list.py`, `parse_rp_results_capture.py`,
`run_results_sigma.py`, `ingest_results_to_horse_runs.py`, `build_sigma_retrieval_corpus.py`,
`update_mission_control.py`, `vp30_operator_card.py`, `run_velo_council.py`,
`run_execution_bridge_shadow.py` (SIM only), `build_innovation_protocol.py`,
`router_shadow_audit.py`, `nightly_eod_learning_runner.py` (shadow-only artifact, but part
of the daily evening sequence). Dashboard: `publish_daily_predictions_to_dashboard.py` and
`new_build_dashboard_server.py` (long-running process, not a daily one-shot).

## 3. Which scripts are shadow-only / paper-intelligence overlays?

All 7 named by the operator were confirmed to exist on disk:
`run_radical_shadow_today.py`, `run_tri_lane_stress_test.py`,
`build_tri_lane_agent_review.py`, `build_deep_race_agent_v1.py`, `build_course_master.py`,
`build_old_velo_three_option_card.py`, `nightly_eod_learning_runner.py`. `THE_ONE_TRUTH.md`
lines 421-567 document each as Steps 9.1-9.6, explicitly labelled SHADOW/PAPER ONLY,
CONTEXT ONLY, or OPERATOR ONLY, with a "hard law" (line 427-430) that no 9.x overlay may
silently change `velo_prime_prob`, `decision_tier`, `assigned_product`, Supabase verdicts,
router lanes, model files, or Telegram/execution behavior. This is a real, enforced
convention in the doctrine — but it is enforced only by naming convention and doc statement,
not by any code-level guard or CI check that would fail if a shadow script started writing
to `velo_verdicts`. No test asserts that these 7 scripts never write to Supabase.

## 4. Which scripts appear obsolete/dead?

`archive/dead_scripts/` (well over 100 files) and `archive/dead_workers/`, `archive/legacy/`,
`archive/legacy_v11/` hold everything superseded, including every Racing-API-era script
(`archive/dead_scripts/post_race_truth_loop.py`, `close_sigma_loops.py`,
`enrich_trainer_analysis.py`, `enrich_horse_history.py`, `ingest_racing_profiles.py`;
`archive/dead_workers/fr_daily_ingest.py`, `hk_daily_ingest.py`, `daily_pipeline.py`;
`archive/legacy/2026-05-19-cleanup/explore_racing_api.py` and others). The
directory-name convention (`dead_scripts`, `dead_workers`, `legacy/<date>-cleanup`) is the
only labelling mechanism — there is no per-file "DEAD" banner requirement, so a file's
obsolete status is only as reliable as whoever filed it into the right archive folder.
`new_build_velo_DEAD.py` sits directly under `archive/` with a self-describing name.

Two live (non-archived) scripts still construct Racing-API Basic-Auth headers:
`scripts/ops/run_international_sigma.py:28,37` and `scripts/ops/run_results_sigma.py:58,271`
both still define/use `RACING_HEADERS`. These are results/reporting tools (Sigma), not the
live scoring bootstrap, and Racing API there appears to be used only for results
reconciliation context, not live scoring — but they are unarchived files still referencing
a "PERMANENTLY DECOMMISSIONED" (`CLAUDE.md`) API. This is a doctrine/code seam: the doctrine
says Racing API "may exist only as archived legacy... or non-live experimental adapter" —
these two files are neither archived nor labelled experimental.

## 5. Which scripts write to Supabase, and which tables?

See `mess_01_write_surface_map.csv` for the full line-by-line map. Summary of true writers
(confirmed by grepping for actual `.insert(`/`.upsert(`/`.update(`/`.delete(`/`method="POST"`
calls, not just string mentions of a table name):

- `run_prime_today.py` → `pipeline_runs` (insert/update, lines 1296-1354), `velo_verdicts`
  (upsert via `app/services/velo_prime_service.py:1201`), `runner_derived_features` (upsert,
  `velo_prime_service.py:1291`), `runner_prediction_snapshots` (insert via
  `src/velo/runner_snapshot_store.py:234`). Reads (does not write) `runner_release_candidates`.
- `build_rpdc_daily.py` → `runner_release_candidates` (delete-then-upsert per date,
  `scripts/ops/build_rpdc_daily.py:645-655` — full day replace, not append).
- `ingest_results_to_horse_runs.py`, `parse_rp_results_capture.py` → `racing_horse_runs`.
- `run_results_sigma.py`, `run_execution_bridge_shadow.py`, `run_multimodel_sigma.py` →
  `velo_verdicts` (reads for reconciliation; sigma also writes `sigma_audits` per prior
  memory of the locked Telegram format — not re-verified line-by-line in this audit, out of
  scope of the 10 named files).
- `publish_daily_predictions_to_dashboard.py` → reads `velo_verdicts.full_analysis` only
  (via supabase-py `.select(...).execute()`, lines 324-330); writes no Supabase table, only
  local JSON.
- `new_build_dashboard_server.py` → **writes nothing, reads nothing from Supabase at all.**
  No `create_client`/`from supabase import` anywhere in the file (confirmed by full-file
  grep). Every one of its 15+ local-file read paths is a JSON/JSONL/CSV artifact some other
  script already wrote. This is the single most important finding of this audit — see Q11.

Many other scripts (`audit_race_day_manifest.py`, `check_rpdc_integrity.py`,
`sync_verdicts_from_supabase.py`, `velo_morning_cockpit.py`, `prove_supabase_persistence.py`,
etc.) mention these table names but on inspection only perform read-only GETs for audit
purposes — no write calls found (`grep` for POST/PATCH/DELETE/upsert/insert in each returned
nothing beyond the ones listed above).

## 6. Which scripts write local files, and where?

`run_prime_today.py`: `data/velo_prime_verdicts_{date}.json` (local backup, unconditional,
line 2437), `data/timing_audit/runtime_timing_audit_{date}.json` (unconditional, line 2482),
`data/velo_run_observability_{date}_{run_id}.json` (effectively unconditional — see Q14),
`data/runner_snapshots_{date}_{run_id}.jsonl` (gated).
`build_rpdc_daily.py`: writes only to Supabase, no local file output.
`publish_daily_predictions_to_dashboard.py`: `data/dashboard_daily_predictions_{date}.json`
(unconditional — the `VELO_DASHBOARD_PUBLISH_ENABLED` env var mentioned in its own docstring,
line 21, is never actually read anywhere in the executable code, confirmed by grep — it is
aspirational documentation, not a real gate) and
`data/dashboard_daily_predictions_publish_audit_v1.json` (also unconditional, overwritten
every run). `racecard_cache_gate.py` writes `data/reports/racecard_cache_gate_latest.json/.md`
every call (lines 243-244). Evening-sequence scripts write the various dated JSON/CSV
artifacts listed in `THE_ONE_TRUTH.md` lines 974-999 (mission control, council packets,
router audit CSVs, nightly learning event JSONLs) — not individually re-verified line-by-line
in this audit beyond the 10 named files, but their existence and naming were spot-checked
via the file list already present under `data/`.

## 7. Which files are gitignored but operationally required?

`.gitignore` lines 84-93 exclude `data/new_build/`, `data/racecard_merged/`,
`data/racecards_*_standard.json`, `data/incoming_pdfs/`, `data/racing_post_account_raw/`,
`data/racing_post_account_parsed/`, `data/racing_post_url_lists/`. Cross-referencing against
`src/velo/racecard_loader.py`, these are **exactly** the two primary racecard sources the
loader reads from disk (`load_racecards()`, `racecard_loader.py:262,281,286` reads
`data/racecards_{date_tag}_standard.json` and `data/racecard_merged/racecard_*_{date}.json`)
plus the injection JSON `build_rpdc_daily.py` requires
(`data/racing_post_account_parsed/*{date}*/racecard_injection.json`,
`build_rpdc_daily.py:87-90`) and the passport bank `data/new_build/passports/` referenced
in `THE_ONE_TRUTH.md` Step 6. **A fresh clone of this repo has zero raceday input data and
cannot run one single day of the pipeline without the operator manually re-running the RP
capture chain from scratch** — this is by design (captured HTML/PDF data is large and
proprietary to RP's terms), but it means "clone the branch and run the same contract"
(`THE_ONE_TRUTH.md` line 16-18) is only true for the *code*, never for the *data*, and
nothing in the repo states that distinction explicitly.

Partial mitigation found: `data/bha_or_diff_latest.csv`, `data/bha_perf_figures_latest.csv`,
and `models/sqpe_v17/sqpe_v17.pkl` all match broad exclusion patterns
(`.gitignore` lines 55/80/110: `data/*.csv`, `data/**/*.csv`, `models/**/*.pkl`) but are
**force-tracked in git anyway** (confirmed via `git ls-files` — all three appear as tracked
paths, meaning they were previously `git add -f`'d, overriding the ignore pattern for those
specific already-tracked files). So the live model weights and BHA sidecar CSVs *do* survive
a clone; the raceday capture/passport/RPDC-injection data does not.

## 8. Which CI jobs cover the live daily path vs only workers/ingestion_spine and app/?

`.github/workflows/ci.yml` (91 lines): job `test` runs
`pytest workers/ingestion_spine/ -v --cov=workers/ingestion_spine` (line 33) only; job `lint`
runs `ruff check workers/ingestion_spine/ app/` (line 52); job `type-check` runs
`mypy workers/ingestion_spine/` (line 76). **None of the three jobs ever runs `pytest tests/`
or touches `scripts/ops/`, `src/velo/`, or `new_build_velo/`.**

`.github/workflows/governed-safety.yml` (54 lines): runs exactly 6 named test files
(`test_capture_proof.py`, `test_worktree_safety_runner.py`, `test_task_contract_runner.py`,
`test_side_effect_sentinel.py`, `test_governed_task_runner.py`,
`test_verify_hardening_state.py`), plus a self-audit of `side_effect_sentinel.py` and a
`grep` check that a task-contract JSON file contains four required classification strings.
This audits the *governance harness* (the meta-layer that is supposed to gate risky
commands), not the pipeline itself.

**Verdict: 0 of the 22 live-daily/evening ops scripts named in this audit's scope are
exercised by any CI job, in any form.** The entire Steps 1-20 raceday contract runs
manually, every day, with no automated regression protection. `tests/test_run_prime_bootstrap.py`
(75 lines, containing 3 tests of `run_prime_today.py`'s bootstrap and RPDC-attach logic)
exists and is a real, useful test — but it is never run in CI (confirmed: neither workflow's
job list includes this filename), so its one broken assertion (Q9) has never surfaced as a
red CI check.

## 9. Which tests are stale or "false-green"?

`tests/test_run_prime_bootstrap.py:34`
(`test_bootstrap_runtime_keeps_telegram_when_enabled`) asserts
`run_prime_today.RACING_HEADERS["Authorization"].startswith("Basic ")`. Confirmed by
full-file grep: `scripts/ops/run_prime_today.py` (2759 lines) contains **zero** occurrences
of `RACING_HEADERS`, `RACING_USER`, `RACING_PASS`, or `RACING_BASE` anywhere —
`_bootstrap_runtime` (line 162) only sets `TOKEN, CHAT_ID, _SB_URL, _SB_KEY, _SB_HDRS,
_BHA_OR_DIFF_LOOKUP, _BHA_PERF_LOOKUP`. If this test were executed today it would raise
`AttributeError`, not silently pass — so it is not "false-green" in the sense of passing
incorrectly; it is a hard failure that has simply never been run, because neither CI
workflow includes this test file (see Q8). A historical snapshot
(`docs/stabilization/snapshots/run_prime_today.py:186,193`) proves `RACING_HEADERS` did
exist in this file at an earlier stage and was removed when direct Racing-API calls were
dropped from the live scoring bootstrap — the test was never updated or deleted to match.
This is a textbook "dead assumption from the decommissioned Racing API era," exactly as
suspected, and it is a landmine sitting inert only because nothing runs it.

The broader `tests/` directory (161 entries) was grepped for `RACING_API`/`theracingapi`
references (20 files hit). The overwhelming majority are *enforcement* tests that correctly
assert Racing API paths are blocked or archive-only (e.g. `test_agent_harness.py`,
`test_harness_enforcement.py`, `test_harness_wiring.py`, most `test_vfu_*.py` files, all
asserting `racing_api_restored is False` or requiring `NO_RACING_API_RESTORATION`). One
weaker candidate: `test_new_build_sources.py` hardcodes exact historical file/race counts
(`inventory["racing_api_racecard_files"] >= 30`, `payload["race_count"] == 52`) tied to a
fixed 2026-05 archive snapshot — not a live-API violation, but brittle and could silently
rot if that archive is ever pruned.

## 10. Where can a synthetic horse_id enter persistence?

`src/velo/racecard_loader.py:187` — inside `load_rp_merged_as_racecards()`, the runner dict
builder falls back to a synthetic ID whenever the RP-merged JSON lacks a numeric `horse_id`:
```
"horse_id": h.get("horse_id") or f"rp_{venue_code}_{name.lower().replace(' ', '_')}",
```
This is the exact `rp_{venue}_{name}` pattern named in the task. `THE_ONE_TRUTH.md` lines
308-315 documents that this fallback is supposed to be "gone except as a last-resort" and
names three scripts that must never regress back to synthetic IDs: `racecard_loader.py`,
`parse_rp_results_capture.py`, `build_rpdc_daily.py` — but the fallback line itself is still
live code in `racecard_loader.py`, meaning the guarantee rests entirely on RP-merged JSON
always having a populated `horse_id` field upstream, not on any code-level assertion in this
function. **No guard was found anywhere downstream** — `build_rpdc_daily.py`'s
`_load_injection_runners()` (lines 97-130) requires `horse_id` to be truthy to include a
runner at all (`if not horse_id: continue`, line 114) but does not validate its *shape*
(i.e. it will happily accept and persist a `rp_`-prefixed synthetic string into
`runner_release_candidates` if one reaches it — the horse-history lookup in
`_fetch_horse_history()` even has an explicit name-based fallback path, lines 179-201,
because `racing_horse_runs.horse_id` sometimes uses the name-based format while injection
uses numeric IDs, meaning synthetic-ID rows are an anticipated, handled case rather than an
impossible one). `run_prime_today.py`'s `_attach_rpdc()` similarly just uses whatever
`horse_id` string is on the top-pick dict with no format validation
(`scripts/ops/run_prime_today.py:842-885`). **There is no hard gate anywhere in the
persistence path that rejects a `rp_`-prefixed synthetic ID before it reaches Supabase** —
only the documentation's promise that the upstream RP-merged data won't produce one.

## 11. Where can the dashboard show stale/fallback data while claiming to be live?

Traced `new_build_dashboard_server.py` (897 lines) in full. Neither `/api/governed-card` nor
`/api/dashboard-truth` ever queries Supabase — confirmed, no `create_client`/`from supabase
import` anywhere in the file. Every response is built from local JSON/JSONL/CSV artifacts
pre-written by other scripts.

`/api/governed-card` (`_build_governed_card`, lines 634-766) tries three fallback sources in
order: (1) New Build paper-predictions JSONL, marked `paper_only: True`; (2) **local
`runner_snapshots_*.jsonl` files** — a locally-written Old-VELO snapshot artifact, marked
`paper_only: False`, `trust_policy: "LIVE_VERDICT_READ_ONLY_DASHBOARD"`, self-described
in-code as `"Official Live VÉLØ local runner snapshot"` (line 599); (3) New Build
two-lane-readiness JSON. On a normal raceday, path (2) is what fires once
`run_prime_today.py` has run and written its runner snapshots — meaning the "live" card is
actually **live-at-scoring-time, frozen until the next scoring run overwrites/adds a new
snapshot file**, not a live Supabase read on every request.

`/api/dashboard-truth` (`_build_dashboard_truth_panel`, lines 274-322) additionally reads
three "latest" files with **no date parameter passed to the loader at all**:
`data/router_shadow_audit_latest.csv` (line 204), `data/doctrine_scorecard_latest.json`
(line 279), `app/static/dashboard/sidecar_stack_latest.json` (line 280). If any of these
three weren't regenerated for the requested date, the endpoint silently serves whatever was
last written, with no staleness check against the requested `date_str` — unlike the
observability loader (`_latest_observability`, lines 132-143), which at least logs a
"date mismatch" warning.

Self-description conflict found: the module docstring (line 3) reads *"Minimal dashboard
server for New Build paper-only reads"* and line 12 states *"No Supabase. No model_manager.
No Live VELO. No Telegram. No staking."*, and the startup banner (lines 888-892) prints
*"Old Live VELO: UNTOUCHED | Shadow: UNTOUCHED | Telegram: OFF"*. This is directly
contradicted by the live `_build_governed_card_from_live_snapshots` code path (471-631 lines,
not dead code — the primary fallback for a normal raceday) which explicitly serves
`"paper_only": False`, `trust_policy: "LIVE_VERDICT_READ_ONLY_DASHBOARD"` data sourced from
real scoring runs. The narrower, locally-honest docstring on that specific function ("Does
not score, persist, notify, stake, or mutate Live VÉLØ", lines 475-476) is accurate — the
file-level self-description is stale, written for an earlier, narrower version of the server
that has since been extended to surface live production verdicts without the header/banner
being updated. This is the clearest single piece of evidence in this audit that the
dashboard's self-description no longer matches its actual behavior.

## 12. Where does RPDC become attached to verdicts?

Two separate code paths exist in `run_prime_today.py`, which is itself a mess worth noting:
`_attach_rpdc()` (lines 842-885) does a live REST GET to
`{SB_URL}/rest/v1/runner_release_candidates?horse_id=eq.{horse_id}&race_id=eq.{race_id}&order=generated_at.desc&limit=2`,
picks `rows[0]` (newest by `generated_at`), and flags `rpdc_lookup_status: "ambiguous_latest"`
if more than one row matched — but **is not called anywhere in `main()`**; its only caller
in the whole repo is the test `test_run_prime_bootstrap.py::test_attach_rpdc_marks_ambiguous_latest_and_uses_newest_row`.
The actual production path is `_attach_rpdc_from_row` (lines 820-839), fed by a pre-fetched
day-level RPDC map built via `resolve_runner_rpdc()`/`_fetch_race_rpdc()`/
`_get_day_rpdc_name_map()` and invoked inline during the Step-3 scoring loop (line 1989).
So the function name that looks like the RPDC-attach entrypoint (`_attach_rpdc`) is dead
code in production and only exercised by a unit test — a second, differently-named function
does the real work. This is a naming/maintenance seam, not a correctness bug, but it means
anyone reading `run_prime_today.py` top-down looking for "where does RPDC attach happen"
will find the wrong function first.

## 13. Where is RPDC only a warning but should arguably be a hard gate?

`src/velo/racecard_cache_gate.py`, `_check_sidecar_date_match()` (lines 162-216) is the RPDC
coverage check — it queries `runner_release_candidates` for the date, computes overlap with
the loaded racecard's race IDs, and requires `coverage >= 0.50` to "pass" — but it is
constructed with `blocking=False` on every return path (lines 174, 199, 209, 213), meaning
**even total RPDC absence (0% coverage) never fails the gate**, it only shows as a `⚠` in
the printed/report output. This is warn-only by design, and arguably should be a hard
blocking check given `THE_ONE_TRUTH.md`'s own words: "If RPDC does not run before scoring,
every horse goes into the model blind with no release context" (line 271) — a statement
that describes a real scoring-quality risk, not a cosmetic one.

Separately, `validate_racecard()` (lines 271-341) has a `VELO_FORCE_CARD` environment
override (checked at line 292 and again independently in `print_gate_result()` at line 349)
that downgrades **all** blocking failures — not just RPDC — to warnings, letting the gate
pass regardless of race/course/runner/metadata completeness. The docstring (lines 282-286)
frames this as an operator manually asserting "a genuine small-card day" — but
`scripts/ops/velo_race_day_button.py:312` hardcodes `extra_env={"VELO_FORCE_CARD": "1"}`
on every single invocation of `run_prime_today.py` through that script, unconditionally,
with no per-day judgment call at all. Given `THE_ONE_TRUTH.md` explicitly disclaims this
button script as "not the operational authority" (line 571), the override being baked into
it is a latent risk rather than an active daily problem — but it means the override exists
in committed code as an always-on default in at least one code path, not only as a manual,
occasional operator flag. There is also an implicit containment bypass
(`racecard_cache_gate.py:294-304`) that auto-sets `force_card=True` whenever a
`.cert.json` sidecar file exists with `fixture_truth_status` of `PARTIAL_MEETING_CONTAINED`
or `CERTIFIED_MEETING_CONTAINED` — a second, file-driven way to silently disable blocking
without any env var at all.

## 14. Where does `--dry-run` still trigger local file writes it probably shouldn't?

`_resolve_persistence_modes()` (`run_prime_today.py:1403-1443`) sets
`persistence_enabled/verdict_persistence_enabled/runner_snapshots_enabled/telegram_enabled`
all to `False` under `--dry-run` (this part works correctly and gates the Supabase writes
and the runner-snapshot writes properly). But three local file writes are **never gated by
this function's output at all** and fire unconditionally, dry-run or not:
- `data/velo_prime_verdicts_{date}.json` (line 2437) — a `try:` block with no flag check,
  explicitly commented "backup only — NOT system of record... Best-effort only" (line 2418).
- `data/timing_audit/runtime_timing_audit_{date}.json` (line 2482) — no flag check at all.
- `data/velo_run_observability_{date}_{run_id}.json` — written via `write_observability_packet()`
  at three call sites (lines 1627, 2563, 2743), none of which thread the CLI `--dry-run` flag
  into that function's own `dry_run` parameter
  (`scripts/ops/write_velo_run_observability.py:204-225` does have such a parameter, it is
  simply never passed `True` from any `run_prime_today.py` call site).

Practically: a `--dry-run` invocation still leaves three dated JSON files on disk that look
identical in shape to a real scoring run's output, with no filename or content marker
distinguishing "this was a dry run" from "this actually persisted" — an operator or another
script reading `data/velo_prime_verdicts_2026_07_04.json` cold has no way to tell from the
file alone whether that day's run was real or a dry-run rehearsal.

## 15. Where does `--verdicts-only` still write beyond `velo_verdicts`?

`--verdicts-only` does not disable `pipeline_runs` writes. `_resolve_persistence_modes()`
only changes `runner_snapshots_enabled` and `telegram_enabled` when `verdicts_only` is set
(lines 1434-1435); `persistence_enabled`/`verdict_persistence_enabled` are untouched and, in
every non-dry-run branch of the function, are **always assigned the identical value** —
despite being named as if they were two independently-controllable flags, they have never
diverged in this implementation. Since `pipeline_runs` writes (`_open_pipeline_run` at line
1518, `_close_pipeline_run` calls at 2571/2603/2633/2756) are gated only on
`persistence_enabled`, **running with `--verdicts-only` opens and closes a `pipeline_runs`
row exactly as a normal full run would**, in addition to writing `velo_verdicts`. This
matches the CLI help text's own honest disclosure ("Does not disable verdict persistence" —
`run_prime_today.py` argparse help for `--verdicts-only`) but the flag name and the presence
of two separately-named dict keys invite a reader to assume finer-grained control than
actually exists.

## 16. Proposed one-page runbook — table of contents (sketch only)

See `mess_01_cleanup_sequence.md` for the full 4-pass programme. At a glance, a
future single-page runbook should be structured as:
1. **One command per phase** (morning / RPDC / scoring / evening) with the exact script and
   flags, no prose duplication across three docs.
2. **One machine-checkable gate per phase transition** (preflight, RPDC coverage, Sigma
   result-integrity) with a single PASS/FAIL contract, not warn-only defaults hidden behind
   env vars.
3. **One dashboard truth statement**: what "live" means precisely (live-at-publish, refreshed
   how often, by what trigger) — not aspirational language.
4. **One CI job that runs the actual pipeline scripts' unit tests** (not just
   `workers/ingestion_spine/`).
5. **One doctrine file**, not two (`THE_ONE_TRUTH.md` root + `docs/current/ONE_TRUTH.md`)
   that both claim supremacy over each other in different ways.

---

## Required classifications
- MESS_01_AUDIT_READ_ONLY
- NO_SUPABASE_WRITES_IN_THIS_MISSION
- NO_SCORING_RUN
- NO_SIGMA_RUN
- NO_TELEGRAM_SEND
- NO_FILE_DELETION
- SIX_REPORT_FILES_WRITTEN
