# VELO data inventory + live weight study — 2026-09-13

Read-only study. **No live weight, model, Supabase or Railway change was made.** Live weights stay
frozen (ONE_TRUTH Law 1); anything below is evidence for an operator decision, not a promotion.
Reproduce: `scripts/analysis/weight_study/README.md`.

## 1. What data exists, and where

### Local (`data/`, 11.2 GB)
| Family | Coverage | Notes |
|---|---|---|
| RP raw HTML captures | 5.4 GB, racecards 39 dates / results 40 / passport 18 (from 24 Jun) | archival |
| Browser profiles | 2.2 GB | **credentials — never leaves the laptop** |
| `new_build/` | 1.5 GB; passport bank `horse_passports_v1.jsonl` 23 MB; `policy_lane_ledger.jsonl` 19,621 rows | no Supabase table |
| Verdicts `velo_prime_verdicts_*` | 116 dates, 17 Mar → 13 Sep | **top pick per race only** |
| Racecards standard / `racecard_merged` | 105 / 97 dates | |
| Results `data/results/rp_results_*` + legacy `data/results_*` | 71 + 74 dates | 17 legacy files are placed-only (Sporting Life) — never ingest |
| Sigma / council / mission control | 69 / 66 / 67 dates | |
| EOD learning events jsonl | 66 dates from 29 Apr | |
| `model_comparison_ledger.csv` | 2,274 rows, 63 dates | Supabase `model_comparison` has **0 rows** |
| `midprice_shadow_ledger.csv` | 6,657 rows, 73 dates | canonical rows only from 30 Jul |
| `data/reports/` | 1,913 files, 590 report types | |

### Supabase `ltbsxbvfsxtnharjvqcm`
211 tables/views; ~80 are empty and several belong to other projects (`cc_*`, npc, crypto, wallet).
The VELO tables that matter:

| Table | Rows | Dates |
|---|---|---|
| `velo_verdicts` | 5,544 | 15 Mar → 13 Sep; **3,694 carry every runner's components in `full_analysis.predictions`** |
| `racing_horse_runs` | 113,569 | to 12 Sep |
| `runner_release_candidates` (RPDC) | 48,830 | 124 dates |
| `canonical_model_scorecards` / `canonical_learning_events` | 33,333 / 30,782 | from 5 Jul (23 / 22 dates) |
| `sigma_audits` | 4,254 | 119 dates |
| `runner_prediction_snapshots` | 26,425 | **stopped 19 Jun** (redundant with `velo_verdicts.full_analysis`) |
| `raceform` | ~1.39 M (estimated) | 2017 → |

### Local dates missing from Supabase
| Local family → table | Missing dates |
|---|---|
| results → `racing_horse_runs` | 13: 05-09,10,12,13,14,15,16,18 (Racing API era, `hrs_*` ids), 05-31, 06-05, 06-14, 06-20, 06-24 |
| verdicts → `velo_race_truth` | 12: 05-01,03,04,10,16,29, 06-23, 06-30, 07-06, 07-24, 07-27, 07-31 (local copy is top pick only) |
| sigma → `sigma_audits` | 7: 05-23,26,28,31, 06-01, 06-24, 08-02 |
| learning events → `canonical_learning_events` ∪ `velo_learning_events` | **41**: 05-01 and 05-23 → 07-15 |
| racecards → RPDC | 10: 05-09 → 05-17, 08-12 |
| council runs, mission control, passport bank, model-comparison ledger, pre-30-Jul midprice ledger | no Supabase table at all |

### Git and Railway
- Git tracks 4,405 data files (1,211 at `data/` root, 1,114 in `reports/`, 609 raw RP racecards) — ONE_TRUTH open issue #4.
  Raw HTML, parquet and the browser profile do not belong in git; Supabase (tables, or Storage for raw files) is the store.
- Railway runs `app.main:app`. Of its routes, **10 read local files only** (`/api/llm-brief`,
  `/api/midprice-shadow`, `/api/old-velo-verdicts`, `/api/doctrine-scorecard`, `/api/upload/spotlight`,
  `/dashboard`, `/old_velo_three_option_card_latest.json`, `/rpdc_gate_card_latest.json`,
  `/sidecar_stack_latest.json`, `/telegram/webhook`) — on Railway those see only what was in git at deploy.
  3 read Supabase only (canonical endpoints), 6 read both. Railway CLI is not authenticated here, so the
  live deployment was not inspected.

## 2. Weight study

### Data
- 3,694 races with per-runner components (36,373 runners) from `velo_verdicts`.
- **665 verdicts were written after their race's off time** and are excluded (rescoring). That is 18% of
  the table — any Supabase-based performance view that does not filter them is contaminated.
- Results joined by race_id+horse_id, then date+horse name, then local full-field results files.
- **2,165 evaluable races** (single winner, ≥70% runners joined, verdict before the off).
- `sim.py` reproduces the live ranking: top pick agrees **98.4%** (100% Jun–Sep; April ran the legacy profile).

Live engine, for reference: weighted average of available components
`sqpe_v17 0.45 · improvement 0.12 · MDS 0.10`, constant-in-field components dropped per race,
macro adjustments, then renormalised to sum to 1 per race.

