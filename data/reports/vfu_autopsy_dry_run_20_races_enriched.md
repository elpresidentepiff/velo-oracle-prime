# VFU-03 — 20-Race Autopsy Enriched Rerun Report

**Generated**: 2026-06-14T20:14:34Z
**Source**: enriched union (VFU_PICK_SP_ENRICHMENT_V1)
**Canonical Passport mutated**: NO
**Supabase written**: NO

---

## Before vs After — pick_sp Coverage

| Metric | Before (VFU-02) | After (VFU-03) |
|---|---|---|
| Full union pick_sp filled | 0/1263 (0.0%) | 107/1263 (8.47%) |
| 20-race sample pick_sp null | 20/20 | 19/20 |
| odds_band UNKNOWN in sample | 20 | 19 |

20-race sample: 1/20 rows now have pick_sp. Full union: 107/1263 rows (8.5%).

---

## Failure Classes (Enriched)

- `VP_FALSE_POSITIVE` — 4 races
- `VP_FALSE_NEGATIVE` — 4 races
- `MID_PRICE_WALL` — 2 races
- `COURSE_DRAIN_CONFIRMED` — 2 races
- `INSUFFICIENT_EVIDENCE` — 1 races

---

## VP Analysis

- Win mean VP: **0.3724**
- Miss mean VP: **0.3105**
- VP explains direction: **True**

---

## Full 1,263-Row Pass Assessment

**Recommendation**: PENDING OPERATOR REVIEW

Coverage at 8.5% (107/1,263). Autopsy engine handles null pick_sp via data_gaps and null-tolerant failure classification. Operator decision required before full pass launch.

**Structural blockers:**

- 294 LOCAL_ONLY rows have no horse_name/date — structurally unmatchable from innovation CSV
- 465 rows are on dates not in innovation CSV — need broader SP source
- 154 CSV matches had SP=0.0 or empty — not usable

---

## Autopsy Table

| # | Horse | Date | Course | VP | Outcome | Pick SP | Failure Class |
|---|---|---|---|---|---|---|---|
| 1 | Big Negotiator | 2026-06-12 | York | 0.563 | WIN | — | N/A |
| 2 | Personal Ambition | 2026-05-16 | Bangor-On-De | 0.622 | WIN | — | N/A |
| 3 | Carry The Flag | 2026-05-09 | Naas (IRE) | 0.473 | WIN | — | N/A |
| 4 | ? |  | Plumpton | 0.401 | WIN | — | N/A |
| 5 | Charlie Boyo | 2026-06-08 | Windsor | 0.467 | MISS | — | VP_FALSE_POSITIVE |
| 6 | Wemightakedlongway | 2026-06-07 | Navan | 0.435 | MISS | 8.00 | VP_FALSE_POSITIVE |
| 7 | Pixie Diva | 2026-06-06 | Lingfield | 0.447 | MISS | — | VP_FALSE_POSITIVE |
| 8 | Thickthorn Tom | 2026-05-27 | Newton Abbot | 0.419 | MISS | — | VP_FALSE_POSITIVE |
| 9 | Kakirra | 2026-05-15 | Newbury | 0.175 | WIN | — | N/A |
| 10 | Man Is King | 2026-05-13 | Bath | 0.180 | WIN | — | N/A |
| 11 | ? |  | Brighton | 0.193 | WIN | — | N/A |
| 12 | Charlie Mason | 2026-05-08 | Ripon | 0.176 | MISS | — | VP_FALSE_NEGATIVE |
| 13 | Hiltons Pass | 2026-05-08 | Ballinrobe ( | 0.174 | MISS | — | VP_FALSE_NEGATIVE |
| 14 | Gaoth Chuil | 2026-05-09 | Killarney (I | 0.289 | MISS | — | MID_PRICE_WALL |
| 15 | American Mike | 2026-05-24 | Uttoxeter | 0.168 | MISS | — | VP_FALSE_NEGATIVE |
| 16 | Secret Trix | 2026-06-04 | Uttoxeter | 0.459 | PLACED | — | INSUFFICIENT_EVIDENCE |
| 17 | Yokohama | 2026-06-11 | Yarmouth | 0.390 | PLACED | — | COURSE_DRAIN_CONFIRMED |
| 18 | ? |  | Yarmouth | 0.348 | MISS | — | COURSE_DRAIN_CONFIRMED |
| 19 | Jannas Journey | 2026-05-09 | Ascot | 0.199 | MISS | — | VP_FALSE_NEGATIVE |
| 20 | Spanish Temptress | 2026-06-11 | Leopardstown | 0.293 | MISS | — | MID_PRICE_WALL |

---

## Hard Rule Confirmations

| Check | Status |
|---|---|
| Canonical Horse Passport NOT mutated | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No Supabase staging created | CONFIRMED |
| No live scoring change | CONFIRMED |
| No model promotion | CONFIRMED |
| No Telegram send | CONFIRMED |
| No Racing API restoration | CONFIRMED |
| No full 1,263-row pass yet | CONFIRMED |
| No Mar–Apr extraction | CONFIRMED |

## Final Classifications

- `VFU_03_20_RACE_AUTOPSY_ENRICHED_RERUN_COMPLETE`
- `VFU_PICK_SP_LOCAL_ENRICHMENT_COMPLETE`
- `VFU_20_RACE_AUTOPSY_ENRICHED_RERUN_COMPLETE`
- `SUPABASE_STAGING_NOT_CREATED`
- `EXTERNAL_SUPABASE_MUTATION_NOTE_RECORDED`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_FULL_1263_PASS_YET`
- `NO_MAR_APR_EXTRACTION`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`