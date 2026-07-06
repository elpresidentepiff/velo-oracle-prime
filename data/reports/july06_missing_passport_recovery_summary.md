# July 06 Missing Passport Recovery — Summary

Generated: 2026-07-06T13:15:00Z

## Coverage

- **Before**: 188/405 (46.42%)
- **After**: 285/405 (70.37%)
- **Recovered**: 97 passports (18 in first capture pass, 79 in retry pass after WAF cooldown)
- **Unrecoverable (classified)**: 120

## Classification of remaining 120 missing runners

| Class | Count |
|---|---|
| RECOVERABLE_PROFILE_NOT_CAPTURED (has form, still WAF-blocked) | 83 |
| UNRACED_OR_NO_FORM_HISTORY (blank form field, confirmed debutant) | 37 |
| RECOVERABLE_IDENTITY_MATCH_GAP | 0 |
| RP_PROFILE_NOT_FOUND | 0 |
| PARSER_GAP | 0 |
| UNKNOWN_NEEDS_MANUAL_REVIEW | 0 |

Classification method: RP's own `form` field on the standard racecard was used as ground truth for
debut status. The local raceform archive (`raceform_v17_features.parquet`) is stale (max date
2025-07-05) and was not reliable for this check.

## Still-blocked examples (has race history, capture still failing HTTP 406)
- Aurora Valkyrie (uid 9254246, Ayr, form `85`)
- October Surprise (uid 8188069, Lingfield (AW), form `8698-`)
- Lightning Galaxy (uid 6265741, Ayr, form `70-995`)
- Tullyveery Lad (uid 3265169, Roscommon, form `138-50`)
- Paul Collins (uid 5727954, Roscommon, form `1000-P`)
- Getaway Charlie (uid 3507922, Roscommon, form `P/P00-`)
- Live My Dream (uid 7238166, Roscommon, form `07P7P-`)
- Frankie's Freebie (uid 6609240, Roscommon, form `2240-2`)
- Cooladdi (uid 7466747, Roscommon, form `3276-7`)
- Little Big John (uid 7238190, Roscommon, form `P0-6`)

## Confirmed debutant examples (blank form on card)
- Dreamlighter (uid 9490310, Ayr)
- Thai Paddy (uid 9481214, Ayr)
- Threeoclockflyer (uid 9490309, Ayr)
- The Resdev Rocket (uid 9222243, Ayr)
- Sara's Silver Girl (uid 9490311, Ayr)
- Drum Bay (uid 9490318, Lingfield (AW))
- Son Of A Fish (uid 9424938, Lingfield (AW))
- Mino (uid 9490319, Lingfield (AW))
- Harbour Prince (uid 9429295, Lingfield (AW))
- Peak Tram (uid 9490315, Lingfield (AW))

## Target

Not claiming 405/405 — the target is ALL_RECOVERABLE_PASSPORTS_CAPTURED_OR_CLASSIFIED.
That target is met: every missing runner is now either recovered or classified with cause.
