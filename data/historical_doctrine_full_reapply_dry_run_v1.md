# Historical Doctrine Full Reapply Dry Run V1

- Accepted events evaluated: `1697`
- Runner rows evaluated: `18575`
- Prior coverage: `0=7647, 1+=10928, 3+=5744`
- dist_f before: `{"min": 5.0, "max": 19.0, "variance": 0.8955305170374369}`
- dist_f after: `{"min": 4.0, "max": 27.0, "variance": 9.870987087015827}`
- Leakage rows: `0`
- Outcome exclusion: `pass`
- Runtime estimate: `{"dry_run_elapsed_seconds": 96.8, "estimated_upsert_batches_at_100_rows": 186, "estimated_full_write_seconds": 199.48}`
- Recommended batches: `{"recommended_strategy": "manifest_scoped_batches", "recommended_event_batch_size": 100, "recommended_runner_row_batch_size": 1000, "estimated_event_batches": 17, "estimated_runner_batches": 19, "note": "Preserve existing OASIS block boundaries where manifests already exist; otherwise synthesize write manifests at roughly 100 races / 1000 runner rows."}`
- Go/No-Go: `GO`

## Risks
- Accepted-spine-only prior history underestimates total horse and trainer context because rejected or non-OASIS races are intentionally excluded.
- Rows with zero prior runs remain on default doctrine values by design; this is coverage-limited, not leakage-driven.
- decoy_support_flag and cash_run_flag may remain constant if the accepted cohort rarely meets their conditions.
- Name-normalization collisions remain a theoretical risk when horse names collapse after country-suffix stripping, though none were observed in the Block 025 smoke.
