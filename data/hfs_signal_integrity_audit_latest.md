
======================================================================
HFS SIGNAL INTEGRITY AUDIT
Generated: 2026-05-09T00:07:26.663162Z
OVERALL STATUS: HFS_TRAINING_BLOCKED
======================================================================

## Table: historical_feature_store  |  Classification: HFS_TRAINING_BLOCKED

  Total rows:                        0
  2026+ rows (live era):             0
  Pre-2026 archive:                  0

  MPI Signal:
    Null count:                      0  (0.0%)

  Chaos Bloom Signal:
    Null count:                      0  (0.0%)

  Signal contract versions:

  Winner parity:   n/a
  Placed parity:   n/a
  Duplicates:      0

  Key field null rates:


## Table: velo_features  |  Classification: HFS_TRAINING_BLOCKED

  Total rows:                        0
  2026+ rows (live era):             0
  Pre-2026 archive:                  0

  MPI Signal:
    Null count:                      0  (0.0%)

  Chaos Bloom Signal:
    Null count:                      0  (0.0%)

  Signal contract versions:

  Winner parity:   n/a
  Placed parity:   n/a
  Duplicates:      0

  Key field null rates:


## Table: runner_derived_features  |  Classification: HFS_TRAINING_BLOCKED

  Total rows:                        0
  2026+ rows (live era):             0
  Pre-2026 archive:                  0

  MPI Signal:
    Null count:                      0  (0.0%)

  Chaos Bloom Signal:
    Null count:                      0  (0.0%)

  Signal contract versions:

  Winner parity:   n/a
  Placed parity:   n/a
  Duplicates:      0

  Key field null rates:


======================================================================
FINAL CLASSIFICATION: HFS_TRAINING_BLOCKED
======================================================================
BLOCKED REASONS:
  - historical_feature_store: TABLE_EMPTY_OR_NOT_FOUND
  - velo_features: TABLE_EMPTY_OR_NOT_FOUND
  - runner_derived_features: TABLE_EMPTY_OR_NOT_FOUND

Playbook G training: BLOCKED — resolve issues above before training.

Recommendation: HFS training blocked. Steps to fix: (1) Run backfill_hfs_mpi_chaos_bloom.py --apply (requires DB password). (2) Re-run backfill_historical_feature_store.py --year 2026 --only-null-signals. (3) Re-run this audit to confirm HFS_TRAINING_READY.

