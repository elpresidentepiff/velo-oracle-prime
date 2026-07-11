"""
VÉLØ Daily Harness
==================

Single orchestration script that runs the full daily intelligence pipeline
in the correct order. Read-only for scoring — does NOT change any verdict,
model, router, or SQPE. Orchestrates existing scripts only.

Usage:
    python scripts/velo_daily_harness.py --date 2026-05-02 --mode morning
    python scripts/velo_daily_harness.py --date 2026-05-02 --mode close
    python scripts/velo_daily_harness.py --date 2026-05-02 --mode full

Modes:
    morning   — pre-race: sidecar stack + signal cards + operator summary
    close     — post-race: sigma + execution bridge + innovation protocol + tracker
    full      — morning + close (if results available)

Hard rules:
    NO scoring changes
    NO model changes
    NO SQPE changes
    NO router changes
    NO staking
    NO live execution
    OPERATOR VISIBILITY ONLY
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"

STEP_TIMEOUT = 180  # 3 minutes per step

DISCLAIMER = (
    "OPERATOR VISIBILITY ONLY — Harness output is intelligence and audit information only. "
    "No scoring, model, SQPE, or router changes. No staking. No live execution."
)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _run_step(
    label: str,
    step_n: int,
    total_steps: int,
    cmd: list[str],
    allow_fail: bool = True,
) -> tuple[bool, str]:
    """
    Run a subprocess step. Returns (success, output_snippet).
    Failures are caught and logged — harness does not abort.
    """
    prefix = f"[STEP {step_n}/{total_steps}]"
    print(f"{prefix} {label}...", flush=True)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=STEP_TIMEOUT,
            cwd=str(ROOT),
        )
        if result.returncode == 0:
            snippet = (result.stdout or "").strip().split("\n")[-1][:120]
            print(f"{prefix} {label}... OK  ({snippet})")
            return True, result.stdout
        else:
            err = (result.stderr or result.stdout or "").strip().split("\n")[0][:120]
            print(f"{prefix} {label}... FAILED: {err}")
            return False, result.stderr or result.stdout
    except subprocess.TimeoutExpired:
        print(f"{prefix} {label}... FAILED: timeout after {STEP_TIMEOUT}s")
        return False, "TIMEOUT"
    except Exception as exc:
        print(f"{prefix} {label}... FAILED: {exc}")
        return False, str(exc)


def _python(script_rel: str, extra_args: list[str] | None = None) -> list[str]:
    """Build a PYTHONPATH-safe python command for a script."""
    cmd = [sys.executable, str(SCRIPTS / script_rel)]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def _check_verdicts(date_str: str) -> tuple[bool, int]:
    """
    Check if velo_verdicts has rows for date_str.
    Tries Supabase REST API using env vars. Returns (has_verdicts, count).
    """
    import os
    import urllib.request

    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not sb_url or not sb_key:
        # Cannot check — assume verdicts may exist
        return True, -1

    try:
        url = (
            f"{sb_url}/rest/v1/velo_verdicts"
            f"?generated_at=gte.{date_str}T00:00:00"
            f"&generated_at=lt.{date_str}T23:59:59"
            f"&select=race_id"
            f"&limit=1"
        )
        req = urllib.request.Request(url, method="GET")
        req.add_header("apikey", sb_key)
        req.add_header("Authorization", f"Bearer {sb_key}")
        req.add_header("Accept", "application/json")
        req.add_header("Prefer", "count=exact")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            count = len(data) if isinstance(data, list) else 0
            return count > 0, count
    except Exception:
        return True, -1  # assume OK on failure


def _check_results(date_str: str) -> bool:
    """Check if the canonical RP results file exists for the given date.

    Fixed 2026-07-11 (ROLE-EVAL-01): the previous candidate paths
    (data/results_{date}.json, data/racing_api_results_{date}.json) never
    matched anything -- parse_rp_results_capture.py always writes to
    data/results/rp_results_{date_tag}.json. This check silently reported
    "no results" every day regardless of whether results actually existed,
    and the racing_api_results_ path referenced a source that must never be
    live per THE_ONE_TRUTH.md (Racing API is permanently decommissioned).
    """
    return (DATA / "results" / f"rp_results_{date_str.replace('-', '_')}.json").exists()


def _load_sidecar(date_str: str) -> dict | None:
    """Load sidecar_stack_operator_card for date."""
    path = DATA / f"sidecar_stack_operator_card_{date_str.replace('-', '_')}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Try dashboard latest
    latest = ROOT / "app" / "static" / "dashboard" / "sidecar_stack_latest.json"
    if latest.exists():
        try:
            d = json.loads(latest.read_text(encoding="utf-8"))
            if d.get("date") == date_str:
                return d
        except Exception:
            pass
    return None


def _print_operator_summary(date_str: str, sidecar: dict | None) -> dict:
    """Print and return the operator summary for morning mode."""
    summary: dict = {"date": date_str, "mode": "morning"}

    print()
    print("=" * 64)
    print(f"  VÉLØ OPERATOR SUMMARY — {date_str}")
    print("  STATUS: OPERATOR_VISIBILITY_ONLY · NO STAKING")
    print("=" * 64)

    if not sidecar:
        print("  SIDECAR DATA: not available for this date")
        summary["sidecar_available"] = False
        return summary

    c = sidecar.get("counts", {})
    stacks = sidecar.get("stacks", {})
    total   = c.get("total_races", 0)
    vp30    = c.get("vp30_count", 0)
    elite   = c.get("elite_stack_count", 0)
    strong  = c.get("strong_stack_count", 0)
    splus   = c.get("strong_stack_plus_count", 0)
    improve = c.get("vp30_improve_count", 0)
    base    = c.get("vp30_base_count", 0)
    suppress = c.get("suppress_count", 0)

    print(f"  Total races scored:     {total}")
    print(f"  VP30 selections:        {vp30}  (VP≥0.40: {sum(1 for s in stacks.values() for r in s if (r.get('velo_prime_prob') or 0) >= 0.40)})")
    print(f"  Tier distribution:     ", end="")
    all_runners = [r for s in stacks.values() for r in s]
    from collections import Counter
    tiers = Counter(r.get("tier", "?") for r in all_runners)
    print("  ".join(f"{t}:{n}" for t, n in sorted(tiers.items())))
    print()
    print(f"  Stack breakdown:")
    print(f"    ELITE_STACK:          {elite}  (Tier A + VP30 + MDS>0.50  — SR baseline 40.1%)")
    print(f"    STRONG_STACK_PLUS:    {splus}")
    print(f"    STRONG_STACK:         {strong}  (VP30 + MDS>0.50 — SR baseline 54.8%)")
    print(f"    VP30_IMPROVE:         {improve} (VP30 + IMP>0.40 — SR baseline 43.5%)")
    print(f"    VP30_BASE:            {base}")
    print(f"    SUPPRESS:             {suppress}  [DRAG — DO NOT RESCUE]")

    # MDS > 0.50 alerts — deduplicate by race_id
    _mds_seen = set()
    mds_high = []
    for s in stacks.values():
        for r in s:
            if (r.get("market_deception_score") or 0) > 0.50 and r.get("race_id") not in _mds_seen:
                _mds_seen.add(r.get("race_id"))
                mds_high.append(r)
    print()
    if mds_high:
        print(f"  ⚡ MDS>0.50 ALERTS ({len(mds_high)}) — HIGHEST LIFT SIGNAL (baseline SR 54.8%):")
        for r in mds_high[:5]:
            print(f"     {r.get('off_time','—'):6s} {r.get('course','—'):15s} {r.get('horse','—'):25s} MDS={r.get('market_deception_score',0):.3f} VP={r.get('velo_prime_prob',0):.3f} T={r.get('tier','?')}")
    else:
        print("  ⚡ MDS>0.50 ALERTS: none today")

    # IMP > 0.40 alerts — deduplicate by race_id
    _imp_seen = set()
    imp_high = []
    for s in stacks.values():
        for r in s:
            if (r.get("improvement_score") or 0) > 0.40 and r.get("race_id") not in _imp_seen:
                _imp_seen.add(r.get("race_id"))
                imp_high.append(r)
    if imp_high:
        print()
        print(f"  📈 IMP>0.40 ALERTS ({len(imp_high)}) — baseline SR 43.5%:")
        for r in imp_high[:5]:
            print(f"     {r.get('off_time','—'):6s} {r.get('course','—'):15s} {r.get('horse','—'):25s} IMP={r.get('improvement_score',0):.3f} VP={r.get('velo_prime_prob',0):.3f}")

    # Elite + Strong first rows
    print()
    print("  TOP SIGNALS (ELITE + STRONG):")
    for stack_name in ["ELITE_STACK", "STRONG_STACK_PLUS", "STRONG_STACK"]:
        for r in (stacks.get(stack_name) or [])[:2]:
            badges = " ".join(r.get("stack_badges") or [])
            print(f"    [{stack_name}] {r.get('off_time','—'):6s} {r.get('course','—'):15s} {r.get('horse','—'):25s} VP={r.get('velo_prime_prob',0):.3f} [{badges}]")

    print()
    print("  LEARNING LOOP STATUS:")
    print("    HFS:         HFS_TRAINING_BLOCKED (35.3% signal-dark)")
    print("    Playbook G:  BLOCKED")
    print("    MPI/CB fix:  APPLIED (hfs_signal_contract_v1)")
    print("    Corpus:      794 rows")
    print()
    print(f"  {DISCLAIMER}")
    print("=" * 64)

    summary["sidecar_available"] = True
    summary["counts"] = c
    summary["mds_high_count"] = len(mds_high)
    summary["imp_high_count"] = len(imp_high)
    return summary


def _print_close_summary(date_str: str, step_results: list[tuple[str, bool, str]]) -> dict:
    """Print and return close mode summary."""
    summary: dict = {"date": date_str, "mode": "close", "steps": {}}
    print()
    print("=" * 64)
    print(f"  VÉLØ CLOSE SUMMARY — {date_str}")
    print("  STATUS: OPERATOR_VISIBILITY_ONLY · PAPER ONLY")
    print("=" * 64)
    for label, ok, output in step_results:
        status = "OK" if ok else "FAILED"
        summary["steps"][label] = status
        print(f"  {label:<40} {status}")
    print()
    print(f"  {DISCLAIMER}")
    print("=" * 64)
    return summary


def run_morning(date_str: str) -> dict:
    """Run pre-race morning mode."""
    print(f"\n[HARNESS] MORNING MODE — {date_str} — {_ts()}")

    # Step 0: check verdicts exist
    has_verdicts, count = _check_verdicts(date_str)
    total_steps = 5
    step = 0

    if not has_verdicts:
        print(f"\nFAIL: No verdicts found for {date_str}.")
        print("      Run run_prime_today.py first, then re-run this harness.")
        return {"status": "NO_VERDICTS", "date": date_str}

    if count > 0:
        print(f"[CHECK] Verdicts found for {date_str}: {count} race(s) scored.")
    else:
        print(f"[CHECK] Verdicts check passed (count unknown — Supabase query skipped).")

    step_results = []

    # Step 1: sidecar stack operator card
    step += 1
    ok, out = _run_step(
        "sidecar_stack_operator_card",
        step, total_steps,
        _python("sidecar_stack_operator_card.py", ["--date", date_str]),
    )
    step_results.append(("sidecar_stack_operator_card", ok, out))

    # Step 2: place signal operator card (if script exists)
    step += 1
    pso = SCRIPTS / "place_signal_operator_card.py"
    if pso.exists():
        ok2, out2 = _run_step(
            "place_signal_operator_card",
            step, total_steps,
            _python("place_signal_operator_card.py", ["--date", date_str]),
        )
        step_results.append(("place_signal_operator_card", ok2, out2))
    else:
        print(f"[STEP {step}/{total_steps}] place_signal_operator_card... SKIP (script not found)")
        step_results.append(("place_signal_operator_card", None, "NOT_FOUND"))

    # Step 3: Old VELO three-option card (WIN / PLACE / LONGSHOT)
    step += 1
    ok_3opt, out_3opt = _run_step(
        "build_old_velo_three_option_card",
        step, total_steps,
        _python("ops/build_old_velo_three_option_card.py", ["--date", date_str]),
    )
    step_results.append(("build_old_velo_three_option_card", ok_3opt, out_3opt))

    # Step 4: cashrun detector (only if racecard merged files exist)
    step += 1
    cashrun_input = DATA / f"cashrun_report_{date_str}.csv"
    cashrun_script = SCRIPTS / "cashrun_detector.py"
    if cashrun_script.exists():
        ok3, out3 = _run_step(
            "cashrun_detector",
            step, total_steps,
            _python("cashrun_detector.py", ["--date", date_str]),
        )
        step_results.append(("cashrun_detector", ok3, out3))
    else:
        print(f"[STEP {step}/{total_steps}] cashrun_detector... SKIP (script not found)")
        step_results.append(("cashrun_detector", None, "NOT_FOUND"))

    # Step 4: load sidecar and print operator summary
    step += 1
    print(f"[STEP {step}/{total_steps}] operator_summary...", end="", flush=True)
    sidecar = _load_sidecar(date_str)
    if sidecar:
        print(" OK")
    else:
        print(" WARN (sidecar data not found — run sidecar_stack_operator_card.py first)")

    summary = _print_operator_summary(date_str, sidecar)
    summary["step_results"] = {s: ("OK" if o else "FAILED" if o is False else "SKIP") for s, o, _ in step_results}

    # Write daily intelligence JSON
    out_path = DATA / f"velo_daily_intelligence_{date_str}.json"
    DATA.mkdir(exist_ok=True)
    out_path.write_text(json.dumps({
        **summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OPERATOR_VISIBILITY_ONLY",
        "disclaimer": DISCLAIMER,
    }, indent=2, default=str), encoding="utf-8")
    print(f"\n[HARNESS] Intelligence file: {out_path}")

    return summary


def run_close(date_str: str) -> dict:
    """Run post-race close mode."""
    print(f"\n[HARNESS] CLOSE MODE — {date_str} — {_ts()}")

    total_steps = 7
    step = 0
    step_results = []

    # Step 1: check results exist
    has_results = _check_results(date_str)
    step += 1
    if not has_results:
        print(f"[STEP {step}/{total_steps}] results_check... WARN: No results file found for {date_str}.")
        print("      Expected: data/results_{YYYYMMDD}.json or data/results_{date}.json")
        print("      Sigma run will attempt but may fail.")
    else:
        print(f"[STEP {step}/{total_steps}] results_check... OK (results file found)")
    step_results.append(("results_check", has_results, ""))

    # Step 2: sigma
    step += 1
    ok2, out2 = _run_step(
        "run_results_sigma",
        step, total_steps,
        _python("run_results_sigma.py", ["--date", date_str]),
    )
    step_results.append(("run_results_sigma", ok2, out2))

    # Step 2b: Old VELO role evaluation (WIN/PLACE/LONGSHOT vs results)
    # ROLE-EVAL-01 (2026-07-11): previously re-ran build_old_velo_three_option_card.py
    # here, which only ever rebuilds pre-race selections from runner snapshots and
    # never evaluates them against results -- role_metrics stayed zero regardless of
    # whether results existed. The morning card is now frozen (see that script's
    # --force-rebuild guard) and evaluated here instead, read-only, with a strict
    # join so an unresolved/ambiguous race blocks rather than silently passing.
    step += 1
    ok_3opt, out_3opt = _run_step(
        "evaluate_old_velo_three_option_card",
        step, total_steps,
        _python("ops/evaluate_old_velo_three_option_card.py", ["--date", date_str, "--strict"]),
    )
    step_results.append(("evaluate_old_velo_three_option_card", ok_3opt, out_3opt))

    # Step 3: execution bridge close
    step += 1
    ok3, out3 = _run_step(
        "run_execution_bridge_shadow",
        step, total_steps,
        _python("run_execution_bridge_shadow.py", ["--date", date_str, "--mode", "SIM", "--audit-results"]),
    )
    step_results.append(("run_execution_bridge_shadow", ok3, out3))

    # Step 4: innovation protocol
    step += 1
    ok4, out4 = _run_step(
        "build_innovation_protocol",
        step, total_steps,
        _python("build_innovation_protocol.py", ["--date", date_str]),
    )
    step_results.append(("build_innovation_protocol", ok4, out4))

    # Step 5: router shadow audit
    step += 1
    prev_csv = DATA / "router_shadow_audit_latest.csv"
    audit_args = []
    if prev_csv.exists():
        audit_args = ["--prev-csv", str(prev_csv)]
    ok5, out5 = _run_step(
        "router_shadow_audit",
        step, total_steps,
        _python("router_shadow_audit.py", audit_args or None),
    )
    step_results.append(("router_shadow_audit", ok5, out5))

    # Step 6: signal tracker
    step += 1
    tracker_script = SCRIPTS / "velo_signal_tracker.py"
    if tracker_script.exists():
        ok6, out6 = _run_step(
            "velo_signal_tracker",
            step, total_steps,
            _python("velo_signal_tracker.py", ["--date", date_str]),
        )
        step_results.append(("velo_signal_tracker", ok6, out6))
    else:
        print(f"[STEP {step}/{total_steps}] velo_signal_tracker... SKIP (not yet built)")
        step_results.append(("velo_signal_tracker", None, "NOT_FOUND"))

    return _print_close_summary(date_str, step_results)


def run_full(date_str: str) -> dict:
    """Run morning + close (if results available)."""
    print(f"\n[HARNESS] FULL MODE — {date_str}")
    morning_result = run_morning(date_str)
    has_results = _check_results(date_str)
    if not has_results:
        print(f"\n[HARNESS] Close mode skipped — no results file found for {date_str}.")
        print("          Run again with --mode close after results are available.")
        return {**morning_result, "close_skipped": True, "reason": "no_results_file"}
    close_result = run_close(date_str)
    return {**morning_result, **close_result, "mode": "full"}


def main() -> None:
    parser = argparse.ArgumentParser(description="VÉLØ Daily Intelligence Harness")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD race date")
    parser.add_argument(
        "--mode",
        choices=["morning", "close", "full"],
        default="morning",
        help="morning=pre-race, close=post-race, full=both",
    )
    args = parser.parse_args()

    date_str = args.date
    mode = args.mode

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  VÉLØ DAILY INTELLIGENCE HARNESS                            ║")
    print("║  OPERATOR VISIBILITY ONLY · NO STAKING · NO EXECUTION       ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    if mode == "morning":
        run_morning(date_str)
    elif mode == "close":
        run_close(date_str)
    elif mode == "full":
        run_full(date_str)

    print(f"\n[HARNESS] Done — {_ts()}")
    print("CONFIRMATION: No scoring/model/SQPE/router/staking/live execution changed.")


if __name__ == "__main__":
    main()
