"""
VÉLØ — Sigma Loop Closer
========================
Pulls today's results from Racing API, reconciles against stored verdicts,
populates race_results / runner_results / velo_post_race_reviews / sigma_audits.

Single-run guard via pipeline_runs table — aborts if a run is already in_progress.

Run: python scripts/close_sigma_loops.py [--date YYYY-MM-DD]
"""

import os
import sys
import json
import logging
import argparse
import uuid
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    Insert a pipeline_run row with status=in_progress.
    Returns run_id if acquired, None if a run is already in_progress.
    """
    # Check for stale/active runs for this type + date
    existing = (
        db.table("pipeline_runs")
        .select("id, status, started_at")
        .eq("run_type", RUN_TYPE)
        .eq("source_date", source_date)
        .eq("status", "in_progress")
        .execute()
    )
    if existing.data:
        run = existing.data[0]
        log.warning(
            "Run already in_progress (id=%s started_at=%s). Aborting.",
            run["id"], run["started_at"],
        )
        return None

    run_id = str(uuid.uuid4())
    db.table("pipeline_runs").insert({
        "id": run_id,
        "service_name": "velo_sigma_closer",
        "run_type": RUN_TYPE,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "source_date": source_date,
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development"),
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
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "races_processed": races,
        "runners_processed": runners,
        "results_processed": results,
        "error_message": error,
    }).eq("id", run_id).execute()
    log.info("Run lock released: %s → %s", run_id, status)


# ─────────────────────────────────────────────────────────────
# Racing API fetch
# ─────────────────────────────────────────────────────────────
def fetch_results(target_date: str) -> List[Dict]:
    """
    Fetch results from Racing API.
    Uses /v1/results/today for today, /v1/results?date=YYYY-MM-DD for past dates.
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
        url = f"{base}/v1/results"
        params = {"date": target_date}

    log.info("GET %s %s", url, params or "")
    resp = session.get(url, params=params, timeout=30)

    if resp.status_code == 402:
        log.error("Racing API returned 402 — subscription tier does not include results. "
                  "Upgrade to Standard/Pro plan.")
        return []
    if resp.status_code == 404:
        log.warning("No results found for %s (404)", target_date)
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

    # Signal attribution — forensic miss analysis
    signal_attribution: dict = {}
    miss_reason = None
    patch_note  = None

    if not top_pick_won:
        confidence = verdict.get("confidence_level", "")

        # Pull full_analysis for signal comparison
        raw_fa = verdict.get("full_analysis") or []
        if isinstance(raw_fa, str):
            try:
                raw_fa = json.loads(raw_fa)
            except Exception:
                raw_fa = []

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

    # Full review outcome
    selections = verdict.get("selections") or []
    placed_selections = []
    for sel in selections:
        horse_id = sel.get("horse_id", "")
        result = next((r for r in runners_result if r.get("horse_id") == horse_id), None)
        if result:
            placed_selections.append({
                "horse_id": horse_id,
                "position": result.get("position"),
                "sp": result.get("sp_dec"),
                "outcome": "win" if _safe_int(result.get("position")) == 1 else
                           "placed" if (_safe_int(result.get("position")) or 99) <= 3 else "miss",
            })

    review_outcome = {
        "outcome": outcome_label,
        "top_pick_position": top_pick_pos,
        "winner_id": winner_id,
        "winner_sp": winner_sp,
        "miss_reason": miss_reason,
        "patch_note": patch_note,
        "signal_attribution": signal_attribution,
        "selections_results": placed_selections,
        "verdict_confidence": verdict.get("confidence_level"),
        "verdict_score": float(verdict.get("top_rank_score", 0)),
    }

    notes = (
        f"{outcome_label}: {top_pick_id} pos={top_pick_pos}, "
        f"winner={winner_id}@{winner_sp}SP. "
        f"{'Patch: ' + patch_note if patch_note else ''}"
    )

    return {
        "verdict_id": verdict_id,
        "race_id": race_id,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "top_pick_won": top_pick_won,
        "top_pick_placed": top_pick_placed,
        "top_pick_position": top_pick_pos,
        "actual_winner_id": winner_id,
        "actual_winner_sp": winner_sp,
        "verdict_accuracy_score": accuracy,
        "review_outcome": review_outcome,
        "notes": notes[:500],
    }


def write_sigma_audit(db: Client, race_id: str, review: Dict, verdict: Dict) -> None:
    outcome = review["review_outcome"]
    db.table("sigma_audits").insert({
        "event_type": "post_race_review",
        "race_id": race_id,
        "horse_id": verdict.get("top_rank_horse_id"),
        "verdict_id": review["verdict_id"],
        "outcome": outcome.get("outcome"),
        "miss_reason": outcome.get("miss_reason"),
        "patch_note": outcome.get("patch_note"),
        "confidence_level": verdict.get("confidence_level"),
        "verdict_score": float(verdict.get("top_rank_score", 0)),
        "decision_tier": verdict.get("decision_tier"),
        "top_pick_position": review.get("top_pick_position"),
        "actual_winner_id": review.get("actual_winner_id"),
        "actual_winner_sp": review.get("actual_winner_sp"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


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
        # Check if exists
        existing = (
            db.table("learned_patterns")
            .select("id, occurrences, successful_predictions, first_observed")
            .eq("pattern_name", name)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            total_n    = (row["occurrences"] or 0) + n
            total_wins = (row["successful_predictions"] or 0) + wins
            new_sr     = round(total_wins / total_n, 4) if total_n else 0.0
            db.table("learned_patterns").update({
                "occurrences":            total_n,
                "successful_predictions": total_wins,
                "success_rate":           new_sr,
                "confidence_level":       round(min(total_n / 50, 1.0), 4),
                "conditions":             conditions,
                "description":            desc,
                "last_observed":          now,
                "updated_at":             now,
                "is_active":              True,
            }).eq("id", row["id"]).execute()
        else:
            db.table("learned_patterns").insert({
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
            }).execute()
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

    log.info("Learned patterns written: %d", written)
    return written


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
        rows = (
            db.table("velo_verdicts")
            .select("id, race_id, confidence_level, top_rank_horse_id, top_rank_score, selections, decision_tier, full_analysis, velo_prime_prob, place_prob, improvement_score, market_deception_score")
            .execute()
        )
        # Filter to verdicts whose race is on target_date
        race_rows = (
            db.table("races")
            .select("race_id, date")
            .eq("date", target_date)
            .execute()
        )
        dated_race_ids = {r["race_id"] for r in race_rows.data}
        verdicts = [
            {**v, "verdict_id": v["id"]}
            for v in rows.data
            if v["race_id"] in dated_race_ids
        ]
        log.info("Found %d verdicts for %s", len(verdicts), target_date)

        if not verdicts:
            log.warning("No verdicts found for %s — nothing to reconcile", target_date)
            release_run_lock(db, run_id, "completed", 0, 0, 0)
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
            release_run_lock(db, run_id, "partial", 0, 0, 0,
                             error="Racing API returned 0 results")
            return

        # Step 4: Match, store, review
        for api_race in api_results:
            race_id = api_race.get("race_id") or api_race.get("id", "")
            if not race_id:
                continue

            # Only store results for races we have in our races table (FK constraint)
            if race_id not in dated_race_ids:
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
            tg_status = "PASS" if wins > 0 else ("FRAME" if placed > 0 else "MISS")
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

        release_run_lock(db, run_id, "completed",
                         races=races_done, runners=runners_done, results=reviews_done)

    except Exception as exc:
        log.exception("Fatal error in sigma loop closer")
        release_run_lock(db, run_id, "failed", error=str(exc))
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
