# RPDC Integrity — 2026-07-04

**Status:** RPDC_UNKNOWN · generated 2026-07-04T21:43:41.427776+00:00 · READ-ONLY

- Races (local backup): 51
- Locally attached: 0
- Supabase rows: 51
- Per-status: {"RPDC_UNKNOWN": 51}
- Detail: ATTACH_FAILURE_SUSPECTED: runner_release_candidates rows exist for the date but every race attached no_data at scoring time (race-ID mismatch?)

Statuses: RPDC_OK / RPDC_LOCAL_ONLY / RPDC_PERSIST_GAP / RPDC_CORRUPTED / RPDC_UNKNOWN.
Repair path: operator-gated historical repair tool (dry-run first). This checker cannot write.