### Results (top pick, flat £1 at SP, paper only)
| Blend (2,165 races) | Win SR | Top-3 | ROI |
|---|---|---|---|
| **LIVE** sqpe .45 / imp .12 / mds .10 | 22.1% | 51.9% | −19.0% |
| sqpe only | 21.4% | 50.8% | −20.1% |
| improvement only | 16.5% | 43.0% | −20.2% |
| **MDS only** | **24.0%** | 52.6% | **−16.6%** |
| place_prob only | 20.8% | 50.3% | −19.7% |

**Out of sample** (fit on all earlier months, test on the next: Jun, Jul, Aug, Sep — 1,714 races):
- Best blend on the training months was MDS-heavy every time: sqpe/MDS = .55/.45 (Jun), .20/.80 (Jul), .10/.90 (Aug, Sep).
  **improvement and place_prob got weight 0 in every fold.**
- Win SR LIVE 23.2% → selected blend 24.1%: **+0.9 pts, 95% CI [+0.1, +1.8]** (paired bootstrap).
- ROI difference 95% CI [−8.3, +4.1] pts — **no evidence of better returns.**

By month (win SR, LIVE vs MDS only): Apr 14.5 vs 24.6 · May 19.2 vs 23.2 · Jun 24.0 vs 24.0 ·
Jul 22.8 vs 24.1 · Aug 26.1 vs 26.1 · Sep 20.8 vs 24.0. Off-time-verified races only (1,769): 23.9 vs 25.8.

### Why
- **Conditional logit** (within-race softmax, per-SD effect): MDS +0.33 (z 7.3), place +0.24 (z 7.0),
  **improvement −0.22 (z −5.1)**, sqpe −0.01 (z −0.3). sqpe and place_prob are near-duplicates
  (Spearman 0.93), so their split is not identifiable.
- **MDS is partly a market model.** Its features include `sp_rank`, `is_fav`, `log_sp`, odds contraction and
  rating-vs-market gap (all pre-race at scoring time). Its top pick is the pre-race favourite 54.7% of the time
  (sqpe 48.2%, improvement 25.8%).
- **The market beats every VELO blend on strike rate.** On 1,265 races with full pre-race odds:
  favourite 28.6% SR / −16.4% ROI; LIVE 22.8% / −15.7%; MDS only 24.4% / −14.6%.
  Components add little beyond the market (winner log-lik: market −1.975, components −2.067, both −1.968).
- **VP is overconfident about 2×.** Top-pick VP band → actual win rate:
  <.20 → 13.7% · .20–.30 → 15.7% · .30–.40 → 20.1% · .40–.50 → 27.6% · .50–.60 → 32.2% · .60+ → 34.1%.
  "High confidence" (VP ≥ 0.50) wins about a third of the time, not over half.
- **Where it loses:** big fields (10–12 runners: 16.0% SR, −34.0% ROI; 13+: 15.5%, −25.3%) and mid/long prices
  (SP 5–8: 10.9%, −29.2%). Only SP 2–3 top picks were profitable (41.1%, +5.4%).
- **Dead inputs:** `comment_intel_score` (0.089) and `release_day_prob` (0.075) are constant for every runner.
  `rpdc_release_score` is present on 10% of runners, No-RPR shadow on 54%.

## 3. Recommendations (operator decisions — nothing applied)
1. **Shadow, don't promote, an MDS-heavy blend** (sqpe .10 / MDS .90, improvement 0) as a forward lane for
   ≥ 300 races. Expected ~+1 pt win SR; returns unproven.
2. **Remove improvement_score from the blend or shadow its removal** — zero weight in every fold and a
   significantly negative coefficient.
3. **Calibrate VP before it drives tiers, VP30 or EW flags** (e.g. per-race temperature scaling fitted on this
   set). This changes confidence labels, not picks.
4. The bigger gap is structural, not weights: VELO trails the pre-race favourite by ~6 pts SR, and loses most
   in big fields and mid-price winners (ONE_TRUTH's known blind spot).
5. **Data hygiene:** stop writing verdicts after the off (or tag them), backfill the Supabase gaps above,
   fix `ingest_results_to_horse_runs.py` (`dist_f`/`class` vs `distance_f`/`race_class` → NULLs), and move the
   10 local-file dashboard routes onto Supabase so Railway shows what the laptop shows.

## 4. Actioned the same day (operator: "do all 5")
- Supabase gaps: 10 results dates → `racing_horse_runs` (5,153 rows); learning events → `velo_learning_events`
  (2,126 events, 59 dates) and canonical scorecards/events for 23 dates; five new tables for council, Mission
  Control, model ledger, passport bank and dashboard reports. Details and what was skipped: ONE_TRUTH
  "Local-only data now has a Supabase home".
- Dashboard: 7 local-file routes read Supabase (newer copy wins) — effective on Railway after deploy.
- Recommendation 1 is live as a shadow lane: `MDS_HEAVY_SHADOW_V1`, forward from 2026-09-14, gate ≥ 300 races.
  Recommendations 2 (drop improvement) and 3 (calibrate VP) are **not** applied.
