# THE ONE TRUTH — VÉLØ ORACLE PRIME

**Written:** 2026-06-06
**Rule:** UK and Ireland only. Racing Post HTML only. No exceptions. No other data sources.

---

## YOU WAKE UP AND SAY: RUN THE ENGINE FOR TODAY

This is exactly what happens. Every step. Every file. Every check.

---

## COMPLETE EXECUTABLE CONTRACT — STEPS 1 TO 20

Every path in this table is committed to Git. Another agent must be able to
clone the branch and run the same contract. `FINAL_CAPTURE_LABEL` is selected
once after Step 3 and reused everywhere; downstream steps must not rediscover it.

| Step | Committed entrypoint | Status | Required input | Required proof/output |
|---|---|---|---|---|
| 1 | `scripts/ops/racing_post_account_collector.py manual-capture` | READY | Logged-in RP session | Index HTML over 100KB |
| 2 | `scripts/ops/build_racing_post_racecard_url_list.py` | READY | Index capture | UK/IRE-only deduplicated racecard URL list |
| 3 | `scripts/ops/racing_post_account_collector.py capture` | READY | Racecard URL list | Final race-page capture manifest and one HTML per race |
| 4 | `scripts/ops/parse_racing_post_racecard_capture.py` | READY | `FINAL_CAPTURE_LABEL` | Injection JSON and standard cache |
| 5 | `scripts/ops/validate_rp_injection.py` | READY | Exact injection from Step 4 | Unique race IDs, no null off-times, full card gate PASS |
| 6 | `scripts/ops/new_build_current_card_feed.py` | READY | Standard cache | Current-card passport feed |
| 7 | `scripts/ops/new_build_two_lane_score.py` | READY | Passport feed | Two-lane readiness report |
| 8 | `scripts/ops/ensure_old_velo_rp_newspaper_files.py` | READY / HARD GATE | RP Newspaper Form PDFs from local Downloads/incoming folders | Five engine PDFs per venue staged, `0010_XX` excluded, PDF-ingested Old VELO files written |
| 8.5 | `scripts/ops/build_rpdc_daily.py` | READY | Exact injection from Step 4 | Current-day RPDC rows with 100% race-ID coverage |
| 9 | `scripts/ops/run_prime_today.py` | READY | RP merged files and RPDC | 100% races scored/persisted and real `pipeline_runs` truth |
| 9.1 | `scripts/ops/run_radical_shadow_today.py` | SHADOW / PAPER ONLY | Same race day artifacts as Step 9 | Radical Shadow VELO report; never live execution |
| 9.2 | `scripts/ops/run_tri_lane_stress_test.py` | SHADOW / PAPER ONLY | Old VELO, New Build, Shadow artifacts | Tri-lane stress test report; never live execution |
| 9.3 | `scripts/ops/build_tri_lane_agent_review.py` | SHADOW / PAPER ONLY | Tri-lane stress test | Race-level agent review instructions |
| 9.4 | `scripts/ops/build_deep_race_agent_v1.py` | SHADOW / PAPER ONLY | RP racecard artifacts plus local evidence | Deep Race Agent gate cards |
| 9.5 | `scripts/ops/build_course_master.py` | SHADOW / CONTEXT ONLY | Course excellence table, Deep Agent eval, today's RP card | Course Master context; never alters scoring/staking |
| 9.6 | `scripts/ops/build_old_velo_three_option_card.py` | SHADOW / OPERATOR ONLY | Old VELO runner snapshots | Old VELO WIN / PLACE / LONGSHOT role card |
| 10A | `scripts/ops/build_rp_results_url_list.py` | READY | `FINAL_CAPTURE_LABEL` manifest | Deduplicated RP results URL list |
| 10B | `scripts/ops/racing_post_account_collector.py capture` | READY | Results URL list | Final results-page capture |
| 11 | `scripts/ops/parse_rp_results_capture.py` | READY | Final results capture | Canonical RP results JSON with numeric IDs and SP truth |
| 12 | `scripts/ops/run_results_sigma.py` | READY | Verdicts and canonical results | Sigma results including wins, frames, SR and frame rate |
| 13 | `scripts/ops/ingest_results_to_horse_runs.py` | READY | Canonical RP results | Supabase `racing_horse_runs` history |
| 14 | `scripts/ops/build_sigma_retrieval_corpus.py` | READY / FRESHNESS-GATED | Sigma audit dump | Retrieval corpus; `date_max` must include latest completed Sigma date |
| 15 | `scripts/ops/update_mission_control.py` | READY | Daily artifacts | Mission Control gate report |
| 16A | `scripts/audit/vp30_operator_card.py` | READY | Daily artifacts | VP30 operator card |
| 16B | `scripts/audit/run_velo_council.py` | READY | Council evidence packet | Council READY and `PASS_TO_LEARNING` |
| 17 | `scripts/ops/run_execution_bridge_shadow.py` | READY / SIM ONLY | Verdict/result truth | SIM-only paper ledger and outcome audit |
| 18 | `scripts/ops/build_innovation_protocol.py` | READY | Verdict/result truth | Deduplicated router evidence dataset |
| 19 | `scripts/ops/router_shadow_audit.py` | READY | Router evidence dataset | Lane audit, freeze state and ledger |
| 20 | `scripts/ops/nightly_eod_learning_runner.py` | READY / SHADOW ONLY | All prior gates PASS | Shadow-only learning artifacts and idempotency proof |

**Hard stop:** if any required script is absent from Git, any command exits
non-zero, or any required proof is missing, stop and announce the obstacle.

---

## STEP 1 — GET THE INDEX

**Why:** The agent does not know what races are on today. Racing Post has one page that lists every race. That is the starting point.

**What the agent does:**
Opens a logged-in Racing Post browser session (Playwright) and captures the main racecards page as an HTML file.

**Command:**
```
python scripts/ops/racing_post_account_collector.py manual-capture
  --date index-YYYY-MM-DD-FINAL
  --start-url https://www.racingpost.com/racecards
  --label rp-index
  --execute
```

**What lands on disk:**
`data/racing_post_account_raw/index-YYYY-MM-DD-FINAL/` — one HTML file, the Racing Post racecards index page.

**How you know it worked:**
File is bigger than 100KB. If it is 5KB the session has expired — Racing Post served a block page instead. Run init-login first.

---

## STEP 2 — BUILD THE URL LIST

**Why:** The index HTML contains links to every individual race page. The agent reads that HTML and extracts every race URL for today's date.

**The fix that matters:** The script uses broad regex directly on the raw HTML. It does NOT trust the JSON date keys inside the page. Reason: when you capture the index the night before, Racing Post stores tomorrow's races under today's date key in the internal JSON — but the race URLs themselves always contain the correct date. Broad regex finds those URLs regardless.

**Command:**
```
python scripts/ops/build_racing_post_racecard_url_list.py
  --date index-YYYY-MM-DD-FINAL
  --target-date YYYY-MM-DD
  --execute
```

