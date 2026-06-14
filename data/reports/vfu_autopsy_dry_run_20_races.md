# VFU-02 — 20-Race Autopsy Dry-Run Report

**Generated**: 2026-06-14T19:37:43Z  
**Total autopsies**: 20  
**Source**: current-era sigma union, May 08–Jun 13  
**Canonical Passport mutated**: NO  
**Supabase written**: NO  

---

## 1. Did the autopsy schema capture useful truth?

**YES — with critical caveats.**

The schema captured VP, outcome, course tier, actual winner SP, failure class, and investigation questions successfully.
Four fields were absent from the sigma union source and represent gaps that must be resolved before the full 1,263-row pass:

| Gap | Impact |
|---|---|
| `pick_sp` — 0% coverage | Cannot classify SP_DEAD_ZONE_FAILURE. Cannot set odds_band. Critical. |
| `horse_id` — ~0% | Cannot join to Horse Passport by RP uid. Name-only join required. |
| `winner_in_frame` — 0% | Requires full field data. Not derivable from sigma-only rows. |
| `race_type / surface / class / field_size` — 0% | Sigma stores race-level summaries only. |

---

## 2. Fields Missing Most Often

- `pick_sp_null — not stored in sigma union` — 20/20 rows
- `horse_id_null — RP uid not in sigma row` — 20/20 rows
- `actual_winner_sp_null` — 3/20 rows
- `actual_winner_name_null` — 3/20 rows
- `off_time_null` — 3/20 rows

---

## 3. Failure Classes Observed

- `VP_FALSE_POSITIVE` — 4 races
- `VP_FALSE_NEGATIVE` — 4 races
- `MID_PRICE_WALL` — 2 races
- `COURSE_DRAIN_CONFIRMED` — 2 races
- `INSUFFICIENT_EVIDENCE` — 1 races

---

## 4. Did VP Explain Wins/Losses?

- Win mean VP: **0.3724**
- Miss mean VP: **0.3105**
- Direction confirmed: **True**

VP gradient holds in this 20-race sample — winners have higher mean VP than misses.

---

## 5. Did Course Tiers Explain Wins/Losses?

- Excelling course picks: 2 | Wins: 0
- Drain course picks: 2 | Losses: 1

Course tier signal present in dry-run. Full pass needed for statistical significance.

---

## 6. Did SP Dead-Zone Appear?

**Cannot assess.** `pick_sp` is 0% populated in the sigma union. SP dead-zone classification
requires pick SP from the innovation protocol CSV or `velo_verdicts` Supabase table.
This is the highest-priority schema gap to resolve before the full pass.

---

## 7. Horses Clearly Needing Passport Update

2 of 20 autopsies flagged `passport_update_candidate = true`.

- `Big Negotiator` | VP=0.563 | WIN | None
- `Personal Ambition` | VP=0.622 | WIN | None

---

## 8. Repeated-Horse Memory Issues

- `Jannas Journey` appears 2+ times in current era | MISS | VP=0.199
- `Spanish Temptress` appears 2+ times in current era | MISS | VP=0.293

No REPEAT_HORSE_MEMORY_MISSED classification triggered in this sample — would require cross-race comparison logic in Phase 4 autopsy engine.

---

## 9. Schema Revisions Before Full 1,263-Row Pass

1. **Join pick_sp from innovation protocol CSV** (`velo_innovation_protocol_1k_deduped.csv`).
   Secondary join: `date + course + off_time` for rows without direct race_id match.
2. **Join horse_id from racecard data** (`data/racing_post_account_parsed/*/racecard_injection.json`).
3. **Add race metadata** (field_size, race_type, distance_f, going) from racecard injection.
4. **winner_in_frame** requires full field scoring snapshot — defer until verdict archive is joined.
5. **vp_gate_label per day** — join from `data/sigma_results/` day-level VP summary.

---

## 10. Should VFU-03 Proceed?

**PROCEED — with schema augmentation first.**

