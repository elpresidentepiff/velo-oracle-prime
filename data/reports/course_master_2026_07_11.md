# VÉLØ Course Master
Generated: 2026-07-11T14:05:26.920514Z

- Date: 2026-07-11
- Status: `COURSE_MASTER_PAPER_ONLY`
- Racing API used: `False`
- Ruleset: `COURSE_MASTER_V1_SIGMA_PLUS_DEEP_AGENT`

## Today
- Courses: 8
- Races: 57
- Action counts: {"COURSE_NEUTRAL": 1, "COURSE_SUPPORT": 4, "COURSE_SUPPRESS": 1, "COURSE_WARNING": 2}

| Course | Races | Action | Score | Confidence | Sigma | Deep ROI | Deep N | Warnings |
|---|---:|---|---:|---|---|---:|---:|---|
| Ascot | 7 | COURSE_WARNING | -2 | MEDIUM | n/a n=0 | -0.2539 | 18 | DEEP_DRAIN_ROI_-0.254_N18 |
| Chester | 8 | COURSE_SUPPORT | 1 | HIGH | DOING_WELL n=28 | -0.0233 | 9 | DEEP_NEGATIVE_ROI_-0.023_N9 |
| Hamilton | 7 | COURSE_SUPPRESS | -3 | HIGH | CAUTION n=31 | -0.0789 | 19 | SIGMA_CAUTION_N31, DEEP_NEGATIVE_ROI_-0.079_N19 |
| Limerick | 7 | COURSE_WARNING | -2 | MEDIUM | n/a n=0 | -0.52 | 9 | DEEP_DRAIN_ROI_-0.520_N9 |
| Navan | 7 | COURSE_NEUTRAL | 0 | LOW | n/a n=0 | 0.19 | 2 | - |
| Newmarket (July) | 8 | COURSE_SUPPORT | 1 | MEDIUM | n/a n=0 | 0.1521 | 14 | - |
| Salisbury | 6 | COURSE_SUPPORT | 2 | HIGH | DOING_WELL n=28 | 1.25 | 4 | - |
| York | 7 | COURSE_SUPPORT | 2 | HIGH | DOING_WELL n=33 | 0.6025 | 4 | - |

## Law
- Course Master is paper-only context.
- It can boost confidence or warn/suppress a review, but it cannot change VP, model score, router, staking, or execution.
- No course becomes a hard ban until sample size and forward evidence justify it.
