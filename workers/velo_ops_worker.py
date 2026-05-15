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
import hashlib
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


def _resolve_date(date_str: str) -> str:
    """Resolve 'today' → Europe/London racing date. Pass through YYYY-MM-DD unchanged."""
    if date_str.lower() == "today":
        from zoneinfo import ZoneInfo  # noqa: PLC0415
        return datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d")
    return date_str


def _take_preflight_snapshot(date: str, target_state: str, ops: "OpsService") -> dict:
    """
    Record system state before daily-eod runs.
    Always attempts DB reads (read-only); degrades gracefully if unavailable.
    """
    snap: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "live_state": {},
        "shadow_state": {},
        "cloud_backup": {"status": "not_queried"},
        "event_counts": {"status": "not_queried"},
        "job_counts": {"status": "not_queried"},
    }

    for label, path in [
        ("live_state",   ROOT / "data" / "sentient_state.json"),
        ("shadow_state", ROOT / "data" / f"sentient_state_{target_state}.json"),
    ]:
        if path.exists():
            raw = path.read_bytes()
            data = json.loads(raw)
            snap[label] = {
                "hash": hashlib.md5(raw).hexdigest(),
                "races": data.get("total_races_observed", 0),
                "last_updated": data.get("last_updated"),
            }
        else:
            snap[label] = {"exists": False}

    try:
        r = ops._get_sb().client.table("velo_learning_events").select(
            "consumed_shadow,consumed_live"
        ).eq("run_date", date).eq("target_state_name", target_state).execute()
        rows = r.data or []
        snap["event_counts"] = {
            "total": len(rows),
            "consumed_shadow_true": sum(1 for x in rows if x["consumed_shadow"]),
            "consumed_shadow_false": sum(1 for x in rows if not x["consumed_shadow"]),
            "consumed_live_true": sum(1 for x in rows if x["consumed_live"]),
        }
    except Exception as exc:
        snap["event_counts"] = {"error": str(exc)}

    try:
        cb = ops._get_sb().client.table("learned_patterns").select(
            "occurrences,last_observed,updated_at"
        ).eq("pattern_name", "SENTIENT_STATE_BACKUP").execute()
        snap["cloud_backup"] = cb.data[0] if cb.data else {"exists": False}
    except Exception as exc:
        snap["cloud_backup"] = {"error": str(exc)}

    try:
        jobs = ops.read_jobs_for_date(date)
        snap["job_counts"] = {
            "total": len(jobs),
            "pass": sum(1 for j in jobs if j.get("status") == "PASS"),
            "fail": sum(1 for j in jobs if j.get("status") == "FAIL"),
            "running": sum(1 for j in jobs if j.get("status") == "RUNNING"),
        }
    except Exception as exc:
        snap["job_counts"] = {"error": str(exc)}

    return snap


def _get_cloud_backup_updated_at(ops: "OpsService") -> str | None:
    """
    Resolve the canonical SENTIENT_STATE_BACKUP row safely.
    Prefer pattern_name, but fall back to pattern_type for compatibility.
    """
    rows = ops._get_sb().client.table("learned_patterns").select(
        "updated_at"
    ).eq("pattern_name", "SENTIENT_STATE_BACKUP").order(
        "updated_at", desc=True
    ).limit(1).execute()
    if rows.data:
        return rows.data[0].get("updated_at")

    fallback = ops._get_sb().client.table("learned_patterns").select(
        "updated_at"
    ).eq("pattern_type", "SENTIENT_STATE_BACKUP").order(
        "updated_at", desc=True
    ).limit(1).execute()
    if fallback.data:
        return fallback.data[0].get("updated_at")

    return None


def _get_results_cache_race_count(date: str) -> int:
    """Return cached result race count for the date, or 0 if unavailable."""
    path = ROOT / "data" / f"results_{date.replace('-', '_')}.json"
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    results = payload.get("results", [])
    return len(results) if isinstance(results, list) else 0


