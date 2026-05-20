# VELO Quarantine Plan V1

## Purpose

This document marks older agent-era files and execution-betting modules so
they are not mistaken for the canonical live VÉLØ runtime.

This is a non-functional hygiene pass. No runtime behavior is changed.

## Why This Exists

The repo currently mixes:

1. legacy agent scaffolding
2. betting and execution modules
3. the modern script-driven scoring and evidence path

Without explicit quarantine, it is too easy to misread old modules as the
current system.

## Quarantine Groups

### LEGACY_AGENT

These files are historical scaffolding and are not the current production
worker system:

- [C:\Users\puror\velo-oracle-prime\src\agents\base_agent.py](C:\Users\puror\velo-oracle-prime\src\agents\base_agent.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\specialized_agents.py](C:\Users\puror\velo-oracle-prime\src\agents\specialized_agents.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_scout.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_scout.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_prime.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_prime.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_archivist.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_archivist.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_manus.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_manus.py)
- [C:\Users\puror\velo-oracle-prime\src\agents\velo_synth.py](C:\Users\puror\velo-oracle-prime\src\agents\velo_synth.py)

Policy:
- reference only
- do not treat as canonical runtime
- rebuild explicitly before reuse

### EXECUTION_BETTING

These files represent a betting or execution posture and are not the current
audit-first race-day operating layer:

- [C:\Users\puror\velo-oracle-prime\app\agents\betting_agents.py](C:\Users\puror\velo-oracle-prime\app\agents\betting_agents.py)
- [C:\Users\puror\velo-oracle-prime\app\agents\betfair_execution_agent.py](C:\Users\puror\velo-oracle-prime\app\agents\betfair_execution_agent.py)
- [C:\Users\puror\velo-oracle-prime\app\agents\betfair_trading_agents.py](C:\Users\puror\velo-oracle-prime\app\agents\betfair_trading_agents.py)
- [C:\Users\puror\velo-oracle-prime\app\agents\odds_movement_predictor.py](C:\Users\puror\velo-oracle-prime\app\agents\odds_movement_predictor.py)

Policy:
- segregated from the canonical scoring path
- do not confuse with the current no-staking / audit-first track
- only revive deliberately under explicit governance

## Canonical Runtime Reminder

The current live scoring and verification spine is:

1. [C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py](C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py)
2. [C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py](C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py)
3. [C:\Users\puror\velo-oracle-prime\src\intelligence\velo_prime_ensemble.py](C:\Users\puror\velo-oracle-prime\src\intelligence\velo_prime_ensemble.py)
4. [C:\Users\puror\velo-oracle-prime\scripts\run_results_sigma.py](C:\Users\puror\velo-oracle-prime\scripts\run_results_sigma.py)
5. [C:\Users\puror\velo-oracle-prime\src\preflight.py](C:\Users\puror\velo-oracle-prime\src\preflight.py)

## What Was Done

- created a machine-readable manifest:
  - [C:\Users\puror\velo-oracle-prime\data\velo_quarantine_manifest_v1.json](C:\Users\puror\velo-oracle-prime\data\velo_quarantine_manifest_v1.json)
- created folder-level quarantine markers:
  - [C:\Users\puror\velo-oracle-prime\src\agents\README_QUARANTINED.md](C:\Users\puror\velo-oracle-prime\src\agents\README_QUARANTINED.md)
  - [C:\Users\puror\velo-oracle-prime\app\agents\README_EXECUTION_BETTING.md](C:\Users\puror\velo-oracle-prime\app\agents\README_EXECUTION_BETTING.md)

## Next Step

Update the remaining ops and classification docs so they explicitly point to:

- runtime map
- quarantine manifest
- canonical live spine

Only after that should a new `Supervisor`, `Verifier`, or `Deep-Dive` worker layer be built.