The 20-race dry-run proves the autopsy structure is sound and produces useful forensic records.
VP explains direction (wins > misses). Failure classes are classifiable from available data.
Course tier evidence is present.

The critical blocker is `pick_sp` — without it, SP dead-zone classification is impossible
and odds_band is UNKNOWN on every row. This must be resolved before the full 1,263-row pass.

Recommended next step: build a `vfu_enrich_pick_sp.py` script that joins pick SP from the
innovation protocol CSV onto the union rows before the Phase 4 autopsy pass.

---

## Autopsy Records Summary

| # | Horse | Date | Course | VP | Outcome | Failure Class | Passport Update? |
|---|---|---|---|---|---|---|---|
| 1 | Big Negotiator | 2026-06-12 | York | 0.563 | WIN | N/A | YES |
| 2 | Personal Ambition | 2026-05-16 | Bangor-On-De | 0.622 | WIN | N/A | YES |
| 3 | Carry The Flag | 2026-05-09 | Naas (IRE) | 0.473 | WIN | N/A | no |
| 4 | ? |  | Plumpton | 0.401 | WIN | N/A | no |
| 5 | Charlie Boyo | 2026-06-08 | Windsor | 0.467 | MISS | VP_FALSE_POSITIVE | no |
| 6 | Wemightakedlongway | 2026-06-07 | Navan | 0.435 | MISS | VP_FALSE_POSITIVE | no |
| 7 | Pixie Diva | 2026-06-06 | Lingfield | 0.447 | MISS | VP_FALSE_POSITIVE | no |
| 8 | Thickthorn Tom | 2026-05-27 | Newton Abbot | 0.419 | MISS | VP_FALSE_POSITIVE | no |
| 9 | Kakirra | 2026-05-15 | Newbury | 0.175 | WIN | N/A | no |
| 10 | Man Is King | 2026-05-13 | Bath | 0.180 | WIN | N/A | no |
| 11 | ? |  | Brighton | 0.193 | WIN | N/A | no |
| 12 | Charlie Mason | 2026-05-08 | Ripon | 0.176 | MISS | VP_FALSE_NEGATIVE | no |
| 13 | Hiltons Pass | 2026-05-08 | Ballinrobe ( | 0.174 | MISS | VP_FALSE_NEGATIVE | no |
| 14 | Gaoth Chuil | 2026-05-09 | Killarney (I | 0.289 | MISS | MID_PRICE_WALL | no |
| 15 | American Mike | 2026-05-24 | Uttoxeter | 0.168 | MISS | VP_FALSE_NEGATIVE | no |
| 16 | Secret Trix | 2026-06-04 | Uttoxeter | 0.459 | PLACED | INSUFFICIENT_EVIDENCE | no |
| 17 | Yokohama | 2026-06-11 | Yarmouth | 0.390 | PLACED | COURSE_DRAIN_CONFIRMED | no |
| 18 | ? |  | Yarmouth | 0.348 | MISS | COURSE_DRAIN_CONFIRMED | no |
| 19 | Jannas Journey | 2026-05-09 | Ascot | 0.199 | MISS | VP_FALSE_NEGATIVE | no |
| 20 | Spanish Temptress | 2026-06-11 | Leopardstown | 0.293 | MISS | MID_PRICE_WALL | no |

---

## Hard Rules Confirmed

- Canonical Horse Passport NOT mutated: YES
- Supabase written: NO
- Live scoring changed: NO
- Model promotion: NO
- Telegram send: NO
- Racing API restoration: NO
- Mar–Apr extraction: NO
- Pre-surgery rows in sample: NO

## Final Classifications

- `VFU_02_20_RACE_AUTOPSY_DRY_RUN_COMPLETE`
- `RACE_AUTOPSY_RECORDS_CREATED`
- `PASSPORT_EXTENSIONS_DRY_RUN_ONLY`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `CURRENT_ERA_ONLY`
- `NO_FULL_1263_PASS_YET`
- `NO_MAR_APR_EXTRACTION`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`