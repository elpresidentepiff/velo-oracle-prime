# VÉLØ Course Master
Generated: 2026-06-21T14:59:54.099332Z

- Date: 2026-06-21
- Status: `COURSE_MASTER_PAPER_ONLY`
- Racing API used: `False`
- Ruleset: `COURSE_MASTER_V1_SIGMA_PLUS_DEEP_AGENT`

## Today
- Courses: 3
- Races: 20
- Action counts: {"COURSE_NEUTRAL": 2, "COURSE_SUPPORT": 1}

| Course | Races | Action | Score | Confidence | Sigma | Deep ROI | Deep N | Warnings |
|---|---:|---|---:|---|---|---:|---:|---|
| Brighton | 7 | COURSE_NEUTRAL | 0 | LOW | n/a n=0 | -1.0 | 2 | - |
| Hexham | 6 | COURSE_SUPPORT | 2 | MEDIUM | DOING_WELL_CAUTION n=19 | 0.2523 | 13 | - |
| Pontefract | 7 | COURSE_NEUTRAL | 0 | MEDIUM | DOING_WELL_CAUTION n=17 | 1.826 | 5 | IDENTITY_MISS_HEAVY_SAMPLE |

## Law
- Course Master is paper-only context.
- It can boost confidence or warn/suppress a review, but it cannot change VP, model score, router, staking, or execution.
- No course becomes a hard ban until sample size and forward evidence justify it.
