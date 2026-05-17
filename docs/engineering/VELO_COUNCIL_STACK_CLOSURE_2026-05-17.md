# VÉLØ Council Stack Closure — 2026-05-17

**Classification:** COUNCIL_STACK_CLOSED | SIGNAL_LIFT_ZONES_CONFIRMED | MIDPRICE_LEAK_IDENTIFIED | NO_SCORING_CHANGE_YET
**Closed:** 2026-05-17 18:34 UTC
**Author:** Council stack — automated audit chain + operator review

---

## 1. Global Evidence Summary

| Metric | Value |
|---|---|
| Race days audited | 67 |
| Total sigma rows | 2050 |
| X-tier excluded | 142 |
| **Global strike rate (non-X)** | **21.4%** (baseline 20%) |
| **Global frame rate (non-X)** | **49.4%** (target 70%) |
| Days above baseline | 27 / 67 |
| Days at baseline | 13 / 67 |
| Days below baseline | 27 / 67 |

The global baseline is confirmed. VÉLØ exceeds the 20% random-selection floor. The frame rate of 49.4% is below the 70% target — this is a known, studied issue. It is not a signal failure. It is a volume problem: low-VP selections are dragging the aggregate down. The fix is suppression, not model retraining.

---

## 2. Proven Lift Zones

The edge is not global. The edge lives in signal partitions.

### VP Band Truth (67 days, monotonic — confirmed)

| Band | n | SR | Frame |
|---|---|---|---|
| VP < 0.20 | 581 | 14.1% | 34.1% |
| VP 0.20–0.30 | 691 | 17.8% | 47.6% |
| VP 0.30–0.40 | 390 | 29.0% | 63.3% |
| **VP ≥ 0.40** | **187** | **44.4%** | **81.3%** |
| VP ≥ 0.30 combined | 577 | 34.0% | 69.2% |
| **VP ≥ 0.30 + Tier A** | **282** | **40.4%** | **74.8%** |

VP bands are monotonically ordered. This is not a quirk of the dataset. This is the model knowing something real.

### Sidecar Signal Truth

| Signal | n | SR | Frame | Lift vs Global | Status |
|---|---|---|---|---|---|
| **MDS > 0.5** | **56** | **62.5%** | **94.6%** | **+41.1pp** | **CROWN JEWEL** |
| **Improvement > 0.40** | **92** | **41.3%** | **78.3%** | **+19.9pp** | **PROVEN** |
| Place prob > 0.80 | 624 | 31.7% | 65.2% | +10.3pp | KEEP |
| Archetype = Compression | 84 | 14.3% | 44.0% | -7.1pp | SUPPRESS |
| Archetype = Structure | 550 | 25.3% | 55.8% | +3.9pp | KEEP |

**MDS > 0.5 (SR=62.5%, Frame=94.6%)** is the highest-lift signal confirmed in the system. At n=56 this is a real pattern, not noise. When VÉLØ fires high MDS it is identifying genuine market-trap situations — horses the market has underestimated or misdirected money away from.

**Improvement score > 0.40 (SR=41.3%, n=92)** confirms the improvement engine is reading genuine forward movement that markets and public money lag behind.

---

## 3. Router Lane Health

| Lane | n | SR | Frame | ROI | Status |
|---|---|---|---|---|---|
| V1_BASE | 32 | 34.4% | 78.1% | +3.5% | WATCHLIST |
| V2_CLASS4_ONLY | 22 | 36.4% | 72.7% | +14.2% | WATCHLIST |
| V6_GOLD_SEAM | 10 | 40.0% | 70.0% | +37.5% | BUILDING |

All three lanes are healthy. No freeze conditions triggered. Gate thresholds:
- V2 → SHADOW_ROUTER_CANDIDATE: needs +8 more qualifying rows (target n=30)
- V1 → SHADOW_CANDIDATE: needs +18 (target n=50)
- V6 → SHADOW_CANDIDATE: needs +10 (target n=20)

**Do not over-edit these lanes.** The biggest risk now is "improving" what is working before understanding the leak.

---

## 4. Suppression Finding: Compression Archetype

