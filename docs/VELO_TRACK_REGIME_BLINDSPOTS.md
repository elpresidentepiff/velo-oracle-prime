# VÉLØ Track & Regime Blindspot Forensic
**Generated:** 2026-04-19 | **Base:** 1,107 sigma_audit races, tracks with n≥10

---

## Overview

Track performance variance is real and exploitable. This audit identifies where the model is structurally strong and where it is operating blind.

---

## Track Performance Table (n ≥ 10 races)

| Track | n | Win% | Frame% | Decoy% | Reading |
|-------|---|------|--------|--------|---------|
| Wexford (IRE) | 14 | **42.9%** | 64.3% | 0.0% | Exceptional — Ireland turf jumps |
| Hereford | 18 | **33.3%** | 61.1% | 16.7% | Strong but decoy-exposed |
| Stratford | 12 | **33.3%** | 58.3% | 0.0% | Strong — small NH field specialist |
| Leopardstown (IRE) | 15 | **33.3%** | 40.0% | 0.0% | Strong win, low frame |
| Southwell | 13 | **30.8%** | 61.5% | 15.4% | AW specialist, decoy risk |
| Wolverhampton (AW) | 68 | **29.4%** | 63.2% | 16.2% | High volume + strong. Primary AW lane. |
| Kempton (AW) | 35 | **28.6%** | 45.7% | 8.6% | Good win, lower frame |
| Newcastle | 14 | **28.6%** | 42.9% | 0.0% | Solid |
| Bellewstown (IRE) | 14 | **28.6%** | 35.7% | 0.0% | Small sample |
| Newton Abbot | 11 | **27.3%** | 63.6% | 0.0% | Strong frame |
| Fontwell | 12 | **25.0%** | 58.3% | 16.7% | High decoy rate — caution |
| Musselburgh | 12 | **25.0%** | 41.7% | 0.0% | Competent |
| Exeter | 20 | **25.0%** | **75.0%** | 0.0% | Strong frame. NH specialist. |
| Chepstow | 21 | 23.8% | 57.1% | 19.0% | Volume + high decoy. Filter needed. |
| Lingfield (AW) | — | — | — | high | AW decoy hub — see below |
| **Down Royal (IRE)** | 15 | 13.3% | 40.0% | 0.0% | Weak — Irish jumping blind spot |
| **Haydock** | 16 | 12.5% | 37.5% | 0.0% | Weak |
| **Ascot** | 10 | 10.0% | 20.0% | 0.0% | CRITICAL blind spot — 1 in 10 |
| **Bangor-on-Dee** | 14 | 7.1% | 35.7% | 0.0% | Weak — Welsh circuit |
| **Doncaster** | 16 | 6.2% | 25.0% | 0.0% | Structural failure |
| **Thirsk** | 16 | 6.2% | 43.8% | 0.0% | Low win — frames but can't convert |
| **Curragh (IRE)** | 21 | 4.8% | 52.4% | 0.0% | Graded Irish flat — model not calibrated |
| **Nottingham** | 15 | 0.0% | 33.3% | 0.0% | Zero wins — complete blind spot |

---

## Surface Analysis: AW vs Turf

| Surface | Races | Win% | Frame% | Decoy Miss Rate |
|---------|-------|------|--------|-----------------|
| All-Weather (AW) | 243 | **22.2%** | 47.7% | 19.3% |
| GB Turf (non-AW, non-Ireland) | 939 | 19.3% | 45.7% | low |
| Ireland | 15 | 13.3% | 20.0% | 0.0% |

**AW races outperform the system average (22.2% vs 19.3%)** — but carry a 19.3% decoy miss rate. The model is structurally strong on AW racing; the risk is market manipulation, not model failure.

**Ireland is a blind spot.** 13.3% win rate, 20.0% frame. The model is not calibrated for Irish racing dynamics (different handicapper, different pace, different class structure).

---

## Critical Blind Spots

