# VÉLØ Unified Evidence Audit V1
**Run:** 2026-04-28 23:42 UTC

---

## Global Summary

| Metric | Value |
|---|---|
| Race days audited | 49 |
| Total verdicts in DB | 1604 |
| Total sigma_audit rows | 1391 |
| X-tier excluded | 142 |
| Global strike rate (non-X) | **20.6%** (baseline 20%) |
| Global frame rate (non-X) | **48.4%** (baseline 70%) |
| Days above baseline | 18 |
| Days at baseline | 9 |
| Days below baseline | 22 |

---

## VP Band Truth

| Band | n | Wins | SR | Frame | Avg VP |
|---|---|---|---|---|---|
| VP<0.20 | 385 | 56 | 14.5% | 33.5% | 0.158 |
| VP 0.20-0.30 | 460 | 83 | 18.0% | 47.8% | 0.243 |
| VP 0.30-0.40 | 245 | 67 | 27.3% | 62.9% | 0.341 |
| VP>=0.40 | 100 | 44 | 44.0% | 85.0% | 0.487 |
| VP>=0.30 combined | 345 | 111 | 32.2% | 69.3% | 0.383 |
| VP>=0.30 + Tier A | 162 | 65 | 40.1% | 77.2% | 0.425 |

**VP ≥ 0.30 outperforms baseline:** YES
**VP ≥ 0.30 + Tier A outperforms VP ≥ 0.30 alone:** YES

---

## Tier Truth

| Tier | n | Wins | SR | Frame | Avg VP |
|---|---|---|---|---|---|
| Tier A | 162 | 65 | 40.1% | 77.2% | 0.425 |
| Tier B | 402 | 85 | 21.1% | 50.0% | 0.277 |
| Tier C | 455 | 72 | 15.8% | 42.2% | 0.212 |
| Tier D | 112 | 15 | 13.4% | 33.9% | 0.164 |
| Tier X | 142 | 18 | 12.7% | 34.5% | 0.145 |

### B-Tier Suppression Test

| | Original | Suppressed (excl B VP<0.30) |
|---|---|---|
| n | 1249 | 977 |
| Rows removed | — | 272 (21.8% coverage lost) |
| Strike rate | 20.6% | 21.6% |
| Frame rate | 48.4% | 49.6% |

---

## Router Lane Truth

| Lane | n | SR | Frame | ROI | Status |
|---|---|---|---|---|---|
| V1_BASE | 27 | 37.0% | 85.2% | +11.5% | WATCHLIST |
| V2_CLASS4_ONLY | 17 | 41.2% | 82.3% | +30.2% | LANE_ACTIVE |
| V6_GOLD_SEAM | 5 | 60.0% | 100.0% | +115.0% | LOW_SAMPLE |

---

## Sidecar / Shadow Signal Truth

| Signal | n | SR | Frame | Lift vs Global | Verdict |
|---|---|---|---|---|---|
| G Shadow (multiplier>1.0) | 0 | — | — | — | INSUFFICIENT_SAMPLE |
| RPDC release score>0.5 | 54 | 24.1% | 48.1% | +3.5% | KEEP |
| RPDC cash window flag | 1 | — | — | — | INSUFFICIENT_SAMPLE |
| Place prob>0.80 | 392 | 31.6% | 66.8% | +11.0% | KEEP |
| Market deception score>0.5 | 31 | 54.8% | 96.8% | +34.2% | KEEP |
| Improvement score>0.40 | 62 | 43.5% | 82.3% | +22.9% | KEEP |
| Macro chaos mode | 0 | — | — | — | INSUFFICIENT_SAMPLE |
| Archetype=Structure | 270 | 21.1% | 53.7% | +0.5% | WATCHLIST |
| Archetype=Compression | 40 | 20.0% | 47.5% | -0.6% | SUPPRESS |

---

## Miss Class Truth

Total misses: 607

