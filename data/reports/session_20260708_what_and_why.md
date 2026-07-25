# 2026-07-08 Session — What Was Done and Why

This is the connect-the-dots report. Not from GitNexus (its MCP tools aren't wired into
this session — `.mcp.json` is read at Claude Code startup, and I can't restart myself
mid-session; the underlying index was refreshed to 20,301 symbols / current commit so
it'll be accurate the next time GitNexus's actual query/impact tools ARE available).
Everything below is from things I actually ran and verified today, in order, with why.

## 1. Why July 8's dashboard was mostly empty

**Symptom:** scoring worked (33/33 races), but New Build, Champion Intent Shadow, and
RPDC all showed "no data."

**Root cause:** today's racecard was built from manually-supplied PDF ratings sheets
(`ingest_racecard_pdfs.py`), not a live browser capture. PDFs produce synthetic
`rp_COURSE_DATE_TIME` race_ids with no real RP horse_uids. New Build, Champion Intent
Shadow, and RPDC all join on real RP identifiers — PDFs can't feed them, structurally,
not as a bug.

**Fix applied same day:** ran the live capture chain (Steps 1-8.5) retroactively for
the 21 races still active (Kempton/Chepstow/Fairyhouse). Confirmed permanent loss for
Catterick/Yarmouth (12 races) — RP drops a course from its live index once the whole
card has finished, no way to recover after the fact. This is *why* `run_full_raceday.py`
must run before racing starts, not why-not-just-run-it-later.

## 2. Why the RP session kept dying

**Symptom:** passport-bank scraping burned through 146 requests, 92% came back HTTP 406.

**Root cause:** the saved browser profile's login session had expired. Nothing in the
pipeline checked login state proactively — it was only visible after the fact, buried in
parsed page content (`account_is_logged: false`).

**Fix:** `scripts/ops/check_rp_session_health.py` (new) — 2-second live probe, wired into
`velo_session_start_check.py` as check #11 and into `run_full_raceday.py`'s pre-flight.
Also fixed `init-login`'s blocking `input()` call, which hung/EOF'd when invoked through
a non-interactive session — added `--wait-seconds` as a non-TTY fallback.

## 3. Why the passport-bank capture looked stuck at a fixed count across "successful" resumes

**Root cause, found later the same day:** `racing_post_account_collector.py`'s capture
manifest was only assembled and written once, at the very end of the whole batch loop.
A killed/timed-out process (this session's tool has a ~590s execution window) lost ALL
that run's progress from the manifest — dedup on the next invocation only sees what's in
the manifest, so it kept re-attempting the same URLs. A second bug compounded it: one
`write_text()` got hit mid-write by a kill signal and left `manifest.json` at 0 bytes,
losing the bookkeeping for 357 already-successful captures (the raw per-URL files were
untouched, only the aggregate index was lost).

**Fix:** manifest now writes after every single capture (not once at the end), and the
write itself is atomic (temp file + `os.replace`, can't be left truncated by a kill
signal). Rebuilt the lost manifest from the surviving per-URL sidecar files rather than
losing the 357 real captures.

## 4. Why Sigma almost blocked the whole July 7 day

**Root cause:** `run_results_sigma.py`'s `COURSE_ALIASES` table had no `trm`→`tramore`
entry. All 7 Tramore races failed their course+time join against real results — would
have tripped the 95% completeness gate (28/35 = 80%, blocked) despite the results
actually existing and being correctly parsed.

**Fix:** one-line alias addition. Also added `--no-notify` to the same script (it had no
way to suppress Telegram before — the first fix-worthy incident of the day was ME running
it without pausing to check that first, which is why the flag exists now).

## 5. Why the Champion Intent Shadow panel stayed blank even after real data existed

**Two separate root causes, found in sequence:**
1. The scorecard builder hardcoded `dashboard_visible: False` on every row — a
   deliberate research-only gate (same governance class as `stake_authorised`,
   `promotion_eligible`). Operator explicitly authorized flipping *only* this flag
   (not the other two, which remain gated pending real multi-day evidence, same
   precedent as the Little Lady Rock case already in this repo's law).
2. Even after that, still blank — because `app/main.py` (the server actually running)
   never defined `/api/model-suggestions` at all. That route only existed on a
   *different* FastAPI app (`new_build_dashboard_server.py`) serving the same static
   HTML. The frontend's fetch silently 404'd and swallowed the error into "No data."

**Fix:** ported the missing route (plus 3 more with the same problem — canonical
scorecard, canonical learning events, canonical race truth, doctrine scorecard) into
`app/main.py`, reusing the existing builder functions rather than duplicating logic.
`app/main.py` is now the single canonical dashboard server; the other file is marked
deprecated-for-standalone-use in its own docstring.

## 6. Why `app/main.py`'s own `/api/dashboard-truth` was lying about Supabase state

Three independent schema-mismatch bugs, found by directly reproducing the exact query
the endpoint ran: `pipeline_runs.completed_at` (real column: `finished_at`),
`velo_verdicts.date` (no such column — must filter by `race_id LIKE`), and reading the
anon `SUPABASE_KEY` (blocked by RLS) instead of the service-role key every other script
in this repo already uses. All three silently produced `SUPABASE_UNAVAILABLE` or wrong
counts instead of erroring loudly. Fixed all three; confirmed against real July 8 data
(33 verdicts, correct pipeline_run row) before and after.

## 7. Why "this happens every day" wasn't actually happening every day

**Root cause:** there was no orchestrator. 15 separate manual commands, no scheduler
that actually ran (Railway cron unproven per ONE_TRUTH's own existing law), no local
automation either. Most days, only core scoring got run.

**Fix:** `scripts/ops/run_full_raceday.py` — one command, the full chain, idempotent on
scoring (never overwrites an already-scored day). Installed as a **local** cron job
(`CRON_TZ=Europe/London`, 07:00 daily) — explicitly NOT a Claude cloud routine, because
cloud routines run in a fresh sandbox with no access to the local RP browser session or
`.env` secrets and would fail silently every day. This is the actual fix for "same
thing every day, only the data changes" — it now runs without anyone asking.

## 8. What's still open, honestly

- **GitNexus MCP tools aren't connected this session** — index refreshed, tools not
  reachable until the session/Claude Code restarts and picks up `.mcp.json`.
- **`docs/VELO_MOT_AUDIT.md`** (2026-06-07, a month old) independently flagged the exact
  "duplicate dashboard/scheduler truth" pattern found again today (its P2-02) — it had
  not been closed before today's session. Also still open from that audit: CI only
  proves `ingestion_spine`, not the Prime scoring path; production Railway health was
  reported down (502) a month ago and was not re-verified today (no accessible URL
  found in this session — flagged, not chased).
- **Cron only fires while this WSL machine is actually running** — same limitation any
  local scheduler has. If the machine is off/asleep at 07:00 UK time, that day reverts
  to manual.
- **New Build / Champion Intent Shadow / RPDC still need live capture before racing
  starts, every day** — the cron now does this automatically, but if the RP session is
  dead when it fires, the pre-flight check aborts loudly (that part's handled) and
  someone still has to re-authenticate interactively (that part can never be automated —
  RP login requires a human typing credentials into a real browser window).

## Classification
`SESSION_SUMMARY_COMPLETE` · `NO_GITNEXUS_MCP_THIS_SESSION` · `GITNEXUS_INDEX_REFRESHED`
