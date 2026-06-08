# Racing API Training File Inventory

Generated: 2026-05-25 | Trust policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING

---

## Parquet Files

| File | Size | Est. Rows | Date Built | Contains RPR | New Build Wired |
|------|------|-----------|------------|--------------|----------------|
| raceform_clean.parquet | 125 MB | ~374,000 | 2026-03-16 | YES (archive-only) | NO |
| raceform_v17_features.parquet | 79 MB | ~200,000 | 2026-03-16 | YES (archive-only) | NO |
| raceform_test_sample.parquet | 12 MB | ~25,000 | 2026-03-16 | YES (archive-only) | NO |
| training/sigma_2k_training_dataset_latest.parquet | 0.15 MB | ~2,000 | 2026-05-19 | NO | NO |

**Note**: raceform_clean and raceform_v17 are NOT wired to New Build spine. They are confirmed present on disk (`raceform_clean_available: true`, `raceform_v17_available: true` per sources.py inventory) but the New Build ingestion pipeline only processes the structured JSON racecards and results files.

---

## Racing API Structured JSON

| Type | Files | Races | Runners | New Build Wired |
|------|-------|-------|---------|----------------|
| racecards_*_standard.json | 36 | 1,654 | ~17,464 | YES (runners.jsonl) |
| results_*.json | 62 | 2,742 | ~25,987 | YES (runner_results.jsonl) |

Date range: 2026-03-17 to 2026-05-17 (racecards), 2026-03-15 to 2026-05-25 (results)

### Fields Accepted from Racing API Cards

horse, horse_id, trainer, trainer_id, jockey, jockey_id, owner, owner_id, sire, dam, damsire, age, sex, draw, headgear, wind_surgery, last_run, form_figures, official_rating (archive-only), topspeed (archive-only), **rpr (archive-only — never enters predictor)**, region, race_class, race_type, distance, going, surface

### Fields Accepted from Racing API Results

horse, horse_id, trainer, jockey, position, won, framed, sp_dec, **rpr (archive-only)**, tsr (archive-only), comment (archive-only), race_id, course, off_time

---

## Racing API Shadow Forward Ledger

- Path: `data/racing_api_shadow_forward_ledger.csv`
- Rows: 1,177
- Date range: 2026-04-29 to 2026-05-24
- Status: `RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK`
- Not ingested into New Build spine

Contains enrichment scores: `racing_api_connection_shadow_score`, `racing_api_course_shadow_score`, `racing_api_distance_shadow_score`, trainer-jockey combo analysis.

---

## Racing API Final Harvest (2026-05-14)

Small batch harvest covering 2026-05-07 to 2026-05-13:
- 6 racecard snapshots, 7 result batches
- 20 trainer analysis profiles (courses/distances/jockeys)
- 20 jockey analysis profiles

**Plan limitation**: Pro endpoints blocked (horse career results, jockey results, trainer results, odds). Standard plan only.

---

## RPDC Backfill

- Path: `data/rpdc_backfill/rpdc_tags_historical.jsonl`
- Rows: 18,554
- New Build wired: YES (rpdc_memory table, 18,554 rows)
- Key fields: rpdc_tags, rpdc_primary_tag, rpdc_release_score, rpdc_cash_window_flag

---

## Summary: What Is and Is Not Wired to New Build

| Source | New Build Status |
|--------|-----------------|
| Racing API racecards JSON | WIRED — 17,464 runners |
| Racing API results JSON | WIRED — 25,987 results |
| RPDC backfill JSONL | WIRED — 18,554 rows |
| raceform_clean.parquet | NOT WIRED — exists, referenced, not ingested |
| raceform_v17_features.parquet | NOT WIRED — exists, referenced, not ingested |
| Racing API shadow ledger CSV | NOT WIRED — shadow/leakage-tagged |
| RP form history JSONL | NOT WIRED — not yet in New Build pipeline |
| RP horse profile JSON | PARTIALLY WIRED — racecard_injection.json ingested, horse_profiles.json not |

No live VELO or Shadow VELO touched.
