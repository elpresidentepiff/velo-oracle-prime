#!/usr/bin/env python3
"""
VÉLØ Worktree Safety Runner
============================
Acts as a hard safety gate before any repo-changing command.
Audits branch, HEAD, and dirty state.

Usage:
    python scripts/ops/worktree_safety_runner.py --mode audit
    python scripts/ops/worktree_safety_runner.py --mode audit --expected-branch stabilization/prime-hardening-v1
    python scripts/ops/worktree_safety_runner.py --mode run --expected-branch stabilization/prime-hardening-v1 -- pytest tests/test_capture_proof.py
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Identify ROOT
# Use environment variable for testing override, otherwise use current working directory
ROOT = Path(os.environ.get("VELO_SAFETY_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT))

# Mandatory States
WORKTREE_SAFE = "WORKTREE_SAFE"
WORKTREE_DIRTY = "WORKTREE_DIRTY"
WORKTREE_WRONG_BRANCH = "WORKTREE_WRONG_BRANCH"
WORKTREE_HEAD_MISMATCH = "WORKTREE_HEAD_MISMATCH"
WORKTREE_NO_GIT_REPO = "WORKTREE_NO_GIT_REPO"
WORKTREE_COMMAND_BLOCKED = "WORKTREE_COMMAND_BLOCKED"
WORKTREE_COMMAND_OK = "WORKTREE_COMMAND_OK"
WORKTREE_COMMAND_FAILED = "WORKTREE_COMMAND_FAILED"

# Optional Sub-states
WORKTREE_UNTRACKED_FILES_PRESENT = "WORKTREE_UNTRACKED_FILES_PRESENT"
WORKTREE_STAGED_CHANGES_PRESENT = "WORKTREE_STAGED_CHANGES_PRESENT"
WORKTREE_UNSTAGED_CHANGES_PRESENT = "WORKTREE_UNSTAGED_CHANGES_PRESENT"

def _run_git(args: List[str], cwd: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git"] + args, cwd=cwd, stderr=subprocess.STDOUT, text=True
        ).strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: {e.output}")
    except Exception as e:
        raise RuntimeError(f"Failed to run git: {str(e)}")

def get_worktree_status(cwd: Path = ROOT) -> dict:
    status = {
        "is_git": False,
        "branch": None,
        "head": None,
        "head_full": None,
        "staged_files": [],
        "unstaged_files": [],
        "untracked_files": [],
        "is_dirty": False,
        "errors": []
    }

    if not (cwd / ".git").exists() and not os.environ.get("VELO_TEST_GIT"):
        # Check if we are inside a git repo (might be a subdirectory)
        try:
            _run_git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
        except Exception:
            status["errors"].append("Not a git repository")
            return status

    status["is_git"] = True
    try:
        status["branch"] = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        status["head"] = _run_git(["rev-parse", "--short", "HEAD"], cwd=cwd)
        status["head_full"] = _run_git(["rev-parse", "HEAD"], cwd=cwd)

        # Staged
        staged = _run_git(["diff", "--cached", "--name-only"], cwd=cwd)
        if staged:
            status["staged_files"] = staged.splitlines()

        # Unstaged
        unstaged = _run_git(["diff", "--name-only"], cwd=cwd)
        if unstaged:
            status["unstaged_files"] = unstaged.splitlines()

        # Untracked
        untracked = _run_git(["ls-files", "--others", "--exclude-standard"], cwd=cwd)
        if untracked:
            status["untracked_files"] = untracked.splitlines()

        status["is_dirty"] = bool(status["staged_files"] or status["unstaged_files"] or status["untracked_files"])

    except Exception as e:
        status["errors"].append(str(e))

    return status

def run_safety_check(
    expected_branch: Optional[str] = None,
    expected_head: Optional[str] = None,
    allow_untracked: bool = False,
    cwd: Path = ROOT
) -> Tuple[str, str, dict]:
    """
    Returns (status, state, details)
    """
    details = get_worktree_status(cwd)
    errors = details["errors"]
    
    if not details["is_git"]:
        return "FAIL", WORKTREE_NO_GIT_REPO, details

    # Logic gates
    if expected_branch and details["branch"] != expected_branch:
        return "FAIL", WORKTREE_WRONG_BRANCH, details

    if expected_head:
        # Check both short and full
        if details["head"] != expected_head and details["head_full"] != expected_head:
            return "FAIL", WORKTREE_HEAD_MISMATCH, details

    if details["staged_files"]:
        return "FAIL", WORKTREE_DIRTY, details

    if details["unstaged_files"]:
        return "FAIL", WORKTREE_DIRTY, details

    if details["untracked_files"] and not allow_untracked:
        return "FAIL", WORKTREE_DIRTY, details

    if errors:
        return "FAIL", WORKTREE_DIRTY, details

    return "PASS", WORKTREE_SAFE, details

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Worktree Safety Runner")
    parser.add_argument("--mode", choices=["audit", "run"], default="audit")
    parser.add_argument("--expected-branch", help="Expected git branch name")
    parser.add_argument("--expected-head", help="Expected git HEAD hash (short or full)")
    parser.add_argument("--allow-untracked", action="store_true", help="Allow untracked files in a safe worktree")
    parser.add_argument("--output", default="data/current/worktree_safety_latest.json", help="Path to write JSON artifact")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run if safe (use -- to separate)")

    args = parser.parse_args()

    # If command starts with --, remove it
    cmd_to_run = args.command
    if cmd_to_run and cmd_to_run[0] == "--":
        cmd_to_run = cmd_to_run[1:]

    status, state, details = run_safety_check(
        expected_branch=args.expected_branch,
        expected_head=args.expected_head,
        allow_untracked=args.allow_untracked
    )

    command_executed = False
    command_exit_code = None
    
    if args.mode == "run":
        if status == "PASS":
            if not cmd_to_run:
                status = "FAIL"
                state = WORKTREE_COMMAND_FAILED
                details["errors"].append("No command provided for run mode")
            else:
                try:
                    print(f"[SAFETY] Executing: {' '.join(cmd_to_run)}")
                    result = subprocess.run(cmd_to_run, cwd=ROOT)
                    command_executed = True
                    command_exit_code = result.returncode
                    if command_exit_code == 0:
                        state = WORKTREE_COMMAND_OK
                    else:
                        state = WORKTREE_COMMAND_FAILED
                        status = "FAIL"
                except Exception as e:
                    status = "FAIL"
                    state = WORKTREE_COMMAND_FAILED
                    details["errors"].append(f"Command execution failed: {str(e)}")
        else:
            state = WORKTREE_COMMAND_BLOCKED
            print(f"[SAFETY] Command BLOCKED due to state: {state}")

    # Final Payload
    payload = {
        "status": status,
        "state": state,
        "branch": details["branch"],
        "head": details["head"],
        "expected_branch": args.expected_branch,
        "expected_head": args.expected_head,
        "is_dirty": details["is_dirty"],
        "staged_files": details["staged_files"],
        "unstaged_files": details["unstaged_files"],
        "untracked_files": details["untracked_files"],
        "command_requested": " ".join(cmd_to_run) if cmd_to_run else None,
        "command_executed": command_executed,
        "command_exit_code": command_exit_code,
        "errors": details["errors"],
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    # Write artifact
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)

    # Print summary to stdout for agents
    print(json.dumps(payload, indent=2))
    
    # Exit with code reflecting success
    sys.exit(0 if status == "PASS" else 1)

if __name__ == "__main__":
    main()
