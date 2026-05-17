# VP40_TIER_A SHADOW POLICY REVIEW V1

**Classification:** POLICY_SIMULATION_ONLY | NO_SCORING_CHANGE | WATCH_ONLY
**Built:** 2026-05-17
**Verdict: WATCH_ONLY — same critical failures as VP40_LANE**
**Evidence base:** SIGMA_2K_SAFE_TRAINING_SLICE_V1 — 1310 rows, VP40_TIER_A n=132

---

## Why VP40_TIER_A Was Reviewed

VP40_LANE passed 7/7 promotion gates but the forensic review found two critical blockers:
1. ROI depends entirely on a single SP=34 winner (Roysse)
2. SP 3.0–8.5 band is a confirmed drain (SR=17.8%, ROI=-18.9%)

The hypothesis was: **restricting to Tier A horses would remove the outlier and clean the SP band.**

Both hypotheses were tested. Both failed.

---

## Lane Definition

```
VP40_TIER_A_LANE: VP >= 0.40 AND decision_tier == 'A'
```

This is the same as VP40_LANE with an additional Tier A filter.
Tier A = VÉLØ's highest-confidence tier (VP≥0.30 zone, cleanest signal).

---

## Why Full VP40_LANE Failed

VP40_LANE (n=150) passed the 7/7 gate report and entered shadow policy review.
The forensic layer found:

```
ROI with Roysse:     +8.2%
ROI without Roysse: -13.9%
```

Roysse (SP=34.0) is a single SP=34 longshot in a 150-row corpus. One horse.
Without that one result, VP40 is a losing lane. That is not a structural edge.

Additionally, the SP 3.0–8.5 zone runs at SR=17.8%, ROI=-18.9% at n=45 within VP40_LANE.
The mid-price band is behaving like the known drain zone, not like a qualified VP40 signal.

---

## The Tier A Test: Does It Fix the Problems?

### Test 1: Does Tier A remove Roysse?

**Answer: No.**

Roysse is Tier A. Confirmed directly from the training corpus:

```
Roysse — date=2026-05-16, VP=0.416, decision_tier=A, SP=34.0, won=True
```

Roysse satisfies both the VP≥0.40 and Tier A conditions.
Restricting to Tier A does not remove the outlier. Both lanes are equally dependent on Roysse.

### Test 2: Does Tier A clean the SP 3.0–8.5 drain?

**Answer: No — drain persists.**

```
VP40_LANE + SP3.0-8.5:        n=45   SR=17.8%   ROI=-18.9%
VP40_TIER_A + SP3.0-8.5:      n=37   SR=16.2%   ROI=-23.0%
```

Tier A slightly reduces the n in the drain zone (45 → 37) but SR and ROI are worse, not better.
The drain is an SP band issue, not a tier issue. Tier A filtering does not address it.

---

## VP40_TIER_A Full Results

```
n=132    SR=44.7%    Frame=80.3%    ROI=+9.4%
Longest losing run (LLR): 7
Max drawdown (flat £1): £17.05
```

Marginally higher ROI than VP40_LANE (+9.4% vs +8.2%), marginally lower SR (44.7% vs 45.3%).
The difference is driven by removing 18 Tier B/C/X rows, not by a structural improvement.

---

## 10-Gate Assessment

| Gate | Condition | VP40_TIER_A Status |
|---|---|---|
| Gate 1: Min evidence | n ≥ 150 / n ≥ 250 preferred | n=132 — min NOT met, preferred not met |
| Gate 2: SR sustained | SR ≥ 40%, no 30-race window < 30% | 44.7% — PASS (temporal not tracked) |
| Gate 3: Frame | Frame ≥ 75% | 80.3% — PASS |
| Gate 4: ROI strip | ROI ≥ 0% ex top 1 and top 2 winners | -15.7% ex Roysse — **FAIL** |
| Gate 5: No subgroup | No course/class collapse at n≥10 | All class 4 — monitor |
| Gate 6: LLR | LLR ≤ 15% of n, no run > 20 | LLR=7 (5.3% of n) — PASS |
| Gate 7: Winner concentration | Top 3 < 40% of ROI, single < 20% | Roysse > 50% of total return — **FAIL** |
| Gate 8: Sentinel | PASS or WARN only | WARN — PASS |
| Gate 9: No live mutation | All live state unchanged | UNTOUCHED — PASS |
| Gate 10: Human approval | Operator explicit decision | Not yet requested |

