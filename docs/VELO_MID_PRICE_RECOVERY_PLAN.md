# VÉLØ Mid-Price Recovery Plan
**Generated:** 2026-04-19 | **Source:** 241 mid_priced_won misses, price band forensic  
**Status:** Long-term roadmap. Not active cycle work.

---

## The Scale of the Problem

The 5–20 SP zone accounts for:
- 421 races (39.3% of all scored races)
- Win rate: 4.3–11.5% across sub-bands
- 40.2% of all misses originate here
- A-tier at 5–8 SP wins at only 6.2% — the model's structural failure is not a tier problem

This is not recoverable by better selection discipline or pass rules. It requires better feature engineering. This plan defines what that looks like.

---

## Why the Model Dies in the Mid-Price Zone

The organism was built to separate clear signals:
- Short-price favourites (dominant form, market consensus, proven class) → model excels
- Genuine outsiders (longshot_prob signal) → model occasionally fires correctly

What the model cannot currently do:
- Distinguish a well-handicapped horse from an over-exposed one in a competitive 0-85 field
- Detect a class drop candidate before the market prices it in
- Identify horses returning from strategic break with stable intent
- Weight sectional speed advantage in fields where surface draw matters

These are fundamentally different from the features the current ensemble uses.

---

## The Three Root Causes

### Cause 1: No Class Transition Signal

**Evidence:** 241 mid_priced_won misses. The dominant sub-class: horses winning by dropping in OR relative to race ceiling.

A horse rated OR 88 entering a 0-75 handicap is running 13lb below its rating. This is the most basic handicapping signal in the industry. The current model does not have a clean class-drop feature.

**Feature needed:** `or_class_ceiling_gap` = (horse OR) - (race ceiling OR). When this is > 10, the horse has a structural weight advantage.

**Data available:** OR is in the current feature set. Race ceiling OR is in the racing API (`race_class`, `race_rating_band`). This can be built from existing data.

---

### Cause 2: No Stable Confidence Proxy

**Evidence:** AW decoy races (94 misses, avg winner SP 4.80). The winner is typically 3–6/1. Connections knew. Market positioned early. We followed the fake steam.

**What's missing:** Trainer's recent win rate at this specific meeting/distance/class combination (AE ratio: actual winners / expected winners). A trainer with AE > 1.5 at Wolverhampton AW 1m handicaps is signalling intent.

**Feature needed:** `trainer_meeting_ae` — trainer's A/E ratio split by course + race type combination.

**Data available:** Trainer data is partially in `trainer_profiles`. Historical AE calculation requires run-result history — available via Racing API but requires a build.

---

### Cause 3: No Sectional / Finish Speed Signal

**Evidence:** Tight-margin competitive handicaps (5–8 SP range) are decided by inches. The model uses form positions and pace_chain but not actual finish speed or sectional splits.

**What's missing:** A horse that has been "running on late" in its last 3 starts (beaten by a length or less, finishing faster than winner in last furlong) is a better candidate for mid-price wins than a horse whose form figures look similar but was beaten further.

**Feature needed:** `late_speed_index` — how much the horse gained ground in the final 2 furlongs vs the field average, normalised by race conditions.

**Data required:** Timeform sectional API or Racetech sectional data. These are third-party data sources not currently in the pipeline.

---

## What Can Be Done Without New Data

One mid-price fix is possible with existing data:

### Existing Feature: class_drop detection (build now)

```python
# Compute from existing fields in full_analysis:
# horse.official_rating vs race.rating_ceiling
or_class_gap = horse_or - race_ceiling_or
if or_class_gap > 10:
    class_drop_flag = True
    class_drop_magnitude = or_class_gap  # the bigger, the stronger the signal
```

This is a Tier 2 feature (reweighting of existing data). It does not require new data sources. It requires:
1. Ensuring `official_rating` (OR) is consistently populated in runner data
2. Ensuring race ceiling OR is pulled from the racing API racecard
3. Computing the gap and adding it as a feature flag

**Expected impact:** The class_drop signal has literature support as one of the strongest mid-price handicap indicators. Implementing it could address a subset of the 241 mid_priced_won misses. Quantifying the impact requires testing after implementation — cannot pre-estimate without data.

---

## Phased Recovery Roadmap

### Phase 1: Class Drop (existing data, near-term)
- Add `or_class_ceiling_gap` feature
- Add to full_analysis output per horse
- Evaluate: does weighting this feature change tier assignment for mid-price horses?
- Expected build time: 1–2 sessions
- Expected impact: unknown until tested

### Phase 2: Trainer AE at Meeting/Distance (Racing API data build)
- Build historical trainer performance table: wins/runs per trainer per course+distance+class combination
- Compute `trainer_meeting_ae` ratio
- Add to full_analysis as a signal flag
- Expected build time: 3–5 sessions (requires historical data ingestion)
- Expected impact: should directly address AW controlled handicap decoy problem

### Phase 3: Sectional Data Integration (third-party data required)
- Source Timeform sectional data or equivalent
- Build `late_speed_index` per horse per run
- Integrate into feature engineering pipeline
- Expected build time: significant (new data partner, ingestion pipeline)
- Expected impact: highest potential upside but most complex

---

## What This Plan Does NOT Include

- Retraining the SQPE ensemble — the current model is the correct architecture
- Adding macro features beyond what's already built
- Any work before Tier 1 (pass rules, MDS re-routing, price discovery) is complete

Mid-price recovery is a third-order problem. Fix the organism's discipline and pricing problem first. The mid-price zone will still be hard even after those fixes — but the organism will be healthier overall when you attack it.
