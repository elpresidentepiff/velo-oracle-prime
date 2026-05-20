# VÉLØ PLACE / FRAME ECONOMICS AUDIT

**Read-only. No scoring, model, router, or staking changes.**

> A signal with weak win ROI but strong frame rate belongs to a different product.
> This audit reclassifies VÉLØ sidecars beyond win-only flat ROI.

*Generated: 2026-05-01 23:53 UTC*
*Sample: 1458 joined rows | 486 with actual finishing position*

---

## SIGNAL FRAME ECONOMICS TABLE

| Signal | n | Win SR | Frame | Top-3 | Top-4 | Top-5 | Win ROI | Place ROI (1/5) | Place ROI (1/4) | Avg SP | Classification | Best Use |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| MDS > 0.50 + VP ≥ 0.30 | 35 | 54.3% | 100.0% | 100.0% | 100.0% | 100.0% | -23.8% | +73.1% | +91.3% | 4.7x | **WIN_NEGATIVE_FRAME_STRONG** | PLACE_BET / EACH_WAY |
| VP30 + Tier A + MDS > 0.50 | 28 | 64.3% | 100.0% | 100.0% | 100.0% | 100.0% | -9.0% | +74.8% | +93.5% | 4.7x | **FRAME_ENGINE** | EACH_WAY / PLACE_BET |
| market_deception_score > 0.50 | 37 | 51.4% | 97.3% | 97.3% | 97.3% | 97.3% | -27.9% | +70.5% | +88.7% | 4.7x | **WIN_NEGATIVE_FRAME_STRONG** | PLACE_BET / EACH_WAY |
| imp > 0.40 + VP ≥ 0.30 | 46 | 50.0% | 87.0% | 87.0% | 87.0% | 87.0% | -9.8% | +15.9% | +23.1% | 3.6x | **FRAME_ENGINE** | EACH_WAY / PLACE_BET |
| VP ≥ 0.40 | 112 | 44.6% | 85.7% | 85.7% | 87.5% | 89.3% | -22.2% | +30.1% | +41.4% | 4.5x | **WIN_NEGATIVE_FRAME_STRONG** | PLACE_BET / EACH_WAY |
| improvement_score > 0.40 | 69 | 43.5% | 82.6% | 82.6% | 82.6% | 82.6% | -17.0% | +15.1% | +23.3% | 3.7x | **FRAME_ENGINE** | EACH_WAY / PLACE_BET |
| Tier A | 183 | 41.0% | 77.0% | 77.0% | 78.7% | 80.9% | -9.1% | +18.3% | +28.6% | 4.6x | **FRAME_ENGINE** | EACH_WAY / PLACE_BET |
| Tier A + VP ≥ 0.30 | 183 | 41.0% | 77.0% | 77.0% | 78.7% | 80.9% | -9.1% | +18.3% | +28.6% | 4.6x | **FRAME_ENGINE** | EACH_WAY / PLACE_BET |
| place_prob > 0.80 + VP ≥ 0.30 | 251 | 36.3% | 74.9% | 74.9% | 77.3% | 79.3% | -23.0% | +12.1% | +21.4% | 4.3x | **WIN_NEGATIVE_FRAME_STRONG** | PLACE_BET / EACH_WAY |
| longshot_prob > 0.50 | 49 | 34.7% | 71.4% | 71.4% | 71.4% | 71.4% | -29.7% | +6.8% | +15.6% | 4.0x | **WIN_NEGATIVE_FRAME_STRONG** | PLACE_BET / EACH_WAY |
| VP ≥ 0.30 | 380 | 32.9% | 70.0% | 70.0% | 72.4% | 75.3% | -17.7% | +7.5% | +16.9% | 4.6x | **FRAME_ENGINE** | EACH_WAY / PLACE_BET |
| VP30 + SP 2–6 | 231 | 25.5% | 69.7% | 69.7% | 72.3% | 75.8% | -25.8% | +2.7% | +11.0% | 3.5x | **WIN_NEGATIVE_FRAME_STRONG** | PLACE_BET / EACH_WAY |
| place_prob > 0.80 | 449 | 31.4% | 65.5% | 65.5% | 69.3% | 71.0% | -21.4% | +2.8% | +12.2% | 5.1x | **WIN_NEGATIVE_FRAME_STRONG** | PLACE_BET / EACH_WAY |
| Archetype: Structure | 273 | 20.9% | 53.8% | 53.8% | 57.9% | 61.5% | -20.8% | -3.1% | +7.7% | 6.0x | **OVERBET_WIN_ONLY** | SUPPRESS |
| All verdicts (baseline) | 1458 | 20.4% | 48.2% | 48.2% | 52.3% | 55.2% | -19.8% | -6.5% | +4.9% | 7.0x | **OVERBET_WIN_ONLY** | SUPPRESS |
| Archetype: Compression | 46 | 23.9% | 47.8% | 47.8% | 50.0% | 52.2% | -2.0% | -12.8% | -3.0% | 7.8x | **WATCH** | WATCH_ONLY |
| VP30 + SP 6–12 | 55 | 7.3% | 47.3% | 47.3% | 54.5% | 58.2% | -32.7% | +14.9% | +31.8% | 8.0x | **OVERBET_WIN_ONLY** | SUPPRESS |
| rpdc_release_score > 0.50 | 58 | 22.4% | 44.8% | 44.8% | 44.8% | 44.8% | +13.6% | -18.1% | -8.8% | 5.2x | **WATCH** | WATCH_ONLY |
| release_day_prob > 0.50 | 0 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | +0.0% | +0.0% | +0.0% | 0.0x | **INSUFFICIENT_SAMPLE** | INSUFFICIENT_SAMPLE |

