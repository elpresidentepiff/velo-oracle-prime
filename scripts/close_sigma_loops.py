"""
VÉLØ — Sigma Loop Closer
========================
Pulls today's results from Racing API, reconciles against stored verdicts,
populates race_results / runner_results / velo_post_race_reviews / sigma_audits.

Single-run guard via pipeline_runs table — aborts if a run is already running (< 24h).
Stale running rows older than 24h are auto-closed as FAIL (age gate).

Run: python scripts/close_sigma_loops.py [--date YYYY-MM-DD]
"""

import os
import sys
import json
import logging
import argparse
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import hashlib
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("velo.sigma_closer")

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
RACING_API_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com").rstrip("/")
RACING_USER     = os.getenv("RACING_API_USERNAME", "")
RACING_PASS     = os.getenv("RACING_API_PASSWORD", "")
SUPA_URL        = os.getenv("SUPABASE_URL", "")
SUPA_KEY        = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                   or os.getenv("SUPABASE_SERVICE_KEY")
                   or os.getenv("SUPABASE_KEY", ""))

RUN_TYPE = "results_reconciliation"

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")


def tg(text: str) -> None:
    """Send a message to Telegram. Silent no-op if credentials missing."""
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        import urllib.request as _ur, json as _j
        body = _j.dumps({"chat_id": TG_CHAT, "text": text[:4096]}).encode()
        req = _ur.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"},
        )
        _ur.urlopen(req, timeout=10)
    except Exception as _e:
        log.warning("Telegram send failed: %s", _e)


# ─────────────────────────────────────────────────────────────
# Single-run guard
# ─────────────────────────────────────────────────────────────
def acquire_run_lock(db: Client, source_date: str) -> Optional[str]:
    """
    Insert a pipeline_runs row with run_state=running.
    Returns run_id if acquired, None if a recent run is already running (< 24h).
    Running rows older than 24h are closed as FAIL (age gate) and a new row is inserted.
    """
    SERVICE = "velo_sigma_closer"
    AGE_GATE_HOURS = 24
    now = datetime.now(timezone.utc)
    existing_run_id = (os.getenv("PIPELINE_RUN_ID") or "").strip()

    if existing_run_id:
        log.info("Using pre-claimed pipeline run from trigger: %s", existing_run_id)
        return existing_run_id

    existing = (
        db.table("pipeline_runs")
        .select("id, started_at")
        .eq("service_name", SERVICE)
        .eq("source_date", source_date)
        .eq("run_state", "running")
        .execute()
    )

    for row in (existing.data or []):
        try:
            started_raw = row["started_at"]
            started = datetime.fromisoformat(started_raw.rstrip("Z")).replace(tzinfo=timezone.utc)
        except Exception:
            started = now - timedelta(hours=AGE_GATE_HOURS + 1)  # treat as stale

        age_hours = (now - started).total_seconds() / 3600
        if age_hours >= AGE_GATE_HOURS:
            # Stale — close as FAIL and allow new run
            db.table("pipeline_runs").update({
                "run_state":     "completed",
                "status":        "FAIL",
                "finished_at":   now.isoformat(),
                "error_message": f"Closed by age gate ({age_hours:.1f}h stale): superseded by new run",
            }).eq("id", row["id"]).execute()
            log.warning(
                "STALE_LOCK: age gate closed run %s (%.1fh old). "
                "This may indicate a zombie container or perpetually hanging process. "
                "Investigate if this recurs.",
                row["id"], age_hours,
            )
            tg(
                f"VELO SIGMA ALERT\n"
                f"Stale lock override: run {row['id'][:8]}... was {age_hours:.1f}h old.\n"
                f"Auto-closed as FAIL. New run starting.\n"
                f"If this recurs, investigate zombie processes."
            )
        else:
            log.warning(
                "Run already running (id=%s, age=%.1fh). Aborting.",
                row["id"], age_hours,
            )
            return None

    run_id = str(uuid.uuid4())
    db.table("pipeline_runs").insert({
        "id":             run_id,
        "service_name":   SERVICE,
        "run_type":       RUN_TYPE,
        "started_at":     now.isoformat(),
        "run_state":      "running",
        "trigger_source": os.getenv("TRIGGER_SOURCE", "manual") or "manual",
        "source_date":    source_date,
        "environment":    os.getenv("RAILWAY_ENVIRONMENT", "production"),
    }).execute()
    log.info("Run lock acquired: %s", run_id)
    return run_id


def release_run_lock(
    db: Client,
    run_id: str,
    status: str,
    races: int = 0,
    runners: int = 0,
    results: int = 0,
    error: Optional[str] = None,
) -> None:
    db.table("pipeline_runs").update({
        "run_state":        "completed",
        "finished_at":      datetime.now(timezone.utc).isoformat(),
        "status":           status,
        "races_processed":  races,
        "runners_processed": runners,
        "results_processed": results,
        "error_message":    error,
    }).eq("id", run_id).execute()
    log.info("Run lock released: %s → %s", run_id, status)


# ─────────────────────────────────────────────────────────────
# Racing API fetch
# ─────────────────────────────────────────────────────────────
def fetch_results(target_date: str) -> List[Dict]:
    """
    Fetch results from Racing API.

    Same-day:  GET /v1/results/today          (Basic+ plan)
    Past-date: GET /v1/results?start_date=&end_date=  (Standard+ plan)

    NOTE: the historical endpoint uses start_date / end_date — NOT a bare
    'date' parameter. Sending 'date=' returns 422 Unprocessable Entity.
    """
    if not RACING_USER or not RACING_PASS:
        raise EnvironmentError("RACING_API_USERNAME / RACING_API_PASSWORD not set")

    session = requests.Session()
    session.auth = (RACING_USER, RACING_PASS)
    session.headers["Accept"] = "application/json"

    today = str(date.today())
    # Strip any trailing /v1 from base to avoid double-pathing
    base = RACING_API_BASE.rstrip("/").removesuffix("/v1")
    if target_date == today:
        url = f"{base}/v1/results/today"
        params = {}
    else:
        # Historical endpoint — requires Standard plan.
        # Correct params: start_date + end_date (not 'date').
        url = f"{base}/v1/results"
        params = {"start_date": target_date, "end_date": target_date}

    log.info("GET %s %s", url, params or "")
    resp = session.get(url, params=params, timeout=30)

    if resp.status_code == 402:
        log.error(
            "Racing API 402 — subscription does not include results. "
            "Upgrade to Standard/Pro plan. Marking run partial."
        )
        return []
    if resp.status_code == 403:
        log.error(
            "Racing API 403 — historical results (/v1/results) require Standard plan. "
            "Same-day cron (/v1/results/today) requires Basic. "
            "Current plan does not cover past-date rerun for %s. Marking run partial.",
            target_date,
        )
        return []
    if resp.status_code == 404:
        log.warning("No results found for %s (404)", target_date)
        return []
    if resp.status_code == 422:
        log.error(
            "Racing API 422 — unprocessable request for %s. "
            "Check endpoint params. URL: %s params: %s",
            target_date, resp.url, params,
        )
        return []

    resp.raise_for_status()
    data = resp.json()

    # API returns either a list or {"results": [...]}
    if isinstance(data, list):
        return data
    return data.get("results", [])


