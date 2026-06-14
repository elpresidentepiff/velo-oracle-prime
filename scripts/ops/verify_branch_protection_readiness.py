#!/usr/bin/env python3
"""
Verify Branch Protection Readiness
==================================
Audits the repository for branch protection readiness.
Checks for policy documentation, CI workflows, and mandatory safety classifications.

Usage:
    python scripts/ops/verify_branch_protection_readiness.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Identify ROOT
ROOT = Path(os.environ.get("VELO_BRANCH_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT))

POLICY_DOC = ROOT / "docs/current/BRANCH_PROTECTION_POLICY.md"
HARDENING_LOG = ROOT / "docs/current/VELO_HARDENING_STATE.md"
CI_WORKFLOW = ROOT / ".github/workflows/governed-safety.yml"
OUTPUT_JSON = ROOT / "data/current/branch_protection_readiness_latest.json"

REQUIRED_CLASSIFICATIONS = [
    "NO_LIVE_SCORING_CHANGE",
    "NO_SUPABASE_WRITES",
    "NO_MODEL_PROMOTION",
    "NO_TELEGRAM_SEND"
]

def verify():
    print(f"[VERIFIER] Checking branch protection readiness...")
    
    status = "PASS"
    state = "READY"
    errors = []
    
    # 1. Check CI Workflow
    if not CI_WORKFLOW.exists():
        errors.append(f"CI workflow missing: {CI_WORKFLOW.relative_to(ROOT)}")
        status = "FAIL"
        state = "NOT_READY"
    
    # 2. Check Hardening Log
    if not HARDENING_LOG.exists():
        errors.append(f"Hardening log missing: {HARDENING_LOG.relative_to(ROOT)}")
        status = "FAIL"
        state = "NOT_READY"

    # 3. Check Policy Doc
    if not POLICY_DOC.exists():
        errors.append(f"Policy doc missing: {POLICY_DOC.relative_to(ROOT)}")
        status = "FAIL"
        state = "NOT_READY"
    else:
        content = POLICY_DOC.read_text()
        if "governed-safety" not in content:
            errors.append("governed-safety check not listed as required in policy")
            status = "FAIL"
            state = "INCOMPLETE_POLICY"
        
        for cls in REQUIRED_CLASSIFICATIONS:
            if cls not in content:
                errors.append(f"Mandatory classification {cls} missing from policy")
                status = "FAIL"
                state = "INCOMPLETE_POLICY"

    payload = {
        "status": status,
        "state": state,
        "ci_workflow_exists": CI_WORKFLOW.exists(),
        "hardening_log_exists": HARDENING_LOG.exists(),
        "policy_doc_exists": POLICY_DOC.exists(),
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
