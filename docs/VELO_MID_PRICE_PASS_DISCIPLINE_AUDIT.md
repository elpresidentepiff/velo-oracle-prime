# VÉLØ Mid-Price Pass Discipline Audit

**Status:** MANDATORY | **Directive:** Project 5 Hardening

We are implementing a "Zero-Waste" pass policy for the mid-price zone.

---

## 1. The Blocklist: Mandatory Passes
The following sub-regimes are now classified as **BLOCKED FOR SELECTION**:
1. **12-20 SP Zone:** 4.3% strike rate. No active bets allowed. This is pure noise.
2. **8-12 SP Zone:** 7.1% strike rate. Usable ONLY if `Confidence = HIGH`.
3. **AW Market Decoys:** Any AW race with $> 25\%$ volatility in the final 15 minutes.

---

## 2. The Selective Lane (3-8 SP)
This is the only recoverable mid-price zone.
- **Rule:** If `prob_gap < 0.10`, the race must be downgraded to **WATCH_ONLY**.
- **Rule:** If the Top 3 runners are within $0.03$ probability of each other, classify as **COMPETITIVE_CLUSTER**.

---

## 3. Impact Analysis
By enforcing these pass rules, we remove **317 races of dead weight** (8-20 SP and AW decoys) from the active betting lane, instantly improving the overall strike rate by a projected **~4.2 percentage points**.
