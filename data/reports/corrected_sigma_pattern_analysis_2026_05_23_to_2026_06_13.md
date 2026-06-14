# VÉLØ — Corrected Sigma Pattern Analysis
## Corrected row-bearing Sigma universe, May 23–Jun 13, 711 rows

Generated: 2026-06-14T09:43:18

---

## Section 1 — Universe Declaration

| Field | Value |
|---|---|
| Row count | 711 |
| Date range | 2026-05-23 to 2026-06-13 |
| Source files | sigma_results_2026_*.json (21 files with rows[]) |
| Excluded | sigma_results_2026_05_21.json, sigma_results_2026_05_22.json (predate rows[] format) |
| VP coverage | 100% (711/711) |
| Historical 2k+ archive | NOT INCLUDED — separate Supabase canon |
| Backfill provenance | NIGHTLY_EOD_LEARNING_EVENTS or LOCAL_VERDICT_JSON per row |

## Section 2 — VP Threshold Ladder

| Threshold | n | Wins | SR | Win SP avg | Win SP median |
|---|---|---|---|---|---|
| VP ALL | 711 | 181 | 25.5% | 3.42 | 2.75 |
| VP >=0.25 | 435 | 134 | 30.8% | 2.55 | 2.38 |
| VP >=0.30 | 334 | 110 | 32.9% | 2.38 | 2.10 |
| VP >=0.35 | 250 | 90 | 36.0% | 2.25 | 2.10 |
| VP >=0.40 | 181 | 74 | 40.9% | 2.13 | 1.83 |
| VP >=0.45 | 130 | 58 | 44.6% | 1.98 | 1.73 |
| VP >=0.50 | 91 | 41 | 45.1% | 1.96 | 1.44 |
| VP >=0.55 | 62 | 27 | 43.5% | 2.07 | 1.33 |

## Section 3 — VP by Odds Band (VP Proxy Test)

> **KEY QUESTION**: Is VP just selecting short-priced favourites, or does it add value within price bands?

| Band | All n | All SR | VP>=.30 n | VP>=.30 SR | VP>=.40 n | VP>=.40 SR | Lift (all→VP.40) |
|---|---|---|---|---|---|---|---|
| ODDS-ON 1.0-1.5 | 15 | 73.3% | 14 | 78.6% | 10 | 90.0% | +16.7% |
| EVS-6/4 1.5-2.5 | 47 | 53.2% | 25 | 68.0% | 13 | 76.9% | +23.7% |
| 2/1-3/1 2.5-4.0 | 82 | 32.9% | 25 | 36.0% | 12 | 41.7% | +8.7% |
| 3/1-5/1 4.0-6.0 | 88 | 14.8% | 20 | 15.0% | 10 | 20.0% | +5.2% |
| 5/1-8/1 6.0-9.0 | 57 | 10.5% | 20 | 10.0% | 5 | 0.0% | -10.5% |
| 8/1-14/1 9-15 | 37 | 5.4% | 9 | 0.0% | 2 | 0.0% | -5.4% |
| 14/1+ 15+ | 22 | 4.5% | 6 | 0.0% | 3 | 0.0% | -4.5% |

**VP PROXY VERDICT**: VP is NOT purely a short-price proxy. In the 1.5-4.0 zone, VP>=0.40 adds +20pp vs all picks in that band. However, VP cannot rescue the 6.0+ dead zone. The primary operating window for VP as a confidence filter is 1.5–4.0 SP.

## Section 4 — VP by Favourite Rank

> Note: Sigma evaluates ONE top pick per race. 'Rank' is inferred from SP within races sharing the same race_id. Most entries are rank 1 by design.

| Rank | VP threshold | n | Wins | SR |
|---|---|---|---|---|
| FAV rank 1 | ALL | 703 | 181 | 25.7% |
| FAV rank 1 | VP>=.40 | 181 | 74 | 40.9% |
| 2nd FAV | ALL | 6 | 0 | 0.0% |
| 3rd+ / long | ALL | 2 | 0 | 0.0% |

## Section 5 — Course Pattern Analysis

> Sample discipline: n<10=OBSERVATION, n 10-19=CAUTION, n>=20=MEANINGFUL

