# Race Day 15 — Manifest Truncation Recurrence Check (Phase 9)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01.

## Background

PR #150 (`RACE-DAY-14-BEST-DAY-PROOF-01`, merged/open at commit `313d40c`) proved a manifest-truncation root cause for 2026-07-14: a filtering step discarded earlier capture attempts, and the PR states the root cause "recurs across 4+ other capture directories." This mission was asked to independently confirm whether the same pattern recurred on 2026-07-15, using the specific example cited in the mission brief: "nine Happy Valley entries while 47 races were captured."

## What was independently checked for 2026-07-15

```
data/racing_post_account_raw/2026-07-15/manifest.json:
  url_count: 9
  latest_url_count: 9
  captures: 9 entries, all status=PASS, all Happy Valley (race_ids 924710-924718)

data/results/rp_results_2026_07_15.json:
  races_parsed: 47
  parse_errors: 0
  results[] course breakdown: Happy Valley=9, Catterick=6, Uttoxeter=7, Bath=6,
                               Yarmouth=6, Lingfield=6, Killarney=7  (sum=47)
```

Every Happy Valley race in the results file (9 of them, race_ids 924710 through 924718, off-times 11:30 through 15:50 local) has a matching raw HTML capture in `data/racing_post_account_raw/2026-07-15/`, and every capture in the manifest has `status: "PASS"`. `url_count` and `latest_url_count` both equal 9 with zero discrepancy, and `parse_errors: 0` across the full 47-race results file.

## Finding

**Not reproduced on 2026-07-15.** Nine Happy Valley entries in today's manifest is not evidence of truncation — it appears to be the genuine, complete size of today's Happy Valley card (9 consecutive race_ids, 9 captures, 9 parsed results, 0 gaps, 0 parse errors). This differs from the PR #150 finding for 2026-07-14, where the manifest was shown to have discarded earlier capture attempts through a specific filtering line (not re-derived in this mission; treated as PR #150's established prior finding, not independently re-audited here since it concerns a different date's raw captures which were not part of this mission's evidence set).

This mission did **not** find the truncation bug firing on 2026-07-15's Happy Valley meeting specifically. It should **not** be reported as "confirmed recurring on 2026-07-15" — that would misstate the evidence. What can be said: the underlying fragile filtering pattern documented in PR #150 was not re-verified as fixed in code during this mission (no code changes were made or inspected for a fix commit between `313d40c` and `aef6305`), so the *latent risk* of recurrence under different meeting-count or capture-retry conditions remains open, even though today's specific 9-race Happy Valley capture happens to be complete.

## Requested breakdown (from the mission brief), as far as it could be reconstructed from available evidence

- **Pre-existing manifest state**: not available — `data/racing_post_account_raw/2026-07-15/manifest.json` as captured contains only the final 9-entry state; no intermediate/pre-filter manifest snapshot was preserved for 2026-07-15 in the primary repo's working tree at the time of evidence collection.
- **Each collector invocation**: `run_full_raceday_cron.log` shows Steps 1-3.5 (racecard index capture, URL list build, individual racecard page capture, supplementary intl-classified capture) each ran once for 2026-07-15, consistent with a single collector pass, not multiple retried passes that might have needed de-duplication.
- **URL list passed per invocation**: `data/racing_post_url_lists/rp_racecards_2026-07-15*.txt` were not included in this mission's evidence_staging set (out of the file list explicitly required by the mission's Phase 0 evidence list) and were not separately hashed; a follow-up pass should pull these in for a byte-level URL-count cross-check.
- **Merged records before/after filtering, raw HTML count, unique canonical URL count**: `html_files_seen: 47`, `racecard_indexed: 47`, `readiness_indexed: 47`, `races_parsed: 47`, `parse_errors: 0` in `rp_results_2026_07_15.json` — all four counters agree exactly, which is itself evidence against a filtering discrepancy on 2026-07-15 (a truncation bug would typically show `html_files_seen` exceeding `races_parsed`, or a manifest `url_count` lower than the actual capture count; neither pattern is present here).

## Conclusion

**Classification: `NOT_RECURRED_ON_2026-07-15` (for the specific Happy Valley example cited).** The known filtering defect from PR #150 is not proven to have fired again on this date. The code path that caused it in PR #150's investigation was not independently re-audited in this mission (out of the evidence scope defined for Phase 0), so this should be read as "not observed today," not "proven fixed." A dedicated regression test replaying PR #150's specific failure scenario against the current code at `aef6305` (and future commits) is the correct way to close this gap permanently — see repair specification below.

## Repair / regression-test specification (NOT implemented in this evidence mission)

1. Pull PR #150's root-cause commit/diff and confirm whether the specific filtering line it identified is still present, unchanged, fixed, or removed at `aef6305` and at the primary repo's current dirty `HEAD`.
2. Add a regression test that feeds a synthetic multi-attempt capture manifest (simulating retries/partial failures) through the same merge/filter code path PR #150 diagnosed, and asserts the final manifest's race count matches the true race-card count, not merely the last successful attempt's count.
3. Add a same-day CI-style check (already partially present via the `html_files_seen == races_parsed == parse_errors:0` triad in `rp_results_*.json`) that fails loudly, rather than silently, if any of the four counters (`html_files_seen`, `racecard_indexed`, `readiness_indexed`, `races_parsed`) diverge for a given date.
4. Preserve pre-filter manifest snapshots (not just the final merged manifest) for at least 7 days, so future forensic missions can reconstruct the "before filtering" state without needing to catch the bug live.
