# VÉLØ Task Contract Runner

**Date:** 2026-06-11
**Status:** ACTIVE
**Classification:** OPS_HARDENING

## 1. Purpose

The Task Contract Runner enforces mission scope by validating changes against a machine-readable contract. It prevents agents from making out-of-scope edits, accidental scoring changes, unauthorized database writes, or hidden production mutations.

## 2. The Task Contract

A task contract is a JSON file that defines the boundaries for a specific task:

- `task_id`: Unique identifier for the mission.
- `allowed_paths`: List of file paths or directories where changes are permitted.
- `forbidden_paths`: List of critical directories that must never be touched.
- `forbidden_keywords`: List of terms (e.g., `supabase`, `live_scoring`) that must not appear in the git diff.
- `classification_required`: List of mandatory final classifications (e.g., `NO_LIVE_SCORING_CHANGE`).

## 3. Explicit Safety States

The runner reports one of the following states:

- `TASK_CONTRACT_OK`: Audit passed; changes are within declared scope.
- `TASK_CONTRACT_MISSING`: The specified contract JSON file was not found.
- `TASK_CONTRACT_INVALID_JSON`: The contract file contains malformed JSON or missing fields.
- `TASK_CONTRACT_FORBIDDEN_PATH_TOUCHED`: Changes detected in a forbidden directory.
- `TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED`: Changes detected in a file not listed in `allowed_paths`.
- `TASK_CONTRACT_FORBIDDEN_KEYWORD_FOUND`: A forbidden keyword was detected in the git diff text.
- `TASK_CONTRACT_CLASSIFICATION_MISSING`: Required final classifications were missing from the report.
- `TASK_CONTRACT_FAILED`: Catch-all for execution errors or unexpected failures.

## 4. Usage

### Preflight (Verify Contract)
Check if a contract is valid before starting work:
```bash
python scripts/ops/task_contract_runner.py --contract ops/task_contracts/P0-3.json --mode preflight
```

### Audit (Verify Execution)
Check if the work performed matches the contract:
```bash
python scripts/ops/task_contract_runner.py --contract ops/task_contracts/P0-3.json --mode audit --base-ref HEAD~1 --classification-file final_report.md
```

## 5. Artifacts

The runner always writes its final state to:
`data/current/task_contract_latest.json`

---
*NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.*
