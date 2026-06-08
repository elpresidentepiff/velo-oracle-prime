# VÉLØ Race-Day Rescue: 2026-06-05

Generated: 2026-06-05T01:15Z

## Classification

```text
VELO_2026_06_05_RUN_RESCUED
OLD_VELO_OFFICIAL_RUN_PASS
NEW_BUILD_PAPER_RUN_PASS
FRESH_RP_RECAPTURE_REQUIRED
NO_TELEGRAM_SENT
```

## What Blocked

The first Old VÉLØ attempt used an early Racing Post capture from 2026-06-01.

```text
Old runner metadata coverage: 369 / 1110 = 33.2%
Blocking missing field: jockey
Gate result: BAD_RACECARD_CACHE_BLOCKED
```

The gate was correct. The early capture had many blank `J:` fields.

## What Fixed It

Fresh RP account recapture was run for all 56 June 5 race URLs.

```text
Raw folder: data/racing_post_account_raw/live-full-racepages-2026-06-05-refresh
Parsed injection: data/racing_post_account_parsed/live-full-racepages-2026-06-05-refresh/racecard_injection.json
Standard cache: data/racecards_2026_06_05_standard.json
Racecard merged files: data/racecard_merged/racecard_*_2026-06-05.json
```

Fresh metadata coverage:

```text
Old VÉLØ gate runners: 614
Metadata complete: 609 / 614 = 99.2%
Gate result: PASS
```

## Old VÉLØ Official Run

```text
Source: RP_MERGED
Races scored: 56 / 56
Runners normalized: 614
Persisted: 56 / 56
Telegram: contained / no-op
Observability packet: data/velo_run_observability_2026_06_05_06c23a66.json
Final status: PASS
```

## New Build Paper Run

```text
Races scored: 56
Runners scored: 614
Passport coverage: 607 / 614 = 98.86%
Missing/unraced passports: 7
Operational lane: LANE_A_CORE_PASSPORT
Intent coverage: 0 / 614, correctly unavailable
RPR violations: 0
SP violations: 0
Final status: READY
```

## Future Button Fix

`scripts/ops/velo_race_day_button.py` now prefers the parsed injection under the active capture label before falling back to the date folder. This prevents the button from rebuilding Old VÉLØ merged files from an older stale parse after a fresh recapture.

## Operator Trust

Proceed with the June 5 VÉLØ day. The day was not lost; the missing data was recovered by recapturing RP after jockey declarations were available.
