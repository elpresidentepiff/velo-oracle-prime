import subprocess
import sys
import os
from pathlib import Path

EXPECTED_ROOT_END = "velo-oracle-prime"
EXPECTED_BRANCH = "main"
EXPECTED_REMOTE = "elpresidentepiff/velo-oracle-prime"

def run_cmd(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def assert_canonical():
    try:
        root = run_cmd("git rev-parse --show-toplevel")
        branch = run_cmd("git branch --show-current")
        remote = run_cmd("git remote -v")
        head = run_cmd("git rev-parse HEAD")
        
        fail_reasons = []
        
        if not root.endswith(EXPECTED_ROOT_END):
            fail_reasons.append(f"Root directory mismatch. Found: {root}")
            
        if branch != EXPECTED_BRANCH:
            fail_reasons.append(f"Branch mismatch. Found: {branch}")
            
        if EXPECTED_REMOTE not in remote:
            fail_reasons.append(f"Remote mismatch. Expected: {EXPECTED_REMOTE}")
            
        if "OneDrive" in root or "feature_v10_launch_fix" in root:
            fail_reasons.append("Running inside a stale worktree (OneDrive/feature_v10).")

        if fail_reasons:
            print("CANONICAL_WORKTREE_FAIL")
            print("reason:")
            for r in fail_reasons:
                print(f"  - {r}")
            print(f"current_root:   {root}")
            print(f"current_branch: {branch}")
            print(f"current_remote: {remote.split('\\n')[0]}")
            print(f"HEAD:           {head}")
            print(f"expected_root:  .../{EXPECTED_ROOT_END}")
            print(f"expected_branch: {EXPECTED_BRANCH}")
            sys.exit(2)
        else:
            print("CANONICAL_WORKTREE_OK")
            print(f"HEAD: {head}")
            sys.exit(0)
            
    except Exception as e:
        print(f"CANONICAL_WORKTREE_FAIL\nreason: {str(e)}")
        sys.exit(2)

if __name__ == "__main__":
    assert_canonical()
