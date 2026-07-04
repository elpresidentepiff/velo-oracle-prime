# VELO 49-Day Signal Discovery Report - The First Evidence of Signal Compression

**Generated:** 2026-04-29

## 1. Executive Summary

VELO is no longer just producing predictions. The 49-day evidence base shows signal compression:

- Global 49-day SR = **20.6%**
- Global 49-day frame = **48.4%**
- VP30_TIER_A = **40.1% SR / 77.2% frame / n=162**
- MDS_HIGH = **54.8% SR / 96.8% frame / n=31**
- IMPROVE_HIGH = **43.5% SR / 82.3% frame / n=62**

This report marks the boundary between VELO's first era and second era.

## 2. What We Found

- VP is monotonic
- VP30_TIER_A is the broadest proven live-quality lane
- MDS_HIGH is the strongest hidden sidecar signal
- IMPROVE_HIGH is a strong underused signal
- B_LOW_VP_SUPPRESS is a confirmed drag zone
- the SP 3.0-8.5 zone is the main miss battlefield

## 3. VP30 Definition From Repo Proof

- VP = `velo_prime_prob`
- VP30 = `velo_prime_prob >= 0.30`
- VP30_TIER_A = `velo_prime_prob >= 0.30 AND decision_tier == 'A'`

## 4. VP Monotonic Truth

| Band | n | SR | Frame |
|---|---:|---:|---:|
| VP < 0.20 | 385 | 14.5% | 33.5% |
| VP 0.20-0.30 | 460 | 18.0% | 47.8% |
| VP 0.30-0.40 | 245 | 27.3% | 62.9% |
| VP >= 0.40 | 100 | 44.0% | 85.0% |

## 5. VP30_TIER_A Evidence

- 40.1% SR
- 77.2% frame
- n=162

## 6. MDS_HIGH Evidence

- 54.8% SR
- 96.8% frame
- n=31

## 7. IMPROVE_HIGH Evidence

- 43.5% SR
- 82.3% frame
- n=62

## 8. PLACE_PROB_HIGH Evidence

- 31.6% SR
- 66.8% frame
- n=392

## 9. B_LOW_VP_SUPPRESS Evidence

- 16.9% SR
- 44.1% frame
- n=272

## 10. MID_PRICE_WINNER_FORENSICS Evidence

- SP 3.0-8.5 winners = 352 misses
- 58% of all misses

## 11. What The Operator Currently Sees

- governed cards
- tier buckets
- MDS numeric line
- C-WATCH grouped lines

## 12. What The Operator Must See

- VP
- signal badges
- sidecar values
- risk warnings
- shadow evidence status

## 13. Whether Telegram Currently Shows It

Before the display patch, no.  
After the local display-only patch, yes if the patched sender is the version executed.

## 14. Why This Is Not Deployment

- shadow evidence is not promotion
- no router change
- no staking automation
- no model change

## 15. Next Shadow-Ledger Step

`candidate_lane_shadow_ledger_dry_run`

## 16. Company Meaning

VELO is learning which parts of itself are trustworthy.

## 17. ETCSLV Meaning

Inside ETCSLV, this report belongs to the **Verification Interface**:

- discoveries feed the **Tool Registry**
- evidence is stored in the **State Store**
- next actions become **Life Cycle Hooks**
- operator visibility improves the **Execution Loop**

That is why this report matters beyond the numbers.

---

*VELO 49-Day Signal Discovery Report V1*
