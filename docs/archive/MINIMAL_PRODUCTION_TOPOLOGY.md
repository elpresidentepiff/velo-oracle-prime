# MINIMAL PRODUCTION TOPOLOGY

**Date:** 2026-06-10 · Target lean setup after the decommission packet is approved.

## Current topology (the truth)
```
GitHub Actions (zombie schedulers, 50 failed fires/day)
      │ HTTP triggers
      ▼
Railway: 5 services ── velo-oracle (502 DEAD) ── velo-prime-scoring (dormant)
                    ── enchanting-exploration (duplicate) ── ingestion-spine (legacy)
                    ── hermes-agent (UNKNOWN, service-role armed) + 1 volume
      ▼
Supabase (35 live tables / 25 empty)
      ▲
Operator WSL box ──── the ONLY living writer (manual daily chain)
```

## Target topology
```
GitHub Actions (ONE workflow: daily-chain-contract CI on PR — no prod schedules
                until the orchestrator is approved)
Railway (phase 1): velo-oracle ONLY, healthy, serving dashboard/API
        (phase 2, post-orchestrator): + ONE scheduled closeout worker
        hermes-agent: operator decision after review (separate project if kept)
Supabase: lean table set —
  verdicts · races/runners · racing_horse_runs · runner_release_candidates
  · sigma_audits · race_results/runner_results · pipeline_runs
  · learned_patterns/permanent_principles · BHA trio · profile banks
  + (future) odds_snapshots for BSP · + (migration) source_truth/feature_degraded on verdicts
Operator box: remains the approving brain; stops being the only engine
```

## Gap → migration steps
1. Approve packet items 1–2 (kill zombie schedules) — instant noise stop.
2. Secret rotation (packet 11) → delete local dumps (12).
3. Operator dashboard session: review hermes-agent (4), confirm duplicate (3), then disable.
4. Decide velo-oracle: redeploy healthy from this branch after June 11, or park Railway entirely and adopt GH-runner orchestrator (ONE_RACE_DAY_COMMAND_SPEC) — **either is fine; running both half-alive is not.**
5. Archive empty tables (9) with migration manifest.
6. Re-point CI from ingestion_spine to `tests/` (Loop 9 fix) and retire spine (7).

**Principle:** one scheduler, one writer per table, zero unknown service-role holders, and nothing that fires into a 502.
