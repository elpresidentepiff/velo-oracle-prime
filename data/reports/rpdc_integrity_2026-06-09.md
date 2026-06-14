# RPDC Integrity — 2026-06-09

**Status:** RPDC_UNKNOWN · generated 2026-06-10T16:11:39.866454+00:00 · READ-ONLY

- Races (local backup): 33
- Locally attached: 0
- Supabase rows: 33
- Per-status: {"RPDC_OK": 33}
- Detail: ATTACH_FAILURE_SUSPECTED: runner_release_candidates rows exist for the date but every race attached no_data at scoring time (race-ID mismatch?)

Statuses: RPDC_OK / RPDC_LOCAL_ONLY / RPDC_PERSIST_GAP / RPDC_CORRUPTED / RPDC_UNKNOWN.
Repair path: operator-gated historical repair tool (dry-run first). This checker cannot write.