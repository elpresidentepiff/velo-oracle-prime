# VÉLØ Contextual Forecasting Layer V1

**Status:** DESIGN ONLY — RESEARCH  
**Phase:** 5 — Intelligence Research  
**Classification:** `CONTEXTUAL_FORECASTING_CORE_RESEARCH` / `NO_LIVE_SCORING` / `DESIGN_ONLY`

---

## Core Doctrine

Forecasting needs context, not just history.

The current VÉLØ model uses:
- Historical form ratings (RPR, OR, TS)
- Market signal (SP, implied_prob)
- Trainer/jockey profiles
- Draw bias
- Class trajectory

What it does NOT currently model:
- Going shift (horse runs different going today than form history suggests)
- Pace setup (front-runner in a field of front-runners — pace trap)
- Race compression (very short fields distort SR patterns)
- Field depth (novice vs competitive field)
- Class move context (class drop to easy race vs genuine class drop)
- Trainer intent signal (beyond RPDC tags)
- Market movement (how odds moved from morning to off — not just final SP)
- Late non-runners (field shrinkage changes dynamics)
- Source quality (Racing Post vs HKJC vs PMU rating reliability differs)
- Jurisdiction rules (HK weight-for-age vs FR handicapping vs UK flat/jump differences)
- Weather and track condition (wet draw bias differs from standard draw bias)
- Timestamp provenance confidence (how reliable is this feature for this race?)

---

## Feature Research Areas

### Going Shift Detection
- Does this horse's form history accurately reflect performance on today's going?
- Going code drift: trained on fast, running on soft → form derating required
- Integration with Race Shape (going affects pace map)

### Pace Setup Modelling
- Count front-runners in field
- Race Shape V2: pace compression score
- Pace-trapped runners have historically suppressed SR vs form

### Field Depth / Race Compression
- Very small fields (≤4 runners) behave differently — remove from main model
- Novice fields have high variance — lower confidence warranted
- Competitive fields (all OR within 5) — model performs better

### Market Movement Signal
- Morning odds → closing SP: how much did the horse shorten or drift?
- Contraction signal (shortened significantly = late money in)
- Drift signal (lengthened = market losing confidence)
- Note: current `odds_contraction_score` is 0 for HK/FR — needs recomputation

### Late Non-Runner Adjustment
- Field shrinkage from 12 to 9 changes draw bias and pace dynamics
- Models trained on 12-runner fields misapply to 9-runner fields

### Source Quality Weighting
- Racing Post ratings: highly reliable for UK
- HKJC ratings: reliable for HK (but different scale)
- PMU ratings: calibration differs from UK RP
- Temporal gap: old ratings (>90 days) should be downweighted

---

## Tie to Existing Research

| Research | Tie-in |
|---|---|
| Race Shape V2 | Pace setup, going interaction |
| Midprice diagnosis | SP 3–8.5 zone miss explanation |
| International lagged arena | Going-only model weak (AUC~0.51) — going context needed |
| HMM/Latent State (Phase 6) | Going-suited horse is a latent state |
| Arena V2 | Market signal dominant — contextual modifiers needed to add value on top |

---

## No-Go Rules

```
NO_LIVE_INTEGRATION: contextual forecasting is research only
NO_LIVE_SCORING: cannot affect VP or ensemble weights until evidence gate
NO_AUTOMATIC_GATE: research findings must go through Council before any integration
```

```
CONTEXTUAL_FORECASTING_V1_STATUS: DEFINED
IMPLEMENTATION: RESEARCH — no code changes until Phase 3 harness + Phase 1 spec established
```
