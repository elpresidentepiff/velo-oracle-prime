# Source Value Matrix V1

## Objective

Compare Racing Post, Racing API, VÉLØ, Sigma, and RPDC source value horse-by-horse. The first pilot starts with Bow Echo and the captured 2026-05-25 horse dossier set.

## Outputs

- `data/reports/source_value_matrix_latest.json`
- `data/reports/source_value_matrix_latest.md`
- `data/reports/bow_echo_source_profile.md`
- `data/reports/source_uniqueness_audit_latest.md`
- `data/reports/archive_context_value_latest.json`
- `data/reports/archive_context_value_latest.md`

## Classifications

- `UNIQUE_TO_RP`
- `UNIQUE_TO_RACING_API`
- `UNIQUE_TO_VELO`
- `DUPLICATED`
- `MISSING`
- `USEFUL_FOR_ARCHIVE`
- `USEFUL_FOR_SHADOW`
- `DO_NOT_USE_FOR_SCORING`

## Boundary

This matrix is read-only. It creates reports only. It does not change scoring, model inputs, router, staking, Telegram, Playbook G, live state, or learning state.
