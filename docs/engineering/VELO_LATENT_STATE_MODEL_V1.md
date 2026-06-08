# VÉLØ Latent State Model V1

**Status:** DESIGN ONLY — RESEARCH  
**Phase:** 6 — Hidden State Research  
**Classification:** `LATENT_STATE_RESEARCH_ONLY` / `NO_PRODUCTION_USE` / `DESIGN_ONLY`

---

## Purpose

A horse is not stationary. Between races, its latent state evolves in ways that are not visible in the form book. The current VÉLØ model treats each race independently conditioned on lagged features. Latent state modelling attempts to estimate the hidden condition of each runner.

No production use. No model promotion. Research only.

---

## Latent States Catalogue

| State | Description | Observable Signal |
|---|---|---|
| IMPROVING | Horse is on an upward trajectory — performance exceeding OR | Improving RPR trend, progressive SP drift, trainer timing active |
| REGRESSING | Horse is declining — below OR in recent runs | Falling RPR trend, trainer easing off, shorter between-run gaps |
| LAID_OUT | Horse has been rested deliberately — trainer timing the run | Long absence (>90 days), OR held flat, trainer+jockey combination returning |
| OVERBET | Horse receives more market support than form warrants | SP much lower than RPR rank implies, negative form_mkt_diverge |
| UNDERBET | Horse receives less market support than form warrants | SP higher than RPR rank implies, positive form_mkt_diverge |
| GOING_SUITED | Horse has strong going preference that is matched today | High going-fit score, form history on same going positive |
| COURSE_SPECIALIST | Horse has exceptional course record relative to overall form | High course_prior_wr >> baseline wr |
| PACE_COMPROMISED | Horse's typical run style is disadvantaged by today's pace setup | Front-runner in pace-hot race, or hold-up horse in slow race |
| TRAINER_INTENT_ACTIVE | Trainer timing signal (RPDC) active | Cash run flag, cycle tag, release day signal |
| MARKET_FALSE_FAVOURITE | Market favourite based on reputation, not recent form | Low SP but RPR rank not 1st, class drop from previous win |
| RACE_SHAPE_TRAP | Horse is tactically compromised by field setup | Draw + pace + field size combination unfavourable |

---

## HMM Research Direction

Hidden Markov Models offer a natural framework:
- Hidden states: the latent conditions above
- Observations: lagged form figures, market signal, race context
- Transition matrix: how states evolve between runs
- Emission matrix: what feature patterns each state tends to produce

Initial research targets:
1. Fit a simple 3-state HMM (IMPROVING / STABLE / REGRESSING) on UK flat form data
2. Assess state persistence: how many runs does a state typically last?
3. Assess emission patterns: what features distinguish states?
4. Compare: does HMM state improve AUC vs. lagged-only baseline?

---

## Connection to Arena Evidence

Arena V2 showed that form-only model (no market signal) has AUC~0.64–0.71. Adding market signal jumps AUC to 0.78–0.90. The gap between market signal and form signal is explained by latent state information embedded in the price. A latent state model could close some of this gap from the form side.

---

## Hard Rules

```
NO_PRODUCTION_USE: HMM/latent-state is research only
NO_MODEL_PROMOTION: no latent state model enters scoring without evidence gate
NO_LIVE_SCORING: latent state scores are shadow/research only
RESEARCH_HORIZON: Phase 6 — no implementation until Phase 3 harness established
```

```
LATENT_STATE_MODEL_V1_STATUS: DEFINED
IMPLEMENTATION: RESEARCH_ONLY — Phase 6
```
