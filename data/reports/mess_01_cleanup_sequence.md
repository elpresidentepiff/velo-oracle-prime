# MESS-01 — Cleanup Sequence Programme
Generated: 2026-07-04 | Proposed only — no work in this programme has been executed.
This document confirms/refines the operator's proposed 4-pass structure against the
evidence gathered in `mess_01_operator_brief.md`. Nothing here has been built; it is the
plan for a future mission.

---

## Pass 1 — Truth Contract Cleanup (SOURCE-01..04)

**Goal:** collapse the doctrine layer down to one file that actually wins, and close the
gap between what the doctrine promises and what the code enforces.

- **SOURCE-01 — Merge or formally subordinate `docs/current/ONE_TRUTH.md` into
  `THE_ONE_TRUTH.md`.** CONFIRMED NEEDED. Both files currently claim supremacy over each
  other in different directions (`docs/current/ONE_TRUTH.md` line 7 says it supersedes
  "root CLAUDE.md state claims"; `CLAUDE.md` says `docs/current/ONE_TRUTH.md` wins any
  conflict; `THE_ONE_TRUTH.md` itself is the step-by-step detail the doctrine file defers
  to). Three files pointing at each other as the authority is exactly the "too many truth
  planes" complaint. Recommend one file, with the step detail as an appendix, not a
  cross-referenced sibling.

- **SOURCE-02 — Retire or clearly quarantine `velo_race_day_button.py`.** CONFIRMED NEEDED,
  with a sharper finding than originally scoped: it's not just an unused convenience script
  — it hardcodes `VELO_FORCE_CARD=1` on every `run_prime_today.py` invocation
  (`scripts/ops/velo_race_day_button.py:312`), which silently disables the cache/RPDC
  completeness gate every time it runs, contradicting `THE_ONE_TRUTH.md`'s own explicit
  disclaimer that it "must not" be treated as the operational authority. Either delete it,
  move it under `archive/`, or strip the force-override and make it fail loudly if a
  human hasn't explicitly confirmed a small card.

- **SOURCE-03 — Close the synthetic horse_id gap (Q10).** CONFIRMED NEEDED. The
  `rp_{venue}_{name}` fallback (`src/velo/racecard_loader.py:187`) is still live code, and
  no downstream script (`build_rpdc_daily.py`, `run_prime_today.py`) validates the *shape*
  of a `horse_id` before persisting it to Supabase — only the documentation's promise that
  upstream data won't produce one. Recommend a lightweight assertion/warning at the
  RPDC-build and verdict-persist boundaries: if `horse_id` matches `^rp_[A-Z]+_`, flag it
  explicitly in the observability packet rather than silently accepting it as a normal
  numeric ID would be accepted.