# ─────────────────────────────────────────────────────────────
# Insert race_results + runner_results
# ─────────────────────────────────────────────────────────────
def store_race_result(db: Client, race_id: str, api_result: Dict) -> int:
    """
    Upsert one race into race_results.
    Returns count of runner_results inserted.
    """
    now = datetime.now(timezone.utc).isoformat()

    # race_results row
    race_row = {
        "race_id": race_id,
        "winning_time_detail": api_result.get("winning_time"),
        "tote_win": _safe_float(api_result.get("tote_win")),
        "tote_place": api_result.get("tote_place"),       # jsonb
        "tote_exacta": _safe_float(api_result.get("tote_exacta")),
        "tote_csf": _safe_float(api_result.get("tote_csf")),
        "tote_trifecta": _safe_float(api_result.get("tote_trifecta")),
        "tote_tricast": _safe_float(api_result.get("tote_tricast")),
        "non_runners": api_result.get("non_runners", []),
        "reconciled_at": now,
    }
    db.table("race_results").upsert(race_row, on_conflict="race_id").execute()

    # runner_results rows
    runners = api_result.get("runners", [])
    count = 0
    for r in runners:
        horse_id = r.get("horse_id") or r.get("id", "")
        if not horse_id:
            continue
        position = _safe_int(r.get("position"))
        row = {
            "race_id": race_id,
            "horse_id": horse_id,
            "position": position,
            "position_text": str(r.get("position", "")),
            "sp": str(r.get("sp", "")),
            "sp_dec": _safe_float(r.get("sp_dec") or r.get("sp")),
            "bsp": _safe_float(r.get("bsp")),
            "btn": _safe_float(r.get("btn")),
            "ovr_btn": _safe_float(r.get("ovr_btn")),
            "time": r.get("time", ""),
            "prize": _safe_float(r.get("prize")),
            "in_running_comment": r.get("in_running_comment", ""),
            "is_winner": (position == 1),
        }
        db.table("runner_results").upsert(
            row, on_conflict="race_id,horse_id"
        ).execute()
        count += 1

    log.info("  race %s → %d runner_results stored", race_id, count)
    return count


# ─────────────────────────────────────────────────────────────
# Signal attribution — forensic miss analysis
# ─────────────────────────────────────────────────────────────
_SPECIALIST_SIGNALS = [
    "improvement_score",
    "market_deception_score",
    "place_prob",
    "longshot_prob",
    "release_day_prob",
    "draw_bias_score",
    "comment_intel_score",
]
_ATTRIBUTION_THRESHOLD = 0.05  # winner must lead by this margin to count


def _attribute_miss_signals(
    full_analysis: list,
    top_pick_id: str,
    winner_id: str,
) -> dict:
    """
    Compare specialist signal scores between winner and top_pick.
    Returns dict with:
      top_pick_scores, winner_scores,
      winner_dominated_signals {signal: delta},
      primary_miss_signal (signal winner dominated most)
    Returns {} if data is absent or winner == top_pick.
    """
    if not full_analysis or not winner_id or winner_id == top_pick_id:
        return {}

    top_scores: dict = {}
    winner_scores: dict = {}

    for runner in full_analysis:
        if isinstance(runner, str):
            try:
                runner = json.loads(runner)
            except Exception:
                continue
        if not isinstance(runner, dict):
            continue
        rid = runner.get("horse_id") or runner.get("horse", "")
        if rid == top_pick_id:
            for s in _SPECIALIST_SIGNALS:
                v = runner.get(s)
                if v is not None:
                    try:
                        top_scores[s] = float(v)
                    except (TypeError, ValueError):
                        pass
        elif rid == winner_id:
            for s in _SPECIALIST_SIGNALS:
                v = runner.get(s)
                if v is not None:
                    try:
                        winner_scores[s] = float(v)
                    except (TypeError, ValueError):
                        pass

    winner_dominated: dict = {}
    for s in _SPECIALIST_SIGNALS:
        ws = winner_scores.get(s)
        ts = top_scores.get(s)
        if ws is not None and ts is not None:
            delta = ws - ts
            if delta > _ATTRIBUTION_THRESHOLD:
                winner_dominated[s] = round(delta, 4)

    primary = (
        max(winner_dominated, key=winner_dominated.get)
        if winner_dominated else None
    )

    return {
        "top_pick_scores": top_scores,
        "winner_scores": winner_scores,
        "winner_dominated_signals": winner_dominated,
        "primary_miss_signal": primary,
    }


