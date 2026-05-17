# VÉLØ 2K Sigma Training Recommendation Packet

**Classification:** SIGMA_2K_TRAINING_PLAN_READY | SHADOW_POLICY_CANDIDATES_ONLY | MIDPRICE_SUPPRESSION_ADVISORY_ONLY | MDS_HIGH_LANE_CONFIRMED | IMPROVER_LANE_CONFIRMED | CASHRUN_DIAGNOSTIC_ONLY | ROUTER_GATE_CONFIRMED | NO_SCORING_CHANGE
**Built:** 2026-05-17
**Evidence base:** 721 labelled rows | 67+ race days | schema sigma_2k_v1

---

## Preamble

This packet is the product of the 2K Sigma council stack. It summarises what the evidence says and what the approved next steps are. It does not change anything. It recommends.

The corpus is VÉLØ's own prediction history, closed by reality. It answers questions no external dataset can: where is VÉLØ genuinely strong, where is it blind, and where is it making confident noise.

---

## 1. What Should Remain Unchanged

### Scoring and model weights
**Status: NO_SCORING_CHANGE**

The ensemble weights (SQPE v17=0.45, improvement=0.12, MDS=0.10) remain unchanged.
No evidence in this corpus justifies weight modification. The evidence identifies *where* signals fire reliably, not that the weights are miscalibrated.

The existing weights were validated in Ensemble Surgery v1 (commit b7e4e0c) with a clear ROI improvement (+13.5% vs -3.1% legacy). That finding stands.

### Router lane rules
**Status: ROUTER_GATE_CONFIRMED — rules unchanged**

V1/V2/V6 lane thresholds and qualification logic are not modified. The corpus confirms they work. Do not over-tune what is working.

### Telegram format
**Status: LOCKED — no change**

### Playbook G directives
**Status: NO_PROMOTION — no change**

### Live state
**Status: UNTOUCHED**

---

## 2. What Should Become Advisory

### Midprice router suppression advisory
**Status: MIDPRICE_SUPPRESSION_ADVISORY_ONLY**

Evidence: SP 3.0–8.5 zone runs at SR=15.5% (n=317), -5.9pp below global baseline. VP/MDS/improvement produce near-zero signal separation in this zone. Router-qualified mid-price selections run at 38–60% SR; unqualified at 14.5%.

Suppression audit: 261 suppressed, 5.2:1 loser:winner ratio, +2.3pp SR delta, -0.6pp frame delta.

Gates passed: 3/4. Frame gate not yet cleared.

**Advisory only until frame gate passes in next cycle.**

Operational flag: `midprice_router_suppression_advisory` — active in Mission Control.

### VP>=0.30 + Midprice Suppress combined filter
**Status: ADVISORY_ONLY → WATCH for shadow policy promotion**

Ablation result: VP>=0.30 + midprice suppression = SR 39.6%, n=139, +19.9pp vs global.
This is the clearest result in the ablation audit. Coverage 66% — not a niche filter.

Track for one full cycle (20+ qualifying results) before shadow policy promotion.

### Compression archetype
**Status: SUPPRESS_CONFIRMED — advisory suppression active**

SR=14.3% globally (-7.1pp). In mid-price: confirmed dead money without MDS/VP/improvement support. This is the advisory suppression finding from the Council Stack Closure.

---

## 3. What Should Be Suppressed

Based on regime audit (721 rows, classifications SUPPRESS):

| Regime | SR | n | Evidence |
|---|---|---|---|
| VP < 0.20 | 13.7% | 249 | SUPPRESS — 34.6pp below the PROVEN zone |
| Tier C | 13.8% | 167 | SUPPRESS — advisory confirmed |
| B-tier VP < 0.30 | 13.4% | 209 | SUPPRESS — drag confirmed |
| Midprice + No Router | 14.5% | 304 | SUPPRESS — advisory active |
| SP 8.5–16.0 | 7.1% | 126 | SUPPRESS — outsider zone bleeding |
| SP > 16.0 | 3.2% | 95 | SUPPRESS — longshot zone: extreme bleeding |

**These are advisory suppression findings. They do not change scores or selections automatically. They inform operator awareness and Mission Control readout.**

---

## 4. What Deserves Shadow Policy Testing

Based on ablation audit (shadow policy candidates, all n ≥ 20):

### MDS_HIGH_LANE
**Classification: MDS_HIGH_LANE_CONFIRMED**

VP>=0.30 + MDS>0.50: SR=66.7%, n=21, +47pp above global.
At n=56 in full unified audit: SR=62.5%, Frame=94.6%.

This lane performs consistently across both corpus views. It needs a dedicated shadow tracking lane — not automatic selection, but operator priority and daily visibility.

**Build: `MDS_HIGH_LANE` as named shadow lane in router shadow audit.**

### IMPROVER_LANE
**Classification: IMPROVER_LANE_CONFIRMED**

