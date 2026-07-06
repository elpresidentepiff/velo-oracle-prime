# CLAUDE.md — Agent Operating Instructions (docs/current spine)

**This is the detailed companion to root `CLAUDE.md`.** Root `CLAUDE.md` is the short
pointer-only version every session loads automatically. This file is the fuller
operating contract for any agent (Claude or otherwise) working inside this repo,
referenced from `docs/current/AGENTS.md` and `docs/current/CURRENT_STATE.md`.

## What VÉLØ is

An auditable UK/IRE horse-racing prediction system. It captures Racing Post HTML,
scores every race with a governed ML ensemble, persists verdicts to Supabase,
reconciles against results nightly (Sigma), and accumulates evidence under hard
learning gates. **No live staking. Not a tips service.** Full definition:
`docs/current/ONE_TRUTH.md`.

## Repo safety rules

1. **Racing API is permanently decommissioned for live use.** RP (Racing Post)
   HTML via `racing_post_account_collector.py` is the only live data path. Any
   live-path import of Racing API is a blocker.
2. **No live staking.** The execution bridge is SIM/PAPER only, with hard runtime
   guards in `src/velo/execution_bridge.py`.
3. **Live model weights are frozen.** No promotion of any shadow/challenger model
   without an explicit operator gate decision recorded in `docs/current/ONE_TRUTH.md`.
4. **RPDC is horse-career memory.** PDF intelligence is a separate feature and must
   never overwrite RPDC fields (`runner_release_candidates`).
5. **Mission Control derives source truth only from the observability packet** —
   never by default, never by inference. Missing/malformed packet = `UNKNOWN` =
   learning blocked.
6. **Sigma Telegram format is locked.** Always use `run_results_sigma.py`. Never
   hand-edit the report format.
7. **No new numbered/duplicate truth files.** `docs/current/ONE_TRUTH.md` is the
   only living truth file. Do not create `ONE_TRUTH_V2.md`, `THE_NEW_TRUTH.md`, etc.

## No live mutation rule

Unless a mission explicitly authorizes it, an agent must never:
- Write to Supabase (any table).
- Send a Telegram message.
- Promote a shadow/challenger model to live.
- Change `velo_prime_ensemble.py` live weights/profile, `models/sqpe_v17/`, or
  `models/specialist/`.
- Deploy to production or touch Railway cron config.

These map to the enforced boundaries in `docs/current/SIDE_EFFECT_SENTINEL.md` and
the full list in `docs/current/FORBIDDEN_ACTIONS.md`.

## Evidence-first rule

No claim about model behaviour, dashboard display, or result outcome is accepted
without naming the exact source file/function/field that produced it. This is
formal law in `docs/current/MODEL_RESULT_REPORTING_LAW.md` (adopted 2026-07-05
after the Little Lady Rock / race 922118 correction chain). In short: model rank,
policy decision, staking authorisation, and race result are four distinct facts —
never collapse them into one word ("result").

## Artifact-path requirement

Every mission output must be a real file at a stated path, or explicitly
`MISSING_ARTIFACT` with the expected path named. Never fabricate a plausible-looking
number when the underlying artifact does not exist. See
`docs/current/ARTIFACT_REGISTRY.md` for what already exists and where.

## Final closeout format

Every mission should close with (at minimum):
- Branch
- Commit
- Files created/updated
- Tests/checks run
- Safety classifications (see `docs/current/FORBIDDEN_ACTIONS.md` for the standard
  classification vocabulary: `NO_LIVE_SCORING_CHANGE`, `NO_SUPABASE_WRITES`,
  `NO_TELEGRAM_SEND`, `NO_MODEL_PROMOTION`, etc.)
- Next recommended mission

## No Supabase / Telegram / model promotion unless explicitly approved

Any mission that needs to write to Supabase, send Telegram, or promote a model must
carry an explicit operator instruction authorizing that specific action for that
specific mission. Absent that instruction, treat all three as forbidden, regardless
of how "obviously correct" the write looks. Precedent: canonical Supabase writes for
`canonical_model_scorecards` / `canonical_learning_events` were only made after the
operator's explicit "write these to canonical scorecards in supabase yes" — see
`data/reports/july06_canonical_runtime_persistence_report.md`.

## Where to look first

- Operational law: `docs/current/ONE_TRUTH.md`
- Step-by-step daily commands (Steps 1-20): root `THE_ONE_TRUTH.md`
- Race day lifecycle: `docs/current/RACE_DAY_RUNBOOK.md`
- Learning gate: `docs/current/LEARNING_ADMISSION_GATE.md`
- VFU state: `docs/current/VFU_INDEX.md`
- System architecture: `docs/current/SYSTEM_MAP.md`
- Fast orientation for a new agent: `docs/current/CURRENT_STATE.md`
- Agent roles: `docs/current/AGENTS.md`
