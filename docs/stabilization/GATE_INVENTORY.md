# GATE INVENTORY

This document lists all defensive gates and suppression rules currently implemented in the VÉLØ Oracle Prime system.

## 1. Mission Control Gates (`update_mission_control.py`)

| Gate Name | Condition | Severity | Resulting Action |
| :--- | :--- | :--- | :--- |
| **Flatline Gate** | `flatline_count > 0` | **CRITICAL** | `learning_gate = BLOCKED`, `promotion_gate = BLOCKED`. |
| **Identity Failure Gate** | `identity_failure_count > 0` | **HIGH** | `promotion_gate = BLOCKED`. |
| **Source Contamination** | `source_truth == RP_MERGED_CONTAMINATED` | **CRITICAL** | `learning_gate = BLOCKED`, `promotion_gate = BLOCKED`. |
| **Council Verdict Gate** | `council_verdict != PASS_TO_LEARNING` | **HIGH** | `shadow_consume = BLOCKED`. |
| **Runner Calibration** | `runner_count < 300` | **INFO** | `runner_calibration_gate = NEEDS_MORE_DATA`. |
| **Decision Policy** | `top_pick_decisions < 150` | **INFO** | `decision_policy_gate = NEEDS_MORE_DAYS`. |

## 2. Startup & Orchestration Gates (`app/main.py`)

| Gate Name | Condition | Severity | Resulting Action |
| :--- | :--- | :--- | :--- |
| **G Live Guard** | `VELO_G_SHADOW_MODE == live` | **CRITICAL** | `RuntimeError` (Startup Blocked). |
| **Execution Mode Guard** | `VELO_EXECUTION_MODE == LIVE` | **CRITICAL** | `RuntimeError` (Startup Blocked). |
| **Betfair Mode Guard** | `BETFAIR_MODE == LIVE` | **CRITICAL** | `RuntimeError` (Startup Blocked). |
| **Pipeline Wrapper Guard**| Canonical wrappers missing from `app/pipelines/` | **CRITICAL** | `RuntimeError` (Startup Blocked). |
| **Forbidden Import Guard**| Forbidden execution agents imported in live path | **CRITICAL** | `RuntimeError` (Startup Blocked). |
| **Schema Verification** | Required Supabase columns/tables missing | **CRITICAL** | `RuntimeError` (Startup Blocked). |

## 3. Scoring & Enforcement Gates

| Gate Name | Condition | Severity | Resulting Action |
| :--- | :--- | :--- | :--- |
| **Execution Bridge Block**| `VeloExecutionBridge.execute()` called in `LIVE` mode | **CRITICAL** | `RuntimeError` (Logic Blocked). |
| **Stale Run Gate** | Last `PASS` pipeline run > 26h ago | **WARNING** | `/health` returns `DEGRADED`. |
| **Model Corrupt Gate** | SQPE model fails `joblib.load()` | **CRITICAL** | `/health` returns `FAIL` (503). |

## 4. Graceful Degradation Strategy
The system follows a strict hierarchy of degradation:
1. **FULL_STRIKE:** All gates clear.
2. **VISION_ONLY:** Safety or quality issues detected; no execution allowed.
3. **DEGRADED:** Metadata or historical data missing; system operable but low-confidence.
4. **BLOCKED:** Critical path failure; app offline or specific pipeline disabled.
