# July 06 URL Universe — AW Venue Fix Report
Generated: 2026-07-06 | Mission: URL-UNIVERSE-01-JULY06-AW-VENUE-FIX

## Root cause
`scripts/ops/build_racing_post_racecard_url_list.py` classifies every extracted racecard URL as UK/IRE or international by checking its venue slug against a hardcoded `UK_IRE_VENUES` allowlist. The allowlist already carried `kempton-aw`, `newcastle-aw`, and `southwell-aw` as precedent for all-weather fixture slugs, but was missing the equivalent slugs for two other AW tracks: `lingfield-aw`, `lingfield-aw-gb` (Lingfield's second fixture ID), and `wolverhampton-aw`. Any URL with one of those three slugs fell through to the international bucket, which is explicitly documented in the script as "archived separately, not fed to VELO."

This is the same bug class that hit `southwell-aw` on 2026-07-05 (see `tests/test_racecard_url_list_venue_classification.py`, pre-existing regression test) and was patched one venue at a time without a systemic check — it recurred the very next day against different venues.

## Before / after counts

| | Races | Physical venues | Course entries | Runners | International bucket |
|---|---|---|---|---|---|
| **Before fix** | 21 | 3 (Ayr, Ripon, Roscommon) | 3 | 254 | 15 (Lingfield AW ×9, Wolverhampton AW ×6) |
| **After fix** | 36 | 5 (+ Lingfield AW, Wolverhampton AW) | 6 (Lingfield's two fixture IDs count separately) | 405 | 0 |

**Newly recovered races: 15.**

## Passport coverage after rebuild
`current_card_passport_feed_2026_07_06.jsonl` rebuilt from the corrected 36-race/405-runner standard cache: **188/405 = 46.4%** passport coverage (up from the pre-fix 103/254 = 40.6%, which was itself computed against the incomplete universe). Both the dated file and `current_card_passport_feed_latest.jsonl` were regenerated.

## What was NOT done in this mission
No scoring (New Build Step 7 not run), no Sigma, no result ingest, no Telegram, no model training, no promotion, no Supabase writes. This mission is a code fix + regression proof only, per the PR-path-only ruling.

## Statement of severity
This is a live race-universe correctness bug, not a one-off scrape issue. The race universe is the first truth gate in the daily pipeline (`THE_ONE_TRUTH.md` Steps 1-6) — every downstream artifact (passports, New Build/Old VELO scoring, Sigma, canonical scorecards, dashboard, learning) depends on the universe being complete before it runs. A silently incomplete universe makes every downstream "PASS" gate meaningless for that day, because the gates check internal consistency of the data they're given, not completeness against reality.

## Recommended follow-up (not in this PR)
Racing Post's `/racecards/{date}/runners-index/` page is an independent, RP-native list of every runner across every course for a given date. Adding it as a second-source cross-check inside `verify_raceday_universe.py` (the existing hardening-addendum gate) would catch this exact bug class automatically — comparing our derived URL-list venue/race count against RP's own index count — rather than relying on a human noticing "there should be 5 tracks, not 3." This is scoped as a separate, smaller follow-up mission, not part of this fix.

## Verification performed
- `tests/test_racecard_url_list_venue_classification.py`: 12/12 passed, including the new regression tests for `lingfield-aw`, `lingfield-aw-gb`, `wolverhampton-aw`, a guard test that all known AW tracks have their `-aw` slug present, and full end-to-end proof (rebuilding the URL list from the already-captured `index-2026-07-06-FINAL` index HTML produces exactly 36 races / empty international bucket / the expected 6 venue slugs), plus injection (`races_count=36`, `skipped_count=0`) and standard-cache (405 active runners) checks against the real regenerated July 06 artifacts.

## Classifications
URL_UNIVERSE_BUG_FIXED · LINGFIELD_AW_INCLUDED · LINGFIELD_AW_GB_INCLUDED · WOLVERHAMPTON_AW_INCLUDED · JULY06_UNIVERSE_36_RACES_CONFIRMED · JULY06_PASSPORT_FEED_405_RUNNERS_CONFIRMED · PASSPORT_COVERAGE_188_OF_405 · NO_SUPABASE_WRITES · NO_SCORING_RUN · NO_SIGMA_RERUN · NO_TELEGRAM · NO_MODEL_TRAINING · NO_PROMOTION · PR_REQUIRED_NOT_DIRECT_PUSH
