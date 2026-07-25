# VÉLØ Course Master
Generated: 2026-06-29T01:25:17.768326Z

- Date: 2026-06-29
- Status: `COURSE_MASTER_PAPER_ONLY`
- Racing API used: `False`
- Ruleset: `COURSE_MASTER_V1_SIGMA_PLUS_DEEP_AGENT`

## Today
- Courses: 5
- Races: 34
- Action counts: {"COURSE_BOOST": 1, "COURSE_NEUTRAL": 3, "COURSE_SUPPORT": 1}

| Course | Races | Action | Score | Confidence | Sigma | Deep ROI | Deep N | Warnings |
|---|---:|---|---:|---|---|---:|---:|---|
| Ffos Las | 7 | COURSE_BOOST | 3 | MEDIUM | n/a n=0 | 0.67 | 10 | - |
| Kempton (AW) | 7 | COURSE_NEUTRAL | 0 | MEDIUM | DRAIN_CAUTION n=16 | -1.0 | 4 | - |
| Pontefract | 7 | COURSE_NEUTRAL | 0 | MEDIUM | DOING_WELL_CAUTION n=17 | 1.826 | 5 | IDENTITY_MISS_HEAVY_SAMPLE |
| Stratford | 6 | COURSE_NEUTRAL | 0 | LOW | n/a n=0 | -0.634 | 5 | - |
| Windsor | 7 | COURSE_SUPPORT | 2 | HIGH | DOING_WELL n=29 | 0.4714 | 7 | - |

## Law
- Course Master is paper-only context.
- It can boost confidence or warn/suppress a review, but it cannot change VP, model score, router, staking, or execution.
- No course becomes a hard ban until sample size and forward evidence justify it.
