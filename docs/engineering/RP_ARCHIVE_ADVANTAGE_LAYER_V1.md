# RP Archive Advantage Layer V1

## Purpose

Use multi-day Racing Post account archive data to prepare horse and race intelligence before VÉLØ scores. This is not model fuel. It is context, warning, contradiction, and operator preparation.

## Data Sources

- Local Racing Post account captures.
- Parsed racecard payloads.
- Parsed horse profile pages.
- Form, entries, stats, quotes, pedigree, sales, and notes tabs where available.
- RPDC memory where already available.

## Scoring Boundary

Racing Post archive data is `ARCHIVE_CONTEXT_ONLY_NOT_SCORING`.

RPR is `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`.

No RP archive field may enter:

- VP
- improvement score
- model inputs
- router/staking
- Telegram picks
- Playbook G
- live learning

## Horse Dossiers

Horse dossiers summarize identity, trainer, owner, sire/dam/dam sire, age, sex, country, recent form, entries, quotes, stats, pedigree, sales, notes, headgear, wind surgery, days since run, newspaper comments, tip count, and archive-only OR/TS/RPR.

Possible flags:

- `HORSE_DOSSIER_READY`
- `INSUFFICIENT_PROFILE`
- `PEDIGREE_POSITIVE`
- `TRAINER_INTENT_SIGNAL`
- `HEADGEAR_CHANGE_ALERT`
- `WIND_SURGERY_ALERT`
- `MARKET_OVERHYPE_RISK`

## Race Dossiers

Race dossiers summarize race shape, runner count, unknown/unexposed count, headgear/wind cluster, trainer clusters, pedigree clusters, newspaper tip concentration, and archive confidence.

Possible flags:

- `CLEAN_CONTEXT`
- `HYPE_TRAP_RISK`
- `UNKNOWN_HEAVY`
- `TRAINER_CLUSTER`
- `PEDIGREE_SIGNAL`
- `MARKET_CONCENTRATED`
- `LOW_CONFIDENCE_ARCHIVE`

## VÉLØ Comparison

After official VÉLØ predictions are locked, compare the top picks to archive context. Do not change predictions.

Possible classifications:

- `VELO_CONFIRMED_BY_CONTEXT`
- `VELO_AGAINST_HYPE`
- `PUBLIC_OVERLOAD_TRAP`
- `QUIET_PROFILE_POSITIVE`
- `ARCHIVE_CONTEXT_WARNING`
- `INSUFFICIENT_ARCHIVE_DATA`

## Watchlist

The next-week watchlist highlights future entry repeats, first-time headgear, wind surgery return, trainer intent, pedigree positives, course/distance memory, market hype risk, quiet profile positives, RPDC improvers, and unknown/unexposed horses.

## Confirmation

This layer has no scoring impact. It prepares the battlefield; it does not steer the VÉLØ engine.
