#!/usr/bin/env python3
"""
VÉLØ Nightly EOD Learning Runner
Automates the nightly learning loop from birth outcomes to shadow brain.

Strictly outcome-only. No HFS features used.
"""

import json
import os
import sys
import glob
import logging
import hashlib
import argparse
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter

# Add root to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
from scripts.playbook_g_shadow_adapter import PlaybookGShadowAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nightly_runner")

class NightlyEODRunner:
    def __init__(
        self,
        date_str: str,
        state_path: str,
        dry_run: bool = False,
        data_error_threshold: float = 0.1,
        pred_file: str | None = None,
        result_file: str | None = None,
    ):
        self.date_str = date_str
        self.date_tag = date_str.replace("-", "_")
        self.state_path = Path(state_path)
        self.dry_run = dry_run
        self.data_error_threshold = data_error_threshold
        
        self.live_state_path = ROOT / "data" / "sentient_state.json"
        self.pred_file = Path(pred_file) if pred_file else ROOT / "data" / f"velo_prime_verdicts_{self.date_tag}.json"
        # Canonical path from parse_rp_results_capture.py; legacy fallback for older runs
        _res_canonical = ROOT / "data" / "results" / f"rp_results_{self.date_tag}.json"
        _res_legacy = ROOT / "data" / f"results_{self.date_tag}.json"
        self.res_file = Path(result_file) if result_file else (_res_canonical if _res_canonical.exists() else _res_legacy)
        
        self.status_path = ROOT / "data" / f"nightly_eod_learning_status_{self.date_tag}.json"
        self.failures_path = ROOT / "data" / f"nightly_eod_learning_failures_{self.date_tag}.json"
        self.council_path = ROOT / "data" / f"nightly_eod_learning_council_audit_{self.date_tag}.json"
        self.events_path = ROOT / "data" / f"nightly_eod_learning_events_{self.date_tag}.jsonl"
        
        self.run_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc).isoformat()
        
        self.failures = []
        self.stats = {
            "prediction_count": 0,
            "result_count": 0,
            "matched_races": 0,
            "events_created": 0,
            "wins": 0,
            "losses": 0,
            "void_or_unknown": 0,
            "loss_count_by_type": Counter(),
            "data_error_count": 0
        }

    def _get_file_hash(self, path: Path):
        if not path.exists(): return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _classify_loss(self, prediction: dict, result: dict) -> str:
        if not prediction or not result: return "DATA_ERROR"
        top_pick = prediction.get("top", {})
        if not top_pick: return "DATA_ERROR"

        top_horse_id = (top_pick.get("horse_id") or "")
        top_horse_name = (top_pick.get("horse") or top_pick.get("horse_name") or "").strip().lower()

        runners = result.get("runners", [])
        winner_id = ""
        winner_name = ""
        sorted_runners = sorted([r for r in runners if str(r.get("position", "")).isdigit()],
                             key=lambda r: int(r["position"]))
        if sorted_runners:
            winner_id = sorted_runners[0].get("horse_id") or ""
            winner_name = (sorted_runners[0].get("horse") or "").strip().lower()

        id_match = bool(top_horse_id and winner_id and top_horse_id == winner_id)
        name_match = bool(top_horse_name and winner_name and top_horse_name == winner_name)
        outcome = "WIN" if (id_match or name_match) else "LOSS"
        if outcome == "WIN": return "NONE"
        
        prob = float(top_pick.get("velo_prime_prob") or 0)
        fav_won = result.get("favourite_won", False)
        
        if prob > 0.55: return "CALIBRATION_ERROR"  # raised from 0.35 — VP>0.35 caught normal picks; VP>0.55 = genuinely overconfident
        if fav_won and prob < 0.2: return "MARKET_LIED"
        return "WRONG_HORSE"

    def run(self):
        logger.info(f"Starting Nightly EOD Runner for {self.date_str} [Run: {self.run_id}]")

        # 0. Learning Admission Gate pre-flight (LEARNING_ADMISSION_GATE.md conditions 8, 11, MC)
        # Condition 12 (operator approval) is not automatable — operator must not invoke
        # this script on a blocked day. All other automatable conditions checked here.
        _gate_blocks = []

        _sigma_path = ROOT / "data" / "sigma_results" / f"sigma_results_{self.date_tag}.json"
        if not _sigma_path.exists():
            _gate_blocks.append("SIGMA_ARTIFACT_MISSING")
        else:
            try:
                _sigma_status = json.loads(_sigma_path.read_text()).get("sigma_status", "UNKNOWN")
                if _sigma_status != "PASS":
                    _gate_blocks.append(f"SIGMA_NOT_PASS:{_sigma_status}")
            except Exception as _e:
                _gate_blocks.append(f"SIGMA_READ_ERROR:{_e}")

        _council_path = ROOT / "data" / "council_runs" / f"council_run_{self.date_str}.json"
        if not _council_path.exists():
            _gate_blocks.append("COUNCIL_RUN_MISSING")
        else:
            try:
                _council = json.loads(_council_path.read_text())
                _cv = _council.get("council_verdict", "NOT_RUN")
                self.council_verdict = _cv
                # A non-PASS verdict no longer blocks learning by itself.
                # Operator ruling 2026-08-02: learning happens every day,
                # including degraded ones. Only a DATA-TRUST failure blocks --
                # contamination, flatline, unknown source, missing sigma or
                # missing snapshots. A low strike rate is a fact about the
                # picks, not about whether the day's data can be believed, and
                # holding those days out biases the evidence base toward days
                # the model already handled well. 2026-08-03 was the case that
                # forced this: 32/32 reconciled, 0 identity failures, 100% PDF
                # enrichment, held out solely because SR was 15.6%.
                from src.velo.council.agents import learning_disposition
                _disp = learning_disposition(_council.get("agent_responses", []))
                self.council_disposition = _disp
                if not _disp["allowed"]:
                    _gate_blocks.append(
                        f"COUNCIL_INTEGRITY:{_cv}:{';'.join(_disp['integrity_reasons'])}"
                    )
                elif _disp["disposition"] != "CLEAN":
                    logger.warning(
                        "Council verdict %s but reasons are performance-only (%s) — "
                        "learning PROCEEDS, day labelled %s.",
                        _cv, "; ".join(_disp["performance_reasons"]), _disp["disposition"],
                    )
            except Exception as _e:
                _gate_blocks.append(f"COUNCIL_READ_ERROR:{_e}")

        _mc_path = ROOT / "data" / "mission_control" / f"{self.date_str}_mission_control.json"
        if not _mc_path.exists():
            _gate_blocks.append("MISSION_CONTROL_MISSING")
        else:
            try:
                # Mission Control writes "learning_gate_status" -- there is no
                # "learning_gate" key. Fix 3 (38023e6, 2026-07-28) read the
                # non-existent name, so this always resolved to UNKNOWN and
                # blocked learning on EVERY day regardless of the real gate
                # state (confirmed: 2026-07-29 and 2026-07-30 both returned
                # FAIL_GATE_BLOCKED / LEARNING_GATE:UNKNOWN while sigma=PASS,
                # council=PASS_TO_LEARNING and learning_gate_status=OPEN).
                # docs/current/ONE_TRUTH.md flags this exact trap in the
                # Mission Control row of the subsystem truth board.
                _lg = json.loads(_mc_path.read_text()).get("learning_gate_status", "UNKNOWN")
                if _lg != "OPEN":
                    _gate_blocks.append(f"LEARNING_GATE:{_lg}")
            except Exception as _e:
                _gate_blocks.append(f"MC_READ_ERROR:{_e}")

        if _gate_blocks:
            logger.error("GATE BLOCKED — learning cannot proceed: %s", _gate_blocks)
            for _block in _gate_blocks:
                self.failures.append({"type": "GATE_BLOCKED", "reason": _block})
            return self._finalize("FAIL_GATE_BLOCKED")

        # Report the verdict that actually applied, not a hardcoded one. This
        # line used to assert "council=PASS_TO_LEARNING" unconditionally, so a
        # WATCH_ONLY day admitted on performance-only grounds logged a verdict
        # it never had -- the same instrument-lies-about-itself pattern that
        # ONE_TRUTH's "Cause 2 — the instruments lie" section documents.
        _disp = getattr(self, "council_disposition", None) or {}
        logger.info(
            "Gate pre-flight PASS — sigma=PASS, council=%s (%s), learning_gate=OPEN",
            getattr(self, "council_verdict", "UNKNOWN"),
            _disp.get("disposition", "UNCLASSIFIED"),
        )

        # 1. Data Integrity Check
        if not self.pred_file.exists():
            self.failures.append({"type": "MISSING_PREDICTIONS", "file": str(self.pred_file)})
            return self._finalize("FAIL")
            
        if not self.res_file.exists():
            self.failures.append({"type": "MISSING_RESULTS", "file": str(self.res_file)})
            return self._finalize("FAIL")

        live_hash_before = self._get_file_hash(self.live_state_path)
        shadow_hash_before = self._get_file_hash(self.state_path)

        # 2. Reconcile
        preds = json.loads(self.pred_file.read_text())
        from scripts.ops.run_results_sigma import _duplicate_alias_race_ids

        pred_identity = {
            str(row.get("race_id", "")): {
                "course": row.get("course", ""),
                "off_time": row.get("off_time", ""),
            }
            for row in preds
        }
        duplicate_alias_ids = _duplicate_alias_race_ids(pred_identity)
        if duplicate_alias_ids:
            logger.info(
                "Excluding %d synthetic aliases shadowed by canonical RP races",
                len(duplicate_alias_ids),
            )
            preds = [row for row in preds if str(row.get("race_id", "")) not in duplicate_alias_ids]
        results_raw = json.loads(self.res_file.read_text())
        results_list = results_raw.get("results", []) if isinstance(results_raw, dict) else results_raw

        # Primary index: RP numeric race_id (e.g. "919896")
        results_map = {r.get("race_id") or r.get("id"): r for r in results_list}

        # Secondary index: venue+off (e.g. "CHP_5.10") for VELO race_ids (rp_CHP_20260606_5.10)
        # "CHE" is the results-parser's own code for Chester; VELO race_ids use "CHS".
        venue_aliases = {"PAT": "PUN", "CHE": "CHS"}

        def _normalise_venue(value: str) -> str:
            venue = (value or "").upper()
            return venue_aliases.get(venue, venue)

        def _venue_off_key(r: dict) -> str | None:
            v = _normalise_venue(r.get("venue") or "")
            o = (r.get("off") or "").strip()
            return f"{v}_{o}" if v and o else None

        results_venue_off = {_venue_off_key(r): r for r in results_list if _venue_off_key(r)}

        def _lookup_result(velo_race_id: str) -> dict | None:
            if velo_race_id in results_map:
                return results_map[velo_race_id]
            # Parse rp_{VENUE}_{DATE}_{TIME} → venue + time for secondary lookup
            parts = velo_race_id.split("_")
            if len(parts) >= 4 and parts[0] == "rp":
                venue = _normalise_venue(parts[1])
                time = parts[3]
                key = f"{venue}_{time}"
                return results_venue_off.get(key)
            return None

        self.stats["prediction_count"] = len(preds)
        self.stats["result_count"] = len(results_list)

        if self.events_path.exists(): self.events_path.unlink()

        for p_race in preds:
            rid = p_race.get("race_id")
            if not rid:
                self.failures.append({"type": "BAD_RACE_ID", "prediction": p_race})
                continue

            r_race = _lookup_result(rid)
            if r_race is None:
                self.stats["data_error_count"] += 1
                self.stats["loss_count_by_type"]["DATA_ERROR"] += 1
                self.failures.append({"type": "MISSING_RESULT", "race_id": rid})
                continue
            self.stats["matched_races"] += 1
            
            top_pick = p_race.get("top", {})
            top_horse_id = (top_pick.get("horse_id") or "")
            # "horse" is the canonical name field in VELO verdicts (not "horse_name")
            top_horse_name = (top_pick.get("horse") or top_pick.get("horse_name") or "").strip().lower()

            winner_id = ""
            winner_name = ""
            runners = r_race.get("runners", [])
            sorted_runners = sorted([r for r in runners if str(r.get("position", "")).isdigit()],
                                 key=lambda r: int(r["position"]))
            if sorted_runners:
                winner_id = sorted_runners[0].get("horse_id") or ""
                winner_name = (sorted_runners[0].get("horse") or "").strip().lower()

            outcome = "UNKNOWN"
            if top_pick and (winner_id or winner_name):
                id_match = bool(top_horse_id and winner_id and top_horse_id == winner_id)
                name_match = bool(top_horse_name and winner_name and top_horse_name == winner_name)
                outcome = "WIN" if (id_match or name_match) else "LOSS"
            
            loss_type = self._classify_loss(p_race, r_race)
            
            # Create Event
            event = {
                "event_type": "result_confirmed",
                "learning_mode": "OUTCOME_ONLY_EOD_REPLAY",
                "learning_allowed": True,
                "learning_permission_reason": "OUTCOME_ONLY_NO_HFS_FEATURES",
                "hfs_training_safe": False,
                "hfs_features_used": False,
                "sentient_state_target": str(self.state_path),
                "idempotency_key": f"{rid}:{self.date_str}",
                "race_id": rid,
                "event_date": self.date_str,
                "prediction_snapshot": top_pick,
                "result_snapshot": {
                    "winner_id": winner_id,
                    "favourite_won": r_race.get("favourite_won")
                },
                "market_snapshot": {},
                "prediction_result": outcome,
                "loss_type": loss_type,
                "confidence_error": abs(float(top_pick.get("velo_prime_prob") or 0.0) - (1.0 if outcome == "WIN" else 0.0)),
                "source_prediction": str(self.pred_file),
                "source_result": str(self.res_file)
            }
            
            # Strict HFS Block
            if "strictly_ordered_vector" in top_pick:
                 event["learning_allowed"] = False
                 event["failure_reason"] = "UNSAFE_HFS_FIELD_PRESENT"
                 self.failures.append({"type": "HFS_READ_ATTEMPTED", "race_id": rid})

            with open(self.events_path, "a") as f:
                f.write(json.dumps(event) + "\n")
            
            self.stats["events_created"] += 1
            if event["learning_allowed"]:
                if outcome == "WIN": self.stats["wins"] += 1
                elif outcome == "LOSS": self.stats["losses"] += 1
                else: self.stats["void_or_unknown"] += 1
                self.stats["loss_count_by_type"][loss_type] += 1

        if self.stats["matched_races"] == 0:
            self.failures.append({"type": "MATCHED_RACES_ZERO"})
            return self._finalize("FAIL")

        data_error_rate = self.stats["data_error_count"] / len(preds) if preds else 0
        if data_error_rate > self.data_error_threshold:
            self.failures.append({"type": "DATA_ERROR_RATE_EXCEEDED", "rate": data_error_rate})
            return self._finalize("FAIL")

        if self.dry_run:
            logger.info("Dry run complete. No updates applied.")
            return self._finalize("PASS")

        # 3. Apply to Shadow State (adapter handles idempotency if audit exists)
        # We use a dedicated audit file for this specific run to check idempotency locally
        nightly_audit_path = ROOT / "data" / f"playbook_g_nightly_audit_{self.date_tag}.json"
        
        adapter = PlaybookGShadowAdapter(str(self.events_path), str(self.state_path), str(nightly_audit_path))
        adapter.run()
        audit_1 = json.loads(nightly_audit_path.read_text())
        updates_1 = audit_1["engine_updates_applied"]
        
        # 4. Duplicate Check
        adapter.run()
        audit_2 = json.loads(nightly_audit_path.read_text())
        updates_2 = audit_2["engine_updates_applied"]
        duplicates_skipped = audit_2["events_skipped_duplicate"]
        
        if updates_2 > 0:
            self.failures.append({"type": "DUPLICATE_REPLAY_MUTATED_STATE", "updates": updates_2})
            return self._finalize("FAIL")

        if audit_1.get("doctrines_fired_dropped", 0) > 0 or audit_2.get("doctrines_fired_dropped", 0) > 0:
            self.failures.append({
                "type": "DOCTRINE_REGRESSION",
                "detail": "Raw events carried doctrines_fired that the adapter dropped -- "
                          "this is the 2026-04-25..2026-07-26 hardcoded-[] bug class recurring. "
                          "Fix scripts/playbook_g_shadow_adapter.py before trusting doctrine_strengths.",
            })
            return self._finalize("FAIL")

        live_hash_after = self._get_file_hash(self.live_state_path)
        if live_hash_before != live_hash_after:
            self.failures.append({"type": "LIVE_STATE_TOUCHED"})
            return self._finalize("FAIL")

        # Set final stats for finalize
        self.stats["updates_1"] = updates_1
        self.stats["updates_2"] = updates_2
        self.stats["dups"] = duplicates_skipped

        verdict = self._finalize("PASS")

        # 4b. Apply the SAME night's events to the LIVE state.
        # Authorized 2026-07-26 (operator sign-off) after the doctrines_fired
        # bug was fixed and both the shadow backfill and a full live catch-up
        # (2026-04-26..2026-07-26, 1714 races) were run and cross-checked for
        # consistency. Only runs after the shadow pass above has PASSED and
        # proven idempotency + no doctrine-drop regression on tonight's own
        # events, using the identical event file -- so this is not a blind
        # extra write, it's gated behind tonight's own shadow verification.
        if verdict == "PASS":
            try:
                from scripts.playbook_g_live_adapter import PlaybookGLiveAdapter
                live_audit_path = ROOT / "data" / f"playbook_g_live_nightly_audit_{self.date_tag}.json"
                live_adapter = PlaybookGLiveAdapter(
                    str(self.events_path), str(self.live_state_path), str(live_audit_path),
                    authorized=True,
                )
                live_adapter.run()
                live_audit = json.loads(live_audit_path.read_text())
                if live_audit.get("doctrines_fired_dropped", 0) > 0:
                    logger.error("LIVE playbook G update had doctrine-drop regression -- see %s", live_audit_path)
                else:
                    logger.info("LIVE playbook G state updated: verdict=%s updates=%s",
                                live_audit.get("verdict"), live_audit.get("engine_updates_applied"))
            except Exception as e:
                logger.error(f"LIVE playbook G update failed (shadow state is unaffected): {e}")
        
        # 5. Trigger Study Layer
        if verdict == "PASS":
            try:
                try:
                    from scripts.eod_result_study_layer import EODStudyLayer
                except ModuleNotFoundError:
                    from scripts.audit.eod_result_study_layer import EODStudyLayer
                study = EODStudyLayer(self.date_str)
                study.run()
                logger.info("Intelligence study layer complete")
            except Exception as e:
                logger.error(f"Failed to trigger study layer: {e}")
                
        return verdict

    def _adapter_state_facts(self) -> dict:
        """What the Playbook G adapters actually did, read from their own audits.

        The runner must not infer this from its own stats: the live adapter is a
        separate component that writes sentient_state.json after the runner's
        own hash guard has already passed, so nothing in self.failures or
        self.stats can see it. Publishing these alongside the guard means a
        reader can distinguish "nothing mutated live state unexpectedly" (the
        guard, live_sentient_state_touched) from "the authorized live adapter
        wrote N updates tonight" (here) -- a distinction that did not exist
        before 2026-08-02 and caused live evolution to be reported as
        shadow-only.
        """
        facts: dict = {}
        for label, path in (
            ("live_adapter", ROOT / "data" / f"playbook_g_live_nightly_audit_{self.date_tag}.json"),
            ("shadow_adapter", ROOT / "data" / f"playbook_g_nightly_audit_{self.date_tag}.json"),
        ):
            if not path.exists():
                facts[f"{label}_audit"] = "MISSING"
                facts[f"{label}_state_written"] = "UNKNOWN"
                continue
            try:
                a = json.loads(path.read_text())
            except Exception as e:
                facts[f"{label}_audit"] = f"UNREADABLE:{e}"
                facts[f"{label}_state_written"] = "UNKNOWN"
                continue
            facts[f"{label}_audit"] = str(path.relative_to(ROOT))
            facts[f"{label}_state_written"] = bool(
                a.get("live_state_touched") if label == "live_adapter" else a.get("shadow_state_touched")
            )
            facts[f"{label}_updates_applied"] = a.get("engine_updates_applied")
            facts[f"{label}_verdict"] = a.get("verdict")
        # Authorized by operator sign-off 2026-07-26; the runner only invokes the
        # live adapter on the verdict == "PASS" path, after the shadow pass has
        # proven idempotency on tonight's own events.
        facts["live_state_write_authorized"] = True
        return facts

    def _finalize(self, verdict: str):
        finished_at = datetime.now(timezone.utc).isoformat()
        
        status = {
            "date": self.date_str,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "learning_mode": "OUTCOME_ONLY_EOD_REPLAY",
            "prediction_count": self.stats["prediction_count"],
            "result_count": self.stats["result_count"],
            "matched_races": self.stats["matched_races"],
            "events_created": self.stats["events_created"],
            "engine_updates_applied_first_run": self.stats.get("updates_1", 0),
            "engine_updates_applied_duplicate_run": self.stats.get("updates_2", 0),
            "duplicates_skipped_second_run": self.stats.get("dups", 0),
            "wins": self.stats["wins"],
            "losses": self.stats["losses"],
            "void_or_unknown": self.stats["void_or_unknown"],
            "loss_count_by_type": dict(self.stats["loss_count_by_type"]),
            "data_error_count": self.stats["data_error_count"],
            "data_error_rate": self.stats["data_error_count"] / self.stats["prediction_count"] if self.stats["prediction_count"] > 0 else 0,
            # UNAUTHORIZED-mutation guard, scoped to the shadow/verification
            # phase only: run() hashes sentient_state.json before the shadow
            # adapters and again after, and appends LIVE_STATE_TOUCHED if it
            # changed. False here means "nothing mutated live state while the
            # shadow pass ran" -- which is the correct answer, and what
            # eod_result_study_layer's LIVE_STATE_MUTATION_DETECTED check is
            # for. Keep it.
            "live_sentient_state_touched": any(f["type"] == "LIVE_STATE_TOUCHED" for f in self.failures),
            "shadow_state_touched": self.stats.get("updates_1", 0) > 0,
            # ...but it says NOTHING about the AUTHORIZED live adapter, which
            # runs afterwards (operator sign-off 2026-07-26) and legitimately
            # writes sentient_state.json. Until 2026-08-02 the status file
            # reported only the guard, so a reader saw
            # live_sentient_state_touched=false and concluded live state was
            # untouched that night, while playbook_g_live_nightly_audit recorded
            # live_state_touched=true with 49 engine updates applied in the same
            # run. Both facts are now published, read from the adapters' own
            # audits rather than inferred from this runner's state.
            **self._adapter_state_facts(),
            "supabase_writes_attempted": any(f["type"] == "SUPABASE_WRITE_ATTEMPTED" for f in self.failures),
            "supabase_backup_attempted": False,
            "hfs_read_attempted": any(f["type"] == "HFS_READ_ATTEMPTED" for f in self.failures),
            "hfs_features_used": False,
            "verdict": verdict
        }
        
        self.status_path.write_text(json.dumps(status, indent=2))
        self.failures_path.write_text(json.dumps(self.failures, indent=2))
        
        # Create Council Audit — read actual Step 16b output, never copy runner verdict
        _council_run_path = ROOT / "data" / "council_runs" / f"council_run_{self.date_str}.json"
        _actual_council_verdict = "NOT_RUN"
        if _council_run_path.exists():
            try:
                _actual_council_verdict = json.loads(_council_run_path.read_text()).get("council_verdict", "NOT_RUN")
            except Exception:
                _actual_council_verdict = "READ_ERROR"

        council = {
            "date": self.date_str,
            "runner_verdict": verdict,
            "council_verdict": _actual_council_verdict,
            "council_source": str(_council_run_path),
            "files_verified": [str(self.status_path), str(self.failures_path), str(self.events_path)],
            "forbidden_files_changed": False,
            "live_sentient_state_touched": status["live_sentient_state_touched"],
            "supabase_writes_attempted": status["supabase_writes_attempted"],
            "hfs_features_used": False,
            "duplicates_blocked": status["duplicates_skipped_second_run"] > 0 or status["events_created"] == 0,
            "data_error_rate": status["data_error_rate"],
            "escalation_required": verdict == "FAIL",
            "escalation_reason": "Run failed" if verdict == "FAIL" else None
        }
        self.council_path.write_text(json.dumps(council, indent=2))
        
        logger.info(f"Nightly Run Finalized: {verdict}")
        return verdict

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-data-error-rate", type=float, default=0.1)
    parser.add_argument("--state", default="data/sentient_state_shadow.json")
    parser.add_argument("--pred-file", default=None)
    parser.add_argument("--result-file", default=None)
    args = parser.parse_args()
    
    target_date = args.date
    if not target_date:
        # Default to yesterday
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        
    runner = NightlyEODRunner(
        target_date,
        args.state,
        args.dry_run,
        args.fail_on_data_error_rate,
        pred_file=args.pred_file,
        result_file=args.result_file,
    )
    runner.run()