**VP40_TIER_A gate status: 2 critical failures (Gate 4 and Gate 7) — same as VP40_LANE**

---

## ROI Strip Test

Remove the highest-SP winners one at a time:

| Removed | Horse | SP | ROI Remaining |
|---|---|---|---|
| Full VP40_TIER_A | — | — | +9.4% |
| Remove top 1 | Roysse | 34.0 | **-15.7%** |
| Remove top 2 | Pageant Girl | 8.0 | -20.0% |
| Remove top 3 | Braganza Bay | 5.5 | -22.8% |

ROI collapses immediately on removing Roysse. This is an outlier-dependent ROI profile.
The verdict is the same as VP40_LANE: **Gate 4 FAIL**.

---

## SP Band Truth (VP40_TIER_A-specific)

| SP Band | n | SR | Frame | ROI | Verdict |
|---|---|---|---|---|---|
| SP<2.0 | 57 | 70.2% | — | -4.2% | HIGH SR, ROI compressed |
| SP2.0-2.99 | 24 | 45.8% | — | +3.6% | HEALTHIEST ZONE |
| SP3.0-8.5 | 37 | 16.2% | — | -23.0% | CONFIRMED DRAIN |
| SP8.51-16.0 | 8 | 0.0% | — | -100% | DEAD ZONE |
| SP>16.0 | 6 | 16.7% | — | +516% | OUTLIER (Roysse effect) |

Pattern is identical to VP40_LANE. The drain zones are structural, not tier-related.

---

## The NO_MIDPRICE Simulation

Removing the SP3.0-8.5 drain zone from VP40_TIER_A reveals the underlying signal:

```
VP40_TIER_A + (SP<3.0 OR SP>8.5)
n=94    SR=55.3%    Frame=84.0%    ROI=+23.3%
```

This is a strong simulation result. However:
- n=94 includes Roysse (SP=34 is in SP>8.5, not excluded)
- A strip test on this filtered set is required before this becomes a candidate
- n=94 is below the n=150 minimum gate

**This simulation points toward a future named lane:**
```
VP40_TIER_A_SHORTPRICE (VP>=0.40 AND Tier A AND SP<3.0 OR SP>16.0)
```
Not yet trackable — needs n≥50 in the restricted sub-lane.

---

## VP40_TIER_A vs VP40_LANE Comparison

| Metric | VP40_LANE | VP40_TIER_A | Delta |
|---|---|---|---|
| n | 150 | 132 | 18 removed (88% retained) |
| SR | 45.3% | 44.7% | -0.6pp |
| Frame | 80.7% | 80.3% | -0.4pp |
| ROI | +8.2% | +9.4% | +1.2pp |
| ROI ex-Roysse | -13.9% | -15.7% | worse |
| Midprice n (SP3-8.5) | 45 | 37 | 8 fewer |
| Midprice SR | 17.8% | 16.2% | worse |
| Midprice ROI | -18.9% | -23.0% | worse |

**Verdict: VP40_TIER_A is marginally different, not materially safer.**
Both lanes fail the same critical gates for the same reasons.

---

## Overlap Analysis

88% of VP40_LANE rows (132/150) are also VP40_TIER_A_LANE.
The 18-row difference is Tier B/C/X at VP≥0.40 — low evidence value.

Of VP40_LANE's 68 winners:
- 59 are Tier A (in VP40_TIER_A)
- 9 are non-Tier-A (removed by Tier A filter)

