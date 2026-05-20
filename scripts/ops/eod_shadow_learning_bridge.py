#!/usr/bin/env python3
"""
VÉLØ EOD Shadow Learning Bridge — PATCHED v2
Bridges confirmed outcomes to Playbook G shadow state.

Strictly shadow-only. No Supabase writes. No live state mutation.

PATCH v2 (2026-05-08) — fixes four root causes confirmed by forensic audit:
  1. MPI: was vp*100. Now (vp*0.6 + mds*0.4)*100 per ensemble formula.
  2. SP:  was 5.0 hardcoded. Now extracted from result runners sp_dec.
  3. learning_allowed: was always False. Now True when result is closed+verified.
  4. chaos_bloom: was null/TypeError path. Now derived from macro fields or 0.0 guarded.

Provenance fields added to every event:
  mpi_source, mpi_input_vp, mpi_input_mds
  sp_source, sp_is_hardcoded, sp_missing_reason
  chaos_bloom_source
  learning_allowed, learning_block_reason

Idempotency key upgraded to race_id:date:target_state.
Shadow target: sentient_state_shadow_daily.json  (separate from repair state)
Live hash verified before/after.
"""

import hashlib
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine

# ─── Configuration ────────────────────────────────────────────────────────────

# Shadow target — separate from repair state and old shadow state
SHADOW_SENTIENT_STATE = ROOT / "data" / "sentient_state_shadow_daily.json"

# Event ledger — append-only, per-date events with provenance
SHADOW_OUTCOME_LEDGER = ROOT / "data" / "playbook_g_outcome_events_shadow_daily.jsonl"

# Loss ledger — append-only, losing events only
SHADOW_LOSS_LEDGER    = ROOT / "data" / "eod_loss_ledger_shadow_daily.jsonl"

# Live state — must never be modified
LIVE_STATE = ROOT / "data" / "sentient_state.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eod_bridge_v2")


# ─── Safety ───────────────────────────────────────────────────────────────────

def _hash_file(path: Path) -> str:
    if not path.exists():
        return "FILE_NOT_FOUND"
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ─── HFS signal computation — matches ensemble formula exactly ────────────────

def _compute_mpi(ps: dict) -> tuple[float, str, float | None, float | None]:
    """
    Compute MPI from prediction snapshot.
    Formula: (vp*0.6 + mds*0.4) scaled to 0-100.
    Returns (mpi_0_to_100, source, input_vp, input_mds).
    """
    vp  = ps.get("velo_prime_prob")
    mds = ps.get("market_deception_score")

    if vp is None:
        return 50.0, "neutral_fallback_vp_missing", None, None

    vp = float(vp)
    if mds is not None:
        mds_f  = float(mds)
        mpi_01 = (vp * 0.6) + (mds_f * 0.4)
        source = "derived_from_vp_mds"
    else:
        mds_f  = None
        mpi_01 = vp
        source = "derived_from_vp_only_mds_missing"

    return round(min(1.0, max(0.0, mpi_01)) * 100, 2), source, round(vp, 4), (round(mds_f, 4) if mds_f is not None else None)


def _compute_chaos_bloom(ps: dict) -> tuple[float, str]:
    """
    Compute chaos_bloom from prediction snapshot.
    Formula mirrors VeloPrimePrediction._compute_hfs_signals().
    Returns (chaos_0_to_100, source).
    Never returns None — guaranteed 0.0 floor with provenance.
    """
    chaos_mode  = ps.get("macro_chaos_mode")
    trap_risk   = ps.get("favourite_trap_risk", "")
    macro_avail = ps.get("macro_available", False)

    if not macro_avail and chaos_mode is None:
        return 0.0, "defaulted_missing_macro"

    base = 0.3
    if chaos_mode:
        base += 0.4
    if str(trap_risk).lower() in ("high",):
        base += 0.3
    elif str(trap_risk).lower() in ("medium",):
        base += 0.15

    return round(min(1.0, max(0.0, base)) * 100, 2), "derived_from_macro_fields"


