# Race Day Prep: 2026-06-05

Generated: 2026-06-05T00:33Z

## Classification

```text
JUNE_5_RACE_DAY_PREP_READY
OLD_VELO_NEWSPAPER_FORM_READY
NEW_BUILD_PASSPORT_READY
NEW_BUILD_LANE_A_CORE_PASSPORT_READY
INTENT_PAPER_ONLY_NO_LIVE_COVERAGE
RPR_SP_CLEAN
```

## Old VÉLØ Newspaper Form

Racing Post embedded full-card capture is parsed and standard-cache ready.

```text
Capture label: live-full-racepages-2026-06-05
Parsed injection: data/racing_post_account_parsed/2026-06-05/racecard_injection.json
Standard cache: data/racecards_2026_06_05_standard.json
Status: PASS
Races: 56
Runners in RP injection: 1110
Courses: Bath, Clonmel, Doncaster, Epsom, Fairyhouse, Goodwood, Musselburgh, Saratoga, Thirsk
Newspaper Form present: 56 / 56 races
Top newspaper tips rows: 280
RPR policy: archive-only
```

Command used:

```powershell
python scripts/ops/parse_racing_post_racecard_capture.py --date 2026-06-05 --capture-label live-full-racepages-2026-06-05 --write-standard-cache --execute
```

## New VÉLØ Passports

Passport bank and current-card feed are ready for June 5.

```text
Passport bank total: 6168
Backfill classification: PASSPORT_BANK_BACKFILL_COMPLETE
Missing passports before backfill: 105
Passports created: 103
Missing passports after backfill: 0
Final-card passport coverage: 1110 / 1110 = 100.0%
Champion feature coverage: 1110 / 1110 = 100.0%
Intent coverage: 0 / 1110 = 0.0%
RPR violations: 0
SP violations: 0
```

Key outputs:

- `data/new_build/reports/passport_bank_backfill_2026_06_05_latest.md`
- `data/new_build/reports/horse_passport_v2_latest.md`
- `data/new_build/reports/rp_profile_passport_feature_matrix_latest.md`
- `data/new_build/current_cards/current_card_passport_feed_latest.jsonl`
- `data/new_build/reports/two_lane_readiness_2026_06_05.md`

Commands used:

```powershell
python scripts/ops/new_build_passport_backfill_final_card.py --standard-cache data/racecards_2026_06_05_standard.json --date 2026-06-05 --capture-date passport-jun05-07-b1 --execute
python scripts/ops/new_build_horse_passports.py
python scripts/ops/new_build_passport_bank_phase2.py --execute
python scripts/ops/new_build_current_card_feed.py --racecard-path data/racecards_2026_06_05_standard.json --execute
python scripts/ops/new_build_two_lane_score.py --date 2026-06-05 --execute
```

## New Build Scoring State

```text
Overall status: READY
Races scored: 56
Runners scored: 1110
Operational lane: LANE_A_CORE_PASSPORT
Lane B: PAPER_ONLY_NO_INTENT
RPR violations: 0
SP violations: 0
```

## Shadow Rail To Watch

The industry league now includes VÉLØ inside the same table and tracks:

```text
SHADOW: VÉLØ + NEWSPAPER >=10
```

Current stored result:

```text
Latest week: 10 decisions, 6 wins, 3 places, 60.0% SR, 90.0% Frame
All stored: 11 decisions, 6 wins, 3 places, 54.5% SR, 81.8% Frame
```

This remains shadow-only. It is evidence for review, not an execution rule.

## Next Operator Checklist

1. If June 5 card changes, recapture/reparse the RP full-card file.
2. Re-run `parse_racing_post_racecard_capture.py` with `--write-standard-cache`.
3. Re-run New Build current-card feed and two-lane scorer.
4. Keep Intent marked unavailable unless genuinely computable.
5. Do not run Telegram/staking/New Build live writes.