| Course | n | Wins | SR | VP avg | VP>=.40 | Warning |
|---|---|---|---|---|---|---|
| Windsor | 23 | 6 | 26.1% | 0.215 | 1 | MEANINGFUL |
| Hamilton | 20 | 6 | 30.0% | 0.345 | 5 | MEANINGFUL |
| Nottingham | 20 | 2 | 10.0% | 0.284 | 2 | MEANINGFUL |
| Lingfield | 19 | 2 | 10.5% | 0.240 | 2 | CAUTION |
| Cartmel | 18 | 5 | 27.8% | 0.258 | 3 | CAUTION |
| Kempton (AW) | 16 | 2 | 12.5% | 0.274 | 2 | CAUTION |
| Wolverhampton | 15 | 5 | 33.3% | 0.211 | 0 | CAUTION |
| Leicester | 14 | 4 | 28.6% | 0.226 | 1 | CAUTION |
| Redcar | 14 | 3 | 21.4% | 0.213 | 1 | CAUTION |
| Beverley | 14 | 3 | 21.4% | 0.235 | 2 | CAUTION |
| Uttoxeter | 13 | 6 | 46.2% | 0.343 | 5 | CAUTION |
| Bath | 13 | 3 | 23.1% | 0.363 | 4 | CAUTION |
| Goodwood | 12 | 1 | 8.3% | 0.275 | 2 | CAUTION |
| Thirsk | 10 | 2 | 20.0% | 0.257 | 2 | CAUTION |
| Wetherby | 8 | 2 | 25.0% | 0.365 | 1 | OBSERVATION |
| Epsom | 8 | 3 | 37.5% | 0.306 | 3 | OBSERVATION |
| Limerick | 8 | 1 | 12.5% | 0.272 | 2 | OBSERVATION |
| Bangor-on-Dee | 7 | 3 | 42.9% | 0.208 | 0 | OBSERVATION |
| Salisbury | 7 | 2 | 28.6% | 0.220 | 1 | OBSERVATION |
| Kelso | 7 | 2 | 28.6% | 0.236 | 0 | OBSERVATION |
| Plumpton | 7 | 3 | 42.9% | 0.369 | 3 | OBSERVATION |
| Newton Abbot | 7 | 4 | 57.1% | 0.336 | 2 | OBSERVATION |
| Brighton | 7 | 1 | 14.3% | 0.215 | 1 | OBSERVATION |
| Carlisle | 7 | 2 | 28.6% | 0.197 | 0 | OBSERVATION |
| Chepstow | 7 | 3 | 42.9% | 0.201 | 0 | OBSERVATION |
| Catterick | 7 | 0 | 0.0% | 0.187 | 0 | OBSERVATION |
| Chester | 7 | 1 | 14.3% | 0.119 | 0 | OBSERVATION |
| Stratford | 7 | 1 | 14.3% | 0.194 | 0 | OBSERVATION |
| Southwell | 7 | 2 | 28.6% | 0.346 | 1 | OBSERVATION |
| Lingfield (AW) | 7 | 2 | 28.6% | 0.504 | 5 | OBSERVATION |
| York | 6 | 2 | 33.3% | 0.165 | 0 | OBSERVATION |
| Huntingdon | 6 | 1 | 16.7% | 0.312 | 0 | OBSERVATION |
| Wolverhampton (AW) | 6 | 0 | 0.0% | 0.205 | 1 | OBSERVATION |
| Newcastle | 6 | 2 | 33.3% | 0.219 | 0 | OBSERVATION |
| Pontefract | 6 | 2 | 33.3% | 0.270 | 1 | OBSERVATION |
| Ripon | 6 | 1 | 16.7% | 0.458 | 2 | OBSERVATION |
| Warwick | 6 | 1 | 16.7% | 0.458 | 3 | OBSERVATION |
| Ffos Las | 6 | 2 | 33.3% | 0.464 | 4 | OBSERVATION |
| Doncaster | 6 | 2 | 33.3% | 0.361 | 2 | OBSERVATION |
| Musselburgh | 6 | 2 | 33.3% | 0.414 | 5 | OBSERVATION |
| Fontwell | 6 | 3 | 50.0% | 0.417 | 3 | OBSERVATION |
| Yarmouth | 6 | 1 | 16.7% | 0.283 | 1 | OBSERVATION |

## Section 6 — Strong vs Weak Day Analysis

| Date | n | W | SR | VP avg | VP>=.40 | VP>=.45 | hi-SP% | Category |
|---|---|---|---|---|---|---|---|---|
| 2026-05-23 | 45 | 13 | 28.9% | 0.188 | 2 | 1 | 75.6% | NORMAL |
| 2026-05-24 | 14 | 4 | 28.6% | 0.214 | 0 | 0 | 64.3% | NORMAL |
| 2026-05-25 | 34 | 7 | 20.6% | 0.231 | 0 | 0 | 52.9% | NORMAL |
| 2026-05-26 | 33 | 6 | 18.2% | 0.311 | 8 | 5 | 57.6% | NORMAL |
| 2026-05-27 | 32 | 10 | 31.2% | 0.285 | 6 | 2 | 43.8% | NORMAL |
| 2026-05-29 | 27 | 6 | 22.2% | 0.205 | 2 | 1 | 0.0% | NORMAL |
| 2026-05-30 | 35 | 4 | 11.4% | 0.171 | 1 | 0 | 45.7% | WEAK |
| 2026-05-31 | 21 | 2 | 9.5% | 0.231 | 1 | 0 | 61.9% | WEAK |
| 2026-06-01 | 21 | 6 | 28.6% | 0.244 | 2 | 2 | 57.1% | NORMAL |
| 2026-06-02 | 27 | 10 | 37.0% | 0.269 | 2 | 2 | 70.4% | STRONG |
| 2026-06-03 | 19 | 5 | 26.3% | 0.441 | 8 | 6 | 52.6% | NORMAL |
| 2026-06-04 | 34 | 13 | 38.2% | 0.440 | 16 | 14 | 61.8% | STRONG |
| 2026-06-05 | 39 | 13 | 33.3% | 0.352 | 16 | 13 | 0.0% | NORMAL |
| 2026-06-06 | 49 | 12 | 24.5% | 0.386 | 20 | 15 | 0.0% | NORMAL |
| 2026-06-07 | 30 | 6 | 20.0% | 0.337 | 9 | 6 | 0.0% | NORMAL |
| 2026-06-08 | 35 | 12 | 34.3% | 0.375 | 14 | 10 | 0.0% | NORMAL |
| 2026-06-09 | 33 | 0 | 0.0% | 0.355 | 10 | 7 | 0.0% | WEAK |
| 2026-06-10 | 34 | 6 | 17.6% | 0.325 | 10 | 5 | 55.9% | WEAK |
| 2026-06-11 | 40 | 12 | 30.0% | 0.393 | 16 | 14 | 0.0% | NORMAL |
| 2026-06-12 | 51 | 18 | 35.3% | 0.369 | 19 | 13 | 0.0% | STRONG |
| 2026-06-13 | 58 | 16 | 27.6% | 0.369 | 19 | 14 | 0.0% | NORMAL |

