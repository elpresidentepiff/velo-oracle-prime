# July 4 2026 — Live RP Scrape & Identity Gate — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | pipeline THE_ONE_TRUTH.md Steps 1-6 executed live | NO SUPABASE WRITES

---

## 1. Races

**51** individual races captured and parsed, matching the URL list built from the live RP index page.

## 2. Courses

**8** — Bellewstown, Beverley, Carlisle, Leicester, Naas, Newmarket (July), Nottingham, Sandown. Same 8 tracks as the earlier PDF-derived capture, now confirmed via the canonical live scrape.

## 3. Active runners

**453** (non-runners excluded). This is lower than the 482 counted from the PDF-derived racecard_merged files — the official standard-card capture reflects the runner list as declared at scrape time, including any non-runner declarations since the PDFs were generated; not investigated further as it doesn't affect this gate's purpose.

## 4. Null off_times

**0.** Preflight gate (`scripts/ops/validate_rp_injection.py`) passed cleanly: `RP_INJECTION_PREFLIGHT_PASS`, 51 races, 51 unique race IDs, 8 courses, 453 active runners.

## 5. horse_id availability

**453/453 (100%).** Every active runner in `data/racecards_2026_07_04_standard.json` carries a real Racing Post horse UID (e.g. `8205613`), sourced from the `__NEXT_DATA__` JSON blob on each live race page — not present at all in the earlier PDF-only capture.

## 6. Passport ID match coverage

**242/453 = 53.4%.** Computed via `new_build_velo.passport_lookup.lookup_passport_features()`, which checks the passport bank's `_by_uid` index first. Confirmed the passport bank itself (`data/new_build/passports/horse_passports_v1.jsonl`, 6,221 entries) carries `horse_rp_uid` on all 6,221 rows — meaning this match is a deterministic integer-ID lookup, not a string comparison.

## 7. Remaining misses

**211** runners have a valid `horse_id` but no matching entry in the passport bank.

## 8. Nature of the remaining misses

**Thin history, not identity ambiguity.** Because every runner now carries a confirmed, unique RP horse UID, a "miss" here means "this specific horse has no passport built yet" — there is no possibility of a miss actually being a same-horse-different-spelling case, or an accidental match between two different horses. That entire risk category (demonstrated earlier with "Beagle Bay"/"Eagle Bay") is structurally closed by ID-based matching.

## 9. Is the name-only ambiguity risk closed?

**Yes.** The earlier PDF-only capture had zero horse_id coverage and relied on name-string matching alone (which produced 2 held-for-review ambiguous candidates in the prior mission). This live scrape supersedes that entirely — every runner is matched (or not) by a confirmed unique ID.

## 10. Does historical depth risk remain?

**Yes — HIGH.** Only 53.4% of today's 453 confirmed-identity runners have any passport history in the bank. New Build's Lane 2 (passport-depth scoring) cannot fire for the other 211 runners; Lane 1 (pre-race-only features) can still fire for all of them since it doesn't depend on the passport bank.

## 11. Is local dry scoring allowed?

Per the operator's explicit decision: **yes**, `run_prime_today.py --dry-run` locally, to exercise the full scoring pipeline against real identity-confirmed data without persisting anything.

## 12. Is Supabase verdict write allowed?

**No.**

## 13. Is Sigma allowed?

**No.**

---

## Required Classifications
- LIVE_RP_IDENTITY_GATE_UPDATED
- RP_HORSE_ID_COVERAGE_COMPLETE (453/453)
- HISTORICAL_PASSPORT_DEPTH_RISK_HIGH (53.4%)
- IDENTITY_RISK_LOW
- NAME_ONLY_AMBIGUITY_RISK_CLOSED
- SAFE_TO_RUN_LOCAL_DRY_SCORING
- NOT_SAFE_TO_WRITE_SUPABASE
- NOT_SAFE_TO_RUN_SIGMA
- REPORT_ONLY
