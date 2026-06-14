# VÉLØ Oracle Prime — Complete Pipeline Specification

**Version:** 2026-06-06  
**Status:** CANONICAL TRUTH — follow this document exactly

This document specifies every file, every script, every data transformation in VÉLØ from raw capture to scored output. Gemini: read every section before taking any action. Violation of any step ordering or field contract causes silent failures that cost a race day.

---

## PART 1: SYSTEM OVERVIEW

VÉLØ runs two parallel scoring pipelines that share the same raw capture source:

```
CAPTURE SOURCE
    └─> PARSE        (parse_racing_post_racecard_capture.py)
         ├─> injection JSON  ──> OLD VELO (SQPE scorer)
         └─> standard cache  ──> NEW BUILD (ML scorer)
```

Both pipelines require the same capture data to be present and valid before any scoring begins.

---

## PART 2: CANONICAL DATA ROOTS

```
velo-oracle-prime/
  data/
    racing_post_account_raw/          # RAW: captured HTML per label
    racing_post_account_parsed/       # PARSED: injection JSON per label
    racecard_merged/                  # MERGED: per-venue files for Old VELO
    racecards_{date_tag}_standard.json # STANDARD CACHE: for New Build feed
    velo_prime_verdicts_{date}.json   # OLD VELO: local verdict output
    new_build/
      current_cards/
        current_card_passport_feed_latest.jsonl  # NEW BUILD: passport feed
      reports/
        two_lane_readiness_{date}.json           # NEW BUILD: readiness report
    reports/
      race_day_button_{date}_latest.json         # BUTTON: full run report
      race_day_button_{date}_latest.md           # BUTTON: human-readable report
```

---

## PART 3: STEP 0 — RAW CAPTURE

**Action:** Human operator runs the RP account collector to capture HTML pages.

**Output directory:** `data/racing_post_account_raw/{label}/`  
**Label format:** `live-full-racepages-{YYYY-MM-DD}` (base) or `live-full-racepages-{YYYY-MM-DD}-refresh2` (updated)

**Critical rule:** If you captured the card early in the day, times may be preliminary. A `-refresh2` label is a re-capture with corrected times. The pipeline MUST use the most recent (refresh) label.

**Auto-detection (ENFORCED in button):**  
`_best_capture_label(date)` sorts all folders matching `live-full-racepages-{date}*` by name length descending. Longer names are more specific (refresh2 > refresh > base). This auto-selects the best label. If operator passes `--capture-label` explicitly, that overrides auto-detection.

**Failure mode:** Using base label when refresh2 exists → stale race times → wrong British time keys → races missing from scoring.

---

## PART 4: STEP 1 — PARSE HTML TO INJECTION JSON

**Script:** `scripts/ops/parse_racing_post_racecard_capture.py`

**Invocation:**
```bash
python scripts/ops/parse_racing_post_racecard_capture.py \
  --date 2026-06-06 \
  --capture-label live-full-racepages-2026-06-06-refresh2 \
  --write-standard-cache \
  --execute
```

**What it does (line by line):**
1. `_resolve_capture_dir(date, capture_label)` → resolves `data/racing_post_account_raw/{label}/`
2. For each `.html` file in that folder:
   - `_load_next_data(html_path)` → extracts `<script id="__NEXT_DATA__">` JSON blob
   - `_get_race_page_data(next_data)` → navigates `props.pageProps.initialState.racePage.data`
   - `_normalise_race(race_page, html_path, capture)` → extracts race fields
3. `_normalise_race` produces the injection race dict with:
   - `race_time`: ISO timestamp from `race.raceTime` (e.g. `"2026-06-06T17:10:00"`)
   - `off_time`: `race.startTime` (already `"HH:MM"`) or `_extract_off_time(race_time)` as fallback
   - `course`: from `race.courseStyleName` or `race.courseName`
   - `runners[]`: each runner via `_normalise_runner()`

**Output — injection JSON:** `data/racing_post_account_parsed/{label}/racecard_injection.json`
```json
{
  "races": [
    {
      "race_id": 920070,
      "course": "Chepstow",
      "race_time": "2026-06-06T17:10:00",
      "off_time": "17:10",
      "runners": [...]
    }
  ]
}
```

**Output — standard cache (with `--write-standard-cache`):** `data/racecards_{date_tag}_standard.json`
- Produced by `_injection_race_to_standard()` which reads `race.get("race_time")` and calls `_extract_off_time()`
- This is the feed source for New Build