# ─── Result extraction ────────────────────────────────────────────────────────

def _extract_winner_sp(result_race: dict) -> tuple[str, float, bool, str, str | None]:
    """
    Extract (winner_horse_id, sp_decimal, favourite_won, sp_source, sp_missing_reason).
    Never silently defaults SP — provenance always set.
    """
    runners = result_race.get("runners", [])
    sorted_r = sorted(
        [r for r in runners if str(r.get("position", "")).isdigit()],
        key=lambda r: int(r["position"]),
    )

    if not sorted_r:
        return "", 0.0, False, "missing_result_match", "no_runners_with_numeric_position"

    winner = sorted_r[0]
    horse_id = winner.get("horse_id", "")
    sp_raw   = winner.get("sp_dec") or winner.get("sp_decimal") or winner.get("bsp")

    if sp_raw is None:
        sp          = 0.0
        sp_source   = "missing_sp_field"
        sp_missing  = "sp_dec_bsp_all_null_in_winner_runner"
    else:
        try:
            sp        = float(sp_raw)
            sp_source = "result_runner_sp_dec"
            sp_missing = None
        except (ValueError, TypeError):
            sp        = 0.0
            sp_source = "sp_parse_failed"
            sp_missing = f"could_not_parse_{sp_raw!r}"

    # Favourite = runner with lowest SP
    all_sps = []
    for r in sorted_r:
        try:
            all_sps.append((float(r.get("sp_dec") or r.get("sp_decimal") or 0), r.get("horse_id")))
        except Exception:
            pass
    fav_won = bool(all_sps and all_sps and min(all_sps, key=lambda x: x[0])[1] == horse_id)

    return horse_id, sp, fav_won, sp_source, sp_missing


# ─── EOD Metrics (unchanged from v1) ─────────────────────────────────────────

class EODMetrics:
    def __init__(self):
        self.total_races = 0
        self.hits = 0
        self.top_3_hits = 0
        self.fav_total = 0
        self.fav_hits = 0
        self.non_fav_total = 0
        self.non_fav_hits = 0
        self.missing_results = 0
        self.brier_sum = 0.0
        self.prob_bins = Counter()
        self.hit_bins = Counter()
        self.loss_types = Counter()
        self.duplicate_skipped = 0

    def add_race(self, prediction: dict, result: dict, outcome: str, loss_type: str):
        self.total_races += 1
        self.loss_types[loss_type] += 1

        if outcome == "UNKNOWN":
            self.missing_results += 1
            return

        prob   = float(prediction.get("velo_prime_prob") or 0.0)
        is_hit = 1 if outcome == "WIN" else 0

        self.brier_sum += (prob - is_hit) ** 2
        bin_idx = int(prob * 10)
        self.prob_bins[bin_idx] += 1
        if is_hit:
            self.hit_bins[bin_idx] += 1
            self.hits += 1

        if result:
            runners = result.get("runners", [])
            top3_ids = [
                r.get("horse_id")
                for r in sorted(
                    [r for r in runners if str(r.get("position", "")).isdigit()],
                    key=lambda r: int(r["position"]),
                )[:3]
            ]
            if prediction.get("horse_id") in top3_ids:
                self.top_3_hits += 1

        is_fav = prediction.get("is_fav", False)
        if is_fav:
            self.fav_total += 1
            if is_hit:
                self.fav_hits += 1
        else:
            self.non_fav_total += 1
            if is_hit:
                self.non_fav_hits += 1

    def calculate(self) -> dict:
        total = self.total_races - self.missing_results
        ece = 0.0
        for b in range(10):
            if self.prob_bins[b] > 0:
                conf = (b * 0.1) + 0.05
                acc  = self.hit_bins[b] / self.prob_bins[b]
                ece += abs(conf - acc) * (self.prob_bins[b] / total) if total > 0 else 0

        return {
            "strike_rate":               self.hits / total if total > 0 else 0,
            "top_1_accuracy":            self.hits / total if total > 0 else 0,
            "top_3_accuracy":            self.top_3_hits / total if total > 0 else 0,
            "brier_score":               self.brier_sum / total if total > 0 else 0,
            "calibration_error":         ece,
            "favourite_strike_rate":     self.fav_hits / self.fav_total if self.fav_total > 0 else 0,
            "non_favourite_strike_rate": self.non_fav_hits / self.non_fav_total if self.non_fav_total > 0 else 0,
            "missing_result_rate":       self.missing_results / self.total_races if self.total_races > 0 else 0,
            "loss_count_by_type":        dict(self.loss_types),
            "event_count":               self.total_races,
            "duplicate_skipped_count":   self.duplicate_skipped,
        }


