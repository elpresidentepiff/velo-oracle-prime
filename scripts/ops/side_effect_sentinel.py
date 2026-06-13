#!/usr/bin/env python3
"""
VÉLØ Side-Effect Sentinel
==========================
Enforces production side-effect safety by auditing and blocking risky commands.
Bridges the gap between mission classification and real ops enforcement.

Usage:
    python scripts/ops/side_effect_sentinel.py --mode audit -- pytest tests/test_task_contract_runner.py
    python scripts/ops/side_effect_sentinel.py --mode run -- pytest tests/test_task_contract_runner.py
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
ROOT = Path(os.environ.get("VELO_SENTINEL_ROOT", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT))

# Mandatory States
SIDE_EFFECT_SAFE = "SIDE_EFFECT_SAFE"
SIDE_EFFECT_FORBIDDEN_COMMAND = "SIDE_EFFECT_FORBIDDEN_COMMAND"
SIDE_EFFECT_FORBIDDEN_ENV = "SIDE_EFFECT_FORBIDDEN_ENV"
SIDE_EFFECT_SUPABASE_WRITE_RISK = "SIDE_EFFECT_SUPABASE_WRITE_RISK"
SIDE_EFFECT_TELEGRAM_SEND_RISK = "SIDE_EFFECT_TELEGRAM_SEND_RISK"
SIDE_EFFECT_MODEL_PROMOTION_RISK = "SIDE_EFFECT_MODEL_PROMOTION_RISK"
SIDE_EFFECT_LIVE_SCORING_RISK = "SIDE_EFFECT_LIVE_SCORING_RISK"
SIDE_EFFECT_COMMAND_BLOCKED = "SIDE_EFFECT_COMMAND_BLOCKED"
SIDE_EFFECT_COMMAND_OK = "SIDE_EFFECT_COMMAND_OK"
SIDE_EFFECT_COMMAND_FAILED = "SIDE_EFFECT_COMMAND_FAILED"

# Risk Patterns
SUPABASE_PATTERNS = [
    "supabase insert", "supabase update", "supabase upsert", 
    "rpc write", "db write", "persist", "write_verdict", "insert_verdict"
]
TELEGRAM_PATTERNS = [
    "telegram send", "send_telegram", "bot.send_message", "TELEGRAM_SEND"
]
MODEL_PATTERNS = [
    "promote_model", "model_promotion", "production_model", "registry promote"
]
SCORING_PATTERNS = [
    "live_scoring", "run_engine_full", "score_race", "score_race_velo_prime", "prediction write"
]

ENV_ALLOW_FLAGS = [
    "VELO_ALLOW_SUPABASE_WRITES",
    "VELO_ALLOW_TELEGRAM_SEND",
    "VELO_ALLOW_MODEL_PROMOTION",
    "VELO_ALLOW_LIVE_SCORING"
]

REQUIRED_CLASSIFICATIONS = [
    "NO_LIVE_SCORING_CHANGE",
    "NO_SUPABASE_WRITES",
    "NO_MODEL_PROMOTION",
    "NO_TELEGRAM_SEND"
]

def check_risky_command(cmd_str: str) -> Tuple[Optional[str], List[str]]:
    risk_hits = []
    
    for p in SUPABASE_PATTERNS:
        if p in cmd_str:
            risk_hits.append(f"SUPABASE:{p}")
            
    for p in TELEGRAM_PATTERNS:
        if p in cmd_str:
            risk_hits.append(f"TELEGRAM:{p}")
            
    for p in MODEL_PATTERNS:
        if p in cmd_str:
            risk_hits.append(f"MODEL:{p}")
            
    for p in SCORING_PATTERNS:
        if p in cmd_str:
            risk_hits.append(f"SCORING:{p}")
            
    if not risk_hits:
        return None, []
        
    # Pick a state based on first hit category
    first = risk_hits[0]
    if first.startswith("SUPABASE"): return SIDE_EFFECT_SUPABASE_WRITE_RISK, risk_hits
    if first.startswith("TELEGRAM"): return SIDE_EFFECT_TELEGRAM_SEND_RISK, risk_hits
    if first.startswith("MODEL"): return SIDE_EFFECT_MODEL_PROMOTION_RISK, risk_hits
    if first.startswith("SCORING"): return SIDE_EFFECT_LIVE_SCORING_RISK, risk_hits
    
    return SIDE_EFFECT_FORBIDDEN_COMMAND, risk_hits

def check_risky_env() -> List[str]:
    hits = []
    for flag in ENV_ALLOW_FLAGS:
        val = os.environ.get(flag, "").lower()
        if val in ["true", "1", "yes"]:
            hits.append(flag)
    return hits

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Side-Effect Sentinel")
    parser.add_argument("--mode", choices=["audit", "run"], default="audit")
    parser.add_argument("--classification-file", help="Path to classification report to verify")
    parser.add_argument("--output", default="data/current/side_effect_sentinel_latest.json", help="Path to write JSON artifact")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run/audit (use -- to separate)")
    
    args = parser.parse_args()
    
    # Clean command
    cmd_to_run = args.command
    if cmd_to_run and cmd_to_run[0] == "--":
        cmd_to_run = cmd_to_run[1:]
    
    cmd_str = " ".join(cmd_to_run) if cmd_to_run else ""
    
    status = "UNKNOWN"
    state = SIDE_EFFECT_SAFE
    risk_hits = []
    env_hits = []
    classification_missing = []
    errors = []
    command_executed = False
    command_exit_code = None

    # 1. Check Command
    state_from_cmd, risk_hits = check_risky_command(cmd_str)
    if state_from_cmd:
        state = state_from_cmd
        status = "FAIL"

    # 2. Check Env
    env_hits = check_risky_env()
    if env_hits:
        # If risky command AND risky env, command risk usually wins as primary state, but we log both.
        # But if command was safe but env was risky, change state to FORBIDDEN_ENV.
        if state == SIDE_EFFECT_SAFE:
            state = SIDE_EFFECT_FORBIDDEN_ENV
            status = "FAIL"

    # 3. Check Classification
    if args.classification_file:
        cls_path = Path(args.classification_file)
        if not cls_path.is_absolute():
            cls_path = ROOT / cls_path
        
        if cls_path.exists():
            cls_text = cls_path.read_text()
            classification_missing = [c for c in REQUIRED_CLASSIFICATIONS if c not in cls_text]
            if classification_missing and status != "FAIL":
                status = "FAIL"
                # Keep existing risk state if present, otherwise set to failed.
                # Actually, missing classification is its own fail mode.
        else:
            errors.append(f"Classification file missing: {args.classification_file}")
            classification_missing = REQUIRED_CLASSIFICATIONS
            status = "FAIL"
    
    # 4. Final Safety Determination
    is_safe = (status != "FAIL" and not errors and not classification_missing)
    if is_safe:
        status = "PASS"
        state = SIDE_EFFECT_SAFE
    else:
        status = "FAIL"

    # 5. Execution
    if args.mode == "run":
        if is_safe:
            if not cmd_to_run:
                errors.append("No command provided for run mode")
                status = "FAIL"
                state = SIDE_EFFECT_COMMAND_FAILED
            else:
                try:
                    print(f"[SENTINEL] Running: {cmd_str}")
                    # Inherit environment but ensure sentinel root is set
                    run_env = os.environ.copy()
                    run_env["VELO_SENTINEL_ROOT"] = str(ROOT)
                    
                    result = subprocess.run(cmd_to_run, cwd=ROOT, env=run_env)
                    command_executed = True
                    command_exit_code = result.returncode
                    if command_exit_code == 0:
                        state = SIDE_EFFECT_COMMAND_OK
                        status = "PASS"
                    else:
                        state = SIDE_EFFECT_COMMAND_FAILED
                        status = "FAIL"
                except Exception as e:
                    status = "FAIL"
                    state = SIDE_EFFECT_COMMAND_FAILED
                    errors.append(f"Execution failed: {str(e)}")
        else:
            state = SIDE_EFFECT_COMMAND_BLOCKED
            print(f"[SENTINEL] BLOCKED: {state}")
    
    # Payload
    payload = {
        "status": status,
        "state": state,
        "mode": args.mode,
        "command_requested": cmd_str if cmd_str else None,
        "command_executed": command_executed,
        "command_exit_code": command_exit_code,
        "risk_hits": risk_hits,
        "env_hits": env_hits,
        "classification_missing": classification_missing,
        "errors": errors,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }

    # Write
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(json.dumps(payload, indent=2))
    sys.exit(0 if status == "PASS" else 1)

if __name__ == "__main__":
    main()
