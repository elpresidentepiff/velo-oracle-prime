# Passport Bank Expansion Latest
Generated: 2026-05-26T02:08:05.224792Z

## Summary
- **Queued horses**: 3595
- **Queued for capture**: 0
- **Next batch count**: 0
- **Captured/profiled already**: 1139
- **Parsed passports**: 987
- **Total passports after run**: 987
- **Duplicates**: 0
- **Failures / blocked no UID**: 0
- **No-form-history or captured-without-passport horses**: 152
- **Upcoming-race coverage rows**: 1091
- **Big Race Entries coverage rows**: 698
- **RPR violations**: 0

## Status Counts
| Status | Count |
|---|---:|
| NEEDS_SOURCE_REVIEW | 2456 |
| PASSPORT_EXISTS | 987 |
| CAPTURED_NEEDS_FORM_HISTORY_OR_NO_RUNS | 152 |

## Source Counts
| Source | Count |
|---|---:|
| raw_profile_link_review | 2456 |
| upcoming_racecard | 1091 |
| current_racecard | 44 |
| big_race_entries | 4 |

## Capture Batches
| Batch | HTML | Sidecars | Manifest |
|---|---:|---:|---|
| passport-bank-batch-001-2026-05-25 | 500 | 500 | True |
| passport-bank-batch-002-2026-05-25 | 283 | 283 | True |
| passport-bank-big-race-entries-2026-05-25 | 28 | 28 | True |
| passport-bank-sources-2026-05-25 | 4 | 4 | True |

## Parsed Batches
| Batch | Horse Profiles | Races | Runners |
|---|---:|---:|---:|
| passport-bank-batch-001-2026-05-25 | 500 | 0 | 0 |
| passport-bank-batch-002-2026-05-25 | 283 | 0 | 0 |
| passport-bank-big-race-entries-2026-05-25 | 0 | 28 | 1008 |
| passport-bank-sources-2026-05-25 | 0 | 0 | 0 |

## Next Batch Sample
| RP UID | Horse | Source | Priority | URL |
|---|---|---|---:|---|

## Continuation Commands
- `python scripts/ops/build_rp_passport_bank_queue.py --execute`
- `python scripts/ops/racing_post_account_collector.py capture --date passport-bank-YYYY-MM-DD-N --url-list data/racing_post_url_lists/passport_bank_next_batch_latest.txt --delay-seconds 1.5 --execute`
- `python scripts/ops/parse_racing_post_account_capture.py --date passport-bank-YYYY-MM-DD-N --execute`
- `python scripts/ops/parse_rp_form_history.py --date passport-bank-YYYY-MM-DD-N`
- `python scripts/ops/new_build_horse_passports.py`