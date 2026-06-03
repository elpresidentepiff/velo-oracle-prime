# VÉLØ HARNESS COMMANDS V1

This document outlines the available commands for the Secure Agent Runtime / Harness Hub (`scripts/ops/run_harness.py`). The harness serves as a central, read-only router for VÉLØ observability and operational scripts.

## Usage
`python scripts/ops/run_harness.py --cmd <command> [--date YYYY-MM-DD]`

## Available Commands

| Command | Description | Required Args |
| :--- | :--- | :--- |
| `harness-audit` | Scans morning models for feature leakage violations using the Bias-Variance governance rules. | None |
| `run-readiness` | Checks data completeness and readiness for a specific day's run in the New Build lane. | `--date` |
| `passport-coverage` | Counts passport coverage and Topspeed (TS) presence in the current card feed. | None |
| `sidecar-league` | Prints the current Sidecar Elo leaderboard (read-only from markdown). | None |
| `sigma-close` | Triggers the 3-step Sigma reconciliation sequence (reconciliation, memory distillation, Elo update). | `--date` |
| `dashboard-check` | Pings the dashboard truth endpoint (`/api/dashboard/truth-summary`) to verify operational status. | None |
| `context-budget` | Scans active scripts and flags any exceeding 500 lines to maintain manageable LLM context windows. | None |
| `markov-state` | Prints the Markov Hidden-State summary for a specific date. | `--date` |
| `rag-brief` | Prints the Agentic RAG evidence dossier for Tier A runners on a specific date. | `--date` |
| `graph-brief` | Prints the Graph-RAG Race Knowledge summary for a specific date. | `--date` |

## Safety Constraints
The harness is strictly read-only or acts as a controlled trigger for safe, predefined pipelines. It does not perform manual file mutations, direct database writes, or live scoring execution.