**CRITICAL FIELD: `off_time`**
- Must be `"HH:MM"` string for every race
- `None` off_time in injection → `to_off_time_key()` fails in build_racecard_merged → race missing from Old VELO
- `None` off_time in standard cache → `off_time` key `None` in feed → New Build passport feed broken
- The bug from 2026-06-06: `_normalise_race` was only storing `race_time` (ISO) but not computing `off_time`
- Fix: line 175 of parser now has `"off_time": race.get("startTime") or _extract_off_time(race.get("raceTime"))`

---

## PART 5: STEP 1B — PREFLIGHT INJECTION GATE

**Enforced in:** `velo_race_day_button.py` — runs immediately after parse, before any scoring.

**Function:** `_preflight_injection_gate(injection_path, date)`

**Checks:**
1. `INJECTION_MISSING`: injection file does not exist at expected path
2. `INJECTION_EMPTY`: `races` array is empty
3. `OFF_TIME_NULL`: any race has `off_time == None` → blocks scoring
4. `COURSE_COUNT_LOW`: fewer than 3 unique courses → likely partial/stale capture

**Behavior:** Any failure → `return 1` immediately. All subsequent steps (build_rp_merged, old_velo_engine, new_build_score) are skipped. Report written with `classification: RACE_DAY_BUTTON_PARTIAL`.

---

## PART 6: STEP 2 — BUILD RACECARD MERGED (OLD VELO INPUT)

**Script:** `scripts/ops/build_racecard_merged_from_injection.py`

**Input:** `data/racing_post_account_parsed/{label}/racecard_injection.json`

**What it does (line by line):**
1. Reads injection JSON, iterates races
2. Groups races by course
3. For each race:
   - `to_off_time_key(race["race_time"])` → converts ISO timestamp to British display time
   - British time key format: `H.MM` (12-hour, e.g. `"5.10"` for 17:10, `"2.30"` for 14:30)
   - Creates race dict keyed by this time string
4. Writes one file per venue: `data/racecard_merged/racecard_{VEN}_{date}.json`
   - Venue codes: `VENUE_CODE_MAP` dict (chepstow → CHP, ascot → ASC, etc.)

**Output per venue:**
```json
{
  "venue": "Chepstow",
  "venue_code": "CHP",
  "date": "2026-06-06",
  "races": {
    "5.10": { "course": "Chepstow", "off": "5.10", "horses": [...] },
    "5.47": { ... }
  }
}
```

**Failure mode:** If `race_time` is ISO but `off_time` in injection is None, `to_off_time_key` still works (uses race_time). But if race_time is also absent → race has time key `""` or error.

---

## PART 7: STEP 3 — OLD VELO ENGINE (SQPE SCORER)

**Script:** `scripts/ops/run_prime_today.py`

**Invocation from button:**
```bash
python scripts/ops/run_prime_today.py \
  --date 2026-06-06 \
  --source rp \
  --no-notify \
  (with VELO_FORCE_CARD=1)
```

**Source path:** `src/velo/racecard_loader.py`

**Source priority in racecard_loader (line by line):**
1. Standard cache: `data/racecards_{date_tag}_standard.json` if exists
   - `_iter_standard_cache_racecard()`: detects injection format by checking if races have `race_time` field
2. RP merged: `data/racecard_merged/racecard_*_{date}.json`
   - `_iter_rp_merged_racecard()`: reads per-venue files
3. Racing API: HTTP call to racing-api.com

**Source truth labels** (written to observability packet):
- `RP_MERGED_CLEAN`: merged files loaded, all fields present
- `RP_MERGED_DEGRADED`: merged files loaded but RPR or other fields missing
- `API_CLEAN`: fell back to Racing API
- `LOCAL_JSON_FALLBACK`: emergency local JSON fallback

**Output — local verdicts:** `data/velo_prime_verdicts_{date}.json`  
**Output — Supabase:** `velo_verdicts` table (when `--no-notify` NOT present and persistence not blocked)  
**Output — observability:** `data/velo_run_observability_{date}_{run_id}.json`

**HARD RULES (NEVER VIOLATE):**
- `--no-notify` is ALWAYS passed from button (no Telegram during button run)
- `VELO_FORCE_CARD=1` is set to bypass certain race-day timing gates
- No live staking. No model training. No SQPE changes.

---

## PART 8: STEP 4 — NEW BUILD CURRENT CARD FEED

**Script:** `scripts/ops/new_build_current_card_feed.py`  
**Module:** `new_build_velo/current_card_feed.py`

**Invocation from button:**
```bash
python scripts/ops/new_build_current_card_feed.py \
  --racecard-path data/racecards_{date_tag}_standard.json \
  --execute
```