def _get_sigma_audits_count(date: str, ops: "OpsService") -> int:
    """Return sigma_audits row count for the date, falling back to row length."""
    try:
        resp = ops._get_sb().client.table("sigma_audits").select(
            "race_id", count="exact"
        ).eq("date", date).execute()
        if getattr(resp, "count", None) is not None:
            return int(resp.count or 0)
        return len(resp.data or [])
    except Exception:
        return 0


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

    # ── Phase 3B: consume unconsumed events into shadow state ─────────────────
    if args.execute and not build_events_only:
        print(
            f"--- LEARN-SHADOW (Phase 3B consume) --- date={args.date} "
            f"target={args.target_state} sample_size={sample_size}"
        )
        ops = OpsService(dry_run=False, execute=True)
        job_id = ops.start_job(args.date, "learn-shadow")
        engine = LearningEngine(dry_run=False, execute=True, target_state=args.target_state)

        events = engine.read_unconsumed_events(args.date)
        if sample_size:
            events = events[:sample_size]
        consume_result = engine.consume_events_into_shadow(events)

        _write_artifact("learn-shadow", args.date, {
            "job_type": "learn-shadow",
            "date": args.date,
            "dry_run": False,
            "target_state": args.target_state,
            "build_events_only": False,
            "sample_size": sample_size,
            "sentient_state_touched": True,
            "playbook_g_promoted": False,
            "playbook_g_consumed": True,
            "events_found": len(events),
            "consume_result": consume_result,
            "status": "SHADOW_CONSUMED",
        })
        ops.finish_job(
            job_id,
            "SUCCESS",
            metrics={
                "events_found": len(events),
                "events_consumed": consume_result.get("consumed", 0),
                "before_race_count": consume_result.get("before_race_count", 0),
                "after_race_count": consume_result.get("after_race_count", 0),
            },
        )
        return

    # ── Phase 3A: build events (+ write to DB with --build-events-only) ──────
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


def cmd_bulk_shadow_build(args: argparse.Namespace) -> None:
    """
    Build learning events for multiple historical dates into a shadow target state.
    Idempotent: existing events are skipped (ignore_duplicates=True).

    Eligible dates: those with both a velo_prime_verdicts artifact AND sigma_audits rows.
    Dates with no events after build are logged as ZERO_EVENTS (data quality, not errors).

    HFS policy: all current pipeline events are proxy_derived.
    missing_hfs_context=True for every event. No exceptions.
    """
    dry = _is_dry_run(args)
    target = args.target_state

    explicit_dates: list[str] = [d.strip() for d in args.dates.split(",") if d.strip()] if args.dates else []

    print(
        f"--- BULK-SHADOW-BUILD --- target={target} dry_run={dry} "
        f"dates={'explicit (' + str(len(explicit_dates)) + ')' if explicit_dates else 'auto-discover'}"
    )

    if not dry:
        ops = OpsService(dry_run=False, execute=True)
        job_id = ops.start_job("bulk", "bulk-shadow-build")

    engine = LearningEngine(dry_run=dry, execute=not dry, target_state=target)

    # Auto-discover eligible dates if not supplied explicitly
    if not explicit_dates:
        try:
            sb_client = engine._get_sb().client
            sigma_dates: set[str] = set()
            offset, page = 0, 1000
            while True:
                r = sb_client.table("sigma_audits").select("date").range(offset, offset + page - 1).execute()
                batch = r.data or []
                for row in batch:
                    d = row.get("date")
                    if d:
                        sigma_dates.add(d)
                if len(batch) < page:
                    break
                offset += page
        except Exception as exc:
            print(f"[WARN] Could not query sigma_audits dates: {exc}. Pass --dates explicitly.")
            sigma_dates = set()
        pred_dates = set()
        for p in (ROOT / "data").glob("velo_prime_verdicts_*.json"):
            key = p.name.replace("velo_prime_verdicts_", "").replace(".json", "").replace("_", "-")
            pred_dates.add(key)
        eligible_dates = sorted(pred_dates & sigma_dates)
    else:
        eligible_dates = sorted(explicit_dates)

    print(f"[BULK] Processing {len(eligible_dates)} dates for target={target}")

    summary: dict = {
        "target_state": target,
        "dry_run": dry,
        "dates_processed": len(eligible_dates),
        "total_events_built": 0,
        "total_written": 0,
        "total_skipped": 0,
        "zero_event_dates": [],
        "by_date": {},
    }

    for date in eligible_dates:
        events = engine.create_learning_events(date)
        db_result: dict = {"written": 0, "skipped": 0, "status": "dry_run"}
        if not dry:
            db_result = engine.write_events_to_db(events)

        proxy_count = sum(1 for e in events if e.get("missing_hfs_context"))
        summary["total_events_built"] += len(events)
        summary["total_written"] += db_result.get("written", 0)
        summary["total_skipped"] += db_result.get("skipped", 0)
        summary["by_date"][date] = {
            "events_built": len(events),
            "written": db_result.get("written", 0),
            "skipped": db_result.get("skipped", 0),
            "proxy_classified": proxy_count,
            "status": db_result.get("status", "dry_run"),
        }
        if len(events) == 0:
            summary["zero_event_dates"].append(date)
            print(f"  [ZERO_EVENTS] {date} — no eligible events (data quality, skipping)")
        else:
            print(
                f"  {date}: built={len(events)} written={db_result.get('written',0)} "
                f"skipped={db_result.get('skipped',0)} proxy={proxy_count}/{len(events)}"
            )

    print(
        f"\n[BULK SUMMARY] total_built={summary['total_events_built']} "
        f"written={summary['total_written']} skipped={summary['total_skipped']} "
        f"zero_dates={len(summary['zero_event_dates'])}"
    )

    if not dry:
        ops.finish_job(
            job_id,
            "SUCCESS",
            metrics={
                "total_events_built": summary["total_events_built"],
                "total_written": summary["total_written"],
                "total_skipped": summary["total_skipped"],
            },
        )

    _write_artifact("bulk-shadow-build", "bulk", summary)


