#!/usr/bin/env python3
"""
Verify Hardening State
======================
Audits docs/current/VELO_HARDENING_STATE.md for required layers and commits.
Ensures the safety perimeter is documented and verifiable.

Usage:
    python scripts/ops/verify_hardening_state.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Identify ROOT
ROOT = Path(os.environ.get("VELO_HARDENING_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT))

HARDENING_LOG_PATH = ROOT / "docs/current/VELO_HARDENING_STATE.md"
OUTPUT_JSON = ROOT / "data/current/hardening_state_check_latest.json"

REQUIRED_LAYERS = [
    "CAPTURE_PROOF",
    "WORKTREE_SAFETY_RUNNER",
    "TASK_CONTRACT_RUNNER",
    "SIDE_EFFECT_SENTINEL",
    "GOVERNED_TASK_RUNNER"
]

REQUIRED_COMMITS = [
    "0737443",
    "95e698d",
    "1f109df",
    "ac8760b",
    "ed8d09d",
    "5dfd9a5"
]

def verify():
    print(f"[VERIFIER] Checking hardening log: {HARDENING_LOG_PATH.relative_to(ROOT)}")
    
    status = "UNKNOWN"
    errors = []
    missing_layers = []
    missing_commits = []
    
    if not HARDENING_LOG_PATH.exists():
        errors.append("Hardening log file missing")
        return _finish("FAIL", errors, [], [], "LOG_MISSING")

    content = HARDENING_LOG_PATH.read_text()
    upper_content = content.upper().replace("-", "_")

    # Check Layers
    for layer in REQUIRED_LAYERS:
        if layer not in upper_content:
            missing_layers.append(layer)
            
    # Check Commits
    for commit in REQUIRED_COMMITS:
        if commit not in content:
            missing_commits.append(commit)

    if missing_layers:
        errors.append(f"Missing required layers in log: {', '.join(missing_layers)}")
    if missing_commits:
        errors.append(f"Missing expected commit hashes in log: {', '.join(missing_commits)}")

    if errors:
        status = "FAIL"
        state = "HARDENING_INCOMPLETE"
    else:
        status = "PASS"
        state = "HARDENING_VERIFIED"
        print("[VERIFIER] SUCCESS: Hardening log is complete.")

    return _finish(status, errors, missing_layers, missing_commits, state)

def _finish(status: str, errors: list, missing_layers: list, missing_commits: list, state: str):
    payload = {
        "status": status,
        "state": state,
        "required_layers": REQUIRED_LAYERS,
        "missing_layers": missing_layers,
        "required_commits": REQUIRED_COMMITS,
        "missing_commits": missing_commits,
        "errors": errors,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)
        
    print(json.dumps(payload, indent=2))
    sys.exit(0 if status == "PASS" else 1)

if __name__ == "__main__":
    verify()
