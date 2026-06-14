# VP Opportunity Gate V1
## VÉLØ Oracle Prime — Daily Operating Gate

**Status**: DRY-RUN ONLY — no live scoring change, no staking rule, no model change  
**Evidence base**: Corrected row-bearing Sigma universe, May 23–Jun 13, 711 rows  
**Script**: `scripts/ops/build_vp_opportunity_panel.py`  
**Version**: VP_OPPORTUNITY_GATE_V1  

---

## What VP Is

`velo_prime_prob` (VP) is the ensemble output probability from VÉLØ's scoring engine.

VP is the **primary permission signal** for whether VÉLØ should engage hard, engage lightly, or stand down.

It is not a scoring formula. It is not a staking rule. It is a Gatekeeper signal.

---

## What VP Is Not

- VP does not change model weights
- VP does not change the scoring formula
- VP does not enable live staking
- VP does not override race conditions
- VP is not a guarantee of wins
- VP cannot rescue picks priced above 6.0 SP

---

## VP Operating Bands (from corrected 711-row evidence)

| Band | SR | Interpretation |
|---|---|---|
| VP < 0.25 | ~18% | Weak / caution — model has no conviction |
| VP 0.25–0.30 | ~22% | Below baseline — review only |
| VP 0.30–0.35 | ~29% | Baseline zone — no strong signal |
| VP 0.35–0.40 | ~33% | Emerging signal |
| **VP 0.40–0.45** | **41%** | **Primary action zone — model engaged** |
| **VP 0.45–0.50** | **45%** | **High-conviction zone** |
| VP >= 0.50 | ~45% | Not materially better than 0.45 — ceiling exists |
| VP >= 0.55 | ~44% | Slight retreat — possible overconfidence signal |

**Baseline**: 25.5% SR across all 711 rows.  
**Primary action zone**: VP >= 0.40, SR=40.9%, n=181.

---

## VP and Odds Band (Critical)

VP is **not a short-price proxy**. It adds real value within price bands:

| SP band | All SR | VP>=0.40 SR | Lift |
|---|---|---|---|
| 1.5–2.5 | 53.2% | **76.9%** | +23.7pp — REAL ALPHA |
| 2.5–4.0 | 32.9% | **41.7%** | +8.8pp — MEANINGFUL |
| 4.0–6.0 | 14.8% | 20.0% | +5.2pp — MODEST |
| 6.0+ | 10.5% | 0.0% | NEGATIVE — VP cannot rescue |

**Operating window**: VP >= 0.40 within SP range 1.5–4.0.  
**Dead zone**: 6.0+ SP. VP does not lift this zone.  
**Dangerous zone**: 4.0–6.0. Modest lift only.

---

## Daily Gate Classification

Run after morning verdicts are generated (pre-race) or after sigma close (post-race).

### GREEN

All three criteria must hold:
- avg VP across today's picks >= **0.35**
- at least **5** picks with VP >= 0.40
- at least **2** picks with VP >= 0.45

Expected SR range: 35–40% (based on strong-day profile).

### AMBER

Mixed card:
- avg VP 0.25–0.35
- 1–4 picks with VP >= 0.40

Expected SR range: 25–30%.

### RED

Any of these triggers it:
- avg VP < 0.25
- zero picks with VP >= 0.40
- card >50% in known low-SR drain courses

Expected SR range: <18%.

---

## MANDATORY CAVEAT — FALSE GREEN RISK

**Jun 09 2026 produced a FALSE GREEN:**
- VP_avg = 0.355
- 10 picks with VP >= 0.40
- **0 wins from 33 evaluated** (SR = 0.0%)

This is the key failure case. High VP concentration on the day does not guarantee wins.

**The gate identifies opportunity conditions, not certain wins.**

21 days of evidence is insufficient to harden these thresholds.

**No live staking rule may be enabled based on gate label alone.**

---

## Additional Warning Signals

When the panel flags these, reduce engagement further:

| Flag | Meaning |
|---|---|
| HIGH_DRAIN_EXPOSURE | >40% of picks at known low-SR courses |
| NO_VP40_PICKS | Zero picks at VP>=0.40 — model has no conviction today |
| ALL_DEAD_ZONE | High proportion of picks above 6.0 SP |

---

## Course Context (as of corrected 711-row universe)

These tiers are based on corrected evidence and require sample discipline.

**n >= 20 = MEANINGFUL | n 10–19 = CAUTION | n < 10 = OBSERVATION ONLY**

| Course tier | Courses (n>=10 only) |
|---|---|
| DRAIN (n>=20, SR<=17%) | Nottingham (n=20, SR=10%), Lingfield (n=19, SR=11%) |
| DRAIN (n>=15) | Kempton AW (n=16, SR=12%) |
| CAUTION (n 10-19, poor) | Goodwood (n=12, SR=8%) |
| OK / Baseline | Hamilton, Windsor, Leicester, Redcar, Beverley, Thirsk |
| DOING_WELL | Uttoxeter (n=13, SR=46%), Wolverhampton (n=15, SR=33%) |
| OBSERVATION (n<10) | Newton Abbot (57%), Fontwell (50%), Bangor/Plumpton/Chepstow (43%) |

**No hard course bans until n >= 20 with sustained evidence.**

---

## SP Terminology (correct usage)

Always be explicit about which SP figure is being used:

| Field | Meaning |
|---|---|
| `race_winner_sp_avg_winning_picks` | avg SP of actual winner in races where our pick WON |
| `race_winner_sp_avg_all_picks` | avg SP of actual winner across all picks (wins + misses) |
| `pick_sp` | our pick's own starting price — RARELY available in sigma rows |

Do not mix these fields in reports.

---

## Scope of This Gate

| Action | Status |
|---|---|
| Classify day as GREEN/AMBER/RED | **YES — purpose of gate** |
| Change VP scoring weights | NO |
| Change model ensemble | NO |
| Enable staking | NO |
| Push to Supabase | NO |
| Send Telegram | NO |
| Override race conditions | NO |

---

## 2k+ Sigma Archive Note

The 711 rows used to calibrate this gate cover **May 23–Jun 13 only**.

The canonical Supabase `sigma_audits` table contains **2,528 rows from Jan 09–Jun 09**.

Gate thresholds must be re-evaluated once the older archive is reconciled.

Reconciliation plan: `data/reports/sigma_2k_archive_reconciliation_plan.md`

**Key risk**: Jan–Apr rows predate Ensemble Surgery v1. VP behaviour was different. Era-flagged merge required before thresholds can be hardened.

---

## How to Run

```bash
# Today's day (auto-detect, uses sigma if available, verdicts if not):
PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py

# Specific date:
PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py --date 2026-06-13

# Force verdicts file (pre-race, morning):
PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py --verdicts-file data/velo_prime_verdicts_2026_06_13.json

# Force sigma file (post-race, evening):
PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py --sigma-file data/sigma_results/sigma_results_2026_06_13.json
```

Output files:
```
data/reports/vp_opportunity_panel_YYYY_MM_DD.json
data/reports/vp_opportunity_panel_YYYY_MM_DD.md
data/reports/vp_opportunity_panel_latest.json  ← always overwritten
data/reports/vp_opportunity_panel_latest.md    ← always overwritten
```

---

*VP_OPPORTUNITY_GATE_V1 — Dry-run only — corrected row-bearing Sigma universe, 711 rows*
