# VP40 SHADOW POLICY REVIEW V1

**Classification:** POLICY_SIMULATION_ONLY | NO_SCORING_CHANGE | WATCH_ONLY
**Built:** 2026-05-17
**Verdict: WATCH_ONLY — do not promote yet**
**Evidence base:** SIGMA_2K_SAFE_TRAINING_SLICE_V1 — 1310 rows, VP40 n=150

---

## Why VP40 Is the First Candidate

VP40_LANE was the first named signal lane to clear all 7 promotion gates:

```
n=150    SR=45.3%    Frame=80.7%    ROI=+8.2%
Gate 1 (n≥50): PASS
Gate 2 (n≥100): PASS
Gate 3 (SR lift ≥15pp): PASS
Gate 4 (Frame ≥70%): PASS
Gate 5 (ROI ≥0): PASS
Gate 6 (LLR ≤25% of n): PASS
Gate 7 (No subgroup collapse): PASS
→ Verdict: SHADOW_POLICY_CANDIDATE
```

This is the strongest evidence footprint of any named lane.
That is why VP40 entered shadow policy review before MDS_HIGH or IMPROVER.

---

## What 7/7 Gates Means

It means the evidence is sufficient to begin a policy discussion.

It does not mean:
```
❌ VP40 is ready for live policy
❌ VP40 scoring changes
❌ VP40 staking changes
❌ VP40 router rule changes
❌ VP40 Telegram output changes
❌ Any live state mutation
```

7/7 gates is a gate to enter the review room. It is not a promotion.

---

## Why This Is Still Not Live Promotion

The forensic review found two critical blockers:

### Blocker 1: ROI Outlier Dependency

VP40_LANE ROI of +8.2% depends materially on a single high-SP winner:

```
Roysse SP=34.0  VP=0.416  (longest-shot VP40 winner in corpus)

ROI with Roysse:     +8.2%
ROI without Roysse: -13.9%
```

A single SP=34 winner in a 150-row corpus is a one-race event. It is not a structural edge.
The reported ROI of +8.2% is partially synthetic.

If Roysse had finished second, VP40_LANE would be ROI=-13.9% and would have failed gate 5.
A gate-5 pass that relies on one race is not evidence of a structural edge.

### Blocker 2: Mid-Price Contamination

Within VP40_LANE, the SP 3.0–8.5 band is a confirmed drain:

```
VP40 + SP3.0–8.5:  n=45    SR=17.8%    ROI=-18.9%
VP40 + SP<2.0:     n=65    SR=67.7%    ROI=-3.3%    (high SR but short prices limit ROI)
VP40 + SP2.0-2.99: n=28    SR=46.4%    ROI=+3.4%    (healthy)
VP40 + SP8.51-16+: n=10    SR=0.0%     ROI=-100%    (dead zone)
```

The mid-price VP40 zone (SP 3.0–8.5) runs at SR=17.8% — below the MIDPRICE_SUPPRESS benchmark of 16.0% by only 1.8pp. This means VP40 in the mid-price zone is behaving like un-qualified mid-price, not like a genuine high-probability selection.

The SP<3.0 zone (n=93, SR=61.3%) is where the genuine edge lives, but ROI there is -1.3% (short prices compress ROI even at high SR).

---

## SP Band Truth (VP40-specific)

| SP Band | n | SR | Frame | ROI | Verdict |
|---|---|---|---|---|---|
| SP<2.0 | 65 | 67.7% | — | -3.3% | HIGH SR, ROI compressed by odds |
| SP2.0-2.99 | 28 | 46.4% | — | +3.4% | HEALTHIEST ZONE |
| SP3.0-8.5 | 45 | 17.8% | — | -18.9% | CONFIRMED DRAIN |
| SP8.51-16.0 | 8 | 0.0% | — | -100% | DEAD ZONE |
| SP>16.0 | 2 | 50.0% | — | +1600% | OUTLIER (Roysse effect) |

**The real edge in VP40_LANE is SP2.0-2.99 (n=28, SR=46.4%, ROI=+3.4%).**
The corpus-wide ROI of +8.2% is driven by two outlier winners in the SP>16 band.

---

## ROI Strip Test

Remove the highest-SP winners one by one to check ROI stability:

| Removed | Horse | SP | ROI Remaining |
|---|---|---|---|
| Full VP40 | — | — | +8.2% |
| Remove top 1 | Roysse | 34.0 | **-13.9%** |
| Remove top 2 | Pageant Girl | 8.0 | -18.7% |
| Remove top 3 | Braganza Bay | 5.5 | -21.9% |

ROI collapses immediately on removing one winner. This is an **outlier-dependent ROI** profile.
A structurally sound lane holds positive ROI even when the best winner is excluded.

---

## Refined Lane Simulations

| Simulation | n | SR | Frame | ROI |
|---|---|---|---|---|
| VP40_LANE (full) | 150 | 45.3% | 80.7% | +8.2% |
| VP40_SP_LT3 | 93 | 61.3% | — | -1.3% |
| VP40_SP_LT4 | 114 | 52.6% | — | -11.1% |
| **VP40_TIER_A_ONLY** | **132** | **44.7%** | **80.3%** | **+9.4%** |
| VP40_SP_LT3_TIER_A | 85 | 60.0% | — | -3.6% |

