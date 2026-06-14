# NAMED LANE PROMOTION GATE REPORT
**Date:** 2026-05-17
**Run:** 2026-05-17 13:44 UTC

7-gate promotion gate analysis. Advisory only. No automatic promotion.
All promotions are operator decisions.

---

## Summary

| Lane | n | SR | Gates | Verdict |
|---|---|---|---|---|
| MDS_HIGH_LANE | 39 | 69.2% | 4/7 | **INSUFFICIENT_N** |
| IMPROVER_LANE | 38 | 42.1% | 4/7 | **INSUFFICIENT_N** |
| VP40_TIER_A_LANE | 132 | 44.7% | 6/7 | **GATE_BLOCKED** |
| VP40_LANE | 150 | 45.3% | 7/7 | **SHADOW_POLICY_CANDIDATE** |
| SHORTFAV_VP30 | 186 | 52.2% | 6/7 | **GATE_BLOCKED** |
| MIDPRICE_ROUTER_QUAL | 18 | 33.3% | 3/7 | **INSUFFICIENT_N** |
| MIDPRICE_SUPPRESS | 545 | 16.0% | 4/7 | **GATE_BLOCKED** |
| LONGSHOT_SUPPRESS | 413 | 6.3% | 4/7 | **GATE_BLOCKED** |

## MDS_HIGH_LANE

**Verdict: INSUFFICIENT_N**
*Accumulate +11 more results to n=50*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ❌ FAIL | 39 | 50 |
| Serious review n≥100 | ❌ FAIL | 39 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ✅ PASS | 69.2 | 35.0 |
| Frame rate ≥70.0% | ✅ PASS | 92.3 | 70.0 |
| ROI not negative | ❌ FAIL | -7.2 | 0.0 |
| LLR ≤25% of n | ✅ PASS | 7.7 | 25.0 |
| No subgroup collapse | ✅ PASS | 0 | 0 |

*No subgroup collapses detected.*

## IMPROVER_LANE

**Verdict: INSUFFICIENT_N**
*Accumulate +12 more results to n=50*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ❌ FAIL | 38 | 50 |
| Serious review n≥100 | ❌ FAIL | 38 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ✅ PASS | 42.1 | 35.0 |
| Frame rate ≥70.0% | ✅ PASS | 76.3 | 70.0 |
| ROI not negative | ❌ FAIL | -36.3 | 0.0 |
| LLR ≤25% of n | ✅ PASS | 21.1 | 25.0 |
| No subgroup collapse | ✅ PASS | 0 | 0 |

*No subgroup collapses detected.*

## VP40_TIER_A_LANE

**Verdict: GATE_BLOCKED**
*Blocked by: Gate 7: No subgroup collapse*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ✅ PASS | 132 | 50 |
| Serious review n≥100 | ✅ PASS | 132 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ✅ PASS | 44.7 | 35.0 |
| Frame rate ≥70.0% | ✅ PASS | 80.3 | 70.0 |
| ROI not negative | ✅ PASS | 9.4 | 0.0 |
| LLR ≤25% of n | ✅ PASS | 5.3 | 25.0 |
| No subgroup collapse | ❌ FAIL | 1 | 0 |

**Subgroup collapses detected:**

- Class 4: SR=22.7% at n=22 (gap=22.0pp below lane SR)

## VP40_LANE

**Verdict: SHADOW_POLICY_CANDIDATE**
*All gates passed — operator promotion discussion required*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ✅ PASS | 150 | 50 |
| Serious review n≥100 | ✅ PASS | 150 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ✅ PASS | 45.3 | 35.0 |
| Frame rate ≥70.0% | ✅ PASS | 80.7 | 70.0 |
| ROI not negative | ✅ PASS | 8.2 | 0.0 |
| LLR ≤25% of n | ✅ PASS | 5.3 | 25.0 |
| No subgroup collapse | ✅ PASS | 0 | 0 |

*No subgroup collapses detected.*

## SHORTFAV_VP30

