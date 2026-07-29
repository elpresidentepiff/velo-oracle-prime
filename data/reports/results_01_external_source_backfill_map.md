# External Source Backfill Map

## BHA_OFFICIAL_RATINGS

- **URL:** https://www.britishhorseracing.com/racing/horses/ratings/
- **Content:** Official Ratings (OR) for all flat/NH horses, updated weekly
- **Status:** PUBLIC
- **Proven:** True
- **Coverage:** All licensed UK racehorses
- **Note:** Downloadable as CSV. Use for OR verification and training data enrichment.

## RP_RACE_CARDS

- **URL:** https://www.racingpost.com/racecards/
- **Content:** Daily racecards with form, RPR, trainer/jockey stats
- **Status:** PAYWALLED_PARTIAL
- **Proven:** True
- **Coverage:** UK+IRE+International
- **Note:** F_0010 PDF workflow active. HTML racecards parse with RP ingestion layer.

## RP_RESULTS

- **URL:** https://www.racingpost.com/results/
- **Content:** Full result history with SP, position, weight, form figures
- **Status:** PAYWALLED_PARTIAL
- **Proven:** True
- **Coverage:** UK+IRE — primary results source from 2026-05-23 onwards
- **Note:** rp_results_YYYY_MM_DD.json available for 39 dates. Winner SP and top3 present.

## BHA_WEIGHTS_AND_CONDITIONS

- **URL:** https://www.britishhorseracing.com/racing/
- **Content:** Race conditions, weight allowances, NH/Flat categories
- **Status:** PUBLIC
- **Proven:** True
- **Coverage:** UK flat and jumps
- **Note:** Used for race_class validation and field size sanity checks.

## RP_TIPSTER_F0010_PDF

- **URL:** Internal — data/reports/F_0010_*.pdf
- **Content:** Racing Post daily tipster selections and analysis
- **Status:** LOCAL_ARTIFACT
- **Proven:** True
- **Coverage:** Used in dashboard pipeline from 2026-05-14
- **Note:** parse_industry_selections.py extracts tipster picks. Primary industry comparison source.

## RACING_API

- **URL:** https://api.theracingapi.com/
- **Content:** Historical race data, trainer/jockey stats
- **Status:** DECOMMISSIONED_2026_05_14
- **Proven:** False
- **Coverage:** N/A — API 401 errors. Decommissioned.
- **Note:** PERMANENTLY DECOMMISSIONED for live use. RP HTML is only live source.

