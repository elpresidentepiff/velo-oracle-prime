# Old VELO vs New Build Outcome Evaluation: 2026-06-16
Generated: 2026-06-16T21:09:44.319112Z

**Classification:** `OUTCOME_EVAL_COMPLETE`
**AUC Status:** `OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY`

> AUC comparison requires same-split historical replay on identical races/runners/targets. Single-day SR/win comparison is indicative only, not statistically valid.

## Summary
| Metric | Value |
|---|---|
| Total races | 33 |
| Races with both signals | 0 |
| Old VELO in NB top-3 (alignment) | 0 / 0 (None%) |
| Races with outcomes | 33 |
| New Build SR | 0.0 |
| Old VELO SR | 0.2121 |
| OR baseline SR | 0.0 |

## AUC Comparison Requirement
AUC is `NOT_COMPARABLE` until historical replay is run on the same split.
See: `data/new_build/reports/historical_replay_requirement.md`

## Race-by-Race Evaluation
| Race | Course | Old VELO | New Build | NB Top-3 | OR Base | Winner | NB Win | Old Win |
|---|---|---|---|---|---|---|---|---|
| 917807 | 2.30 Ascot | Notable Speech | - | - | - | Ten Bob Tony | - | N |
| 917808 | 4.20 Ascot | Bow Echo | - | - | - | Bow Echo | - | Y |
| 917809 | 3.40 Ascot | Rayevka | - | - | - | Mission Central | - | N |
| 921012 | 3.50 Stratford | Edelak | - | - | - | Edelak | - | Y |
| 921013 | 3.15 Stratford | Lheur De Gloire | - | - | - | In The Air | - | N |
| 921014 | 2.05 Stratford | Maskarvel | - | - | - | Louis Veron | - | N |
| 921015 | 4.30 Stratford | Two To Tango | - | - | - | Tamarind Bay | - | N |
| 921016 | 2.40 Stratford | Northern Rose | - | - | - | Mayday Games | - | N |
| 921017 | 5.08 Stratford | Raffles Nobu | - | - | - | Saint Polo | - | N |
| 921101 | 6.30 Beverley | Waasil | - | - | - | Waasil | - | Y |
| 921102 | 7.00 Beverley | Bee Farmer | - | - | - | Lorca's Waltz | - | N |
| 921103 | 8.00 Beverley | Jojo Rabbit | - | - | - | Dream Deal | - | N |
| 921104 | 9.00 Beverley | Dandy's Angel | - | - | - | Regal Glory | - | N |
| 921105 | 8.30 Beverley | Hostelry | - | - | - | Anificas Beauty | - | N |
| 921106 | 7.30 Beverley | Emerald Army | - | - | - | Langholm | - | N |
| 921107 | 2.15 Thirsk | Talitha Rouge | - | - | - | Counter Intuitive | - | N |
| 921108 | 4.02 Thirsk | It Just Takes Time | - | - | - | Mr King | - | N |
| 921109 | 4.42 Thirsk | Marajito | - | - | - | Emerald Harmony | - | N |
| 921110 | 3.25 Thirsk | Frantic | - | - | - | Vingegaard | - | N |
| 921111 | 2.50 Thirsk | Simba's Pride | - | - | - | Dragon Spin | - | N |
| 921112 | 5.20 Thirsk | Knicks | - | - | - | Crocus Time | - | N |
| 921113 | 3.05 Ascot | Great Barrier Reef | - | - | - | Great Barrier Reef | - | Y |
| 921114 | 5.35 Ascot | Map Of Stars | - | - | - | Map Of Stars | - | Y |
| 921115 | 5.00 Ascot | Puturhandstogether | - | - | - | Kizlyar | - | N |
| 921116 | 6.10 Ascot | Gamrai | - | - | - | Daiquiri Bay | - | N |
| 921402 | 8.20 Wolverhampton (AW) | Spaceman | - | - | - | Spaceman | - | Y |
| 921403 | 5.45 Wolverhampton (AW) | Ballisty | - | - | - | Duidin | - | N |
| 921404 | 8.54 Wolverhampton (AW) | Asian Journey | - | - | - | Kaaranah | - | N |
| 921405 | 5.15 Wolverhampton (AW) | Pentonville | - | - | - | Pentonville | - | Y |
| 921406 | 6.45 Wolverhampton (AW) | Go Lockers Go | - | - | - | King Of Chaos | - | N |
| 921407 | 7.15 Wolverhampton (AW) | Mick The Hat | - | - | - | Ada Rose | - | N |
| 921408 | 7.45 Wolverhampton (AW) | Arlecchino's Rex | - | - | - | Rockafeller Skank | - | N |
| 922895 | 6.15 Wolverhampton (AW) | Hadlan | - | - | - | Angel Ang | - | N |

## Boundaries
- Read-only comparison. Old VELO model and scoring pipeline untouched.
- No Telegram, staking, or live table writes.
- AUC comparison requires same-split historical replay — not done here.