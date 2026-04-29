# VELO 49-Day Signal Discovery Report — The First Evidence of Signal Compression

Generated: 2026-04-29 01:26 UTC

## 1. Executive Summary

VÉLØ is no longer just producing predictions. The 49-day evidence base shows signal compression:
certain internal score combinations are dramatically stronger than the global baseline.

- Global 49-day SR = **20.6%**
- Global 49-day frame = **48.4%**
- VP>=0.30 + Tier A = **40.1% SR / 77.2% frame / n=162**
- MDS>0.5 = **54.8% SR / 96.8% frame / n=31**
- Improvement score >0.40 = **43.5% SR / 82.3% frame / n=62**

The intelligence is real. The operator visibility layer is still behind it.

## 2. What We Found

- VP is monotonic: higher VP bands win and frame more often.
- VP>=0.30 + Tier A is the broadest proven live-quality lane.
- Market deception score >0.50 is the strongest hidden sidecar signal.
- Improvement score >0.40 is a strong underused signal.
- Tier B with VP<0.30 is a confirmed drag zone.
- The main miss battlefield is the SP 3.0-8.5 winner zone.

## 3. VP30 Definition From Repo Proof

- VP = `VP is the shorthand used by the audits for velo_prime_prob, the live VELO_PRIME field-level win probability output.`
- VP30 = `velo_prime_prob >= 0.30`
- VP30_TIER_A = `velo_prime_prob >= 0.30 AND decision_tier == 'A'`

## 4. VP Monotonic Truth

| Band | n | SR | Frame |
|---|---:|---:|---:|
| VP<0.20 | 385 | 14.5% | 33.5% |
| VP 0.20–0.30 | 460 | 18.0% | 47.8% |
| VP 0.30–0.40 | 245 | 27.3% | 62.9% |
| VP>=0.40 | 100 | 44.0% | 85.0% |

The monotonic climb is structural, not cosmetic.

## 5. VP30_TIER_A Evidence

- SR = **40.1%**
- Frame = **77.2%**
- n = **162**

## 6. MDS_HIGH Evidence

- SR = **54.8%**
- Frame = **96.8%**
- n = **31**

## 7. IMPROVE_HIGH Evidence

- SR = **43.5%**
- Frame = **82.3%**
- n = **62**

## 8. PLACE_PROB_HIGH Evidence

- SR = **31.6%**
- Frame = **66.8%**
- n = **392**

## 9. B_TIER_LOW_VP_SUPPRESS Evidence

- SR = **16.9%**
- Frame = **44.1%**
- n = **272**

## 10. MID_PRICE_WINNER_FORENSICS Evidence

- SP 3.0-8.5 winners = **352 misses**
- Share of all misses = **58.0%**

## 11. What the Operator Currently Sees

- Tier buckets and governed A/B cards
- MDS numeric line on governed cards
- Execution state and reasons
- C-WATCH grouped lines with prob/gap/place

## 12. What the Operator Must See

- VP as a visible number on every governed card
- candidate lane badges (VP30_TIER_A, MDS_HIGH, IMPROVE_HIGH, PLACE_HIGH)
- suppress warnings (B-tier VP<0.30)
- forensic risk warnings (SP 3.0-8.5 danger zone)
- shadow evidence lines: n, SR, frame, status

## 13. Whether Telegram Currently Shows It

- VP30_TIER_A badge live: **NO**
- MDS_HIGH badge live: **NO**
- IMPROVE_HIGH badge live: **NO**

Current answer: treat operator visibility as unresolved until the display-only Telegram patch is approved and wired.

## 14. Why This Is Not Deployment

- These are shadow evidence cohorts, not promotion approvals.
- No routing change is approved.
- No staking automation is approved.
- The shadow ledger append script is not yet live.

## 15. Next Shadow-Ledger Step

`candidate_lane_shadow_ledger_dry_run`

The dry run must prove that every VP30_TIER_A, MDS_HIGH, IMPROVE_HIGH, PLACE_HIGH,
B_LOW_VP_SUPPRESS, and MID_PRICE_FORENSICS event is captured with correct running SR/frame.

## 16. Company Meaning

VÉLØ is no longer just predicting. It is learning which parts of itself are trustworthy.
That is the commercial turn: a racing intelligence system that can expose why a pick is elite,
dangerous, suppressed, or only forensic - and can prove the evidence trail behind each claim.

