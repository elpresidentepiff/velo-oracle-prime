# 2026-05-19 Pre-Sigma Prediction Identity Integrity

**Run:** 2026-05-19T12:17:57.490022+00:00  
**Classification:** `IDENTITY_READY_FOR_SIGMA`  
**Source:** RP_PROFILE_FALLBACK (inferred from 38 RP_ horse_ids)  

## Count Verification

| Check | Expected | Actual | Status |
|---|---|---|---|
| Verdicts scored | 38 | 38 | OK |
| Dashboard races | 38 | 38 | OK |
| Source | RP_PROFILE_FALLBACK | RP_PROFILE_FALLBACK (inferred from 38 RP_ horse_ids) | OK |

## Horse ID Breakdown

| Type | Count |
|---|---|
| Racing API canonical | 0 |
| RP synthetic clean | 38 |
| High risk (spaces/blank) | 0 |
| Medium risk (unknown format) | 0 |
| Blank horse names | 0 |

## Sigma Matchability

| Path | Count |
|---|---|
| Primary (ID + race_id) | 38 |
| Fallback (course/time/name) | 0 |
| **Total matchable** | **38** |

## Row Audit

| Course | Time | Horse | horse_id_type | Risk | Sigma | Flags |
|---|---|---|---|---|---|---|
| Cork | 5.12 | Joyful Tidings | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Cork | 5.42 | Steel Magnolia | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Cork | 6.42 | Al Haarith | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Cork | 7.12 | Goal Exceeded | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Cork | 7.42 | Carmel'S Phoenix | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Cork | 8.12 | Highway Sixty One | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Hexham | 5.50 | Watchoutitscookie | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Hexham | 6.20 | Conquer The Breeze | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Hexham | 6.50 | Lewa House | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Hexham | 7.20 | Milan Milos | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Hexham | 7.50 | Passing Diamond | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Hexham | 8.20 | Well Educated | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Hexham | 8.50 | King Kodiak | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Huntingdon | 6.00 | Crackalackin | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Huntingdon | 6.30 | Pleasure Garden | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Huntingdon | 7.00 | Klervia | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Huntingdon | 7.30 | Gasmani | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Huntingdon | 8.00 | Ice Jet | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Huntingdon | 8.30 | On Lovers Walk | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 2.10 | Big Bear Hug | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 2.40 | Vidmiyr | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 3.10 | Huntly Lodge | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 3.40 | No Gain | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 4.10 | Poetic Grace | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 4.45 | Reidh | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 5.20 | Beau Jardine | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Lingfield | 5.55 | Harry Brown | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Newcastle | 2.30 | Edwardtheninth | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Newcastle | 3.00 | Littlecote | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Newcastle | 4.00 | Gold Digger | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Newcastle | 4.35 | Mystical Land | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Newcastle | 5.05 | Annie Edson Taylor | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Newcastle | 5.35 | Cusack | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Nottingham | 2.20 | Runman | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Nottingham | 3.20 | Lady Lauren | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Nottingham | 3.50 | Domination | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Nottingham | 4.20 | Pretty Spirited | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |
| Nottingham | 4.55 | Timebar | `RP_SYNTHETIC_CLEAN` | LOW | PRIMARY | — |

## Conclusion

**IDENTITY_READY_FOR_SIGMA**

All 38 predictions are structurally sound. RP synthetic IDs are normalized (no spaces). Sigma can match via course/time/name fallback.