# ─────────────────────────────────────────────────────────────
# Generate post-race reviews
# ─────────────────────────────────────────────────────────────
def generate_review(
    db: Client,
    verdict: Dict,
    api_result: Dict,
    runners_result: List[Dict],
) -> Dict:
    """
    Compare a verdict against actual results.
    Returns a velo_post_race_reviews row.
    """
    top_pick_id = verdict["top_rank_horse_id"]
    verdict_id  = verdict["verdict_id"]
    race_id     = verdict["race_id"]

    # Find winner from runners_result (position may be string from API)
    winner = next((r for r in runners_result if _safe_int(r.get("position")) == 1), None)
    winner_id = winner.get("horse_id", "") if winner else ""
    winner_sp = _safe_float(winner.get("sp_dec")) if winner else None

    # Find top_pick in results
    top_pick_result = next(
        (r for r in runners_result if r.get("horse_id") == top_pick_id), None
    )
    top_pick_pos = _safe_int(top_pick_result.get("position")) if top_pick_result else None
    top_pick_won    = (top_pick_pos == 1)
    top_pick_placed = (top_pick_pos is not None and top_pick_pos <= 3)

    # Accuracy score: 1.0 = win, 0.5 = placed, 0.0 = miss
    if top_pick_won:
        accuracy = 1.0
        outcome_label = "WIN"
    elif top_pick_placed:
        accuracy = 0.5
        outcome_label = "PLACED"
    else:
        accuracy = 0.0
        outcome_label = "MISS"

    # RPD-C tag extraction — passive metadata from full_analysis
    top_pick_rpd_tag: str | None = None
    winner_rpd_tag: str | None = None

    # Pull full_analysis once for signal attribution, RPD tags, and track context
    raw_fa = verdict.get("full_analysis") or []
    if isinstance(raw_fa, str):
        try:
            raw_fa = json.loads(raw_fa)
        except Exception:
            raw_fa = []

    # Track context — from top runner block (passive enrichment, injected at persist time)
    _top_runner = raw_fa[0] if raw_fa and isinstance(raw_fa[0], dict) else {}
    track_chaos_rating = _top_runner.get("track_chaos_rating")
    track_pace_bias    = _top_runner.get("track_pace_bias")

    for _runner in raw_fa:
        if isinstance(_runner, str):
            try:
                _runner = json.loads(_runner)
            except Exception:
                continue
        if not isinstance(_runner, dict):
            continue
        _rid = _runner.get("horse_id") or _runner.get("horse", "")
        if _rid == top_pick_id and "rpd_tag" in _runner:
            top_pick_rpd_tag = _runner["rpd_tag"]
        elif _rid == winner_id and "rpd_tag" in _runner:
            winner_rpd_tag = _runner["rpd_tag"]

    # Signal attribution — forensic miss analysis
    signal_attribution: dict = {}
    miss_reason = None
    patch_note  = None

    if not top_pick_won:
        confidence = verdict.get("confidence_level", "")

        # raw_fa already parsed above (RPD-C extraction)
        signal_attribution = _attribute_miss_signals(raw_fa, top_pick_id, winner_id)
        primary_signal = signal_attribution.get("primary_miss_signal")

        # Classify miss reason — signal-attributed first, then structural fallbacks
        if top_pick_pos is None:
            miss_reason = "non_runner_or_untracked"
        elif primary_signal:
            # Winner dominated on a specific signal the model underweighted
            miss_reason = f"signal_underweighted_{primary_signal}"
            dominated = signal_attribution.get("winner_dominated_signals", {})
            patch_note = (
                f"Winner {winner_id} (SP {winner_sp}) dominated on {primary_signal} "
                f"by {dominated.get(primary_signal, '?'):.3f}. "
                f"Top pick {top_pick_id} pos={top_pick_pos}. "
                f"Signals: {dominated}"
            )
        elif confidence == "HIGH":
            miss_reason = "high_confidence_no_signal_gap"
            patch_note = (
                f"HIGH confidence miss — winner {winner_id} (SP {winner_sp}) "
                f"not distinguishable from full_analysis signals. "
                f"Possible class/going factor not in feature set."
            )
        elif winner_sp and winner_sp > 10:
            miss_reason = "outsider_hedge_omitted"
            patch_note = f"Winner {winner_id} was SP {winner_sp} — longshot signal missed."
        else:
            miss_reason = "market_decoy_followed"

    # Full review outcome — selections_results removed (velo_verdicts.selections not populated)
    review_outcome = {
        "outcome": outcome_label,
        "top_pick_position": top_pick_pos,
        "winner_id": winner_id,
        "winner_sp": winner_sp,
        "miss_reason": miss_reason,
        "patch_note": patch_note,
        "signal_attribution": signal_attribution,
        "verdict_confidence": verdict.get("confidence_level"),
        "verdict_score": float(verdict.get("top_rank_score", 0)),
        # RPD-C doctrine layer — passive metadata
        "top_pick_rpd_tag": top_pick_rpd_tag,
        "winner_rpd_tag": winner_rpd_tag,
        # Track context — from passive enrichment in full_analysis
        "race_course": verdict.get("race_course"),
        "track_chaos_rating": track_chaos_rating,
        "track_pace_bias": track_pace_bias,
    }

    notes = (
        f"{outcome_label}: {top_pick_id} pos={top_pick_pos}, "
        f"winner={winner_id}@{winner_sp}SP. "
        f"course={verdict.get('race_course') or 'unknown'} "
        f"chaos={track_chaos_rating}. "
        f"{'Patch: ' + patch_note if patch_note else ''}"
    )

    # Classify miss_category from miss_reason for downstream queries
    # (backfill_miss_evidence.py populates this manually for historical data;
    #  new reviews should have it from the start)
    miss_category = None
    if miss_reason:
        if miss_reason.startswith("signal_underweighted_"):
            miss_category = "signal_underweighted"
        elif miss_reason == "high_confidence_no_signal_gap":
            miss_category = "high_confidence_miss"
        elif miss_reason == "outsider_hedge_omitted":
            miss_category = "outsider_miss"
        elif miss_reason == "market_decoy_followed":
            miss_category = "market_decoy_followed"
        elif miss_reason == "non_runner_or_untracked":
            miss_category = "non_runner"
        else:
            miss_category = miss_reason  # pass through unknown reasons

    return {
        "verdict_id": verdict_id,
        "race_id": race_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "top_pick_won": top_pick_won,
        "top_pick_placed": top_pick_placed,
        "top_pick_position": top_pick_pos,
        "actual_winner_id": winner_id,
        "actual_winner_sp": winner_sp,
        "verdict_accuracy_score": accuracy,
        "review_outcome": review_outcome,
        "miss_category": miss_category,
        "learning_ready": (miss_category is not None),
        "notes": notes[:500],
    }


def _get_race_record(db: Client, race_id: str) -> Dict:
    """
    Look up a race's metadata (date, course) from the races table.
    Returns a dict with 'date' and 'course' keys, or empty dict if not found.
    """
    try:
        result = db.table("races").select("date, course").eq("race_id", race_id).limit(1).execute()
        if result.data:
            return result.data[0]
    except Exception as e:
        log.warning("  [races lookup] failed for %s: %s", race_id, e)
    return {}


def write_sigma_audit(db: Client, race_id: str, review: Dict, verdict: Dict) -> None:
    # Look up race metadata from races table (not from verdict which lacks these fields)
    race_record = _get_race_record(db, race_id)
    race_date = race_record.get("date", "") or ""
    race_course = race_record.get("course", "") or ""

    outcome = review["review_outcome"]
    chaos   = outcome.get("track_chaos_rating")
    pace    = outcome.get("track_pace_bias")
    # Use race_course from races table as primary; fall back to verdict enrichment
    course  = race_course or outcome.get("race_course") or verdict.get("race_course") or ""
    notes   = f"chaos={chaos} pace={pace}"
    if outcome.get("patch_note"):
        notes += f" | {outcome['patch_note']}"
    db.table("sigma_audits").upsert({
        "event_type":       "post_race_review",
        "race_id":          race_id,
        "horse_id":         verdict.get("top_rank_horse_id"),
        "verdict_id":       review["verdict_id"],
        "date":             race_date,
        "track":            course,
        "outcome":          outcome.get("outcome"),
        "miss_reason":      outcome.get("miss_reason"),
        "patch_note":       outcome.get("patch_note"),
        "confidence_level": verdict.get("confidence_level"),
        "verdict_score":    float(verdict.get("top_rank_score", 0)),
        "decision_tier":    verdict.get("decision_tier"),
        "top_pick_position": review.get("top_pick_position"),
        "actual_winner_id": review.get("actual_winner_id"),
        "actual_winner_sp": review.get("actual_winner_sp"),
        "notes":            notes[:500],
        "created_at":       datetime.now(timezone.utc).isoformat(),
    }, on_conflict="race_id").execute()


