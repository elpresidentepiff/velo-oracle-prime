#!/usr/bin/env python3
"""
VÉLØ Governed Task Runner
==========================
Unified orchestration layer that chains all P0 safety runners.
Mandatory entry point for all agent tasks.

Workflow:
1. Worktree Safety Check
2. Task Contract Preflight (Scope)
3. Side-Effect Sentinel (Production Risk)
4. Command Execution (if safe)
5. Task Contract Audit (Result)
6. Side-Effect Sentinel Audit (Final)

Usage:
    python scripts/ops/governed_task_runner.py \\
        --expected-branch stabilization/prime-hardening-v1 \\
        --contract ops/task_contracts/P1-1.json \\
        -- pytest tests/test_side_effect_sentinel.py
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
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def _run_script(script_name: str, args: List[str]) -> Tuple[int, str]:
    script_path = ROOT / "scripts" / "ops" / script_name
    cmd = [sys.executable, str(script_path)] + args
    print(f"[GOVERNOR] Calling: {script_name} {' '.join(args)}")
    
    # We use capture_output to inspect JSON but also let stdout/stderr flow if needed
    # Actually, for the governor, we want to capture JSON result.
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return result.returncode, result.stdout

class GovernedTaskRunner:
    def __init__(self, args):
        self.args = args
        self.results = {}
        self.status = "UNKNOWN"
        self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.output_json = ROOT / "data" / "current" / "governed_task_latest.json"

    def run(self):
        print(f"\n[GOVERNOR] Starting Governed Task execution...")
        
        # 1. Worktree Safety
        wt_args = ["--mode", "audit"]
        if self.args.expected_branch: wt_args.extend(["--expected-branch", self.args.expected_branch])
        if self.args.expected_head: wt_args.extend(["--expected-head", self.args.expected_head])
        
        rc, out = _run_script("worktree_safety_runner.py", wt_args)
        self.results["worktree"] = self._parse_json(out)
        if rc != 0:
             return self.fail("WORKTREE_SAFETY_FAILED")

        # 2. Task Contract Preflight
        tc_args = ["--contract", self.args.contract, "--mode", "preflight"]
        rc, out = _run_script("task_contract_runner.py", tc_args)
        self.results["contract_preflight"] = self._parse_json(out)
        if rc != 0:
            return self.fail("CONTRACT_PREFLIGHT_FAILED")

        # 3. Side-Effect Sentinel Audit
        se_args = ["--mode", "audit"]
        if self.args.classification_file: se_args.extend(["--classification-file", self.args.classification_file])
        se_args.append("--")
        se_args.extend(self.args.command)
        
        rc, out = _run_script("side_effect_sentinel.py", se_args)
        self.results["side_effect_audit"] = self._parse_json(out)
        if rc != 0:
            return self.fail("SIDE_EFFECT_AUDIT_FAILED")

        # 4. Command Execution (via Sentinel RUN mode for ultimate protection)
        print(f"\n[GOVERNOR] All gates passed. Executing command...")
        se_run_args = ["--mode", "run"]
        if self.args.classification_file: se_run_args.extend(["--classification-file", self.args.classification_file])
        se_run_args.append("--")
        se_run_args.extend(self.args.command)
        
        # In run mode, we want the output to be live for the operator
        run_cmd = [sys.executable, str(ROOT / "scripts" / "ops" / "side_effect_sentinel.py")] + se_run_args
        res = subprocess.run(run_cmd, cwd=ROOT)
        self.results["execution_exit_code"] = res.returncode
        
        if res.returncode != 0:
            # We don't stop here, we still want the audit
            print(f"[GOVERNOR] Warning: Command exited with code {res.returncode}")

        # 5. Final Task Contract Audit
        print(f"\n[GOVERNOR] Task complete. Performing final audit...")
        tca_args = ["--contract", self.args.contract, "--mode", "audit"]
        if self.args.base_ref: tca_args.extend(["--base-ref", self.args.base_ref])
        if self.args.classification_file: tca_args.extend(["--classification-file", self.args.classification_file])
        
        rc, out = _run_script("task_contract_runner.py", tca_args)
        self.results["contract_audit"] = self._parse_json(out)
        
        if rc == 0:
            self.status = "PASS"
            print(f"\n[GOVERNOR] SUCCESS: Task governed and verified.")
        else:
            self.status = "FAIL"
            print(f"\n[GOVERNOR] FAILURE: Task final audit failed.")

        return self.save()

    def _parse_json(self, text: str) -> dict:
        try:
            # Find JSON block
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"raw_output": text}
        except:
            return {"error": "Failed to parse JSON", "raw": text}

    def fail(self, reason: str):
        self.status = "FAIL"
        self.results["failure_reason"] = reason
        print(f"\n[GOVERNOR] ABORTED: {reason}")
        return self.save()

    def save(self):
        payload = {
            "status": self.status,
            "results": self.results,
            "created_at": self.created_at
        }
        self.output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_json, "w") as f:
            json.dump(payload, f, indent=2)
        
        sys.exit(0 if self.status == "PASS" else 1)

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Governed Task Runner")
    parser.add_argument("--expected-branch", help="Expected git branch")
    parser.add_argument("--expected-head", help="Expected HEAD commit")
    parser.add_argument("--contract", required=True, help="Path to P0-3 task contract")
    parser.add_argument("--base-ref", help="Base ref for final contract audit (defaults to staged/unstaged)")
    parser.add_argument("--classification-file", help="Path to classification file")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Task command to run (use -- to separate)")

    args = parser.parse_args()
    
    # Clean command
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    
    if not args.command:
        print("[GOVERNOR] Error: No command provided.")
        sys.exit(1)

    runner = GovernedTaskRunner(args)
    runner.run()

if __name__ == "__main__":
    main()