| Miss class | Count |
|---|---|
| mid_priced_won | 279 |
| outsider_won | 92 |
| market_decoy_followed | 87 |
| short_fav_won | 81 |
| non_runner_or_untracked | 26 |
| outsider_hedge_omitted | 23 |
| horse_set_divergence (1 non-runners) | 7 |
| horse_absent_from_result | 4 |
| horse_set_divergence (2 non-runners) | 3 |
| high_confidence_miss | 2 |
| signal_underweighted_place_prob | 1 |
| horse_set_divergence (3 non-runners) | 1 |
| horse_set_divergence (4 non-runners) | 1 |

**SP 3.0–8.5 zone misses:** 352 (58.0% of all misses)
**High VP (≥0.40) misses:** 15
**AW/Southwell card misses:** 97

---

## Signal Rankings

| Signal | n | SR | Frame | Rank |
|---|---|---|---|---|
| VP>=0.30 + Tier A | 162 | 40.1% | 77.2% | **PROVEN_SIGNAL** |
| Tier A (all VP) | 162 | 40.1% | 77.2% | **PROVEN_SIGNAL** |
| Sidecar:Improvement score>0.40 | 62 | 43.5% | 82.3% | **PROVEN_SIGNAL** |
| VP>=0.30 | 345 | 32.2% | 69.3% | **PROMISING_SIGNAL** |
| Sidecar:Place prob>0.80 | 392 | 31.6% | 66.8% | **PROMISING_SIGNAL** |
| Sidecar:Market deception score>0.5 | 31 | 54.8% | 96.8% | **PROMISING_SIGNAL** |
| Tier B VP>=0.30 | 130 | 30.0% | 62.3% | **WATCHLIST_SIGNAL** |
| V1_BASE | 27 | 37.04% | 85.19% | **WATCHLIST_SIGNAL** |
| V2_CLASS4_ONLY | 17 | 41.18% | 82.35% | **WATCHLIST_SIGNAL** |
| Sidecar:RPDC release score>0.5 | 54 | 24.1% | 48.1% | **WATCHLIST_SIGNAL** |
| Tier B (all VP) | 402 | 21.1% | 50.0% | **NOISY_SIGNAL** |
| Sidecar:Archetype=Structure | 270 | 21.1% | 53.7% | **NOISY_SIGNAL** |
| Sidecar:Archetype=Compression | 40 | 20.0% | 47.5% | **NOISY_SIGNAL** |
| Tier B VP<0.30 | 272 | 16.9% | 44.1% | **SUPPRESS_SIGNAL** |
| V6_GOLD_SEAM | 5 | 60.0% | 100.0% | **INSUFFICIENT_SAMPLE** |

---

## Conclusions

**A. What is working:** VP>=0.30, VP>=0.30 + Tier A, Tier A (all VP), Sidecar:Place prob>0.80, Sidecar:Market deception score>0.5, Sidecar:Improvement score>0.40
**B. What is not working:** Tier B VP<0.30
**C. Promising (under-sampled):** Tier B VP>=0.30, V1_BASE, V2_CLASS4_ONLY, Sidecar:RPDC release score>0.5
**D. Suppress candidates:** Tier B VP<0.30
**E. Shadow-only:** V1_BASE, V2_CLASS4_ONLY, V6_GOLD_SEAM, Playbook G V3 core
**F. Candidate lanes:** VP>=0.30, Sidecar:Place prob>0.80, Sidecar:Market deception score>0.5
**G. Needs more data:** V6_GOLD_SEAM...
**H. Modifications:** See modification_impact for per-change metrics
**I. Frame attribution:** Frame detection appears structural (VP>=0.30 band performs consistently). Cannot attribute to a single modification without pre-ensemble baseline. Post-ensemble (Mar 16+) data is primary evidence corpus.

**J. Next protocol:**
1. Continue evidence accumulation for V2/V6 router lanes. 2. Track VP>=0.30+TierA as shadow candidate lane (do not stake). 3. B-tier drag not yet large enough to confirm suppression. 4. Build audit dossier from this output. 5. Next promotion review when V2 reaches n=30.

---
*Generated by scripts/run_velo_unified_evidence_audit.py — 2026-04-28 23:42 UTC*