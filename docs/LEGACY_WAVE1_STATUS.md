# Legacy Wave 1 Status

Wave 1 containment covers the 10 highest-risk legacy scripts identified in the `Legacy Script Retirement / Quarantine` ticket.

| Script | Status | Candidate Rewrite Later | Override Env Var | Fallback Secret Material Removed | `py_compile` Passed |
| --- | --- | --- | --- | --- | --- |
| `scripts/evolve_playbook_g_from_sigma_audits.py` | quarantined | no | `VELO_LEGACY_ALLOW_EVOLVE_PLAYBOOK_G` | yes | yes |
| `scripts/ingest_rp_stats.py` | quarantined | no | `VELO_LEGACY_ALLOW_INGEST_RP_STATS` | yes | yes |
| `scripts/shadow_comparison_g_provisional.py` | quarantined | no | `VELO_LEGACY_ALLOW_SHADOW_COMPARISON_G` | yes | yes |
| `scripts/ingest_racing_profiles.py` | quarantined | yes | `VELO_LEGACY_ALLOW_INGEST_RACING_PROFILES` | yes | yes |
| `scripts/build_rpdc_profiles.py` | quarantined | yes | `VELO_LEGACY_ALLOW_BUILD_RPDC_PROFILES` | yes | yes |
| `scripts/patch_g_doctrine_simulate.py` | quarantined | no | `VELO_LEGACY_ALLOW_PATCH_G_DOCTRINE` | yes | yes |
| `scripts/query_trainer_field_truth.py` | quarantined | no | `VELO_LEGACY_ALLOW_QUERY_TRAINER_FIELD_TRUTH` | yes | yes |
| `scripts/backfill_race_truth.py` | quarantined | no | `VELO_LEGACY_ALLOW_BACKFILL_RACE_TRUTH` | yes | yes |
| `scripts/apply_approved_proposals.py` | quarantined | no | `VELO_LEGACY_ALLOW_APPLY_APPROVED_PROPOSALS` | yes | yes |
| `scripts/backfill_miss_evidence.py` | quarantined | no | `VELO_LEGACY_ALLOW_BACKFILL_MISS_EVIDENCE` | yes | yes |

Notes:
- Wave 1 was containment-only: no active spine changes, no behavioral refactors, no moves, and no deletions.
- `scripts/ingest_racing_profiles.py` and `scripts/build_rpdc_profiles.py` remain quarantine-now / candidate-rewrite-later.
- Some legacy files in this set had pre-existing dirty or untracked state before Wave 1. The Wave 1 changes were limited to quarantine markers, fallback-secret removal, and explicit execution gates.
