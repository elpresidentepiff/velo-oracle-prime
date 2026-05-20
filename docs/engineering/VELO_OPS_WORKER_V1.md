# VÉLØ Ops Worker V1 - Technical Specification

## Overview
The VÉLØ Ops Worker is a deterministic orchestrator designed to manage the daily lifecycle of the VÉLØ racing operating system. It provides a unified CLI for ingestion, prediction, market snapshots, sigma reconciliation, and shadow learning.

## Core Philosophy
1. **Deterministic:** Operations follow a strict, repeatable path.
2. **Gated:** Every destructive or network-facing action requires explicit flags (`--execute`, `--allow-network`).
3. **Traceable:** Every job run is logged in the database and local artifacts.
4. **Idempotent:** Re-running a job should not create duplicate states or corrupt the database.

## State Machine
The worker manages the transition of a "Racing Day" through several states:
1. `INGESTED`: Racecards and API data are locally available.
2. `PREDICTED`: All races have full-runner predictions generated.
3. `SNAPSHOT_CAPTURED`: Pre-race market state is preserved.
4. `RECONCILED`: Results are matched against predictions (Sigma).
5. `LEARNED`: Verified events are fed into the shadow learning state.

## Safety Guards
- **Dry-Run by Default:** All commands perform no external side effects unless `--execute` is passed.
- **Network Isolation:** Network access is blocked unless `--allow-network` is passed.
- **Production Lock:** The worker is prohibited from overwriting `sentient_state.json` or promoting Playbook G to live in Phase 1.
