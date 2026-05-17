# MIDPRICE ROUTER SUPPRESSION ADVISORY V1

**Classification:** ADVISORY_ONLY | NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_STAKING_CHANGE
**Evidence base:** SP_MIDPRICE_LEAK_AUDIT_V1 (2026-05-17)
**Status:** ACTIVE — reporting layer only

---

## What This Is

An advisory suppression flag for VELO selections in the SP 3.0–8.5 zone that lack router lane qualification.

This is not a model change. It is an operator awareness layer. The flag is reported in Mission Control and weekly audits. It does not change scoring, weights, staking, or routing logic.

---

## Evidence Base

From `SP_MIDPRICE_LEAK_AUDIT_V1` (67 days, 317 mid-price selections with results):

| Finding | Value |
|---|---|
| Mid-price SR | 15.5% |
| Global SR | 21.4% |
| Gap | **-5.9pp** (mid-price underperforms) |
| VP separation (winners vs bait) | +0.007 (noise — no useful separation) |
| MDS separation | +0.008 (noise) |
| Improvement separation | -0.012 (inverse — bait scores higher) |
| MDS>0.5 occurrences in mid-price | 0 of 317 (market-trap detector absent in this zone) |

Router lanes separate strongly inside mid-price:

| Lane | In-lane SR | Out-lane SR | Separation |
|---|---|---|---|
| V1_BASE | 38.5% (n=13) | 14.5% | +24pp |
| V2_CLASS4 | 40.0% (n=10) | 14.7% | +25pp |
| V6_GOLD_SEAM | 60.0% (n=5) | 14.7% | **+45pp** |

**Conclusion:** In the SP 3.0–8.5 zone, VP and MDS alone do not separate winners from bait. Router lane qualification does.

---

## The Advisory Flag

**Name:** `midprice_router_suppression_advisory`

**Condition (true when ALL of the following):**
1. Expected or actual SP is in range [3.0, 8.5]
2. No active router lane among V1_BASE, V2_CLASS4, V6_GOLD_SEAM

**Where it appears:**
- Mission Control JSON (`prediction.midprice_advisory`)
- Mission Control console output
- Weekly audit reports

**Where it does NOT appear:**
- Scoring output — not changed
- Telegram — not changed
- Betfair bridge — not connected
- Router rules — not changed

---

## Operational Meaning

A selection flagged `midprice_router_suppression_advisory=true` is a horse where:
- VELO believes it has merit (VP may be reasonable)
- But it sits in a price zone where the signals do not reliably separate winners from bait
- And no router lane has qualified it as an active tracking candidate

**Operator interpretation:** This is the mid-price noise zone. Watch, but do not act without additional evidence.

A selection flagged `midprice_router_suppression_advisory=false` (i.e., router-qualified in mid-price) is significantly more interesting. Historically, router-qualified mid-price selections perform at 38–60% SR, vs 14.5% for unqualified ones.

---

## The Money Question (from suppression audit)

Before treating this as a suppression rule, the question must be answered:

> If we suppress mid-price non-router selections, how many losers do we remove vs winners we lose?

This is answered by `scripts/midprice_router_suppression_audit.py`.

The audit outputs:
- Total winners suppressed and % of all winners
- Total losers removed and % of all losers
- Loser:winner ratio in suppressed group
- Net SR and Frame delta if suppression had been active

**Gate for promotion to active suppression rule:**
- Loser:winner ratio ≥ 5:1 in suppressed group
- Net SR delta ≥ +1.5pp
- Net Frame delta ≥ +1.0pp
- n ≥ 50 in the suppressed group
- Reviewed and approved by operator

Until these gates are passed, this remains advisory only.

---

## Audit Scripts

| Script | Purpose |
|---|---|
| `scripts/sp_midprice_leak_audit.py` | Full mid-price dissection by VP/MDS/tier/lane/course/class |
| `scripts/midprice_router_suppression_audit.py` | Money question: losers removed vs winners lost |

---

## Governance

No changes were made to:
- Scoring weights or model parameters
- Router lane rules or thresholds
- Staking amounts or execution mode
- Telegram format or output
- Playbook G directives
- Live state

The advisory layer is read-only. It observes and reports. It does not act.

---

*MIDPRICE_ROUTER_SUPPRESSION_ADVISORY_V1 — locked 2026-05-17*
