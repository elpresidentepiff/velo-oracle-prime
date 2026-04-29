# VÉLØ Telegram Signal Attribution Panel V1

**Version:** 1
**Created:** 2026-04-29 00:43 UTC
**Status:** DESIGN ONLY

---

## Why This Exists

VÉLØ has discovered signals that predict race outcomes at elite levels:

| Signal | SR | Frame | n |
|---|---|---|---|
| Market Deception Score > 0.50 | **54.8%** | **96.8%** | 31 |
| VP≥0.30 + Tier A | 40.1% | 77.2% | 162 |
| Improvement Score > 0.40 | 43.5% | 82.3% | 62 |

These signals are currently invisible at the operator layer.
The Telegram output shows VP and Tier but does not surface which candidate
lanes fired, what the sidecar values are, or whether the pick is in a
drag or suppress zone.

This panel design fixes that without changing any prediction logic.

---

## What the Panel Shows

For every VÉLØ pick in the Telegram report:

1. **VP and Tier** — always shown (already present, format standardised)
2. **Candidate Lane Badges** — which of the 6 shadow lanes fired
3. **Sidecar Values** — MDS, improvement score, place prob if above threshold
4. **Suppress Warnings** — if the pick is in a confirmed drag zone
5. **Risk Flags** — mid-price winner danger zone, short-fav override risk
6. **Router Status** — always confirms shadow-only state
7. **Operator Note** — SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION

---

## What the Panel Does NOT Do

- Does not change predictions
- Does not change routing logic
- Does not imply staking approval for any badge
- Does not override the human operator's decision
- Does not produce or modify any model outputs

---

## The Company Case

> VÉLØ does not merely output predictions.
> VÉLØ audits its own confidence, identifies which signal families are working,
> and refuses to promote them until a shadow ledger proves durability.
> The Signal Attribution Panel makes this legible to the operator in real time.

A horse with VP=0.34, Tier A, MDS=0.71, Improvement=0.47 is not the same
as a horse with VP=0.34, Tier A, MDS=0.10, Improvement=0.12.
The prediction layer must expose that difference.

---
*VÉLØ Telegram Signal Attribution Panel V1 | 2026-04-29 00:43 UTC*