# VÉLØ Process Wiring Map V1

> **One Truth document.** Defines how data flows through VÉLØ from scoring through operator output.
> Companion to `TRUTH_REGISTRY.md` (field/table truth) and `VELO_RUNTIME_MAP_V1.md` (file classification).
> Last updated: 2026-05-01.

---

## Daily Flow Overview

```
Racing API
    │
    ▼
run_prime_today.py  ── normalize ── score_race_velo_prime()
    │                                       │
    │                                velo_verdicts (Supabase)
    │                                       │
    ├─── Telegram: VP30 card (A/B/C/D/X)   │
    │                                       │
    ├─── Telegram: PLACE SIGNALS ◄──────────┤ (see Section 1)
    │                                       │
    └─── Local: place_signal_operator_card.py ◄── scripts/place_signal_operator_card.py
                        │
                data/place_signal_operator_card_YYYY_MM_DD.md

After results close:
    run_results_sigma.py ──► sigma_audits (Supabase) / velo_post_race_reviews
```

---

## Section 1 — Place Signal Classifier: Operator Visibility Layer

### Status

```
OPERATOR_VISIBILITY_ONLY
TELEGRAM_OPTIONAL           (gate: VELO_ENABLE_PLACE_SIGNAL_TELEGRAM, default OFF, now ON)
NOT_LIVE_WEIGHTED           (no change to velo_prime_prob, SQPE, ensemble)
NOT_STAKING                 (no betting instruction)
NOT_ROUTER_PROMOTION        (no candidate_route() change)
NO_SCORING_CHANGE           (read-only from velo_verdicts)
```

### Files

| File | Role |
|---|---|
| `src/velo/place_signal_classifier.py` | Core classifier — `PlaceSignal` dataclass + `classify()` + `classify_from_verdict()` |
| `scripts/place_signal_operator_card.py` | Daily operator card — reads `velo_verdicts`, classifies, outputs markdown |
| `scripts/run_prime_today.py` | Wires place signal Telegram via `_build_place_signal_tg()` in STEP 5 |

### Entry Point

```python
from src.velo.place_signal_classifier import classify_from_verdict, PlaceSignal
sig: PlaceSignal = classify_from_verdict(verdict_row)
```

### Inputs (from `velo_verdicts`)

| Field | Threshold | Role |
|---|---|---|
| `velo_prime_prob` | ≥ 0.30 = VP30 | Primary gate — no signal below |
| `decision_tier` | `A` = elite tier | ELITE gate trigger |
| `market_deception_score` | > 0.50 = MDS_HIGH | ELITE / STRONG gate trigger |
| `improvement_score` | > 0.40 = IMP_HIGH | STRONG_PLUS / IMPROVE_WATCH trigger |
| `place_prob` | > 0.80 = PLACE_HIGH | PLACE_SUPPORT trigger |

### Classification Priority (first match wins)

| Label | Conditions | Status | Min Place Odds | E/W 1/4 ROI | n |
|---|---|---|---:|---:|---:|
| `ELITE_PLACE_STACK` | Tier A + VP30 + MDS_HIGH | `LIVE_OPERATOR_PLACE_SIGNAL` | 1.05 | +170% | 28 |
| `STRONG_PLACE_STACK_PLUS` | VP30 + MDS_HIGH + IMP_HIGH | `LIVE_OPERATOR_PLACE_SIGNAL` | 1.05 | +90% | 20 |
| `STRONG_PLACE_STACK` | VP30 + MDS_HIGH | `LIVE_OPERATOR_PLACE_SIGNAL` | 1.05 | +169% | 35 |
| `IMPROVE_PLACE_WATCH` | VP30 + IMP_HIGH (no MDS) | `LIVE_OPERATOR_PLACE_WATCH` | 1.20 | +51% | 46 |
| `SUPPRESS` | Tier B + VP < 0.30 | `SUPPRESS` | never | — | 303 |
| `PLACE_SUPPORT_WATCH` | VP30 + PLACE_HIGH (no MDS, no IMP) | `LIVE_OPERATOR_PLACE_WATCH` | 1.40 | +59% | 251 |
| `BASE_PLACE_TRUST` | VP30 only | `BASE_PLACE_TRUST` | 1.50 | +52% | 380 |
| `BELOW_VP30` | VP < 0.30 | `NO_SIGNAL` | — | — | — |

### Outputs

`PlaceSignal` dataclass fields:

| Field | Type | Notes |
|---|---|---|
| `place_stack_label` | str | Label from table above |
| `place_stack_status` | str | `LIVE_OPERATOR_PLACE_SIGNAL` / `LIVE_OPERATOR_PLACE_WATCH` / `BASE_PLACE_TRUST` / `NO_SIGNAL` / `SUPPRESS` |
| `min_place_odds` | float\|None | Minimum exchange place odds for +EV (operator must verify) |
| `evidence_n` | int | Sample size from audit |
| `evidence_frame_rate` | float | WIN+PLACE rate from audit |
| `evidence_win_sr` | float | Win strike rate from audit |
| `evidence_ew_1_4_roi` | float | Each-way 1/4 place-leg ROI from audit |
| `badges` | list[str] | Flags that fired: `VP30`, `MDS_HIGH`, `IMP_HIGH`, `PLACE_HIGH`, `TIER_A` |
| `suppress_reason` | str\|None | `B_TIER_LOW_VP` if SUPPRESS |
| `place_operator_note` | str | Human-readable evidence note |

### Telegram Gate

```
Env var:  VELO_ENABLE_PLACE_SIGNAL_TELEGRAM
Default:  0 (OFF)
Current:  1 (ON — set 2026-05-01)
```

When enabled, fires in `run_prime_today.py` STEP 5 — after C-WATCH list, before D/X pass list.
Sends ELITE through BASE_PLACE_TRUST only. SUPPRESS and BELOW_VP30 are excluded from Telegram.
Gated in a try/except — failure is non-fatal, scoring pipeline unaffected.

### Where It Sits in Daily Flow

1. `run_prime_today.py` STEP 3 — verdicts generated + persisted to `velo_verdicts`
2. `run_prime_today.py` STEP 4 — verdicts written to Supabase
3. `run_prime_today.py` STEP 5 — `_build_place_signal_tg()` classifies from `scored` list (in-memory), sends if gate ON
4. Separately: `scripts/place_signal_operator_card.py --date YYYY-MM-DD` — reads from Supabase, outputs full markdown card
5. After results close: outcomes can be matched against place signal class for economics tracking

### Safety Contract

```
NO change to velo_prime_prob
NO change to SQPE
NO change to ensemble weights
NO change to decision_tier
NO change to candidate_route()
NO change to router shadow lanes
NO staking
NO Betfair integration
NO live execution
READ-ONLY from velo_verdicts
```

### Proof Run — 2026-05-01

```
1  ELITE_PLACE_STACK
1  IMPROVE_PLACE_WATCH
8  PLACE_SUPPORT_WATCH
5  BASE_PLACE_TRUST
9  SUPPRESS
19 BELOW_VP30
```

All syntax checks passed. No runtime errors. No scoring pipeline impact.

### Known Next Step

1. Collect outcomes (WIN / PLACED / MISS) per place signal class over next 20+ days
2. Track actual place frame rate vs audit expectation
3. Do not discuss promotion until n≥20 per class with closed results

### Commit History

| Commit | Description |
|---|---|
| `58ed2a1` | feat: add VÉLØ place economics audit and place signal operator visibility |

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-01 | Document created. Section 1: Place Signal Classifier wired. |
