# Race Day 15 — Manifest Truncation Recurrence Check (Phase 9, v2 — CORRECTED)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. **Revision v2** — supersedes the v1 finding `NOT_RECURRED_ON_2026-07-15`, which the operator correctly identified as logically reversed: v1 used the post-fallback `races_parsed=47` counter as evidence the original manifest was complete, when that counter was itself produced only after some (unproven-in-v1) fallback reconstruction had already occurred.

## Corrected classification

**`MANIFEST_TRUNCATION_CONFIRMED_RECURRING_ROOT_CAUSE_LOCATED`**

The truncation recurred on 2026-07-15, and this revision locates its exact cause in code, not merely by counter comparison.

## Evidence, reconstructed from the original files (not from post-fallback counters)

| Artifact | Finding |
|---|---|
| `data/racing_post_account_raw/2026-07-15/manifest.json` (final on-disk state) | `url_count=9`, `latest_url_count=9`, 9 `captures`, **all 9 are Happy Valley** (`generated_at=2026-07-15T14:05:19.623446Z`) |
| Raw HTML files physically on disk in the same directory | **49 total**: 40 non-Happy-Valley + 9 Happy Valley — every one of the 40 UK/IRE files that the manifest's bookkeeping lost is still present on disk, untouched |
| `data/racing_post_url_lists/rp_racecards_2026-07-15.txt` (Step 3 input) | 38 UK/IRE URLs |
| `data/racing_post_url_lists/rp_racecards_2026-07-15_intl.txt` (Step 3.5 input) | 9 Happy Valley URLs |
| `run_full_raceday_cron.log`, 2026-07-15 block | Step 3 (`--url-list rp_racecards_2026-07-15.txt`) runs, THEN Step 3.5 (`--url-list rp_racecards_2026-07-15_intl.txt`) runs — both invoke `racing_post_account_collector.py capture --date 2026-07-15`, both target the identical output directory `data/racing_post_account_raw/2026-07-15/`, and therefore both read and write the identical `manifest.json` |

## Root cause, located in code

`scripts/ops/racing_post_account_collector.py`, function `capture_urls()`, lines 329-334:

```python
captures_by_url = {
    item.get("source_url"): item
    for item in existing_captures + captures
    if item.get("source_url")
}
all_captures = [captures_by_url[u] for u in urls if u in captures_by_url]
```

`existing_captures` is loaded correctly from the manifest already on disk at the start of each invocation (Step 3.5 does load Step 3's 40 prior captures into `captures_by_url`). But the final line, `all_captures = [captures_by_url[u] for u in urls if u in captures_by_url]`, filters strictly by membership in **the current invocation's own `urls` list** — when Step 3.5 runs with its 9-URL Happy Valley list, none of Step 3's 40 UK/IRE URLs are members of that list, so all 40 are silently dropped from the manifest that gets written to disk. This happens on every capture within the run (the comment at line 321-328 explains the manifest is rewritten after every single capture, not just once at the end), so by the time Step 3.5 finishes its 9th and final capture, the manifest has been fully overwritten down to 9 entries.

This is the **same class of defect** PR #150 documented for 2026-07-14 (a filtering step discarding earlier captures) recurring in a different call site: two sequential collector invocations sharing one output directory/manifest, where the second invocation's own url-scoped filter — not a deliberate content moderation/quality filter — destroys the first invocation's bookkeeping. Nothing was lost at the raw-capture layer (all 49 HTML files remain on disk); only the manifest's index of what was captured was corrupted.

## Why the final results file still shows 47 races

`rp_results_2026_07_15.json` (47 races, 7 courses, 0 parse errors) does **not** derive from the truncated 9-entry racecard manifest. `scripts/ops/build_rp_results_url_list.py`'s `_find_manifest()` function, given `--date 2026-07-15`, can only resolve to `data/racing_post_account_raw/2026-07-15/manifest.json` (no `live-full-racepages-2026-07-15*` directory exists) — i.e. the same truncated, 9-entry, Happy-Valley-only manifest. A straightforward run of that script against that manifest would therefore have produced only 9 result URLs, not 47. Yet `data/racing_post_url_lists/rp_results_2026-07-15.txt` on disk has 47 entries across all 7 courses. **This proves the 47-URL results list was not produced by the standard automated path** — some other reconstruction occurred, consistent with the operator's own firsthand account of directly observing a manual rebuild of the URL list from the raw HTML files' canonical links (which, as noted, were never deleted and remained fully available for exactly this kind of recovery).

## What remains open (explicitly, not glossed over)

- The exact command or script that performed the reconstruction (rebuilding 47 URLs from the raw HTML canonical links) was **not found in any log copied into this mission's evidence set** — `run_full_raceday_cron.log`'s 2026-07-15 block shows only the standard Step 1-9.6 sequence, which does not include a second, corrective URL-list build. This is consistent with the reconstruction having been a manual, off-pipeline operator action (matching the operator's own account of directly observing it happen live), not an automated recovery step.
- No intermediate, pre-Step-3.5, 40-entry version of `manifest.json` was preserved as a separate file to hash directly — its prior existence is inferred from (a) the collector script's own atomic-write-after-every-capture behavior (meaning a 40-entry manifest necessarily existed on disk for the full duration between Step 3 finishing and Step 3.5 starting), and (b) the 40 raw HTML files' own capture timestamps in the URL-keyed metadata sidecars, not from a captured snapshot of the manifest itself at that moment.

## Repair / regression-test specification (NOT implemented in this evidence mission)

1. **Root fix**: `capture_urls()` must not silently drop `existing_captures` entries whose URL is absent from the current invocation's `urls` list. The correct behavior is a true union/merge — `all_captures` should include every entry in `captures_by_url`, not just those filtered to the current call's own URL scope. If a distinction between "captured by this invocation" and "captured previously" is needed downstream, add an explicit field (e.g. `captured_by_invocation: bool`) rather than silently dropping rows.
2. Add a regression test that runs `capture_urls()` (or a mocked equivalent) twice in sequence against the same `output_dir`/`capture_date` with two disjoint URL lists (mirroring Step 3 + Step 3.5 exactly), and asserts the final manifest's `captures` list contains the union of both invocations' URLs, not just the second's.
3. Add a same-run consistency check comparing `len(manifest.captures)` against the actual count of `.html` files present in the same directory; fail loudly if they diverge (this would have caught the 9-vs-49 discrepancy same-day instead of requiring a later forensic reconstruction).
4. Preserve intermediate manifest states (e.g. write a timestamped copy before each new collector invocation touches an existing manifest) so future forensic missions do not need to infer intermediate states from indirect evidence.
5. Investigate and document whatever manual/ad-hoc process rebuilt `rp_results_2026-07-15.txt` from raw HTML canonical links, and consider promoting it to a first-class, logged, automated fallback step rather than leaving it as an undocumented manual recovery action.