# ─────────────────────────────────────────────────────────────
# Learned patterns writer
# ─────────────────────────────────────────────────────────────
def _update_learned_patterns(db: Client, run_reviews: List[Dict], target_date: str) -> int:
    """
    Derive patterns from today's sigma run_reviews and upsert into learned_patterns.
    Returns count of patterns written.
    """
    from collections import defaultdict
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    written = 0

    def _upsert_pattern(name: str, p_type: str, desc: str,
                        conditions: dict, n: int, wins: int) -> None:
        nonlocal written
        sr = round(wins / n, 4) if n else 0.0
        db.table("learned_patterns").upsert({
            "pattern_name":           name,
            "pattern_type":           p_type,
            "description":            desc,
            "conditions":             conditions,
            "occurrences":            n,
            "successful_predictions": wins,
            "success_rate":           sr,
            "avg_roi":                None,
            "confidence_level":       round(min(n / 50, 1.0), 4),
            "first_observed":         now,
            "last_observed":          now,
            "created_at":             now,
            "updated_at":             now,
            "is_active":              True,
        }, on_conflict="pattern_name").execute()
        written += 1

    # 1. Per-tier accuracy patterns
    tier_stats: dict = defaultdict(lambda: {"n": 0, "wins": 0})
    for rr in run_reviews:
        t = rr["decision_tier"]
        tier_stats[t]["n"] += 1
        if rr["outcome"] == "WIN":
            tier_stats[t]["wins"] += 1

    for tier, s in tier_stats.items():
        _upsert_pattern(
            name=f"tier_{tier}_accuracy",
            p_type="tier_accuracy",
            desc=f"Decision tier {tier}: cumulative win accuracy from sigma reconciliation",
            conditions={"decision_tier": tier, "source_date": target_date},
            n=s["n"], wins=s["wins"],
        )

    # 2. Miss-reason frequency patterns
    miss_stats: dict = defaultdict(int)
    for rr in run_reviews:
        if rr["outcome"] not in ("WIN", "PLACED") and rr.get("miss_reason"):
            miss_stats[rr["miss_reason"]] += 1

    for reason, count in miss_stats.items():
        _upsert_pattern(
            name=f"miss_reason_{reason}",
            p_type="miss_pattern",
            desc=f"Miss reason '{reason}' — cumulative frequency from sigma",
            conditions={"miss_reason": reason, "source_date": target_date},
            n=count, wins=0,
        )

    # 3. High-confidence accuracy pattern
    hc = [r for r in run_reviews if r.get("confidence") == "HIGH"]
    if hc:
        hc_wins = sum(1 for r in hc if r["outcome"] == "WIN")
        _upsert_pattern(
            name="high_confidence_accuracy",
            p_type="confidence_accuracy",
            desc="Accuracy when verdict confidence_level=HIGH",
            conditions={"confidence_level": "HIGH", "source_date": target_date},
            n=len(hc), wins=hc_wins,
        )

    # 4. Signal attribution patterns — forensic layer
    # For each miss with a primary_miss_signal, track which signals are
    # systematically underweighted vs winners.
    signal_miss_counts: dict = defaultdict(lambda: {"n": 0, "tiers": []})
    for rr in run_reviews:
        if rr["outcome"] in ("WIN", "PLACED"):
            continue
        attr = rr.get("signal_attribution") or {}
        primary = attr.get("primary_miss_signal")
        if not primary:
            continue
        signal_miss_counts[primary]["n"] += 1
        signal_miss_counts[primary]["tiers"].append(rr["decision_tier"])

    for signal, data in signal_miss_counts.items():
        n = data["n"]
        tiers = data["tiers"]
        tier_freq = {}
        for t in tiers:
            tier_freq[t] = tier_freq.get(t, 0) + 1
        dominant_tier = max(tier_freq, key=tier_freq.get) if tier_freq else "?"
        _upsert_pattern(
            name=f"signal_miss_{signal}",
            p_type="signal_attribution",
            desc=(
                f"Winner dominated top_pick on '{signal}' — signal underweighted. "
                f"Most frequent in {dominant_tier}-tier races."
            ),
            conditions={
                "signal": signal,
                "dominant_tier": dominant_tier,
                "tier_distribution": tier_freq,
                "source_date": target_date,
            },
            n=n,
            wins=0,  # these are misses — wins always 0 for this pattern type
        )

    # 5. Per-tier primary miss signal — which signal fails each tier most
    tier_signal_acc: dict = defaultdict(lambda: defaultdict(int))
    for rr in run_reviews:
        if rr["outcome"] in ("WIN", "PLACED"):
            continue
        attr = rr.get("signal_attribution") or {}
        primary = attr.get("primary_miss_signal")
        if not primary:
            continue
        tier_signal_acc[rr["decision_tier"]][primary] += 1

    for tier, signal_counts in tier_signal_acc.items():
        worst_signal = max(signal_counts, key=signal_counts.get)
        _upsert_pattern(
            name=f"tier_{tier}_primary_miss_signal",
            p_type="tier_signal_profile",
            desc=(
                f"In {tier}-tier misses, '{worst_signal}' is the most common "
                f"signal the winner dominated. Implies {tier}-tier scoring "
                f"may underweight this signal."
            ),
            conditions={
                "decision_tier": tier,
                "signal_counts": dict(signal_counts),
                "source_date": target_date,
            },
            n=sum(signal_counts.values()),
            wins=0,
        )

    # 6. RPD tag vs outcome — how often each tag appears on winners and top-picks
    rpd_winner_acc: dict = defaultdict(lambda: {"n": 0, "wins": 0})
    rpd_top_pick_acc: dict = defaultdict(lambda: {"n": 0, "wins": 0})
    for rr in run_reviews:
        winner_tag   = rr.get("winner_rpd_tag")
        top_pick_tag = rr.get("top_pick_rpd_tag")
        if winner_tag:
            rpd_winner_acc[winner_tag]["n"] += 1
            # Every winner is a "win" for this pattern — counts how often tag appears on winner
            rpd_winner_acc[winner_tag]["wins"] += 1
        if top_pick_tag:
            rpd_top_pick_acc[top_pick_tag]["n"] += 1
            if rr["outcome"] == "WIN":
                rpd_top_pick_acc[top_pick_tag]["wins"] += 1

    for tag, stats in rpd_winner_acc.items():
        _upsert_pattern(
            name=f"rpd_winner_tag_{tag}",
            p_type="rpd_tag_accuracy",
            desc=f"Race winners tagged RPD-C '{tag}' — observation frequency",
            conditions={"rpd_tag": tag, "role": "winner", "source_date": target_date},
            n=stats["n"], wins=stats["wins"],
        )

    for tag, stats in rpd_top_pick_acc.items():
        _upsert_pattern(
            name=f"rpd_top_pick_tag_{tag}_accuracy",
            p_type="rpd_tag_accuracy",
            desc=(
                f"Top-pick horses tagged RPD-C '{tag}': win rate. "
                f"If low, '{tag}' selections need requalification."
            ),
            conditions={"rpd_tag": tag, "role": "top_pick", "source_date": target_date},
            n=stats["n"], wins=stats["wins"],
        )

    log.info("Learned patterns written: %d", written)
    return written


