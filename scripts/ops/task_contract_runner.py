#!/usr/bin/env python3
"""
VÉLØ Task Contract Runner
==========================
Enforces mission scope by validating changes against a machine-readable contract.
Prevents out-of-scope edits and accidental production mutations.

Usage:
    python scripts/ops/task_contract_runner.py --contract contract.json --mode preflight
    python scripts/ops/task_contract_runner.py --contract contract.json --mode audit --base-ref HEAD~1
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
ROOT = Path(os.environ.get("VELO_TASK_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT))

# Mandatory States
TASK_CONTRACT_OK = "TASK_CONTRACT_OK"
TASK_CONTRACT_MISSING = "TASK_CONTRACT_MISSING"
TASK_CONTRACT_INVALID_JSON = "TASK_CONTRACT_INVALID_JSON"
TASK_CONTRACT_FORBIDDEN_PATH_TOUCHED = "TASK_CONTRACT_FORBIDDEN_PATH_TOUCHED"
TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED = "TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED"
TASK_CONTRACT_FORBIDDEN_KEYWORD_FOUND = "TASK_CONTRACT_FORBIDDEN_KEYWORD_FOUND"
TASK_CONTRACT_CLASSIFICATION_MISSING = "TASK_CONTRACT_CLASSIFICATION_MISSING"
TASK_CONTRACT_FAILED = "TASK_CONTRACT_FAILED"

def _run_git(args: List[str], cwd: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git"] + args, cwd=cwd, stderr=subprocess.STDOUT, text=True
        ).strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: {e.output}")
    except Exception as e:
        raise RuntimeError(f"Failed to run git: {str(e)}")

def load_contract(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Contract missing at: {path}")
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid contract JSON: {str(e)}")

def validate_contract_schema(contract: dict):
    required = ["task_id", "allowed_paths", "forbidden_paths", "forbidden_keywords", "classification_required"]
    for field in required:
        if field not in contract:
            raise ValueError(f"Contract missing required field: {field}")
        if field != "task_id" and not isinstance(contract[field], list):
            raise ValueError(f"Contract field {field} must be a list")

def check_paths(changed_files: List[str], allowed: List[str], forbidden: List[str]) -> Tuple[List[str], List[str]]:
    forbidden_hits = []
    out_of_scope = []
    
    for f in changed_files:
        # Check forbidden
        is_forbidden = False
        for p in forbidden:
            if f.startswith(p) or p in f:
                forbidden_hits.append(f)
                is_forbidden = True
                break
        
        if is_forbidden:
            continue
            
        # Check allowed
        is_allowed = False
        for p in allowed:
            if f == p or f.startswith(p):
                is_allowed = True
                break
        
        if not is_allowed:
            out_of_scope.append(f)
            
    return forbidden_hits, out_of_scope

def check_keywords(diff_text: str, forbidden_keywords: List[str]) -> List[str]:
    hits = []
    for kw in forbidden_keywords:
        if kw in diff_text:
            hits.append(kw)
    return hits

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Task Contract Runner")
    parser.add_argument("--contract", required=True, help="Path to task contract JSON")
    parser.add_argument("--mode", choices=["preflight", "audit"], default="audit")
    parser.add_argument("--base-ref", help="Git ref to compare against (e.g. HEAD~1 or hash)")
    parser.add_argument("--classification-file", help="Path to final classification report/text")
    parser.add_argument("--output", default="data/current/task_contract_latest.json", help="Path to write JSON artifact")
    
    args = parser.parse_args()
    
    contract_path = Path(args.contract)
    if not contract_path.is_absolute():
        contract_path = ROOT / contract_path
        
    status = "UNKNOWN"
    state = TASK_CONTRACT_FAILED
    errors = []
    payload = {}
    
    # Init Payload
    payload = {
        "task_id": "UNKNOWN",
        "contract_path": str(args.contract),
        "base_ref": args.base_ref,
        "changed_files": [],
        "forbidden_path_hits": [],
        "out_of_scope_hits": [],
        "forbidden_keyword_hits": [],
        "classification_required": [],
        "classification_missing": [],
        "errors": [],
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    try:
        # 1. Load Contract
        try:
            contract = load_contract(contract_path)
            validate_contract_schema(contract)
            payload["task_id"] = contract["task_id"]
            payload["classification_required"] = contract["classification_required"]
        except FileNotFoundError as e:
            payload["status"] = "FAIL"
            payload["state"] = TASK_CONTRACT_MISSING
            payload["errors"].append(str(e))
            return _finish(payload, args.output)
        except ValueError as e:
            payload["status"] = "FAIL"
            payload["state"] = TASK_CONTRACT_INVALID_JSON
            payload["errors"].append(str(e))
            return _finish(payload, args.output)

        if args.mode == "preflight":
            payload["status"] = "PASS"
            payload["state"] = TASK_CONTRACT_OK
            return _finish(payload, args.output)

        # 2. Audit Mode - Check Git
        try:
            if args.base_ref:
                changed = _run_git(["diff", "--name-only", args.base_ref])
                diff_text = _run_git(["diff", args.base_ref])
            else:
                # Staged and unstaged (tracked)
                changed = _run_git(["diff", "HEAD", "--name-only"])
                diff_text = _run_git(["diff", "HEAD"])
                
                # Untracked files
                untracked = _run_git(["ls-files", "--others", "--exclude-standard"])
                if untracked:
                    changed_list = changed.splitlines() if changed else []
                    changed_list.extend(untracked.splitlines())
                    changed = "\n".join(changed_list)
                    # For untracked files, we can append their content to diff_text to check for keywords
                    for u in untracked.splitlines():
                        u_path = ROOT / u
                        if u_path.exists() and u_path.is_file():
                            diff_text += f"\n+++ {u}\n" + u_path.read_text(errors="replace")
                
            changed_files = changed.splitlines() if changed else []
            payload["changed_files"] = changed_files
            
            # Paths
            forbidden_hits, out_of_scope = check_paths(
                changed_files, 
                contract["allowed_paths"], 
                contract["forbidden_paths"]
            )
            payload["forbidden_path_hits"] = forbidden_hits
            payload["out_of_scope_hits"] = out_of_scope
            
            # Keywords
            forbidden_keywords = contract["forbidden_keywords"]
            keyword_hits = []
            rel_contract_path = str(contract_path.relative_to(ROOT))
            
            for f in changed_files:
                # SKIP keyword check on the contract file itself to avoid self-triggering
                if f == rel_contract_path:
                    continue
                
                f_diff = ""
                try:
                    if args.base_ref:
                        f_diff = _run_git(["diff", args.base_ref, "--", f])
                    else:
                        # Check staged/unstaged
                        f_diff = _run_git(["diff", "HEAD", "--", f])
                        
                    # If diff is empty and file exists, it might be untracked
                    if not f_diff:
                        f_path = ROOT / f
                        if f_path.exists() and f_path.is_file():
                            # Check if it is untracked
                            untracked_check = _run_git(["ls-files", "--others", "--exclude-standard", f])
                            if untracked_check:
                                f_diff = f_path.read_text(errors="replace")
                except Exception:
                    pass
                
                if f_diff:
                    keyword_hits.extend(check_keywords(f_diff, forbidden_keywords))
            
            payload["forbidden_keyword_hits"] = list(set(keyword_hits))
            
        except Exception as e:
            payload["status"] = "FAIL"
            payload["state"] = TASK_CONTRACT_FAILED
            payload["errors"].append(f"Git analysis failed: {str(e)}")
            return _finish(payload, args.output)

        # 3. Check Classification
        if args.classification_file:
            cls_path = Path(args.classification_file)
            if not cls_path.is_absolute():
                cls_path = ROOT / cls_path
            
            if cls_path.exists():
                cls_text = cls_path.read_text()
                missing = [c for c in contract["classification_required"] if c not in cls_text]
                payload["classification_missing"] = missing
            else:
                payload["classification_missing"] = contract["classification_required"]
                payload["errors"].append(f"Classification file missing: {args.classification_file}")
        else:
            # If audit mode requires classification but none provided, we might fail depending on policy.
            # But the prompt says "If classification_required entries are missing... return non-PASS".
            # If no file provided, we treat all as missing.
            payload["classification_missing"] = contract["classification_required"]

        # Final Logic
        if payload["forbidden_path_hits"]:
            payload["status"] = "FAIL"
            payload["state"] = TASK_CONTRACT_FORBIDDEN_PATH_TOUCHED
        elif payload["out_of_scope_hits"]:
            payload["status"] = "FAIL"
            payload["state"] = TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED
        elif payload["forbidden_keyword_hits"]:
            payload["status"] = "FAIL"
            payload["state"] = TASK_CONTRACT_FORBIDDEN_KEYWORD_FOUND
        elif payload["classification_missing"]:
            payload["status"] = "FAIL"
            payload["state"] = TASK_CONTRACT_CLASSIFICATION_MISSING
        else:
            payload["status"] = "PASS"
            payload["state"] = TASK_CONTRACT_OK

    except Exception as e:
        payload["status"] = "FAIL"
        payload["state"] = TASK_CONTRACT_FAILED
        payload["errors"].append(str(e))

    return _finish(payload, args.output)

def _finish(payload: dict, output_rel_path: str):
    output_path = ROOT / output_rel_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    
    print(json.dumps(payload, indent=2))
    sys.exit(0 if payload.get("status") == "PASS" else 1)

if __name__ == "__main__":
    main()
