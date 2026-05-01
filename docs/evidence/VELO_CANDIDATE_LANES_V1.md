# VÉLØ Candidate Lanes V1

**Evidence basis:** Unified Evidence Audit V1 (49 days, 1391 sigma rows)
**Design date:** 2026-04-28 | **Last updated:** 2026-04-30
**Status:** PAPER_EXECUTION_LEDGER_ACTIVE — execution bridge live (SIM/PAPER only), annotation wiring pending

---

## Lane Status Summary

| Lane | Status | n | SR | Frame | Priority |
|---|---|---|---|---|---|
| VP30_TIER_A | SHADOW_CANDIDATE | 162 | 40.1% | 77.2% | 1 |
| MARKET_DECEPTION_HIGH | SHADOW_CANDIDATE | 31 | 54.8% | 96.8% | 2 |
| IMPROVEMENT_SCORE_HIGH | SHADOW_CANDIDATE | 62 | 43.5% | 82.3% | 3 |
| PLACE_PROB_HIGH | WATCHLIST | 392 | 31.6% | 66.8% | 4 |
| B_TIER_LOW_VP_SUPPRESS | SUPPRESS_CANDIDATE | 272 | 16.9% | 44.1% | 5 |
| MID_PRICE_WINNER_FORENSICS | FORENSICS_ONLY | — | —% | —% | 6 |

---

## Governance Principles

- No lane affects live routing without explicit operator approval
- Shadow ledger is append-only — never overwrite historical records
- Freeze conditions are automatic — once triggered, human review required to unfreeze
- Promotion gates require human sign-off at every step
- Evidence numbers must come from closed-result sigma_audits — no simulation
- ROI figures are research-only — no staking until n≥100 and explicit approval

## Signal Promotion Board — Evidence to Live Governance

Candidate lanes are not equal to live weights.
They are evidence lanes that must earn promotion through a formal board.

### Lane-to-signal truth

- `VP30_TIER_A`: evidence lane built on the live `VP / SQPE` core
- `MARKET_DECEPTION_HIGH`: maps to a signal that is already live-weighted via `market_deception_score`
- `IMPROVEMENT_SCORE_HIGH`: strong evidence lane, but the underlying `improvement_score` is still disabled in the live ensemble
- `PLACE_PROB_HIGH`: maps to a signal that is already live-weighted via `place_prob`
- `B_TIER_LOW_VP_SUPPRESS`: suppress lane, not a promotion lane
- `MID_PRICE_WINNER_FORENSICS`: forensics lane, not a probability driver

### Promotion doctrine

1. No lane graduates because the narrative is exciting.
2. No shadow lane becomes live-weighted without closed-result evidence, dedupe confirmation, and formal review.
3. `IMPROVEMENT_SCORE_HIGH` is the biggest current truth-gap lane:
   - evidence is strong
   - live weight is still zero
   - board decision is still pending
4. Router lanes and paper directives remain governance signals, not probability drivers.

## Lane Lifecycle

1. DESIGN → shadow annotation active (ledger tracking begins)
1. WATCHLIST → n≥20, SR positive, no freeze triggered
1. SHADOW_CANDIDATE → n≥30, SR≥baseline, Frame≥70%, positive ROI
1. PAPER_EXECUTION → n≥60, operator approves paper P&L tracking
1. LIVE_DISCUSSION → n≥100, multi-month evidence, operator reviews
1. LIVE_ACTIVATION → explicit operator decision, legal review, disclaimers

## Auto-Freeze Rules

- SR drops below global baseline (20.6%) at n≥20
- Frame drops below 50% at n≥20
- 7+ consecutive losses
- ROI below -20% at n≥30

**Unfreeze requires:** Human review of last 20 races + operator approval

---

## Highest Priority Lanes

### 1. VP30_TIER_A — Most Proven
- n=162, SR=40.1%, Frame=77.2% across 49 days
- This is the most evidence-backed lane in the system
- Ready for shadow ledger tracking immediately

### 2. MARKET_DECEPTION_HIGH — Highest Upside
- n=31, SR=54.8%, Frame=96.8%
- Exceptional numbers but small sample — must track for regression
- Highest lift (+34.2%) of any signal in the system

### 3. IMPROVEMENT_SCORE_HIGH — Strong and Growing
- n=62, SR=43.5%, Frame=82.3%
- Second-highest SR with meaningful sample
- Consistently strong across operating period

---

## Next Steps

1. Add shadow lane annotation fields to velo_verdicts or sigma_audits table
2. Wire VP30_TIER_A shadow flag to daily sigma output (annotation only, no routing change)
3. Wire MARKET_DECEPTION_HIGH shadow flag
4. Wire IMPROVEMENT_SCORE_HIGH shadow flag
5. Build shadow_lane_ledger.csv (separate from router_shadow_audit_ledger.csv)
6. Run 30 qualifying results through each lane before first review
7. No staking, no routing changes, no production impact

---

## Execution Bridge Integration (Phase 6 — 2026-04-29)

The VeloExecutionBridge maps VP30_TIER_A (and sub-signals) to ExecutionDirectives for paper tracking. Relationship to candidate lanes:

| Bridge Directive | Candidate Lane Overlap | Paper Ledger State |
|---|---|---|
| POWER_ANCHOR_MODE | VP30_TIER_A + candidate_execution_allowed | n=3, 2/2 closed wins |
| FAVOURITE_LIABILITY_MODE | MDS_HIGH + VP≥0.30 | n=0 (no lays tracked yet) |
| MULTI_THREAT_ZONE_MODE | IMPROVE_HIGH + VP≥0.30 | n=0 |
| WATCH_ONLY | VP≥0.30 gate not met | n=6, 1 win (no bet — gate working) |
| BLOCKED | Sub-threshold | n=29 |

The bridge does not replace candidate-lane annotation wiring — annotation in velo_verdicts/sigma_audits is still the pending step. The paper ledger is the evidence accumulation path; annotation wiring is the signal classification path.

---

*VÉLØ Oracle Prime — Candidate Lanes V1 | Paper execution active (SIM/PAPER only) | No live deployment*
