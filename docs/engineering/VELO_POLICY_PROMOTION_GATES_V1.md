# VÉLØ POLICY PROMOTION GATES V1

**Classification:** GOVERNANCE_PROTOCOL | NO_SCORING_CHANGE | OPERATOR_APPROVAL_REQUIRED
**Built:** 2026-05-17
**Purpose:** Hard promotion gates for moving any named signal lane from SHADOW to live policy

---

## What This Document Is

This document defines the minimum evidence requirements that must be met before any named signal
lane can be discussed as a live policy candidate. It does not define what happens after the gates
are passed — that is an operator decision.

Passing the gates opens the door to a conversation.
Passing the gates is not the conversation.
The conversation is not the decision.
The decision requires human approval.

**Nothing promotes automatically at any threshold.**

---

## Hard Promotion Gates

All 10 gates must be passed for a lane to be considered for live policy discussion.

### Gate 1 — Minimum Evidence

```
n >= 150 (minimum for shadow review)
n >= 250 (preferred before live policy vote)
```

A lane with n<150 has not survived enough race days to show seasonal variation.
Below n=150, sample variance can explain most of the SR/ROI signal.

**Current state (2026-05-17):**
- VP40_LANE: n=150 (minimum met, preferred not met)
- All other lanes: n<150 or n<50

### Gate 2 — SR Sustained

```
SR >= 40% across the full evidence window
No single month or 30-race sub-window showing SR < 30%
```

SR must hold across time, not just accumulate from early wins.

### Gate 3 — Frame Rate

```
Frame rate >= 75%
```

Frame rate (placed rate) is a proxy for model calibration. Below 75%, the model is producing
candidates that consistently under-perform on path proximity — the win signal may be partially
noise.

### Gate 4 — ROI Structural Stability

```
ROI >= 0% (positive flat stake)
ROI >= 0% when top 1 winner excluded from calculation
ROI >= 0% when top 2 winners excluded from calculation
```

This is the ROI strip test. A structurally sound edge survives removal of its best winners.
If ROI collapses to negative when the highest-SP winner is removed, the ROI is outlier-dependent,
not structural.

**Why this gate exists:** VP40_LANE passed the 7-gate report's ROI gate (gate 5) with +8.2% ROI.
But the forensic review found that ROI drops to -13.9% without a single SP=34 winner (Roysse).
That is not a structural edge. The 7-gate report does not test this — this gate 4 extension closes
that gap.

### Gate 5 — No Subgroup Collapse

```
No single course, class, or going subgroup shows:
  SR < lane_SR - 20pp
  at n >= 10
```

A structural edge must hold across track and class conditions. If Beverley or Class 5 is dragging
the average down at meaningful n, the edge is conditional — not broad enough for a policy lane.

### Gate 6 — Losing Run Risk Acceptable

```
Longest losing run (LLR) <= 15% of n
No single losing run exceeding 20 consecutive selections
```

Losing runs define the operator experience. An LLR of 15 at n=100 (15%) is hard to ride even
on paper. An LLR > 20 absolute is a psychological barrier that undermines consistency.

### Gate 7 — No Outlier Winner Concentration

```
Top 3 SP winners combined < 40% of total ROI
No single winner > 20% of total return
```

If three winners are generating more than 40% of the ROI, the lane is dependent on rare events.
That is variance, not edge. The policy must survive without those outliers.

**Calculation:** total_return = sum(winning_SPs). Winner contribution = winner_SP / total_return.

### Gate 8 — Sentinel Clear

```
SafetySentinel must return PASS or WARN (not BLOCK)
No forbidden files modified
No live state touched
```

The execution environment must be clean before any policy discussion can begin.

### Gate 9 — No Live State Mutation

```
candidate_route() unchanged
router lane masks unchanged
ensemble weights unchanged
scoring pipeline unchanged
staking config unchanged
Telegram format unchanged
Playbook G state unchanged
```

Policy discussion cannot happen while any live state is in transition.

### Gate 10 — Human Approval

```
Operator decision required at every gate
No automatic promotion
No automatic demotion
All policy changes require explicit approval documented in the session log
```

This gate never passes automatically. It requires a human to read the evidence and make a
deliberate choice.

---

## Gate Summary Table

