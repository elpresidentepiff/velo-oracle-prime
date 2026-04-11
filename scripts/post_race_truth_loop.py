"""
VÉLØ Post-Race Truth Loop
==========================
Layer 4 of the VÉLØ organism — the memory organ.

For every scored race, records four truth dimensions:
  1. core_miss_type   — what did the organism get wrong?
  2. horse_state_truth — were state tags directionally correct vs finish?
  3. gate_truth        — did TIE v3 gate help or hurt?
  4. archetype_truth   — did the race behave like the assigned archetype?

All truth rules are explicit and documented inline. No vibes. No black box.
"Correct" always means directionally verifiable against actual finish position.

Reads from:
  velo_verdicts   — predictions with full_analysis JSONB (state, gate, archetype)
  sigma_audits    — reconciled outcomes (WIN / PLACED / MISS / NO_RESULT)
  Racing API      — optional live fetch for races not yet in sigma_audits

Writes to:
  race_truth_audits — one row per race (upsert on race_id)
  Supabase view: velo_truth_rollup — weekly KPI aggregation

Requires:
  supabase/migrations/20260405_004_race_truth_audits.sql applied in Supabase

Usage:
    python scripts/post_race_truth_loop.py [--date YYYY-MM-DD]
    python scripts/post_race_truth_loop.py --rollup [--days 7]
    python scripts/post_race_truth_loop.py --date 2026-04-05 --dry-run
    python scripts/post_race_truth_loop.py --date 2026-04-05 --fetch-missing
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Credentials ───────────────────────────────────────────────────────────────

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {
    "apikey":        SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

RACING_USER = os.getenv("RACING_API_USERNAME", "")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "")
RACING_BASE = "https://api.theracingapi.com/v1"
RACING_HEADERS = {
    "Authorization": "Basic " + base64.b64encode(
        f"{RACING_USER}:{RACING_PASS}".encode()
    ).decode(),
    "User-Agent": "Mozilla/5.0",
    "Accept":     "application/json",
}

TODAY = date.today().isoformat()


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(path: str) -> list:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1{path}",
        headers={**SB_HEADERS, "Prefer": ""},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def sb_upsert(table: str, data: dict | list, on_conflict: str) -> bool:
    url = f"{SB_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    body = json.dumps(data).encode()
    headers = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except urllib.error.HTTPError as e:
        print(f"  [SB UPSERT FAIL] {table}: HTTP {e.code} — {e.read()[:200]}")
        return False
    except Exception as e:
        print(f"  [SB UPSERT FAIL] {table}: {e}")
        return False


# ── Racing API helper ─────────────────────────────────────────────────────────

def racing_get(path: str) -> dict:
    req = urllib.request.Request(f"{RACING_BASE}{path}", headers=RACING_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def fetch_results_for_date(race_date: str) -> dict[str, dict]:
    """
    Fetch Racing API results for a date. Returns dict keyed by race_id.

    Each value: {winner_id, winner_sp, top3_ids, finish_positions: {horse_id: pos}}
    """
    cache_path = ROOT / "data" / f"results_{race_date.replace('-','_')}.json"
    if cache_path.exists() and cache_path.stat().st_size > 200:
        raw = json.loads(cache_path.read_text())
    else:
        try:
            raw = racing_get(f"/results?start_date={race_date}&end_date={race_date}&limit=50")
            cache_path.write_text(json.dumps(raw, indent=2))
        except Exception as e:
            print(f"  [RACING API FAIL] fetching results for {race_date}: {e}")
            return {}

    out: dict[str, dict] = {}
    for race in raw.get("results", []):
        rid = race.get("race_id") or race.get("id", "")
        if not rid:
            continue
        runners = race.get("runners", [])
        sorted_r = sorted(
            [r for r in runners if str(r.get("position", "")).isdigit()],
            key=lambda r: int(r["position"]),
        )
        top3 = sorted_r[:3]
        winner = sorted_r[0] if sorted_r else {}
        finish_pos = {r.get("horse_id", ""): int(r["position"]) for r in sorted_r if r.get("horse_id")}
        out[rid] = {
            "winner_id":       winner.get("horse_id", ""),
            "winner_sp":       float(winner.get("sp_dec") or 0),
            "winner_horse":    winner.get("horse", "?"),
            "top3_ids":        [r.get("horse_id", "") for r in top3],
            "finish_positions": finish_pos,
        }
    return out


# ── Extract helpers ───────────────────────────────────────────────────────────

def _parse_full_analysis(verdict: dict) -> list[dict]:
    """Return full_analysis as a list of runner dicts."""
    raw = verdict.get("full_analysis")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


def _get_top_runner(verdict: dict) -> dict:
    """Return the top runner dict from full_analysis, or empty dict."""
    fa = _parse_full_analysis(verdict)
    return fa[0] if fa else {}


def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _safe_bool(v, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "1", "yes")


# ── Truth Rule 1: Core miss type ──────────────────────────────────────────────
# Rules evaluated in priority order — first match wins.
# Labels match the vocabulary defined in the user spec.

def evaluate_core_miss_type(
    outcome: str,                  # WIN | PLACED | MISS | NO_RESULT
    tier: str,                     # A | B | C | D | X
    archetype: str | None,         # Structure | Compression | PrepRelease | PublicTrap | Chaos
    suppression: bool,             # archetype_suppression from verdict
    trap_flag: bool,               # archetype_trap_flag from verdict
    winner_sp: float,              # actual winner starting price
    top_was_fav: bool,             # was our top pick the market favourite?
    gate_fired: bool,
) -> str:
    """
    Hard-rule classification of what went wrong (or right).

    Priority:
      1. clean_hit          — top pick won, no suppression active
      2. over_suppressed    — top pick won BUT we said suppress (PublicTrap → pass)
      3. right_horse_wrong_tier — top pick placed, but tier was A (should have been B/EW)
      4. false_public_trap  — assigned PublicTrap, top pick won (trap call wrong)
      5. under_suppressed   — didn't call trap, outcome MISS, obvious fav won
      6. missed_public_trap — outcome MISS, winner was very short fav, we picked non-fav
      7. false_prep_release — assigned PrepRelease, outcome MISS
      8. false_chaos        — tier X (chaos assigned), but a clear winner emerged at short SP
      9. missed_chaos       — outcome MISS, winner was a large outsider (≥14 SP)
      10. wrong_top_horse   — outcome MISS, no special pattern (catch-all)
    """
    if outcome == "WIN":
        if suppression:
            # We told people not to back it — horse won anyway
            return "over_suppressed"
        return "clean_hit"

    if outcome == "PLACED":
        if tier == "A":
            # A-STRIKE means we said back-to-win; horse only placed
            # EW would have been the right call
            return "right_horse_wrong_tier"
        # Placed at non-A tier is broadly acceptable — not a failure pattern
        return "clean_hit"  # treat PLACED as success for archetype/gate eval

    if outcome == "NO_RESULT":
        return "no_result"

    # outcome == MISS from here on
    if archetype == "PublicTrap" and not suppression:
        # We said trap but horse wasn't suppressed — internal inconsistency flag
        return "false_public_trap"

    if archetype == "PublicTrap":
        # We said trap (suppress). Top horse missed. Suppression was irrelevant
        # (we weren't going to back it anyway). Check if trap call itself was right
        # — the "trap" horse was not our recommended pick, so the miss is just a miss.
        return "false_public_trap" if winner_sp >= 6.0 else "wrong_top_horse"

    if suppression and outcome == "MISS":
        # We suppressed and the horse missed — suppression was correct but we still lost
        return "under_suppressed"

    if not top_was_fav and winner_sp <= 2.5:
        # We picked a non-fav, the odds-on shot won — we missed the obvious horse
        return "missed_public_trap"

    if archetype == "PrepRelease":
        return "false_prep_release"

    if tier == "X":
        # We said chaos (passed). If a clear winner emerged at short SP, chaos was wrong.
        if winner_sp <= 5.0:
            return "false_chaos"
        return "wrong_top_horse"

    if winner_sp >= 14.0:
        # Big outsider won — race was actually chaotic, we didn't read it
        return "missed_chaos"

    return "wrong_top_horse"


# ── Truth Rule 2: Horse-state truth ───────────────────────────────────────────
# For each state tag: was it directionally correct vs actual finish position?
#
# Proxy: positive state → expect WIN or PLACED. Neutral/negative → no prediction.
# Threshold: "placed" means top 3 in field of 7+, top 2 in smaller fields.

_NEUTRAL_STATE_VALUES = {
    "readiness_state":   "cold",
    "release_state":     "conditioning",
    "rest_pattern":      "neutral",
    "class_move_state":  "neutral",
    "stable_heat":       "cold",
    "jockey_signal":     "neutral",
    "market_state":      "ignored",
    "race_fit_state":    "adequate",
    "chaos_exposure":    "low",
}

_POSITIVE_STATE_VALUES = {
    "readiness_state":   {"warming", "primed"},
    "release_state":     {"hidden", "release_candidate"},
    "rest_pattern":      {"fresh"},
    "class_move_state":  {"drop", "engineered_drop"},
    "stable_heat":       {"warm", "hot"},
    "jockey_signal":     {"positive", "strong_positive"},
    "market_state":      {"quietly_backed"},
    "race_fit_state":    {"strong"},
}

_NEGATIVE_STATE_VALUES = {
    "readiness_state":  set(),       # cold is neutral; no negative below cold
    "release_state":    set(),
    "rest_pattern":     {"over_rested", "rebound"},  # directionally uncertain
    "class_move_state": {"rise"},    # class rise = harder race → expect worse result
    "stable_heat":      set(),
    "jockey_signal":    {"negative"},
    "market_state":     {"obvious", "drifting"},
    "race_fit_state":   {"weak"},
    "chaos_exposure":   {"medium", "high"},
}


def evaluate_horse_state_truth(
    horse_state: dict,  # from full_analysis[0].horse_state or top_horse_* columns
    outcome: str,       # WIN | PLACED | MISS
) -> dict[str, str]:
    """
    For each of the 9 state dimensions, return:
      "correct"               — positive tag fired, horse placed/won
      "wrong"                 — positive tag fired, horse missed
      "correct_negative"      — negative tag fired, horse missed (correct warning)
      "wrong_negative"        — negative tag fired, horse placed/won (wrong warning)
      "insufficient_evidence" — neutral tag or no data; no directional prediction made
    """
    if not horse_state or outcome == "NO_RESULT":
        return {k: "insufficient_evidence" for k in _NEUTRAL_STATE_VALUES}

    placed = outcome in ("WIN", "PLACED")
    result: dict[str, str] = {}

    for dim, neutral_val in _NEUTRAL_STATE_VALUES.items():
        val = horse_state.get(dim) or neutral_val

        if val in _POSITIVE_STATE_VALUES.get(dim, set()):
            result[dim] = "correct" if placed else "wrong"

        elif val in _NEGATIVE_STATE_VALUES.get(dim, set()):
            # Negative tag: we expect the horse NOT to place
            result[dim] = "correct_negative" if not placed else "wrong_negative"

        else:
            result[dim] = "insufficient_evidence"

    return result


# ── Truth Rule 3: Gate truth ──────────────────────────────────────────────────

def evaluate_gate_truth(
    top_runner: dict,
    outcome: str,
) -> dict:
    """
    Did the TIE v3 gate help or hurt?

    gate_helped  — gate fired an upgrade or EW flag, horse placed/won
    gate_hurt    — gate fired an upgrade, horse missed (we over-promoted)
    gate_neutral — gate did not fire, or no upgrade applied
    """
    gate_fired      = _safe_bool(top_runner.get("tie_gate_fires"))
    gate_upgrade    = top_runner.get("tie_gate_tier_upgrade")  # e.g. "B" or None
    gate_ew         = _safe_bool(top_runner.get("tie_gate_ew_flag"))
    gate_signals    = top_runner.get("tie_gate_signals") or []
    gate_signal_n   = int(top_runner.get("tie_gate_signal_count") or 0)

    placed = outcome in ("WIN", "PLACED")

    if not gate_fired:
        outcome_label = "gate_neutral"
    elif gate_upgrade:
        # Upgrade fired — this is the high-stakes gate action
        outcome_label = "gate_helped" if placed else "gate_hurt"
    elif gate_ew:
        # EW flag only — softer action
        outcome_label = "gate_helped" if placed else "gate_hurt"
    else:
        outcome_label = "gate_neutral"

    return {
        "gate_fired":          gate_fired,
        "gate_upgrade_applied": gate_upgrade is not None,
        "gate_upgrade_tier":   gate_upgrade,
        "gate_ew_flag":        gate_ew,
        "gate_signal_count":   gate_signal_n,
        "gate_signals":        gate_signals,
        "gate_outcome":        outcome_label,
        "gate_reason_truth":   f"upgrade={gate_upgrade} ew={gate_ew} signals={gate_signal_n} → {outcome_label}",
    }


# ── Truth Rule 4: Archetype truth ─────────────────────────────────────────────

def evaluate_archetype_truth(
    assigned_archetype: str | None,
    outcome: str,
    winner_sp: float,
    tier: str,
    finish_pos: int | None,
    suppression: bool,
) -> dict:
    """
    Did the race behave like the archetype we assigned?

    Inference of "actual behavior" from hard signals:
      Structure   — top pick won cleanly at moderate-short odds
      PrepRelease — top pick placed AND had strong prep indicators (outcome is our proxy)
      Compression — top pick placed at a class-drop race (outcome proxy)
      PublicTrap  — top pick missed AND actual winner was very short fav
      Chaos       — top pick missed AND actual winner was a large outsider (SP ≥ 12)

    Match: assigned archetype aligns with inferred behavior.
    We record both assigned and inferred so mismatches are learnable.
    """
    placed = outcome in ("WIN", "PLACED")

    # ── Infer actual race behavior ─────────────────────────────────────────────
    if placed and not suppression:
        if finish_pos == 1:
            inferred = "Structure"   # top pick won — structural result
        else:
            inferred = "PrepRelease"  # top pick placed but didn't win — prep/value pick
    elif not placed and winner_sp <= 2.5:
        inferred = "PublicTrap"   # obvious fav won, we missed it
    elif not placed and winner_sp >= 12.0:
        inferred = "Chaos"        # outsider won — unpredictable race
    elif not placed and tier == "X":
        inferred = "Chaos"        # chaos was assigned AND we were right to pass
    elif suppression and placed:
        inferred = "PublicTrap"   # we said trap, horse still won/placed — wrong trap call
    else:
        inferred = "Structure"    # default: structured miss, no special pattern

    # ── Evaluate match ────────────────────────────────────────────────────────
    # Broad groupings for match evaluation (some archetypes are close siblings)
    _match_groups = {
        "Structure":   {"Structure"},
        "Compression": {"Compression", "PrepRelease"},   # both are value/setup plays
        "PrepRelease": {"PrepRelease", "Compression"},
        "PublicTrap":  {"PublicTrap"},
        "Chaos":       {"Chaos"},
    }

    match = inferred in _match_groups.get(assigned_archetype or "", {assigned_archetype})

    # Per-archetype correctness label
    if assigned_archetype == "PublicTrap":
        if outcome == "MISS" and winner_sp <= 3.0:
            correctness = "correct"   # we called trap, horse lost, short fav won as expected
        elif outcome == "MISS":
            correctness = "insufficient_evidence"  # horse lost but not to obvious fav
        else:
            correctness = "wrong"     # we called trap, horse won/placed
    elif assigned_archetype in ("PrepRelease", "Compression"):
        correctness = "correct" if placed else "wrong"
    elif assigned_archetype == "Structure":
        correctness = "correct" if outcome == "WIN" else ("insufficient_evidence" if placed else "wrong")
    elif assigned_archetype == "Chaos":
        if tier == "X":
            # We passed. Was passing right?
            # "Right" if winner was outsider (genuine chaos) or close race
            correctness = "correct" if winner_sp >= 8.0 else "wrong"
        else:
            correctness = "insufficient_evidence"
    else:
        correctness = "insufficient_evidence"

    return {
        "assigned_archetype": assigned_archetype,
        "inferred_archetype": inferred,
        "archetype_match":    match,
        "archetype_truth":    correctness,
        "trap_correct":       assigned_archetype == "PublicTrap" and correctness == "correct",
        "compression_correct": assigned_archetype == "Compression" and correctness == "correct",
        "prep_release_correct": assigned_archetype == "PrepRelease" and correctness == "correct",
        "chaos_correct":       assigned_archetype == "Chaos" and correctness == "correct",
    }


# ── Main audit function ───────────────────────────────────────────────────────

def audit_race(verdict: dict, sigma: dict | None, result: dict | None) -> dict | None:
    """
    Evaluate all four truth dimensions for one race.

    Parameters
    ----------
    verdict : dict — one row from velo_verdicts (with full_analysis JSONB)
    sigma   : dict | None — one row from sigma_audits (may be None if not yet reconciled)
    result  : dict | None — Racing API result (may be None if fetch skipped)

    Returns
    -------
    dict — ready to upsert to race_truth_audits, or None if outcome unavailable
    """
    race_id = verdict.get("race_id", "")

    # ── Resolve outcome ───────────────────────────────────────────────────────
    if sigma:
        outcome      = sigma.get("outcome") or "NO_RESULT"
        finish_pos   = sigma.get("top_pick_position")
        winner_id    = sigma.get("actual_winner_id") or ""
        winner_sp    = _safe_float(sigma.get("actual_winner_sp"))
    elif result:
        # Sigma missing — derive from Racing API result
        top_horse_id = verdict.get("top_rank_horse_id") or ""
        winner_id    = result.get("winner_id", "")
        winner_sp    = _safe_float(result.get("winner_sp"))
        finish_pos   = result["finish_positions"].get(top_horse_id) if top_horse_id else None
        top3_ids     = result.get("top3_ids", [])
        if top_horse_id == winner_id:
            outcome = "WIN"
        elif top_horse_id in top3_ids:
            outcome = "PLACED"
        elif top_horse_id:
            outcome = "MISS"
        else:
            outcome = "NO_RESULT"
    else:
        # No outcome available — skip
        return None

    # ── Extract prediction data ───────────────────────────────────────────────
    top_runner        = _get_top_runner(verdict)
    tier              = verdict.get("decision_tier") or top_runner.get("decision_tier") or None
    archetype         = verdict.get("race_archetype") or top_runner.get("race_archetype")
    arch_conf         = verdict.get("archetype_confidence") or top_runner.get("archetype_confidence")
    suppression       = _safe_bool(verdict.get("archetype_suppression") or top_runner.get("archetype_suppression"))
    trap_flag         = _safe_bool(verdict.get("archetype_trap_flag") or top_runner.get("archetype_trap_flag"))
    vp_prob           = _safe_float(verdict.get("velo_prime_prob"))
    top_horse_id      = verdict.get("top_rank_horse_id") or top_runner.get("horse_id") or ""

    # Horse-state from nested horse_state dict (preferred) or top_horse_* columns
    hs = top_runner.get("horse_state") or {}
    if not hs:
        # Fall back to top_horse_* columns on verdict row
        hs = {
            "readiness_state":  verdict.get("top_horse_readiness_state"),
            "release_state":    verdict.get("top_horse_release_state"),
            "rest_pattern":     verdict.get("top_horse_rest_pattern"),
            "class_move_state": verdict.get("top_horse_class_move_state"),
            "stable_heat":      verdict.get("top_horse_stable_heat"),
            "jockey_signal":    verdict.get("top_horse_jockey_signal"),
            "market_state":     verdict.get("top_horse_market_state"),
            "race_fit_state":   verdict.get("top_horse_race_fit_state"),
            "chaos_exposure":   verdict.get("top_horse_chaos_exposure"),
        }

    top_was_fav = _safe_bool(top_runner.get("is_fav"))
    gate_fired  = _safe_bool(top_runner.get("tie_gate_fires"))

    # Generated_at → race_date
    raw_date = verdict.get("generated_at") or ""
    race_date = raw_date[:10] if raw_date else None

    # ── Evaluate four truth dimensions ────────────────────────────────────────
    finish_pos_int = int(finish_pos) if finish_pos is not None else None

    core_miss = evaluate_core_miss_type(
        outcome      = outcome,
        tier         = tier,
        archetype    = archetype,
        suppression  = suppression,
        trap_flag    = trap_flag,
        winner_sp    = winner_sp,
        top_was_fav  = top_was_fav,
        gate_fired   = gate_fired,
    )

    state_truth = evaluate_horse_state_truth(hs, outcome)

    gate_truth = evaluate_gate_truth(top_runner, outcome)

    arch_truth = evaluate_archetype_truth(
        assigned_archetype = archetype,
        outcome            = outcome,
        winner_sp          = winner_sp,
        tier               = tier,
        finish_pos         = finish_pos_int,
        suppression        = suppression,
    )

    # ── Assemble truth_payload ────────────────────────────────────────────────
    truth_payload = {
        "horse_state_truth":  state_truth,
        "gate_truth":         gate_truth,
        "archetype_truth":    arch_truth,
        "evidence": {
            "outcome":        outcome,
            "finish_pos":     finish_pos_int,
            "winner_id":      winner_id,
            "winner_sp":      winner_sp,
            "vp_prob":        vp_prob,
            "tier":           tier,
            "suppression":    suppression,
            "top_was_fav":    top_was_fav,
        },
    }

    return {
        "race_id":               race_id,
        "race_date":             race_date,
        "generated_at":          datetime.utcnow().isoformat(),
        # Prediction snapshot
        "decision_tier":          tier,
        "assigned_archetype":     archetype,
        "archetype_confidence":   arch_conf,
        "velo_prime_prob":        vp_prob if vp_prob > 0 else None,
        "top_horse_id":           top_horse_id or None,
        "gate_fired":             gate_truth["gate_fired"],
        "gate_upgrade_applied":   gate_truth["gate_upgrade_applied"],
        # Actual outcome
        "result_outcome":         outcome,
        "finish_position":        finish_pos_int,
        "actual_winner_id":       winner_id or None,
        "actual_winner_sp":       winner_sp if winner_sp > 0 else None,
        # Truth summaries
        "core_miss_type":         core_miss,
        "gate_outcome":           gate_truth["gate_outcome"],
        "archetype_match":        arch_truth["archetype_match"],
        "archetype_truth":        arch_truth["archetype_truth"],
        # Full payload
        "truth_payload":          truth_payload,
    }


# ── Rollup report ─────────────────────────────────────────────────────────────

def generate_rollup(days: int = 7) -> str:
    """
    Query race_truth_audits for the last N days and generate a text summary.
    Answers the 8 questions from the weekly report spec.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    try:
        rows = sb_get(
            f"/race_truth_audits"
            f"?select=core_miss_type,gate_outcome,archetype_match,archetype_truth,"
            f"assigned_archetype,result_outcome,truth_payload,decision_tier"
            f"&race_date=gte.{since}"
            f"&result_outcome=neq.NO_RESULT"
            f"&order=race_date.desc"
        )
    except Exception as e:
        return f"[ROLLUP FAIL] Could not query race_truth_audits: {e}"

    if not rows:
        return f"[ROLLUP] No audited races found in last {days} days (since {since})."

    n = len(rows)

    # 1. Most common miss type
    miss_counts: Counter = Counter(r["core_miss_type"] for r in rows if r.get("core_miss_type"))
    most_common_miss = miss_counts.most_common(3)

    # 2. Win + place rates
    wins   = sum(1 for r in rows if r.get("result_outcome") == "WIN")
    placed = sum(1 for r in rows if r.get("result_outcome") in ("WIN", "PLACED"))

    # 3. Archetype performance (place rate by archetype)
    arch_total:   Counter = Counter()
    arch_placed:  Counter = Counter()
    arch_correct: Counter = Counter()
    for r in rows:
        arch = r.get("assigned_archetype") or "Unknown"
        arch_total[arch] += 1
        if r.get("result_outcome") in ("WIN", "PLACED"):
            arch_placed[arch] += 1
        if r.get("archetype_truth") == "correct":
            arch_correct[arch] += 1

    arch_place_rate = {
        a: arch_placed[a] / arch_total[a]
        for a in arch_total if arch_total[a] >= 3
    }
    best_arch  = max(arch_place_rate, key=arch_place_rate.get, default="n/a")
    worst_arch = min(arch_place_rate, key=arch_place_rate.get, default="n/a")

    # 4. State tag reliability
    tag_correct: Counter = Counter()
    tag_total:   Counter = Counter()
    for r in rows:
        tp = r.get("truth_payload")
        if isinstance(tp, dict):
            hs_truth = tp.get("horse_state_truth") or {}
        elif isinstance(tp, str):
            try:
                hs_truth = json.loads(tp).get("horse_state_truth") or {}
            except Exception:
                hs_truth = {}
        else:
            hs_truth = {}
        for dim, verdict_val in hs_truth.items():
            if verdict_val in ("correct", "wrong"):
                tag_total[dim] += 1
                if verdict_val == "correct":
                    tag_correct[dim] += 1

    tag_accuracy = {
        dim: tag_correct[dim] / tag_total[dim]
        for dim in tag_total if tag_total[dim] >= 3
    }
    most_reliable  = max(tag_accuracy, key=tag_accuracy.get, default="n/a")
    most_misleading = min(tag_accuracy, key=tag_accuracy.get, default="n/a")

    # 5. Gate performance
    gate_helps   = sum(1 for r in rows if r.get("gate_outcome") == "gate_helped")
    gate_hurts   = sum(1 for r in rows if r.get("gate_outcome") == "gate_hurt")
    gate_fires   = sum(1 for r in rows if r.get("gate_fired"))
    gate_upgrade = sum(1 for r in rows if r.get("gate_upgrade_applied"))

    # 6. PublicTrap precision
    trap_rows    = [r for r in rows if r.get("assigned_archetype") == "PublicTrap"]
    trap_correct_n = sum(1 for r in trap_rows if r.get("archetype_truth") == "correct")
    trap_acc     = trap_correct_n / len(trap_rows) if trap_rows else None

    # ── Format report ─────────────────────────────────────────────────────────
    lines = [
        f"VÉLØ WEEKLY TRUTH REPORT — last {days} days (since {since})",
        "=" * 60,
        f"Races audited:    {n}",
        f"Win rate:         {wins/n:.1%}  ({wins}/{n})",
        f"Place rate:       {placed/n:.1%}  ({placed}/{n})",
        "",
        "MOST COMMON MISS TYPE",
        *[f"  {miss}: {count} ({count/n:.0%})" for miss, count in most_common_miss],
        "",
        "ARCHETYPE PERFORMANCE (place rate, min 3 races)",
        *[f"  {a}: {arch_place_rate[a]:.0%} ({arch_placed[a]}/{arch_total[a]})" for a in sorted(arch_place_rate)],
        f"  Best:  {best_arch}  ({arch_place_rate.get(best_arch,0):.0%})",
        f"  Worst: {worst_arch}  ({arch_place_rate.get(worst_arch,0):.0%})",
        "",
        "STATE TAG RELIABILITY (directional accuracy, min 3 samples)",
        *[f"  {dim}: {tag_accuracy[dim]:.0%} ({tag_correct[dim]}/{tag_total[dim]})" for dim in sorted(tag_accuracy)],
        f"  Most reliable:   {most_reliable}  ({tag_accuracy.get(most_reliable,0):.0%})",
        f"  Most misleading: {most_misleading}  ({tag_accuracy.get(most_misleading,0):.0%})",
        "",
        "TIE v3 GATE",
        f"  Fires:    {gate_fires}",
        f"  Upgrades: {gate_upgrade}",
        f"  Helped:   {gate_helps}",
        f"  Hurt:     {gate_hurts}",
        f"  Precision: {gate_helps/(gate_helps+gate_hurts):.0%}" if (gate_helps + gate_hurts) > 0 else "  Precision: n/a",
        "",
        "PUBLIC TRAP CALLS",
        f"  Total:   {len(trap_rows)}",
        f"  Correct: {trap_correct_n}",
        f"  Accuracy: {trap_acc:.0%}" if trap_acc is not None else "  Accuracy: n/a",
        "=" * 60,
    ]
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Post-Race Truth Loop")
    parser.add_argument("--date",         default=TODAY,      help="Race date (YYYY-MM-DD)")
    parser.add_argument("--rollup",       action="store_true", help="Generate weekly rollup report")
    parser.add_argument("--days",         type=int, default=7, help="Rollup window in days (default 7)")
    parser.add_argument("--dry-run",      action="store_true", help="Evaluate but do not write to DB")
    parser.add_argument("--fetch-missing", action="store_true",
                        help="Fetch results from Racing API for races not yet in sigma_audits")
    args = parser.parse_args()

    # ── Rollup mode ───────────────────────────────────────────────────────────
    if args.rollup:
        print(f"\nGenerating {args.days}-day truth rollup...")
        report = generate_rollup(days=args.days)
        print(report)
        return

    race_date = args.date
    print(f"\nVÉLØ POST-RACE TRUTH LOOP — {race_date}")
    print("=" * 60)

    if not SB_URL or not SB_KEY:
        print("  ABORT: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in .env")
        sys.exit(1)

    # ── STEP 1: Load verdicts ─────────────────────────────────────────────────
    print("\nSTEP 1: Load verdicts from velo_verdicts")
    # Use select=* so the query works regardless of which Layer 1-3 migrations
    # have been applied. Columns from pending migrations (002: top_horse_* state
    # columns, 003: archetype columns) are simply absent from the response when
    # not yet deployed. Fallback paths in audit_race() read from full_analysis
    # JSONB instead — no data is lost.
    verdicts_raw = sb_get(
        f"/velo_verdicts"
        f"?select=*"
        f"&generated_at=gte.{race_date}T00:00:00"
        f"&generated_at=lt.{race_date}T23:59:59"
        f"&order=generated_at"
    )
    print(f"  Verdicts loaded: {len(verdicts_raw)}")
    if not verdicts_raw:
        print("  ABORT: no verdicts found for this date")
        sys.exit(0)

    # Deduplicate: keep latest verdict per race_id
    verdicts: dict[str, dict] = {}
    for v in verdicts_raw:
        rid = v["race_id"]
        if rid not in verdicts or (v.get("generated_at") or "") > (verdicts[rid].get("generated_at") or ""):
            verdicts[rid] = v
    print(f"  Unique races: {len(verdicts)}")

    # ── STEP 2: Load sigma outcomes ───────────────────────────────────────────
    print("\nSTEP 2: Load outcomes from sigma_audits")
    sigma_raw = sb_get(
        f"/sigma_audits"
        f"?select=race_id,outcome,top_pick_position,actual_winner_id,actual_winner_sp,miss_reason"
        f"&date=eq.{race_date}"
        f"&event_type=eq.sigma_reconciliation"
    )
    sigma_by_race: dict[str, dict] = {r["race_id"]: r for r in sigma_raw}
    print(f"  Outcomes from sigma_audits: {len(sigma_by_race)}")

    # ── STEP 3: Fetch missing results from Racing API ─────────────────────────
    missing_races = [rid for rid in verdicts if rid not in sigma_by_race]
    api_results: dict[str, dict] = {}

    if missing_races:
        print(f"\nSTEP 3: {len(missing_races)} races without sigma outcome")
        if args.fetch_missing:
            print("  Fetching results from Racing API...")
            api_results = fetch_results_for_date(race_date)
            print(f"  API results available: {len(api_results)}")
        else:
            print("  Skipping API fetch — use --fetch-missing to enable")
    else:
        print(f"\nSTEP 3: All races have sigma outcomes — no API fetch needed")

    # ── STEP 4: Evaluate truth ────────────────────────────────────────────────
    print("\nSTEP 4: Evaluate truth")
    records = []
    skipped = []

    for race_id, verdict in verdicts.items():
        sigma  = sigma_by_race.get(race_id)
        result = api_results.get(race_id)

        record = audit_race(verdict, sigma, result)
        if record is None:
            skipped.append(race_id)
            src = "sigma" if sigma else ("api_result" if result else "no_outcome")
            print(f"  SKIP  {race_id}  — {src} unavailable")
            continue

        records.append(record)
        miss = record["core_miss_type"]
        arch = record["assigned_archetype"] or "?"
        gate = record["gate_outcome"]
        print(
            f"  {'AUDIT':<6}  {race_id:<40}  "
            f"outcome={record['result_outcome']:<8}  "
            f"miss={miss:<25}  arch={arch:<15}  gate={gate}"
        )

    print(f"\n  Evaluated: {len(records)}  Skipped: {len(skipped)}")

    if not records:
        print("  Nothing to write.")
        sys.exit(0)

    # ── STEP 5: Write to race_truth_audits ───────────────────────────────────
    if args.dry_run:
        print("\nSTEP 5: DRY RUN — not writing to DB")
        for r in records:
            print(f"  [DRY]  {r['race_id']}  →  core={r['core_miss_type']}  gate={r['gate_outcome']}")
        return

    print("\nSTEP 5: Write to race_truth_audits")
    ok = 0
    fail = 0
    for record in records:
        if sb_upsert("race_truth_audits", record, "race_id"):
            ok += 1
        else:
            fail += 1
            print(f"  FAIL: {record['race_id']}")

    print(f"  Written: {ok}  Failed: {fail}")

    # ── STEP 6: Summary ───────────────────────────────────────────────────────
    print("\nSTEP 6: Truth summary for this run")
    miss_counts: Counter = Counter(r["core_miss_type"] for r in records)
    gate_counts: Counter = Counter(r["gate_outcome"] for r in records)
    arch_miss:   Counter = Counter(
        r["assigned_archetype"] for r in records
        if r.get("result_outcome") == "MISS"
    )

    print(f"\n  Miss types:")
    for miss, count in miss_counts.most_common():
        print(f"    {miss:<30} {count}")

    print(f"\n  Gate outcomes:")
    for outcome_k, count in gate_counts.most_common():
        print(f"    {outcome_k:<25} {count}")

    print(f"\n  Misses by archetype:")
    for arch, count in arch_miss.most_common():
        print(f"    {arch:<20} {count}")

    print("\nDone.")


if __name__ == "__main__":
    main()