**What lands on disk:**
`data/racing_post_url_lists/rp_racecards_YYYY-MM-DD.txt` — UK/IRE only, deduplicated by race ID
`data/racing_post_url_lists/rp_racecards_YYYY-MM-DD_intl.txt` — international URLs archived separately. Not fed to VELO. Kept for when international support is built.

**How you know it worked:**
Open the UK/IRE file. You must see at least 3 different tracks. Every URL must be a UK or Irish venue. Count must match the number of races running that day. If a track is missing go back and check the index capture. International file is written automatically — do not feed it into the capture command.

---

## STEP 3 — CAPTURE ALL RACE PAGES

**Why:** Each URL in the list is an individual race page on Racing Post. The agent opens every single one and saves the full HTML. This is the raw data. Every horse, every jockey, every weight, every form figure, every trainer stat, spotlight comment, newspaper tip — it is all inside that HTML.

**Command:**
```
python scripts/ops/racing_post_account_collector.py capture
  --url-list data/racing_post_url_lists/rp_racecards_YYYY-MM-DD.txt
  --date live-full-racepages-YYYY-MM-DD
  --batch-size 15
  --execute
```

Run with `--batch-size 15` to avoid tool timeouts. Run it again for the next 15. Keep going until all races are done. If you re-run on the same day add a suffix: base → -refresh → -refresh2. Record the exact final capture label and pass that same label/path to every downstream step.

**What lands on disk:**
`data/racing_post_account_raw/live-full-racepages-YYYY-MM-DD/` — one HTML file per race, one JSON metadata file per race.

**How you know it worked:**
Every HTML file must be bigger than 500KB. A 5KB file means that race page was blocked — session expired. Run init-login and re-capture those URLs.

---

## STEP 4 — PARSE THE HTML

**Why:** The raw HTML files are not structured data. The agent reads every HTML file and extracts the race data from the `__NEXT_DATA__` JSON blob that Racing Post bakes into every page. This gives you clean structured data: race time, going, distance, class, prize money, every horse with jockey, weight, form, official rating, RPR, topspeed, draw, trainer statistics, spotlight comments, newspaper tips.

**Command:**
```
python scripts/ops/parse_racing_post_racecard_capture.py
  --date YYYY-MM-DD
  --capture-label live-full-racepages-YYYY-MM-DD
  --write-standard-cache
  --execute
```

**What lands on disk — two files:**

**File 1 — The Injection JSON:**
`data/racing_post_account_parsed/live-full-racepages-YYYY-MM-DD/racecard_injection.json`
This is what Old VELO reads from. All races, all runners, every field.

**File 2 — The Standard Cache:**
`data/racecards_YYYY_MM_DD_standard.json`
This is what New Build reads from. Same data, slightly different shape.

**How you know it worked:**
Zero races with a null `off_time`. Every race has a time in HH:MM format (e.g. "14:30"). Number of races matches what you expected from the URL list.

---

## STEP 5 — PREFLIGHT GATE

**Why:** Before any scoring happens the system checks the injection data is clean. If the data is bad no scoring runs. This prevents verdicts being written from corrupt or partial data.

**What it checks:**
- Injection file exists
- At least 3 distinct courses present (fewer means partial capture)
- Every single race has an `off_time` — zero nulls allowed

**Command:**
```
python scripts/ops/validate_rp_injection.py
  --injection-path data/racing_post_account_parsed/FINAL_CAPTURE_LABEL/racecard_injection.json
```

This is a hard gate. If it exits non-zero, stop. Do not run New Build, RPDC, Old VELO, Council, or learning.

If it blocks, it tells you exactly why. Fix the data and re-run.

---

## STEP 6 — BUILD PASSPORT FEED (New Build scores first)

**Why:** New Build scores horses using their historical profile — everything that horse has done in past races. That profile is called a passport. Before New Build can score, the agent matches every runner on today's card to their passport.

