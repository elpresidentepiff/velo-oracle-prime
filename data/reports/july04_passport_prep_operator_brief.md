# July 4 2026 — Passport & RP Intake Prep — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY (except local dropzone file placement) | NO SCORING, NO SUPABASE WRITES, NO SIGMA

---

## Mission update: RP files arrived mid-mission

This mission started under the assumption that no RP source material existed for 2026-07-04 (confirmed true at the time — no cache file, no RP-merged file, no raw capture directory contents). Partway through, the operator supplied 53 real files from a Windows OneDrive path. These were copied into the proper local, gitignored dropzone (`data/racing_post_account_raw/2026-07-04/`) rather than referenced from their original location, consistent with the intake manifest this mission itself defines. Everything below reflects that updated state.

## 1. Was today's card found (structured racecard)?

**No.** No `data/racecards_2026_07_04_standard.json` (cache format) and no `data/racecard_merged/racecard_*_2026-07-04.json` (RP-merged format) exist. A structured racecard has not been built yet — that is the explicit job of the next mission (JULY04-RP-INGEST), not this one.

## 2. Were RP files found?

**Yes — 53 files, now in `data/racing_post_account_raw/2026-07-04/`:**
- **8 courses with racecard PDFs**: Bellewstown, Beverley, Carlisle, Leicester, Naas, Newmarket, Nottingham, Sandown
- **7 of those 8 are complete** (all 6 RP file types: F_0010 Industry Selections, F_0011 Postdata, F_0012 Colourcard, F_0015_OR Official Ratings, F_0016 Spotlight, F_0032_TS Top Speed)
- **Sandown is missing F_0011 (Postdata)** — 5/6 present
- **5 courses have only a course-statistics HTML page** (Ffos Las, Musselburgh, Salisbury, Stratford, Thirsk) — no racecard PDF at all for these; unclear if they're part of today's card or supplementary background material Steven captured for another reason

## 3-4. Raw RP dropzone / manifest

Dropzone: `data/racing_post_account_raw/2026-07-04/` (gitignored, confirmed via `.gitignore` line 91 — never committed). Manifest files (`july04_rp_file_intake_manifest.md`/`.json`) were written before the files arrived and remain accurate for any future date's intake.

## 5. Passport coverage status

**Not computable yet.** Per-field coverage (horse_id, trainer, jockey, draw, OR, RPR, TS, spotlight, odds, form, going, race_type, class, distance, age/sex) requires a parsed, structured racecard — none exists. The coverage matrix (`july04_passport_coverage_matrix.csv`) records file-level status only (`BLOCKED_NO_TODAY_CARD` for the 7 complete courses, `PARTIAL` for Sandown, `MISSING_RP` for the 5 stats-page-only courses) rather than fabricating per-field percentages from unparsed PDFs.

## 6. Critical missing fields

- Structured racecard doesn't exist yet (blocking, applies to all courses)
- Sandown missing Postdata (F_0011)
- 5 courses (Ffos Las, Musselburgh, Salisbury, Stratford, Thirsk) have no racecard PDF, only a stats page

## 7-8. safe_to_run_verdicts_only / safe_to_run_scoring

Both **false**. No structured racecard exists, so there is nothing yet for `run_prime_today.py` to score or persist regardless of which flags are used.

## Existing tooling identified (not run this mission)

`scripts/ops/ingest_racecard_pdfs.py` already detects and classifies these exact file codes (confirmed via grep: it explicitly handles `F_0012` colourcard detection by filename). This is very likely the correct tool for JULY04-RP-INGEST, but was **not executed** in this mission — parsing/merging into a racecard is the next mission's job, not this preparation pass's.

---

## Recommended next step

**JULY04-RP-INGEST**: run the PDF ingestion/merge step against `data/racing_post_account_raw/2026-07-04/`, resolve the Sandown Postdata gap and the 5 stats-page-only courses (confirm with Steven whether those 5 are meant to be part of today's card or not), then re-run this readiness gate. Only if it turns green should a `--verdicts-only` proof or scoring attempt follow.

---

## Required Classifications
- JULY04_PASSPORT_RP_PREP_COMPLETE
- RAW_RP_DROPZONE_DECLARED
- RP_FILES_RECEIVED_AND_INVENTORIED
- TODAY_CARD_NOT_YET_BUILT
- PASSPORT_COVERAGE_PENDING_INGEST
- READY_TO_SCORE_GATE_WRITTEN
- NO_RAW_RP_FILES_COMMITTED
- NO_SUPABASE_WRITES
- NO_SCORING_RUN
- NO_SIGMA_RUN
- NO_RUNNER_SNAPSHOT_WRITE
- NO_TELEGRAM_SEND
- NO_MODEL_TRAINING
- REPORT_ONLY
