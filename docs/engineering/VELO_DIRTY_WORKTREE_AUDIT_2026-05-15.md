# VELO Dirty Worktree Audit — 2026-05-15

## Classification
`DIRTY_TREE_BLOCKING_LIVE_OPS`

The current worktree must remain blocked for live-affecting execution because dirty high-risk files exist in scoring and notification paths. The Safety Sentinel block is correct.

## Current Block Reason
- `app/services/velo_prime_service.py`
- `scripts/run_prime_today.py`
- `scripts/send_telegram_summary.py`

These are not cosmetic files. They touch official scoring persistence, same-day prediction writing, and Telegram delivery behavior.

## Operating Rule
No live-affecting command should be suggested until these files are either:
- intentionally committed with review
- explicitly reverted
- quarantined and removed from the active path
- or classified by a human as safe and unrelated

## High-Priority File Audit

### `app/services/velo_prime_service.py`
- Status: modified
- Suspected purpose: official scoring persistence layer for `velo_verdicts`
- Risk level: `CRITICAL`
- Affects:
  - scoring: yes
  - Telegram: no direct send, but changes persisted output shape
  - router: possible indirect governance effects
  - staking: indirect if downstream consumes verdict columns
  - dashboard: yes, via persisted fields
  - learning: indirect through verdict truth
- What changed:
  - runtime `git_commit_sha` persistence added
  - `decision_tier` persistence added
  - RPDC field handling changed from `plot_conviction`-derived placeholders to explicit RPDC fields
  - persistence schema expectations expanded
- Audit read:
  - some of this work looks useful and probably needed
  - but it changes official verdict persistence behavior and schema assumptions
- Classification: `HUMAN_REVIEW_REQUIRED`
- Safe action now: do not merge, do not run live scoring from this dirty tree

### `scripts/run_prime_today.py`
- Status: modified
- Suspected purpose: official day scoring runner / persistence entrypoint
- Risk level: `CRITICAL`
- Affects:
  - scoring: yes
  - Telegram: yes, notification suppression path
  - router: indirect
  - staking: indirect
  - dashboard: yes, via verdict outputs
  - learning: indirect through verdict generation
- What changed:
  - UTF-8 console output reconfigure
  - explicit stale-card / date-mismatch persistence block
- Audit read:
  - the stale-card guard is the kind of protection we want
  - but this is still a core official scoring file, so it cannot ride along unreviewed
- Classification: `HUMAN_REVIEW_REQUIRED`
- Safe action now: review and isolate as its own scoring-safety change set

### `scripts/send_telegram_summary.py`
- Status: untracked at discovery, now quarantined outside repo
- Suspected purpose: ad hoc Telegram sender
- Risk level: `CRITICAL`
- Affects:
  - scoring: no
  - Telegram: yes, directly
  - router: no
  - staking: no
  - dashboard: no
  - learning: no
- What changed:
  - standalone script with hardcoded bot token and chat id
- Audit read:
  - this is an immediate quarantine item
  - hardcoded credentials in an untracked script are not acceptable in the active worktree
- Classification: `QUARANTINE`
- Safe action now:
  - done: moved out of repo executable path into quarantine
  - rotate credentials if they were real and exposed

### `scripts/run_results_sigma.py`
- Status: modified
- Suspected purpose: results reconciliation, sigma auditing, Telegram reporting, pipeline run truth
- Risk level: `HIGH`
- Affects:
  - scoring: no direct scoring
  - Telegram: yes
  - router: no
  - staking: no
  - dashboard: indirect through results truth
  - learning: yes, because Sigma truth gates learning
- What changed:
  - commit SHA write into pipeline run truth
  - Telegram delivery truth append hooks
  - verdict shape compatibility
  - miss-forensics report generation
- Audit read:
  - this file carries valuable instrumentation work
  - but it also changes Telegram and post-race truth behavior
- Classification: `BLOCKING_LIVE_OPS`
- Safe action now: split telemetry/reporting changes from any behavior changes before approval

### `scripts/cashrun_detector.py`
- Status: modified
- Suspected purpose: Racing Post CASHRUN intent-layer extraction and operator report generation
- Risk level: `HIGH`
- Affects:
  - scoring: no official scoring changes
  - Telegram: no
  - router: no
  - staking: no
  - dashboard: yes, via CASHRUN/operator sidecars
  - learning: indirect operator context only
- What changed:
  - large rewrite into RP intent-layer scorer/reporter
  - file inventory, field coverage, RP context scoring, report generation
- Audit read:
  - strategically useful
  - but too large to assume safe without review
  - should be treated as an intelligence-layer subsystem, not casually mixed into live ops changes
- Classification: `QUARANTINE`
- Safe action now: keep isolated from official scoring branch decisions

