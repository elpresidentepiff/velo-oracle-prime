# VELO Runtime Map V1

## Purpose

This document defines the canonical runtime shape of `velo-oracle-prime` as it exists now.

The repo currently contains three overlapping eras:

1. legacy multi-agent scaffolding
2. betting and execution systems
3. the newer evidence, audit, and operator-visibility stack

The job of this map is to identify what is live, what is support, what is audit, and what should be treated as legacy or quarantine material.

## What Recent Commits Were Actually Doing

The recent commit stream is centered on auditability and operator visibility, not on a clean worker-agent runtime:

- `bfe983a` Racing API shadow enrichment forward-test logging
- `0d24bbb` Telegram Signal Stack display patch
- `0bf2be7` operator visibility resolution
- `c1e61d2` Playbook G v3 offline candidate package
- `d4029f1` shadow ledger design + Telegram attribution panel + Special Day V2
- `3a007eb` candidate lane design
- `0cfbbed` unified evidence audit truth layer
- `06ba74b` router shadow audit hardening
- `fb46db5` execution router evidence engine

That means the repo's newest coherent operating layer is the evidence and operator layer.

## Canonical Runtime

### LIVE_RUNTIME

- [C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py](C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py)
  Role: primary race-day scoring pipeline

- [C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py](C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py)
  Role: canonical `score_race_velo_prime` wire-in layer

- [C:\Users\puror\velo-oracle-prime\src\intelligence\velo_prime_ensemble.py](C:\Users\puror\velo-oracle-prime\src\intelligence\velo_prime_ensemble.py)
  Role: production meta-ensemble probability engine

- [C:\Users\puror\velo-oracle-prime\scripts\run_results_sigma.py](C:\Users\puror\velo-oracle-prime\scripts\run_results_sigma.py)
  Role: results reconciliation and sigma loop

- [C:\Users\puror\velo-oracle-prime\src\preflight.py](C:\Users\puror\velo-oracle-prime\src\preflight.py)
  Role: hard precondition gate for scoring entrypoints

### LIVE_SUPPORT

- [C:\Users\puror\velo-oracle-prime\app\core\runtime_env.py](C:\Users\puror\velo-oracle-prime\app\core\runtime_env.py)
  Role: environment and runtime resolution

- [C:\Users\puror\velo-oracle-prime\src\velo\racing_api_shadow_enrichment.py](C:\Users\puror\velo-oracle-prime\src\velo\racing_api_shadow_enrichment.py)
  Role: shadow-only Racing API enrichment cache and ledger support

- [C:\Users\puror\velo-oracle-prime\scripts\preflight_10am_check.py](C:\Users\puror\velo-oracle-prime\scripts\preflight_10am_check.py)
  Role: read-only preflight operational check

- [C:\Users\puror\velo-oracle-prime\scripts\velo_morning_cockpit.py](C:\Users\puror\velo-oracle-prime\scripts\velo_morning_cockpit.py)
  Role: operator daily brief across truth tables

- [C:\Users\puror\velo-oracle-prime\scripts\production_checks.py](C:\Users\puror\velo-oracle-prime\scripts\production_checks.py)
  Role: Railway and Cloudflare health checks

- [C:\Users\puror\velo-oracle-prime\scripts\velo_ops_check.py](C:\Users\puror\velo-oracle-prime\scripts\velo_ops_check.py)
  Role: git, Railway, Supabase, Telegram, and route cross-check

### AUDIT_EVIDENCE

- [C:\Users\puror\velo-oracle-prime\scripts\run_velo_unified_evidence_audit.py](C:\Users\puror\velo-oracle-prime\scripts\run_velo_unified_evidence_audit.py)
- [C:\Users\puror\velo-oracle-prime\scripts\router_shadow_audit.py](C:\Users\puror\velo-oracle-prime\scripts\router_shadow_audit.py)
- [C:\Users\puror\velo-oracle-prime\scripts\racing_api_shadow_forward_audit.py](C:\Users\puror\velo-oracle-prime\scripts\racing_api_shadow_forward_audit.py)
- [C:\Users\puror\velo-oracle-prime\scripts\audit_telegram_signal_visibility.py](C:\Users\puror\velo-oracle-prime\scripts\audit_telegram_signal_visibility.py)
- [C:\Users\puror\velo-oracle-prime\scripts\audit_vp30_lineage.py](C:\Users\puror\velo-oracle-prime\scripts\audit_vp30_lineage.py)
- [C:\Users\puror\velo-oracle-prime\scripts\generate_special_day_report.py](C:\Users\puror\velo-oracle-prime\scripts\generate_special_day_report.py)