VP>=0.30 + IMP>0.40: SR=50.0%, n=22, +30pp above global.
At n=92 in full unified audit: SR=41.3%, Frame=78.3%.

Consistent across both corpus views. Markets and public money lag genuine improvement. VÉLØ's improvement engine is catching real forward movement.

**Build: `IMPROVER_LANE` as named shadow lane in router shadow audit.**

### VP>=0.40 + TierA
**Classification: SHADOW_POLICY_CANDIDATE**

SR=44.8%, n=67, +25pp above global. This is not a small-sample finding.

**Build: Track as standalone reporting lane in Mission Control.**

### VP>=0.30 + Router (full lane)
**Classification: SHADOW_POLICY_CANDIDATE**

SR=37.0%, n=27, +17pp above global. Already tracked as V1/V2/V6 lanes individually.

### VP>=0.30 + Midprice Suppress
**Classification: SHADOW_POLICY_CANDIDATE — one cycle before review**

SR=39.6%, n=139, +20pp above global. Largest sample among shadow candidates. Clearest result in ablation. Track for 20+ qualifying results in next cycle.

---

## 5. What Deserves Model-Weight Review Later

**Current ruling: nothing.**

No finding in this corpus justifies weight review at this time. The conditions for model-weight review are:

1. n ≥ 200 qualifying results with consistent SR lift ≥ +3pp sustained over 20+ days
2. Consistent across ≥ 3 VP/MDS/SP regime partitions
3. No contradicting evidence in ablation audit
4. Separate `SIGMA_RETRAINING_APPROVAL_V1` governance doc created and reviewed by operator

None of these conditions are met. The corpus is at 721 rows. Continue accumulating. The earliest model-weight discussion is possible at ~1500+ rows with the above conditions met.

---

## 6. What Needs More Data

| Signal | Current n | Minimum n | Status |
|---|---|---|---|
| MDS>0.50 + IMP>0.40 | 11 | 50 | NEEDS_MORE_DATA |
| MDS>0.50 + Router | 1 | 20 | NEEDS_MORE_DATA |
| VP>=0.30 + Router + TierA | 13 | 20 | NEEDS_MORE_DATA |
| Full stack combo | 5 | 20 | NEEDS_MORE_DATA |
| V6_GOLD_SEAM overall | 10 | 20 | NEEDS_MORE_DATA |
| RPDC release score | 54 (full audit) | 100 | NEEDS_MORE_DATA |
| CASHRUN as standalone | varies | 100 | CASHRUN_DIAGNOSTIC_ONLY |

CASHRUN is a diagnostic and operator-facing tool, not a model input. Its performance as a standalone predictor is not the right question. The right question is: does CASHRUN filter within VP>=0.30 populations improve SR? That requires dedicated study once n≥100 in that overlap.

---

## 7. What Is Unsafe to Promote

| Candidate | Why Unsafe |
|---|---|
| Any scoring change | No evidence justifies weight change at this corpus size |
| Live suppression rules | Frame gate not cleared; advisory only |
| Automatic Tier C exclusion | Would remove 167 rows; some C-tier with VP>=0.30 still performs |
| SP>8.5 automatic exclusion | Would remove 47% of corpus; too aggressive |
| MDS>0.50 as single gate | n=21/56 — sample too small for standalone policy |
| B-tier automatic suppression | VP>=0.30 B-tier is still KEEP (SR=30.0%, n=130) |
| Router promotion to paper execution | POWER_ANCHOR n=3 — far from n=20 first review |

---

## Final Classifications

```
NO_SCORING_CHANGE             — all ensemble weights unchanged
SHADOW_POLICY_CANDIDATES_ONLY — MDS_HIGH, IMPROVER, VP40+TierA, VP30+Midprice
MIDPRICE_SUPPRESSION_ADVISORY_ONLY — advisory active, 3/4 gates passed
MDS_HIGH_LANE_CONFIRMED       — SR=62.5-66.7%, build dedicated shadow lane
IMPROVER_LANE_CONFIRMED       — SR=41.3-50.0%, build dedicated shadow lane
CASHRUN_DIAGNOSTIC_ONLY       — operator-facing, not model input
ROUTER_GATE_CONFIRMED         — V1/V2/V6 proven, rules unchanged
```

---

## Next Build Queue (in priority order)

1. `MDS_HIGH_LANE` — shadow tracking lane in router audit
2. `IMPROVER_LANE` — shadow tracking lane in router audit
3. `VP>=0.30 + Midprice Suppress` — one cycle tracking before shadow policy vote
4. Mission Control UI — surface regime readout visually
5. `sigma_2k_midprice_cycle2_audit.py` — second cycle check after frame gate
6. Accumulate to 1500+ rows — do not rush retraining discussion

---

*VELO_2K_SIGMA_TRAINING_RECOMMENDATION_PACKET — 2026-05-17*
*This is not retraining for excitement. This is forensic self-knowledge.*
