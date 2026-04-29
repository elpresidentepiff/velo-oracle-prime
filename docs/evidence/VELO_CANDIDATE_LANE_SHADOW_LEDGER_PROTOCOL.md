# VÉLØ Candidate Lane Shadow Ledger Protocol

**Version:** 1
**Created:** 2026-04-29 00:43 UTC
**Status:** DESIGN ONLY

---

## What This Protocol Governs

The shadow ledger system tracks qualifying races against each candidate signal lane
after race results close. It provides the evidence base for future promotion decisions.
It does not change predictions, routing logic, staking, or any production system.

---

## When to Append

After every sigma batch (`run_results_sigma.py`), run the append script:

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/run_candidate_lane_shadow_append.py --date YYYY-MM-DD
```

*(Script not yet built — next mission: candidate_lane_shadow_ledger_dry_run)*

---

## How Qualification Works

For each sigma_audit row on the date:
1. Load the verdict JSON for that race (VP, MDS, improve_score, place_prob, tier)
2. Evaluate each lane condition
3. If condition met: append one row to that lane's ledger CSV
4. A race may qualify for multiple lanes simultaneously
5. Dedup: skip if race_id already exists in that lane's ledger

---

## Highest Priority Lane

> **MARKET_DECEPTION_HIGH** — SR=54.8%, Frame=96.8%, n=31
>
> This is the highest-lift signal in the system. The polarity flip (previously used as
> a decoy blocker, now confirmed as a winner predictor) makes this the most important
> signal to track. Every qualifying row added to this ledger is high-value evidence.

---

## Promotion Decision Process

1. Running stats are computed after each batch
2. When minimum_n is reached, SR and Frame are reviewed
3. If SR >= floor AND Frame >= floor: generate promotion notice to operator
4. Operator reviews lane evidence document before any promotion decision
5. No promotion without explicit operator approval
6. Promotion moves lane to next lifecycle stage — it does NOT activate live staking

---

## Storage Layout

```
data/shadow_ledgers/
  vp30_tier_a_shadow_ledger.csv
  market_deception_high_shadow_ledger.csv
  improvement_score_high_shadow_ledger.csv
  place_prob_high_shadow_ledger.csv
  b_tier_low_vp_suppress_ledger.csv
  mid_price_winner_forensics_ledger.csv
  shadow_ledger_index.json           ← running stats per lane
  snapshots/                          ← immutable timestamped snapshots
```

---

## Hard Rules (Non-Negotiable)

- NO staking or betting based on ledger state.
- NO router rule changes from ledger observations.
- NO model training based on ledger patterns.
- NO promotion without operator approval.
- NO auto-unfreeze of MARKET_DECEPTION_HIGH — operator-only.

---
*VÉLØ Shadow Ledger Protocol V1 | 2026-04-29 00:43 UTC*