The 9 removed winners were net positive contributors. Removing them slightly lowers SR,
slightly increases ROI (removed losers outnumber removed winners in the Tier B/C/X rows).

---

## The Real Finding: Where the Edge Lives

The evidence across both lanes consistently points to:

```
1. SP < 3.0 (especially SP 2.0–2.99)
   n=24  SR=45.8%  ROI=+3.6%  (within VP40_TIER_A)
   This is the structural zone — consistent SR, positive ROI, no outlier dependency

2. SP 3.0–8.5 is the enemy
   n=37  SR=16.2%  ROI=-23.0%  (within VP40_TIER_A)
   Behaves identically to MIDPRICE_SUPPRESS — the VP40 filter does not qualify these horses

3. SP>8.5 is outlier territory
   n=6   SR=16.7%  ROI=+516%   (Roysse effect)
   One or two extreme SP winners distort the entire corpus ROI
```

The genuine edge in VP40_TIER_A is the SP<3.0 zone, particularly SP 2.0–2.99.

---

## Promotion Requirements

All of the following must be true before any promotion discussion:

```
1. n >= 250 (current: 132 — needs +118 more results)
2. ROI >= 0% when top winner excluded (current: fails at -15.7%)
3. SP band drain resolved:
   Either restrict VP40_TIER_A to SP<3.0 (removing the drain)
   Or wait for the drain zone to self-correct as n grows
4. No severe course/class collapse at n>=10
5. Sentinel PASS or WARN (not BLOCK)
6. Human approval at operator council — no automatic promotion
```

---

## Stop Conditions

If VP40_TIER_A_LANE crosses any of these at n>=150, trigger a council review:

```
SR < 40% at n >= 150
Frame < 70% at n >= 150
ROI < -5% at n >= 150 (sustained negative)
LLR > 20% of n
New subgroup collapse at n >= 10 (SR gap > 20pp)
Outlier dependency worsens (single winner > 60% of total return)
```

---

## Path Forward

```
1. Neither VP40_LANE nor VP40_TIER_A is promotable at n=132-150.
   Both fail Gate 4 (ROI strip) and Gate 7 (winner concentration).

2. Wait for n >= 250. At n=250, Roysse's contribution dilutes naturally
   as more results accumulate.

3. Consider naming a new candidate lane at n>=50:
   VP40_TIER_A_SHORTPRICE (VP>=0.40 AND Tier A AND SP<3.0)
   Current n in this sub-lane: ~85 within VP40_TIER_A at SP<3.0
   Run strip test on this sub-lane before declaring it a candidate.

4. Re-run both policy reviews at n=200 and n=250 as milestones.
   The automated scripts handle this: run vp40_shadow_policy_review.py
   and vp40_tier_a_shadow_policy_review.py then vp40_lane_comparison.py.
```

---

## No Live Promotion Rule

```
NOTHING IN THIS DOCUMENT AUTHORISES ANY LIVE ACTION.

Neither VP40_LANE nor VP40_TIER_A is a live policy.
Neither lane has any connection to:
  - candidate_route() in the scoring pipeline
  - router lane masks
  - ensemble weights
  - staking configuration
  - Telegram output format
  - Playbook G directives

Policy simulation findings are advisory only.
They inform future discussion.
They do not trigger any action.
All policy changes require explicit human approval
with documented evidence and operator council sign-off.
```

---

## Governance

```
NO_SCORING_CHANGE
NO_MODEL_CHANGE
NO_ROUTER_CHANGE
NO_STAKING_CHANGE
NO_TELEGRAM_CHANGE
NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION
POLICY_SIMULATION_ONLY
WATCH_ONLY
```

---

*VP40_TIER_A_SHADOW_POLICY_REVIEW_V1 — 2026-05-17*
*Evidence base: SIGMA_2K_SAFE_TRAINING_SLICE_V1 at 1310 rows, VP40_TIER_A n=132*
*Next review: when n >= 200 or n >= 250 OR VP40_TIER_A_SHORTPRICE sub-lane reaches n>=50*
