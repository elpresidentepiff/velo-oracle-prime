# Race Day 15 (2026-07-15) — Four-Model Winners Report (v2, corrected)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. **Revision v2** — issued after operator REQUEST CHANGES on PR #151 v1. See `race_day_15_frozen_recount.md` for the full correction log (P0-19..P0-24).

**TRUTH LAW APPLIED, CORRECTED**: v1 of this report over-counted Old VÉLØ by including 2 post-race Happy Valley "wins" inside a figure it mislabelled timing-proven, and mislabelled `radical_shadow_2026_07_15.json` as the No-RPR model when it is a distinct decision layer built around Old VÉLØ's own pick. Both defects are fixed in this revision.

## Headline (first page)

| View | Model | Wins | Eligible | Strike rate | Status |
|---|---|---|---|---|---|
| **Strict pre-race** | Old VÉLØ | **12** | **38** | **31.6%** | `STRICT_PRE_RACE_PROVEN` — canonical `off_dt_utc` after 08:46:03Z snapshot generation, excludes all 9 Happy Valley races (already run 03:30-07:50 UTC) |
| Full replay (informational only, NOT predictive) | Old VÉLØ | 14 | 46 | 30.4% | `FULL_SNAPSHOT_REPLAY_INCLUDING_POST_RACE` — includes the 9 Happy Valley races; never quote this as a strike rate |
| **Strict pre-race** | No-RPR (genuine, `sqpe_no_rpr_shadow_prob`) | **8** | **33** | **24.2%** | `STRICT_PRE_RACE_PROVEN`, 5 races excluded on tied top score (fail-closed) |
| Afternoon pre-race | New Build (Lane A) | 7 | 32 | 21.9% | `AFTERNOON_PRE_RACE_PROVEN` only — generated 14:09:30Z, valid solely for races whose off-time was still ahead of that instant |
| Afternoon pre-race shadow | Champion Intent Shadow | 9 | 32 | 28.1% | `AFTERNOON_PRE_RACE_PROVEN` shadow-only, `velo_scoring_allowed=False` for every row regardless of timing |

Sigma's previously reported 15/46 (32.6%) and this mission's own v1 report's 14/47 remain **both invalid** as Old VÉLØ performance claims — see `race_day_15_frozen_recount.md` Section "Phase 6b" for the Sigma contamination finding (unchanged) and the corrected Phase 6/6b text for why 14/47 was also wrong.

---

## Old VÉLØ winners — STRICT_PRE_RACE_PROVEN (n=12)

| Time | Course | Horse | SP | Tier | Product |
|---|---|---|---|---|---|
| 2.18 | Uttoxeter | Fine Thing | 2.88 | B | PASS |
| 2.40 | Catterick | South West | 2.88 | B | PASS |
| 2.48 | Uttoxeter | Lady Fortune | 11.0 | B | EW_CANDIDATE |
| 3.10 | Catterick | Lady Dublin | 3.0 | A | VISION_ONLY |
| 5.00 | Yarmouth | Adalida | 2.5 | A | VISION_ONLY |
| 5.05 | Bath | Havana Club | 3.25 | A | VISION_ONLY |
| 5.20 | Lingfield | Probation | 2.25 | C | PASS |
| 5.30 | Killarney | Minaun View | 4.0 | B | EW_CANDIDATE |
| 5.35 | Yarmouth | Splash | 6.0 | C | PASS |
| 5.50 | Lingfield | Brunhilde | 1.14 | B | PASS |
| 6.20 | Lingfield | Fire Thunder | 1.25 | A | WIN_ONLY |
| 7.20 | Lingfield | Desert Shadow | 3.5 | A | VISION_ONLY |

## No-RPR winners — genuine, from `sqpe_no_rpr_shadow_prob`, STRICT_PRE_RACE_PROVEN (n=8)

