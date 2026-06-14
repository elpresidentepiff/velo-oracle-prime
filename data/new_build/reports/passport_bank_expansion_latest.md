# Passport Bank Expansion Latest
Generated: 2026-06-03T23:36:24.048819Z

## Summary
- **Queued horses**: 12970
- **Queued for capture**: 2011
- **Next batch count**: 500
- **Captured/profiled already**: 3759
- **Parsed passports**: 3759
- **Total passports after run**: 3759
- **Duplicates**: 0
- **Failures / blocked no UID**: 0
- **No-form-history or captured-without-passport horses**: 0
- **Upcoming-race coverage rows**: 5534
- **Big Race Entries coverage rows**: 698
- **RPR violations**: 0

## Status Counts
| Status | Count |
|---|---:|
| NEEDS_SOURCE_REVIEW | 7200 |
| PASSPORT_EXISTS | 3759 |
| QUEUED_FOR_CAPTURE | 2011 |

## Source Counts
| Source | Count |
|---|---:|
| raw_profile_link_review | 7400 |
| upcoming_racecard | 5534 |
| current_racecard | 32 |
| big_race_entries | 4 |

## Capture Batches
| Batch | HTML | Sidecars | Manifest |
|---|---:|---:|---|
| passport-bank-batch-001-2026-05-25 | 500 | 500 | True |
| passport-bank-batch-002-2026-05-25 | 283 | 283 | True |
| passport-bank-big-race-entries-2026-05-25 | 28 | 28 | True |
| passport-bank-bulk-2026-05-30 | 0 | 0 | False |
| passport-bank-sources-2026-05-25 | 4 | 4 | True |

## Parsed Batches
| Batch | Horse Profiles | Races | Runners |
|---|---:|---:|---:|
| passport-bank-batch-001-2026-05-25 | 500 | 0 | 0 |
| passport-bank-batch-002-2026-05-25 | 283 | 0 | 0 |
| passport-bank-big-race-entries-2026-05-25 | 0 | 28 | 1008 |
| passport-bank-bulk-2026-05-30 | 0 | 0 | 0 |
| passport-bank-sources-2026-05-25 | 0 | 0 | 0 |

## Next Batch Sample
| RP UID | Horse | Source | Priority | URL |
|---|---|---|---:|---|
| 5906667 | A Little Something | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5906667/a-little-something/form |
| 7930857 | A Rose Adaay | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7930857/a-rose-adaay/form |
| 7015865 | A Time For Us | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7015865/a-time-for-us/form |
| 6296525 | A War Eagle | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/6296525/a-war-eagle/form |
| 7436646 | Abbey Scope | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7436646/abbey-scope/form |
| 3106233 | Abduction | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/3106233/abduction/form |
| 8259454 | Able Astra | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/8259454/able-astra/form |
| 9227124 | Aca Fast | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9227124/aca-fast/form |
| 7952284 | Acclaimed Freedom | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7952284/acclaimed-freedom/form |
| 9179712 | Adalo | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9179712/adalo/form |
| 6202583 | Addarella | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/6202583/addarella/form |
| 7834676 | Addmann | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7834676/addmann/form |
| 9317884 | Adeel | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9317884/adeel/form |
| 5906628 | Adelaide Bay | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5906628/adelaide-bay/form |
| 3617929 | Adjuvant | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/3617929/adjuvant/form |
| 8062541 | Aerial Silk | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/8062541/aerial-silk/form |
| 5692566 | Aeroinvincible | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5692566/aeroinvincible/form |
| 5031194 | Aestheticism | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5031194/aestheticism/form |
| 7639523 | Afjan | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7639523/afjan/form |
| 8309330 | Afraj | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/8309330/afraj/form |
| 5315435 | Age Of Baroque | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5315435/age-of-baroque/form |
| 7324714 | Ahead Of Fashion | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7324714/ahead-of-fashion/form |
| 9162125 | Aida | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9162125/aida/form |
| 8039750 | Aigeas | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/8039750/aigeas/form |
| 4922498 | Ailt An Chorrain | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/4922498/ailt-an-chorrain/form |

## Continuation Commands
- `python scripts/ops/build_rp_passport_bank_queue.py --execute`
- `python scripts/ops/racing_post_account_collector.py capture --date passport-bank-YYYY-MM-DD-N --url-list data/racing_post_url_lists/passport_bank_next_batch_latest.txt --delay-seconds 1.5 --execute`
- `python scripts/ops/parse_racing_post_account_capture.py --date passport-bank-YYYY-MM-DD-N --execute`
- `python scripts/ops/parse_rp_form_history.py --date passport-bank-YYYY-MM-DD-N`
- `python scripts/ops/new_build_horse_passports.py`