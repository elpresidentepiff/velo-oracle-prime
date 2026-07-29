# Passport Bank Expansion Latest
Generated: 2026-07-10T22:36:32.317467Z

## Summary
- **Queued horses**: 16946
- **Queued for capture**: 2908
- **Next batch count**: 500
- **Captured/profiled already**: 7807
- **Parsed passports**: 7807
- **Total passports after run**: 7958
- **Duplicates**: 0
- **Failures / blocked no UID**: 0
- **No-form-history or captured-without-passport horses**: 0
- **Upcoming-race coverage rows**: 10693
- **Big Race Entries coverage rows**: 0
- **RPR violations**: 0

## Status Counts
| Status | Count |
|---|---:|
| PASSPORT_EXISTS | 7807 |
| NEEDS_SOURCE_REVIEW | 6231 |
| QUEUED_FOR_CAPTURE | 2908 |

## Source Counts
| Source | Count |
|---|---:|
| upcoming_racecard | 10693 |
| raw_profile_link_review | 6243 |
| current_racecard | 10 |

## Capture Batches
| Batch | HTML | Sidecars | Manifest |
|---|---:|---:|---|
| passport-bank-2026-07-08-1 | 500 | 500 | True |
| passport-bank-2026-07-08-2 | 500 | 500 | True |
| passport-bank-2026-07-10-1 | 244 | 244 | True |

## Parsed Batches
| Batch | Horse Profiles | Races | Runners |
|---|---:|---:|---:|
| passport-bank-2026-07-08-1 | 500 | 0 | 0 |
| passport-bank-2026-07-08-2 | 500 | 0 | 0 |
| passport-bank-2026-07-10-1 | 244 | 0 | 0 |
| passport-bank-batch-001-2026-05-25 | 500 | 0 | 0 |
| passport-bank-batch-002-2026-05-25 | 283 | 0 | 0 |
| passport-bank-big-race-entries-2026-05-25 | 0 | 28 | 1008 |
| passport-bank-bulk-2026-05-30 | 0 | 0 | 0 |
| passport-bank-sources-2026-05-25 | 0 | 0 | 0 |

## Next Batch Sample
| RP UID | Horse | Source | Priority | URL |
|---|---|---|---:|---|
| 8048359 | Admiral Will Brown | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/8048359/admiral-will-brown/form |
| 9522179 | Aghadrum Boy | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9522179/aghadrum-boy/form |
| 9503902 | Al Wathba | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9503902/al-wathba/form |
| 7935114 | Amber Hamur | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7935114/amber-hamur/form |
| 9424782 | Annie Batt | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9424782/annie-batt/form |
| 7360551 | Arabian Force | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7360551/arabian-force/form |
| 3586957 | Arch Enemy | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/3586957/arch-enemy/form |
| 7613508 | Art Lover | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7613508/art-lover/form |
| 4438455 | Autocrat | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/4438455/autocrat/form |
| 5920303 | Back In Black | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5920303/back-in-black/form |
| 5884257 | Beauty By My Side | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5884257/beauty-by-my-side/form |
| 3500896 | Beauzon | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/3500896/beauzon/form |
| 9263895 | Bincimbal | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9263895/bincimbal/form |
| 9004867 | Brandenburg | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9004867/brandenburg/form |
| 5113814 | Calafrio | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/5113814/calafrio/form |
| 9481216 | Call Of The Sea | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9481216/call-of-the-sea/form |
| 9522193 | Candle Glow | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9522193/candle-glow/form |
| 9517089 | Channel Islands | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9517089/channel-islands/form |
| 9517088 | Chertsey | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/9517088/chertsey/form |
| 4839350 | Christian David | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/4839350/christian-david/form |
| 6238152 | Danger Bay | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/6238152/danger-bay/form |
| 4891158 | Daonethatgotaway | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/4891158/daonethatgotaway/form |
| 6074555 | Dash Of Azure | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/6074555/dash-of-azure/form |
| 8144016 | David Of Athens | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/8144016/david-of-athens/form |
| 7525344 | Dialin For Dollars | upcoming_racecard | 10 | https://www.racingpost.com/profile/horse/7525344/dialin-for-dollars/form |

## Continuation Commands
- `python scripts/ops/build_rp_passport_bank_queue.py --execute`
- `python scripts/ops/racing_post_account_collector.py capture --date passport-bank-YYYY-MM-DD-N --url-list data/racing_post_url_lists/passport_bank_next_batch_latest.txt --delay-seconds 1.5 --execute`
- `python scripts/ops/parse_racing_post_account_capture.py --date passport-bank-YYYY-MM-DD-N --execute`
- `python scripts/ops/parse_rp_form_history.py --date passport-bank-YYYY-MM-DD-N`
- `python scripts/ops/new_build_horse_passports.py`