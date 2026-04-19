# VÉLØ Price Band Forensic
**Generated:** 2026-04-19 | **Base:** 1,070 scored races

---

## The Full Curve

| Winner SP Band | Races | Win% | Frame% | Miss Share | Rank-2 Recovery |
|----------------|-------|------|--------|------------|-----------------|
| <2.0 (odds-on) | 91 | **61.5%** | **83.5%** | 2.7% | 5 (33.3% of band misses) |
| 2.0–3.0 | 184 | **33.7%** | **62.5%** | 12.4% | 26 (37.7%) |
| 3.0–5.0 | 284 | 19.7% | 50.7% | 25.2% | 28 (20.0%) |
| 5.0–8.0 | 227 | 11.5% | 39.2% | 24.8% | 18 (13.0%) |
| 8.0–12.0 | 127 | 7.1% | 32.3% | 15.5% | 9 (10.5%) |
| 12.0–20.0 | 94 | 4.3% | 31.9% | 11.5% | 2 (3.1%) |
| 20.0+ | 62 | **8.1%** | 29.0% | 7.9% | 3 (6.8%) |

---

## Zone Classification

### DOMINANT: <2.0
- 61.5% win rate. 83.5% frame rate.
- When the race resolves at odds-on, VÉLØ is pointing at it 61% of the time.
- Only 2.7% of all misses come from this zone.
- **Action:** Trust the model completely here. Any odds-on pick is a high-confidence selection candidate.

### STRONG: 2.0–3.0
- 33.7% win rate. 62.5% frame.
- 184 races — meaningful sample.
- Rank-2 recovery is highest here (37.7%) — close-margin races where second horse matters most.
- **Action:** Primary selection zone for future betting lanes. High edge band.

### COMPETENT: 3.0–5.0
- 19.7% win, 50.7% frame.
- Largest single band: 284 races = 26.5% of all races.
- 25.2% of all misses originate here — the single biggest miss-volume bucket.
- Rank-2 covers 20% of band misses.
- **Action:** Selective only. Market decoy contamination is real here. Needs decoy filter.

### DEAD ZONE: 5.0–12.0
- 5.0–8.0: 11.5% win. 8.0–12.0: 7.1% win.
- Combined 354 races, combined 40.3% of all misses.
- Rank-2 recovery drops sharply (10–13%).
- **This is where money disappears.** The model cannot price horses in this zone.
- **Action:** Do not pursue. If winner is in this band, we simply do not know who it is.

### VALUE RECOVERY: 12.0–20.0
- 4.3% win. Dead by win rate alone.
- BUT: 31.9% frame means we are in the top-3 often even here.
- Rank-2 recovery almost zero (3.1%) — when a 12–20/1 wins, it is truly not in our top-2.
- **Action:** Block from single-pick selection. Cannot recover here with 2nd pick either.

### OUTSIDER SNAP: 20.0+
- 8.1% win — higher than 8–20 bands. The model occasionally finds 20/1+ winners.
- 5 confirmed wins at 20/1+: 51/1, 41/1, 34/1, 23/1, 21/1.
- These are genuine value hits — the model's outsider detection signal is working.
- **Action:** Do not suppress outsider signals. When the model fires at 20/1+, respect it.

---

## A-Tier by Price Band

| Band | n | Win% | Frame% | Reading |
|------|---|------|--------|---------|
| <2.0 | 36 | **72.2%** | **91.7%** | Exceptional |
| 2.0–3.0 | 32 | **46.9%** | **84.4%** | Premium |
| 3.0–5.0 | 25 | 20.0% | 72.0% | Competent |
| 5.0–8.0 | 16 | 6.2% | 62.5% | Frame only |
| 8.0–12.0 | 5 | 40.0% | 60.0% | Small sample, volatile |
| 20.0+ | 4 | 0.0% | 50.0% | Too small |

**A-tier is elite up to 5/1. Above 5/1, even A-tier cannot reliably win — it can frame.**  
The 6.2% win rate for A-tier at 5–8 SP is the clearest evidence that the model's structural weakness in the mid-price zone is not a tier problem — it is a fundamental pricing problem.

---

## The Mid-Priced Killing Field

The 5–20 zone accounts for:
- 421 races (39.3% of all races)
- Combined win rate: 8.3%
- 40.2% of all misses

**Why we die here:**
1. Mid-priced horses in this zone are not clearly the market pick and not clearly outsiders — they sit in the ambiguity zone.
2. The model's feature engineering (specialist scores, RPDC tags, pace) is designed to separate clear favourites from the field. It is not calibrated for ambiguous competitive handicaps.
3. Market decoy contamination is highest in the 3–8 range — controlled AW handicaps where market moves mislead.

**Recovery via rank-2 in this zone:** partial. Rank-2 covers 13–20% of misses in the 3–8 band, dropping to 3% at 12–20. The answer is not a second pick — it is better feature engineering for the mid-priced zone.
