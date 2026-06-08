# Arena V2 Market Provenance Audit

**Status:** COMPLETE — closing market confirmed  
**Classification:** `CLOSING_MARKET_CONFIRMATION_ENGINE` / `NOT_MORNING_EDGE_ENGINE` / `MORNING_ODDS_ARENA_REQUIRED`  
**Date authored:** 2026-05-23  
**Authority:** El Presidente

---

## Purpose

Arena V2 added market signal features to the international pack arena tests and all 5 packs returned GATE_REOPENED_SAFE_SHADOW_CANDIDATE. Before any deployment decision is made, the provenance of every market feature must be established with precision.

**The central question:** Are the market features available at morning prediction time, or are they closing-market / race-start signals that would be inaccessible when VÉLØ runs?

---

## Market Feature Inventory

All 6 market features added to Arena V2 derive from a single source field: `sp_dec`.

| Feature | Derivation | Source field |
|---|---|---|
| `implied_prob` | `1 / sp_dec` | `sp_dec` |
| `sp_rank` | Rank within race by `sp_dec` | `sp_dec` |
| `log_sp` | `log(sp_dec)` | `sp_dec` |
| `is_fav` | `sp_dec == sp_dec.min()` within race | `sp_dec` |
| `market_prob_ratio` | `implied_prob / race_avg_implied_prob` | `sp_dec` |
| `form_mkt_diverge` | `rpr_rank_lagged - sp_rank` | `sp_dec` (for sp_rank component) |

**All 6 features are transformations of `sp_dec` exclusively.**

---

## What is sp_dec?

`sp_dec` is the **Starting Price** (SP) — the official settlement odds at the moment the race begins.

| Property | Value |
|---|---|
| Timing | Set at race off (post-parade, post-market close) |
| Availability | RACE-START ONLY — not available before the race begins |
| Morning availability | NO |
| Pre-race (late) availability | NO — SP is set at the instant of race-off |
| Category | CLOSING_MARKET |

SP is determined by the on-course bookmaker market at the moment of starting. In UK/IR racing it is the official BHA return price. In HK racing (HKJC) and FR racing (PMU), the equivalent is the final tote dividend or pari-mutuel pool.

**SP is the last known market signal, not the first.**

---

## Provenance Classification Per Feature

| Feature | Classification | Morning-safe? | Notes |
|---|---|---|---|
| `sp_dec` (source) | `CLOSING_MARKET_ONLY` | NO | Race-start price. Not available at morning prediction time. |
| `implied_prob` | `CLOSING_MARKET_ONLY` | NO | Transformation of sp_dec. |
| `sp_rank` | `CLOSING_MARKET_ONLY` | NO | Rank within race at race-off. |
| `log_sp` | `CLOSING_MARKET_ONLY` | NO | Log transform of sp_dec. |
| `is_fav` | `CLOSING_MARKET_ONLY` | NO | Favourite flag determined at race-off. |
| `market_prob_ratio` | `CLOSING_MARKET_ONLY` | NO | Race-normalised implied_prob — same timing issue. |
| `form_mkt_diverge` | `CLOSING_MARKET_ONLY` (partial) | NO | rpr_rank_lagged is PRE_RACE_SAFE; sp_rank component is CLOSING_MARKET_ONLY. Combined feature is CLOSING_MARKET_ONLY. |

**Summary: All 6 features are CLOSING_MARKET_ONLY. Zero morning-safe market features exist in Arena V2.**

---

## Source Data Verification

```
data/raceform_v17_features.parquet
  → sp_dec column: float64
  → sp_dec null%: 0.62% (near-complete coverage)
  → sp_dec sample values: [8.0, 67.0, 6.0, ...]
  → Interpretation: decimal SP odds (8.0 = 7/1, 67.0 = 66/1, 6.0 = 5/1)
```

These are post-race settlement prices drawn from historical Racing Post data. They are available in the training parquet because they are **results-linked** — each row's sp_dec is the price that was recorded after the race ran. This is the canonical post-race field.

In a live prediction pipeline, sp_dec for today's runners does NOT exist at morning run time.

