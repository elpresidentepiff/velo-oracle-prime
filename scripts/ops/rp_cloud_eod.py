#!/usr/bin/env python3
"""Cloud-owned Racing Post results capture and governed EOD handoff.

Railway cron containers do not share the morning worker's filesystem.  This
entrypoint reconstructs the exact scored race universe from durable Supabase
morning truth, converts the preserved Racing Post racecard URLs to results
URLs, captures and parses the RP HTML with the existing cloud credentials and
browser profile, and then invokes the canonical EOD orchestrator.

No alternate racing source is used.  No scoring, model, weight, gate, staking,
or execution-mode behaviour is changed.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LONDON = ZoneInfo("Europe/London")
PROFILE = ROOT / "data" / "browser_profiles" / "racing_post_account"
RAW = ROOT / "data" / "racing_post_account_raw"
URL_LIST_ROOT = ROOT / "data" / "racing_post_url_lists"
REPORT_ARTIFACT_PREFIXES = ("data/", "app/static/dashboard/")

MANDATORY_EOD_STEPS = {
    "Step 12: Results + sigma reconciliation",
    "Step 12B: Multi-model sigma",
    "Step 13: Ingest results to horse runs",
    "Step 15: Update Mission Control",
    "Step 16b: VELO Council",
    "Step 16c: LLM End-of-Day Report",
    "Step 16d: Mission Control final refresh (post-council)",
    "Step 20: Nightly EOD learning runner",
    "Step 20C: Canonical scorecard rebuild (results-aware)",
    "Step 20D: Canonical scorecard persist (post-results)",
    "Step 20E: Canonical learning events build + persist",
    "Step 20F: Persist nightly learning events (velo_learning_events)",
    "Step 22: Persist daily artifacts (council, MC, ledger, reports)",
}


def _supabase() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and Supabase service key are required")
    return url, key


def _get(table: str, params: dict[str, str]) -> list[dict]:
    url, key = _supabase()
    response = requests.get(
        f"{url}/rest/v1/{table}",
        params=params,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected Supabase payload for {table}: {type(payload).__name__}")
    return payload


def _chunks(values: list[str], size: int = 40) -> list[list[str]]:
    return [values[offset : offset + size] for offset in range(0, len(values), size)]


def _results_url(source_url: str, race_id: str) -> str | None:
    url = (source_url or "").strip()
    if "/racecards/" not in url:
        return None
    result = url.replace("/racecards/", "/results/").rstrip("/")
    if not result.endswith(f"/{race_id}"):
        return None
    return result


def _top_pick_name(verdict: dict) -> str | None:
    full = verdict.get("full_analysis") or {}
    predictions = (full.get("predictions") or []) if isinstance(full, dict) else []
    top_id = str(verdict.get("top_rank_horse_id") or "")
    for row in predictions:
        if not isinstance(row, dict):
            continue
        if str(row.get("horse_id") or row.get("id") or "") == top_id:
            return row.get("horse") or row.get("name") or row.get("horse_name")
    return None


def _safe_artifact_path(source_path: str) -> Path | None:
    normal = (source_path or "").replace("\\", "/").lstrip("/")
    if ".." in Path(normal).parts or not normal.startswith(REPORT_ARTIFACT_PREFIXES):
        return None
    target = (ROOT / normal).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return target


def _hydrate_report_artifacts(date_str: str) -> int:
    rows = _get(
        "velo_report_artifacts",
        {
            "select": "artifact_type,source_path,payload",
            "run_date": f"eq.{date_str}",
            "order": "persisted_at.asc",
        },
    )
    written = 0
    for row in rows:
        # The verdict backup is rebuilt above from the latest durable verdict rows.
        # Never replace it with an older report-artifact snapshot.
        if row.get("artifact_type") == "velo_prime_verdicts":
            continue
        target = _safe_artifact_path(str(row.get("source_path") or ""))
        if target is None or row.get("payload") is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(row["payload"], indent=2), encoding="utf-8")
        written += 1
    return written


def prepare_cloud_eod_inputs(date_str: str) -> dict[str, Any]:
    """Materialize the exact scored race universe from durable morning truth."""
    races = _get(
        "races",
        {
            "select": "race_id,course,date,time,raw",
            "date": f"eq.{date_str}",
            "order": "time.asc",
        },
    )
    if not races:
        raise RuntimeError(f"No Supabase races found for {date_str}")

    race_by_id = {str(row.get("race_id") or ""): row for row in races if row.get("race_id")}
    verdict_rows: list[dict] = []
    select = (
        "race_id,top_rank_horse_id,velo_prime_prob,decision_tier,confidence_level,"
        "generated_at,full_analysis,assigned_product,predicted_field_size,race_type"
    )
    for chunk in _chunks(sorted(race_by_id)):
        verdict_rows.extend(
            _get(
                "velo_verdicts",
                {"select": select, "race_id": f"in.({','.join(chunk)})"},
            )
        )
    latest: dict[str, dict] = {}
    for row in verdict_rows:
        race_id = str(row.get("race_id") or "")
        if not race_id:
            continue
        if race_id not in latest or str(row.get("generated_at") or "") > str(
            latest[race_id].get("generated_at") or ""
        ):
            latest[race_id] = row
    if not latest:
        raise RuntimeError(f"No scored velo_verdicts found for Supabase races on {date_str}")

    standard_cards: list[dict] = []
    backup_verdicts: list[dict] = []
    result_urls: list[str] = []
    missing: list[str] = []
    for race_id in sorted(latest, key=lambda rid: str(race_by_id.get(rid, {}).get("time") or "")):
        race = race_by_id.get(race_id)
        if not race:
            missing.append(f"{race_id}:MISSING_RACE_ROW")
            continue
        raw = race.get("raw") or {}
        source_url = raw.get("source_url") or raw.get("final_url") or ""
        result_url = _results_url(str(source_url), race_id)
        if not result_url:
            missing.append(f"{race_id}:MISSING_OR_INVALID_RP_URL")
            continue
        standard_cards.append(raw)
        result_urls.append(result_url)
        verdict = latest[race_id]
        top_pick_name = _top_pick_name(verdict)
        if not top_pick_name:
            missing.append(f"{race_id}:TOP_PICK_NAME_MISSING")
            continue
        backup_verdicts.append(
            {
                "race_id": race_id,
                "course": race.get("course") or raw.get("course") or "",
                "off_time": raw.get("off_time") or str(race.get("time") or ""),
                "top": {
                    "horse": top_pick_name,
                    "horse_id": verdict.get("top_rank_horse_id"),
                },
                "tier": verdict.get("decision_tier"),
                "assigned_product": verdict.get("assigned_product"),
                "signal_stack": {"vp": verdict.get("velo_prime_prob")},
            }
        )

    if missing or len(result_urls) != len(latest):
        raise RuntimeError(
            f"Cloud EOD race-universe gate failed: scored={len(latest)} urls={len(result_urls)} "
            f"missing={missing[:10]}"
        )

    date_tag = date_str.replace("-", "_")
    racecard_path = ROOT / "data" / f"racecards_{date_tag}_standard.json"
    verdict_path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
    url_path = URL_LIST_ROOT / f"rp_results_{date_str}.txt"
    racecard_path.parent.mkdir(parents=True, exist_ok=True)
    URL_LIST_ROOT.mkdir(parents=True, exist_ok=True)
    racecard_path.write_text(json.dumps(standard_cards, indent=2), encoding="utf-8")
    verdict_path.write_text(json.dumps(backup_verdicts, indent=2), encoding="utf-8")
    url_path.write_text("\n".join(result_urls) + "\n", encoding="utf-8")
    hydrated = _hydrate_report_artifacts(date_str)

    return {
        "date": date_str,
        "races_available": len(races),
        "scored_races": len(latest),
        "results_urls": len(result_urls),
        "report_artifacts_hydrated": hydrated,
        "racecard_path": str(racecard_path.relative_to(ROOT)),
        "verdict_path": str(verdict_path.relative_to(ROOT)),
        "url_list": str(url_path.relative_to(ROOT)),
        "source": "Supabase morning RP truth -> Racing Post results HTML",
    }


def _run(label: str, command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"\n[CLOUD-EOD] {label}: {' '.join(command)}", flush=True)
    child_env = os.environ.copy()
    child_env.update(env or {})
    result = subprocess.run(command, cwd=ROOT, env=child_env, check=False)
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def _login() -> None:
    from playwright.sync_api import sync_playwright

    from scripts.ops.rp_cloud_probe import cloud_login

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.firefox.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=True,
            viewport={"width": 1400, "height": 1000},
            firefox_user_prefs={"gfx.webrender.enabled": False, "gfx.webrender.all": False},
        )
        result = cloud_login(context)
        context.close()
    if result.get("status") != "PASS":
        raise RuntimeError(f"Racing Post cloud login failed: {result.get('reason') or result}")


def _verify_eod_report(date_str: str) -> dict[str, Any]:
    path = ROOT / "data" / "reports" / f"run_full_raceday_eod_{date_str.replace('-', '_')}.json"
    if not path.exists():
        raise RuntimeError(f"EOD report missing: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    by_name = {row.get("step"): row for row in report.get("results") or []}
    missing = sorted(MANDATORY_EOD_STEPS - set(by_name))
    failed = sorted(step for step in MANDATORY_EOD_STEPS if step in by_name and not by_name[step].get("ok"))
    if missing or failed:
        raise RuntimeError(f"Mandatory EOD postcondition failed: missing={missing} failed={failed}")
    return {"report": str(path.relative_to(ROOT)), "mandatory_steps_passed": len(MANDATORY_EOD_STEPS)}


def _verify_pipeline_run(date_str: str) -> dict[str, Any]:
    rows = _get(
        "pipeline_runs",
        {
            "select": "id,status,run_state,source_date,started_at,finished_at,commit_sha,environment",
            "service_name": "eq.velo-results-sigma",
            "source_date": f"eq.{date_str}",
            "order": "started_at.desc",
            "limit": "1",
        },
    )
    if not rows or rows[0].get("status") != "PASS" or rows[0].get("run_state") != "completed":
        raise RuntimeError(f"Durable Sigma pipeline run not PASS/completed for {date_str}: {rows}")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="Race date YYYY-MM-DD; defaults to London today")
    parser.add_argument("--execute", action="store_true", help="Capture RP results and run canonical EOD")
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--include-passport-refresh", action="store_true")
    args = parser.parse_args()
    date_str = args.date or datetime.now(LONDON).date().isoformat()

    print(f"VELO CLOUD RP EOD — {date_str}", flush=True)
    print("executor=Railway source=RacingPost-HTML durable_truth=Supabase", flush=True)
    preparation = prepare_cloud_eod_inputs(date_str)
    print(json.dumps({"preparation": preparation}, indent=2), flush=True)
    if not args.execute:
        print("[CLOUD-EOD] PLAN_ONLY — capture and EOD were not executed", flush=True)
        return 0

    _login()
    _run(
        "capture RP results pages",
        [
            sys.executable,
            "scripts/ops/racing_post_account_collector.py",
            "capture",
            "--url-list",
            str(ROOT / preparation["url_list"]),
            "--date",
            f"rp-results-{date_str}",
            "--profile-dir",
            str(PROFILE),
            "--output-dir",
            str(RAW),
            "--delay-seconds",
            os.getenv("RP_CLOUD_CAPTURE_DELAY_SECONDS", "1.5"),
            "--execute",
        ],
    )
    _run(
        "parse RP results pages",
        [
            sys.executable,
            "scripts/ops/parse_rp_results_capture.py",
            "--date",
            date_str,
            "--capture-date",
            f"rp-results-{date_str}",
            "--execute",
        ],
    )
    eod_command = [
        sys.executable,
        "scripts/ops/run_full_raceday_eod.py",
        "--date",
        date_str,
        "--execute",
        "--skip-results-capture",
    ]
    if not args.include_passport_refresh:
        eod_command.append("--skip-passport-refresh")
    if args.no_notify:
        eod_command.append("--no-notify")
    _run(
        "canonical EOD sequence",
        eod_command,
        env={"TRIGGER_SOURCE": "railway_cron", "VELO_EXECUTION_MODE": "SIM"},
    )
    report = _verify_eod_report(date_str)
    pipeline = _verify_pipeline_run(date_str)
    print(json.dumps({"status": "PASS", "eod": report, "pipeline_run": pipeline}, indent=2), flush=True)
    print(f"[CLOUD-EOD] PASS — governed EOD completed for {date_str}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
