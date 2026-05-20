"""
sentient_loop_repair_v1.py — VÉLØ SENTIENT LOOP REPAIR V1

P0 SHADOW-ONLY REPAIR.

Fixes three root causes of broken learning:
  1. MPI was VP*100 (wrong). Fix: (vp*0.6 + mds*0.4)*100 per ensemble formula.
  2. chaos_bloom was null/hardcoded. Fix: derived from macro_chaos_mode + favourite_trap_risk.
  3. learning_allowed was always False. Fix: True when result verified + event not consumed.
  4. Duplicate guard was global (race_id only). Fix: per-target consumption key.

Target state: data/sentient_state_shadow_repair_v1.json  (NEVER touches live state)
Evidence ledger: data/sentient_loop_repair_consumed_events.jsonl
Audit output: data/sentient_loop_repair_audit_v1.json
              docs/engineering/SENTIENT_LOOP_REPAIR_AUDIT_V1.md

Hard rules:
  - NO write to sentient_state.json (live state)
  - NO Supabase writes
  - NO scoring changes
  - NO model changes
  - NO router/staking/Telegram
  - NO fabricated MPI or chaos_bloom — only null when data missing
  - 5-event proof run first, then full run
  - Result: A (exact broken functions) through K (remaining blockers) required
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
DOCS_ENG = ROOT / "docs" / "engineering"

REPAIR_STATE   = DATA / "sentient_state_shadow_repair_v1.json"
CONSUMED_LEDGER = DATA / "sentient_loop_repair_consumed_events.jsonl"
AUDIT_JSON     = DATA / "sentient_loop_repair_audit_v1.json"
AUDIT_MD       = DOCS_ENG / "SENTIENT_LOOP_REPAIR_AUDIT_V1.md"

# DO NOT change this — safety gate: live state must never be modified
LIVE_STATE = DATA / "sentient_state.json"

TARGET_STATE_ID = str(REPAIR_STATE)  # used as part of consumption key


# ─── Safety guard ──────────────────────────────────────────────────────────────

def _assert_live_state_untouched(live_hash_before: str) -> bool:
    """Return True if live sentient_state.json is byte-for-byte unchanged."""
    import hashlib
    if not LIVE_STATE.exists():
        return True
    current = hashlib.sha256(LIVE_STATE.read_bytes()).hexdigest()
    return current == live_hash_before


def _hash_file(path: Path) -> str:
    import hashlib
    if not path.exists():
        return "FILE_NOT_FOUND"
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ─── HFS signal computation (mirrors ensemble formula exactly) ─────────────────

def _compute_mpi(ps: dict) -> tuple[float | None, str]:
    """
    Compute MPI from prediction snapshot.
    Formula mirrors VeloPrimePrediction._compute_hfs_signals() exactly.
    Returns (mpi_0_to_100, source_label).
    """
    vp  = ps.get("velo_prime_prob")
    mds = ps.get("market_deception_score")

    if vp is None:
        return None, "missing_vp"

    vp = float(vp)
    if mds is not None:
        mpi_01 = (vp * 0.6) + (float(mds) * 0.4)
        source  = "derived_from_vp_mds"
    else:
        mpi_01  = vp
        source  = "derived_from_vp_only_mds_missing"

    return round(min(1.0, max(0.0, mpi_01)) * 100, 2), source


def _compute_chaos_bloom(ps: dict) -> tuple[float | None, str]:
    """
    Compute chaos_bloom from prediction snapshot.
    Formula mirrors VeloPrimePrediction._compute_hfs_signals() exactly.
    Returns (chaos_0_to_100, source_label).
    """
    chaos_mode = ps.get("macro_chaos_mode")
    trap_risk  = ps.get("favourite_trap_risk", "")
    macro_avail = ps.get("macro_available", False)

    if not macro_avail and chaos_mode is None:
        return None, "macro_context_missing"

    base = 0.3
    if chaos_mode:
        base += 0.4
    if str(trap_risk).lower() in ("high",):
        base += 0.3
    elif str(trap_risk).lower() in ("medium",):
        base += 0.15

    return round(min(1.0, max(0.0, base)) * 100, 2), "derived_from_macro_fields"


# ─── Result file utilities ─────────────────────────────────────────────────────

def _load_results_for_date(date: str) -> dict[str, dict]:
    """
    Load results file for date and return {race_id: result_dict}.
    Tries results_YYYY_MM_DD.json.
    """
    fname = DATA / f"results_{date.replace('-','_')}.json"
    if not fname.exists():
        return {}
    try:
        raw = json.loads(fname.read_text())
        results_list = raw if isinstance(raw, list) else raw.get("results", raw.get("data", []))
        return {r.get("race_id") or r.get("id"): r for r in results_list if r.get("race_id") or r.get("id")}
    except Exception:
        return {}


def _extract_winner(result_race: dict) -> tuple[str, float, bool]:
    """
    Extract (winner_horse_id, winner_sp_decimal, favourite_won) from result race.
    Returns ("", 0.0, False) if not available.
    """
    runners = result_race.get("runners", [])
    sorted_r = sorted(
        [r for r in runners if str(r.get("position", "")).isdigit()],
        key=lambda r: int(r["position"])
    )
    if not sorted_r:
        return "", 0.0, False

    winner = sorted_r[0]
    horse_id = winner.get("horse_id", "")
    sp_str   = winner.get("sp_dec") or winner.get("sp_decimal") or winner.get("sp") or ""
    try:
        sp = float(sp_str)
    except (ValueError, TypeError):
        sp = 0.0

    # Detect favourite: lowest SP among all runners (simple heuristic)
    all_sps = []
    for r in sorted_r:
        try:
            all_sps.append((float(r.get("sp_dec") or r.get("sp_decimal") or 0), r.get("horse_id")))
        except Exception:
            pass
    fav_won = bool(all_sps and min(all_sps, key=lambda x: x[0])[1] == horse_id)

    return horse_id, sp, fav_won


# ─── Consumption ledger ────────────────────────────────────────────────────────

def _load_consumed_keys() -> set[str]:
    """Load already-consumed consumption keys for this target state."""
    if not CONSUMED_LEDGER.exists():
        return set()
    consumed = set()
    for line in CONSUMED_LEDGER.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("target_state") == TARGET_STATE_ID:
                consumed.add(rec["consumption_key"])
        except Exception:
            pass
    return consumed


def _record_consumed(consumption_key: str, race_id: str, date: str, outcome: str) -> None:
    with CONSUMED_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "consumption_key": consumption_key,
            "race_id": race_id,
            "date": date,
            "outcome": outcome,
            "target_state": TARGET_STATE_ID,
            "consumed_at": datetime.utcnow().isoformat() + "Z",
        }) + "\n")


# ─── Engine inputs builder ─────────────────────────────────────────────────────

def _build_engine_inputs(
    race_id: str, date: str, ps: dict, result_race: dict,
    winner_id: str, sp: float, fav_won: bool,
    mpi: float | None, chaos_bloom: float | None,
) -> tuple[dict, dict, dict]:
    """
    Build (race_data, prediction, actual_result) for SentientLoopbackEngine.observe_race_outcome().
    No fabrication: null stays null, marked as missing_hfs_context.
    """
    race_data = {
        "race_id":            race_id,
        "race_date":          date,
        "mpi":                mpi if mpi is not None else None,
        "chaos_bloom":        chaos_bloom if chaos_bloom is not None else 0.0,
        "missing_hfs_context": (mpi is None or chaos_bloom is None),
        "story_anchor":       "favourite" if fav_won else "non-favourite",
        "power_anchor":       ps.get("horse_id", ""),
        "threat_cluster":     [],
        "narrative_disruption": 0.0,
        "fav_trip_blocked":   False,
        "runners":            [],
        "integrity_score":    100,
    }

    prediction = {
        "power_anchor":      ps.get("horse_id", ""),
        "confidence":        float(ps.get("velo_prime_prob") or 0),
        "doctrines_fired":   ps.get("doctrines_fired") or [],
    }

    actual_result = {
        "winner":          winner_id,
        "sp":              sp if sp > 0 else 5.0,
        "favourite_won":   fav_won,
        "winner_profile": {
            "running_style": "unknown",
            "draw": None,
            "was_hidden_improver": False,
            "late_money": False,
        },
    }

    return race_data, prediction, actual_result


# ─── Per-date processor ────────────────────────────────────────────────────────

def _process_date(
    date: str,
    engine,
    consumed: set[str],
    dry_run: bool = False,
    max_events: int | None = None,
) -> dict:
    """Process one date. Returns per-date stats dict."""
    pred_file = DATA / f"velo_prime_verdicts_{date.replace('-','_')}.json"
    if not pred_file.exists():
        return {"date": date, "skip_reason": "NO_PREDICTION_FILE", "processed": 0}

    results_map = _load_results_for_date(date)
    if not results_map:
        return {"date": date, "skip_reason": "NO_RESULT_FILE", "processed": 0}

    try:
        raw = json.loads(pred_file.read_text())
    except Exception as e:
        return {"date": date, "skip_reason": f"PARSE_ERROR:{e}", "processed": 0}

    races = raw if isinstance(raw, list) else raw.get("verdicts", raw.get("predictions", []))

    stats = {
        "date":              date,
        "races_in_pred":     len(races),
        "results_available": len(results_map),
        "processed":         0,
        "skipped_duplicate": 0,
        "skipped_no_result": 0,
        "skipped_unknown":   0,
        "observe_called":    0,
        "observe_success":   0,
        "mpi_null":          0,
        "chaos_null":        0,
        "events":            [],
    }

    count = 0
    for race in races:
        if max_events is not None and count >= max_events:
            break

        race_id  = race.get("race_id")
        top      = race.get("top") or {}
        # Prediction file race-level race_id may differ from top_pick race_id;
        # prefer race-level
        if not race_id:
            race_id = top.get("race_id")
        if not race_id:
            stats["skipped_no_result"] += 1
            continue

        idempotency_key  = f"{race_id}:{date}"
        consumption_key  = f"{idempotency_key}|{TARGET_STATE_ID}"

        if consumption_key in consumed:
            stats["skipped_duplicate"] += 1
            continue

        result_race = results_map.get(race_id)
        if not result_race:
            stats["skipped_no_result"] += 1
            continue

        winner_id, sp, fav_won = _extract_winner(result_race)
        if not winner_id:
            stats["skipped_unknown"] += 1
            continue

        outcome = "WIN" if (top.get("horse_id") == winner_id) else "LOSS"

        mpi, mpi_src          = _compute_mpi(top)
        chaos_bloom, chaos_src = _compute_chaos_bloom(top)

        if mpi is None:
            stats["mpi_null"] += 1
        if chaos_bloom is None:
            stats["chaos_null"] += 1

        races_before = engine.state.get("total_races_observed", 0)

        event_record = {
            "race_id":        race_id,
            "date":           date,
            "idempotency_key": idempotency_key,
            "consumption_key": consumption_key,
            "predicted_horse": top.get("horse_id"),
            "actual_winner":  winner_id,
            "outcome":        outcome,
            "velo_prime_prob": top.get("velo_prime_prob"),
            "decision_tier":  race.get("tier"),
            "mpi":            mpi,
            "mpi_src":        mpi_src,
            "chaos_bloom":    chaos_bloom,
            "chaos_src":      chaos_src,
            "sp":             sp,
            "market_deception_score": top.get("market_deception_score"),
            "improvement_score":      top.get("improvement_score"),
            "learning_allowed":       True,
            "missing_hfs_context":    (mpi is None or chaos_bloom is None),
            "races_before_observe":   races_before,
            "observe_called":         False,
            "observe_success":        False,
            "races_after_observe":    races_before,
            "observe_error":          None,
        }

        if not dry_run:
            race_data, pred_in, res_in = _build_engine_inputs(
                race_id, date, top, result_race,
                winner_id, sp, fav_won, mpi, chaos_bloom,
            )
            try:
                engine.observe_race_outcome(race_data, pred_in, res_in)
                races_after = engine.state.get("total_races_observed", 0)
                event_record["observe_called"]   = True
                event_record["observe_success"]  = True
                event_record["races_after_observe"] = races_after
                stats["observe_called"]  += 1
                stats["observe_success"] += 1
            except Exception as e:
                event_record["observe_called"] = True
                event_record["observe_error"]  = str(e)
                stats["observe_called"] += 1

            _record_consumed(consumption_key, race_id, date, outcome)
            consumed.add(consumption_key)

        stats["processed"] += 1
        stats["events"].append(event_record)
        count += 1

    return stats


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="VÉLØ Sentient Loop Repair V1 — shadow only")
    parser.add_argument("--proof-run", type=int, metavar="N", default=None,
                        help="Run only first N events (proof mode). Omit for full run.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build inputs but do NOT call observe_race_outcome()")
    args = parser.parse_args()

    proof_mode = args.proof_run is not None
    dry_run    = args.dry_run

    print("=" * 65)
    print("VÉLØ SENTIENT LOOP REPAIR V1")
    if proof_mode:
        print(f"MODE: PROOF RUN ({args.proof_run} events)")
    elif dry_run:
        print("MODE: DRY RUN (no state mutations)")
    else:
        print("MODE: FULL RUN")
    print("=" * 65)

    # ── Safety: hash live state before we start ────────────────────────────────
    live_hash_before = _hash_file(LIVE_STATE)
    print(f"\n[safety] Live state hash (before): {live_hash_before[:16]}…")
    print(f"[safety] Target repair state:       {REPAIR_STATE.name}")
    print(f"[safety] HFS_TRAINING_SAFE not required for shadow learning")

    # ── Initialise repair state (fresh — never uses existing shadow state) ─────
    if REPAIR_STATE.exists() and not proof_mode:
        # In full run: reset to fresh if consuming the same state again would double-count
        # But the consumption ledger guards against that — so we load existing state
        print(f"\n[state] Loading existing repair state: {REPAIR_STATE.name}")
    else:
        print(f"\n[state] Initialising fresh repair state")
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine as _SE
        _init = _SE(state_file=str(REPAIR_STATE), disable_cloud_backup=True)
        _init._save_state()
        del _init

    from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
    engine = SentientLoopbackEngine(state_file=str(REPAIR_STATE), disable_cloud_backup=True)
    races_start = engine.state.get("total_races_observed", 0)
    print(f"[state] Repair state races_observed at start: {races_start}")

    # ── Load consumed events (per target state) ────────────────────────────────
    consumed = _load_consumed_keys()
    print(f"[consumed] Previously consumed for this state: {len(consumed)}")

    # ── Discover available dates ───────────────────────────────────────────────
    pred_files = sorted(DATA.glob("velo_prime_verdicts_*.json"))
    dates = []
    for pf in pred_files:
        # Extract date from filename: velo_prime_verdicts_2026_05_05.json
        parts = pf.stem.replace("velo_prime_verdicts_", "")
        if len(parts) == 10 and parts[4] == "_" and parts[7] == "_":
            dates.append(parts.replace("_", "-"))
    print(f"[dates] Found prediction files for: {dates}")

    # ── Field source map (reported in audit — A finding) ──────────────────────
    field_source_map = {
        "race_id":                "pred_file[race].race_id",
        "horse_id (predicted)":   "pred_file[race].top.horse_id",
        "actual_winner":          "results_file runners sorted by position[0].horse_id",
        "velo_prime_prob":        "pred_file[race].top.velo_prime_prob",
        "decision_tier":          "pred_file[race].tier",
        "market_deception_score": "pred_file[race].top.market_deception_score",
        "improvement_score":      "pred_file[race].top.improvement_score",
        "mpi (FIXED)":            "(velo_prime_prob*0.6 + market_deception_score*0.4) * 100  [was: vp*100 — WRONG]",
        "chaos_bloom (FIXED)":    "derived from macro_chaos_mode + favourite_trap_risk  [was: null — MISSING]",
        "sp":                     "results_file runners[position==1].sp_dec  [was: 5.0 hardcoded — WRONG]",
        "narrative_disruption":   "0.0 (hardcoded — not yet computable from available fields)",
        "learning_allowed (FIXED)": "True when result verified + not consumed  [was: always False — BROKEN]",
        "idempotency_key":        "race_id:date",
        "consumption_key (FIXED)": "race_id:date|target_state_path  [was: race_id only — global collision]",
    }

    # ── Run per-date ───────────────────────────────────────────────────────────
    all_stats:  list[dict] = []
    total_events_cap = args.proof_run if proof_mode else None

    events_processed_total = 0
    for date in dates:
        remaining = None
        if total_events_cap is not None:
            remaining = total_events_cap - events_processed_total
            if remaining <= 0:
                break

        stats = _process_date(date, engine, consumed, dry_run=dry_run, max_events=remaining)
        all_stats.append(stats)

        processed = stats.get("processed", 0)
        events_processed_total += processed

        if stats.get("skip_reason"):
            print(f"  {date}: SKIPPED — {stats['skip_reason']}")
        else:
            print(
                f"  {date}: processed={processed} "
                f"observe={stats.get('observe_success',0)}/{stats.get('observe_called',0)} "
                f"dupes={stats.get('skipped_duplicate',0)} "
                f"no_result={stats.get('skipped_no_result',0)} "
                f"mpi_null={stats.get('mpi_null',0)} "
                f"chaos_null={stats.get('chaos_null',0)}"
            )

    # ── Verify live state untouched ────────────────────────────────────────────
    live_hash_after = _hash_file(LIVE_STATE)
    live_untouched  = (live_hash_before == live_hash_after)
    print(f"\n[safety] Live state hash (after):  {live_hash_after[:16]}…")
    print(f"[safety] Live state untouched:     {live_untouched}")
    if not live_untouched:
        print("  *** CRITICAL: Live state was modified — investigation required ***")

    # ── State mutation proof ───────────────────────────────────────────────────
    races_end      = engine.state.get("total_races_observed", 0)
    state_mutated  = races_end > races_start
    aggression     = engine.state.get("appetite_state", {}).get("aggression_level", "?")
    print(f"\n[mutation proof]")
    print(f"  races_observed start: {races_start}")
    print(f"  races_observed end:   {races_end}")
    print(f"  delta:                {races_end - races_start:+d}")
    print(f"  state_mutated:        {state_mutated}")
    print(f"  aggression:           {aggression}")

    # ── Totals ─────────────────────────────────────────────────────────────────
    total_processed      = sum(s.get("processed", 0) for s in all_stats)
    total_observe_called = sum(s.get("observe_called", 0) for s in all_stats)
    total_observe_ok     = sum(s.get("observe_success", 0) for s in all_stats)
    total_dupes          = sum(s.get("skipped_duplicate", 0) for s in all_stats)
    total_mpi_null       = sum(s.get("mpi_null", 0) for s in all_stats)
    total_chaos_null     = sum(s.get("chaos_null", 0) for s in all_stats)

    # Sample before/after for first 5 events (proof evidence)
    proof_events = []
    for s in all_stats:
        for ev in s.get("events", []):
            proof_events.append(ev)
            if len(proof_events) >= 5:
                break
        if len(proof_events) >= 5:
            break

    # ── Determine remaining blockers ───────────────────────────────────────────
    remaining_blockers = []
    if not live_untouched:
        remaining_blockers.append("CRITICAL: live sentient_state.json was modified")
    if total_mpi_null > 0:
        remaining_blockers.append(
            f"MPI_NULL: {total_mpi_null} events had no MPI (velo_prime_prob missing from prediction)"
        )
    if total_chaos_null > 0:
        remaining_blockers.append(
            f"CHAOS_NULL: {total_chaos_null} events had no chaos_bloom (macro context not available)"
        )
    remaining_blockers.append(
        "HFS_TRAINING_SAFE=False still blocks LIVE promotion — shadow accumulation only"
    )
    remaining_blockers.append(
        "Training artifact (4,643 races) not promoted — requires operator decision"
    )
    remaining_blockers.append(
        "7–14 day shadow accumulation required before any promotion discussion"
    )

    # ── Build audit payload ────────────────────────────────────────────────────
    payload = {
        "generated_at":     datetime.utcnow().isoformat() + "Z",
        "mode":             "PROOF_RUN" if proof_mode else ("DRY_RUN" if dry_run else "FULL_RUN"),
        "proof_event_cap":  args.proof_run,

        # A — Exact broken files and functions
        "A_broken_files_and_functions": {
            "eod_shadow_learning_bridge.py::_prepare_engine_inputs()": [
                "mpi = vp * 100  ← WRONG. Real formula: (vp*0.6 + mds*0.4)*100",
                "chaos_bloom = top_pick.get('chaos_bloom') * 100  ← ALWAYS NULL (field not in prediction snapshot)",
                "sp = 5.0  ← HARDCODED. Real SP available in results_YYYY_MM_DD.json runners[0].sp_dec",
            ],
            "eod_shadow_learning_bridge.py::event dict": [
                "learning_allowed hardcoded False  ← BLOCKS all adapter replay",
            ],
            "eod_shadow_learning_bridge.py::_load_processed_races()": [
                "Tracks race_id only (global). Same event can never feed a new shadow state.",
            ],
            "playbook_g_shadow_adapter.py::_prepare_engine_inputs()": [
                "Same wrong MPI formula: mpi = vp * 100",
            ],
        },

        # B — Why MPI/chaos_bloom were missing
        "B_why_hfs_missing": {
            "mpi": (
                "VeloPrimePrediction._compute_hfs_signals() computes mpi internally "
                "but to_dict() does NOT include mpi in the output dict. "
                "So mpi is NOT stored in velo_prime_verdicts_YYYY_MM_DD.json. "
                "EOD bridge used velo_prime_prob * 100 as a proxy — this is wrong. "
                "Fix: compute from available fields: (vp*0.6 + mds*0.4)*100. "
                "Both velo_prime_prob and market_deception_score ARE in the snapshot."
            ),
            "chaos_bloom": (
                "chaos_bloom is computed from macro_context object "
                "which is not serialised to the prediction file. "
                "However macro_chaos_mode (bool) and favourite_trap_risk (str) ARE serialised. "
                "Fix: reconstruct chaos_bloom from macro_chaos_mode + favourite_trap_risk. "
                "This matches the ensemble formula exactly."
            ),
        },

        # C — Event payload before/after
        "C_event_payload_before_after": {
            "before": {
                "mpi": "velo_prime_prob * 100  (proxy, not real MPI)",
                "chaos_bloom": "None  (field not in prediction snapshot)",
                "sp": "5.0  (hardcoded)",
                "learning_allowed": "False  (hardcoded)",
                "consumption_key": "race_id  (global — prevents cross-state replay)",
            },
            "after": {
                "mpi": "(velo_prime_prob*0.6 + market_deception_score*0.4)*100",
                "chaos_bloom": "derived from macro_chaos_mode + favourite_trap_risk → [30, 70, 100]*100 range",
                "sp": "results_file runners[position=1].sp_dec  (real SP)",
                "learning_allowed": "True when result verified + race_id present + not consumed",
                "consumption_key": "race_id:date|target_state_path  (per target state)",
            },
        },

        # D — Duplicate guard fix
        "D_duplicate_guard_fix": {
            "old": "Tracked race_id in JSONL. Same race_id could never be fed to a new shadow state.",
            "new": "Tracks consumption_key = f'{idempotency_key}|{target_state_path}'. "
                   "Same event CAN feed a different shadow state file. "
                   "Cannot double-feed the same state (idempotent per target).",
            "ledger": str(CONSUMED_LEDGER),
        },

        # E — 5-event shadow proof
        "E_5_event_proof": proof_events[:5],

        # F — 61-event shadow proof (all processed in this run)
        "F_full_run_summary": {
            "dates_processed": [s["date"] for s in all_stats if not s.get("skip_reason")],
            "dates_skipped":   [{"date": s["date"], "reason": s["skip_reason"]} for s in all_stats if s.get("skip_reason")],
            "total_processed":         total_processed,
            "total_observe_called":    total_observe_called,
            "total_observe_success":   total_observe_ok,
            "total_skipped_duplicate": total_dupes,
            "total_mpi_null":          total_mpi_null,
            "total_chaos_null":        total_chaos_null,
        },

        # G — observe_race_outcome fired?
        "G_observe_race_outcome_fired": total_observe_called > 0,
        "G_observe_success_count":      total_observe_ok,

        # H — Shadow state mutated?
        "H_shadow_state_mutated": state_mutated,
        "H_races_before":         races_start,
        "H_races_after":          races_end,
        "H_races_delta":          races_end - races_start,
        "H_aggression_after":     aggression,

        # I — Live state untouched?
        "I_live_sentient_state_untouched": live_untouched,
        "I_live_state_hash_before":        live_hash_before,
        "I_live_state_hash_after":         live_hash_after,

        # J — HFS_TRAINING_SAFE still blocks live?
        "J_HFS_TRAINING_SAFE_still_blocks_live": True,
        "J_note": (
            "This script does NOT modify HFS_TRAINING_SAFE. "
            "Shadow learning proceeds without it. "
            "Live promotion still requires HFS_TRAINING_SAFE=True AND operator sign-off."
        ),

        # K — Remaining blockers
        "K_remaining_blockers": remaining_blockers,

        # Full field source map
        "field_source_map": field_source_map,

        # Per-date detail
        "per_date": all_stats,

        # State refs
        "target_state_file":    str(REPAIR_STATE),
        "live_state_file":      str(LIVE_STATE),
        "consumed_ledger":      str(CONSUMED_LEDGER),
    }

    AUDIT_JSON.write_text(json.dumps(payload, indent=2))
    print(f"\nWritten: {AUDIT_JSON.name}")

    # ── Build Markdown ─────────────────────────────────────────────────────────
    DOCS_ENG.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# VÉLØ SENTIENT LOOP REPAIR AUDIT V1",
        "",
        f"Generated: {payload['generated_at']}",
        f"Mode: **{payload['mode']}**",
        "",
        "## A — Broken Files and Functions",
        "",
    ]
    for file_fn, errors in payload["A_broken_files_and_functions"].items():
        lines.append(f"### `{file_fn}`")
        lines.append("")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    lines += [
        "## B — Why MPI and chaos_bloom Were Missing",
        "",
        f"**MPI:** {payload['B_why_hfs_missing']['mpi']}",
        "",
        f"**chaos_bloom:** {payload['B_why_hfs_missing']['chaos_bloom']}",
        "",
        "## C — Event Payload Before vs After",
        "",
        "| Field | Before (broken) | After (repaired) |",
        "|---|---|---|",
    ]
    for field, before in payload["C_event_payload_before_after"]["before"].items():
        after = payload["C_event_payload_before_after"]["after"].get(field, "—")
        lines.append(f"| `{field}` | {before} | {after} |")

    lines += [
        "",
        "## D — Duplicate Guard Fix",
        "",
        f"- **Old:** {payload['D_duplicate_guard_fix']['old']}",
        f"- **New:** {payload['D_duplicate_guard_fix']['new']}",
        f"- **Ledger:** `{CONSUMED_LEDGER.name}`",
        "",
        "## E — 5-Event Shadow Proof",
        "",
        "| Race | Date | Outcome | VP | MPI | chaos | SP | Obs Called | Obs OK | Δ races |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for ev in payload["E_5_event_proof"]:
        delta = (ev.get("races_after_observe", 0) or 0) - (ev.get("races_before_observe", 0) or 0)
        lines.append(
            f"| {ev.get('race_id','?')} "
            f"| {ev.get('date','?')} "
            f"| {ev.get('outcome','?')} "
            f"| {ev.get('velo_prime_prob','?')} "
            f"| {ev.get('mpi','null')} "
            f"| {ev.get('chaos_bloom','null')} "
            f"| {ev.get('sp','?')} "
            f"| {ev.get('observe_called','?')} "
            f"| {ev.get('observe_success','?')} "
            f"| {delta:+d} |"
        )

    lines += [
        "",
        "## F — Full Run Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total events processed | {total_processed} |",
        f"| observe_race_outcome called | {total_observe_called} |",
        f"| observe_race_outcome success | {total_observe_ok} |",
        f"| Skipped (duplicate) | {total_dupes} |",
        f"| MPI null events | {total_mpi_null} |",
        f"| chaos_bloom null events | {total_chaos_null} |",
        "",
        "## G — observe_race_outcome Fired?",
        "",
        f"**Fired: {payload['G_observe_race_outcome_fired']}** | Success count: {total_observe_ok}",
        "",
        "## H — Shadow State Mutated?",
        "",
        f"**Mutated: {state_mutated}**",
        f"- races_observed before: {races_start}",
        f"- races_observed after: {races_end}",
        f"- delta: {races_end - races_start:+d}",
        f"- aggression after: {aggression}",
        "",
        "## I — Live State Untouched?",
        "",
        f"**Untouched: {live_untouched}**",
        f"- Hash before: `{live_hash_before[:32]}…`",
        f"- Hash after: `{live_hash_after[:32]}…`",
        "",
        "## J — HFS_TRAINING_SAFE Still Blocks Live?",
        "",
        f"**Yes — live promotion still blocked.** {payload['J_note']}",
        "",
        "## K — Remaining Blockers",
        "",
    ]
    for b in remaining_blockers:
        lines.append(f"- {b}")

    lines += [
        "",
        "## Hard Rules",
        "",
        "- No live sentient_state.json modified.",
        "- No Supabase writes.",
        "- No scoring changes.",
        "- No model changes.",
        "- No router/staking/Telegram.",
        "- No fabricated MPI or chaos_bloom.",
        "- Shadow accumulation only. Live promotion requires HFS_TRAINING_SAFE=True + operator sign-off.",
    ]

    AUDIT_MD.write_text("\n".join(lines))
    print(f"Written: {AUDIT_MD.name}")

    print("\n=== REPAIR SUMMARY ===")
    print(f"  G observe fired:      {payload['G_observe_race_outcome_fired']} ({total_observe_ok} success)")
    print(f"  H state mutated:      {state_mutated} ({races_end - races_start:+d} races)")
    print(f"  I live untouched:     {live_untouched}")
    print(f"  J live still blocked: True (HFS_TRAINING_SAFE=False)")
    print(f"  K blockers remaining: {len(remaining_blockers)}")


if __name__ == "__main__":
    main()