**Verdict: GATE_BLOCKED**
*Blocked by: Gate 5: ROI not negative*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ✅ PASS | 186 | 50 |
| Serious review n≥100 | ✅ PASS | 186 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ✅ PASS | 52.2 | 35.0 |
| Frame rate ≥70.0% | ✅ PASS | 84.9 | 70.0 |
| ROI not negative | ❌ FAIL | -9.5 | 0.0 |
| LLR ≤25% of n | ✅ PASS | 3.8 | 25.0 |
| No subgroup collapse | ✅ PASS | 0 | 0 |

*No subgroup collapses detected.*

## MIDPRICE_ROUTER_QUAL

**Verdict: INSUFFICIENT_N**
*Accumulate +32 more results to n=50*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ❌ FAIL | 18 | 50 |
| Serious review n≥100 | ❌ FAIL | 18 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ❌ FAIL | 33.3 | 35.0 |
| Frame rate ≥70.0% | ✅ PASS | 72.2 | 70.0 |
| ROI not negative | ✅ PASS | 12.5 | 0.0 |
| LLR ≤25% of n | ❌ FAIL | 38.9 | 25.0 |
| No subgroup collapse | ✅ PASS | 0 | 0 |

*No subgroup collapses detected.*

## MIDPRICE_SUPPRESS

**Verdict: GATE_BLOCKED**
*Blocked by: Gate 3: SR lift ≥15.0pp over 20.0% baseline; Gate 4: Frame rate ≥70.0%; Gate 5: ROI not negative*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ✅ PASS | 545 | 50 |
| Serious review n≥100 | ✅ PASS | 545 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ❌ FAIL | 16.0 | 35.0 |
| Frame rate ≥70.0% | ❌ FAIL | 52.1 | 70.0 |
| ROI not negative | ❌ FAIL | -23.1 | 0.0 |
| LLR ≤25% of n | ✅ PASS | 6.8 | 25.0 |
| No subgroup collapse | ✅ PASS | 0 | 0 |

*No subgroup collapses detected.*

## LONGSHOT_SUPPRESS

**Verdict: GATE_BLOCKED**
*Blocked by: Gate 3: SR lift ≥15.0pp over 20.0% baseline; Gate 4: Frame rate ≥70.0%; Gate 5: ROI not negative*

| Gate | Pass | Value | Required |
|---|---|---|---|
| Min evidence n≥50 | ✅ PASS | 413 | 50 |
| Serious review n≥100 | ✅ PASS | 413 | 100 |
| SR lift ≥15.0pp over 20.0% baseline | ❌ FAIL | 6.3 | 35.0 |
| Frame rate ≥70.0% | ❌ FAIL | 24.5 | 70.0 |
| ROI not negative | ❌ FAIL | -11.7 | 0.0 |
| LLR ≤25% of n | ✅ PASS | 15.7 | 25.0 |
| No subgroup collapse | ✅ PASS | 0 | 0 |

*No subgroup collapses detected.*

---

## Promotion Gate Definitions

| Gate | Condition | Rationale |
|---|---|---|
| Gate 1 | n ≥ 50 | Minimum viable evidence |
| Gate 2 | n ≥ 100 | Serious policy review threshold |
| Gate 3 | SR ≥ 35% (15pp above 20% baseline) | Material SR lift confirmed |
| Gate 4 | Frame rate ≥ 70% | Frame coverage healthy |
| Gate 5 | ROI ≥ 0% | Not losing money flat-stake |
| Gate 6 | LLR ≤ 25% of n | Losing-run risk acceptable |
| Gate 7 | No subgroup collapse | No class/course collapses (SR gap > 20pp at n≥10) |

All 7 gates must pass for SHADOW_POLICY_CANDIDATE verdict.
Promotions are operator decisions only — no gate triggers automatic change.

---

## Governance

```
NO_SCORING_CHANGE | NO_MODEL_CHANGE | NO_ROUTER_CHANGE
NO_STAKING_CHANGE | NO_TELEGRAM_CHANGE | NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION | ADVISORY_TRACKING_ONLY
```

*NAMED_LANE_PROMOTION_GATE_REPORT_V1 — advisory only, no execution impact*