# VÉLØ PLACE ECONOMICS AUDIT

**Read-only. No scoring, model, router, or staking changes.**

> Confluence stacks show 100% frame rates but short prices mean flat-win ROI is negative.
> This audit answers: at what place odds do these stacks become profitable?

*Generated: 2026-05-02 00:21 UTC*

---

## PLACE ECONOMICS TABLE — Core stacks

| Stack | Badge | n | Win SR | Frame | Win ROI | Avg SP | Breakeven Place | Best Place Odds (profit) | Classification |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Tier A + VP30 + MDS | ELITE_STACK | 28 | 64.3% | 100.0% | -9.0% | 7.8x | 1.00 | ≥1.05 | **PLACE_VALUE** |
| VP30 + MDS | STRONG_STACK | 35 | 54.3% | 100.0% | -23.8% | 7.8x | 1.00 | ≥1.05 | **PLACE_VALUE** |
| VP30 + MDS + IMPROVE | STRONG_STACK_PLUS | 20 | 55.0% | 100.0% | -23.9% | 4.6x | 1.00 | ≥1.05 | **PLACE_VALUE** |
| VP30 + MDS + IMP + PLACE | STRONG_STACK_PLUS | 20 | 55.0% | 100.0% | -23.9% | 4.6x | 1.00 | ≥1.05 | **PLACE_VALUE** |
| VP30 + IMPROVE | STRONG_STACK | 46 | 50.0% | 87.0% | -9.8% | 4.7x | 1.15 | ≥1.20 | **PLACE_VALUE** |
| VP30 + PLACE only | WATCH_STACK | 251 | 36.3% | 74.9% | -23.0% | 5.8x | 1.34 | ≥1.40 | **PLACE_VALUE_MODERATE** |
| VP30 alone | BASE_TRUST_SIGNAL | 380 | 32.9% | 70.0% | -17.7% | 6.0x | 1.43 | ≥1.50 | **PLACE_VALUE_MODERATE** |
| B-tier + VP < 0.30 | SUPPRESS_STACK | 303 | 16.2% | 42.9% | -23.1% | 8.8x | 2.33 | never in test range | **SUPPRESS** |
| All verdicts (baseline) | BASELINE | 1458 | 20.4% | 48.2% | -19.8% | 8.6x | 2.07 | never in test range | **WATCH** |

---

## SIMULATED PLACE ROI — At fixed odds (flat £1 place bet per horse)

Positive = profitable at that place price.

| Stack | n | Frame | 1.05 | 1.10 | 1.15 | 1.20 | 1.25 | 1.30 | 1.40 | 1.50 | 1.75 | 2.00 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tier A + VP30 + MDS | 28 | 100.0% | +5.0% | +10.0% | +15.0% | +20.0% | +25.0% | +30.0% | +40.0% | +50.0% | +75.0% | +100.0% |
| VP30 + MDS | 35 | 100.0% | +5.0% | +10.0% | +15.0% | +20.0% | +25.0% | +30.0% | +40.0% | +50.0% | +75.0% | +100.0% |
| VP30 + MDS + IMPROVE | 20 | 100.0% | +5.0% | +10.0% | +15.0% | +20.0% | +25.0% | +30.0% | +40.0% | +50.0% | +75.0% | +100.0% |
| VP30 + MDS + IMP + PLACE | 20 | 100.0% | +5.0% | +10.0% | +15.0% | +20.0% | +25.0% | +30.0% | +40.0% | +50.0% | +75.0% | +100.0% |
| VP30 + IMPROVE | 46 | 87.0% | -8.7% | -4.3% | -0.0% | +4.3% | +8.7% | +13.0% | +21.7% | +30.4% | +52.2% | +73.9% |
| VP30 + PLACE only | 251 | 74.9% | -21.4% | -17.6% | -13.9% | -10.1% | -6.4% | -2.6% | +4.9% | +12.4% | +31.1% | +49.8% |
| VP30 alone | 380 | 70.0% | -26.5% | -23.0% | -19.5% | -16.0% | -12.5% | -9.0% | -2.0% | +5.0% | +22.5% | +40.0% |
| B-tier + VP < 0.30 | 303 | 42.9% | -55.0% | -52.8% | -50.7% | -48.5% | -46.4% | -44.2% | -39.9% | -35.6% | -24.9% | -14.2% |
| All verdicts (baseline) | 1458 | 48.2% | -49.4% | -47.0% | -44.6% | -42.1% | -39.7% | -37.3% | -32.5% | -27.7% | -15.6% | -3.6% |

---

## EACH-WAY SIMULATION (place leg only, £1)

Uses estimated SP for our pick. WIN/PLACED = placed. Bookmaker terms simulated.
Note: PLACED outcome SP estimated as ~1.8x winner SP (proxy — actual pick SP unavailable).

| Stack | n | Frame | Avg SP | E/W 1/4 | E/W 1/5 | E/W 1/6 |
|---|---:|---:|---:|---:|---:|---:|
| Tier A + VP30 + MDS | 28 | 100.0% | 7.8x | +170.1% | +136.1% | +113.6% |
| VP30 + MDS | 35 | 100.0% | 7.8x | +169.1% | +135.3% | +113.0% |
| VP30 + MDS + IMPROVE | 20 | 100.0% | 4.6x | +90.1% | +72.1% | +60.2% |
| VP30 + MDS + IMP + PLACE | 20 | 100.0% | 4.6x | +90.1% | +72.1% | +60.2% |
| VP30 + IMPROVE | 46 | 87.0% | 4.7x | +51.4% | +38.5% | +30.0% |
| VP30 + PLACE only | 251 | 74.9% | 5.8x | +58.6% | +41.8% | +30.7% |
| VP30 alone | 380 | 70.0% | 6.0x | +52.2% | +35.7% | +24.8% |
| B-tier + VP < 0.30 | 303 | 42.9% | 8.8x | +36.9% | +18.1% | +5.7% |
| All verdicts (baseline) | 1458 | 48.2% | 8.6x | +43.9% | +24.7% | +12.1% |