| Gate | Condition | VP40 Status (2026-05-17) |
|---|---|---|
| Gate 1: Min evidence | n ≥ 150 / n ≥ 250 preferred | 150/250 — min met, preferred not |
| Gate 2: SR sustained | SR ≥ 40%, no 30-race window < 30% | 45.3% — PASS (temporal not yet tracked) |
| Gate 3: Frame | Frame ≥ 75% | 80.7% — PASS |
| Gate 4: ROI strip | ROI ≥ 0% ex top 1 and top 2 winners | -13.9% ex top 1 — **FAIL** |
| Gate 5: No subgroup | No course/class collapse at n≥10 | Beverley 0% at n=5 — monitor (n too small) |
| Gate 6: LLR | LLR ≤ 15% of n, no run > 20 | LLR=8 (5.3% of n) — PASS |
| Gate 7: Winner concentration | Top 3 < 40% of ROI, single < 20% | Roysse = ~50% of total return — **FAIL** |
| Gate 8: Sentinel | PASS or WARN only | WARN — PASS |
| Gate 9: No live mutation | All live state unchanged | UNTOUCHED — PASS |
| Gate 10: Human approval | Operator explicit decision | Not yet requested |

**VP40 current gate status: 2 critical failures (Gate 4 and Gate 7)**

---

## What Happens When All 10 Gates Pass

1. The operator reviews the gate report and forensic review
2. A shadow policy discussion is opened — what does the policy look like?
3. A shadow run is defined — what selections would have been made in the past 30/60/90 days?
4. The shadow run is reviewed before any live execution
5. If shadow run is acceptable, a controlled live trial is defined
6. The trial requires separate approval before execution begins
7. The trial runs with hard kill switches and automatic stop conditions

The earliest any lane can reach live policy trial is when:
- All 10 gates pass across at least two separate weekly evidence reviews
- Shadow run review is complete
- Controlled trial parameters are explicitly approved

---

## Stop Conditions (Apply to Any Lane Under Review)

These conditions trigger immediate demotion from SHADOW_POLICY_CANDIDATE:

```
SR drops > 5pp below reference at n >= 50 (per lane collapse thresholds)
ROI becomes negative at n >= 250 sustained over 30+ new results
LLR > 20 consecutive losses at any point
New subgroup collapse identified at n >= 15 (SR gap > 20pp)
ROI outlier dependency introduced (single winner > 20% of total return)
Sentinel returns BLOCK
Forbidden files modified
Live state touched without approval
```

---

## Named Lane Gate Progress (2026-05-17)

| Lane | n | G1 | G2 | G3 | G4 | G5 | G6 | G7 | Status |
|---|---|---|---|---|---|---|---|---|---|
| VP40_LANE | 150 | ½ | ? | ✅ | ❌ | ? | ✅ | ❌ | WATCH_ONLY |
| VP40_TIER_A_LANE | 132 | ½ | ? | ✅ | ? | ? | ? | ? | PROMISING |
| MDS_HIGH_LANE | 39 | ❌ | ❌ | ✅ | ? | ? | ✅ | ? | INSUFFICIENT_N |
| IMPROVER_LANE | 38 | ❌ | ❌ | ✅ | ? | ? | ✅ | ? | INSUFFICIENT_N |
| SHORTFAV_VP30 | 186 | ✅ | ✅ | ✅ | ? | ? | ? | ? | GATE_BLOCKED (ROI<0) |
| MIDPRICE_ROUTER_QUAL | 18 | ❌ | ❌ | ? | ? | ? | ? | ? | INSUFFICIENT_N |

*G1=n gate, G2=temporal SR, G3=frame, G4=ROI strip, G5=no subgroup, G6=LLR, G7=winner concentration*

---

## Governance

```
NO_SCORING_CHANGE at any gate
NO_MODEL_CHANGE at any gate
NO_ROUTER_CHANGE at any gate
NO_STAKING_CHANGE at any gate
NO_TELEGRAM_CHANGE at any gate
NO_PLAYBOOK_G_PROMOTION at any gate
NO_LIVE_STATE_MUTATION at any gate
ALL_PROMOTIONS_REQUIRE_HUMAN_APPROVAL
ALL_PROMOTIONS_REQUIRE_10_GATE_PASS
```

---

*VELO_POLICY_PROMOTION_GATES_V1 — 2026-05-17*
*Supersedes: 7-gate promotion gate report (adds gate 4 ROI strip and gate 7 winner concentration)*
*Next review: when any lane crosses n=250 or requests live policy discussion*
