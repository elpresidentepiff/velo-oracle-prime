# Kakirra — VFU-08 Passport Override Case Study

**Generated**: 2026-06-14T22:14:54Z
**Review version**: VFU_PASSPORT_REVIEW_QUEUE_V1
**Canonical Passport mutated**: NO
**do_not_merge**: TRUE

---

## Identity

| Field | Value |
|---|---|
| Horse name | Kakirra |
| RP_UID | 8866972 |
| Namespace | RP_UID (canonical) |
| ID source | PASSPORT_NORM_MATCH |
| ID confidence | HIGH |

---

## VFU Appearances — Truth Table

| Date | Course | VP | VP ≥ 0.40 | Outcome |
|---|---|---|---|---|
| 2026-05-13 | Bath | 0.343 | **NO** | **WIN** |
| 2026-05-15 | Newbury | 0.175 | **NO** | **WIN** |
| 2026-06-02 | Wolverhampton | 0.277 | **NO** | **WIN** |

**VFU appearances**: 3 | **VFU wins**: 3 | **SR**: 100%
**VP range**: 0.175–0.343 (avg 0.265)
**All wins below VP threshold (0.40)**: **YES**

---

## Canonical Passport Profile

| Field | Value |
|---|---|
| Career runs | 5 |
| Career wins | 3 |
| Win rate | 0.6 |
| SP trajectory | SHORTENING |
| Position trend | IMPROVING |
| Margin trend | IMPROVING |
| AW specialist | True |
| Avg SP last 5 | 59.72 |
| Avg SP last 3 | 7.19 |
| Current OR | 60 |
| Last run date | 2026-06-02 |

---

## VP vs Passport Gap Analysis

**Pattern type**: VP_UNDERCOUNTING
**Verdict**: PASSPORT_TRUTH_AHEAD_OF_VP

> Kakirra won all 3 VÉLØ-observed appearances. VP ranged 0.175–0.343 at race time, never reaching the 0.40 threshold. Under VP_BELIEF_01 doctrine, none of these wins would be predicted. This is a VP false-negative cluster: the model is systematically blind to this horse.

### Possible causes of VP suppression

- Missing OR/RPR at race time (or_missing / rpr_missing flags)
- AW specialist on flat going — model may under-weight surface preference
- SP shortening trajectory not captured in VP ensemble
- Small field size on each occasion — model may penalise
- Horse winning on trainer angle not captured in SQPE/MDS

---

## Core Doctrine Implication

> VP_BELIEF_01 (VP>=0.40 = opportunity signal) is confirmed valid on the population. But Kakirra shows individual horses can win consistently BELOW the threshold. A blanket VP<0.40 exclusion would have missed all 3 Kakirra wins. This does not invalidate VP doctrine — it adds a case for horse-level modifiers.

---

## Recommended Action

Do not promote Kakirra to live staking from this data. Investigate OR/RPR availability at Kakirra's races. Consider whether AW specialist flag should modify VP calculation. Kakirra is the primary evidence for a potential VP blind-spot in AW specialists.

---

## Proposed Passport Labels

| Label | Justification |
|---|---|
| VP_UNDERCOUNTING_WATCHLIST | 3/3 wins below VP 0.40 threshold |
| AW_SPECIALIST | Passport confirms AW specialist |
| SP_SHORTENING_SIGNAL | Passport SP trajectory: SHORTENING |
| POSITION_TREND_IMPROVING | Passport position trend: IMPROVING |
| MARGIN_TREND_IMPROVING | Passport margin trend: IMPROVING |
| VFU_WIN_CONFIRMED_CURRENT_ERA | 3 identity-confirmed wins in current era |

**All labels are proposals only. `do_not_merge=True`. Operator must approve before any Passport write.**

---

## Hard Rule Confirmations

| Check | Status |
|---|---|
| Canonical Passport NOT mutated | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No live scoring change | CONFIRMED |
| No doctrine promotion | CONFIRMED |