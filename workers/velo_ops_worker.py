"""
VÉLØ Ops Worker V2
Deterministic daily orchestrator. Dry-run by default.

Phase 2: live subprocess wrappers for predict and sigma.
         learn-shadow stays contract-only (Phase 3).

Usage:
    python workers/velo_ops_worker.py <command> --date YYYY-MM-DD [--execute] [--allow-network]

Commands:
    ingest            Fetch racecards and API data
    predict           Run VÉLØ predictions for all races
    snapshot-market   Capture pre-race market state
    sigma             Pull results and reconcile with predictions
    learn-shadow      Build and consume learning events into shadow state
    healthcheck       Report system status for the day
    full-day          Run ingest → predict → sigma → healthcheck (--execute skips learn-shadow)

Safety guards:
    --dry-run         Default True. No external side effects.
    --execute         Required to trigger real execution (overrides dry-run).
    --allow-network   Required for any network / API / DB call.
    Sentient state:   NEVER touched.
    Playbook G:       NEVER promoted.
    Migrations:       NEVER applied by this worker.
    learn-shadow:     Always dry-run / contract only until Phase 3.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env before any service imports so Supabase keys are available
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from app.services.ops_service import OpsService
from app.services.learning_engine import LearningEngine

ARTIFACT_DIR = ROOT / "data" / "ops_worker_dry_run"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def _write_artifact(job_type: str, date: str, payload: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    path = ARTIFACT_DIR / f"{date}_{job_type}_{ts}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[ARTIFACT] {path}")
    return path


def _is_dry_run(args: argparse.Namespace) -> bool:
    return not args.execute


def _subprocess_env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return env


def _run_script(script_path: Path, extra_args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(script_path)] + extra_args
    print(f"[EXEC] {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=_subprocess_env(),
        timeout=timeout,
    )


# ── Command implementations ────────────────────────────────────────────────────


def cmd_ingest(args: argparse.Namespace) -> None:
    dry = _is_dry_run(args)
    print(f"--- INGEST --- date={args.date} dry_run={dry} network={args.allow_network}")
    if not dry and not args.allow_network:
        print("[BLOCKED] --allow-network required for live ingest. Aborting.")
        sys.exit(1)
    ops = OpsService(dry_run=dry, execute=args.execute)
    job_id = ops.start_job(args.date, "ingest")
    _write_artifact("ingest", args.date, {
        "job_type": "ingest",
        "date": args.date,
        "dry_run": dry,
        "allow_network": args.allow_network,
        "intended_action": "Fetch racecards and runner data from Racing API",
        "calls_run_prime_today": False,
        "status": "DRY_RUN_CONTRACT_ONLY" if dry else "PENDING_PHASE3",
    })
    ops.finish_job(job_id, "SUCCESS", metrics={"races_discovered": 0})


def cmd_predict(args: argparse.Namespace) -> None:
    dry = _is_dry_run(args)
    print(f"--- PREDICT --- date={args.date} dry_run={dry}")
    ops = OpsService(dry_run=dry, execute=args.execute)
    job_id = ops.start_job(args.date, "predict")

    if dry:
        _write_artifact("predict", args.date, {
            "job_type": "predict",
            "date": args.date,
            "dry_run": True,
            "intended_action": "Score all races via run_prime_today.py",
            "calls_run_prime_today": True,
            "scoring_change": False,
            "model_change": False,
            "status": "DRY_RUN_CONTRACT_ONLY",
        })
        ops.finish_job(job_id, "SUCCESS", metrics={"predictions_generated": 0})
        return

    # ── Live execution ────────────────────────────────────────────────────────
    script = ROOT / "scripts" / "run_prime_today.py"
    _timeout = int(os.environ.get("VELO_WORKER_TIMEOUT", "900"))
    try:
        proc = _run_script(script, ["--date", args.date], timeout=_timeout)
    except subprocess.TimeoutExpired as exc:
        ops.finish_failure(job_id, "SUBPROCESS_TIMEOUT", f"run_prime_today.py exceeded {exc.timeout}s timeout")
        _write_artifact("predict", args.date, {
            "job_type": "predict", "date": args.date, "dry_run": False,
            "error_type": "SUBPROCESS_TIMEOUT", "status": "FAIL",
        })
        sys.exit(1)

    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print("[STDERR]", proc.stderr[:1000], file=sys.stderr)

    if proc.returncode == 0:
        ops.finish_success(job_id, metrics={"exit_code": 0}, output_artifacts={"stdout_tail": proc.stdout[-500:]})
        _write_artifact("predict", args.date, {
            "job_type": "predict",
            "date": args.date,
            "dry_run": False,
            "exit_code": 0,
            "scoring_change": False,
            "model_change": False,
            "status": "PASS",
        })
    else:
        error_type = ops.classify_error(proc.stdout, proc.stderr, proc.returncode)
        ops.finish_failure(job_id, error_type, (proc.stderr or proc.stdout)[-1000:])
        _write_artifact("predict", args.date, {
            "job_type": "predict",
            "date": args.date,
            "dry_run": False,
            "exit_code": proc.returncode,
            "error_type": error_type,
            "status": "FAIL",
        })
        sys.exit(proc.returncode)


def cmd_snapshot_market(args: argparse.Namespace) -> None:
    dry = _is_dry_run(args)
    print(f"--- SNAPSHOT-MARKET --- date={args.date} dry_run={dry} network={args.allow_network}")
    if not dry and not args.allow_network:
        print("[BLOCKED] --allow-network required for live snapshot. Aborting.")
        sys.exit(1)
    ops = OpsService(dry_run=dry, execute=args.execute)
    job_id = ops.start_job(args.date, "snapshot-market")
    _write_artifact("snapshot-market", args.date, {
        "job_type": "snapshot-market",
        "date": args.date,
        "dry_run": dry,
        "allow_network": args.allow_network,
        "intended_action": "Capture pre-race odds snapshots (T-15m window)",
        "status": "DRY_RUN_CONTRACT_ONLY" if dry else "PENDING_PHASE3",
    })
    ops.finish_job(job_id, "SUCCESS", metrics={"snapshots_captured": 0})


def cmd_sigma(args: argparse.Namespace) -> None:
    dry = _is_dry_run(args)
    print(f"--- SIGMA --- date={args.date} dry_run={dry} network={args.allow_network}")
    if not dry and not args.allow_network:
        print("[BLOCKED] --allow-network required for live sigma. Aborting.")
        sys.exit(1)
    ops = OpsService(dry_run=dry, execute=args.execute)
    job_id = ops.start_job(args.date, "sigma")

    if dry:
        _write_artifact("sigma", args.date, {
            "job_type": "sigma",
            "date": args.date,
            "dry_run": True,
            "allow_network": args.allow_network,
            "intended_action": "Fetch results and reconcile via run_results_sigma.py",
            "calls_run_results_sigma": True,
            "sigma_script_unchanged": True,
            "status": "DRY_RUN_CONTRACT_ONLY",
        })
        ops.finish_job(job_id, "SUCCESS", metrics={"reconciled_races": 0, "sigma_failures": 0})
        return

    # ── Live execution ────────────────────────────────────────────────────────
    script = ROOT / "scripts" / "run_results_sigma.py"
    _timeout = int(os.environ.get("VELO_WORKER_TIMEOUT", "900"))
    try:
        proc = _run_script(script, ["--date", args.date], timeout=_timeout)
    except subprocess.TimeoutExpired as exc:
        ops.finish_failure(job_id, "SUBPROCESS_TIMEOUT", f"run_results_sigma.py exceeded {exc.timeout}s timeout")
        _write_artifact("sigma", args.date, {
            "job_type": "sigma", "date": args.date, "dry_run": False,
            "error_type": "SUBPROCESS_TIMEOUT", "sigma_script_unchanged": True, "status": "FAIL",
        })
        sys.exit(1)

    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print("[STDERR]", proc.stderr[:1000], file=sys.stderr)

    if proc.returncode == 0:
        ops.finish_success(job_id, metrics={"exit_code": 0}, output_artifacts={"stdout_tail": proc.stdout[-500:]})
        _write_artifact("sigma", args.date, {
            "job_type": "sigma",
            "date": args.date,
            "dry_run": False,
            "exit_code": 0,
            "sigma_script_unchanged": True,
            "status": "PASS",
        })
    else:
        error_type = ops.classify_error(proc.stdout, proc.stderr, proc.returncode)
        ops.finish_failure(job_id, error_type, (proc.stderr or proc.stdout)[-1000:])
        _write_artifact("sigma", args.date, {
            "job_type": "sigma",
            "date": args.date,
            "dry_run": False,
            "exit_code": proc.returncode,
            "error_type": error_type,
            "sigma_script_unchanged": True,
            "status": "FAIL",
        })
        sys.exit(proc.returncode)


def cmd_learn_shadow(args: argparse.Namespace) -> None:
    build_events_only = getattr(args, "build_events_only", False)
    sample_size = getattr(args, "sample_size", None)

    # Phase 3A: build events (optionally write to DB with --execute --build-events-only)
    # Phase 3B: shadow consumption — not yet implemented
    if args.execute and not build_events_only:
        print("[NOTICE] learn-shadow Phase 3B (shadow consumption) not yet implemented.")
        print("[NOTICE] Pass --build-events-only to write learning events to DB.")

    # DB writes only when --execute + --build-events-only; always read sigma_audits
    engine_execute = args.execute and build_events_only
    dry_label = not engine_execute

    print(
        f"--- LEARN-SHADOW --- date={args.date} dry_run={dry_label} "
        f"target={args.target_state} build_events_only={build_events_only} "
        f"sample_size={sample_size}"
    )

    ops = OpsService(dry_run=dry_label, execute=engine_execute)
    job_id = ops.start_job(args.date, "learn-shadow")

    engine = LearningEngine(
        dry_run=dry_label,
        execute=engine_execute,
        target_state=args.target_state,
    )

    events = engine.create_learning_events(args.date)

    db_result: dict = {"written": 0, "skipped": 0, "status": "dry_run"}
    if engine_execute:
        db_result = engine.write_events_to_db(events, sample_size=sample_size)

    _write_artifact("learn-shadow", args.date, {
        "job_type": "learn-shadow",
        "date": args.date,
        "dry_run": dry_label,
        "target_state": args.target_state,
        "build_events_only": build_events_only,
        "sample_size": sample_size,
        "sentient_state_touched": False,
        "playbook_g_promoted": False,
        "playbook_g_consumed": False,
        "events_built": len(events),
        "db_result": db_result,
        "status": "DRY_RUN_EVENTS_COUNTED" if dry_label else "EVENTS_WRITTEN",
    })

    ops.finish_job(
        job_id,
        "SUCCESS",
        metrics={"events_built": len(events), "events_written": db_result.get("written", 0)},
    )


def cmd_healthcheck(args: argparse.Namespace) -> None:
    dry = _is_dry_run(args)
    print(f"--- HEALTHCHECK --- date={args.date} dry_run={dry}")

    jobs: list = []
    if args.execute:
        try:
            ops = OpsService(dry_run=dry, execute=args.execute)
            jobs = ops.read_jobs_for_date(args.date)
        except Exception as exc:
            print(f"[WARN] Could not read velo_job_runs: {exc}")

    job_summary = {j.get("job_type", "unknown"): j.get("status", "UNKNOWN") for j in jobs}
    overall = "HEALTHY" if all(s == "PASS" for s in job_summary.values()) and job_summary else "STUB"

    _write_artifact("healthcheck", args.date, {
        "job_type": "healthcheck",
        "date": args.date,
        "dry_run": dry,
        "intended_action": "Report pipeline completeness and safety state",
        "sentient_state_touched": False,
        "migrations_applied": False,
        "jobs_from_db": jobs,
        "job_summary": job_summary,
        "status": overall,
    })


def cmd_full_day(args: argparse.Namespace) -> None:
    dry = _is_dry_run(args)
    print(f"--- FULL-DAY --- date={args.date} dry_run={dry}")
    cmd_ingest(args)
    cmd_predict(args)
    cmd_snapshot_market(args)
    cmd_sigma(args)
    # learn-shadow intentionally skipped when --execute (Phase 3)
    if not args.execute:
        cmd_learn_shadow(args)
    cmd_healthcheck(args)


def main() -> None:
    setup_logging()
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--date", required=True, help="Target date YYYY-MM-DD")
    shared.add_argument("--dry-run", action="store_true", default=True, help="Dry-run mode (default: True)")
    shared.add_argument("--execute", action="store_true", default=False, help="Enable real execution (overrides dry-run)")
    shared.add_argument("--allow-network", action="store_true", default=False, help="Allow network / API / DB calls")
    shared.add_argument("--target-state", default="shadow_repair_v1", help="Shadow state target for learn-shadow")

    parser = argparse.ArgumentParser(
        description="VÉLØ Ops Worker V2 — deterministic daily orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest",           parents=[shared], help="Fetch racecards and API data")
    sub.add_parser("predict",          parents=[shared], help="Run VÉLØ predictions")
    sub.add_parser("snapshot-market",  parents=[shared], help="Capture pre-race market state")
    sub.add_parser("sigma",            parents=[shared], help="Reconcile results with predictions")
    learn_shadow_p = sub.add_parser("learn-shadow", parents=[shared], help="Build learning events (Phase 3A); shadow consume Phase 3B")
    learn_shadow_p.add_argument("--build-events-only", action="store_true", default=False, help="Build and write events to DB; skip shadow consumption (Phase 3A)")
    learn_shadow_p.add_argument("--sample-size", type=int, default=None, metavar="N", help="Limit to first N events for testing")
    sub.add_parser("healthcheck",      parents=[shared], help="Report system status")
    sub.add_parser("full-day",         parents=[shared], help="Full pipeline: ingest→predict→sigma→healthcheck")

    args = parser.parse_args()

    dispatch = {
        "ingest":           cmd_ingest,
        "predict":          cmd_predict,
        "snapshot-market":  cmd_snapshot_market,
        "sigma":            cmd_sigma,
        "learn-shadow":     cmd_learn_shadow,
        "healthcheck":      cmd_healthcheck,
        "full-day":         cmd_full_day,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
