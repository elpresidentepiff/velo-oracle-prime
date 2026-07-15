# Manifest Gap Autopsy — 2026-07-14 (Phase 10, investigate-only, no repair)

## Symptom

`data/racing_post_account_raw/2026-07-14/manifest.json` records only **3**
captures (`924691`, `924692`, `924693` — all Longchamp), while the raw
capture directory holds **45** `.html` files (43 race pages + 2 course/index
pages). Step 10A (`build_rp_results_url_list.py`) trusted the manifest and
therefore produced only 3 results URLs; the operator worked around this by
extracting canonical URLs directly from all 45 HTML files via regex, which
is how the correct 43-race `rp_results_2026-07-14.txt` list was built (see
`race_day_14_race_universe_2026_07_14.csv` and `_evidence_import_manifest.json`
in `evidence_staging/2026-07-14/` for the reconstructed canonical-URL
inventory and per-file hashes).

## Root cause — proven from code, both committed and uncommitted

`scripts/ops/racing_post_account_collector.py`'s batch `capture` mode
(used by Steps 3 and 10B) writes the manifest with this logic (line numbers
refer to the **committed HEAD** version, `f095f4e`):

```python
captures_by_url = {
    item.get("source_url"): item
    for item in existing_captures + captures
    if item.get("source_url")
}
all_captures = [captures_by_url[url] for url in urls if url in captures_by_url]
```

`all_captures` is filtered down to only the URLs present in the **current
invocation's `urls` list** (loaded from whatever `--url-list` file was
passed to *this specific call*). `existing_captures` (read from the manifest
at the start of the call) are merged in, but then immediately dropped again
by the `if url in captures_by_url` filter unless they also happen to be in
the current call's URL list.

**Effect:** any invocation of `capture` whose `--url-list` is a strict
subset of a previous invocation's URL list will silently **truncate** the
manifest down to that subset — discarding the manifest records (not the
HTML files themselves, which are written unconditionally per-URL earlier in
the function) for every URL not in the current call. Given the observed
manifest content (exactly the 3 Longchamp URLs, with `started_at` timestamps
14:04:35–14:04:50 UTC), the most consistent explanation is that `capture`
was invoked at least twice against `data/racing_post_account_raw/2026-07-14/`
on 2026-07-14: an earlier, larger invocation produced all 45 HTML files, and
a later invocation — passed only the 3 Longchamp URLs (possibly a
supplementary/retry capture for that one card) — overwrote the manifest down
to those 3 entries. This mission does not have shell/command history to
prove the exact sequence of invocations; the code-path proof stands
independently of that sequence.

Contrast with `manual_capture` (used for Step 1 index capture), which is
correctly **append-only**:

```python
all_captures = existing_captures + [meta]
```

This function does not filter by a `urls` list because it only ever
processes one URL per call — it is not affected by the bug.

## The 2026-07-08 fix was real but incomplete

`ONE_TRUTH.md` records a 2026-07-08 fix ("manifest writes incremental+atomic
per capture"). The **uncommitted working-tree diff** for
`scripts/ops/racing_post_account_collector.py` (captured read-only via
`git diff HEAD` from the primary repo, preserved in this worktree's
provenance packet — see `provenance/UNCOMMITTED_RUNTIME_CODE_PROVENANCE.json`)
confirms a fix attempt exists but was **never committed**:

- Added `_atomic_write_json()` (temp file + `os.replace`) so a killed
  process can't leave `manifest.json` half-written/corrupted.
- Moved the manifest write **inside** the per-URL capture loop (so each
  successful capture is durably persisted immediately, not just at the end
  of the batch) — this addresses the "resume loses all progress" failure
  mode described in the diff's own comment (which the comment explicitly
  attributes to the 2026-07-08 passport-bank capture incident).
- **Did not touch** the `all_captures = [captures_by_url[u] for u in urls if
  u in captures_by_url]` line — the exact truncation-by-current-urls bug
  responsible for the 2026-07-14 3-entry manifest is present **unchanged**
  in both the committed and the uncommitted version of this file.

So: the atomicity/durability half of the 2026-07-08 fix was implemented
(uncommitted, sitting in the primary repo's dirty working tree as of this
mission), but the truncation bug that caused *this specific* 2026-07-14
incident is a different bug from the one the 2026-07-08 fix targeted, and it
remains unfixed in every version of the file this mission inspected.

## This is not an isolated incident

Cross-referencing every `data/racing_post_account_raw/*/manifest.json`
against its directory's `.html` file count (primary repo, read-only,
2026-07-14) shows the pattern recurs, with severity ranging from a
consistent and likely benign off-by-one (html_count = manifest_entries + 1,
almost certainly the course/index page skipped for `manual_capture`
elsewhere) up to severe truncation matching this bug:

| Directory | HTML files | Manifest entries | Gap |
|---|---|---|---|
| 2026-07-07 | 36 | 35 | 1 (benign pattern) |
| 2026-07-08 | 26 | 25 | 1 (benign pattern) |
| 2026-07-09 | 41 | 40 | 1 (benign pattern) |
| 2026-07-10 | 51 | 50 | 1 (benign pattern) |
| 2026-07-11 | 59 | 58 | 1 (benign pattern) |
| 2026-07-12 | 23 | 22 | 1 (benign pattern) |
| **2026-07-13** | **54** | **36** | **18 (severe)** |
| **2026-07-14** | **45** | **3** | **42 (severe)** |
| live-full-racepages-2026-06-28 | 30 | 7 | 23 (severe) |
| passport-backfill-2026-07-06 | 186 | 180 | 6 (moderate) |
| **rp-results-2026-06-28** | **32** | **2** | **30 (severe)** |
| rp-results-2026-07-04-final | 51 | 52 | -1 (manifest has extra — different failure mode, not investigated here) |
| rp-results-2026-07-08 | 45 | 33 | 12 (moderate/severe) |

