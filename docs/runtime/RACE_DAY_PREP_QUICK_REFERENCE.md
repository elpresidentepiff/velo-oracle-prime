# Race Day Prep Quick Reference

Use this when preparing the next race day.

## 1. Industry / VÉLØ League Rail

Build the week/month/all-time league table with VÉLØ included:

```powershell
python scripts/audit/build_industry_selection_league.py
```

Main outputs:

- `data/reports/industry_selection_league_latest.md`
- `data/reports/industry_selection_league_latest.json`
- `data/reports/industry_selection_league_picks_latest.csv`

Key shadow rail:

```text
SHADOW: VÉLØ + NEWSPAPER >=10
```

Meaning:

```text
VÉLØ top pick matches the Racing Post embedded Newspaper Form horse with 10+ industry tips.
```

This rail is shadow-only evidence. It must not alter staking, Telegram, or live scoring.

## 2. Old VÉLØ Newspaper Form Prep

Parse the Racing Post embedded full-card capture and write the standard cache Old VÉLØ can read:

```powershell
python scripts/ops/parse_racing_post_racecard_capture.py --date YYYY-MM-DD --capture-label live-full-racepages-YYYY-MM-DD --write-standard-cache --execute
```

Expected files:

- `data/racing_post_account_parsed/YYYY-MM-DD/racecard_injection.json`
- `data/racecards_YYYY_MM_DD_standard.json`

Check:

```text
status = PASS
newspaper_form_present races = all races
top_newspaper_tips present
RPR policy = archive-only
```

## 3. New VÉLØ Passport Prep

Backfill missing passports from the final-card standard cache:

```powershell
python scripts/ops/new_build_passport_backfill_final_card.py --standard-cache data/racecards_YYYY_MM_DD_standard.json --date YYYY-MM-DD --capture-date CAPTURE_LABEL --execute
python scripts/ops/new_build_horse_passports.py
python scripts/ops/new_build_passport_bank_phase2.py --execute
python scripts/ops/new_build_current_card_feed.py --racecard-path data/racecards_YYYY_MM_DD_standard.json --execute
python scripts/ops/new_build_two_lane_score.py --date YYYY-MM-DD --execute
```

Expected New Build outputs:

- `data/new_build/reports/passport_bank_backfill_YYYY_MM_DD_latest.md`
- `data/new_build/features/rp_profile_passport_features_latest.parquet`
- `data/new_build/current_cards/current_card_passport_feed_latest.jsonl`
- `data/new_build/reports/two_lane_readiness_YYYY_MM_DD.md`

Readiness target:

```text
overall_status = READY
operational_lane = LANE_A_CORE_PASSPORT
passport coverage = 100% or clearly explained
intent coverage = 0% is acceptable/currently expected
RPR violations = 0
SP violations = 0
```

## 4. Hard Boundaries

- No Telegram from New Build.
- No staking from New Build.
- No live table writes from New Build.
- No RPR as model fuel.
- No same-race SP in morning model.
- Newspaper Form belongs to Old VÉLØ / industry audit, not Passport model features.
