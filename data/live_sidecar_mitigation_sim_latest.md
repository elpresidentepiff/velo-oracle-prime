
====================================================================
LIVE SIDECAR MITIGATION SIMULATION
Generated: 2026-05-02T20:09:43.268333Z
Sample: 301 races with full runner scores and closed results
====================================================================

## Profile Comparison

Profile                          n      SR   Frame      ROI   AvgSP  VP30n  VP30SR   MaxDD  LoseRun
---------------------------------------------------------------------------------------------------
A_CURRENT_LIVE                 301   0.206   0.435   -0.226    6.60     52   0.269   89.68       21 ← LIVE
B_CORE_ONLY                    301   0.213   0.488   -0.026    6.60     52   0.269   47.97       20  ROI+0.200vs live
C_CORE_PLUS_MDS_PLACE          301   0.206   0.452   -0.234    6.60     52   0.269   92.18       24  ROI-0.008vs live
D_REMOVE_RED_FLAGS             301   0.199   0.439   -0.261    6.60     52   0.269  100.18       27  ROI-0.035vs live
E_STRICT_VALUE                 301   0.209   0.478   -0.081    6.60     52   0.269   71.00       34  ROI+0.145vs live

## Verdicts

  Best profile by ROI:         B_CORE_ONLY  (-0.026)
  Best profile by SR:          B_CORE_ONLY  (0.213)
  Best profile by frame rate:  B_CORE_ONLY  (0.488)

  Shadow comparison candidate:        B_CORE_ONLY
  release_day_prob → disable-test:    NO — inconclusive at this sample size
  comment_intel_score → disable-test: NO — inconclusive at this sample size
  improvement_score verdict:          SHADOW_TEST

## Notes
  Frame rate uses live engine's top_pick_placed for same-horse selections.
  ROI = flat-stake £1 per race, winner SP taken as return.
  VP30 SR = strike rate among races where profile top-pick has VP≥0.30.

## Live Code Change: NONE
  No scoring weights changed. No model touched. No router changed.
  No staking. No Telegram. No live execution. Simulation only.