---

## What Arena V2 Is

Arena V2 does NOT test whether VÉLØ can predict race outcomes using information available at morning selection time.

Arena V2 tests whether, given the market's closing consensus at race-off, a model trained on form features + that consensus can beat the favourite (who is also determined by the same closing market).

**Arena V2 is a CLOSING_MARKET_CONFIRMATION_ENGINE:**

```
CLOSING_MARKET_CONFIRMATION_ENGINE:
  Input: Form features (lagged, safe) + SP at race-off (CLOSING_MARKET_ONLY)
  Output: Beat-the-favourite accuracy using full market information
  Timing: Race-start — all market information visible
  Not equivalent to: Morning prediction with only form + morning odds
```

---

## What Arena V2 Is NOT

```
NOT_MORNING_EDGE_ENGINE:
  A morning prediction system requires features available before race-off.
  SP is not available before race-off.
  Arena V2 results cannot be used to claim morning edge.
```

If VÉLØ is to be deployed as a morning selection tool, a separate arena is required using only:
- Lagged form features (safe — already in Arena V1)
- Morning odds (HKJC tote pool morning price / PMU morning price) — NOT YET SOURCED

---

## Arena Classification

| Arena | Features | Timing | Classification |
|---|---|---|---|
| Arena V1 | Lagged form features only | PRE_RACE_MORNING_SAFE | MORNING_FORM_ENGINE — all 5 packs FAIL |
| Arena V2 (this audit) | Form + SP | CLOSING_MARKET | CLOSING_MARKET_CONFIRMATION_ENGINE — all 5 packs GATE_REOPENED |
| Arena V3 (not yet built) | Form + morning odds | PRE_RACE_MORNING_SAFE | MORNING_EDGE_ENGINE — required before any morning deployment |

---

## Implication for FR_AUTEUIL_JUMPS_V2

FR_AUTEUIL_JUMPS_V2 returned SR = FavSR (0pp gap) in Arena V2. The favourite is also determined by SP. The model tied the favourite exactly — this is the weakest result and is particularly marginal because:

1. The closing market signal is no more discriminating than simply backing the market favourite
2. Morning odds (if sourced) may provide less signal than SP for jump racing
3. FR_AUTEUIL_JUMPS_V2 remains lowest priority even after an Arena V3 is built

---

## Required Next Arena (Gate-Blocked)

Before any international pack can be classified for morning deployment, a third arena is required per pack:

**Arena V3 — Morning Odds Arena (MORNING_EDGE_ENGINE test)**  
- Uses lagged form features + morning market proxy (HKJC tote pool / PMU morning price)  
- Morning odds source must be proven legal and timestamped pre-race  
- Gate criteria: AUC ≥ 0.75 AND SR > FavSR (strictly greater) — same as V1/V2  
- Required for ALL 5 packs independently before any live deployment consideration

This is the provenance gap that must be closed. Arena V2 evidence is real and valuable — it confirms the form + market model works when full market information is available. It does not confirm morning deployability.

---

## Hard Rules

```
Arena V2 results ARE NOT sufficient evidence for morning deployment
Arena V2 results ARE valid evidence for closing-market strategy research
Morning odds sourcing (HKJC / PMU) required before Arena V3 can be built
SP at race-off MUST NOT be used as a live feature in the morning prediction pipeline
Morning odds legality must be confirmed before ingestion (no scraping without rights)
Each pack's Arena V3 must pass independently — no cross-pack credit
```

---

```
ARENA_V2_MARKET_PROVENANCE_AUDIT_STATUS: COMPLETE
MARKET_FEATURE_TIMING: CLOSING_MARKET_ONLY (all 6 features)
ARENA_V2_CLASSIFICATION: CLOSING_MARKET_CONFIRMATION_ENGINE
MORNING_DEPLOYABILITY: NOT_ESTABLISHED — Arena V3 required
MORNING_ODDS_SOURCE: NOT_YET_SOURCED (HKJC tote pool / PMU morning price needed)
GATE_STATUS: INTERNATIONAL_STILL_GATED — no promotion, no migration, no workers
```