The 2026-07-14 racecard directory is the worst single-day case on record for
racecard captures; 2026-07-13 (the immediately preceding day) shows the same
severe pattern, suggesting the truncation bug has been live for at least the
last two race days at time of this mission, independent of the operator's
successful same-day HTML-regex workaround.

**Note on 2026-07-14 results directory**: `rp-results-2026-07-14/` (Step
10B, the results capture used by Step 11/12) shows html=43, manifest
entries=44 (i.e. manifest has *one more* entry than HTML race pages — likely
because it also recorded a course/index capture correctly and was captured
in a single unbroken invocation) — so the truncation bug did **not** recur
on the results side that evening; only the racecard side manifest was
affected. This is consistent with Sigma (Step 12) correctly evaluating all
43 results despite the racecard-side manifest defect, because Step 11/12
consume the RP results capture (built from the operator's manually
reconstructed 43-URL list), not the defective racecard manifest.

## Whether result completeness relied on fallback rather than canonical manifest truth

**Yes, explicitly.** `data/racing_post_url_lists/rp_results_2026-07-14.txt`
(43 URLs) was NOT built by the canonical Step 10A path
(`build_rp_results_url_list.py`, which reads `manifest.json` and would have
emitted only 3 URLs given the defect). It was built by an operator-run
regex extraction directly against the 45 raw HTML files' `<link
rel="canonical">` tags. This fallback is why Sigma, Mission Control, Council,
and nightly learning for 2026-07-14 all reflect the full 43-race day rather
than a silently-truncated 3-race day — but it means the day's result
completeness currently rests on a **manual, undocumented, non-repeatable**
workaround rather than the pipeline's own canonical Step 10A output. Had the
operator not caught and manually corrected this, Step 10A/10B/11/12 would
have silently proceeded on a 3-race sample, and Mission Control's
`source_truth: RP_MERGED_CLEAN` classification would have been **wrong**
for the day (it was only made correct by the manual intervention this
mission is now auditing).

## Repair recommendation (NOT implemented in this mission)

1. **Fix the truncation bug**, not just add atomicity: change
   `all_captures = [captures_by_url[u] for u in urls if u in captures_by_url]`
   to something that is *union*, not filter-by-current-batch, e.g.:
   ```python
   all_captures = list(captures_by_url.values())  # union of existing + new, never drops prior URLs
   ```
   (Optionally re-sort by original capture order/timestamp if a stable
   ordering is required downstream.) This makes the manifest genuinely
   append-only/union-safe across however many separate `capture` invocations
   target the same `day_dir`, matching `manual_capture`'s already-correct
   behavior.
2. **Commit the existing uncommitted atomic-write fix** (`_atomic_write_json`,
   per-capture incremental persistence) alongside the above — it is a real,
   independent improvement and should not be lost as uncommitted work in a
   422-file-dirty working tree.
3. **Add a manifest-vs-directory consistency check** as a hard gate before
   Step 10A runs: compare `len([f for f in day_dir.glob("*.html")])` against
   `manifest["url_count"]`; if they disagree, fail loudly (raise) rather than
   silently proceeding to build a truncated results URL list. This would
   have caught the 2026-07-14 (and 2026-07-13) incidents automatically
   instead of relying on operator vigilance.

## Regression-test specification for a later mission (NOT implemented here)

A test module (e.g. `tests/ops/test_racing_post_account_collector_manifest.py`)
should assert, using a fake/mocked Playwright page:

1. **Union-not-filter**: call `capture_urls()` twice against the same
   `day_dir`, with the second call's `--url-list` a strict subset of the
   first's URLs. Assert the resulting `manifest.json["captures"]` contains
   entries for the UNION of both calls' URLs (i.e. the count from call 1 is
   preserved after call 2 runs), not just the second call's subset.
2. **Atomicity**: simulate a process kill mid-write (e.g. monkeypatch
   `_atomic_write_json` to raise after the temp file is written but before
   `os.replace`) and assert the pre-existing `manifest.json` on disk is
   unchanged (not zero-length, not partially written).
3. **Directory-vs-manifest consistency gate**: assert `build_rp_results_url_list.py`
   (or an equivalent guard) raises/fails loudly when
   `len(list(day_dir.glob("*.html"))) != manifest["url_count"]`, rather than
   silently emitting a truncated URL list.
4. **Regression fixture**: replay the exact 2026-07-14 scenario (45 HTML
   files present, 3-entry manifest) as a fixture and assert the new gate (3)
   fires `FAIL`/raises rather than `PASS`-ing through to Step 10A/10B.

## Aside — unrelated tooling debt (logged, not investigated)

A Claude memory-plugin error was observed during this mission: `Module not
found ... claude-mem/.../worker-service.cjs`. This is unrelated to the VÉLØ
pipeline or the manifest bug above and is recorded here only per the mission
brief's instruction to log it as an aside. No action taken.
