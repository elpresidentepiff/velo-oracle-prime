# VÉLØ Course Master
Generated: 2026-07-23T21:03:01.688406Z

- Date: 2026-07-24
- Status: `COURSE_MASTER_PAPER_ONLY`
- Racing API used: `False`
- Ruleset: `COURSE_MASTER_V1_SIGMA_PLUS_DEEP_AGENT`

## Today
- Courses: 9
- Races: 63
- Action counts: {"COURSE_BOOST": 1, "COURSE_NEUTRAL": 3, "COURSE_SUPPORT": 1, "COURSE_SUPPRESS": 2, "COURSE_WARNING": 2}

| Course | Races | Action | Score | Confidence | Sigma | Deep ROI | Deep N | Warnings |
|---|---:|---|---:|---|---|---:|---:|---|
| Ascot | 6 | COURSE_WARNING | -2 | MEDIUM | n/a n=0 | -0.2539 | 18 | DEEP_DRAIN_ROI_-0.254_N18 |
| Chepstow | 7 | COURSE_WARNING | -2 | MEDIUM | n/a n=0 | -0.5 | 9 | DEEP_DRAIN_ROI_-0.500_N9 |
| Cork | 7 | COURSE_NEUTRAL | 0 | LOW | n/a n=0 | 1.06 | 5 | - |
| Kilbeggan | 8 | COURSE_NEUTRAL | 0 | LOW | n/a n=0 | 0.0 | 2 | - |
| Sandown | 6 | COURSE_SUPPRESS | -3 | MEDIUM | n/a n=0 | -0.35 | 10 | DEEP_DRAIN_ROI_-0.350_N10, DEEP_LOW_STRIKE_0.200 |
| Thirsk | 7 | COURSE_SUPPRESS | -3 | MEDIUM | n/a n=0 | -1.0 | 11 | DEEP_DRAIN_ROI_-1.000_N11, DEEP_LOW_STRIKE_0.182 |
| UTT | 8 | COURSE_NEUTRAL | 0 | LOW | n/a n=0 | n/a | 0 | - |
| Uttoxeter | 8 | COURSE_BOOST | 5 | HIGH | EXCELLING n=27 | 0.2082 | 11 | - |
| York | 6 | COURSE_SUPPORT | 2 | HIGH | DOING_WELL n=33 | 0.6025 | 4 | - |

## Law
- Course Master is paper-only context.
- It can boost confidence or warn/suppress a review, but it cannot change VP, model score, router, staking, or execution.
- No course becomes a hard ban until sample size and forward evidence justify it.