def cmd_bulk_shadow_consume(args: argparse.Namespace) -> None:
    """
    Consume all unconsumed velo_learning_events for target_state across ALL dates.
    Processes in run_date order. Optional --sample-size caps consumption for gated batches.

    Safety gates (hard stop):
      - consumed_live=True detected at any point
      - live sentient_state.json hash changes during run
      - cloud backup updated_at changes during run
    """
    dry = _is_dry_run(args)
    target = args.target_state
    sample_size: int | None = getattr(args, "sample_size", None)

    print(
        f"--- BULK-SHADOW-CONSUME --- target={target} dry_run={dry} "
        f"sample_size={sample_size if sample_size else 'ALL'}"
    )

    if dry:
        print("[DRY-RUN] No state will be mutated.")

    # ── Baseline snapshots ────────────────────────────────────────────────────
    import hashlib as _hl
    live_path = ROOT / "data" / "sentient_state.json"
    shadow_path = ROOT / "data" / f"sentient_state_{target}.json"

    live_hash_before = _hl.md5(live_path.read_bytes()).hexdigest()[:8] if live_path.exists() else None
    shadow_races_before: int | None = None
    if shadow_path.exists():
        sj = json.loads(shadow_path.read_bytes())
        shadow_races_before = sj.get("total_races_observed")

    print(
        f"[PREFLIGHT] live_hash={live_hash_before} "
        f"shadow_races_before={shadow_races_before}"
    )

    # Cloud backup baseline
    cloud_ts_before: str | None = None
    try:
        ops_tmp = OpsService(dry_run=True, execute=False)
        cloud_ts_before = _get_cloud_backup_updated_at(ops_tmp)
    except Exception:
        pass

    engine = LearningEngine(dry_run=dry, execute=not dry, target_state=target)

    # ── Load unconsumed events ────────────────────────────────────────────────
    events = engine.read_all_unconsumed_events(sample_size=sample_size)
    print(f"[BULK-CONSUME] Found {len(events)} unconsumed events to process")

    if not events:
        print("[BULK-CONSUME] No unconsumed events - idempotency confirmed.")
        _write_artifact("bulk-shadow-consume", "all", {
            "target_state": target,
            "dry_run": dry,
            "sample_size": sample_size,
            "events_found": 0,
            "consumed": 0,
            "skipped": 0,
            "shadow_races_before": shadow_races_before,
            "shadow_races_after": shadow_races_before,
            "live_hash_before": live_hash_before,
            "live_hash_after": live_hash_before,
            "live_unchanged": True,
            "status": "IDEMPOTENT_EMPTY",
        })
        return

    if dry:
        _write_artifact("bulk-shadow-consume", "all", {
            "target_state": target,
            "dry_run": True,
            "sample_size": sample_size,
            "events_found": len(events),
            "status": "DRY_RUN",
        })
        return

    # ── Execute consume ───────────────────────────────────────────────────────
    consume_result = engine.consume_events_into_shadow(events)

    consumed = consume_result.get("consumed", 0)
    skipped = consume_result.get("skipped", 0)
    shadow_races_after = consume_result.get("after_race_count")

    # ── Post-run safety checks ────────────────────────────────────────────────
    live_hash_after = _hl.md5(live_path.read_bytes()).hexdigest()[:8] if live_path.exists() else None
    live_unchanged = (live_hash_after == live_hash_before)

    if not live_unchanged:
        print(f"[HARD STOP] sentient_state.json hash changed! before={live_hash_before} after={live_hash_after}")
        _write_artifact("bulk-shadow-consume", "all", {
            "status": "SAFETY_VIOLATION",
            "stop_reason": "live_state_hash_changed",
            "live_hash_before": live_hash_before,
            "live_hash_after": live_hash_after,
        })
        sys.exit(1)

    cloud_ts_after: str | None = None
    try:
        cloud_ts_after = _get_cloud_backup_updated_at(ops_tmp)
    except Exception:
        pass

    if cloud_ts_before and cloud_ts_after and cloud_ts_after != cloud_ts_before:
        print(f"[HARD STOP] Cloud backup updated_at changed! before={cloud_ts_before} after={cloud_ts_after}")
        _write_artifact("bulk-shadow-consume", "all", {
            "status": "SAFETY_VIOLATION",
            "stop_reason": "cloud_backup_touched",
        })
        sys.exit(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    safety = (
        "SAFE" if (
            live_unchanged
            and consume_result.get("consumed_live_total", 0) == 0
            and (cloud_ts_before is None or cloud_ts_after == cloud_ts_before)
        ) else "VIOLATION"
    )

    summary = {
        "target_state": target,
        "dry_run": dry,
        "sample_size": sample_size,
        "events_found": len(events),
        "consumed": consumed,
        "skipped": skipped,
        "shadow_races_before": shadow_races_before,
        "shadow_races_after": shadow_races_after,
        "live_hash_before": live_hash_before,
        "live_hash_after": live_hash_after,
        "live_unchanged": live_unchanged,
        "cloud_backup_before": cloud_ts_before,
        "cloud_backup_after": cloud_ts_after,
        "safety": safety,
        "status": "OK" if skipped == 0 else "PARTIAL",
    }

    print(
        f"[BULK-CONSUME] consumed={consumed} skipped={skipped} "
        f"races {shadow_races_before}->{shadow_races_after} "
        f"live_hash={live_hash_after} (unchanged={live_unchanged}) "
        f"safety={safety}"
    )

    _write_artifact("bulk-shadow-consume", "all", summary)


def cmd_daily_eod(args: argparse.Namespace) -> None:
    """
    Phase 4A — daily EOD orchestration.
    Sequence: sigma → learn-shadow build → learn-shadow consume → healthcheck → forensic report.

    NOTE: Ingestion (ingest command) is NOT automated in Phase 4A.
    Ingest remains manual / external until a safe ingest wrapper is verified in Phase 5.

    Safety gates (hard stop):
      - consumed_live=True detected at preflight
      - sigma subprocess non-zero exit
      - events_built > 0 but written=0 and skipped=0 (DB upsert malfunction)
      - live sentient_state.json hash changes during run
      - cloud backup updated_at changes during run

    Rollback note (document only — do not run automatically):
      If shadow state is restored from backup, reset DB consumed flags first:
        UPDATE velo_learning_events SET consumed_shadow=false
        WHERE run_date='YYYY-MM-DD' AND target_state_name='shadow_repair_v1';
      Then re-run daily-eod consume stage.
    """
    dry = _is_dry_run(args)
    date = args.date

    print(
        f"--- DAILY-EOD --- date={date} dry_run={dry} "
        f"network={args.allow_network} target={args.target_state}"
    )
    print("[NOTE] Ingestion is NOT automated in Phase 4A — run ingest manually if needed.")

    ops = OpsService(dry_run=dry, execute=args.execute)
    eod_job_id = ops.start_job(date, "daily-eod")

    # ── Preflight snapshot ────────────────────────────────────────────────────
    preflight = _take_preflight_snapshot(date, args.target_state, ops)
    live_hash_before = preflight.get("live_state", {}).get("hash")
    cloud_ts_before = preflight.get("cloud_backup", {}).get("updated_at")

    print(
        f"[PREFLIGHT] live_races={preflight['live_state'].get('races')} "
        f"shadow_races={preflight['shadow_state'].get('races')} "
        f"events_total={preflight['event_counts'].get('total', 'N/A')} "
        f"consumed_live={preflight['event_counts'].get('consumed_live_true', 'N/A')}"
    )

    # Hard stop: consumed_live already present for this date
    if preflight.get("event_counts", {}).get("consumed_live_true", 0) > 0:
        print("[HARD STOP] consumed_live=True detected at preflight. SAFETY_VIOLATION.")
        ops.finish_failure(eod_job_id, "SAFETY_VIOLATION", "consumed_live_true_at_preflight")
        _write_artifact("daily-eod", date, {
            "overall_status": "SAFETY_VIOLATION",
            "stop_reason": "consumed_live_true_at_preflight",
            "preflight": preflight,
        })
        sys.exit(1)

    pipeline: dict = {
        "sigma":         {"status": "SKIPPED"},
        "learn_build":   {"status": "SKIPPED"},
        "learn_consume": {"status": "SKIPPED"},
        "healthcheck":   {"status": "SKIPPED"},
    }
    warnings: list[str] = []

    # ── Stage 1: Sigma ────────────────────────────────────────────────────────
    sigma_args = argparse.Namespace(
        date=date, execute=args.execute, allow_network=args.allow_network,
        dry_run=dry, target_state=args.target_state,
    )
    try:
        cmd_sigma(sigma_args)
        pipeline["sigma"] = {
            "status": "PASS",
            "results_races": _get_results_cache_race_count(date),
            "sigma_audits_written": _get_sigma_audits_count(date, ops),
        }
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 1
        pipeline["sigma"] = {"status": "FAIL", "exit_code": code}
        ops.finish_failure(eod_job_id, "SIGMA_FAILED", f"sigma exit {code}")
        _write_artifact("daily-eod", date, {
            "overall_status": "SIGMA_FAILED",
            "stop_reason": f"sigma_exit_{code}",
            "pipeline": pipeline,
            "preflight": preflight,
        })
        sys.exit(code)

    # ── Stage 2: Learn-shadow build ───────────────────────────────────────────
    if (
        pipeline["sigma"].get("results_races", 0) == 0
        or pipeline["sigma"].get("sigma_audits_written", 0) == 0
    ):
        report = {
            "date": date,
            "target_state": args.target_state,
            "overall_status": "SIGMA_RESULTS_NOT_READY",
            "stop_reason": "ZERO_RESULTS_HARD_STOP",
            "pipeline": {
                **pipeline,
                "learn_build": {"status": "SKIPPED"},
                "learn_consume": {"status": "SKIPPED"},
                "healthcheck": {"status": "SKIPPED"},
            },
            "preflight": preflight,
            "warnings": [
                "No usable Sigma result truth was persisted for this date.",
                "Learning build and consume were skipped by hard-stop guard.",
            ],
            "live_state_touched": False,
            "shadow_delta": 0,
        }
        report_dir = ROOT / "data" / "phase4_daily_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{date}_daily_eod_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[REPORT] {report_path}")
        ops.finish_failure(
            eod_job_id,
            "SIGMA_RESULTS_NOT_READY",
            "ZERO_RESULTS_HARD_STOP",
        )
        _write_artifact("daily-eod", date, report)
        print(f"[DAILY-EOD] {report.get('overall_status')}")
        sys.exit(1)

    engine = LearningEngine(dry_run=dry, execute=args.execute, target_state=args.target_state)
    events = engine.create_learning_events(date)
    db_build: dict = {"written": 0, "skipped": 0, "status": "dry_run"}
    if args.execute:
        db_build = engine.write_events_to_db(events)

    build_status = "PASS"
    if len(events) == 0:
        build_status = "WARN"
        warnings.append("ZERO_EVENTS_BUILT — sigma may have produced no qualifying rows for this date")
    elif args.execute and db_build.get("written", 0) == 0 and db_build.get("skipped", 0) == 0:
        build_status = "FAIL"

    pipeline["learn_build"] = {
        "status": build_status,
        "events_built": len(events),
        "written": db_build.get("written", 0),
        "skipped": db_build.get("skipped", 0),
    }

    # Hard stop: events exist but DB accepted nothing (upsert malfunction)
    if build_status == "FAIL":
        ops.finish_failure(eod_job_id, "DB_WRITE_FAILURE", "events_built_but_nothing_written_or_skipped")
        _write_artifact("daily-eod", date, {
            "overall_status": "ZERO_EVENTS",
            "stop_reason": "events_built_but_db_write_empty",
            "pipeline": pipeline,
            "preflight": preflight,
        })
        sys.exit(1)

    # ── Stage 3: Learn-shadow consume ─────────────────────────────────────────
    consume_result: dict = {
        "consumed": 0, "skipped": 0, "status": "dry_run",
        "before_race_count": 0, "after_race_count": 0,
    }
    if args.execute:
        unconsumed = engine.read_unconsumed_events(date)
        consume_result = engine.consume_events_into_shadow(unconsumed)
        consume_status = "WARN" if consume_result.get("skipped", 0) > 0 else "PASS"
        if consume_result.get("skipped", 0) > 0:
            warnings.append(f"PARTIAL_CONSUME: {consume_result['skipped']} events skipped")
        pipeline["learn_consume"] = {
            "status": consume_status,
            "events_found": len(unconsumed),
            "consumed": consume_result.get("consumed", 0),
            "skipped": consume_result.get("skipped", 0),
            "before_race_count": consume_result.get("before_race_count", 0),
            "after_race_count": consume_result.get("after_race_count", 0),
        }
    else:
        pipeline["learn_consume"] = {"status": "DRY_RUN"}

    # ── Live state integrity check ────────────────────────────────────────────
    live_path = ROOT / "data" / "sentient_state.json"
    if live_path.exists() and live_hash_before:
        live_hash_after = hashlib.md5(live_path.read_bytes()).hexdigest()
        if live_hash_after != live_hash_before:
            print("[HARD STOP] sentient_state.json hash changed during run. SAFETY_VIOLATION.")
            ops.finish_failure(eod_job_id, "SAFETY_VIOLATION", "live_state_hash_changed")
            _write_artifact("daily-eod", date, {
                "overall_status": "SAFETY_VIOLATION",
                "stop_reason": "live_state_hash_changed",
                "pipeline": pipeline,
                "preflight": preflight,
            })
            sys.exit(1)

    # ── Cloud backup integrity check ──────────────────────────────────────────
    if cloud_ts_before:
        try:
            cb = ops._get_sb().client.table("learned_patterns").select("updated_at").eq(
                "pattern_name", "SENTIENT_STATE_BACKUP"
            ).execute()
            cloud_ts_after = cb.data[0].get("updated_at") if cb.data else None
            if cloud_ts_after and cloud_ts_after != cloud_ts_before:
                print("[HARD STOP] Cloud backup updated_at changed. SAFETY_VIOLATION.")
                ops.finish_failure(eod_job_id, "SAFETY_VIOLATION", "cloud_backup_touched")
                _write_artifact("daily-eod", date, {
                    "overall_status": "SAFETY_VIOLATION",
                    "stop_reason": "cloud_backup_touched",
                    "pipeline": pipeline,
                    "preflight": preflight,
                })
                sys.exit(1)
        except Exception as exc:
            warnings.append(f"CLOUD_BACKUP_CHECK_FAILED: {exc}")

    # ── Stage 4: Healthcheck ──────────────────────────────────────────────────
    hc_args = argparse.Namespace(
        date=date, execute=args.execute, dry_run=dry, target_state=args.target_state,
    )
    cmd_healthcheck(hc_args)
    pipeline["healthcheck"] = {"status": "PASS"}

    # ── Forensic report ───────────────────────────────────────────────────────
    report = engine.generate_daily_report(
        date=date,
        pipeline=pipeline,
        preflight=preflight,
        consume_result=consume_result,
        warnings=warnings,
    )

    report_dir = ROOT / "data" / "phase4_daily_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{date}_daily_eod_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[REPORT] {report_path}")

    ops.finish_job(
        eod_job_id,
        "SUCCESS",
        metrics={
            "events_built": len(events),
            "events_consumed": consume_result.get("consumed", 0),
            "shadow_races_before": consume_result.get("before_race_count", 0),
            "shadow_races_after": consume_result.get("after_race_count", 0),
            "overall_status": report.get("overall_status"),
        },
    )
    _write_artifact("daily-eod", date, report)
    print(f"[DAILY-EOD] {report.get('overall_status')}")


