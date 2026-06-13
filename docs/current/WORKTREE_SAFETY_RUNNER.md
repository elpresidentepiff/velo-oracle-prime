# VÉLØ Worktree Safety Runner

**Date:** 2026-06-11
**Status:** ACTIVE
**Classification:** OPS_HARDENING

## 1. Purpose

The Worktree Safety Runner is a hard safety gate that audits the repository state before executing any command that might modify the codebase or environment. It prevents "agent chaos" by ensuring that commands are only run on the correct branch, at the expected commit, and in a clean worktree.

## 2. Core Safety Rules

Execution is **BLOCKED** and returns a non-PASS status if:
- The repository is "dirty" (staged changes, unstaged changes, or untracked files).
- The current branch does not match the `--expected-branch` (if provided).
- The current HEAD does not match the `--expected-head` (if provided).
- The command itself fails (returns non-zero exit code).

## 3. Explicit Safety States

The runner reports one of the following states:

- `WORKTREE_SAFE`: Audit passed, repo is clean and matches expectations.
- `WORKTREE_DIRTY`: Repo has uncommitted changes or untracked files.
- `WORKTREE_WRONG_BRANCH`: Current branch does not match `--expected-branch`.
- `WORKTREE_HEAD_MISMATCH`: Current HEAD does not match `--expected-head`.
- `WORKTREE_NO_GIT_REPO`: Script executed outside of a git repository.
- `WORKTREE_COMMAND_BLOCKED`: Safety check failed; command was not executed.
- `WORKTREE_COMMAND_OK`: Safety check passed and command returned exit code 0.
- `WORKTREE_COMMAND_FAILED`: Safety check passed but command returned non-zero.

## 4. Usage

### Audit Only
Audit the current worktree state:
```bash
python scripts/ops/worktree_safety_runner.py --mode audit --expected-branch stabilization/prime-hardening-v1
```

### Run Command (Safe Mode)
Run a command only if the worktree is safe:
```bash
python scripts/ops/worktree_safety_runner.py --mode run --expected-branch stabilization/prime-hardening-v1 -- pytest tests/test_capture_proof.py
```

## 5. Artifacts

The runner always writes its final state to:
`data/current/worktree_safety_latest.json`

This artifact is machine-readable and should be used by downstream loops to verify the provenance of any repo changes.

---
*NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.*