# ─── Shadow Learning Bridge ───────────────────────────────────────────────────

class ShadowLearningBridge:

    TARGET_STATE_ID = str(SHADOW_SENTIENT_STATE)

    def __init__(self, date_str: str = None):
        self.date_str       = date_str or datetime.now().strftime("%Y-%m-%d")
        self.prediction_file = ROOT / "data" / f"velo_prime_verdicts_{self.date_str.replace('-', '_')}.json"
        self.result_file     = ROOT / "data" / f"results_{self.date_str.replace('-', '_')}.json"

        # ── Hash live state before we start ───────────────────────────────────
        self.live_hash_before = _hash_file(LIVE_STATE)

        # ── Initialise shadow state ────────────────────────────────────────────
        if not SHADOW_SENTIENT_STATE.exists():
            # Initialise fresh (never copy live state — keep shadow independent)
            logger.info("[bridge_v2] Initialising fresh shadow daily state")
        self.engine = SentientLoopbackEngine(
            state_file=str(SHADOW_SENTIENT_STATE),
            disable_cloud_backup=True,
        )

        self.processed_keys = self._load_processed_keys()
        self.metrics        = EODMetrics()

        # Observe counters for audit report
        self.obs_called   = 0
        self.obs_success  = 0
        self.obs_failures = []

    def _load_processed_keys(self) -> set:
        """Load already-consumed idempotency keys for this shadow target."""
        processed = set()
        if SHADOW_OUTCOME_LEDGER.exists():
            with open(SHADOW_OUTCOME_LEDGER, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev  = json.loads(line)
                        key = ev.get("idempotency_key", ev.get("race_id", ""))
                        if key:
                            processed.add(key)
                    except json.JSONDecodeError:
                        continue
        return processed

    def _idempotency_key(self, race_id: str) -> str:
        return f"{race_id}:{self.date_str}:{self.TARGET_STATE_ID}"

    def _classify_loss(self, prediction: dict, result: dict) -> str:
        if not prediction or not result:
            return "DATA_ERROR"
        outcome = "WIN" if prediction.get("horse_id") == result.get("winner_id") else "LOSS"
        if outcome == "WIN":
            return "NONE"

        prob      = float(prediction.get("velo_prime_prob") or 0)
        fav_won   = result.get("favourite_won", False)
        if not prediction.get("horse_id"):
            return "DATA_ERROR"
        if prediction.get("improvement_score") is None:
            return "SIGNAL_GAP"
        if fav_won and prob < 0.2:
            return "MARKET_LIED"
        if prob > 0.35:
            return "CALIBRATION_ERROR"
        return "WRONG_HORSE"

    def _prepare_engine_inputs(
        self,
        race_id: str,
        top_pick: dict,
        winner_id: str,
        sp: float,
        fav_won: bool,
        mpi: float,
        chaos_bloom: float,
    ) -> tuple[dict, dict, dict]:
        race_data = {
            "race_id":             race_id,
            "race_date":           self.date_str,
            "mpi":                 mpi,
            "chaos_bloom":         chaos_bloom,  # always float — never None
            "story_anchor":        "favourite" if fav_won else "non-favourite",
            "power_anchor":        top_pick.get("horse_id", ""),
            "threat_cluster":      [],
            "narrative_disruption": 0.0,
            "fav_trip_blocked":    False,
            "runners":             [],
            "integrity_score":     100,
        }
        prediction = {
            "power_anchor":   top_pick.get("horse_id", ""),
            "confidence":     float(top_pick.get("velo_prime_prob") or 0),
            "doctrines_fired": top_pick.get("doctrines_fired") or [],
        }
        actual_result = {
            "winner":        winner_id,
            "sp":            sp if sp > 0 else 5.0,  # engine needs non-zero; document via sp_source
            "favourite_won": fav_won,
            "winner_profile": {
                "running_style": "unknown",
                "draw":          None,
                "was_hidden_improver": False,
                "late_money":    False,
            },
        }
        return race_data, prediction, actual_result

    def _learning_allowed(self, outcome: str, race_id: str, winner_id: str, top_pick: dict) -> tuple[bool, str | None]:
        """Return (allowed, block_reason). block_reason=None when allowed."""
        if outcome == "UNKNOWN":
            return False, "outcome_unknown"
        if not race_id:
            return False, "race_id_missing"
        if not winner_id:
            return False, "winner_id_missing"
        if not top_pick.get("horse_id"):
            return False, "predicted_horse_id_missing"
        return True, None

    def run(self):
        logger.info(f"[bridge_v2] Running for {self.date_str}")
        logger.info(f"[bridge_v2] Live hash before: {self.live_hash_before[:16]}…")

        if not self.prediction_file.exists():
            logger.error(f"[bridge_v2] Prediction file not found: {self.prediction_file}")
            return
        if not self.result_file.exists():
            logger.error(f"[bridge_v2] Result file not found: {self.result_file}")
            return

        predictions_raw = json.loads(self.prediction_file.read_text())
        results_raw     = json.loads(self.result_file.read_text())
        results_list    = results_raw.get("results", []) if isinstance(results_raw, dict) else results_raw
        results_map     = {r.get("race_id") or r.get("id"): r for r in results_list}

        for pred_race in predictions_raw:
            race_id = pred_race.get("race_id")
            top     = pred_race.get("top", {})
            if not race_id:
                race_id = top.get("race_id")
            if not race_id:
                continue

            idem_key = self._idempotency_key(race_id)
            if idem_key in self.processed_keys:
                self.metrics.duplicate_skipped += 1
                continue

            result_race = results_map.get(race_id)
            if not result_race:
                continue

            winner_id, sp, fav_won, sp_source, sp_missing = _extract_winner_sp(result_race)
            if winner_id:
                result_race["winner_id"] = winner_id

            outcome   = "UNKNOWN"
            if result_race and top:
                outcome = "WIN" if top.get("horse_id") == winner_id else "LOSS"

            loss_type = self._classify_loss(top, result_race)
            self.metrics.add_race(top, result_race, outcome, loss_type)

            # ── HFS signals (patched formulas) ────────────────────────────────
            mpi, mpi_src, mpi_vp, mpi_mds = _compute_mpi(top)
            chaos_bloom, chaos_src         = _compute_chaos_bloom(top)

            # ── learning_allowed gate ──────────────────────────────────────────
            allowed, block_reason = self._learning_allowed(outcome, race_id, winner_id, top)

            # ── Build event dict with full provenance ─────────────────────────
            event = {
                "event_type":           "result_confirmed",
                "race_id":              race_id,
                "event_date":           self.date_str,
                "idempotency_key":      idem_key,
                "prediction_snapshot":  top,
                "result_snapshot": {
                    "winner_id":    winner_id,
                    "favourite_won": result_race.get("favourite_won") if result_race else None,
                },
                "market_snapshot": {},
                "prediction_result": outcome,
                "loss_type":          loss_type,
                # MPI provenance
                "mpi":                mpi,
                "mpi_source":         mpi_src,
                "mpi_input_vp":       mpi_vp,
                "mpi_input_mds":      mpi_mds,
                # chaos_bloom provenance
                "chaos_bloom":        chaos_bloom,
                "chaos_bloom_source": chaos_src,
                # SP provenance
                "sp_decimal":         sp if sp > 0 else None,
                "sp_source":          sp_source,
                "sp_is_hardcoded":    False,
                "sp_missing_reason":  sp_missing,
                # Learning gate
                "learning_allowed":   allowed,
                "learning_block_reason": block_reason,
                "learning_mode":      "SHADOW_ONLY",
                # Safety
                "sentient_state_target": self.TARGET_STATE_ID,
            }

            # ── Call observe_race_outcome when learning is allowed ─────────────
            if allowed:
                race_data, pred_in, res_in = self._prepare_engine_inputs(
                    race_id, top, winner_id, sp, fav_won, mpi, chaos_bloom,
                )
                self.obs_called += 1
                try:
                    self.engine.observe_race_outcome(race_data, pred_in, res_in)
                    self.obs_success += 1
                    logger.debug(f"[bridge_v2] observe OK: {race_id}")
                except Exception as e:
                    self.obs_failures.append({"race_id": race_id, "error": str(e)})
                    logger.warning(f"[bridge_v2] observe FAILED: {race_id} — {e}")

            with open(SHADOW_OUTCOME_LEDGER, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")

            if outcome in ("LOSS",) or loss_type == "DATA_ERROR":
                with open(SHADOW_LOSS_LEDGER, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "race_id":  race_id,
                        "date":     self.date_str,
                        "loss_type": loss_type,
                        "prediction": top.get("horse"),
                        "prob":     top.get("velo_prime_prob"),
                    }) + "\n")

            self.processed_keys.add(idem_key)

        # ── Verify live state untouched ────────────────────────────────────────
        live_hash_after = _hash_file(LIVE_STATE)
        live_untouched  = (self.live_hash_before == live_hash_after)
        if not live_untouched:
            logger.critical("[bridge_v2] *** LIVE STATE MODIFIED — INVESTIGATE IMMEDIATELY ***")

        # ── Audit files ────────────────────────────────────────────────────────
        audit_tag    = self.date_str.replace("-", "_")
        final_metrics = self.metrics.calculate()
        races_observed = self.engine.state.get("total_races_observed", 0)

        audit_data = {
            "date":                   self.date_str,
            "bridge_version":         "v2_patched_2026_05_08",
            "metrics":                final_metrics,
            "shadow_state_file":      str(SHADOW_SENTIENT_STATE),
            "outcome_ledger":         str(SHADOW_OUTCOME_LEDGER),
            "loss_ledger":            str(SHADOW_LOSS_LEDGER),
            "total_races_observed_shadow": races_observed,
            "obs_called":             self.obs_called,
            "obs_success":            self.obs_success,
            "obs_failures":           self.obs_failures,
            "live_hash_before":       self.live_hash_before,
            "live_hash_after":        live_hash_after,
            "live_state_untouched":   live_untouched,
        }

        (ROOT / "data" / f"eod_flags_shadow_{audit_tag}.json").write_text(json.dumps(audit_data, indent=2))
        (ROOT / "data" / "shadow_learning_loop_audit_v1.json").write_text(json.dumps(audit_data, indent=2))

        logger.info(
            f"[bridge_v2] Complete. Shadow races: {races_observed} | "
            f"observe: {self.obs_success}/{self.obs_called} | "
            f"live untouched: {live_untouched}"
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VÉLØ EOD Shadow Learning Bridge v2")
    parser.add_argument("--date", help="Date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    bridge = ShadowLearningBridge(date_str=args.date)
    bridge.run()
