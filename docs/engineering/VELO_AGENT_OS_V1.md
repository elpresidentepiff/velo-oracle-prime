# VELO Agent OS V1

## Goal
Turn VELO from a script-driven racing workflow into a governed multi-agent operating system.

## Core Pattern
`Planner -> Specialist Agent -> Evaluator -> Safety Sentinel -> Audit Ledger -> Shadow Learning`

This is not a one-agent system. It is a controlled operating model where specialist agents can only act inside explicit safety boundaries.

## Architecture

### Planner
- Supervisor Agent
- decides what is safe to run next
- does not score, learn, or promote

### Specialist Agents
- Morning Ingestion Agent
- RacingPostAdapter Agent
- Racing API Spine Agent
- Market Agent
- VELO Scoring Agent
- Convergence Agent
- Sigma Agent
- Learning Agent
- Report Agent
- Red Team Agent

### Evaluators
- Sigma Agent for results truth
- Report Agent for operator-grade visibility
- Safety Sentinel Agent for veto power

### Safety and Memory
- Safety Sentinel blocks unsafe commands before mutation
- Audit Ledger records artifacts, reports, and branch truth
- Shadow Learning is allowed only into approved shadow targets

## Current Platform Truth
- live state: `data/sentient_state.json` is protected
- contaminated state: `shadow_full_train_v1`
- approved shadow target: `shadow_full_train_v2`
- Racing Post: primary intelligence layer
- Racing API: structure, IDs, results, fallback
- CASHRUN: operator visibility layer
- live learning: blocked

## First Implementation Slice
This V1 slice is intentionally small:
- governance docs
- Learning State Registry
- read-only Mission Control
- Safety Sentinel
- Agent Registry skeleton

No autonomous executor is enabled in this slice.

## Non-Goals for V1
- no model retraining engine
- no live promotion
- no automated staking
- no GUI operator control
- no autonomous write-capable orchestration
- no video/race vision

## Success Criteria
`VELO_AGENT_OS_FOUNDATION_READY` means:
- daily EOD zero-results hard-stop is enforced
- learning target registry is explicit
- Mission Control can summarize state read-only
- Safety Sentinel can classify `SAFE`, `WARN`, `BLOCK`
- Agent roles and permissions are documented