These are not the scoring core, but they are part of the current operational truth layer.

### EXECUTION_BETTING

- [C:\Users\puror\velo-oracle-prime\app\agents\betting_agents.py](C:\Users\puror\velo-oracle-prime\app\agents\betting_agents.py)
- [C:\Users\puror\velo-oracle-prime\app\agents\betfair_execution_agent.py](C:\Users\puror\velo-oracle-prime\app\agents\betfair_execution_agent.py)
- [C:\Users\puror\velo-oracle-prime\app\agents\betfair_trading_agents.py](C:\Users\puror\velo-oracle-prime\app\agents\betfair_trading_agents.py)
- [C:\Users\puror\velo-oracle-prime\src\velo\execution_bridge.py](C:\Users\puror\velo-oracle-prime\src\velo\execution_bridge.py)
- [C:\Users\puror\velo-oracle-prime\src\velo\execution_guard.py](C:\Users\puror\velo-oracle-prime\src\velo\execution_guard.py)

These files are real and non-trivial, but they belong to a betting and execution posture that does not match the current audit-first track.

### LEGACY_AGENT

- [C:\Users\puror\velo-oracle-prime\src\agents\base_agent.py](C:\Users\puror\velo-oracle-prime\src\agents\base_agent.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\specialized_agents.py](C:\Users\puror\velo-oracle-prime\src\agents\specialized_agents.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_scout.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_scout.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_prime.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_prime.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_archivist.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_archivist.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_manus.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_manus.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_synth.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_synth.py)

These files should not be treated as the current live worker system.

## Why The Repo Feels Messy

### 1. There are multiple competing architectures

- generic multi-agent orchestration
- betting-agent architecture
- execution bridge architecture
- script-driven race-day runtime
- new evidence and operator stack

There is no single file or folder today that says "this is the one true runtime."

### 2. Legacy agents are not production-safe

The clearest examples:

- [C:\Users\puror\velo-oracle-prime\src\agents\specialized_agents.py](C:\Users\puror\velo-oracle-prime\src\agents\specialized_agents.py)
  The analyst logic still uses placeholder randomness for core signals.

- [C:\Users\puror\velo-oracle-prime\src\agents\velo_scout.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_scout.py)
  The Racing API routes are stale against the verified `/v1/racecards/...` path.

- [C:\Users\puror\velo-oracle-prime\src\agents\velo_prime.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_prime.py)
  It is a legacy Five Filters conversational wrapper, not the current production scoring chain.

### 3. Betting and execution code still sits next to audit-first infrastructure

The repo now has a strong evidence-first operating doctrine, but execution code remains present and substantial. That creates conceptual drag even if those files are not being used today.

### 4. Some ops docs are stale

[C:\Users\puror\velo-oracle-prime\scripts\DANGEROUS_SCRIPTS.md](C:\Users\puror\velo-oracle-prime\scripts\DANGEROUS_SCRIPTS.md) still describes a production map that does not perfectly match the files actually present now.

## Current Truth

The real runtime today is script-driven:

1. load or fetch racecards
2. normalize
3. score through `score_race_velo_prime`
4. persist verdicts
5. render Telegram Signal Stack
6. later reconcile outcomes in sigma

That is the actual operating chain. The repo's existing "agent" code is not the canonical implementation of that chain.

## Recommended Next Build Step

Before building any new `Supervisor`, `Verifier`, or `Deep-Dive` layer:

1. quarantine or clearly label `LEGACY_AGENT` files
2. quarantine or clearly label `EXECUTION_BETTING` files
3. update operational docs so the runtime map matches reality
4. only then build the new worker layer against the actual script-driven core

## Bottom Line

The repo is not missing capability.

It is missing a clean boundary between:

- what is live
- what is support
- what is audit
- what is legacy
- what is execution-only

This map is the first step toward that cleanup.