### `app/static/dashboard/index.html`
- Status: modified
- Suspected purpose: dashboard UI and sidecar rendering layer
- Risk level: `MEDIUM`
- Affects:
  - scoring: no
  - Telegram: no
  - router: no
  - staking: no
  - dashboard: yes
  - learning: no
- What changed:
  - CASHRUN panel added
  - sidecar path corrected
  - CASHRUN-aware row badges and metadata rendering
  - race-name rendering cleanup
- Audit read:
  - meaningful UI work, not live-model risk by itself
  - but still operator-facing, so bad data joins can mislead if shipped casually
- Classification: `QUARANTINE`
- Safe action now: keep separate from scoring/live ops approval lane

### `app/static/dashboard/sidecar_stack_latest.json`
- Status: modified
- Suspected purpose: generated dashboard sidecar artifact
- Risk level: `LOW`
- Affects:
  - scoring: no
  - Telegram: no
  - router: no
  - staking: no
  - dashboard: yes
  - learning: no
- What changed:
  - same-day operator visibility payload, likely regenerated from current sidecar logic
- Audit read:
  - this is runtime/generated data, not source code
  - it should not be used as evidence of a code change by itself
- Classification: `QUARANTINE`
- Safe action now: regenerate when needed; do not treat as a source-of-truth code delta

## High-Risk File Classification Table

| File | Classification | Live-Ops Impact |
|---|---|---|
| `app/services/velo_prime_service.py` | `BLOCKING_LIVE_OPS` + `HUMAN_REVIEW_REQUIRED` | official scoring persistence |
| `scripts/run_prime_today.py` | `BLOCKING_LIVE_OPS` + `HUMAN_REVIEW_REQUIRED` | official scoring entrypoint |
| `scripts/run_results_sigma.py` | `BLOCKING_LIVE_OPS` | Sigma truth and Telegram instrumentation |
| `scripts/cashrun_detector.py` | `QUARANTINE` | operator/RP intelligence lane |
| `scripts/send_telegram_summary.py` | `QUARANTINE` | secret incident / Telegram |
| `app/static/dashboard/index.html` | `QUARANTINE` | operator dashboard only |
| `app/static/dashboard/sidecar_stack_latest.json` | `QUARANTINE` | generated runtime artifact |

## Additional Dirty Files Worth Tracking

### `docs/engineering/VELO_LLM_COUNCIL_V1.md`
- Status: modified
- Risk level: `LOW`
- Recommendation: `SAFE_TO_QUARANTINE`
- Notes: governance doc drift only

### `docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md`
- Status: modified
- Risk level: `LOW`
- Recommendation: `SAFE_TO_QUARANTINE`
- Notes: wiring-map drift only

### `scripts/audit_railway_supabase_run_status.py`
- Status: modified
- Risk level: `MEDIUM`
- Recommendation: `SAFE_TO_QUARANTINE`
- Notes: operational audit tooling, not live scoring, but still affects operator truth

### `scripts/sync_verdicts_from_supabase.py`
- Status: modified
- Risk level: `MEDIUM`
- Recommendation: `NEEDS_HUMAN_REVIEW`
- Notes: local verdict hydration can poison downstream operator truth if shape changes are wrong

### `scripts/velo_signal_tracker.py`
- Status: modified
- Risk level: `MEDIUM`
- Recommendation: `SAFE_TO_QUARANTINE`
- Notes: results/sidecar operator tracking, not live scoring

## Recommended Cleanup Lanes

### Lane 1 — Blocking Live Ops
Must be resolved before any live-affecting command:
- `app/services/velo_prime_service.py`
- `scripts/run_prime_today.py`
- `scripts/send_telegram_summary.py`
- `scripts/run_results_sigma.py`

### Lane 2 — Operator / Dashboard
Can be quarantined and reviewed separately:
- `app/static/dashboard/index.html`
- `app/static/dashboard/sidecar_stack_latest.json`
- `scripts/cashrun_detector.py`
- `scripts/velo_signal_tracker.py`

### Lane 3 — Governance / Audit
Review separately, low urgency for live freeze:
- `docs/engineering/VELO_LLM_COUNCIL_V1.md`
- `docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md`
- `scripts/audit_railway_supabase_run_status.py`

## Safe Next Actions
1. Freeze live-affecting execution from this worktree.
2. Quarantine `scripts/send_telegram_summary.py` immediately.
3. Review `app/services/velo_prime_service.py` and `scripts/run_prime_today.py` as a paired scoring-safety patch set.
4. Review `scripts/run_results_sigma.py` as a post-race truth / Telegram instrumentation patch set.
5. Treat dashboard and CASHRUN files as a separate operator-intelligence lane.

## Final Classification
`DIRTY_TREE_BLOCKING_LIVE_OPS`

The worktree is not safe for live-affecting operations until the high-risk dirty files are intentionally reviewed, quarantined, or removed from the active execution path.