---

## WIN ENGINE vs FRAME ENGINE

| Classification | Meaning | Correct product |
|---|---|---|
| WIN_ENGINE | Win ROI positive, SR ≥ 25% | Win bet |
| FRAME_ENGINE | Frame ≥ 65%, place proxy positive | Each-way / place |
| WIN_NEGATIVE_FRAME_STRONG | Win ROI negative, frame ≥ 65% | Place bet — NOT win bet |
| TOP4_TOP5_CANDIDATE | Frame weak but top-4/5 rate strong | Exchange top-4/5 market |
| OVERBET_WIN_ONLY | Win ROI negative, frame < 55% | SUPPRESS |

> Previous audit labelled signals as HARMFUL purely on win ROI.
> Correct label is WIN_NEGATIVE_FRAME_STRONG if frame ≥ 65%.
> A bad win bet can still be a good place leg.

---

## SIDECAR RECLASSIFICATION

| Signal | Previous label | Corrected label | Reason |
|---|---|---|---|
| improvement_score > 0.40 | OVERBET_RISK | **FRAME_ENGINE** | frame rate > 65% — reclassified |
| market_deception_score > 0.50 | OVERBET_RISK | **WIN_NEGATIVE_FRAME_STRONG** | frame rate > 65% — reclassified |
| place_prob > 0.80 | OVERBET_RISK | **WIN_NEGATIVE_FRAME_STRONG** | frame rate > 65% — reclassified |
| release_day_prob > 0.50 | HARMFUL | **INSUFFICIENT_SAMPLE** | confirmed harmful |

---

## ACCUMULATOR SIMULATION (paper only)

Legs selected: VP30 + place_prob > 0.80

| Fold | Days with legs | Acca wins | Hit rate | Avg return | Recommendation |
|---|---:|---:|---:|---:|---|
| 3-fold | 38 | 2 | 5.3% | 0.3x | DO_NOT_USE |
| 4-fold | 34 | 1 | 2.9% | 0.8x | DO_NOT_USE |
| 5-fold | 30 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 6-fold | 24 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 7-fold | 15 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 3-fold | 2 | 1 | 50.0% | 1.8x | DO_NOT_USE |
| 4-fold | 0 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 5-fold | 0 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 6-fold | 0 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 7-fold | 0 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 3-fold | 33 | 2 | 6.1% | 0.4x | DO_NOT_USE |
| 4-fold | 26 | 2 | 7.7% | 1.3x | DO_NOT_USE |
| 5-fold | 21 | 1 | 4.8% | 10.7x | DO_NOT_USE |
| 6-fold | 12 | 0 | 0.0% | 0.0x | DO_NOT_USE |
| 7-fold | 10 | 0 | 0.0% | 0.0x | DO_NOT_USE |

---

## SP BAND BREAKDOWN — VP30

| SP band | n | Win SR | Frame |
|---|---:|---:|---:|
| 2_to_4 | 6 | 33.3% | 100.0% |
| 4_to_6 | 1 | 0.0% | 100.0% |
| 6_to_10 | 3 | 0.0% | 100.0% |
| evens_or_under | 16 | 100.0% | 100.0% |
| over_20 | 2 | 0.0% | 100.0% |

---

## HARD TRUTH

- No live code changed.
- No SQPE / model / router / staking changes.
- release_day_prob and comment_intel are CONTAINMENT_CANDIDATES for win-bet context.
- They may still be valid as place/frame context signals.
- SQPE remains the primary win-probability anchor.
- MDS > 0.50 is a high-signal win engine with proven 54.8% SR at n=31.
- place_prob > 0.80 is a FRAME ENGINE — correct use is place / each-way, not win-flat.

*PLACE/FRAME ECONOMICS AUDIT — operator intelligence only.*