# ─────────────────────────────────────────────────────────────
# Governance: create sigma proposals from learned_patterns
# ─────────────────────────────────────────────────────────────
_PROPOSAL_THRESHOLD = 5          # min occurrences before a pattern triggers a proposal
_PROPOSAL_HIGH_THRESHOLD = 15   # occurrences above which severity escalates to HIGH


def _create_sigma_proposals(db: Client, target_date: str) -> int:
    """
    Read learned_patterns rows above _PROPOSAL_THRESHOLD occurrences and create
    DRAFT proposals in patch_proposals via GovernanceAPI.

    At end of run, transitions all DRAFTs to PENDING so human review can begin.
    Returns count of new proposals created (duplicates silently skipped).

    Called as Step 8 in sigma main() after learned_patterns are written.
    Does NOT alter scores, rankings, or any prediction artefact.
    """
    try:
        from src.v13.governance.api import GovernanceAPI
        from src.v13.governance.persistence import ProposalPersistence
    except ImportError as e:
        log.warning("Governance module not importable — skipping proposals: %s", e)
        return 0

    # Load patterns above threshold
    try:
        patt_rows = (
            db.table("learned_patterns")
            .select("pattern_name, pattern_type, description, conditions, "
                    "occurrences, success_rate, confidence_level")
            .gte("occurrences", _PROPOSAL_THRESHOLD)
            .eq("is_active", True)
            .execute()
        )
    except Exception as e:
        log.warning("learned_patterns query failed — skipping proposals: %s", e)
        return 0

    patterns = patt_rows.data or []
    if not patterns:
        log.info("No learned_patterns above threshold — no proposals created")
        return 0

    log.info("Creating sigma proposals from %d patterns above threshold=%d",
             len(patterns), _PROPOSAL_THRESHOLD)

    persistence = ProposalPersistence(db)
    created = 0

    _PATTERN_TYPE_MAP = {
        "tier_accuracy":      ("SIGMA", "TIER_ACCURACY"),
        "miss_pattern":       ("SIGMA", "MISS_PATTERN"),
        "signal_attribution": ("SIGMA", "SIGNAL_UNDERWEIGHTED"),
        "tier_signal_profile": ("SIGMA", "SIGNAL_UNDERWEIGHTED"),
        "confidence_accuracy": ("SIGMA", "CONFIDENCE_CALIBRATION"),
        "rpd_tag_accuracy":   ("RPD",   "RPD_TAG_ACCURACY"),
    }

    for p in patterns:
        n         = p.get("occurrences") or 0
        sr        = p.get("success_rate")
        ptype     = p.get("pattern_type", "")
        pname     = p.get("pattern_name", "")
        desc      = p.get("description", "")
        conditions = p.get("conditions") or {}

        # Determine critic_type and finding_type from pattern_type
        critic_type, finding_type = _PATTERN_TYPE_MAP.get(ptype, ("SIGMA", "UNKNOWN_PATTERN"))

        # Severity
        if n >= _PROPOSAL_HIGH_THRESHOLD:
            severity = "HIGH"
        elif n >= _PROPOSAL_THRESHOLD * 2:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # Escalate miss / signal patterns that have high frequency and low win rate
        if sr is not None and sr < 0.15 and n >= _PROPOSAL_HIGH_THRESHOLD:
            severity = "CRITICAL"

        proposed_change = {
            "pattern_name":   pname,
            "pattern_type":   ptype,
            "occurrences":    n,
            "success_rate":   sr,
            "conditions":     conditions,
            "suggested_action": (
                f"Review doctrine weighting for pattern '{pname}'. "
                f"Seen {n}× with success_rate={sr}. "
                f"Evidence from sigma run {target_date}."
            ),
        }

        pid = persistence.persist_proposal(
            source_race_id=None,          # pattern-level, not single-race
            source_pattern_name=pname,
            critic_type=critic_type,
            severity=severity,
            finding_type=finding_type,
            description=desc,
            proposed_change=proposed_change,
        )
        if pid:
            log.info("  Proposal created: %s [%s/%s] n=%d sr=%s severity=%s",
                     pname, critic_type, finding_type, n, sr, severity)
            created += 1
        else:
            log.debug("  Proposal deduplicated (already exists): %s", pname)

    # Transition all DRAFTs to PENDING at end of sigma run
    if created > 0:
        try:
            transitioned = persistence.transition_all_drafts_to_pending()
            log.info("Governance: %d new proposals → PENDING (%d DRAFTs transitioned total)",
                     created, transitioned)
        except Exception as e:
            log.warning("transition_all_drafts_to_pending failed (non-fatal): %s", e)

    return created


# ─────────────────────────────────────────────────────────────
# Phase 1 — Sigma → Playbook G doctrine auto-pipeline
# ─────────────────────────────────────────────────────────────
def _write_zep_outcomes(db: Client, run_reviews: List[Dict], target_date: str) -> None:
    """
    Step 10 — Write race outcomes to Zep Cloud graph memory.

    Each closed race review becomes one or more graph facts:
      - The winner's result (horse + trainer + jockey + course + SP + OR + RPD-C)
      - VELO's pick outcome (WIN / PLACED / MISS)

    Zep parses these into entity nodes and temporal edges, making them available
    to VOX for cross-session intelligence retrieval without re-querying Supabase.

    Completely optional — if ZEP_API_KEY is not set, this is a silent no-op.
    """
    try:
        from src.intelligence.zep_memory import zep_client as _zep
    except ImportError:
        log.debug("Step 10: zep_client not available — skipping")
        return

    if not os.getenv("ZEP_API_KEY", ""):
        log.debug("Step 10: ZEP_API_KEY not set — skipping Zep graph write")
        return

    # Fetch winner details from runner_results for richer graph facts
    race_ids = [rr["race_id"] for rr in run_reviews]
    winner_rows: Dict[str, Dict] = {}
    try:
        rows = (
            db.table("runner_results")
            .select("race_id, horse_name, trainer, jockey, sp_dec, or_rating, course, distance")
            .eq("is_winner", True)
            .in_("race_id", race_ids)
            .execute()
        )
        for r in rows.data:
            winner_rows[r["race_id"]] = r
    except Exception as e:
        log.debug("Step 10: winner row fetch failed (non-fatal): %s", e)

    written = 0
    for rr in run_reviews:
        race_id = rr["race_id"]
        outcome = rr["outcome"]
        winner  = winner_rows.get(race_id, {})
        verdict = rr.get("decision_tier", "?")

        # Write winner outcome to Zep graph
        try:
            _zep.write_race_outcome(
                horse_name  = winner.get("horse_name") or rr.get("winner_id", "unknown"),
                trainer     = winner.get("trainer", ""),
                jockey      = winner.get("jockey", ""),
                course      = winner.get("course", ""),
                race_date   = target_date,
                position    = 1,
                sp_decimal  = _safe_float(winner.get("sp_dec")),
                or_rating   = winner.get("or_rating"),
                rpdc_tag    = rr.get("winner_rpd_tag"),
                velo_verdict= f"VELO-{verdict}-{outcome}",
            )
            written += 1
        except Exception as e:
            log.debug("Step 10: write_race_outcome failed for %s: %s", race_id, e)

    log.info("Step 10: Zep graph write complete — %d outcome facts written", written)