**Archetype = Compression: SR=14.3%, n=84**

This is 7.1pp below global baseline. Compression horses — those that look like handicap value plays in compressed markets — are dead money without a stronger supporting signal.

**SUPPRESS CONFIRMED.** Compression without MDS > 0.5, VP ≥ 0.30, or improvement > 0.40 should be treated as:

```
NOISE / SUPPRESS / DO NOT PROMOTE
```

CASHRUN is useful as a filter inside Compression, not as a trigger. A Compression horse with high CASHRUN activation but weak VP + MDS is still bait.

---

## 5. Primary Leak: SP 3.0–8.5 Mid-Price Zone

**511 misses = 55.1% of all misses (928 total)**

This is the weekly battlefield. The system is bleeding in the mid-price zone. This is not random. It is structural.

Horses at SP 3.0–8.5 are the "believable" zone: not obvious favourites, not longshots. They look plausible. Markets look ordered. Models get seduced. Public money creates false signal density.

Miss profile breakdown (all misses):

| Class | Count | % |
|---|---|---|
| mid_priced_won | 459 | 49.5% |
| outsider_won | 162 | 17.5% |
| short_fav_won | 152 | 16.4% |
| market_decoy_followed | 87 | 9.4% |
| non_runner/untracked | 26 | 2.8% |
| other | 42 | 4.5% |

**The mid-price miss category alone is 49.5% of all misses.** This is the primary unsolved problem.

**Weekly study target:** `SP_MIDPRICE_LEAK_AUDIT_V1`

---

## 6. Governance

**NO actions taken on any of the following:**
- Scoring changes — none
- Model changes — none
- Staking changes — none
- Telegram format changes — none
- Playbook G promotion — none
- Live state mutation — none
- Router rule changes — none

The council stack is read-only intelligence. Evidence accumulation only.

**Permanent operating rules remain in force:**
```
NO live staking
NO candidate_route() changes without evidence gate
NO router rule changes
NO SQPE/model training
NO Playbook E
NO model changes from single-day analysis
NO baseline overwrite
NO force push
```

---

## 7. Next Approved Builds

**In priority order:**

### 7a. SP_MIDPRICE_LEAK_AUDIT_V1
```
scripts/sp_midprice_leak_audit.py
outputs:
  data/reports/sp_midprice_leak_audit_latest.json
  data/reports/sp_midprice_leak_audit_latest.md
  docs/engineering/SP_MIDPRICE_LEAK_AUDIT_V1.md
```
Question: Inside SP 3.0–8.5, what separates winners from bait?

### 7b. MDS_HIGH_LANE tracking
Shadow lane for market_deception_score > 0.5 + VP ≥ 0.30 combined.
Not automatic betting. Operator priority, report prominence, weekly tracking.
Lane name: `MDS_HIGH_LANE`

### 7c. IMPROVER_LANE tracking
Shadow lane for improvement_score > 0.40 + VP ≥ 0.30.
Lane name: `IMPROVER_LANE`

### 7d. Mission Control upgrade
Daily operator view should surface:
- MDS_HIGH count today
- IMPROVER_HIGH count today
- VP ≥ 0.40 count today
- COMPRESSION_SUPPRESS count today
- MIDPRICE_RISK count today
- Router lane status

---

## Strategic Reading

Before this closure, VÉLØ had predictions.

After this closure, VÉLØ has:
- A confirmed baseline (21.4% SR)
- Proven lift zones (MDS, Improvement, VP bands)
- Suppression zones (Compression, low VP)
- Router health with evidence accumulation
- A named primary leak (SP 3.0–8.5)
- A learning stack (sigma → ingest → RPDC → innovation protocol)
- An execution bridge (paper only)
- Agent governance (no live state mutation)

The operating question is no longer:

> "Did VÉLØ pick the winner?"

The operating question is:

> "Which signal regime is this race in?
> Is this a proven edge zone?
> Is this a mid-price trap?
> Should the machine strike, frame, suppress, or wait?"

**That is the operating system.**

---

*Council stack closed 2026-05-17. Next council: after SP_MIDPRICE_LEAK_AUDIT_V1 completes.*