**What the agent does:**
Reads the standard cache (today's runners). For each horse, looks up their passport in `data/new_build/passports/horse_passports_v1.jsonl`. Combines the race data with the passport data into one row per runner.

**Command:**
```
python scripts/ops/new_build_current_card_feed.py
  --racecard-path data/racecards_YYYY_MM_DD_standard.json
  --execute
```

**What lands on disk — dated, never overwritten:**
`data/new_build/current_cards/current_card_passport_feed_latest.jsonl` — always the most recent run
`data/new_build/current_cards/current_card_passport_feed_YYYY_MM_DD.jsonl` — dated archive, stays forever

**How you know it worked:**
The dated file exists with today's date. Courses match today's card — not yesterday's. Check `passport_found` count in the report — tells you how many horses have history in the system.

---

## STEP 7 — SCORE WITH NEW BUILD

**Why:** New Build scores every horse using the passport — which is the entire life of that horse. Every run it has ever had. Every result. Every performance metric across every surface, distance, going, and class. That history IS the signal. A horse with 20 runs tells you something. A horse with 2 runs tells you something different. A horse with no entry in the passport bank is unknown and cannot be fully scored.

The two-lane scorer uses that life history in two ways. Lane 1 uses only the features you know before the race — draw, weight, going, class. Lane 2 adds the full passport depth. If a horse has no passport, Lane 2 cannot fire for that horse and the report states this explicitly. The readiness report shows for every race whether it was scored at full depth, partial depth, or not at all — so you know exactly what you are working with.

**Command:**
```
python scripts/ops/new_build_two_lane_score.py
  --date YYYY-MM-DD
  --execute
```

**What lands on disk:**
`data/new_build/reports/two_lane_readiness_YYYY_MM_DD.json`
`data/new_build/reports/two_lane_readiness_YYYY_MM_DD.md`

---

## STEP 8 — GET AND INGEST OLD VELO RP NEWSPAPER FILES

**Why:** Old VELO was built to read Racing Post data in newspaper form. The engine source is the Racing Post `Newspaper Form` dropdown PDF pack, not the selection file and not a convenient injection fallback. The agent must first find/download/stage the RP newspaper PDFs, then ingest them into `data/racecard_merged/`, then score.

This is a hard source gate. If the five required files are not present for every venue, Old VELO scoring must stop and announce the missing files. Do not run `run_prime_today.py --source rp` from stale or injection-derived `racecard_merged` files and call it complete.

**Important correction — Newspaper Form dropdown files:**

Racing Post's race page has a `Newspaper Form` dropdown. The Old VELO newspaper-file feed must use the five engine-intelligence files per track/race day:

1. `0011_XX` — Postdata grid
2. `0012_XX` — Colour racecard
3. `0015_OR` — Official ratings/history sheet
4. `0016_XX` — Spotlight comments
5. `0032_TS` — Topspeed ratings

`0010_XX` is the selection box / competitor consensus file. It must not be fed into Old VELO as engine truth. It may be stored separately for competitor-comparison reporting only. The gate script records any `0010_XX` files it sees and excludes them.

**Each Old VELO race payload must contain engine facts from these sources:**

1. **Race info** — name, distance, going, class, prize money, surface, race type
2. **Postdata grid** — trainer form, going, distance, course, draw, ability, recent form factors
3. **Colour racecard facts** — runners, weights, jockey/trainer, OR, TS, RPR
4. **Official ratings/history** — OR movement, historical marks, best winning ratings
5. **Spotlight and Topspeed** — runner comments plus condition-specific speed figures

Every runner in every race also carries: horse name, jockey, trainer, weight, draw, form figures, official rating, RPR, topspeed, days since last run, spotlight comment, headgear, wind surgery flag.

**Competitor comparison rule:** `0010_XX` can be parsed into a separate competitor-predictions report, but it must remain outside the Old VELO scoring input. If a report compares VELO with Racing Post/press selections, it must label that lane as competitor intelligence.

**Command — required before Old VELO scoring:**
```
PYTHONPATH=. python scripts/ops/ensure_old_velo_rp_newspaper_files.py
  --date YYYY-MM-DD
  --execute
```

**What lands on disk:**
`data/incoming_pdfs/YYYY-MM-DD/` — staged engine PDFs only (`0011_XX`, `0012_XX`, `0015_OR`, `0016_XX`, `0032_TS`)
`data/reports/old_velo_rp_newspaper_file_gate_YYYY_MM_DD.json` — source gate proof
`data/reports/old_velo_rp_newspaper_file_gate_YYYY_MM_DD.md` — human-readable source gate proof
`data/racecard_merged/racecard_{VENUE}_YYYY-MM-DD.json` — one PDF-ingested Old VELO file per venue, named by venue code (GOO, NAV, PER, PUN etc.)

**How you know it worked:**
The gate report status is `PASS`. Every expected venue has all five required keys. No `0010_XX` file is staged as engine input. Every race has `off`, `course`, `name`, `distance` populated. Every runner has `official_rating`, `topspeed`, `form_figures`. Time keys are dot-time and match the race schedule.

**Hard stop:**
If `ensure_old_velo_rp_newspaper_files.py` exits non-zero, stop. The operator must download the missing RP `Newspaper Form` files or provide the folder using `--search-dir`. Do not substitute `build_racecard_merged_from_injection.py` unless the operator explicitly labels the run as non-compliant/fallback.

---

## STEP 8.5 — BUILD RPDC (Run BEFORE Scoring)

**Why:** RPDC stands for Release Candidate Detector and Context. It reads the run history of every horse running today, computes release signals — how many runs since last win, whether the horse is at or below its last winning mark, whether it is returning to a course it has won at, whether the stable is warm — and writes tags to Supabase for the scorer to attach. If RPDC does not run before scoring, every horse goes into the model blind with no release context.

**Source:** The exact injection JSON that passed Step 5. This is the correct pre-scoring source — it has real Racing Post horse IDs and real trainer IDs from the HTML parse. Do NOT use runner_snapshots as the source (those are post-scoring). Never allow RPDC to independently select a capture by date.

**Command:**
```
PYTHONPATH=. python scripts/ops/build_rpdc_daily.py
  --date YYYY-MM-DD
  --injection-path data/racing_post_account_parsed/FINAL_CAPTURE_LABEL/racecard_injection.json
```

**What it does:**
Reads every runner from the injection JSON. For each horse looks up the last 20 runs in `racing_horse_runs` by their Racing Post horse ID. Computes tags. Writes one row per runner to `runner_release_candidates` in Supabase.

**Tags it can assign:**
- `MARK_READY` — horse is at or below its last winning official rating
- `BELOW_LAST_WIN_MARK` — horse is rated below where it last won
- `MARK_NEAR` — within 3 lbs of last winning mark
- `CYCLE_RUN_1/2/3` — first, second, third run of the campaign
- `FRESH_RETURN` — 22–45 days since last run (optimal freshness window)
- `LONG_ABSENCE` — 90+ days off (fitness question)
- `STABLE_WARM` — trainer win rate >= 15% in last 30 days
- `COURSE_RETURN` — returning to a course where it has won before
- `DISTANCE_RETURN` — returning to a winning distance
- `WIN_STREAK` — 2+ wins in last 5 runs
- `PLACE_FORM` — placed last time without winning

**Cash window:** Score >= 3.0 → `rpdc_cash_window_flag = True`. This is a high-conviction signal.

**How you know it worked:**
No `RPDC zero-runner warning` messages in the scoring run. Score output shows `runners: 320 OK / 0 FAIL`. Tags appear in `runner_release_candidates` table in Supabase.

**Important — RPDC deepens over time:**
RPDC is only as good as `racing_horse_runs`. That table is built from the evening ingest pipeline (Step 13 — `ingest_results_to_horse_runs.py`). Every evening after races are run, Step 11 parses the RP results HTML and writes real RP horse IDs into `racing_horse_runs`. The next morning RPDC finds those IDs and computes real release tags.

On the first day the RP pipeline runs, `racing_horse_runs` has no RP-sourced history. RPDC computes from empty history and every horse gets `PLACE_FORM` only. After weeks of running the full evening pipeline nightly, the table fills with real run history and RPDC gives meaningful tags. This is expected and correct — it builds in depth over time.

**Horse ID chain — must be consistent across all scripts:**
All IDs are now real Racing Post numeric IDs (e.g. `9254402`). The synthetic `rp_{VENUE}_{name}` format is gone except as a last-resort fallback. The three scripts that were fixed to enforce this:
- `src/velo/racecard_loader.py` — uses real ID from rp_merged file, not constructed slug
- `scripts/ops/parse_rp_results_capture.py` — uses `horseId` from __NEXT_DATA__, not slug
- `scripts/ops/build_rpdc_daily.py` — reads injection JSON with real IDs, passes to Supabase lookup

If any of these three go back to synthetic IDs, RPDC breaks silently.

---

## STEP 9 — SCORE WITH OLD VELO

**Why:** Old VELO reads the RP files and runs every horse through a chain of systems. The SQPE Specialist Ensemble is the main scorer — a trained gradient boosting model. But multiple other systems fire alongside it:

**Systems that run during scoring:**

- **SQPE Ensemble** — the core probability model. Scores every horse. Produces win probability and place probability.
- **Race Archetypes** — classifies each race as Structure, Compression, or other archetype. This affects how the governor reads the signals.
- **TIE v3 Gate** — a secondary signal gate. Checks whether enough signals align before a verdict is issued.
- **Horse State Tagging** — checks doctrine signals for each horse: days since last run, trainer timing patterns, form trajectory. If horse state tagging fails for a horse, that horse cannot receive a tier — it is excluded with reason stated.
- **Spotlight Parser** — processes the spotlight comments from the RP files. Extracts NLP signals.
- **RPD-C Engine** — a passive metadata layer. Attaches RPD tags to runners. Does not alter scores or rankings. Audit only.
- **Playbook G (Sentient Loopback)** — loads the system's evolutionary state: how aggressive the appetite is, how many races have been observed. Audit mode only during scoring — it does not change any score. If it fails to load, scoring continues unaffected.
- **Product Router** — routes every verdict to the correct product lane based on tier and VP.
- **Signal Stack** — builds a complete signal payload for every race that is written to the observability record.
- **Midprice Hunter** — evaluates mid-price opportunities passively. Does not alter verdicts.

**Note on LLM Council, HSF, and Mission Control:** These systems are not confirmed active in the current morning scoring run. They must be verified and added to this truth when confirmed.

**Command:**
```
python scripts/ops/run_prime_today.py
  --date YYYY-MM-DD
  --source rp
  --no-notify
```

On Windows you must prefix with `PYTHONIOENCODING=utf-8` — the script uses Unicode characters in its output and Windows defaults to CP1252:
```
PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py --date YYYY-MM-DD --source rp --no-notify
```

**What a race verdict looks like:**

Every race gets one verdict. The top-ranked horse gets a tier and a product:

| Tier | Meaning |
|---|---|
| A-STRIKE | Strong signal — prob high, gap wide, place floor solid |
| B-PLAYABLE | Decent signal — check market before acting |
| C-WATCH | Some signal — each-way angle if price is generous |
| D-NO BET | Weak signal — no clear edge |
| X-CHAOS | Pass — model cannot identify a reliable leader |

| Product | Meaning |
|---|---|
| WIN_ONLY | Execution authorized — highest confidence A-tier only |
| VISION_ONLY | Signal exists but execution not yet authorized |
| PASS | No betting action — tier too weak, decoy risk, or containment lock |

**How you know it worked:**
- 30/30 verdicts written (or however many races are on the card)
- 0 score errors
- Local backup file exists: `data/velo_prime_verdicts_YYYY_MM_DD.json`
- Supabase write-proof shows ✓ for every race ID
- WIN_ONLY count reflects genuine high-conviction races (typically 0–5 on a normal card)

**Expected warnings (non-fatal, do not stop scoring):**

- `RP_MERGED_DEGRADED` — always appears when source is rp_merged. This means learning is blocked for this run but scoring is unaffected. Expected.
- ~~`Year 2026 outside BHA data range (2024-2024) — using 2024`~~ — **FIXED 2026-06-06.** `archive/dead_scripts/cache_bha_macro_features.py` updated with 2025 (from BHA Annual Data Pack) and 2026 (YTD May 2026 monthly reports, projected) rows. Parquet rebuilt. 2026/flat = thin_market ci_code=0.930, 2026/jump = thin_market ci_code=0.799 (horse population decline signal active). If this warning reappears, `data/bha_macro_features.parquet` has been deleted or overwritten — rerun the archive script.

**NOT expected — these mean something is broken:**

- `RPDC zero-runner warning` — was a known bug (synthetic horse IDs). NOW FIXED. If this appears it means one of the three ID chain scripts has regressed back to synthetic slugs: `src/velo/racecard_loader.py`, `scripts/ops/parse_rp_results_capture.py`, or `scripts/ops/build_rpdc_daily.py`.

**Spotlight verification (check timing audit after each run):**

After scoring, `data/timing_audit/runtime_timing_audit_YYYY_MM_DD.json` shows `spotlight_runners_parsed`. As of 2026-06-06 fix, this should be ~85–90% of all runners (281/320 on the June 7th test card). If it reads 0, the spotlight passthrough in `src/velo/racecard_loader.py` has regressed — the field must be `"spotlight": h.get("spotlight_comment") or h.get("diomed_comment") or ""`.

**What lands on disk and in the database:**
- Verdicts written to Supabase `velo_verdicts` table
- `data/velo_prime_verdicts_YYYY_MM_DD.json` — local backup (NOT system of record)
- `data/velo_run_observability_YYYY_MM_DD_*.json` — full observability packet
- `runner_snapshots_YYYY_MM_DD_*.jsonl` — per-runner feature snapshot for every horse scored
- `data/timing_audit/runtime_timing_audit_YYYY_MM_DD.json` — stage timing breakdown
- Telegram messages suppressed with `--no-notify` during testing

**BHA OR diff badge (Phase 2 — active from 2026-06-07):**
Every verdict top pick now has three extra fields (null when horse not in BHA changed list):
- `bha_or_diff` — integer diff (+3, -2, etc.) from `data/bha_or_diff_latest.csv`
- `bha_or_diff_flag` — `RAISED` / `LOWERED` / null
- `bha_or_diff_magnitude` — absolute value of diff
Source file: `data/bha_or_diff_latest.csv` (1,143 horses whose mark changed this BHA cycle).
Update this file each week by replacing with the new BHA "changed ratings" CSV download.
Discipline mapping: Chase→Chase diff; Hurdle/NHF→Hurdle diff; Flat (incl. AWT)→Flat diff with AWT fallback.
Evidence accumulation only — no scoring weight. Track `bha_or_diff_flag=LOWERED` SR over 4–6 weeks to quantify underpriced-mark effect.

**BHA Surface Trajectory badge (Phase 3 — active from 2026-06-07):**
Every verdict top pick now has five extra fields (null/SPARSE when horse not in BHA perf figures list):
- `surf_traj_surface` — surface code used: T=Turf, A=AW, H=Hurdle, S=Chase, N=NH Flat
- `surf_traj_n` — number of non-zero figures used (max 6)
- `surf_traj_latest_fig` — most recent BHA performance figure on that surface
- `surf_traj_slope` — linear regression slope over figures oldest→newest (float, 2dp)
- `surf_traj_flag` — ACCELERATING (>5) / PROGRESSIVE (>2) / STABLE (−2 to 2) / REGRESSING (−2 to −5) / DECLINING (<−5) / SPARSE (<2 figures)
Source file: `data/bha_perf_figures_latest.csv` (11,851 horses, latest 6 figures per horse).
Update this file each week by replacing with the new BHA "performance figures" CSV download.
Discipline mapping: Chase→S figures; Hurdle/NHF→H figures; Flat→T or A (whichever surface has more non-zero figures).
Excludes: zero figures (NR/PU/void); `x` cells (ran but no figure assigned).
Evidence accumulation only — no scoring weight. Track ACCELERATING/PROGRESSIVE SR over 4–6 weeks to determine if improving surface trajectory predicts wins.

---

## STEPS 9.1-9.5 -- PAPER INTELLIGENCE OVERLAYS

**Status:** Active from 2026-06-21. These steps run after Step 9 scoring and
before operator dashboard review. They are not live model scoring. They are not
staking permission. They are context, stress testing, and agent review.

**Hard law:** If any 9.x overlay conflicts with Old VELO, New Build, or the
persisted Step 9 verdict, the conflict is reported. No overlay may silently
change `velo_prime_prob`, `decision_tier`, `assigned_product`, Supabase
verdicts, router lanes, model files, or Telegram/execution behavior.

### Step 9.1: Radical Shadow VELO

Command:
```
PYTHONPATH=. python scripts/ops/run_radical_shadow_today.py --date YYYY-MM-DD
```

Outputs:
- `data/reports/radical_shadow_YYYY_MM_DD.json`
- `data/reports/radical_shadow_YYYY_MM_DD.md`
- `data/reports/radical_shadow_latest.json`
- `data/reports/radical_shadow_latest.md`

Purpose: run the No-RPR / radical interpretation as paper-only intelligence.
It is designed to challenge RPR dependence and expose mid-price opportunities.

### Step 9.2: Tri-Lane Stress Test

Command:
```
PYTHONPATH=. python scripts/ops/run_tri_lane_stress_test.py --date YYYY-MM-DD --version v2
```

Outputs:
- `data/reports/tri_lane_stress_test_YYYY_MM_DD_v2.json`
- `data/reports/tri_lane_stress_test_YYYY_MM_DD_v2.md`
- latest copies under `data/reports/tri_lane_stress_test_latest.*`

Purpose: compare Old VELO, New Build/Passport, and Shadow VELO together. This
is a stress test only. `live_execution_allowed` must remain false.

### Step 9.3: Tri-Lane Agent Review

Command:
```
PYTHONPATH=. python scripts/ops/build_tri_lane_agent_review.py --date YYYY-MM-DD --version v2
```

Outputs:
- `data/reports/tri_lane_agent_review_YYYY_MM_DD_v2.json`
- `data/reports/tri_lane_agent_review_YYYY_MM_DD_v2.md`
- latest copies under `data/reports/tri_lane_agent_review_latest.*`

Purpose: turn tri-lane conflicts into explicit race review instructions. This
is where an agent is told which races need human-style scrutiny.

### Step 9.4: Deep Race Agent V1

Command:
```
PYTHONPATH=. python scripts/ops/build_deep_race_agent_v1.py --date YYYY-MM-DD
```

Outputs:
- `data/reports/deep_race_agent_v1_YYYY_MM_DD_v2.json`
- `data/reports/deep_race_agent_v1_YYYY_MM_DD_v2.md`
- latest copies under `data/reports/deep_race_agent_v1_latest.*`

Purpose: paper-only analyst layer using RP race evidence, local gold, identity
checks, support/risk scoring, and "why VELO may be wrong" explanations. The
agent can mark `GREEN_CASH_REVIEW`, `AMBER_UPGRADE_REVIEW`,
`SUPPRESS_OR_STUDY`, or `STUDY_ONLY`, but it cannot alter Step 9.

Backfill/evaluation:
```
PYTHONPATH=. python scripts/ops/build_deep_race_agent_v1.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
PYTHONPATH=. python scripts/ops/evaluate_deep_race_agent_v1.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

### Step 9.5: Course Master

Command:
```
PYTHONPATH=. python scripts/ops/build_course_master.py --date YYYY-MM-DD
```

Outputs:
- `data/reports/course_master_YYYY_MM_DD.json`
- `data/reports/course_master_YYYY_MM_DD.md`
- `data/reports/course_master_latest.json`
- `data/reports/course_master_latest.md`

Purpose: course-level context from historical Sigma course excellence plus Deep
Race Agent evaluation. It labels today's courses as `COURSE_BOOST`,
`COURSE_SUPPORT`, `COURSE_NEUTRAL`, `COURSE_WARNING`, or `COURSE_SUPPRESS`.

Course Master is context only. It tells the operator whether today's battlefield
is historically friendly or dangerous for VELO. It does not select horses.

### Step 9.6: Old VELO Three-Option Card

Command:
```
PYTHONPATH=. python scripts/ops/build_old_velo_three_option_card.py --date YYYY-MM-DD
```

Old VELO must not be read as a single-horse system only. Step 9 writes full
runner snapshots for every scored horse. Step 9.6 turns those snapshots into
three operator roles per race:

- `WIN` — highest `velo_prime_prob`
- `PLACE` — highest `place_prob`, distinct from WIN when possible
- `LONGSHOT` — highest value/longshot role score, preferring `sp_dec >= 4.5`
  and using `longshot_prob`, `market_deception_score`, `improvement_score`,
  `sqpe_no_rpr_shadow_prob`, and odds band

Outputs:

- `data/reports/old_velo_three_option_card_YYYY_MM_DD.json`
- `data/reports/old_velo_three_option_card_YYYY_MM_DD.md`
- `data/reports/old_velo_three_option_card_latest.json`
- `data/reports/old_velo_three_option_card_latest.md`

Boundary: this is an operator/shadow card only. It does not change live scoring,
does not change model weights, does not stake, and does not write Telegram. It
only exposes the structure already present in Old VELO runner snapshots.

June 23 proof: on 2026-06-23 Old VELO WIN went 3/17, but the LONGSHOT role found
4/17 winners and exposed the mid-price/outsider class that the single top-pick
view missed. Therefore the daily operator view must show all three Old VELO
roles.

### Dashboard Proof

The dashboard endpoint `/api/governed-card?date=YYYY-MM-DD` must expose:
- `shadow_loaded`
- `tri_lane_loaded`
- `tri_review_loaded`
- `deep_agent_loaded`
- `course_master_loaded`

The dashboard page must show Old VELO, New Build, No-RPR/Shadow, Tri-Lane,
Deep Agent, and Course Master in separate lanes. Missing overlay data must show
as missing. It must never borrow numbers from another lane.

---

## NO RACE-DAY BUTTON

Do not use `velo_race_day_button.py` as the operational authority. The morning chain is run as explicit numbered steps when requested.

One capture label becomes the daily truth at Step 4. The exact injection path from that label must be passed to Step 5, Step 8, and Step 8.5. No downstream script may independently choose a different capture. Stop immediately on any non-zero exit or race-identity mismatch.

---

## PART 2 — EVENING (after all races finish, ~21:00 BST)

### THE FULL EVENING SEQUENCE — ONE OVERVIEW

After sigma completes, run the learning loop in this order:

```
Step 12: run_results_sigma.py               — reconcile predictions vs results
Step 13: ingest_results_to_horse_runs.py    — write run history (feeds tomorrow's RPDC)
Step 14: build_sigma_retrieval_corpus.py    — rebuild retrieval knowledge base
Step 15: update_mission_control.py          — refresh gate status from today's artifacts
Step 16: run_velo_council.py                — LLM Council tribunal (deterministic, no API key needed)
Step 17: run_execution_bridge_shadow.py     — paper ledger close (SIM only, no staking)
Step 18: build_innovation_protocol.py       — verdict-result dedup for router dataset
Step 19: router_shadow_audit.py             — router lane evidence accumulation
Step 20: nightly_eod_learning_runner.py     — Playbook G sentient loopback
```

**Commands:**
```
PYTHONPATH=. python scripts/ops/update_mission_control.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/audit/run_velo_council.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/ops/run_execution_bridge_shadow.py --date YYYY-MM-DD --mode SIM --audit-results
PYTHONPATH=. python scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
PYTHONPATH=. python scripts/ops/router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv
PYTHONPATH=. python scripts/ops/nightly_eod_learning_runner.py --date YYYY-MM-DD
```

**What to look for:**
- Mission Control: `source_truth: RP_MERGED_CLEAN`, `flatline_count: 0`
- Council: `Council Verdict: PASS_TO_LEARNING` (all gates clear)
- Execution bridge: `GATE NEUTRAL` or better — check POWER_ANCHOR SR and P&L
- Router: all lanes healthy, no freeze conditions
- Playbook G: `matched_races: N/N`, `wins` matches sigma strike count, `live_sentient_state_touched: False`

**Three path fixes applied 2026-06-06 (same bug pattern — canonical results path):**
- `ingest_results_to_horse_runs.py` — was looking for `data/results_YYYY_MM_DD.json`; fixed to `data/results/rp_results_YYYY_MM_DD.json`
- `nightly_eod_learning_runner.py` — same wrong path; fixed with canonical-first, legacy-fallback
- `nightly_eod_learning_runner.py` — win detection used `horse_id` only; verdicts pre-2026-06-07 have synthetic IDs (`rp_CHP_poetry_of_time`), results have real RP IDs. Added name-based fallback: `top.get("horse")` vs `winner.get("horse")`. Both `_classify_loss` and the main loop fixed.

### STEP 10 — CAPTURE RESULTS

**Why:** Now that races have run, you go back to Racing Post and download the results pages. These pages show who won, finishing positions, starting prices.

**Command — first build the result URLs from the exact final morning capture:**
```
python scripts/ops/build_rp_results_url_list.py
  --date YYYY-MM-DD
  --capture-label FINAL_CAPTURE_LABEL
  --execute
```

**Then capture them:**
```
python scripts/ops/racing_post_account_collector.py capture
  --url-list data/racing_post_url_lists/rp_results_YYYY-MM-DD.txt
  --date rp-results-YYYY-MM-DD-final
  --execute
```

**What lands on disk:**
`data/racing_post_account_raw/rp-results-YYYY-MM-DD-final/` — one HTML per race, results now populated.

---

### STEP 11 — PARSE RESULTS

**Why:** Extract the results from the HTML into structured data.

**Command:**
```
python scripts/ops/parse_rp_results_capture.py
  --date YYYY-MM-DD
  --capture-date rp-results-YYYY-MM-DD-final
  --execute
```

**What lands on disk:**
`data/results/rp_results_YYYY_MM_DD.json`

**How you know it worked:**
- `races_parsed` matches expected race count (e.g. 49 for 7 venues)
- `parse_errors: 0`
- SP populated on ~99% of runners (check `sp_dec > 0` count)
- `winner_sp > 0` on every race result
- All horse IDs are real RP numeric IDs (no `rp_` prefix)

**SP merge fix (applied 2026-06-06):** The results parser merges two horse data sources — the pre-race racecard index (has OR, TS, draw etc. but sp=None) and the live results table scraper (has real SP). The merge must be field-level: table_lookup values win for SP, jockey, trainer fields. A uid-level `.update()` was overwriting real SP with None. Fixed in `parse_rp_results_capture.py` lines ~515–524.

**Results file structure:** Top-level key is `results` (list of races), not `races`. Each race has `off` (dot-time, e.g. "1.20") and `race_time_raw` (ISO datetime).

---

### STEP 12 — SIGMA

**Why:** Sigma reconciles what VELO predicted against what actually happened. It finds every race VELO scored, checks who won, classifies every miss by type (mid-priced winner, outsider, market decoy, short favourite). Sends a Telegram report. This is how VELO learns what it got right and wrong.

**Command:**
```
python scripts/ops/run_results_sigma.py --date YYYY-MM-DD --source cache
```

---

### STEP 13 — INGEST RESULTS INTO HORSE HISTORY

**Why:** Every result gets written into the horse run history. This is what builds the passports for tomorrow. Tomorrow's New Build is only as good as the history ingested today. Also feeds RPDC — tomorrow morning RPDC will find real run history for horses that ran today.

**Command:**
```
python scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
```

**What lands in the database:**
`racing_horse_runs` — one row per runner, with real RP horse ID, position, SP, course, distance, going, race class.

**How you know it worked:**
`INGEST COMPLETE — {date}  Races: N  Runners written: N` — number should match result races × runners (typically 400–500 runners on a full UK day).

**Path fix (applied 2026-06-06):** Script was looking for `data/results_YYYY_MM_DD.json` (legacy path). Correct canonical path is `data/results/rp_results_YYYY_MM_DD.json` (output of `parse_rp_results_capture.py`). Fixed to check canonical path first, legacy path as fallback.

---

### STEP 14 — REBUILD RETRIEVAL CORPUS

**Why:** Updates the searchable knowledge base the retrieval layer uses to find similar past races when scoring.

**Command:**
```
python scripts/ops/build_sigma_retrieval_corpus.py --require-through-date YYYY-MM-DD
```

---

## THE FULL DAY — ONE DIAGRAM

```
YOU SAY: RUN THE ENGINE FOR TODAY

MORNING
  Step 1  Capture index page
          → data/racing_post_account_raw/index-YYYY-MM-DD-FINAL/  (one HTML)

  Step 2  Build URL list from index HTML
          → data/racing_post_url_lists/rp_racecards_YYYY-MM-DD.txt

  Step 3  Capture every race page (batch of 15 at a time)
          → data/racing_post_account_raw/live-full-racepages-YYYY-MM-DD/  (one HTML per race)

  Step 4  Parse every HTML — extract from __NEXT_DATA__
          → data/racing_post_account_parsed/{label}/racecard_injection.json  (Old VELO reads this)
          → data/racecards_YYYY_MM_DD_standard.json  (New Build reads this)

  Step 5  Preflight gate — blocks if injection is bad

  Step 6  Build passport feed — match every runner to their passport
          → data/new_build/current_cards/current_card_passport_feed_YYYY_MM_DD.jsonl

  Step 7  Score with New Build (passport scorer)
          → data/new_build/reports/two_lane_readiness_YYYY_MM_DD.json

  Step 8  Build Old VELO RP files — one file per track, 5 components per race:
          (1) race info  (2) postdata pick  (3) topspeed pick
          (4) spotlight verdict  (5) newspaper selections
          → data/racecard_merged/racecard_GOO_YYYY-MM-DD.json  (7 races × 5 components)
          → data/racecard_merged/racecard_NAV_YYYY-MM-DD.json  (8 races × 5 components)
          → data/racecard_merged/racecard_PER_YYYY-MM-DD.json  (7 races × 5 components)
          → data/racecard_merged/racecard_PUN_YYYY-MM-DD.json  (8 races × 5 components)

  Step 8.5  Build RPDC release candidate tags (runs BEFORE scoring)
            Reads injection JSON → looks up racing_horse_runs → writes runner_release_candidates
            → Supabase runner_release_candidates table (320 rows for a 30-race card)

  Step 9  Score with Old VELO (SQPE ensemble)
          → data/velo_prime_verdicts_YYYY_MM_DD.json
          → Supabase velo_verdicts table

EVENING (after 21:00 BST)
  Step 10 Capture results pages from Racing Post
  Step 11 Parse results
          → data/results/rp_results_YYYY_MM_DD.json
  Step 12 Sigma — compare predictions to results → Telegram report
  Step 13 Ingest results into horse history → builds tomorrow's passports
  Step 14 Rebuild retrieval corpus
```

---

## WHEN THINGS GO WRONG

| What you see | What it means | What you do |
|---|---|---|
| HTML file is 5KB | Session expired, RP served a block page | Run init-login, re-capture |
| off_time is null in injection | Parser could not find race time | Re-parse, check parser line 175 |
| Preflight gate blocks | Injection has bad or partial data | Fix the data, re-run parse |
| Fewer venues than expected | Some race pages not captured | Check for 5KB files, re-capture those |
| 404 errors on capture | Race URL is stale or wrong | Re-extract URLs from a fresh index |
| Passport feed shows wrong date | Feed not re-run for today | Run new_build_current_card_feed.py |
| UnicodeEncodeError on Windows | Script prints Unicode chars, Windows terminal is CP1252 | Run with PYTHONIOENCODING=utf-8 prefix |

---

## HARD RULES — NEVER BREAK

1. UK and Ireland only. International venues are contamination. Delete them.
2. Racing Post HTML only. No Racing API. No Sporting Life. Ever.
3. No live staking. No model training. No SQPE changes.
4. Do not create new scripts. Use what is in scripts/ops/ only.
5. Do not touch anything without saying what you are doing first.
6. If you find a problem you stop and state it. You do not patch. You fix the source.
7. Brutal truth always. A problem stated is fixable. A problem hidden kills the system.

---

# AUTHORITATIVE UNIFORM EVENING AND LEARNING CONTRACT

**Effective:** 2026-06-07

This section is the authoritative daily contract. It overrides any earlier evening
summary that stops before Step 20 or does not verify the learned artifacts.

The day is not complete because results were scraped or Sigma ran. The day is
complete only when Steps 10 through 20 pass in order and the final verification
below passes.

## DAILY SOURCE AND SAFETY RULES

1. UK and Ireland only.
2. Racing Post HTML/results only.
3. No Racing API and no Sporting Life.
4. Racing API enrichment is not a Council evidence source, Council tool,
   Council requirement, Council warning, or Council release gate.
5. All execution bridge activity is SIM/paper only. No live staking.
6. Playbook G learning is shadow-only. `data/sentient_state.json` must not change.
7. At the first failed gate, stop and announce the exact obstacle. Fix safely,
   rerun the failed step, and only then continue.

## ONE DAILY COMMAND SEQUENCE

Run from the canonical repository root with `PYTHONPATH=.` and
`PYTHONIOENCODING=utf-8`.

```text
Step 10A python scripts/ops/build_rp_results_url_list.py --date YYYY-MM-DD --capture-label FINAL_CAPTURE_LABEL --execute
Step 10B python scripts/ops/racing_post_account_collector.py capture --url-list data/racing_post_url_lists/rp_results_YYYY-MM-DD.txt --date rp-results-YYYY-MM-DD-final --execute
Step 11  python scripts/ops/parse_rp_results_capture.py --date YYYY-MM-DD --capture-date rp-results-YYYY-MM-DD-final --execute
Step 12  python scripts/ops/run_results_sigma.py --date YYYY-MM-DD --source cache
Step 13  python scripts/ops/ingest_results_to_horse_runs.py --date YYYY-MM-DD
Step 14  python scripts/ops/build_sigma_retrieval_corpus.py --require-through-date YYYY-MM-DD
Step 15  python scripts/ops/update_mission_control.py --date YYYY-MM-DD
Step 16a python scripts/audit/vp30_operator_card.py --date YYYY-MM-DD > data/vp30_operator_card_YYYY-MM-DD.md
Step 16b python scripts/audit/run_velo_council.py --date YYYY-MM-DD
Step 17  python scripts/ops/run_execution_bridge_shadow.py --date YYYY-MM-DD --mode SIM --audit-results
Step 18  python scripts/ops/build_innovation_protocol.py --date YYYY-MM-DD
Step 19  python scripts/ops/router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv
Step 20  python scripts/ops/nightly_eod_learning_runner.py --date YYYY-MM-DD
Final    python scripts/audit/run_velo_council.py --date YYYY-MM-DD
Final    python scripts/ops/update_mission_control.py --date YYYY-MM-DD
```

If result capture batching does not continue correctly, create a missing-only RP
URL list from the original canonical result list and capture only those missing
URLs into the same final capture folder. Never accept duplicate URLs or a partial
capture.

## REQUIRED GATES BY STEP

### Steps 10-11: RP Result Integrity

- Captured HTML count equals expected UK/IRE race count.
- Manifest URL count and unique URL count equal expected race count.
- Every capture is PASS with HTTP 200.
- Parsed race count equals expected race count.
- `parse_errors: 0`.
- Every starter has `sp_dec > 0`.
- Every winner has `winner_sp > 0`.
- Every horse ID and winner ID is a real numeric RP ID.
- Only true non-runners may have zero SP.

**Stop if any result gate fails. Sigma must never consume partial or fake data.**

### Step 12: Sigma

- Results source is `data/results/rp_results_YYYY_MM_DD.json`.
- All predictions reconcile or are explicitly classified as true non-runners.
- Identity failures are zero.
- Record wins, frames, misses, strike rate, frame rate, and non-runners.
- Sigma artifact exists at `data/sigma_results/sigma_results_YYYY_MM_DD.json`.

### Step 13: Horse History

- `INGEST COMPLETE` is printed.
- Races written equals parsed result races.
- Runners written equals all runners in the parsed RP result file.
- Destination is Supabase table `racing_horse_runs`.

This is learned history used by tomorrow's passports and RPDC.

### Step 14: Retrieval Memory

- Retrieval corpus build completes.
- Output exists at `data/sigma_memory/sigma_retrieval_corpus_v1.jsonl`.
- Report the corpus date range and announce if current evidence is not included.

### Step 15: Mission Control

Required:

- `source_truth: RP_MERGED_CLEAN`
- `flatline_count: 0`
- `identity_failure_count: 0`
- `learning_gate: OPEN`
- `promotion_gate: OPEN`
- Sigma artifact PRESENT with the correct wins and evaluated count.

Stop if any required Mission Control gate fails.

### Step 16: LLM Council

Required:

- VP30 card exists at `data/vp30_operator_card_YYYY-MM-DD.md`.
- Council packet, run, and report exist.
- `Council Status: READY`.
- `Council Verdict: PASS_TO_LEARNING`.
- No Racing API enrichment evidence source appears in the Council packet/report.

Council outputs:

- `data/council_packets/council_packet_YYYY-MM-DD.json`
- `data/council_runs/council_run_YYYY-MM-DD.json`
- `data/council_reports/velo_council_report_YYYY-MM-DD.md`

Stop on `EVIDENCE_INCOMPLETE`, `WATCH_ONLY`, or `QUARANTINE_DAY`.

### Step 17: Execution Bridge

Required:

- Mode is SIM.
- `simulation_only: True`.
- Live execution did not occur.
- Outcome audit completed.
- POWER_ANCHOR sample, SR, frame rate, P&L, ROI, and freeze status reported.

Destination: `data/velo_execution_bridge_paper_ledger.csv`.

### Step 18: Innovation/Router Dataset

Required:

- Result lookup contains today's courses and date.
- Exactly one output row exists per verdict.
- Every evaluated runner has a result position and `sp_decimal > 0`.
- Only true non-runners may have zero SP.
- Newly enriched rows replace stale pre-result copies during deduplication.

Destination: `data/velo_innovation_protocol_1k_deduped.csv`.

Stop if result lookup reports zero courses, positions are missing, or evaluated
runner SP is zero. Router learning must never consume hollow rows.

### Step 19: Router Shadow Audit

Required:

- Audit completes without exception.
- V1, V2, and V6 report state, sample, SR, frame, ROI, and drawdown.
- Freeze conditions are explicitly reported.

Outputs:

- `data/router_shadow_audit_latest.csv`
- `data/router_shadow_audit_latest.md`
- timestamped router audit snapshot
- `data/router_shadow_audit_ledger.csv`

### Step 20: Playbook G Nightly Learning

Required:

- `verdict: PASS`.
- `matched_races` equals the full prediction/result race count.
- `events_created` equals the full race count.
- `wins` equals Sigma wins.
- `data_error_count: 0`.
- `engine_updates_applied_first_run` equals events created.
- `engine_updates_applied_duplicate_run: 0`.
- `duplicates_skipped_second_run` equals events created.
- `live_sentient_state_touched: false`.
- `hfs_features_used: false`.
- Hardened Playbook G verdict is `SHADOW_ONLY_OK`.

Venue aliases must reconcile before learning. Example: RP venue `PAT` and VELO
venue `PUN` both identify Punchestown. A venue-alias miss is a matcher defect,
not missing result data.

## WHERE LEARNING GOES

### Actual Learned State

- `data/sentient_state_shadow.json` - evolved Playbook G shadow state.
- Supabase `racing_horse_runs` - runner history used by tomorrow's passports/RPDC.
- `data/velo_innovation_protocol_1k_deduped.csv` - router evidence dataset.
- `data/sigma_memory/sigma_retrieval_corpus_v1.jsonl` - retrieval memory.

### Daily Learning Proof

- `data/nightly_eod_learning_events_YYYY_MM_DD.jsonl`
- `data/nightly_eod_learning_status_YYYY_MM_DD.json`
- `data/nightly_eod_learning_failures_YYYY_MM_DD.json`
- `data/playbook_g_nightly_audit_YYYY_MM_DD.json`
- `data/nightly_eod_learning_council_audit_YYYY_MM_DD.json`
- `data/eod_sigma_study_YYYYMMDD.json`
- `data/eod_playbook_g_shadow_critique_YYYYMMDD.json`

### Governance Proof

- `data/mission_control/YYYY-MM-DD_mission_control.json`
- `data/mission_control/latest.json`
- Council packet, run, and report for the date.
- Router audit latest files and immutable snapshot.

## FINAL DAILY ACCEPTANCE CHECK

The agent must report all of the following every day:

1. Results coverage: parsed/expected races and starter SP coverage.
2. Sigma: wins/evaluated, strike rate, frames/evaluated, frame rate.
3. Horse-history ingest: races and runners written.
4. Retrieval corpus status and date range.
5. Mission Control: source truth, flatlines, identity failures, and gates.
6. Council: status and verdict.
7. Execution bridge: POWER_ANCHOR metrics and freeze status.
8. Router: every lane state and freeze status.
9. Playbook G: matched races, events, wins, losses, updates, duplicates blocked,
   live-state touch, and final verdict.
10. Every remaining warning or blocker.

**Uniform completion statement:**

`DAY COMPLETE` may only be stated when Steps 10-20 and the final refreshed
Council/Mission Control checks all pass. Otherwise state `DAY INCOMPLETE` and
name the exact failed step and obstacle.

---

## HARDENING ADDENDUM - RACEDAY UNIVERSE GATE

Before morning scoring and before evening learning, run:

```
python scripts/ops/verify_raceday_universe.py --date YYYY-MM-DD --execute
```

This compares RP injection, standard cache, Old VELO RP-merged files, New Build
readiness, and RP results when available. All race IDs must match. If the check
returns `FAIL`, stop. Do not score, do not run Sigma, and do not learn until the
artifact mismatch is fixed.

---

## CANONICAL MODEL TRUTH SPINE (added 2026-07-06, MODEL-TRUTH-01..04)

- Dirty/local runtime artifacts are evidence, not final truth.
- GitHub stores reviewed code, law, generated proof artifacts, and regression tests.
- Supabase canonical tables (`public.canonical_model_scorecards`, `public.canonical_learning_events`) are the operational truth source for model scorecards and learning events.
- Dashboard must read `canonical_model_scorecards` and `canonical_learning_events` for model/result/learning truth.
- Dashboard must not invent model truth from ad-hoc local JSON, stale sidecar outputs, or prose reports.
- Sigma remains result reconciliation truth, but model-rank and policy learning must join through canonical scorecard rows.
- No model claim is accepted unless backed by: `source_path`, `source_field`, `race_id`, `horse_id`, `rank`, `odds`, `result`, `policy_decision`, `stake_authorised`, `learning_class`.
- **Little Lady Rock 2026-07-05 is the regression anchor**: New Build Lane A/B rank 1, SP 41.0, policy `NO_EDGE`, `stake_authorised=false`, learning `VALUE_DISCOVERY_POLICY_BLOCKED`, no promotion.
- Any future dashboard panel that displays model truth must either read canonical endpoints, or be explicitly labelled runtime/local/non-canonical.

Canonical dashboard consumer endpoints (`scripts/ops/new_build_dashboard_server.py`, read-only, no Supabase writes):
- `GET /api/canonical-scorecard?date=YYYY-MM-DD`
- `GET /api/canonical-learning-events?date=YYYY-MM-DD`
- `GET /api/canonical-race-truth?date=YYYY-MM-DD&race_id=<race_id>`

Builders: `scripts/ops/build_canonical_model_scorecard.py`, `scripts/ops/persist_canonical_model_scorecard.py`, `scripts/ops/build_canonical_learning_events.py`. Law: `docs/current/MODEL_RESULT_REPORTING_LAW.md`. See also `docs/current/VELO_MODEL_SOURCE_MAP.md`.

Chain of custody:

```
Dirty repo   = evidence
GitHub       = reviewed proof/code/law
Supabase     = canonical operational truth
Dashboard    = canonical consumer
Learning     = canonical consumer
Promotion    = gated
```

No dashboard truth is accepted from random local files.
