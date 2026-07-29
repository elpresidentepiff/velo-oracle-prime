"""
new_build_dashboard_server.py

DEPRECATED AS A STANDALONE SERVER (2026-07-08). app/main.py is now the one
canonical dashboard server -- it has every route this file defines (verified
via route-set diff 2026-07-08; the only gap is /api/health vs app/main.py's
equivalent /health). Running BOTH servers on the same port at different
times is exactly what caused the Champion Intent Shadow panel to silently
show "No Champion Intent data" for a full session on 2026-07-08: the
frontend always calls /api/model-suggestions, but whichever of these two
apps happened to be running that hour may not have had the route. See
docs/current/ONE_TRUTH.md.

This module is kept because app/main.py imports fetch_canonical_scorecard,
fetch_canonical_learning_events, and _remap_numeric_race_ids from it
directly -- do not delete. Do not run this file's __main__ block in
production; use app/main.py (or .local_salvage/run_dashboard.py-style
`from dotenv import load_dotenv; load_dotenv(); import uvicorn;
uvicorn.run("app.main:app", ...)` launcher) instead.

Original docstring (routes now mirrored on app/main.py):
Minimal dashboard server for New Build paper-only reads.

Serves:
  GET /             → redirect to /dashboard
  GET /dashboard    → static dashboard HTML
  GET /sidecar_stack_latest.json  → New Build sidecar JSON
  GET /api/governed-card?date=YYYY-MM-DD → New Build verdicts in governed-card shape
  GET /api/health   → health check

Read-only Supabase reads added for canonical truth endpoints
(public.canonical_model_scorecards, public.canonical_learning_events).
No Supabase writes. No model_manager. No Live VELO. No Telegram. No staking.

Usage:
  python scripts/ops/new_build_dashboard_server.py [--port 8000]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    raise SystemExit("Run: pip install fastapi uvicorn")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATIC_DIR = ROOT / "app" / "static" / "dashboard"
NEW_BUILD_ROOT = ROOT / "data" / "new_build"
REPORT_DIR = NEW_BUILD_ROOT / "reports"
PRED_DIR = NEW_BUILD_ROOT / "paper_predictions"

app = FastAPI(title="New Build Dashboard", docs_url=None, redoc_url=None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default=None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sb_get(path: str) -> list[dict]:
    """Read-only Supabase REST fetch. No write path exists in this file.

    Paginates via PostgREST Range headers -- the default max-rows (1000)
    was silently truncating canonical_model_scorecards on any date with
    >1000 rows (found 2026-07-16: a single day's canonical scorecard is
    1236 rows once all four models + roles are persisted). Loops until a
    page returns fewer rows than requested, or a fetched page is empty.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return []
    page_size = 1000
    all_rows: list[dict] = []
    offset = 0
    while True:
        req = urllib.request.Request(
            url + "/rest/v1" + path,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range-Unit": "items",
                "Range": f"{offset}-{offset + page_size - 1}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                page = json.loads(r.read().decode())
        except Exception:
            break
        if not page:
            break
        all_rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return all_rows


def fetch_canonical_scorecard(date: str) -> list[dict]:
    """Read-only fetch from public.canonical_model_scorecards for one run_date."""
    return _sb_get(f"/canonical_model_scorecards?select=*&run_date=eq.{date}&order=race_id,model_name,rank")


def fetch_canonical_learning_events(date: str) -> list[dict]:
    """Read-only fetch from public.canonical_learning_events for one run_date."""
    return _sb_get(f"/canonical_learning_events?select=*&run_date=eq.{date}&order=race_id,model_name")


def _fmt_time(val: str | None) -> str | None:
    if not val:
        return None
    s = str(val)
    if "T" in s:
        try:
            return datetime.fromisoformat(s).strftime("%H:%M")
        except Exception:
            pass
    # RP dot notation: "2.20" = 14:20, "9.00" = 21:00 — UK racing is always PM (13:00–22:00)
    if "." in s and ":" not in s:
        try:
            parts = s.strip().split(".")
            h, m = int(parts[0]), int(parts[1][:2])
            if 1 <= h <= 9:  # 1pm–9pm
                h += 12
            return f"{h:02d}:{m:02d}"
        except Exception:
            pass
    return s[:5] if len(s) >= 5 else s


def _find_predictions_for_date(date_str: str) -> list[dict]:
    """Load predictions for a specific date, preferring date-specific JSONL."""
    # Prefer date-specific file
    specific = PRED_DIR / f"new_build_predictions_{date_str.replace('-', '_')}.jsonl"
    if specific.exists():
        rows = _read_jsonl(specific)
        if rows:
            return rows
    # Fall back to latest
    latest = PRED_DIR / "new_build_predictions_latest.jsonl"
    if latest.exists():
        rows = _read_jsonl(latest)
        return [r for r in rows if str(r.get("race_date", ""))[:10] == date_str]
    return []


def _find_live_runner_snapshots_for_date(date_str: str) -> list[dict]:
    """Read the latest full-field runner snapshot for the requested date."""
    date_tag = date_str.replace("-", "_")
    candidates = sorted(
        (ROOT / "data").glob(f"runner_snapshots_{date_tag}_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        rows = _read_jsonl(path)
        rows = [r for r in rows if str(r.get("race_date") or "")[:10] == date_str]
        if rows:
            return rows
    return []


def _find_current_card_feed_for_date(date_str: str) -> list[dict]:
    path = NEW_BUILD_ROOT / "current_cards" / "current_card_passport_feed_latest.jsonl"
    rows = _read_jsonl(path)
    return [r for r in rows if str(r.get("race_date") or "")[:10] == date_str]


def _latest_file(pattern: str) -> Path | None:
    candidates = sorted(
        ROOT.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _latest_observability(date_str: str) -> tuple[dict, Path | None]:
    date_tag = date_str.replace("-", "_")
    candidates = sorted(
        ROOT.glob(f"data/velo_run_observability_{date_tag}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    loaded = [(_load_json(path, {}) or {}, path) for path in candidates]
    for data, path in loaded:
        if data.get("persistence_status") == "OK" and data.get("race_scoring_coverage_pct") == 100.0:
            return data, path
    return loaded[0] if loaded else ({}, None)


def _load_new_build_readiness(date_str: str) -> tuple[dict, Path]:
    date_tag = date_str.replace("-", "_")
    path = REPORT_DIR / f"two_lane_readiness_{date_tag}.json"
    return (_load_json(path, {}) or {}, path)


def _load_rp_time_changes(date_str: str) -> dict[str, dict[str, str]]:
    """Compare the first RP card capture with the final refresh by race ID."""
    parsed_root = ROOT / "data" / "racing_post_account_parsed"
    initial = _load_json(parsed_root / f"live-full-racepages-{date_str}" / "racecard_injection.json", {}) or {}
    refresh = _load_json(parsed_root / f"live-full-racepages-{date_str}-refresh" / "racecard_injection.json", {}) or {}

    def _times(payload: dict) -> dict[str, str]:
        result = {}
        for race in payload.get("races") or []:
            race_id = str(race.get("race_id") or "")
            off_time = _fmt_time(race.get("off_time") or race.get("race_time"))
            if race_id and off_time:
                result[race_id] = off_time
        return result

    initial_times = _times(initial)
    refresh_times = _times(refresh)
    return {
        race_id: {"previous_off_time": initial_times[race_id], "off_time": off_time}
        for race_id, off_time in refresh_times.items()
        if race_id in initial_times and initial_times[race_id] != off_time
    }


def _passport_coverage_from_readiness(report: dict) -> float:
    scorecards = report.get("race_day_scorecards") or []
    found = 0
    total = 0
    for card in scorecards:
        raw = str(card.get("passport_coverage") or "")
        match = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", raw)
        if match:
            found += int(match.group(1))
            total += int(match.group(2))
            continue
        runner_count = int(card.get("runner_count") or 0)
        pct = card.get("passport_coverage_pct")
        if runner_count and pct is not None:
            found += round(runner_count * (float(pct) / 100.0))
            total += runner_count
    return (found / total) if total else 0.0


def _build_truth_summary(date_str: str) -> dict:
    obs, obs_path = _latest_observability(date_str)
    nb, nb_path = _load_new_build_readiness(date_str)
    sigma_summary = _load_json(ROOT / "data" / "sigma_memory" / "sigma_memory_summary.json", {}) or {}
    truth_packet = _load_json(
        ROOT / "data" / f"velo_daily_run_truth_{date_str.replace('-', '_')}.json",
        {},
    ) or {}
    shadow_lanes: dict[str, dict] = {}
    shadow_path = ROOT / "data" / "router_shadow_audit_latest.csv"
    if shadow_path.exists():
        try:
            with shadow_path.open("r", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    lane = row.get("label")
                    if lane:
                        shadow_lanes[lane] = {
                            "n": int(float(row.get("n") or 0)),
                            "strike_rate": float(row.get("sr") or 0),
                            "frame_rate": float(row.get("fr") or 0),
                            "roi": float(row.get("roi") or 0),
                            "state": row.get("lane_state") or row.get("status") or "UNKNOWN",
                        }
        except Exception:
            shadow_lanes = {}

    metrics = obs.get("metrics") or {}
    races_scored = int(metrics.get("races_processed") or nb.get("races_scored") or 0)
    runners_scored = int(metrics.get("runners_processed") or nb.get("runners_scored") or 0)
    persistence_status = obs.get("persistence_status") or "UNKNOWN"
    live_ready = bool(obs) and obs.get("race_scoring_coverage_pct") == 100.0 and persistence_status == "OK"
    nb_status = nb.get("overall_status") or "UNKNOWN"

    warnings = list(obs.get("warnings") or [])
    if obs and str(obs.get("date"))[:10] != date_str:
        warnings.append(f"Observability date mismatch: requested {date_str}, loaded {obs.get('date')}")
    if not obs:
        warnings.append(f"No Live VÉLØ observability artifact found for {date_str}")
    if not nb:
        warnings.append(f"No New Build readiness artifact found for {date_str}")
    if truth_packet.get("alert_required"):
        warnings.append(f"Truth packet alert: {truth_packet.get('status', 'UNKNOWN')}")

    sigma_status = "PASS" if sigma_summary else "UNKNOWN"
    if sigma_summary and not (ROOT / "data" / "sigma_memory" / f"sigma_memory_{date_str.replace('-', '_')}.jsonl").exists():
        sigma_status = "PENDING"

    return {
        "schema_version": "dashboard_truth_summary_v1",
        "generated_at": _utc_now(),
        "operational_date": date_str,
        "live_velo_status": "READY" if live_ready else ("UNKNOWN" if not obs else "CHECK"),
        "source_truth_label": obs.get("source_truth") or "UNKNOWN",
        "feature_health": obs.get("feature_health") or "UNKNOWN",
        "supabase_persistence_status": persistence_status,
        "supabase_readback_verified": "PASS" if persistence_status == "OK" and obs.get("supabase_write_attempt_success") else "UNKNOWN",
        "new_build_status": nb_status,
        "truth_packet_status": truth_packet.get("status", "MISSING"),
        "truth_packet_alert_required": truth_packet.get("alert_required"),
        "passport_coverage_pct": round(_passport_coverage_from_readiness(nb) * 100.0, 2),
        "intent_coverage_pct": float((nb.get("intent_coverage") or {}).get("coverage_pct") or 0.0),
        "sigma_status": sigma_status,
        "latest_sigma_sr": float(sigma_summary.get("global_sr") or 0.0),
        "shadow_lanes_status": "CURRENT_CUMULATIVE" if shadow_lanes else "MISSING",
        "shadow_lanes": shadow_lanes,
        "races_scored": races_scored,
        "runners_scored": runners_scored,
        "observability_file": str(obs_path.relative_to(ROOT)) if obs_path else None,
        "new_build_file": str(nb_path.relative_to(ROOT)),
        "stale_data_warnings": warnings,
        "guards": {
            "no_telegram_from_new_build": True,
            "new_build_paper_only": True,
            "no_staking": True,
            "rpr_archive_only": True,
        },
    }


def _build_dashboard_truth_panel(date_str: str) -> dict:
    summary = _build_truth_summary(date_str)
    obs, obs_path = _latest_observability(date_str)
    governed = _build_governed_card(date_str)
    meta = governed.get("meta") or {}
    doctrine = _load_json(ROOT / "data" / "doctrine_scorecard_latest.json", None)
    sidecar = _load_json(STATIC_DIR / "sidecar_stack_latest.json", None)
    return {
        "generated_at": _utc_now(),
        "a_supabase": {
            "status": "CONNECTED" if summary["supabase_persistence_status"] == "OK" else "UNKNOWN",
            "run_status": summary["supabase_persistence_status"],
            "verdict_count_today": summary["races_scored"],
            "latest_pipeline_run": {"started_at": obs.get("timestamp")},
            "error": None if summary["supabase_persistence_status"] == "OK" else "No OK persistence artifact for requested date",
        },
        "b_local_harness": {
            "status": "FOUND" if obs_path else "MISSING",
            "file": str(obs_path.relative_to(ROOT)) if obs_path else None,
            "data": {
                "final_status": summary["live_velo_status"],
                "feature_health": summary["feature_health"],
            } if obs_path else None,
            "error": None if obs_path else f"No observability artifact found for {date_str}",
        },
        "c_doctrine_scorecard": {
            "status": "FOUND" if doctrine else "MISSING",
            "data": doctrine,
            "error": None if doctrine else "doctrine_scorecard_latest.json not found",
        },
        "d_new_build_sidecar": {
            "status": "FOUND" if sidecar else "MISSING",
            "file": "app/static/dashboard/sidecar_stack_latest.json" if sidecar else None,
            "data": {
                "record_count": meta.get("record_count", 0),
                "date_matches_today": meta.get("requested_date") == date_str,
                "rpr_violations": meta.get("rpr_violations", 0),
            } if sidecar else None,
            "error": None if sidecar else "sidecar_stack_latest.json not found",
        },
        "meta": {
            "target_date": date_str,
            "no_scoring": True,
            "no_live_writes": True,
            "no_telegram": True,
            "no_staking": True,
            "truth_summary": summary,
        },
    }


def _load_deep_race_agent_for_date(date_str: str) -> dict[str, dict]:
    """Load deep race agent cards keyed by normalised horse name."""
    date_tag = date_str.replace("-", "_")
    for suffix in (f"{date_tag}_v1", f"{date_tag}_v2"):
        path = ROOT / "data" / "reports" / f"deep_race_agent_v1_{suffix}.json"
        if path.exists():
            data = _load_json(path, {})
            if data:
                result = {}
                for card in data.get("agent_cards") or []:
                    h = str(card.get("horse") or "").strip().lower()
                    if h:
                        result[h] = card
                return result
    return {}


def _load_old_velo_for_date(date_str: str) -> dict[str, dict]:
    """Load old VÉLØ three-option card keyed by normalised horse name."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / "reports" / f"old_velo_three_option_card_{date_tag}.json"
    data = _load_json(path, {})
    if not data:
        return {}
    result = {}
    for race in data.get("races") or []:
        for pick in race.get("picks") or []:
            h = str(pick.get("horse") or "").strip().lower()
            if not h:
                continue
            role = str(pick.get("role") or "").upper()
            existing = result.get(h, {})
            existing.setdefault("old_velo_slots", [])
            if role and role not in existing["old_velo_slots"]:
                existing["old_velo_slots"].append(role)
            if role == "WIN":
                existing["old_velo_vp"] = float(pick.get("velo_prime_prob") or 0)
            existing["old_velo_race_id"] = race.get("race_id") or existing.get("old_velo_race_id")
            existing["old_velo_off_time"] = race.get("off_time") or existing.get("old_velo_off_time")
            existing["old_velo_course"] = race.get("course") or existing.get("old_velo_course")
            existing["old_velo_tier"] = race.get("tier") or existing.get("old_velo_tier")
            result[h] = existing
    return result


def _build_governed_card_from_two_lane_readiness(date_str: str) -> dict | None:
    """Build dashboard rows from New Build two-lane readiness artifacts.

    The two-lane scorer writes race-level top-3 scorecards rather than a full
    prediction JSONL. This adapter joins those top-3 scores back onto the
    current-card feed so the UI can show real New Build reads plus full runner
    counts without falling through to Old VÉLØ snapshots.
    """
    report, report_path = _load_new_build_readiness(date_str)
    scorecards = report.get("race_day_scorecards") or []
    feed_rows = _find_current_card_feed_for_date(date_str)
    if not scorecards or not feed_rows:
        return None

    score_by_race_horse: dict[tuple[str, str], dict] = {}
    race_meta: dict[str, dict] = {}
    time_changes = _load_rp_time_changes(date_str)
    for card in scorecards:
        race_id = str(card.get("race_id") or "")
        race_meta[race_id] = card
        for pick in card.get("lane_a_top3") or []:
            horse_key = str(pick.get("horse") or "").strip().lower()
            if horse_key:
                score_by_race_horse[(race_id, horse_key)] = pick

    shadow_map = _load_radical_shadow_for_date(date_str)
    deep_agent_map = _load_deep_race_agent_for_date(date_str)
    old_velo_map = _load_old_velo_for_date(date_str)

    verdicts = []
    for row in feed_rows:
        race_id = str(row.get("race_id") or "")
        horse = str(row.get("horse") or "")
        horse_key = horse.strip().lower()
        pick = score_by_race_horse.get((race_id, horse_key), {})
        card = race_meta.get(race_id, {})
        prob = float(pick.get("prob") or 0.0)
        rank = int(pick.get("rank") or 99)
        passport_found = bool(row.get("passport_found"))
        reason_codes = list(row.get("reason_codes") or [])
        if row.get("missing_reason"):
            reason_codes.append(str(row.get("missing_reason")))

        sh_race = shadow_map.get(race_id, {})
        # shadow is per top-pick horse — only attach if this runner IS that horse
        sh = sh_race if (sh_race.get("horse") or "").strip().lower() == horse_key else {}
        radical = sh.get("radical", {})
        sh_passport = sh.get("passport", {})

        da = deep_agent_map.get(horse_key, {})
        da_agent = da.get("agent") or {}
        da_evidence = da.get("evidence") or {}

        ov = old_velo_map.get(horse_key, {})

        verdicts.append({
            "race_id": race_id,
            "horse": horse,
            "horse_id": str(row.get("rp_uid") or ""),
            "course": row.get("course") or "",
            "off_time": row.get("off_time"),
            "previous_off_time": (time_changes.get(race_id) or {}).get("previous_off_time"),
            "time_changed": race_id in time_changes,
            "race_name": row.get("race_title") or card.get("race_title") or "",
            "date": date_str,
            "rank": rank,
            "champion_rank": rank,
            "champion_probability": prob,
            "velo_prime_prob": prob,
            "market_deception_score": 0.0,
            "improvement_score": 0.0,
            "place_prob": 0.0,
            "assigned_product": "NEW_BUILD_PAPER_ONLY",
            "router_reasons": ["PAPER_ONLY", "NO_STAKING", "NO_TELEGRAM", "NO_LIVE_WRITE"],
            "execution_allowed": False,
            "candidate_execution_allowed": False,
            "passport_found": passport_found,
            "new_build_lane": report.get("operational_lane") or "LANE_A_CORE_PASSPORT",
            "nb_decision_lane": pick.get("nb_decision_lane") or card.get("top_pick_lane"),
            "reason_codes": reason_codes,
            "stack_badges": ["NEW_BUILD_PAPER", "CORE_PASSPORT"] + (["PASSPORT"] if passport_found else []),
            "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
            "rp_rpr_velo_allowed": False,
            "missing_metadata": not (row.get("course") and row.get("off_time") and horse),
            "metadata_complete": bool(row.get("course") and row.get("off_time") and horse),
            "paper_only": True,
            # Radical Shadow (Win + Frame gate)
            "shadow_action": radical.get("action"),
            "shadow_confidence": radical.get("confidence"),
            "shadow_win_gate_probability": sh.get("win_gate_probability"),
            "shadow_frame_gate_probability": sh.get("frame_gate_probability"),
            "shadow_passport_available": sh_passport.get("passport_available"),
            "shadow_warnings": radical.get("warnings") or [],
            "shadow_reasons": radical.get("reasons") or [],
            # Deep Race Agent (champion layer)
            "deep_agent_verdict": da_agent.get("agent_verdict"),
            "deep_agent_gate": da_agent.get("gate"),
            "deep_agent_identity": (da_evidence.get("identity") or {}).get("overall_confidence"),
            "deep_agent_support_score": da_agent.get("support_score"),
            "deep_agent_risk_score": da_agent.get("risk_score"),
            "deep_agent_support_tags": da.get("support_tags") or da_agent.get("support_tags") or [],
            "deep_agent_risk_tags": da.get("risk_tags") or da_agent.get("risk_tags") or [],
            "deep_agent_danger_horses": da.get("danger_horses") or [],
            # Old VÉLØ
            "old_velo_slots": ov.get("old_velo_slots") or [],
            "old_velo_vp": ov.get("old_velo_vp"),
        })

    verdicts.sort(key=lambda x: (x.get("off_time") or "", x.get("course") or "", x.get("rank") or 99))
    meta_complete = sum(1 for v in verdicts if v["metadata_complete"])
    return {
        "meta": {
            "status": "NEW_BUILD_TWO_LANE_READY",
            "requested_date": date_str,
            "loaded_date": date_str,
            "source": "new_build_two_lane_readiness",
            "message": "New Build paper-only two-lane readiness joined to current-card feed.",
            "allow_fallback": False,
            "date_match": True,
            "stale_data_blocked": False,
            "governed_card_loaded_date": date_str,
            "governed_card_status": "NEW_BUILD_PAPER_READY",
            "sidecar_loaded_date": date_str,
            "sidecar_status": "NEW_BUILD_TWO_LANE",
            "sidecar_date_match": True,
            "cashrun_loaded_date": None,
            "cashrun_status": "UNAVAILABLE_NEW_BUILD_PAPER",
            "cashrun_counts": {},
            "metadata_coverage": round(meta_complete / len(verdicts), 4) if verdicts else 0.0,
            "commit_sha": "new_build_two_lane",
            "router_version": "New Build Two-Lane Paper Router v1",
            "record_count": len(verdicts),
            "date_mismatch": False,
            "gov_overlay": False,
            "exact_date_file_present": True,
            "new_build_paper_only": True,
            "champion_version": "Core_V0_OR_Passport",
            "classification": report.get("overall_status", "NEW_BUILD_PAPER_READY"),
            "rpr_violations": report.get("rpr_violations", 0),
            "passport_coverage_pct": _passport_coverage_from_readiness(report),
            "intent_coverage": report.get("intent_coverage", {}),
            "races": report.get("races_scored", len({v["race_id"] for v in verdicts})),
            "runners": report.get("runners_scored", len(verdicts)),
            "readiness_file": str(report_path.relative_to(ROOT)),
            "time_changes": time_changes,
        },
        "cashrun": {
            "status": "UNAVAILABLE_NEW_BUILD_PAPER",
            "loaded_date": None,
            "counts": {},
            "rows": [],
        },
        "verdicts": verdicts,
    }


def _load_radical_shadow_for_date(date_str: str) -> dict:
    """Load radical shadow report keyed by race_id → decision dict."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / "reports" / f"radical_shadow_{date_tag}.json"
    data = _load_json(path, {})
    if not data:
        return {}
    decisions = data.get("decisions", [])
    return {str(d["race_id"]): d for d in decisions if d.get("race_id")}


def _build_no_rpr_race_map(rows: list[dict]) -> dict:
    """Build race_id → {top_horse, top_prob} from sqpe_no_rpr_shadow_prob in snapshot rows."""
    race_probs: dict[str, list[tuple[float, str]]] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        horse = row.get("horse") or ""
        prob = float(row.get("sqpe_no_rpr_shadow_prob") or 0.0)
        if rid and horse and prob > 0:
            race_probs.setdefault(rid, []).append((prob, horse))
    result = {}
    for rid, pairs in race_probs.items():
        pairs.sort(reverse=True)
        top_prob, top_horse = pairs[0]
        result[rid] = {"top_horse": top_horse, "top_prob": top_prob}
    return result


_COURSE_ABBR = {
    "Curragh": "CUR", "Uttoxeter": "UTT", "Cartmel": "CRT",
    "Wolverhampton": "WOL", "Wolverhampton (AW)": "WOL",
    "Kempton": "KEM", "Kempton (AW)": "KEM",
    "Chelmsford": "CHE", "Chelmsford City": "CHE",
    "Lingfield": "LIN", "Lingfield (AW)": "LIN",
    "Southwell": "SOW", "Southwell (AW)": "SOW",
    "Newcastle": "NCS", "Newcastle (AW)": "NCS",
    "Dundalk": "DUN", "Dundalk (AW)": "DUN",
    "Tramore": "TRM", "Brighton": "BRI", "Pontefract": "PON",
    "Newmarket": "NMK", "Newmarket (July)": "NMK", "Newmarket (Rowley Mile)": "NMK",
    "Worcester": "WOR", "Cork": "COR", "Chester": "CHS",
    "Kilbeggan": "KLB", "Ascot": "ASC", "York": "YOR",
    "Downpatrick": "DPT", "Killarney": "KLN",
}


def _load_injection_numeric_to_velo_race_id(date_str: str) -> dict[str, str]:
    """Map RP numeric race_id (used by New Build) → rp_CRS_YYYYMMDD_H.MM (used by Live VÉLØ).

    New Build's two-lane readiness keys races by the raw RP numeric race_id.
    Live VÉLØ verdicts/snapshots key races by rp_{course}_{date}_{dot_time}.
    Without this bridge the two never join and New Build always reads empty.
    """
    date_tag = date_str.replace("-", "_")
    mapping: dict[str, str] = {}
    inj_matches = sorted((ROOT / "data" / "racing_post_account_parsed").glob(
        f"*{date_str}*/racecard_injection.json"
    )) + sorted((ROOT / "data" / "racing_post_account_parsed").glob(
        f"*{date_tag}*/racecard_injection.json"
    ))
    if not inj_matches:
        return mapping
    inj = _load_json(inj_matches[-1], {})
    for race in (inj.get("races") or []):
        num = str(race.get("race_id", ""))
        if not num:
            continue
        course_full = race.get("course", "")
        course_code = _COURSE_ABBR.get(course_full, course_full[:3].upper())
        off_raw = race.get("off_time", "")
        if ":" in off_raw:
            h, m = map(int, off_raw.split(":"))
            if h >= 13:
                h -= 12
            dot = f"{h}.{m:02d}"
        else:
            dot = off_raw
        mapping[num] = f"rp_{course_code}_{date_str.replace('-', '')}_{dot}"
    return mapping


def _build_governed_card_from_live_snapshots(date_str: str) -> dict | None:
    """Serve the official local Live VÉLØ runner snapshot in dashboard shape.

    Read-only bridge for the dashboard UI. Does not score, persist, notify,
    stake, or mutate Live VÉLØ.
    """
    rows = _find_live_runner_snapshots_for_date(date_str)
    if not rows:
        return None

    # Pre-build No-RPR top pick per race and shadow decisions
    no_rpr_map = _build_no_rpr_race_map(rows)
    shadow_map = _load_radical_shadow_for_date(date_str)
    deep_agent_map = _load_deep_race_agent_for_date(date_str)
    old_velo_map = _load_old_velo_for_date(date_str)

    # Load New Build two-lane Lane A top3 per race
    #
    # No numeric_to_velo remap here (2026-07-18 fix): New Build's own
    # race_day_scorecards use plain RP numeric race_id, and so do these live
    # runner snapshot rows (`row.get("race_id")` below) -- they match directly,
    # 60/60 confirmed. Remapping numeric->rp_COURSE_DATE_TIME here (that scheme
    # only applies to /api/model-suggestions's CHAMPION_INTENT_SHADOW rows, per
    # the frontend's own comment on this exact confusion) silently broke the
    # join 100% of the time, showing "No New Build data for this date" every
    # single day regardless of whether New Build actually ran.
    tl_data, _ = _load_new_build_readiness(date_str)
    nb_lane_a_map: dict[str, dict] = {}
    for card in tl_data.get("race_day_scorecards", []):
        rid = str(card.get("race_id") or "")
        if not rid:
            continue
        lane_a_top3 = sorted(card.get("lane_a_top3") or [], key=lambda x: x.get("rank", 99))
        nb_lane_a_map[rid] = {
            "top3": [{"horse": p.get("horse"), "rank": p.get("rank"), "prob": p.get("prob") or p.get("lane_a_prob"), "nb_decision_lane": p.get("nb_decision_lane")} for p in lane_a_top3[:3]],
            "runner_count": card.get("runner_count"),
            "passport_coverage": card.get("passport_coverage"),
        }

    verdicts = []
    for row in rows:
        prob = float(row.get("velo_prime_prob") or 0.0)
        mds = float(row.get("market_deception_score") or 0.0)
        improvement = float(row.get("improvement_score") or 0.0)
        place_prob = float(row.get("place_prob") or 0.0)
        assigned_product = row.get("assigned_product") or "PASS"
        tier = row.get("tier") or ""
        off_time = _fmt_time(row.get("off_time"))
        metadata_complete = bool(row.get("course") and off_time and row.get("horse"))
        badges = []
        if tier == "A":
            badges.append("TIER_A")
        if prob >= 0.30:
            badges.append("VP30")
        if mds >= 0.50:
            badges.append("MDS_HIGH")
        if improvement >= 0.40:
            badges.append("IMPROVE_HIGH")
        if place_prob >= 0.80:
            badges.append("PLACE_PROB_HIGH")

        rid = str(row.get("race_id") or "")
        horse_key_snap = str(row.get("horse") or "").strip().lower()
        nr = no_rpr_map.get(rid, {})
        sh_race_snap = shadow_map.get(rid, {})
        sh = sh_race_snap if (sh_race_snap.get("horse") or "").strip().lower() == horse_key_snap else {}
        nb = nb_lane_a_map.get(rid, {})
        radical = sh.get("radical", {})
        sh_passport = sh.get("passport", {})
        da_snap = deep_agent_map.get(horse_key_snap, {})
        da_agent_snap = da_snap.get("agent") or {}
        da_evidence_snap = da_snap.get("evidence") or {}
        ov_snap = old_velo_map.get(horse_key_snap, {})

        verdicts.append({
            "race_id": rid,
            "horse": row.get("horse") or "",
            "horse_id": str(row.get("horse_id") or ""),
            "course": row.get("course") or "",
            "off_time": off_time,
            "race_name": "",
            "date": date_str,
            "rank": row.get("rank"),
            "top_pick_name": row.get("top_pick_name"),
            "top_pick_vp": row.get("top_pick_vp"),
            "velo_prime_prob": prob,
            "sqpe_v17_prob": row.get("sqpe_v17_prob"),
            "sqpe_no_rpr_shadow_prob": row.get("sqpe_no_rpr_shadow_prob"),
            "place_prob": place_prob,
            "market_deception_score": mds,
            "improvement_score": improvement,
            "longshot_prob": row.get("longshot_prob"),
            "release_day_prob": row.get("release_day_prob"),
            "comment_intel_score": row.get("comment_intel_score"),
            "archetype_label": row.get("race_archetype") or "",
            "archetype_confidence": row.get("archetype_confidence") or "",
            "assigned_product": assigned_product,
            "router_reasons": row.get("router_reasons") or [],
            "execution_allowed": bool(row.get("execution_allowed")),
            "candidate_execution_allowed": False,
            "passport_found": None,
            "new_build_lane": None,
            "reason_codes": row.get("rpd_evidence_codes") or [],
            "stack_badges": badges,
            "rpr_policy": "LIVE_LEGACY_ACCEPTED_POLICY",
            "rp_rpr_velo_allowed": False,
            "missing_metadata": not metadata_complete,
            "metadata_complete": metadata_complete,
            "vp30": prob >= 0.30,
            "mds_high": mds >= 0.50,
            "improve_high": improvement >= 0.40,
            "cash_run_flag": bool(row.get("cash_run_flag")),
            "setup_run_flag": bool(row.get("setup_run_flag")),
            "operator_read_profile": "LIVE_VELO_LOCAL_SNAPSHOT",
            "operator_skepticism_flags": [],
            "signal_stack": row.get("active_components") or [],
            "rp_flatline_warning": False,
            "trust_policy": "LIVE_VERDICT_READ_ONLY_DASHBOARD",
            "paper_only": False,
            # New Build two-lane Lane A (top3 per race on all runner rows)
            "new_build_top3": nb.get("top3") or [],
            "new_build_runner_count": nb.get("runner_count"),
            "new_build_passport_coverage": nb.get("passport_coverage"),
            # No-RPR shadow (top pick per race, on all runner rows)
            "no_rpr_top_horse": nr.get("top_horse"),
            "no_rpr_top_prob": nr.get("top_prob"),
            # Radical shadow lane
            "shadow_action": radical.get("action"),
            "shadow_confidence": radical.get("confidence"),
            "shadow_win_gate_probability": sh.get("win_gate_probability"),
            "shadow_frame_gate_probability": sh.get("frame_gate_probability"),
            "shadow_passport_available": sh_passport.get("passport_available"),
            "shadow_warnings": radical.get("warnings") or [],
            "shadow_reasons": radical.get("reasons") or [],
            # Deep Race Agent (champion layer)
            "deep_agent_verdict": da_agent_snap.get("agent_verdict"),
            "deep_agent_gate": da_agent_snap.get("gate"),
            "deep_agent_identity": (da_evidence_snap.get("identity") or {}).get("overall_confidence"),
            "deep_agent_support_score": da_agent_snap.get("support_score"),
            "deep_agent_risk_score": da_agent_snap.get("risk_score"),
            "deep_agent_support_tags": da_snap.get("support_tags") or da_agent_snap.get("support_tags") or [],
            "deep_agent_risk_tags": da_snap.get("risk_tags") or da_agent_snap.get("risk_tags") or [],
            "deep_agent_danger_horses": da_snap.get("danger_horses") or [],
            # Old VÉLØ
            "old_velo_slots": ov_snap.get("old_velo_slots") or [],
            "old_velo_vp": ov_snap.get("old_velo_vp"),
            "old_velo_tier": ov_snap.get("old_velo_tier"),
        })

    verdicts.sort(key=lambda x: (x.get("off_time") or "", x.get("course") or "", x.get("rank") or 99))
    meta_complete = sum(1 for v in verdicts if v["metadata_complete"])
    race_count = len({v["race_id"] for v in verdicts})
    return {
        "meta": {
            "status": "LIVE_LOCAL_SNAPSHOT_READY",
            "requested_date": date_str,
            "loaded_date": date_str,
            "source": "local_json_exact",
            "message": "Official Live VÉLØ local runner snapshot. Read-only dashboard bridge.",
            "allow_fallback": False,
            "date_match": True,
            "stale_data_blocked": False,
            "governed_card_loaded_date": date_str,
            "governed_card_status": "PASS_EXACT_DATE",
            "sidecar_loaded_date": date_str,
            "sidecar_status": "LIVE_LOCAL_SNAPSHOT",
            "sidecar_date_match": True,
            "cashrun_loaded_date": None,
            "cashrun_status": "UNAVAILABLE_DASHBOARD_READ_ONLY",
            "cashrun_counts": {},
            "metadata_coverage": round(meta_complete / len(verdicts), 4) if verdicts else 0.0,
            "commit_sha": rows[0].get("run_id", "local_snapshot"),
            "router_version": "ProductRouter v1",
            "record_count": len(verdicts),
            "date_mismatch": False,
            "gov_overlay": False,
            "exact_date_file_present": True,
            "new_build_paper_only": False,
            "classification": "LIVE_LOCAL_SNAPSHOT_DASHBOARD_READY",
            "rpr_violations": 0,
            "races": race_count,
            "runners": len(verdicts),
        },
        "cashrun": {
            "status": "UNAVAILABLE_DASHBOARD_READ_ONLY",
            "loaded_date": None,
            "counts": {},
            "rows": [],
        },
        "verdicts": verdicts,
    }


def _build_governed_card(date_str: str) -> dict:
    """Build governed-card API response from New Build artifacts only."""
    preds = _find_predictions_for_date(date_str)

    # Try race-day report for metadata
    report_path = REPORT_DIR / f"new_build_race_day_{date_str.replace('-', '_')}_latest.json"
    report = _load_json(report_path, {})
    feed = report.get("current_card_feed", {}) if report else {}

    if not preds:
        # Live snapshot is richer (has VP, MDS, improvement, No-RPR, shadow) — try first
        live_snapshot = _build_governed_card_from_live_snapshots(date_str)
        if live_snapshot:
            return live_snapshot
        two_lane = _build_governed_card_from_two_lane_readiness(date_str)
        if two_lane:
            return two_lane
        return {
            "meta": {
                "status": "NO_DATA",
                "requested_date": date_str,
                "loaded_date": None,
                "source": "new_build_paper_only",
                "message": f"No predictions found for {date_str}. Run two-lane scorer first.",
                "date_match": False,
                "governed_card_status": "NO_DATA",
                "new_build_paper_only": True,
                "record_count": 0,
            },
            "cashrun": {"status": "UNAVAILABLE", "rows": []},
            "verdicts": [],
        }

    # Build verdicts in governed-card shape
    verdicts = []
    for row in preds:
        prob = float(row.get("champion_probability") or 0.0)
        rank = int(row.get("champion_rank") or 99)
        passport = bool(row.get("passport_found"))
        off_time = _fmt_time(row.get("off_time"))
        verdicts.append({
            "race_id": str(row.get("race_id") or ""),
            "horse": row.get("horse") or "",
            "horse_id": str(row.get("rp_uid") or ""),
            "course": row.get("course") or "",
            "off_time": off_time,
            "race_name": row.get("race_title") or "",
            "date": date_str,
            "velo_prime_prob": prob,
            "champion_probability": prob,
            "champion_rank": rank,
            "place_prob": 0.0,
            "market_deception_score": 0.0,
            "improvement_score": 0.0,
            "archetype_label": "",
            "assigned_product": "NEW_BUILD_PAPER_ONLY",
            "router_reasons": [
                "NEW_BUILD_PAPER_ONLY",
                "NO_STAKING",
                "NO_TELEGRAM",
                "NO_LIVE_WRITE",
                "INTENT_UNAVAILABLE_TODAY",
            ],
            "execution_allowed": False,
            "candidate_execution_allowed": False,
            "passport_found": passport,
            "passport_strength_score": row.get("passport_strength_score"),
            "new_build_lane": "CORE_V0_OR_PASSPORT",
            "reason_codes": row.get("reason_codes") or [],
            "stack_badges": ["NEW_BUILD_PAPER", "CORE_PASSPORT"] + (["PASSPORT"] if passport else ["NO_PASSPORT"]),
            "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
            "rp_rpr_velo_allowed": False,
            "missing_metadata": not (row.get("course") and off_time and row.get("horse")),
            "metadata_complete": bool(row.get("course") and off_time and row.get("horse")),
            "vp30": prob >= 0.30,
            "mds_high": False,
            "improve_high": False,
            "cash_run_flag": False,
            "operator_read_profile": "NEW_BUILD_PAPER",
            "operator_skepticism_flags": [],
            "signal_stack": [],
            "rp_flatline_warning": False,
            "feature_missing_filled_from_median": row.get("feature_missing_filled_from_median") or [],
            "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
            "paper_only": True,
        })

    verdicts.sort(key=lambda x: (x.get("off_time") or "", x.get("course") or ""))
    meta_complete = sum(1 for v in verdicts if v["metadata_complete"])
    pp_cov = feed.get("passport_coverage", {})

    return {
        "meta": {
            "status": "NEW_BUILD_PAPER_READY",
            "requested_date": date_str,
            "loaded_date": date_str,
            "source": "new_build_paper_predictions",
            "message": "New Build paper-only. No Live VÉLØ, no Telegram, no staking.",
            "allow_fallback": False,
            "date_match": True,
            "stale_data_blocked": False,
            "governed_card_loaded_date": date_str,
            "governed_card_status": "NEW_BUILD_PAPER_READY",
            "sidecar_loaded_date": date_str,
            "sidecar_status": "NEW_BUILD_SIDECAR",
            "sidecar_date_match": True,
            "cashrun_loaded_date": None,
            "cashrun_status": "UNAVAILABLE_NEW_BUILD_PAPER",
            "cashrun_counts": {},
            "metadata_coverage": round(meta_complete / len(verdicts), 4) if verdicts else 0.0,
            "commit_sha": "new_build_paper",
            "router_version": "New Build Paper Router v1",
            "record_count": len(verdicts),
            "date_mismatch": False,
            "gov_overlay": False,
            "exact_date_file_present": True,
            "new_build_paper_only": True,
            "champion_version": report.get("champion_version", "Challenger_V1"),
            "classification": report.get("classification", "NEW_BUILD_PAPER_READY_NO_INTENT"),
            "rpr_violations": report.get("rpr_violations", 0),
            "passport_coverage": pp_cov,
            "intent_coverage": report.get("intent_current_card_coverage", {}),
            "races": report.get("race_count", len({v["race_id"] for v in verdicts})),
            "runners": len(verdicts),
        },
        "cashrun": {
            "status": "UNAVAILABLE_NEW_BUILD_PAPER",
            "loaded_date": None,
            "counts": {},
            "rows": [],
        },
        "verdicts": verdicts,
    }


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/sidecar_stack_latest.json")
async def sidecar():
    path = STATIC_DIR / "sidecar_stack_latest.json"
    data = _load_json(path, {"status": "NOT_FOUND"})
    return JSONResponse(data)


@app.get("/api/governed-card")
async def governed_card(date: str = Query(default=None), allow_fallback: bool = Query(default=False)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = _build_governed_card(target)
    return JSONResponse(result)


@app.get("/api/dashboard/truth-summary")
async def dashboard_truth_summary(date: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return JSONResponse(_build_truth_summary(target))


@app.get("/api/dashboard-truth")
async def dashboard_truth(date: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return JSONResponse(_build_dashboard_truth_panel(target))


@app.get("/api/doctrine-scorecard")
async def doctrine_scorecard():
    path = ROOT / "data" / "doctrine_scorecard_latest.json"
    data = _load_json(path)
    if data is None:
        return JSONResponse(
            {
                "status": "NOT_FOUND",
                "message": "doctrine_scorecard_latest.json not found — run build_doctrine_market_scorecard.py first",
                "generated_at": _utc_now(),
                "no_scoring": True,
                "no_model_calls": True,
                "no_live_writes": True,
            },
            status_code=404,
        )
    return JSONResponse(data)


def _find_old_velo_verdicts_for_date(date_str: str) -> list[dict]:
    """Read velo_prime_verdicts_{date_tag}.json and return flat list."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
    if not path.exists():
        return []
    raw = _load_json(path, [])
    if not isinstance(raw, list):
        return []
    result = []
    for verdict in raw:
        top = verdict.get("top") or {}
        result.append({
            "race_id": verdict.get("race_id") or "",
            "course": verdict.get("course") or "",
            "off_time": verdict.get("off_time") or "",
            "race_name": verdict.get("race_name") or "",
            "tier": verdict.get("tier") or "",
            "horse": top.get("horse") or "",
            "velo_prime_prob": float(top.get("velo_prime_prob") or 0),
            "market_deception_score": float(top.get("market_deception_score") or 0),
            "improvement_score": float(top.get("improvement_score") or 0),
            "place_prob": float(top.get("place_prob") or 0),
            "prob_gap": float(top.get("prob_gap") or 0),
            "confidence_level": top.get("confidence_level") or "low",
            "assigned_product": verdict.get("product") or "",
            "router_reasons": top.get("reasons") or [],
        })
    return result


@app.get("/api/old-velo-verdicts")
async def old_velo_verdicts(date: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = _find_old_velo_verdicts_for_date(target)
    return JSONResponse({
        "date": target,
        "source": "velo_prime_verdicts_local",
        "count": len(rows),
        "verdicts": rows,
    })


@app.get("/api/canonical-scorecard")
async def canonical_scorecard(date: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = fetch_canonical_scorecard(target)
    return JSONResponse({
        "date": target,
        "source_table": "public.canonical_model_scorecards",
        "count": len(rows),
        "rows": rows,
        "no_supabase_write": True,
    })


@app.get("/api/canonical-learning-events")
async def canonical_learning_events(date: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = fetch_canonical_learning_events(target)
    return JSONResponse({
        "date": target,
        "source_table": "public.canonical_learning_events",
        "count": len(rows),
        "rows": rows,
        "no_supabase_write": True,
    })


@app.get("/api/canonical-race-truth")
async def canonical_race_truth(date: str = Query(default=None), race_id: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not race_id:
        return JSONResponse({"status": "ERROR", "message": "race_id is required"}, status_code=400)
    scorecard_rows = [r for r in fetch_canonical_scorecard(target) if r.get("race_id") == race_id]
    learning_rows = [r for r in fetch_canonical_learning_events(target) if r.get("race_id") == race_id]
    return JSONResponse({
        "date": target,
        "race_id": race_id,
        "source_tables": ["public.canonical_model_scorecards", "public.canonical_learning_events"],
        "scorecard_count": len(scorecard_rows),
        "learning_event_count": len(learning_rows),
        "scorecard_rows": scorecard_rows,
        "learning_events": learning_rows,
        "no_supabase_write": True,
    })


def _remap_numeric_race_ids(payload: dict, date_str: str) -> dict:
    """New Build / Champion Intent Shadow lanes key rows by RP's raw numeric
    race_id; every other lane (and the dashboard's own race grouping) uses
    rp_{course}_{date}_{dot_time}. Without this, those lanes never join to
    a race in the UI regardless of date."""
    numeric_to_velo = _load_injection_numeric_to_velo_race_id(date_str)
    if not numeric_to_velo:
        return payload
    for row in payload.get("rows", []) or []:
        rid = str(row.get("race_id") or "")
        if rid in numeric_to_velo:
            row["race_id"] = numeric_to_velo[rid]
    return payload


@app.get("/api/model-suggestions")
async def model_suggestions(date: str = Query(default=None)):
    """Read-only, current-day pre-race suggestions across all model lanes.

    Never scores, trains, promotes, stakes, or writes anywhere — joins
    whatever artifacts already exist on disk. Missing lanes are reported as
    MISSING_ARTIFACT with their expected source_path, never silently
    dropped. This is CURRENT_DAY_RUNTIME_SUGGESTION_NOT_RESULT_TRUTH, not
    canonical post-race truth — use /api/canonical-scorecard for that once
    results are in.
    """
    from scripts.ops.model_suggestions_builder import build_model_suggestions
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return JSONResponse(_remap_numeric_race_ids(build_model_suggestions(target), target))


@app.get("/api/model-suggestions-race")
async def model_suggestions_race(date: str = Query(default=None), race_id: str = Query(default=None)):
    """Same as /api/model-suggestions, filtered to a single race_id."""
    from scripts.ops.model_suggestions_builder import build_model_suggestions
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not race_id:
        return JSONResponse({"status": "ERROR", "message": "race_id is required"}, status_code=400)
    return JSONResponse(build_model_suggestions(target, race_id=race_id))


def _load_agent_verdicts_for_date(date_str: str) -> dict[str, dict]:
    """race_id|normalized_horse -> agent card, from Deep Race Agent V1's dated
    report. Best-effort: returns {} if the report hasn't run for this date."""
    path = ROOT / "data" / "reports" / f"deep_race_agent_v1_{date_str.replace('-', '_')}_v2.json"
    data = _load_json(path, {})
    out: dict[str, dict] = {}
    for card in data.get("agent_cards", []) if isinstance(data, dict) else []:
        horse_key = re.sub(r"[^a-z0-9]", "", str(card.get("horse", "")).lower())
        race_id = str(card.get("race_id") or "")
        out[f"{race_id}|{horse_key}"] = card.get("agent", {})
    return out


@app.get("/api/plot-conviction")
async def plot_conviction(date: str = Query(default=None)):
    """RP PDF ratings-sheet high-conviction picks (postdata_score / plot_conviction),
    read straight from racecard_merged, enriched with Deep Race Agent's verdict
    where that report has run for the date. Read-only -- joins whatever's on
    disk, never scores/writes. Wired 2026-07-18 alongside the postdata_score/
    plot_conviction -> verdict logic in build_deep_race_agent_v1.py; this panel
    is how the operator actually sees which horses those PDF signals fired on.
    """
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    agent_verdicts = _load_agent_verdicts_for_date(target)

    picks: list[dict] = []
    for path in sorted((ROOT / "data" / "racecard_merged").glob(f"racecard_*_{target}.json")):
        payload = _load_json(path, {})
        races = payload.get("races") if isinstance(payload, dict) else None
        if not isinstance(races, dict):
            continue
        venue = payload.get("venue")
        for race_key, race in races.items():
            if not isinstance(race, dict):
                continue
            race_id = str(race.get("race_id") or "")
            off_time = race.get("off") or race.get("off_time") or race_key
            for h in race.get("horses") or []:
                if not isinstance(h, dict):
                    continue
                postdata_score = h.get("postdata_score")
                plot_conv = h.get("plot_conviction")
                # Deliberately tighter than _agent_judgement's 0.3/0.7 thresholds
                # (which just need to move a verdict) -- this panel is a visual
                # shortlist for the operator, so the bar is "genuinely strong",
                # not "any signal at all".
                strong_postdata = isinstance(postdata_score, (int, float)) and abs(postdata_score) >= 0.5
                strong_plot = isinstance(plot_conv, (int, float)) and plot_conv >= 0.7
                if not (strong_postdata or strong_plot):
                    continue
                horse_key = re.sub(r"[^a-z0-9]", "", str(h.get("horse_name", "")).lower())
                agent = agent_verdicts.get(f"{race_id}|{horse_key}", {})
                picks.append({
                    "venue": venue,
                    "off_time": off_time,
                    "race_id": race_id,
                    "horse": h.get("horse_name"),
                    "postdata_score": postdata_score,
                    "plot_conviction": plot_conv,
                    "spotlight_comment": h.get("spotlight_comment"),
                    "agent_verdict": agent.get("agent_verdict"),
                    "support_score": agent.get("support_score"),
                    "risk_score": agent.get("risk_score"),
                })

    picks.sort(key=lambda p: (p.get("plot_conviction") or 0) + abs(p.get("postdata_score") or 0), reverse=True)
    total_found = len(picks)
    picks = picks[:30]
    return JSONResponse({
        "date": target,
        "source": "racecard_merged (PDF ratings-sheet fields) + deep_race_agent_v1 verdict join",
        "thresholds": {"postdata_score_abs_gte": 0.5, "plot_conviction_gte": 0.7},
        "total_found": total_found,
        "count": len(picks),
        "picks": picks,
    })


@app.get("/old_velo_three_option_card_latest.json", include_in_schema=False)
async def old_velo_three_option_card():
    """Serve the Old VELO WIN/PLACE/LONGSHOT operator card for the dashboard.

    Ported from app/main.py 2026-07-18 -- that route existed in production
    but was never added here, so this (local dev) server 404'd on the exact
    path the frontend fetches, and the WIN/PLACE/LONGSHOT lane silently
    showed nothing regardless of whether Step 9.6 had actually run. Same
    recurring pattern as the /api/plot-conviction and /api/model-suggestions
    parity gaps between these two servers.
    """
    card_path = ROOT / "data" / "reports" / "old_velo_three_option_card_latest.json"
    if not card_path.exists():
        raise HTTPException(status_code=404, detail="Three-option card not found")
    return FileResponse(str(card_path), media_type="application/json")


@app.get("/api/deep-race-agent")
async def deep_race_agent(date: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_tag = target.replace("-", "_")
    # prefer _v1 then _v2
    for suffix in (f"{date_tag}_v1", f"{date_tag}_v2"):
        path = ROOT / "data" / "reports" / f"deep_race_agent_v1_{suffix}.json"
        if path.exists():
            data = _load_json(path, {})
            if data:
                cards = data.get("agent_cards") or []
                upgrade = [c for c in cards if (c.get("agent") or {}).get("agent_verdict") == "UPGRADE_CANDIDATE_REVIEW"]
                watch = [c for c in cards if (c.get("agent") or {}).get("agent_verdict") == "WATCH_ONLY"]
                support = [c for c in cards if (c.get("agent") or {}).get("agent_verdict") == "PASS_WITH_SUPPORT_REVIEW"]
                return JSONResponse({
                    "date": target,
                    "status": "OK",
                    "source": str(path),
                    "generated_at": data.get("generated_at"),
                    "summary": data.get("summary") or {},
                    "upgrade_candidates": upgrade,
                    "watch_only": watch,
                    "pass_with_support": support,
                    "all_cards": cards,
                })
    return JSONResponse({"date": target, "status": "NOT_RUN", "upgrade_candidates": [], "watch_only": [], "pass_with_support": [], "all_cards": []}, status_code=200)


@app.get("/api/radical-shadow")
async def radical_shadow(date: str = Query(default=None)):
    target = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_tag = target.replace("-", "_")
    path = ROOT / "data" / "reports" / f"radical_shadow_{date_tag}.json"
    data = _load_json(path, {})
    if not data:
        return JSONResponse({"date": target, "status": "NOT_RUN", "decisions": []})
    decisions = data.get("decisions") or []
    top = sorted([d for d in decisions if d.get("decision") in ("WIN_CANDIDATE_SHADOW", "CASH_RUN")],
                 key=lambda x: float(x.get("win_gate") or 0), reverse=True)
    return JSONResponse({
        "date": target,
        "status": "OK",
        "generated_at": data.get("generated_at"),
        "summary": data.get("decision_counts") or {},
        "top_picks": top,
        "all_decisions": decisions,
    })


@app.get("/api/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "mode": "new_build_paper_only",
        "generated_at": _utc_now(),
        "old_live_velo_touched": False,
        "shadow_touched": False,
        "telegram_sent": False,
        "staking": False,
    })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()
    print(f"Starting New Build paper-only dashboard on {args.host}:{args.port}")
    print("  GET /dashboard           - New Build paper dashboard")
    print("  GET /api/governed-card   - New Build verdicts (no Live VELO, no staking)")
    print("  GET /api/health          - health check")
    print("  Old Live VELO: UNTOUCHED | Shadow: UNTOUCHED | Telegram: OFF")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