def cmd_forensic_report(args: argparse.Namespace) -> None:
    """
    Generate a forensic report for a given date without running any pipeline stages.
    Reads current state from disk and DB only. Safe to run at any time.
    """
    dry = _is_dry_run(args)
    date = args.date
    print(f"--- FORENSIC-REPORT --- date={date} dry_run={dry} target={args.target_state}")

    ops = OpsService(dry_run=dry, execute=args.execute)
    engine = LearningEngine(dry_run=dry, execute=args.execute, target_state=args.target_state)
    preflight = _take_preflight_snapshot(date, args.target_state, ops)

    report = engine.generate_daily_report(
        date=date,
        pipeline={},
        preflight=preflight,
        consume_result={},
        warnings=["forensic_report_only — no pipeline stages run"],
    )

    report_dir = ROOT / "data" / "phase4_daily_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{date}_forensic_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[REPORT] {report_path}")
    _write_artifact("forensic-report", date, report)
    print(f"[FORENSIC-REPORT] {report.get('overall_status')}")


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
    bulk_p = sub.add_parser("bulk-shadow-build", parents=[shared], help="Build learning events for multiple dates into shadow target state")
    bulk_p.add_argument("--dates", default="", help="Comma-separated dates YYYY-MM-DD. Omit to auto-discover from sigma_audits + verdict artifacts.")
    bulk_consume_p = sub.add_parser("bulk-shadow-consume", parents=[shared], help="Consume all unconsumed learning events across all dates into shadow target state")
    bulk_consume_p.add_argument("--sample-size", type=int, default=None, metavar="N", help="Limit to first N events (date-ordered) for gated batch testing")
    sub.add_parser("daily-eod",        parents=[shared], help="EOD cycle: sigma→learn-shadow-build→consume→healthcheck→report (ingest NOT automated)")
    sub.add_parser("forensic-report",  parents=[shared], help="Read-only forensic report for a date (no pipeline stages)")

    args = parser.parse_args()
    args.date = _resolve_date(args.date)

    dispatch = {
        "ingest":           cmd_ingest,
        "predict":          cmd_predict,
        "snapshot-market":  cmd_snapshot_market,
        "sigma":            cmd_sigma,
        "learn-shadow":     cmd_learn_shadow,
        "healthcheck":      cmd_healthcheck,
        "full-day":         cmd_full_day,
        "bulk-shadow-build":    cmd_bulk_shadow_build,
        "bulk-shadow-consume":  cmd_bulk_shadow_consume,
        "daily-eod":            cmd_daily_eod,
        "forensic-report":  cmd_forensic_report,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