def _feed_playbook_g(
    db: Client,
    run_reviews: List[Dict],
    verdicts_by_race: Dict[str, Dict],
    target_date: str,
) -> int:
    """
    Step 9 — Feed sigma reconciliation outcomes into SentientLoopbackEngine (Playbook G).

    Converts each race review into an observe_race_outcome() call, updating
    doctrine_strengths, emotion_laws, and appetite_state in sentient_state.json.
    State is also backed up to Supabase learned_patterns (SENTIENT_STATE_BACKUP).

    Idempotent: a dedup marker (pattern_name='playbook_g_fed_{date}') in
    learned_patterns prevents double-ingestion on re-run for the same date.

    Returns count of races fed into playbook_g.
    """
    if not run_reviews:
        log.info("Step 9: no reviews to feed — skipping playbook_g")
        return 0

    # ── Dedup guard ──────────────────────────────────────────────────────────
    dedup_name = f"playbook_g_fed_{target_date}"
    try:
        existing = (
            db.table("learned_patterns")
            .select("id")
            .eq("pattern_name", dedup_name)
            .execute()
        )
        if existing.data:
            log.info(
                "Step 9: playbook_g already fed for %s (dedup_name=%s) — skipping",
                target_date, dedup_name,
            )
            return 0
    except Exception as e:
        log.warning("Step 9: dedup check failed (%s) — proceeding cautiously", e)

    # ── Lazy import Playbook G ────────────────────────────────────────────────
    try:
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
        engine = SentientLoopbackEngine()
    except Exception as e:
        log.warning("Step 9: SentientLoopbackEngine import failed — skipping: %s", e)
        return 0

    fed = 0
    wins_fed = 0

    # ── Enrich with race context from Supabase (batch, non-fatal) ────────────
    race_ids = [rr["race_id"] for rr in run_reviews]
    race_meta: Dict[str, Dict] = {}
    winner_sp_map: Dict[str, Optional[float]] = {}

    try:
        meta_rows = (
            db.table("races")
            .select("race_id, going, class, runners_count, distance_f")
            .in_("race_id", race_ids)
            .execute()
        )
        for r in meta_rows.data:
            race_meta[r["race_id"]] = r
        log.debug("Step 9: race meta loaded for %d races", len(race_meta))
    except Exception as e:
        log.warning("Step 9: race meta enrichment failed (non-fatal): %s", e)

    try:
        sp_rows = (
            db.table("runner_results")
            .select("race_id, sp_dec")
            .eq("is_winner", True)
            .in_("race_id", race_ids)
            .execute()
        )
        for r in sp_rows.data:
            winner_sp_map[r["race_id"]] = _safe_float(r.get("sp_dec"))
        log.debug("Step 9: winner SP loaded for %d races", len(winner_sp_map))
    except Exception as e:
        log.warning("Step 9: winner SP enrichment failed (non-fatal): %s", e)

    for rr in run_reviews:
        race_id = rr["race_id"]
        verdict = verdicts_by_race.get(race_id, {})
        outcome = rr["outcome"]
        meta    = race_meta.get(race_id, {})
        winner_sp = winner_sp_map.get(race_id) or rr.get("actual_winner_sp")

        # Going → chaos_bloom proxy
        going = (meta.get("going") or "").lower()
        if "heavy" in going:
            chaos_bloom = 75
        elif "soft" in going:
            chaos_bloom = 65
        elif "good to soft" in going:
            chaos_bloom = 50
        elif "good" in going:
            chaos_bloom = 30
        elif "firm" in going:
            chaos_bloom = 20
        else:
            chaos_bloom = 40   # unknown going — neutral

        # Class → narrative_disruption proxy (lower class = more upsets)
        race_class = str(meta.get("class") or "")
        if race_class in ("5", "6", "7"):
            narrative_disruption = 65
        elif race_class in ("3", "4"):
            narrative_disruption = 45
        else:
            narrative_disruption = 25   # class 1/2 or unknown

        # Winner SP → mpi (market pressure index) proxy
        if winner_sp and winner_sp > 10:
            mpi = 80   # big-priced winner — market was wrong
        elif winner_sp and winner_sp > 5:
            mpi = 50
        elif winner_sp:
            mpi = 20   # short-priced winner — market was right
        else:
            mpi = 0    # no data

        # Build enriched race_data
        race_data = {
            "race_id":              race_id,
            "story_anchor":         verdict.get("top_rank_horse_id", ""),
            "power_anchor":         verdict.get("top_rank_horse_id", ""),
            "mpi":                  mpi,
            "chaos_bloom":          chaos_bloom,
            "narrative_disruption": narrative_disruption,
            "runners":              [],
            "going":                meta.get("going", ""),
            "race_class":           race_class,
            "distance_f":           meta.get("distance_f"),
            "runners_count":        meta.get("runners_count", 0),
        }

        # Build prediction stub from verdict
        prediction = {
            "power_anchor":  verdict.get("top_rank_horse_id", ""),
            "confidence":    float(verdict.get("top_rank_score") or 0),
            "doctrines_fired": [],
        }

        # Build actual_result
        actual_result = {
            "winner":         rr.get("winner_id", ""),
            "favourite_won":  (outcome == "WIN"),
            "winner_profile": {},
        }

        try:
            engine.observe_race_outcome(race_data, prediction, actual_result)
            fed += 1
            if outcome == "WIN":
                wins_fed += 1
            log.debug(
                "Step 9: race %s fed → playbook_g (outcome=%s)", race_id, outcome
            )
        except Exception as e:
            log.warning("Step 9: observe_race_outcome failed for %s: %s", race_id, e)

    if fed == 0:
        log.info("Step 9: no races successfully fed to playbook_g")
        return 0

    # ── Write mutation summary + dedup marker to learned_patterns ─────────────
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    source_hash = hashlib.sha256(
        f"playbook_g:{target_date}:{fed}".encode()
    ).hexdigest()[:16]

    try:
        db.table("learned_patterns").upsert({
            "pattern_name":           dedup_name,
            "pattern_type":           "system_marker",
            "description":            (
                f"Playbook G fed from sigma run {target_date}: "
                f"{fed} races, {wins_fed} wins"
            ),
            "conditions": {
                "source_date":   target_date,
                "fed_count":     fed,
                "wins_fed":      wins_fed,
                "source_hash":   source_hash,
                "doctrine_family": "SENTIENT_LOOPBACK",
                "mutation_type": "observe_race_outcome",
                "sigma_report":  f"pipeline_runs/{target_date}",
            },
            "occurrences":            fed,
            "successful_predictions": wins_fed,
            "success_rate":           round(wins_fed / fed, 4) if fed else 0.0,
            "confidence_level":       round(min(fed / 20, 1.0), 4),
            "first_observed":         now_naive,
            "last_observed":          now_naive,
            "created_at":             now_naive,
            "updated_at":             now_naive,
            "is_active":              True,
        }, on_conflict="pattern_name").execute()
        log.info("Step 9: dedup marker written — pattern_name=%s", dedup_name)
    except Exception as e:
        log.warning("Step 9: dedup marker write failed (non-fatal): %s", e)

    log.info(
        "Step 9: playbook_g fed — %d races ingested (%d wins), "
        "doctrine state updated in sentient_state.json + Supabase backup",
        fed, wins_fed,
    )
    return fed


