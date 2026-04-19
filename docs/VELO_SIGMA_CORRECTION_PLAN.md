# VÉLØ Sigma Correction Plan

**Revision:** 2026-04-19.01 | **Source:** 1,107-Race Forensic Audit

This plan defines the structural corrections required to close the 408-race leak identified in the 1000-race audit.

---

## 1. The Critical Failure Taxonomy

| Failure Class | Count | Severity | Recoverability | Danger |
|---|---|---|---|---|
| **Mid-Priced Omitted (5-20)** | 241 | CRITICAL | HIGH | High |
| **Market Decoy Followed** | 167 | HIGH | MEDIUM | High |
| **Outsider Won (Blind Spot)** | 90 | MEDIUM | LOW | Low |
| **Short-Fav Trap** | 66 | MEDIUM | MEDIUM | Medium |

---

## 2. Priority Correction Ladder

1. **[FIRST ORDER] A-Tier Fortress Protection:** Hard-gate all execution to A-tier sub-3.0 ($60.3\%$ strike) while price discovery matures.
2. **[FIRST ORDER] AW Decoy Containment:** Implement a 0.85x confidence penalty for all AW races showing high volatility in the final 5 minutes before off.
3. **[SECOND ORDER] Mid-Price Sensitivity:** Refine the `prob_gap` requirement for the 5-20 SP zone. No bets unless `prob_gap > 0.12`.
4. **[SECOND ORDER] Rank-2 Vision:** Surface the 2nd-ranked horse as a "SLA Hedge" when the price is $> 8.0$ and Rank-1 confidence is < HIGH.

---

## 3. The "Eureka" Edge
**A-Tier + High Confidence + Sub-3.0 SP = 60.3% Win Rate.**
This is not a statistic; it is a law. We will treat this lane as the "Gold Standard" for all future betting readiness gates.