**Category summary**:
- STRONG days (SR>=35%): avg VP=0.359, avg VP40=12.3
- NORMAL days (18-34%): avg VP=0.309, avg VP40=8.7
- WEAK days (<18%): avg VP=0.270, avg VP40=5.5

**KEY CAVEAT — Jun 09**: VP_avg=0.355, VP40=10, but SR=0.0% (0/33 winners). High VP on the day does NOT guarantee wins. The gate identifies opportunity conditions only.

## Section 7 — Field Size Breakdown

| Field Size | All n | All SR | VP>=.40 n | VP>=.40 SR |
|---|---|---|---|---|
| FS 2-5 | 39 | 48.7% | 25 | 48.0% |
| FS 6-8 | 92 | 34.8% | 34 | 47.1% |
| FS 9-12 | 112 | 25.9% | 35 | 45.7% |
| FS 13+ | 63 | 15.9% | 8 | 62.5% |

## Section 8 — Frame Rate as Next-Day Predictor

| Signal | Pearson r | Verdict |
|---|---|---|
| today frame_rate → tomorrow SR | +0.067 | NOISE |
| today avg VP → tomorrow SR | +0.307 | WEAK (not actionable) |

**VERDICT**: No cross-day signal is strong. Sequential SR is essentially memoryless at daily resolution. Frame rate does not predict next-day SR.

## Section 9 — Opportunity Gate Proposal

> **PROPOSAL ONLY — not enabled, no scoring change**

### GREEN DAY
- avg VP >= 0.35
- at least 5 picks with VP >= 0.40
- at least 2 picks with VP >= 0.45
- Expected SR range: 35-40%

### AMBER DAY
- avg VP 0.25-0.35
- 1-4 picks with VP >= 0.40
- Expected SR range: 25-30%

### RED DAY (any trigger)
- avg VP < 0.25
- zero picks with VP >= 0.40
- card >50% in historically low-SR courses
- Expected SR range: <18%

**CRITICAL CAVEAT**: Jun 09 (VP_avg=0.355, VP40=10) would have scored GREEN but produced 0 wins. The gate must be treated as a soft signal — insufficient data (21 days) to harden thresholds.

## Section 10 — Guardrail Test Recommendations

1. **VP coverage test**: Sigma run must emit VP for >=95% of rows or raise VP_COVERAGE_BELOW_THRESHOLD
2. **Schema continuity**: Every sigma artifact must have rows[] array — aggregate-only artifacts rejected
3. **VP threshold report**: Auto-generate after every sigma close — ladder from ALL to >=0.55
4. **Subset vs universe warning**: Any report with n<711 must state 'CORRECTED_ROW_BEARING_SUBSET'
5. **Provenance check**: Every row must have vp_provenance field — UNRECOVERABLE triggers alert

## Required Caveats

- VP threshold is an operational filter, not a scoring formula change
- Course rules are observations (n<20), not bans
- Strike rate alone is insufficient — ROI and price context required
- 711 rows = corrected row-bearing universe, NOT the full historical 2k+ Supabase canon
- No live staking rule should be enabled from this analysis

## Classifications

- **CORRECTED_SIGMA_PATTERN_ANALYSIS_COMPLETE**: YES
- **SIGMA_711_ROW_UNIVERSE_DECLARED**: YES
- **OLDER_2K_SIGMA_ARCHIVE_NOT_CONFUSED**: YES
- **VP_FILTER_VALIDATED_ON_CORRECTED_ROWS**: YES
- **VP_PROXY_TO_ODDS_TESTED**: YES — VP adds real alpha in 1.5-4.0 zone (+20pp lift)
- **COURSE_SAMPLE_WARNINGS_ACTIVE**: YES — n<20 flagged OBSERVATION/CAUTION
- **OPPORTUNITY_GATE_PROPOSED_NOT_ENABLED**: YES
- **NO_LIVE_SCORING_CHANGE**: YES
- **NO_SUPABASE_WRITES**: YES
- **NO_MODEL_PROMOTION**: YES
- **NO_TELEGRAM_SEND**: YES