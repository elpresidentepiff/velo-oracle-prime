#!/usr/bin/env python3
"""
VÉLØ Agent Harness Controller — scripts/ops/run_agent_harness.py
================================================================
The single entry point for all governed agent task execution.

Usage:
    python scripts/ops/run_agent_harness.py \\
        --task SIGMA_CLOSE \\
        --date 2026-06-08 \\
        --source-truth RP_SCRAPER_CLEAN \\
        --sigma-complete \\
        --council-complete

    python scripts/ops/run_agent_harness.py \\
        --task COUNCIL_AUDIT \\
        --date 2026-06-08 \\
        --source-truth RP_MERGED_CLEAN \\
        --sigma-complete

    python scripts/ops/run_agent_harness.py --list-tasks

Architectural boundary:
    This script governs VELO operations only:
      - Source truth and pipeline health
      - Scoring safety
      - Learning eligibility
      - Data contamination and recovery
      - Mission Control and Council evidence

    It has NO dependency on Spotify, podcasts, media generation,
    or publishing. Those concerns belong to the Media Ops Engine.

    Trusted truth artifacts produced here may be READ by the
    Media Ops Engine, but Media Ops must never invoke, modify,
    or become part of this harness.

Deployment tiers (per VELO_AGENT_HARNESS_V1.md §6):
    SHADOW            — Observes; records violations but cannot block.
    ENFORCED_READ_ONLY — Controls audits, reports, Sigma, Council packets.
    ENFORCED_CODE      — Agents may modify approved non-live files.
    LIVE_ADJACENT      — Requires Sentinel + Council + operator approval.
    NEVER_PERMITTED    — Autonomous betting, live-learning, model self-mod.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.velo.harness.contracts import DeploymentTier
from src.velo.harness.executor import HarnessExecutor
from src.velo.harness.task_registry import TASK_REGISTRY, get_contract


def _print_banner() -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  VÉLØ AGENT HARNESS CONTROLLER                                  ║")
    print("║  VELO PROTECTION ONLY · NO MEDIA OPS · NO SPOTIFY               ║")
    print("║  Agent Harness → VELO truth artifacts → Media Ops Engine        ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()


def _list_tasks() -> None:
    print("\nRegistered tasks in TASK_REGISTRY:\n")
    for task_id, contract in sorted(TASK_REGISTRY.items()):
        print(f"  {task_id}")
        print(f"    Tier:      {contract.deployment_tier.value}")
        print(f"    Type:      {contract.task_type}")
        print(f"    Objective: {contract.objective[:80]}...")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VÉLØ Agent Harness Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        help="Task ID from TASK_REGISTRY (e.g. SIGMA_CLOSE, COUNCIL_AUDIT)",
    )
    parser.add_argument("--date", help="Race date YYYY-MM-DD")
    parser.add_argument(
        "--source-truth",
        default="SOURCE_UNKNOWN_BLOCK",
        choices=[
            "RP_SCRAPER_CLEAN",
            "RP_SCRAPER_DEGRADED",
            "RP_MERGED_CLEAN",
            "RP_MERGED_DEGRADED",
            "LOCAL_VERIFIED_ARTIFACT",
            "SOURCE_UNKNOWN_BLOCK",
        ],
        help="Source truth label for this run",
    )
    parser.add_argument(
        "--sigma-complete",
        action="store_true",
        help="Assert that Sigma close is complete for this date",
    )
    parser.add_argument(
        "--council-complete",
        action="store_true",
        help="Assert that Council audit is complete for this date",
    )
    parser.add_argument(
        "--learning-requested",
        action="store_true",
        help="Assert that learning is requested (triggers learning gate checks)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/harness_returns",
        help="Directory to write ExecutionReturn artifacts",
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="List all registered tasks and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate contract and Sentinel only; do not execute commands",
    )

    args = parser.parse_args()

    _print_banner()

    if args.list_tasks:
        _list_tasks()
        return 0

    if not args.task:
        parser.error("--task is required unless --list-tasks is specified")

    # ── Load contract ─────────────────────────────────────────────────────────
    try:
        contract = get_contract(args.task)
    except KeyError as exc:
        print(f"[HARNESS ERROR] {exc}")
        return 1

    # Substitute {date} placeholder in commands
    date_str = args.date or ""
    substituted_commands = [
        cmd.replace("{date}", date_str) for cmd in contract.allowed_commands
    ]
    # Rebuild contract with substituted commands (contracts are frozen, so we
    # create a new instance with the same fields but substituted commands)
    from dataclasses import replace as dc_replace
    contract = dc_replace(contract, allowed_commands=substituted_commands)

    print(f"[HARNESS] Task:         {contract.mission_id}")
    print(f"[HARNESS] Tier:         {contract.deployment_tier.value}")
    print(f"[HARNESS] Source truth: {args.source_truth}")
    print(f"[HARNESS] Date:         {date_str or '(not specified)'}")
    print(f"[HARNESS] Sigma:        {'COMPLETE' if args.sigma_complete else 'INCOMPLETE'}")
    print(f"[HARNESS] Council:      {'COMPLETE' if args.council_complete else 'INCOMPLETE'}")
    print(f"[HARNESS] Dry run:      {'YES' if args.dry_run else 'NO'}")
    print()

    if args.dry_run:
        # Validate contract and Sentinel only
        from src.velo.harness.sentinel import Sentinel
        sentinel = Sentinel(repo_root=str(ROOT))
        result = sentinel.evaluate(
            contract=contract,
            source_truth=args.source_truth,
            sigma_complete=args.sigma_complete,
            council_complete=args.council_complete,
            learning_requested=args.learning_requested,
        )
        print("[HARNESS DRY RUN] Sentinel evaluation:")
        print(f"  Passed:     {result.passed}")
        if result.violations:
            print("  Violations:")
            for v in result.violations:
                print(f"    - {v}")
        if result.warnings:
            print("  Warnings:")
            for w in result.warnings:
                print(f"    - {w}")
        return 0 if result.passed else 1

    # ── Execute ───────────────────────────────────────────────────────────────
    executor = HarnessExecutor(repo_root=str(ROOT))
    ret = executor.run(
        contract=contract,
        source_truth=args.source_truth,
        sigma_complete=args.sigma_complete,
        council_complete=args.council_complete,
        learning_requested=args.learning_requested,
    )

    # Write return artifact
    artifact_path = ret.write(args.output_dir)

    # Print summary
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print(f"║  VERDICT: {ret.verdict.value:<55}║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"[HARNESS] Artifact: {artifact_path}")
    print(f"[HARNESS] Git HEAD: {ret.git_head_before} → {ret.git_head_after}")

    if ret.sentinel_violations:
        print("[HARNESS] Sentinel violations:")
        for v in ret.sentinel_violations:
            print(f"  - {v}")

    if ret.safety_gates:
        print("[HARNESS] Safety gates:")
        for k, v in ret.safety_gates.items():
            print(f"  {k}: {v}")

    print()
    print("[HARNESS] CONFIRMATION: Agent Harness governs VELO only.")
    print("[HARNESS] Media Ops Engine reads final artifacts — it does not")
    print("[HARNESS] invoke, modify, or become part of this harness.")
    print()

    return 0 if ret.verdict.value in ("PASS", "PARTIAL") else 1


if __name__ == "__main__":
    raise SystemExit(main())
