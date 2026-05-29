"""
new_build_dashboard_server.py
Minimal dashboard server for New Build paper-only reads.

Serves:
  GET /             → redirect to /dashboard
  GET /dashboard    → static dashboard HTML
  GET /sidecar_stack_latest.json  → New Build sidecar JSON
  GET /api/governed-card?date=YYYY-MM-DD → New Build verdicts in governed-card shape
  GET /api/health   → health check

No Supabase. No model_manager. No Live VELO. No Telegram. No staking.

Usage:
  python scripts/ops/new_build_dashboard_server.py [--port 8000]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    raise SystemExit("Run: pip install fastapi uvicorn")

ROOT = Path(__file__).resolve().parents[2]
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


def _fmt_time(val: str | None) -> str | None:
    if not val:
        return None
    if "T" in str(val):
        try:
            return datetime.fromisoformat(val).strftime("%H:%M")
        except Exception:
            pass
    return str(val)[:5] if len(str(val)) >= 5 else val


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


def _build_governed_card(date_str: str) -> dict:
    """Build governed-card API response from New Build artifacts only."""
    preds = _find_predictions_for_date(date_str)

    # Try race-day report for metadata
    report_path = REPORT_DIR / f"new_build_race_day_{date_str.replace('-', '_')}_latest.json"
    report = _load_json(report_path, {})
    feed = report.get("current_card_feed", {}) if report else {}

    if not preds:
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