**What it does (line by line):**
1. If `--racecard-path` provided: reads standard cache → `_iter_standard_cache_racecard(path)`
2. Otherwise: scans `data/racing_post_account_parsed/*/racecard_injection.json` for recent files
3. For each race in the feed source:
   - Builds a "passport" dict per runner
   - `off_time` read from: `race.get("race_time")` in injection format (note: field is called `race_time` in injection, value is ISO timestamp — `off_time` field is separate)
   - Line 426: `"off_time": race.get("race_time")` — this reads the ISO timestamp into the off_time slot of the feed. Dashboard `_fmt_time()` handles both ISO and British dot-time.
4. Writes: `data/new_build/current_cards/current_card_passport_feed_latest.jsonl`

**Failure mode:** If standard cache missing (parse not run) → empty feed → two_lane_score fails with 0 races.

---

## PART 9: STEP 5 — NEW BUILD TWO-LANE SCORER

**Script:** `scripts/ops/new_build_two_lane_score.py`  
**Module:** `new_build_velo/two_lane_scorer.py`

**Invocation from button:**
```bash
python scripts/ops/new_build_two_lane_score.py \
  --date 2026-06-06 \
  --execute
```

**Reads:** `data/new_build/current_cards/current_card_passport_feed_latest.jsonl`

**Produces:**
- `data/new_build/reports/two_lane_readiness_{date}.json`
- Fields: `overall_status`, `races_scored`, `runners_scored`, `operational_lane`, `rpr_violations`, `sp_violations`

**Lane selection:**
- `LANE_A_CORE_PASSPORT`: primary ML scorer (Challenger V1, 45-feature)
- `LANE_B_FALLBACK`: fallback scorer

**Observability fields in readiness report:**
- `overall_status`: "READY" or "FAIL"
- `races_scored`: integer count
- `runners_scored`: integer count
- `intent_coverage`: fraction of runners with intent signal

---

## PART 10: THE BUTTON — CANONICAL INVOCATION

**Script:** `scripts/ops/velo_race_day_button.py`

**Full invocation (normal day, from scratch):**
```bash
PYTHONPATH=. PYTHONUTF8=1 python3 scripts/ops/velo_race_day_button.py \
  --date 2026-06-06
```
The button will auto-detect the best capture label via `_best_capture_label()`.

**If re-running after a manual parse:**
```bash
PYTHONPATH=. PYTHONUTF8=1 python3 scripts/ops/velo_race_day_button.py \
  --date 2026-06-06 \
  --no-parse
```

**If forcing a specific label:**
```bash
PYTHONPATH=. PYTHONUTF8=1 python3 scripts/ops/velo_race_day_button.py \
  --date 2026-06-06 \
  --capture-label live-full-racepages-2026-06-06-refresh2
```

**Step execution order:**
1. `parse_rp_card` (unless `--no-parse`)
2. `_preflight_injection_gate` — HARD BLOCK on failure
3. `build_rp_merged`
4. `old_velo_engine`
5. `new_build_feed`
6. `new_build_score`
7. Write report: `data/reports/race_day_button_{date}_latest.json`

**Classification:**
- `RACE_DAY_BUTTON_READY`: old_velo AND new_build_score both exit 0
- `RACE_DAY_BUTTON_PARTIAL`: any step failed

---

## PART 11: LEARNING PIPELINE (POST-RACE)

**Runs after results are available (evening).**

**Step 1 — Capture results:**  
`scripts/ops/new_build_capture_results.py --date 2026-06-06`  
Output: `data/new_build/results/results_{date}.json`

**Step 2 — Sigma (Old VELO):**  
`scripts/ops/run_results_sigma.py --date 2026-06-06`  
Reads verdicts + results, writes sigma stats, updates learning corpus.

**Step 3 — EOD Shadow Learning Bridge:**  
`scripts/ops/eod_shadow_learning_bridge.py --date 2026-06-06`  
Writes corpus rows for model improvement.

**Step 4 — Innovation Protocol:**  
`scripts/ops/build_innovation_protocol.py --date 2026-06-06`  
Identifies improvement opportunities from run.

**Step 5 — Router Shadow Audit:**  
`scripts/ops/router_shadow_audit.py`  
Validates signal routing is consistent.

**Orchestration:** `scripts/ops/velo_daily_harness.py --date 2026-06-06 --mode close`

---

## PART 12: FAILURE MODES — FULL REGISTRY

