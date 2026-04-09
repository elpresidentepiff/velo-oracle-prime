# VÉLØ Shadow Card — UPDATED — 09 APR 2026
**Shadow/G Refresh Cycle Complete**
**Training: sigma_audits (500 closed-loop races)**
**Generated: 09:20 UTC**

---

## A. Updated Card Summary

| Metric | Value |
|--------|-------|
| Total races | 50 |
| CONFIRMED | 4 |
| WATCH | 18 |
| CAUTION | 21 |
| DECOY | 7 |

Prior card: CONFIRMED=8, WATCH=18, CAUTION=24
**Change: 4 confirmed downgraded, 7 decoys newly surfaced**

---

## B. Stable Confirmed (4) — Post-Refresh

These 4 passed both Tier A/B AND A/E-adjusted place >0.30 with CLEAN MDS.

| Horse | Region | Tier | Prob | Place | A/E adj_place | Flags |
|-------|--------|------|------|-------|---------------|-------|
| Senor Cortez | GB | A | 0.3666 | 0.8929 | **0.6072** | CLEAN |
| Pearly Squirrel | GB | B | 0.3420 | 1.0000 | **0.3900** | CLEAN |
| Inferno Sacree | GB | B | 0.3486 | 0.9491 | **0.3701** | CLEAN |
| Rock Of Ireland | IRE | B | 0.2627 | 0.8464 | **0.3301** | CLEAN |

---

## C. Downgraded — Original Confirmed → CAUTION

| Horse | Region | Old | New | Reason |
|-------|--------|-----|-----|--------|
| Diomed Spirit | GB | CONFIRMED | CAUTION | adj_place=0.271 < 0.30 |
| Incredible Army | IRE | CONFIRMED | CAUTION | adj_place=0.289 < 0.30 |
| Queue Dos | GB | CONFIRMED | CAUTION | adj_place=0.284 < 0.30 |
| Brighterdaysahead | GB | CONFIRMED | CAUTION | adj_place=0.188 weak |

---

## D. New Decoys (7) — MDS > 0.25

| Horse | Region | Tier | Prob | MDS | Verdict |
|-------|--------|------|------|-----|---------|
| Game Point | IRE | C | 0.1585 | 0.1404 | **NEW DECOY** — MID_PRICED_TRAP |
| Got The Booty | GB | A | 0.4096 | 0.4835 | AVOID |
| Minella Yoga | GB | B | 0.3449 | 0.4548 | AVOID |
| Lulamba | GB | A | 0.3704 | 0.3571 | DECOY |
| On The Inlet | GB | A | 0.4214 | 0.3167 | DECOY |
| Suir Monad | IRE | A | 0.3655 | 0.3076 | DECOY |
| Astrological | GB | C | 0.3455 | 0.3168 | DECOY + HIGH_IMPR |

**Note: MDS decoy overrides high Tier A place probability.**

---

## E. Doctrine Rules Applied (sigma_audits 500 races)

1. **MID_PRICED_DECOY**: top_prob 0.08-0.30 + top3 MDS>0.15 → 42% of misses
2. **MDS_DECOY**: top3 MDS > 0.25 → 23% of misses
3. **A/E_PLACE_ADJUST**: tier-specific place multipliers:
   - Tier A ×0.68 | Tier B ×0.39 | Tier C ×0.48 | Tier D ×0.32 | Tier X ×0.44
   - CONFIRMED threshold: adj_place > 0.30
4. **TIER_A_EDGE**: Tier A 1.7x more reliable than Tier B (HR 0.34 vs 0.20)

---

## F. G/Shadow State

- **G shadow**: G_TOO_FEW_RACES — neutral multiplier (1.0)
- **Active edge**: sigma_audits A/E doctrine (500 closed-loop races)
- **G activates**: when learned_patterns populated from real scoring runs

---

## G. Material Change Summary

| | Count |
|-|-------|
| Original confirmed | 8 |
| Stable confirmed | 4 |
| Downgraded to CAUTION | 4 |
| New decoys surfaced | 7 |
| **Verdict** | **CARD MATERIALLY CHANGED** |

---

## H. Telegram Send Status

- Part 1: OK ✓
- Part 2: OK ✓ (plain text)
- Part 3: OK ✓

**Backup: velo-oracle-prime/telegram_cards/**
**Comparison: /tmp/shadow_comparison_09apr2026.json**