- **SOURCE-04 — Un-archive or properly archive the two still-live Racing-API scripts.**
  REFINED FROM OPERATOR SCOPE. `run_international_sigma.py` and `run_results_sigma.py` both
  still construct `RACING_HEADERS` for Racing-API Basic Auth and are NOT under `archive/` —
  yet `run_results_sigma.py` is the Step-12 LOCKED daily Sigma script (per `CLAUDE.md` hard
  law #6, "always use run_results_sigma.py"), so it cannot simply be archived. This item
  needs a narrower fix than "archive it": confirm exactly what these two scripts use Racing
  API for (results reconciliation context, not live scoring, per this audit's reading) and
  either (a) explicitly label that usage as "non-live experimental adapter" per the
  doctrine's own allowed exception, or (b) remove the dependency if it's genuinely dead
  code within those files. Do not archive `run_results_sigma.py` wholesale — it is in daily
  use.

## Pass 2 — Dashboard Truth Cleanup (DASH-01..04)

**Goal:** make the dashboard's self-description match what it actually serves, and put a
staleness signal on every panel that can silently serve old data.

- **DASH-01 — Rewrite `new_build_dashboard_server.py`'s module docstring, header comment,
  and startup banner.** CONFIRMED NEEDED — this is the single strongest finding in the
  whole audit (Q11). The file says "New Build paper-only reads... No Live VELO" while
  `_build_governed_card_from_live_snapshots` (lines 471-631) is a fully-built, frequently-hit
  code path that explicitly serves live production verdict data with
  `trust_policy: "LIVE_VERDICT_READ_ONLY_DASHBOARD"`. This is not a hypothetical edge case;
  it is the normal path on a normal raceday once Step 9 has run. The fix is documentation +
  banner text, not code — the underlying behavior (read-only, no writes, no Telegram, no
  staking) is genuinely safe; only the self-description is wrong.

- **DASH-02 — Add date-matching/staleness flags to the three un-scoped "_latest" files read
  by `/api/dashboard-truth`.** CONFIRMED NEEDED. `data/router_shadow_audit_latest.csv`,
  `data/doctrine_scorecard_latest.json`, `app/static/dashboard/sidecar_stack_latest.json`
  are read with zero date parameter (`new_build_dashboard_server.py:204,279,280`) — unlike
  the observability loader, which at least logs a mismatch warning. Recommend the same
  pattern: log/surface a mismatch flag when the artifact's own embedded date (if any) does
  not match the requested `date_str`.

- **DASH-03 — Make the `VELO_DASHBOARD_PUBLISH_ENABLED` env var either real or removed from
  the docstring.** CONFIRMED NEEDED. `publish_daily_predictions_to_dashboard.py`'s docstring
  (line 21) describes this flag as required, but it is never read anywhere in the executable
  code — the publish write is fully unconditional. Either wire the check in, or delete the
  misleading docstring line so nobody assumes there's a kill-switch that doesn't exist.

- **DASH-04 — Clarify "live" in operator-facing language across the dashboard chain.**
  CONFIRMED NEEDED, refined: this audit found the entire dashboard chain is
  poll-and-cache end to end — `publish_daily_predictions_to_dashboard.py` queries Supabase
  once per invocation and freezes a JSON snapshot; `new_build_dashboard_server.py` never
  queries Supabase at all, only reads whatever local artifact was last written. Recommend a
  single sentence added to operator docs: "Live" in this system always means "as of the last
  publish run," never "as of this HTTP request" — and the dashboard UI itself should print a
  generated_at timestamp prominently so the operator can self-judge freshness rather than
  trusting a "live" label.

## Pass 3 — Ops Harness Cleanup (OPS-01..04)

**Goal:** turn warn-only gates that guard real scoring-quality risk into blocking gates,
and give `--dry-run`/`--verdicts-only` behavior that matches their names.

- **OPS-01 — Make the RPDC sidecar coverage check (`_check_sidecar_date_match`,
  `src/velo/racecard_cache_gate.py:162-216`) blocking, or at minimum blocking above a lower
  threshold than the current 50%.** CONFIRMED NEEDED, with a caveat: `THE_ONE_TRUTH.md`
  itself documents (lines 303-306) that on the very first day the RP pipeline runs, RPDC
  legitimately has zero meaningful history and this is "expected and correct." A hard block
  at day zero would wrongly halt a cold-start system. Recommend the gate become blocking
  only once `racing_horse_runs` has demonstrated non-trivial history (e.g. after N days of
  successful evening ingest) — i.e. a graduated gate, not a permanent warn-only one.

- **OPS-02 — Restrict `VELO_FORCE_CARD` and the implicit cert-file bypass
  (`racecard_cache_gate.py:294-304`) to require an explicit, logged operator justification
  string, not just a truthy env var or the mere presence of a cert file.** CONFIRMED NEEDED.
  Two different ways to silently disable every blocking check exist today (env var, and
  cert-file `fixture_truth_status`) and neither requires the operator to state *why* on that
  specific date. At minimum, log the justification into the observability packet so it's
  auditable after the fact which days ran under a forced override.

- **OPS-03 — Thread `--dry-run` through to the three local file writes that currently ignore
  it** (`data/velo_prime_verdicts_*.json`, `data/timing_audit/runtime_timing_audit_*.json`,
  `data/velo_run_observability_*.json`). CONFIRMED NEEDED, with a lighter-touch alternative
  worth considering instead of fully suppressing these writes: since they are genuinely
  useful for rehearsing a run without side effects, an acceptable fix is tagging the
  filename or a `"dry_run": true` field inside the JSON itself, rather than suppressing the
  write outright — the risk is not that a dry-run writes a local file, it's that the file is
  indistinguishable from a real run's output after the fact.

- **OPS-04 — Rename or consolidate `persistence_enabled` / `verdict_persistence_enabled` in
  `_resolve_persistence_modes()` so the two keys either genuinely diverge or collapse to
  one name.** CONFIRMED NEEDED. They have never diverged in the current implementation
  (`run_prime_today.py:1403-1443`) despite being named as if `--verdicts-only` could
  independently gate `pipeline_runs` vs `velo_verdicts` — it cannot. Either implement the
  finer-grained control the names imply (if there's a real use case for persisting verdicts
  without opening a `pipeline_runs` row), or rename to a single `persistence_enabled` key to
  stop inviting the misreading found in this audit (Q15).

## Pass 4 — CI Reality Cleanup (CI-01..04)

**Goal:** give the actual daily pipeline the automated regression protection it currently
has none of.

- **CI-01 — Add a CI job that runs the general `tests/` suite (or at minimum the
  ops/src-related subset), not just `workers/ingestion_spine/`.** CONFIRMED NEEDED. This is
  the highest-leverage single change available: 0 of 22 live-daily/evening scripts named in
  this audit are exercised by any workflow today, and the one existing test file that does
  cover `run_prime_today.py` (`tests/test_run_prime_bootstrap.py`) is never run, which is why
  its stale `RACING_HEADERS` assertion has sat broken without anyone noticing.

- **CI-02 — Fix or delete the stale `RACING_HEADERS` assertion in
  `tests/test_run_prime_bootstrap.py:34`** before adding it to CI (CI-01), or it will be a
  guaranteed first-run red build. Simplest fix: delete the assertion (the attribute no
  longer exists in current architecture) or replace it with an equivalent assertion about
  whatever the current bootstrap function actually sets.

- **CI-03 — Extend `governed-safety.yml` (or a new workflow) to cover the 7 shadow-only
  overlay scripts with at least a smoke test** that asserts they do not write to Supabase or
  mutate `velo_verdicts`/model files, turning the doctrine's "hard law" (Q3,
  `THE_ONE_TRUTH.md:427-430`) from a documentation promise into an automated check. This is
  a new item not explicitly proposed by the operator but justified directly by the evidence
  that the hard law currently has zero code-level enforcement.

- **CI-04 — Add a lightweight CI check for the two "aspirational" env-var gaps found in this
  audit** (`VELO_DASHBOARD_PUBLISH_ENABLED` never read; `VELO_FORCE_CARD` un-logged) — e.g.
  a grep-based test (in the style already used by `governed-safety.yml`'s classification
  check) that fails if a docstring promises an env-var gate that the surrounding code never
  actually reads. This generalizes a pattern this audit found twice and would catch future
  recurrences cheaply.

---

## Summary of adjustments to the operator's original proposal

- SOURCE-02 needed a sharper finding: the button script isn't just unused, it actively
  bypasses the completeness gate on every run.
- SOURCE-04 needed narrowing: don't archive `run_results_sigma.py` (it's the LOCKED daily
  Sigma script) — the Racing-API reference inside it needs its own, smaller-scoped fix.
- OPS-01 needed a caveat for legitimate cold-start days (RPDC has no history on day one by
  design) — recommend a graduated gate, not an immediate hard block.
- CI-03 and CI-04 are new items, not in the operator's original 4-item-per-pass sketch,
  added because the evidence directly supports them (shadow-overlay hard law has zero code
  enforcement; the aspirational-env-var pattern recurred twice independently).

All other items (SOURCE-01, SOURCE-03, DASH-01 through DASH-04, OPS-02 through OPS-04,
CI-01, CI-02) are confirmed as originally scoped by the operator, each backed by the
file:line evidence in `mess_01_operator_brief.md`.