| Failure | Symptom | Root cause | Guard |
|---------|---------|------------|-------|
| Wrong capture label | Course at wrong time / missing from dashboard | Button defaulted to base label when refresh2 existed | `_best_capture_label()` auto-selects refresh2 |
| `off_time` is None | Races missing from racecard_merged | `_normalise_race` didn't compute off_time | Parser line 175 fixed; preflight gate blocks |
| Standard cache missing | New Build feed empty, 0 races scored | `--write-standard-cache` not passed to parse | Button always passes it |
| Injection file missing | `build_rp_merged` fails immediately | Parse step failed silently | Preflight gate blocks |
| Low course count | Partial race day scored | Capture folder has only 1-2 courses | Preflight gate warns if <3 courses |
| RPR None for all runners | `RP_MERGED_DEGRADED` source truth | RPR field name changed (was `rpr`, now `RPR_ACCEPTED`) | `rpr_policy: RPR_ACCEPTED` in loader |

---

## PART 13: TEST SUITE

**Existing tests (relevant to button flow):**
- `tests/test_button_preflight.py` — 14 tests for `_best_capture_label` and `_preflight_injection_gate`
- `tests/test_racecard_cache_gate.py` — racecard completeness gate
- `tests/test_new_build_current_card_feed.py` — feed builder
- `tests/test_new_build_paper_scorer.py` — paper scorer
- `tests/test_live_passport_feed.py` — live passport feed

**Run all preflight tests:**
```bash
PYTHONPATH=. python3 -m pytest tests/test_button_preflight.py -v
```

---

## PART 14: OBSERVABILITY CONTRACTS

**Old VELO run observability:** `data/velo_run_observability_{date}_{run_id}.json`  
Schema: `VELO_OBSERVABILITY_CONTRACT_V1` (schema_version: "1.1.0")  
Mandatory fields: `source_truth`, `feature_health`, `active_formula`, `race_scoring_coverage_pct`, `persistence_status`, `supabase_write_attempt_success`, `decision_tier_status`, `learning_gate`, `next_safe_command`

**New Build readiness:** `data/new_build/reports/two_lane_readiness_{date}.json`  
Fields: `overall_status`, `races_scored`, `runners_scored`, `operational_lane`

**Button report:** `data/reports/race_day_button_{date}_latest.json`  
Fields: `classification` (READY/PARTIAL), `old_velo.status`, `new_build.races_scored`, `steps[]`

---

## PART 15: HARD RULES — NEVER VIOLATE

1. **No live staking** — paper only until explicitly authorized
2. **No model training** from button — training is a separate controlled process
3. **No SQPE changes** from button — formula is locked
4. **No router changes** from button
5. **--no-notify always passed** from button to old VELO (prevents Telegram during batch run)
6. **Standard cache always written** — `--write-standard-cache` always passed to parse
7. **Preflight gate must pass** before any scoring — no override flag exists by design
8. **capture_label auto-detected** — always selects most recent (longest) label unless overridden

---

## PART 16: KEY FILE-TO-FIELD MAPPING

| Data file | Key field | Source in RP HTML | Format |
|-----------|-----------|-------------------|--------|
| injection JSON | `race_time` | `race.raceTime` | ISO timestamp `"2026-06-06T17:10:00"` |
| injection JSON | `off_time` | `race.startTime` | `"HH:MM"` e.g. `"17:10"` |
| racecard_merged | time key | `to_off_time_key(race_time)` | British `"H.MM"` e.g. `"5.10"` |
| standard cache | `off_time` | `_extract_off_time(race_time)` | `"HH:MM"` |
| passport feed | `off_time` | injection `race_time` (ISO) | ISO (dashboard `_fmt_time()` handles both) |
| verdicts | `off_time` | racecard_merged time key | British `"H.MM"` |

---

## PART 17: CANONICAL RUN COMMAND FOR TODAY

```bash
cd /c/Users/puror/velo-oracle-prime
PYTHONPATH=. PYTHONUTF8=1 python3 scripts/ops/velo_race_day_button.py --date $(date +%Y-%m-%d)
```

On Windows (PowerShell):
```powershell
$date = Get-Date -Format "yyyy-MM-dd"
# Use Bash tool: PYTHONPATH=. PYTHONUTF8=1 python3 scripts/ops/velo_race_day_button.py --date $date
```

Expected terminal output on clean run:
```
[AUTO-LABEL] Detected refresh capture: using 'live-full-racepages-2026-06-06-refresh2' over base
[BUTTON] date=2026-06-06  capture_label=live-full-racepages-2026-06-06-refresh2
[PREFLIGHT GATE] ✓ PASS — injection OK: 49 races, 7 courses, all off_times present
classification: RACE_DAY_BUTTON_READY
```

Any other output → investigate before assuming success.
