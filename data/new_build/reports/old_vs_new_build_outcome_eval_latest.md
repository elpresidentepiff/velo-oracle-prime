# Old VELO vs New Build Outcome Evaluation: 2026-06-21
Generated: 2026-06-21T01:46:16.034497Z

**Classification:** `OUTCOME_PENDING`
**AUC Status:** `OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY`

> AUC comparison requires same-split historical replay on identical races/runners/targets. Single-day SR/win comparison is indicative only, not statistically valid.

## Summary
| Metric | Value |
|---|---|
| Total races | 20 |
| Races with both signals | 20 |
| Old VELO in NB top-3 (alignment) | 10 / 20 (50.0%) |
| Races with outcomes | 0 |
| New Build SR | None |
| Old VELO SR | None |
| OR baseline evaluated | 0 |
| OR baseline SR | None |

## AUC Comparison Requirement
AUC is `NOT_COMPARABLE` until historical replay is run on the same split.
See: `data/new_build/reports/historical_replay_requirement.md`

## Race-by-Race Evaluation
| Race | Course | Old VELO | New Build | NB Top-3 | OR Base | Winner | NB Win | Old Win |
|---|---|---|---|---|---|---|---|---|
| 921031 | 15:13 Hexham | Conquer The Breeze | Cossack Chach | Cossack Chach, Conquer The Breeze, Kientzheim | - | PENDING | - | - |
| 921032 | 15:43 Hexham | Well Educated | Perseus Way | Perseus Way, Haarar, High Dancer | - | PENDING | - | - |
| 921033 | 16:13 Hexham | Laffer Curve | Buddah Castle | Buddah Castle, Laffer Curve, Passengerontheship | - | PENDING | - | - |
| 921034 | 14:43 Hexham | Loman Lady | Run Happy | Run Happy, Beyond The Verge, Redbridge Rocco | - | PENDING | - | - |
| 921035 | 16:43 Hexham | Miss Kassiopi | Jeteye | Jeteye, Belladinotte, Myfavouritesister | - | PENDING | - | - |
| 921036 | 14:13 Hexham | Malangen | Newport | Newport, Curious Mrs Fox, Bouboule | - | PENDING | - | - |
| 921232 | 15:05 Pontefract | Cabrera | Cabrera | Cabrera, Revoir, Lemsairbat | - | PENDING | - | - |
| 921233 | 16:05 Pontefract | Rock Opera | The Good Biscuit | The Good Biscuit, Rock Opera, Azure Zain | - | PENDING | - | - |
| 921234 | 13:35 Pontefract | Clash Of Hearts | Clash Of Hearts | Clash Of Hearts, Onslaught, Excessive | - | PENDING | - | - |
| 921235 | 15:35 Pontefract | Trojan Soldier | Treasure Islands | Treasure Islands, Anzac Day, Secret Force | - | PENDING | - | - |
| 921236 | 14:35 Pontefract | South Parade | Equity Law | Equity Law, Squealer, D Flawless | - | PENDING | - | - |
| 921237 | 16:35 Pontefract | Masaban | Amidst The Chaos | Amidst The Chaos, Ravishing Beauty, Thats My Boy Luke | - | PENDING | - | - |
| 921238 | 14:05 Pontefract | Melissa Honey | Instant Bond | Instant Bond, Diligent Henry, Ideal Guest | - | PENDING | - | - |
| 921239 | 16:56 Brighton | Correspondence | The Flying Seagull | The Flying Seagull, Correspondence, Rogue Bullet | - | PENDING | - | - |
| 921240 | 14:26 Brighton | Nevasca Cinza | Ridger | Ridger, Debrief, Landslide | - | PENDING | - | - |
| 921241 | 15:56 Brighton | Danehill Star | Danehill Star | Danehill Star, Extraterrestrial, Man Is King | - | PENDING | - | - |
| 921242 | 13:56 Brighton | Palazzo Persico | Endowed | Endowed, Kodi Fire, Pentonville | - | PENDING | - | - |
| 921243 | 14:56 Brighton | Power Of Prayer | Night Bear | Night Bear, Power Of Prayer, Sarangpur | - | PENDING | - | - |
| 921244 | 15:26 Brighton | Lucky Sevens | Lucky Sevens | Lucky Sevens, Twilight Guest, West Hill Rosie | - | PENDING | - | - |
| 921245 | 16:26 Brighton | Shes Got The Blues | Mister Sandman | Mister Sandman, Barnsnape Boy, Shes Got The Blues | - | PENDING | - | - |

## Boundaries
- Read-only comparison. Old VELO model and scoring pipeline untouched.
- No Telegram, staking, or live table writes.
- AUC comparison requires same-split historical replay — not done here.