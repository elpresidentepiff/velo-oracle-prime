# RACE DAY 11 EXECUTION PACKET — 2026-06-11

**Prepared:** 2026-06-10, while Race Day 10 was in progress (and therefore untouched).
**Mode:** production rehearsal. Telegram DISABLED. Dashboard publish DISABLED. Learning decided by LEARNING_ADMISSION_GATE.md.

## What already ran on 2026-06-10 (rehearsal evidence, all read-only)

| Probe | Result |
|---|---|
| `velo_session_start_check.py` | RUNS — 0 CRITICAL, 3 WARN (degraded-day history, learning-block history, dirty worktree) |
| `validate_rp_injection.py` (June 10 injection) | PASS — 34 races / 5 courses / 381 runners, consistent with 34 verdicts + 381 RPDC rows |
| `prove_supabase_persistence.py --date 2026-06-09` | PASS |
| `prove_supabase_persistence.py --date 2026-06-10` | FAIL — `RPDC_PERSIST_GAP local_attached=34 supabase_tagged=0` (pre-fix rows; fix `66d23a0` takes effect June 11) |
| MC source-truth fix on real packets | June 9→CLEAN/OPEN · June 10→DEGRADED/BLOCKED · June 11→UNKNOWN/BLOCKED |
| Tests | 15/15 (11 mission-control + 4 RPDC boundary) |

## What refused to run on 2026-06-10 (would write or touch live state)
`run_prime_today.py` (any mode — writes `pipeline_runs` even before persist) · `build_rpdc_daily.py` (Supabase writes) · `update_mission_control.py` full script (overwrites `latest.json` during Race Day 10) · evening chain Steps 10–20 (Race Day 10 closeout belongs to the operator) · dashboard publish scripts · any Telegram send.

## Exact June 11 command sequence

```bash
# ── MORNING ──────────────────────────────────────────────────────────────
# 0  Pre-flight (read-only)
PYTHONPATH=. python scripts/ops/velo_session_start_check.py

# 1-3 Capture index → URL list → race pages (THE_ONE_TRUTH Steps 1-3, date 2026-06-11)
#     Choose FINAL_CAPTURE_LABEL once; use it everywhere below.

# 4  Parse
PYTHONPATH=. python scripts/ops/parse_racing_post_racecard_capture.py \
  --date 2026-06-11 --capture-label FINAL_CAPTURE_LABEL --write-standard-cache --execute

# 5  GATE (read-only — hard stop on non-zero)
PYTHONPATH=. python scripts/ops/validate_rp_injection.py \
  --injection-path data/racing_post_account_parsed/FINAL_CAPTURE_LABEL/racecard_injection.json

# 6  Merged build (local writes only)
PYTHONPATH=. python scripts/ops/build_racecard_merged_from_injection.py \
  --date 2026-06-11 --injection-path <same>

# 6b RATINGS SOURCE CHECK (manual until fix #5 lands):
#    grep pdf_intel coverage in data/racecard_merged/racecard_*_2026-06-11.json —
#    >50% runners missing postdata_score/or_compression_score ⇒ day will be DEGRADED.
#    Fix the source NOW or accept a degraded, learning-blocked day knowingly.

# 7  RPDC build (Supabase write — standard approved morning op)
PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date 2026-06-11 --injection-path <same>

# 8  SCORING — DRY-RUN FIRST (no persist, no Telegram; verified in code lines 1363-1368)
PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py \
  --date 2026-06-11 --source rp --dry-run
#    Check: local verdicts JSON has rpdc_lookup_status=attached AND
#    observability packet source_truth. THIS is the feature-health packet.

# 9  REAL RUN (Supabase write — standard daily op; operator go/no-go after dry-run)
PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py \
  --date 2026-06-11 --source rp --no-notify

# 10 PERSISTENCE PROOF (read-only; must PASS — first day the RPDC fix shows in Supabase)
PYTHONPATH=. python scripts/ops/prove_supabase_persistence.py --date 2026-06-11

# ── EVENING (after ~21:00 BST) ───────────────────────────────────────────
# 11-13 Results capture + parse (THE_ONE_TRUTH Steps 10A/10B/11)
# 14 Sigma (cache is now the DEFAULT; flag kept for explicitness)
PYTHONPATH=. python scripts/ops/run_results_sigma.py --date 2026-06-11 --source cache
# 15 Horse runs ingest
PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date 2026-06-11
# 16 Retrieval corpus
PYTHONPATH=. python scripts/ops/build_sigma_retrieval_corpus.py --require-through-date 2026-06-11
# 17 Mission Control (now observability-derived — cannot call degraded clean)
PYTHONPATH=. python scripts/ops/update_mission_control.py --date 2026-06-11
# 18 Council
PYTHONPATH=. python scripts/audit/vp30_operator_card.py --date 2026-06-11 > data/vp30_operator_card_2026-06-11.md
PYTHONPATH=. python scripts/audit/run_velo_council.py --date 2026-06-11
# 19 LEARNING — only per LEARNING_ADMISSION_GATE.md, only if LEARNING_READY,
#    only with operator approval. Otherwise stop and record LEARNING_BLOCKED_*.
```

## Write surfaces (so nothing is a surprise)
| Stage | Writes |
|---|---|
| Capture/parse/merge | local `data/` only |
| RPDC build | Supabase `runner_release_candidates` |
| Scoring dry-run | local only (verify no `pipeline_runs` row appears — first-use check) |
| Scoring real | Supabase `velo_verdicts` + `pipeline_runs`, local backup/observability/snapshots |
| Sigma/ingest | Supabase `sigma_audits`, `racing_horse_runs`; local sigma artifacts |
| Mission Control | local `data/mission_control/` only |
| Persistence proof | local `data/reports/` only |

## Clean vs degraded classification for June 11
**UNKNOWN until the morning run** — by design (no observability packet exists yet, and Mission Control now says so instead of guessing). The day becomes CLEAN-READY only if stage 6b shows PDF-intel coverage >50% and the scoring packet reads `RP_MERGED_CLEAN`. June 10 was DEGRADED; if June 11's source has the same gap, expect DEGRADED again and treat stage 6b as the moment to fix it.

## Operator approvals required on the day
Go/no-go after dry-run (stage 8→9) · learning admission (stage 19) · any dashboard publish · any Telegram re-enable.
