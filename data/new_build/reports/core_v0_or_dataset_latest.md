# Core V0_OR Challenger Dataset
Generated: 2026-05-25T21:57:46.938118Z

## OR Diagnosis
- `or_rating` in raceform_clean has 100% coverage but 41% are `'–'` (unrated horses: maidens, novice stakes)
- `or_num` in v17_features had 40% nulls — correct, reflects real absence of handicap mark
- Fix: derive `official_rating` (numeric, 0 for unrated) + `is_rated` flag
- `or_vs_field` (relative OR) already in Core V0 at 100% — retained

## Coverage
- official_rating coverage (Flat): 59.1% rated

## Features Added vs Core V0
- `official_rating` — absolute OR value (0 when unrated)
- `is_rated` — 1 if horse has a handicap mark, 0 otherwise

## Dataset Size
| Split | Rows |
|---|---|
| Train (2015-2023) | 987,511 |
| Val (2024) | 117,299 |
| Test (2025) | 57,221 |