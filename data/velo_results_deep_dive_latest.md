# VÉLØ Results Deep Dive — 2026-04-29 to 2026-05-10

## Executive Read

- Days analyzed: `11`
- Total settled top picks: `435`
- Overall strike rate: `20.92%`
- Overall frame rate: `52.41%`
- Average top-pick VP: `0.2680`
- Sigma wrong-horse labels: `168`
- Sigma calibration-error labels: `40`

## Where VÉLØ Is Going Wrong

1. The main failure class is still picking the wrong horse rather than total confidence collapse.
2. Mid-strength and weak days are dragging the window harder than the strong days can rescue it.
3. VP30 base is cleaner than freedom-sidecar thinking; improve-heavy and mixed stacks are less trustworthy.
4. Industry rails are beating us on the dates where external comparison exists, especially Spotlight.
5. Operational truth is incomplete: some result days exist without local verdict truth, and only one day has a formal run-truth packet.

## Missing / Broken Inputs

- Results present but no local verdict file: `none`
- Local verdict file present but no results file: `none`
- Local verdict archive mismatch days: `2026-04-29, 2026-05-02, 2026-05-03, 2026-05-04, 2026-05-05, 2026-05-07`
- Telegram delivery is not yet first-class system-of-record truth.
- Commit SHA lineage is still not attached to every scoring run in a provable way.

## Day Breakdown

| Date | Picks | Wins | Frames | SR | FR | Sigma Verdict | Wrong Horse | Calibration | Unmatched | Local-Sigma Delta |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 2026-04-29 | 37 | 6 | 18 | 16.22% | 48.65% | ACCEPTABLE_DAY | 27 | 4 | 1 | -1 |
| 2026-04-30 | 42 | 4 | 21 | 9.52% | 50.0% | UNAVAILABLE | 0 | 0 | 1 | 0 |
| 2026-05-02 | 48 | 7 | 21 | 14.58% | 43.75% | ACCEPTABLE_DAY | 37 | 9 | 5 | -7 |
| 2026-05-03 | 32 | 10 | 23 | 31.25% | 71.88% | STRONG_DAY | 20 | 5 | 4 | -4 |
| 2026-05-04 | 56 | 10 | 29 | 17.86% | 51.79% | ACCEPTABLE_DAY | 38 | 10 | 2 | -3 |
| 2026-05-05 | 27 | 3 | 12 | 11.11% | 44.44% | WEAK_DAY | 22 | 7 | 5 | -5 |
| 2026-05-06 | 29 | 8 | 18 | 27.59% | 62.07% | UNAVAILABLE | 0 | 0 | 5 | 0 |
| 2026-05-07 | 39 | 13 | 22 | 33.33% | 56.41% | ACCEPTABLE_DAY | 24 | 5 | 2 | -2 |
| 2026-05-08 | 47 | 11 | 28 | 23.4% | 59.57% | UNAVAILABLE | 0 | 0 | 2 | 0 |
| 2026-05-09 | 59 | 16 | 27 | 27.12% | 45.76% | UNAVAILABLE | 0 | 0 | 5 | 0 |
| 2026-05-10 | 19 | 3 | 9 | 15.79% | 47.37% | UNAVAILABLE | 0 | 0 | 3 | 0 |

## By Tier

| Bucket | Count | Wins | Frames | SR | FR | Avg VP | Avg MDS | Avg Improve |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 90 | 39 | 68 | 43.33% | 75.56% | 0.4517 | 0.2488 | 0.1996 |
| B | 229 | 42 | 115 | 18.34% | 50.22% | 0.2487 | 0.0684 | 0.0992 |
| C | 72 | 9 | 33 | 12.5% | 45.83% | 0.1829 | 0.0481 | 0.0840 |
| D | 10 | 0 | 2 | 0.0% | 20.0% | 0.1461 | 0.0192 | 0.0694 |
| X | 34 | 1 | 10 | 2.94% | 29.41% | 0.1274 | 0.0302 | 0.0513 |

## By Probability Band

| Bucket | Count | Wins | Frames | SR | FR | Avg VP | Avg MDS | Avg Improve |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.20-0.29 | 145 | 22 | 65 | 15.17% | 44.83% | 0.2443 | 0.0584 | 0.0960 |
| 0.30-0.39 | 80 | 23 | 58 | 28.75% | 72.5% | 0.3421 | 0.1309 | 0.1420 |
| 0.40-0.49 | 33 | 16 | 26 | 48.48% | 78.79% | 0.4460 | 0.2789 | 0.2082 |
| 0.50+ | 24 | 14 | 20 | 58.33% | 83.33% | 0.6187 | 0.4080 | 0.2825 |
| <0.20 | 153 | 16 | 59 | 10.46% | 38.56% | 0.1583 | 0.0314 | 0.0669 |

## By Sidecar Role

| Bucket | Count | Wins | Frames | SR | FR | Avg VP | Avg MDS | Avg Improve |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ELITE_STACK | 1 | 1 | 1 | 100.0% | 100.0% | 0.8327 | 0.7709 | 0.2897 |
| IMP_HIGH | 11 | 9 | 10 | 81.82% | 90.91% | 0.4370 | 0.4981 | 0.5442 |
| MDS_HIGH | 10 | 8 | 9 | 80.0% | 90.0% | 0.5671 | 0.6635 | 0.4211 |
| STRONG_STACK | 3 | 3 | 3 | 100.0% | 100.0% | 0.6716 | 0.6831 | 0.3115 |
| SUPPRESS | 15 | 2 | 8 | 13.33% | 53.33% | 0.2748 | 0.0645 | 0.1157 |
| VP30 | 64 | 31 | 53 | 48.44% | 82.81% | 0.4207 | 0.2485 | 0.1775 |
| VP30_BASE | 114 | 39 | 87 | 34.21% | 76.32% | 0.3988 | 0.1630 | 0.1395 |
| VP30_IMPROVE | 7 | 3 | 4 | 42.86% | 57.14% | 0.3948 | 0.2731 | 0.5142 |