### Nottingham — 0 wins from 15 races
The only tracked track with zero wins. The model consistently misidentifies winners at Nottingham. Root cause not yet determined — possibly draw bias, galloping track that favours hold-up horses the model underweights, or data sparsity in training.

### Curragh — 4.8% win from 21 races
Irish graded flat racing. The model's handicap-oriented feature set is not calibrated for Curragh-grade flat races where class and pedigree dominate over form and pace signals.

### Doncaster — 6.2% win from 16 races
One of GB's premier flat tracks. Low win rate despite volume. Likely cause: Doncaster features many large-field competitive handicaps where the mid-price dead zone dominates.

### Ascot — 10.0% win from 10 races
Small sample but concerning. Ascot races typically feature high-class horses with global form — the model's UK-centric feature engineering may underweight international form.

### Thirsk — 6.2% win, 43.8% frame
High frame rate but cannot convert to wins. The model identifies the contention zone but not the winner. Possible cause: tight finish racing where small-margin variables (going, draw, sectionals) decide the result.

---

## AW Decoy Map

| AW Track | Decoy Misses | Win% | Risk Level |
|----------|-------------|------|-----------|
| Wolverhampton (AW) | 11 | 29.4% | HIGH — profitable but decoy-heavy |
| Kempton (AW) | 5 | 28.6% | MEDIUM |
| Lingfield (AW) | 12 | — | HIGH — AW decoy hub |
| Newcastle (AW) | 10 | — | HIGH |
| Southwell | 2 | 30.8% | LOW-MEDIUM |

**Wolverhampton AW is the highest-volume profitable track with the highest decoy exposure.** 68 races, 29.4% win — but 16.2% decoy rate means 1 in 6 Wolves bets is following a fake move. Apply market_deception_score filter at Wolverhampton before selection.

---

## NH vs Flat Regime Split

| Regime | Strong Tracks | Weak Tracks |
|--------|-------------|------------|
| National Hunt (jumps) | Wexford, Hereford, Stratford, Exeter, Newton Abbot | Bangor-on-Dee, Down Royal |
| Flat (turf) | Leopardstown, Bellewstown | Curragh, Nottingham, Thirsk, Doncaster, Ascot |
| All-Weather | Wolverhampton, Southwell, Kempton | Lingfield (decoy hub) |

**The model performs better on National Hunt than on competitive flat.** NH races have stronger form signals (jumping ability, going preference, trainer intent) that align with the current feature set. Competitive flat handicaps at major venues (Doncaster, Ascot, Curragh) produce the lowest win rates.

---

## Track-Level Recommendations

| Track | Action |
|-------|--------|
| Wolverhampton (AW) | Primary betting lane — apply decoy filter |
| Exeter, Newton Abbot, Stratford | Trust signal — low decoy, strong frame |
| Wexford | Trust signal when it fires |
| Chepstow | Apply decoy filter (19% decoy rate) |
| Hereford | Apply decoy filter (16.7% decoy rate) |
| Lingfield (AW) | Decoy filter mandatory |
| Newcastle (AW) | Decoy filter mandatory |
| Nottingham | Flag. Consider suppression until calibration improved. |
| Curragh | Flag. Ireland-specific model needed. |
| Doncaster, Ascot | Selective only. Large-field competitive — avoid backing 5/1+ |
| Thirsk | Frame betting only — not win selections |

---

## Forensic Conclusions

| Question | Answer |
|----------|--------|
| Is track performance variance real? | **Yes. Range from 0% (Nottingham) to 42.9% (Wexford).** |
| What is the primary track risk? | AW decoy contamination at Wolves, Lingfield, Newcastle, Kempton |
| Is AW profitable net of decoy? | Yes — 22.2% win rate is above system average. Filter, don't suppress. |
| Is Ireland a problem? | Yes. 13.3% win, 20.0% frame. Structurally underperforming. |
| Should Nottingham be suppressed? | Pending investigation. Zero wins from 15 is a serious flag. |
| Is the model a flat or NH specialist? | Better NH. Flat at major venues (Curragh, Doncaster, Ascot) is weak. |
