# Global Clean Spine Audit V4

## Authority Model
- Accepted historical training authority = `race_results distinct accepted events + races.runners_count + accepted historical_feature_store rows`
- Known caveat = `direct runner_results join has legacy horse-id drift and is not the authority for Playbook G V2 training cohort.`

- Accepted events: `1697`
- Accepted runner rows: `18575`
- Accepted HFS rows: `18575`
- Parity pass: `True`
- Winner parity: `True`
- Duplicate race_id count: `0`
- Duplicate event_key count: `0`
- Duplicate race_id+horse_id count: `0`
- Missing / orphan HFS rows: `0 / 0`
- Vector distribution: `{"37": 18575}`
- MPI nulls / variance: `0 / 894.6195363333167`
- chaos_bloom nulls / variance: `0 / 60.28016533286081`
- Macro-year mismatch: `0`
- Provenance completeness: `True`
- Historical doctrine contract complete: `True`
