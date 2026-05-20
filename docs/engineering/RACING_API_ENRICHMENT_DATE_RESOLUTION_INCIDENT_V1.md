# INCIDENT REPORT: Racing API Enrichment Date Resolution
**Date:** 2026-05-02
**Status:** STABILIZATION IN PROGRESS

## 1. The Failure
The `racing_api_enrichment_operator_card.py` failed to produce statistics for race days, reporting 0% coverage despite statistics existing in the database and the enrichment adapter being functional.

## 2. Root Cause: Date vs. Provenance
The script incorrectly used `generated_at` as the primary race-day selector.
- **`generated_at`**: The timestamp of when a database row was written or updated.
- **`race date`**: The actual day the race occurs.
When verdicts were regenerated (e.g., during a repair mission), their `generated_at` changed to "today," causing the selector to miss them when looking for "yesterday's" data.

## 3. The False Trail (Process Failure)
The agent incorrectly assumed that missing coverage in the report implied data was not persisted in `full_analysis`. This led to:
- Unnecessary edits to `app/services/velo_prime_service.py` (Live Scorer).
- Unnecessary edits to `src/intelligence/velo_prime_ensemble.py` (Ensemble).
- Discovery later that the data **was** correctly persisted all along; only the retrieval query was flawed.

## 4. The Resolution
- **Identity Rule:** Use `race_id` manifest from local racecards as the definitive list of races for a day.
- **Retrieval:** Fetch verdicts from Supabase using the manifest list (`IN (race_id_list)`).
- **Provenance:** `generated_at` is demoted to a display-only field for forensic tracking.

## 5. Files Affected during Chase
- `app/services/velo_prime_service.py`
- `src/intelligence/velo_prime_ensemble.py`
- `scripts/racing_api_enrichment_operator_card.py`
- `src/velo/race_metadata_resolver.py`
- `src/velo/racing_api_stat_adapter.py`