# ─────────────────────────────────────────────────────────────
# Create rp_imports storage bucket
# ─────────────────────────────────────────────────────────────
def ensure_rp_imports_bucket(db: Client) -> None:
    try:
        buckets = db.storage.list_buckets()
        names = [b["name"] if isinstance(b, dict) else b.name for b in buckets]
        if "rp_imports" not in names:
            db.storage.create_bucket("rp_imports", options={"public": False})
            log.info("Created Supabase storage bucket: rp_imports")
        else:
            log.info("Bucket rp_imports already exists")
    except Exception as e:
        log.error("Failed to create rp_imports bucket: %s", e)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main(target_date: str) -> None:
    if not SUPA_URL or not SUPA_KEY:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    # ── Preflight gate — must pass before any DB access or reconciliation ─────
    print("\nPREFLIGHT")
    from src.preflight import preflight_or_die
    preflight_or_die(tg_fn=tg)   # exits sys.exit(1) on FAIL
    # ─────────────────────────────────────────────────────────────────────────

    db = create_client(SUPA_URL, SUPA_KEY)
    log.info("=== VÉLØ Sigma Loop Closer — %s ===", target_date)

    # Step 0: Create rp_imports bucket if missing
    ensure_rp_imports_bucket(db)

    # Step 1: Single-run guard
    run_id = acquire_run_lock(db, target_date)
    if not run_id:
        sys.exit(1)

    races_done = 0
    runners_done = 0
    reviews_done = 0
    run_reviews: list = []  # per-execution review records for tier-split reporting

    try:
        # Step 2: Load verdicts for target_date from DB
        # First get race_ids for the target date so we can filter server-side.
        race_rows = (
            db.table("races")
            .select("race_id, date, course")
            .eq("date", target_date)
            .execute()
        )
        race_context = {
            r["race_id"]: {"date": r.get("date", ""), "course": r.get("course", "")}
            for r in race_rows.data
        }
        dated_race_ids = list(race_context.keys())
        _dated_race_set = set(dated_race_ids)  # O(1) membership test

        if not dated_race_ids:
            log.warning("No races found in races table for %s", target_date)
            release_run_lock(db, run_id, "PASS", 0, 0, 0)
            return

        # Server-side filter: only fetch verdicts for today's races
        rows = (
            db.table("velo_verdicts")
            .select("id, race_id, generated_at, confidence_level, top_rank_horse_id, "
                    "top_rank_score, selections, decision_tier, full_analysis, "
                    "velo_prime_prob, place_prob, improvement_score, market_deception_score")
            .in_("race_id", dated_race_ids)
            .order("generated_at", desc=True)
            .execute()
        )

        # Dedup: keep only the latest verdict per race_id (by generated_at)
        _seen_races: set = set()
        _deduped: list = []
        for v in rows.data:
            if v["race_id"] not in _seen_races:
                _seen_races.add(v["race_id"])
                _deduped.append(v)

        verdicts = [
            {**v, "verdict_id": v["id"],
             "race_date": race_context.get(v["race_id"], {}).get("date", ""),
             "race_course": race_context.get(v["race_id"], {}).get("course", "")}
            for v in _deduped
        ]
        log.info("Found %d verdicts for %s", len(verdicts), target_date)

        if not verdicts:
            log.warning("No verdicts found for %s — nothing to reconcile", target_date)
            release_run_lock(db, run_id, "PASS", 0, 0, 0)
            return

        verdict_by_race = {v["race_id"]: v for v in verdicts}

        # Step 3: Fetch results from Racing API
        api_results = fetch_results(target_date)
        log.info("Racing API returned %d race results", len(api_results))

        if not api_results:
            log.warning(
                "No results returned from Racing API for %s. "
                "Races may not have finished yet, or subscription tier "
                "may not include results. Marking run as partial.",
                target_date,
            )
            release_run_lock(db, run_id, "DEGRADED", 0, 0, 0,
                             error="Racing API returned 0 results")
            return

        # Step 4: Match, store, review
        for api_race in api_results:
            race_id = api_race.get("race_id") or api_race.get("id", "")
            if not race_id:
                continue

            # Only store results for races we have in our races table (FK constraint)
            if race_id not in _dated_race_set:
                continue

            # Store race_results + runner_results
            runner_count = store_race_result(db, race_id, api_race)
            races_done += 1
            runners_done += runner_count

            # Generate review if we have a verdict
            if race_id in verdict_by_race:
                verdict = verdict_by_race[race_id]
                runners_list = api_race.get("runners", [])

                # Normalise horse_id field (API may use 'horse_id' or 'id')
                for r in runners_list:
                    if "horse_id" not in r and "id" in r:
                        r["horse_id"] = r["id"]

                review = generate_review(db, verdict, api_race, runners_list)

                # Upsert review
                db.table("velo_post_race_reviews").upsert(
                    review, on_conflict="verdict_id"
                ).execute()

                # Sigma audit
                try:
                    write_sigma_audit(db, race_id, review, verdict)
                except Exception as e:
                    log.warning("sigma_audit write failed for %s: %s", race_id, e)

                outcome = review["review_outcome"].get("outcome", "?")
                log.info(
                    "  verdict %s → %s (pos=%s, winner=%s@%s)",
                    race_id, outcome,
                    review.get("top_pick_position"),
                    review.get("actual_winner_id"),
                    review.get("actual_winner_sp"),
                )
                reviews_done += 1
                run_reviews.append({
                    "race_id":            race_id,
                    "outcome":            outcome,
                    "decision_tier":      verdict.get("decision_tier") or "?",
                    "miss_reason":        review["review_outcome"].get("miss_reason"),
                    "signal_attribution": review["review_outcome"].get("signal_attribution", {}),
                    "top_pick_position":  review.get("top_pick_position"),
                    "actual_winner_sp":   review.get("actual_winner_sp"),
                    "winner_id":          review.get("actual_winner_id"),
                    "score":              float(verdict.get("top_rank_score") or 0),
                    "confidence":         verdict.get("confidence_level"),
                    "top_pick_rpd_tag":   review["review_outcome"].get("top_pick_rpd_tag"),
                    "winner_rpd_tag":     review["review_outcome"].get("winner_rpd_tag"),
                })

        # Step 5: Summary
        log.info("")
        log.info("=== RECONCILIATION COMPLETE ===")
        log.info("  races processed  : %d", races_done)
        log.info("  runners processed: %d", runners_done)
        log.info("  reviews generated: %d", reviews_done)

        if reviews_done > 0:
            from collections import defaultdict
            wins   = sum(1 for r in run_reviews if r["outcome"] == "WIN")
            placed = sum(1 for r in run_reviews if r["outcome"] == "PLACED")
            misses_n = reviews_done - wins - placed
            strike_pct = wins / reviews_done * 100
            frame_pct  = (wins + placed) / reviews_done * 100

            log.info("  wins    : %d", wins)
            log.info("  placed  : %d", placed)
            log.info("  misses  : %d", misses_n)
            log.info("  strike rate: %.1f%%", strike_pct)

            # ── Tier-split stats ──────────────────────────────────────────────
            tier_stats: dict = defaultdict(lambda: {"W": 0, "P": 0, "M": 0, "n": 0})
            for rr in run_reviews:
                t = rr["decision_tier"]
                tier_stats[t]["n"] += 1
                if rr["outcome"] == "WIN":    tier_stats[t]["W"] += 1
                elif rr["outcome"] == "PLACED": tier_stats[t]["P"] += 1
                else:                           tier_stats[t]["M"] += 1

            tier_order = ["A", "B", "C", "D", "X", "?"]
            tier_lines = []
            for t in tier_order:
                if t not in tier_stats:
                    continue
                s = tier_stats[t]
                sr = s["W"] / s["n"] * 100 if s["n"] else 0
                tier_lines.append(
                    f"  {t}: {s['n']} races | W{s['W']} P{s['P']} M{s['M']} | {sr:.0f}% strike"
                )
                log.info("Tier %s: n=%d W=%d P=%d M=%d strike=%.0f%%",
                         t, s["n"], s["W"], s["P"], s["M"], sr)

            # ── Forensic audit: A/B tier misses ──────────────────────────────
            ab_misses = [
                rr for rr in run_reviews
                if rr["decision_tier"] in ("A", "B") and rr["outcome"] not in ("WIN", "PLACED")
            ]
            forensic_lines = []
            for rr in ab_misses:
                forensic_lines.append(
                    f"  ⚠ {rr['decision_tier']}-tier miss | race {rr['race_id']} | "
                    f"pos={rr['top_pick_position']} | winner@{rr['actual_winner_sp']}SP | "
                    f"{rr['miss_reason'] or 'unknown'}"
                )
                log.warning("A/B tier miss: race=%s pos=%s winner_sp=%s reason=%s",
                            rr["race_id"], rr["top_pick_position"],
                            rr["actual_winner_sp"], rr["miss_reason"])

            # ── Telegram sigma report ─────────────────────────────────────────
            tg_status = "PASS" if wins > 0 else ("PLACED" if placed > 0 else "MISS")
            tier_block = "\n".join(tier_lines) if tier_lines else "  (no tier data)"
            forensic_block = ("\n" + "\n".join(forensic_lines)) if forensic_lines else ""

            tg(
                f"VELO SIGMA REPORT — {target_date}\n"
                f"{'─' * 30}\n"
                f"Races reconciled: {reviews_done}\n"
                f"Wins:   {wins}  ({strike_pct:.1f}% strike)\n"
                f"Placed: {placed}  (frame: {frame_pct:.1f}%)\n"
                f"Misses: {misses_n}\n"
                f"\nTIER SPLIT:\n{tier_block}"
                f"{forensic_block}\n"
                f"\nStatus: {tg_status}"
            )
            log.info("Telegram sigma report sent")
        else:
            tg(
                f"VELO SIGMA REPORT — {target_date}\n"
                f"{'─' * 30}\n"
                f"No reviews generated — results may not be available yet.\n"
                f"Races processed: {races_done}\n"
                f"Status: PARTIAL"
            )
            log.info("Telegram sigma report sent (partial)")

        # Step 6: Write learned patterns
        if run_reviews:
            try:
                _update_learned_patterns(db, run_reviews, target_date)
            except Exception as e:
                log.warning("learned_patterns write failed (non-fatal): %s", e)

        # Step 7: Update entity bibles
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from scripts.populate_entity_bibles import populate_bibles
            bible_counts = populate_bibles(db)
            log.info("Entity bibles updated: %s", bible_counts)
        except Exception as e:
            log.warning("Entity bible update failed (non-fatal): %s", e)

        # Step 8: Governance — create proposals from learned_patterns above threshold
        try:
            proposals_n = _create_sigma_proposals(db, target_date)
            log.info("Governance proposals created this run: %d", proposals_n)
        except Exception as e:
            log.warning("Governance proposal creation failed (non-fatal): %s", e)

        # Step 9: Feed sigma outcomes into Playbook G doctrine state (auto-pipeline)
        if run_reviews:
            try:
                fed_n = _feed_playbook_g(db, run_reviews, verdict_by_race, target_date)
                log.info("Playbook G doctrine feed complete: %d races ingested", fed_n)
            except Exception as e:
                log.warning("Playbook G feed failed (non-fatal): %s", e)

        # Step 10: Write race outcomes to Zep graph memory (entity intelligence persistence)
        if run_reviews:
            try:
                _write_zep_outcomes(db, run_reviews, target_date)
            except Exception as e:
                log.warning("Zep graph write failed (non-fatal): %s", e)

        release_run_lock(db, run_id, "PASS",
                         races=races_done, runners=runners_done, results=reviews_done)

    except Exception as exc:
        log.exception("Fatal error in sigma loop closer")
        release_run_lock(db, run_id, "FAIL", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        default=str(date.today()),
        help="Date to reconcile (YYYY-MM-DD). Defaults to today.",
    )
    args = parser.parse_args()
    main(args.date)