## Highest-Confidence Misses

| Date | Course | Time | Horse | Tier | VP | Winner | Stack Roles |
|---|---|---:|---|---|---:|---|---|
| 2026-04-29 | Southwell (AW) | 2:55 | Bellatina | A | 0.5954 | Frumoasa (IRE) | VP30, VP30_BASE |
| 2026-05-02 | Hexham | 6:15 | Moonshine Man | A | 0.5776 | Kingston Narcissus (FR) | VP30_BASE |
| 2026-05-05 | Hereford | 7:47 | Triple Haych | A | 0.5733 | Not So Sobers (GB) | VP30_BASE |
| 2026-05-04 | Beverley | 2:30 | Lady Dublin | A | 0.5182 | Moonlight Tango (GB) | VP30_BASE |
| 2026-05-03 | Newmarket | 4:10 | Call Me Tomorrow | A | 0.4980 | Efsixteen (GB) | VP30_BASE |
| 2026-05-04 | Fakenham | 2:18 | Path Of Stars | A | 0.4907 | Pottersmattyeeehaa (GB) | VP30_BASE |
| 2026-05-04 | Beverley | 3:05 | Donna Rumma | A | 0.4710 | Lake Muritz (GB) | VP30_BASE |
| 2026-05-04 | Curragh | 1:15 | Ischgl | A | 0.4618 | Immortal Guard (IRE) | VP30_IMPROVE |
| 2026-05-02 | Doncaster | 7:32 | Trucial Pearl | A | 0.4542 | Tekitoff (GB) | VP30_BASE |
| 2026-05-05 | Gowran Park | 6:38 | Faiyum | A | 0.4295 | Sindria (IRE) | VP30_BASE |
| 2026-05-05 | Ffos Las | 2:48 | Prince Rhinegold | A | 0.3751 | Model Approach (IRE) | VP30_BASE |
| 2026-05-05 | Gowran Park | 7:08 | Almeiyda | A | 0.3700 | Dark Lucinda (IRE) | VP30_BASE |

## Industry Benchmark

- Dates covered: `2026-05-06, 2026-05-07, 2026-05-10`

| Rail | Count | Wins | Frames | SR | FR |
|---|---:|---:|---:|---:|---:|
| D EXPRESS (Melissa Jones) | 75 | 24 | 43 | 32.0% | 57.33% |
| DAILY MAIL (Robin Goodfellow) | 69 | 17 | 30 | 24.64% | 43.48% |
| DAILY MIRROR (Newsboy) | 74 | 18 | 36 | 24.32% | 48.65% |
| DAILY RECORD (Garry Owen) | 74 | 16 | 39 | 21.62% | 52.7% |
| LAMBOURN (Liam Headd) | 16 | 2 | 9 | 12.5% | 56.25% |
| NEWMARKET (David Milnes) | 33 | 8 | 15 | 24.24% | 45.45% |
| POSTDATA | 97 | 25 | 53 | 25.77% | 54.64% |
| RP RATINGS (Ainsley Scorah) | 83 | 21 | 39 | 25.3% | 46.99% |
| RP RATINGS (Paul Curtis) | 83 | 21 | 39 | 25.3% | 46.99% |
| SPOTLIGHT | 97 | 26 | 55 | 26.8% | 56.7% |
| TELEGRAPH (Marlborough) | 74 | 22 | 41 | 29.73% | 55.41% |
| THE GUARDIAN | 69 | 19 | 39 | 27.54% | 56.52% |
| THE IRISH SUN | 24 | 6 | 14 | 25.0% | 58.33% |
| THE NORTH (Colin Russell) | 2 | 2 | 2 | 100.0% | 100.0% |
| THE STAR (Jason Heavey) | 74 | 17 | 35 | 22.97% | 47.3% |
| THE SUN (Templegate) | 74 | 19 | 41 | 25.68% | 55.41% |
| THE TIMES (Rob Wright) | 74 | 21 | 36 | 28.38% | 48.65% |
| TOPSPEED | 54 | 8 | 22 | 14.81% | 40.74% |
| VELO | 88 | 22 | 47 | 25.0% | 53.41% |
| WEST COUNTRY (Liam Watson) | 24 | 4 | 14 | 16.67% | 58.33% |

## What Looks Missing

1. A stable morning truth packet for every scored day, not just failure days.
2. A consistent local verdict archive for every result day so replay windows are complete.
3. A cleaner sidecar promotion discipline: VP30 base looks useful, but improve-heavy and mixed stacks need stricter proof.
4. A formal benchmark rail in daily close so Spotlight/Postdata/Topspeed comparisons are not ad hoc.
5. A miss-class drilldown that tells us whether weak days are caused by tier drift, market shape misses, or source-quality gaps.

## Recommended Next Fixes

1. Make daily run-truth packets automatic and mandatory for every scoring day.
2. Add commit SHA + trigger source into persisted scoring truth.
3. Keep VP30 base as the clean reference lane; hold improve/MDS claims to replay and close truth.
4. Run the industry benchmark automatically on every closed day where RP selection files exist.
5. Add a miss-forensics layer that tags high-confidence losses by likely cause using results + source completeness.