---

## SP BAND BREAKDOWN — VP30 + MDS (STRONG_STACK) and Tier A + VP30 + MDS (ELITE_STACK)

### Tier A + VP30 + MDS

| SP band | n | Win SR | Frame |
|---|---:|---:|---:|
| 10.0+ | 5 | 0.0% | 100.0% |
| 2.0–3.0 | 2 | 100.0% | 100.0% |
| 3.0–4.0 | 1 | 0.0% | 100.0% |
| 4.0–6.0 | 2 | 0.0% | 100.0% |
| 6.0–10.0 | 2 | 0.0% | 100.0% |
| odds_on | 16 | 100.0% | 100.0% |

### VP30 + MDS

| SP band | n | Win SR | Frame |
|---|---:|---:|---:|
| 10.0+ | 6 | 0.0% | 100.0% |
| 2.0–3.0 | 2 | 100.0% | 100.0% |
| 3.0–4.0 | 2 | 0.0% | 100.0% |
| 4.0–6.0 | 2 | 0.0% | 100.0% |
| 6.0–10.0 | 6 | 0.0% | 100.0% |
| odds_on | 17 | 100.0% | 100.0% |

### VP30 + MDS + IMPROVE

| SP band | n | Win SR | Frame |
|---|---:|---:|---:|
| 10.0+ | 3 | 0.0% | 100.0% |
| 2.0–3.0 | 1 | 100.0% | 100.0% |
| 3.0–4.0 | 2 | 0.0% | 100.0% |
| 4.0–6.0 | 1 | 0.0% | 100.0% |
| 6.0–10.0 | 3 | 0.0% | 100.0% |
| odds_on | 10 | 100.0% | 100.0% |

### VP30 + MDS + IMP + PLACE

| SP band | n | Win SR | Frame |
|---|---:|---:|---:|
| 10.0+ | 3 | 0.0% | 100.0% |
| 2.0–3.0 | 1 | 100.0% | 100.0% |
| 3.0–4.0 | 2 | 0.0% | 100.0% |
| 4.0–6.0 | 1 | 0.0% | 100.0% |
| 6.0–10.0 | 3 | 0.0% | 100.0% |
| odds_on | 10 | 100.0% | 100.0% |

---

## FIELD SIZE BREAKDOWN — VP30 alone vs VP30 + MDS

### VP30 alone

| Field size | n | Win SR | Frame |
|---|---:|---:|---:|
| 10–12 | 16 | 0.0% | 31.2% |
| 13+ | 8 | 37.5% | 62.5% |
| 7–9 | 44 | 31.8% | 75.0% |
| unknown | 282 | 35.5% | 71.6% |
| ≤6 | 30 | 26.7% | 70.0% |

### VP30 + MDS

| Field size | n | Win SR | Frame |
|---|---:|---:|---:|
| 7–9 | 5 | 80.0% | 100.0% |
| unknown | 28 | 50.0% | 100.0% |
| ≤6 | 2 | 50.0% | 100.0% |

---

## REQUIRED ANSWERS

**1. Does Tier A + VP30 + MDS become profitable as place framework?**
  n=28, Frame=100.0%, Win ROI=-9.0%
  Breakeven place odds needed: 1.00
  Profitable at: ≥1.05
  E/W 1/4 place leg ROI: +170.1%  |  E/W 1/5 place leg ROI: +136.1%
  → YES at low odds — PLACE_VALUE

**4. VP30 + MDS vs VP30 + IMPROVE — which is better value?**
  VP30+MDS:    Frame=100.0%, PlaceROI@1.20=+20.0%, AvgSP=7.8
  VP30+IMPROVE:Frame=87.0%, PlaceROI@1.20=+4.3%, AvgSP=4.7
  → VP30+MDS (lower odds needed)

**7. Suppress stack confirmation:**
  B-tier + VP<0.30: n=303, SR=16.2%, Frame=42.9%, WinROI=-23.1%
  → SUPPRESS — confirmed, do not upgrade with sidecars

---

## FINAL OPERATOR BADGE RECOMMENDATIONS

| Stack | Badge | Place Economics | Recommendation |
|---|---|---|---|
| Tier A + VP30 + MDS | **ELITE_STACK** | Profitable at ≥1.05 | PLACE_VALUE |
| VP30 + MDS | **STRONG_STACK** | Profitable at ≥1.05 | PLACE_VALUE |
| VP30 + MDS + IMPROVE | **STRONG_STACK_PLUS** | Profitable at ≥1.05 | PLACE_VALUE |
| VP30 + MDS + IMP + PLACE | **STRONG_STACK_PLUS** | Profitable at ≥1.05 | PLACE_VALUE |
| VP30 + IMPROVE | **STRONG_STACK** | Profitable at ≥1.20 | PLACE_VALUE |
| VP30 + PLACE only | **WATCH_STACK** | Profitable at ≥1.40 | PLACE_VALUE_MODERATE |
| VP30 alone | **BASE_TRUST_SIGNAL** | Profitable at ≥1.50 | PLACE_VALUE_MODERATE |
| B-tier + VP < 0.30 | **SUPPRESS_STACK** | Not profitable in test range | SUPPRESS |
| All verdicts (baseline) | **BASELINE** | Not profitable in test range | WATCH |

---

**J. No live code changed. No scoring/SQPE/model/router/staking changes.**

*PLACE ECONOMICS AUDIT — operator intelligence only.*