| Time | Course | Horse | SP | Score |
|---|---|---|---|---|
| 2.31 | Bath | Grey Horizon | 4.5 | 0.1772 |
| 3.10 | Catterick | Lady Dublin | 3.0 | 0.2569 |
| 4.01 | Bath | Campeona | 1.25 | 0.2291 |
| 5.50 | Lingfield | Brunhilde | 1.14 | 0.2184 |
| 6.10 | Yarmouth | Anchiano | 26.0 | 0.1526 |
| 7.30 | Killarney | Bella Colombia | 3.12 | 0.0935 |
| 7.40 | Yarmouth | Startled Lady | 3.5 | 0.1619 |
| 8.30 | Killarney | Loyal Touch | 9.5 | 0.0873 |

## New Build winners — Lane A, AFTERNOON_PRE_RACE_PROVEN only (n=7)

| Time | Course | Horse | SP | Lane | Score |
|---|---|---|---|---|---|
| 3.31 | Bath | Darkened Edge | 2.25 | lane_a | 0.190652 |
| 3.40 | Catterick | The Good Biscuit | 2.75 | lane_a | 0.176653 |
| 4.18 | Uttoxeter | Pep Talking | 3.5 | lane_a | 0.221825 |
| 4.48 | Uttoxeter | Belladinotte | 9.5 | lane_a | 0.14198 |
| 5.50 | Lingfield | Brunhilde | 1.14 | lane_a | 0.27532 |
| 6.20 | Lingfield | Fire Thunder | 1.25 | lane_a | 0.150185 |
| 7.20 | Lingfield | Desert Shadow | 3.5 | lane_a | 0.306604 |

## Champion Intent winners — shadow, AFTERNOON_PRE_RACE_PROVEN only, velo_scoring_allowed=False (n=9)

| Time | Course | Horse | SP | Score |
|---|---|---|---|---|
| 3.10 | Catterick | Lady Dublin | 3.0 | 0.269206 |
| 3.31 | Bath | Darkened Edge | 2.25 | 0.204122 |
| 3.40 | Catterick | The Good Biscuit | 2.75 | 0.155394 |
| 4.01 | Bath | Campeona | 1.25 | 0.238131 |
| 5.00 | Yarmouth | Adalida | 2.5 | 0.30003 |
| 5.50 | Lingfield | Brunhilde | 1.14 | 0.330959 |
| 6.20 | Lingfield | Fire Thunder | 1.25 | 0.147397 |
| 7.10 | Yarmouth | Highland Harvey | 2.2 | 0.132866 |
| 7.20 | Lingfield | Desert Shadow | 3.5 | 0.270703 |

---

## Shared and unique winners (compared strictly within each model's own timing-proven population — NOT a like-for-like race-universe comparison, since the four models have different proven denominators: Old VÉLØ/No-RPR = 38/33 pre-race races at 08:46Z; New Build/Champion Intent = 32 pre-race races at ~14:09Z)

- Shared by all four: Brunhilde
- Unique to Old VÉLØ: Fine Thing, Havana Club, Lady Fortune, Minaun View, Probation, South West, Splash
- Unique to No-RPR: Anchiano, Bella Colombia, Grey Horizon, Loyal Touch, Startled Lady
- Unique to New Build: Belladinotte, Pep Talking
- Unique to Champion Intent: Highland Harvey

## Excluded / timing-unproven races

See `race_day_15_timing_excluded_races.csv` for the full per-race exclusion ledger (40 rows: 9 Old VÉLØ Happy Valley post-race exclusions + 15 New Build post-race exclusions + 16 Champion Intent post-race exclusions). Old VÉLØ additionally has 0 non-runners in the strict population; No-RPR has 5 races excluded on fail-closed tied top score (`race_day_15_frozen_recount.json`, `phase6_no_rpr_genuine.tie_ledger`).

Full breakdown: `race_day_15_four_model_winners.csv`, `race_day_15_four_model_placed_only.csv`, `race_day_15_four_model_misses.csv`, `race_day_15_non_runners_exclusions.csv`, `race_day_15_timing_excluded_races.csv`, `race_day_15_frozen_recount.json`.