**Finding:** VP40_TIER_A_ONLY is the most stable refined lane — higher ROI than the full VP40_LANE, and the ROI profile is not driven by a single outlier. VP40_TIER_A is already a tracked named lane (n=132, SR=44.7%, ROI=+9.4%). It does not need to be a separate lane — it is already proven.

The SP<3.0 filtered simulations show high SR but negative or flat ROI — short prices compress returns even at 60%+ win rates.

---

## Overlap Analysis

| Lane | Overlap with VP40 | % of VP40 | Shared winners |
|---|---|---|---|
| VP40_TIER_A_LANE | 132/150 | 88.0% | 59/68 |
| SHORTFAV_VP30 | 93/150 | 62.0% | — |
| MDS_HIGH_LANE | 34/150 | 22.7% | — |
| IMPROVER_LANE | 22/150 | 14.7% | — |
| MIDPRICE_ROUTER_QUAL | — | — | — |

88% of VP40_LANE rows are also VP40_TIER_A_LANE. The two lanes are almost the same lane. The 12% difference (18 rows) are Tier B/C/X at VP≥0.40 — low evidence value.

**Winners lost if restricted to VP40_TIER_A:** 9 out of 68 total wins = 13.2%.
9 winners lost, but 132 selections become 150 — a modest coverage cost for Tier A restriction.

---

## Subgroup Risk

### Course Subgroup

| Course | n | SR | ROI |
|---|---|---|---|
| Ripon | 5 | 80.0% | +210% |
| Yarmouth | 5 | 80.0% | +26.2% |
| Chepstow | 5 | 40.0% | +10.0% |
| Bath | 6 | 50.0% | -12.8% |
| Beverley | 5 | 0.0% | -100% |
| Hereford | 6 | 33.3% | -75.0% |
| Doncaster | 5 | 20.0% | -40.0% |

Beverley at SR=0% (n=5) and Hereford at ROI=-75% (n=6) are visible drains but at very small n — these are noise, not structural collapse. Continue monitoring as n grows.

### Class Subgroup

All 150 VP40 rows are class 4 — no class breakdown meaningful.

### Going Subgroup

Going data is sparse in the corpus — no reliable going breakdown possible.

---

## Losing Run Risk

```
Longest losing run: 8
Max drawdown (flat £1): £17.89
LLR as % of n: 5.3%
```

LLR of 8 is within tolerance at n=150. The drawdown of £17.89 on £1 flat stake means the operator
would face a 17-race losing period at the worst point in the sample. Manageable but notable.

---

## Promotion Requirements (what VP40 needs)

All of the following must be true before promotion to any live policy:

```
1. n >= 250 (current: 150 — needs +100 more results)
2. ROI >= 0% when top winner excluded (current: fails at -13.9%)
3. SP band drain resolved:
   - Either restrict VP40 to SP<3.5 (removing the mid-price drain zone)
   - Or enforce VP40_TIER_A (already a proven lane with positive ROI)
4. No severe course collapse at n>=10 (Beverley at n=5 is noise — monitor)
5. Sentinel PASS or WARN (not BLOCK)
6. Human approval at operator council — no automatic promotion
```

---

## Stop Conditions

If VP40_LANE crosses any of these at n>=200, trigger a council review and demote:

```
SR < 40% at n >= 200
Frame < 70% at n >= 200
ROI < -5% at n >= 200 (sustained negative, not single-event)
LLR > 20% of n
New subgroup collapse at n >= 15 (SR < SR_lane - 20pp)
```

---

## Current Recommendation: WATCH_ONLY

```
VERDICT:        WATCH_ONLY
NEXT GATE:      n >= 250 AND ROI stable without top winner
CURRENT STATUS: 7/7 promotion gates (but outlier dependency is a disqualifier)
WATCH:          VP40_TIER_A_ONLY — already proven, already positive ROI, no outlier dependency
DO NOT:         Change scoring, routing, staking, Telegram, or any live system
```

---

## The Real Finding

VP40_LANE with broad SP coverage is not yet a clean policy lane.
VP40_TIER_A_LANE is the better-defined lane — same core signal, cleaner ROI, already proven.

The shadow policy discussion for VP40 should be about:

```
1. Should VP40_TIER_A become an explicit execution gate?
   (it already exists as a named lane — this is a question of whether it gets operator priority)

2. Should VP40 + SP3.0-8.5 be explicitly suppressed?
   (the evidence suggests it should — this is the MIDPRICE_SUPPRESS argument)

3. Should the promotion gate report add an outlier check gate?
   (ROI stability without top N winners should be gate 8)
```

These are discussion questions, not actions. Nothing changes until the discussion concludes with
human approval and n >= 250.

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

*VP40_SHADOW_POLICY_REVIEW_V1 — 2026-05-17*
*Evidence base: SIGMA_2K_SAFE_TRAINING_SLICE_V1 at 1310 rows, VP40 n=150*
*Next review: when n >= 250 OR VP40_TIER_A makes separate promotion gate case*
