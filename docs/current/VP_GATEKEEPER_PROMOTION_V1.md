# VP Gatekeeper Promotion V1
## VÉLØ Oracle Prime — Operational Doctrine

**Status**: DRY-RUN / REPORTING ONLY — no live scoring, no staking, no model change
**Promoted**: 2026-06-14
**Evidence base**: Current-era sigma union, 1,263 rows, May 08–Jun 13 2026
**Supersedes**: VP_OPPORTUNITY_GATE_V1.md (gate criteria unchanged, scope expanded)

---

## The Doctrine

> **VP is the primary permission signal for whether VÉLØ should engage hard, engage lightly, or stand down.**

VP controls **engagement intensity**, not the model's raw score.

---

## What VP Controls

| Domain | VP role |
|---|---|
| Daily opportunity classification | YES — GREEN / AMBER / RED gate |
| Engagement intensity | YES — how hard to lean on today's picks |
| Selection confidence filter | YES — VP>=0.40 is primary action zone |
| Day-strength diagnosis | YES — avg VP across the card |
| Course/track performance lens | YES — VP contextualises course signal |
| Sigma archive analysis spine | YES — VP as discriminating variable across history |
| Post-race review spine | YES — VP vs outcome retrospective |

---

## What VP Does Not Control

| Domain | Status |
|---|---|
| Live scoring formula | **NO — not changed** |
| Model weights | **NO — not changed** |
| Automatic staking | **NO — never triggered by gate alone** |
| Telegram sends | **NO** |
| Supabase writes | **NO** |
| Model promotion | **NO** |

---

## Why VP Was Promoted

VP was not weak. The pipeline was weak.

The model carried the signal. The system buried it in the `notes` field, failed to promote it into row schema, and let downstream artifacts lose visibility. This is a **harness failure**, not an intelligence failure.

Evidence: the VP gradient holds across the full historical archive:

| Outcome | Mean VP (2,286 rows across archive) |
|---|---|
| WIN | **0.3367** |
| PLACED | 0.2948 |
| MISS | 0.2394 |

---

## VP Performance — Current Era (1,263 rows, May 08–Jun 13)

| Metric | Value |
|---|---|
| Baseline SR | 24.3% |
| Mean VP | 0.2953 |
| VP>=0.40 SR | **41.5%** (n=253) |
| VP>=0.45 SR | 44.8% (n=181) |
| VP>=0.50 SR | 45.6% (n=125) |
| VP>=0.60 SR | **50.0%** (n=50) |

The gradient is monotonic and clean.

---

## VP Operating Bands

| Band | SR | Interpretation |
|---|---|---|
| VP < 0.25 | 16.8% | No conviction |
| VP 0.25–0.30 | 21.9% | Below baseline |
| VP 0.30–0.35 | 27.1% | Baseline zone |
| VP 0.35–0.40 | 24.4% | Variable / emerging |
| **VP 0.40–0.45** | **33.3%** | **Primary action zone** |
| **VP 0.45–0.50** | **42.9%** | **High-conviction zone** |
| VP >= 0.50 | 45.6% | Very high conviction |
| VP >= 0.60 | **50.0%** | Peak conviction (n=50) |

---

## VP and Odds Band

| Winner SP band | All SR | VP>=0.40 SR | Verdict |
|---|---|---|---|
| 1.0–2.5 | 60.7% | **74.3%** | **REAL ALPHA +13.6pp** |
| 2.5–4.0 | 35.5% | 33.3% | Mixed (n=45) |
| 4.0–6.0 | 18.6% | 26.9% | Modest lift |
| 6.0–10.0 | 14.2% | 13.6% | ~flat |
| 10.0+ | 6.1% | 4.2% | **DEAD ZONE** |

---

## Daily Gate Classification

### GREEN
All three criteria:
- avg VP >= **0.35**
- at least **5** picks VP >= 0.40
- at least **2** picks VP >= 0.45

### AMBER
- avg VP 0.25–0.35
- 1–4 picks VP >= 0.40

### RED
- avg VP < 0.25 OR zero picks VP >= 0.40

---

## MANDATORY CAVEAT — FALSE GREEN RISK

**2026-06-09 produced a FALSE GREEN:**
- VP_avg = 0.358, 9 picks VP>=0.40, SR = 13.8%

The gate identifies opportunity conditions. It does not guarantee outcomes.

**No live staking rule may be enabled based on gate label alone.**

---

## Era Definition

| Era | Date range | Status |
|---|---|---|
| CURRENT_ERA | May 08–present | Gate applies |
| PRE_SURGERY_MAY | May 01–07 | Separate study |
| PRE_SURGERY_ARCHIVE | Mar–Apr | Separate study |
| SKELETON | Jan–Feb | Excluded |

---

## Course Context (Current Era, 1,263 rows)

| Tier | Courses (MEANINGFUL n>=20) |
|---|---|
| EXCELLING | Musselburgh (55% SR), Worcester (47.6%), Uttoxeter (44.4%) |
| DOING_WELL | York, Salisbury, Windsor, Catterick, Chester |
| OK | Bath, Lingfield, Leicester, Goodwood, Doncaster, Haydock, Ripon, Chepstow |
| CAUTION | Hamilton (16.1%), Nottingham (18.5%) |
| DRAIN | Yarmouth (9.1%), Beverley (10.0%) |

No hard course bans until n >= 30 with sustained evidence.

---

## How to Run

```bash
# Today's gate (auto-detect):
PYTHONPATH=. ./venv/bin/python scripts/ops/build_vp_opportunity_panel.py

# Specific date:
PYTHONPATH=. ./venv/bin/python scripts/ops/build_vp_opportunity_panel.py --date 2026-06-14

# Pre-race (morning verdicts):
PYTHONPATH=. ./venv/bin/python scripts/ops/build_vp_opportunity_panel.py --verdicts-file data/velo_prime_verdicts_2026_06_14.json

# Post-race (sigma close):
PYTHONPATH=. ./venv/bin/python scripts/ops/build_vp_opportunity_panel.py --sigma-file data/sigma_results/sigma_results_2026_06_14.json
```

**VP Gatekeeper is report-only. It controls engagement review intensity only. It does not alter live scoring, staking, model weights, selections, or Telegram output.**

---

## Scope Confirmation

| Action | Status |
|---|---|
| Classify day as GREEN/AMBER/RED | **YES** |
| Surface VP by course/odds/date | **YES** |
| Change scoring formula | **NO** |
| Change model weights | **NO** |
| Enable live staking | **NO** |
| Write to Supabase | **NO** |
| Send Telegram | **NO** |

---

*VP_GATEKEEPER_PROMOTION_V1 — Dry-run only — Current-era 1,263 rows — 2026-06-14*
