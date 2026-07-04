# SIGMA-25 — Persisted Source Trace — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | code-read + local-artifact audit | NO SUPABASE WRITES, NO CODE CHANGES

---

## Correction to mission premise

Two named files in the mission spec do not exist in this repo and were not traced as named:
- `scripts/ops/fresh_daily_predictions_to_supabase.py` — no such file found anywhere in the tree.
- `scripts/ops/build_rpdc_daily.py` — exists but is not in the `velo_verdicts` write path (confirmed via grep: no `velo_verdicts`/`insert`/`upsert` calls in that file).

The actual writer is `app/services/velo_prime_service.py::persist_race_predictions()`, called from `scripts/ops/run_prime_today.py` STEP 4 (line 2132). This is the real target traced below.

---

## 1. Are pick_sp / field_size / race_type actually available to the live writer?

**Mixed — one is persisted under a different name, one is persisted but not selected, one is never persisted at all.**

- **field_size** — **persisted**, but as `predicted_field_size` (not `field_size`), computed as `len(race.get("runners") or [])` (`velo_prime_service.py:944`). It is a real top-level column on `velo_verdicts`, gated behind the `honesty_labels` optional-column group (migration `20260418_001`). **However, `run_results_sigma.py`'s own `select=` clause (line 382) does not request this column today** — so even though it's in the table, the LOCKED writer never reads it. This is a one-line select-clause fix, not a schema question.
- **pick_sp** — **persisted, indirectly.** There is no `pick_sp` column. But `full_analysis.predictions` (a JSON array of every runner's raw prediction dict, written verbatim at `velo_prime_service.py:1038/1061`) **is** selected by `run_results_sigma.py` today (`full_analysis` is in the select list, line 382) and each runner dict inside it carries `sp_dec` and `horse_id`. Confirmed directly in a local verdict artifact (`data/velo_prime_verdicts_2026_06_30.json`, race 922170): `top.sp_dec = 3.5`, `top.horse_id = 5021393`. To get `pick_sp` for a sigma row: find the entry in `full_analysis.predictions` whose `horse_id == top_rank_horse_id`, read `.sp_dec`. This is a lookup, not a flat field.
- **race_type** — **not persisted anywhere.** Confirmed absent from the `row` dict built in `persist_race_predictions()` (no `race_type`/`type` key at all), absent from `full_analysis_data` (only `predictions`/`plot_intel`/`governance` keys), and absent from the local verdict JSON fallback files (`velo_prime_verdicts_2026_06_29.json`, `..._30.json` — checked directly, key not present at any level). It exists only transiently in `run_prime_today.py`'s in-memory `race` dict during scoring (used at lines 1936/1938/1942 for BHA lookups and claiming-race detection) and is discarded after the scoring loop. **This field genuinely does not exist downstream of scoring today — writing it live requires a schema change (new column) and a code change to actually persist `race.get("type")`, not just a sigma-side read fix.**

## 2. Is verdict_id available inline or only via separate reconciliation?

**Only via reconciliation, and it requires a select-clause fix too.** `run_results_sigma.py`'s current select (line 382) does not request `velo_verdicts`'s own row identifier (`id`) — only `race_id` and other content columns. `race_id` alone is not usable as `sigma_audits.verdict_id` because (per SUPA-02) `velo_verdicts` can have duplicate rows per `race_id` (re-scored races) and the sigma script's own dedup logic (lines 499-508) already picks "latest `generated_at`" to resolve exactly this ambiguity. `verdict_id` should be that same picked row's `id`, joined on `race_id` (+ `generated_at` tie-break, the same key sigma already computes internally) — a small addition to the select clause plus carrying `id` through the `predictions[rid]` dict, not a new query.

## 3. Which sources are confirmed persisted?

- `field_size` (as `predicted_field_size`) — confirmed persisted, confirmed unselected by sigma's query.
- `pick_sp` (via `full_analysis.predictions[*].sp_dec` + `horse_id` match) — confirmed persisted, confirmed already selected (full_analysis is in the query) but not yet extracted/used.
- `verdict_id` (as `velo_verdicts.id`) — presumed persisted (standard PK column on every Supabase table use in this schema), confirmed unselected — **not independently confirmed via a live Supabase query in this pass** (this audit stayed read-only against local code/artifacts only per mission scope; a `SELECT id FROM velo_verdicts LIMIT 1` would close this out).

## 4. Which sources are only transient?

- `race_type` — confirmed transient-only. Exists in `run_prime_today.py`'s in-memory `race` dict during scoring, never written to any persisted store (Supabase column, `full_analysis` JSON, or local JSON fallback).

## 5. What fallback sources are safe?

None needed for `field_size`, `pick_sp`, or `verdict_id` — all three already have a live Supabase source once the select clause and extraction logic are added. For `race_type`, the only viable fallback is the RP racecard/scoring input itself (`race.get("type")` inside `run_prime_today.py`), which means `race_type` can only be fixed by adding it to `persist_race_predictions()`'s write payload (a `velo_verdicts` schema change) — not by changing anything in `run_results_sigma.py`, since there is nothing to read that doesn't already exist. The `data/racecard_merged/*.json` PDF-intel files were checked as a possible fallback and are **not usable**: their `race_info` field is a free-text string in the sampled file, not a structured `type`/`race_type` key.

## 6. What code patch would be safe next?

Two independent, separately-scoped patches:

1. **`run_results_sigma.py` select-clause + extraction patch** (safe to draft next, pending operator sign-off since LOCKED): add `predicted_field_size,id` to the existing `select=` string (line 382, both occurrences), then in the `sigma_row` build (lines 1066-1085) add `"field_size": v.get("predicted_field_size")`, `"pick_sp": <lookup in full_analysis.predictions by horse_id>`, `"verdict_id": v.get("id")`. This only reads fields already returned by Supabase (or requestable with a one-line select change) — no schema migration required.
2. **`persist_race_predictions()` schema+code patch for `race_type`** — separate, larger-scoped: requires a new Supabase migration (new `race_type` column on `velo_verdicts`, mirroring the pattern of the other optional-column groups already in this function) plus a one-line addition (`"race_type": race.get("type")`) to the `row` dict. This is a live-writer schema change, not a sigma-read fix, and should not be bundled with patch #1.

## 7. What tests must be written with the patch?

- Unit test on the `sigma_row` builder: given a fixture `predictions[race_id]` dict with `full_analysis.predictions` containing a `sp_dec`-bearing runner matching `top_rank_horse_id`, assert `pick_sp` extracts the correct value.
- Unit test: given a `predictions[race_id]` dict with `predicted_field_size` present/absent, assert `field_size` is populated/`None` correctly (no exception on missing key).
- Unit test: given a `predictions[race_id]` dict with `id` present, assert `verdict_id` is written as that id; given no matching row, assert `None` (never guessed).
- Regression test: assert `actual_winner_sp`/`decision_tier`/all currently-working fields are unchanged by the patch (protect the known-good path).
- Integration/dry-run test: run the patched script against a fixture day's worth of `velo_verdicts` and diff the resulting `sigma_row` payloads against the pre-patch payloads, confirming only the 3 new keys differ.

## 8. What must not be written yet?

Nothing. No Supabase write, no `run_results_sigma.py` patch, no `persist_race_predictions()` patch, no migration were performed or drafted as executable code in this audit. Both patches described in Q6 are proposals for the next mission(s), gated on explicit operator sign-off since `run_results_sigma.py` is LOCKED and `race_type` requires a schema migration.

---

## Scope limitation
No live Supabase query was executed in this pass (per REPORT_ONLY / no-writes scope, and to avoid re-spending the read budget already used in SUPA-02/SIGMA-23). The claim that `velo_verdicts` has a queryable `id` PK column is inferred from standard Supabase table conventions and the fact every other table in this schema (per SUPA-02's table map) is queried via PostgREST which requires a PK — it was not directly confirmed with a `select=id` call. This is the one open item before patch #1 (verdict_id) can be called fully proven; everything else in this report (field_size, pick_sp, race_type) is confirmed directly from code and local artifact inspection, not inferred.

## Required Classifications
- SIGMA_25_PERSISTED_SOURCE_TRACE_COMPLETE
- NO_SUPABASE_WRITES
- NO_CODE_CHANGE
- LOCKED_SIGMA_WRITER_NOT_PATCHED
- PICK_SP_SOURCE_CONFIDENCE_CONFIRMED_PERSISTED
- FIELD_SIZE_SOURCE_CONFIDENCE_CONFIRMED_PERSISTED
- RACE_TYPE_SOURCE_CONFIDENCE_CONFIRMED_TRANSIENT_ONLY
- VERDICT_ID_SOURCE_CONFIDENCE_SOURCE_NEEDS_SUPABASE_QUERY
- PATCH_READY — for field_size/pick_sp/verdict_id (pending operator sign-off, LOCKED file)
- PATCH_BLOCKED — for race_type (requires new Supabase migration first)
- SUPABASE_WRITE_APPROVAL_REQUIRED
- REPORT_ONLY
