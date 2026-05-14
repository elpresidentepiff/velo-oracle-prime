"""
VÉLØ Learning Engine — Phase 3A
Builds verified learning events from prediction artifacts + sigma results.
Phase 3B shadow consumption is not yet implemented.

Event sources (in priority order):
  1. data/velo_prime_verdicts_{date}.json  — prediction fields, sidecars
  2. data/results_{date}.json             — winner, SP, finishing position
  3. Supabase sigma_audits                — outcome classification (WIN/MISS/PLACED)

Events are only built for races that have a sigma_audits row.
Tier X and result-missing races are naturally excluded.

HFS context policy:
  mpi_source='derived_from_vp_mds' and chaos_bloom_source='derived_from_macro_field_trap'
  are proxy-derived values, NOT true HFS signals.
  missing_hfs_context=True for all current pipeline events.
  hfs_context_quality='proxy_derived' always for current pipeline output.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("velo.learning_engine")

ROOT = Path(__file__).resolve().parents[2]

# Sources that are proxy-derived, not true HFS
_PROXY_SOURCES = frozenset({
    "derived_from_vp_mds",
    "derived_from_macro_field_trap",
})


def _make_event_id(run_date: str, race_id: str, horse_id: str, event_type: str) -> str:
    """Deterministic 16-hex-char event ID."""
    raw = f"{run_date}:{race_id}:{horse_id}:{event_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _classify_hfs_context(top: dict) -> tuple[bool, str, str | None]:
    """
    Returns (missing_hfs_context, hfs_context_quality, missing_hfs_reason).

    missing_hfs_context=True unless values are proven from true HFS.
    All current pipeline output uses proxy-derived mpi/chaos — always proxy_derived.
    """
    mpi_source = top.get("mpi_source") or ""
    chaos_source = top.get("chaos_bloom_source") or ""
    horse_state_failed = bool(top.get("horse_state_failed", False))
    horse_state = top.get("horse_state") or {}

    is_proxy = (
        mpi_source in _PROXY_SOURCES
        or chaos_source in _PROXY_SOURCES
        or horse_state_failed
        or not horse_state
    )

    if is_proxy:
        parts: list[str] = []
        if mpi_source in _PROXY_SOURCES or chaos_source in _PROXY_SOURCES:
            parts.append("mpi/chaos present but proxy-derived, not HFS-originated")
        if horse_state_failed:
            parts.append("horse_state_failed")
        elif not horse_state:
            parts.append("horse_state_empty")
        reason = "; ".join(parts) or "proxy_derived"
        return True, "proxy_derived", reason

    return False, "hfs_originated", None


class LearningEngine:
    """
    VÉLØ learning event builder.
    Phase 3A: build events, write to velo_learning_events.
    Phase 3B: shadow consume — not yet implemented.
    """

    def __init__(
        self,
        dry_run: bool = True,
        execute: bool = False,
        target_state: str = "shadow_repair_v1",
    ) -> None:
        self.dry_run = dry_run
        self.execute = execute
        self.target_state = target_state
        self._sb = None

    def _get_sb(self):
        if self._sb is None:
            from src.data.supabase_client import get_supabase_client  # noqa: PLC0415
            self._sb = get_supabase_client()
        return self._sb

    # ── Data loaders ──────────────────────────────────────────────────────────

    def _load_verdicts(self, date: str) -> list[dict]:
        date_key = date.replace("-", "_")
        path = ROOT / "data" / f"velo_prime_verdicts_{date_key}.json"
        if not path.exists():
            logger.warning("[LearningEngine] verdict file not found: %s", path)
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []

    def _load_results_index(self, date: str) -> dict[str, dict]:
        """Index results_{date}.json as {race_id: winner_fields + runners}."""
        date_key = date.replace("-", "_")
        path = ROOT / "data" / f"results_{date_key}.json"
        if not path.exists():
            logger.warning("[LearningEngine] results file not found: %s", path)
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        races: list[dict] = (
            raw.get("results", []) if isinstance(raw, dict)
            else (raw if isinstance(raw, list) else [])
        )
        index: dict[str, dict] = {}
        for race in races:
            race_id = race.get("race_id")
            if not race_id:
                continue
            runners = race.get("runners", [])
            winner = next((r for r in runners if str(r.get("position", "")) == "1"), None)
            if not winner:
                continue
            bsp = winner.get("bsp") or None
            if bsp == "":
                bsp = None
            index[race_id] = {
                "winner_name": winner.get("horse", ""),
                "winner_id": winner.get("horse_id", ""),
                "winner_sp": winner.get("sp_dec"),
                "winner_bsp": bsp,
                "runners": runners,
            }
        return index

    def _load_sigma_audits(self, date: str) -> dict[str, dict]:
        """Index sigma_audits rows as {race_id: row}. Always reads — read-only operation."""
        try:
            result = (
                self._get_sb().client
                .table("sigma_audits")
                .select(
                    "race_id,outcome,decision_tier,horse_id,"
                    "actual_winner_id,actual_winner_sp,actual_winner_name,off_time"
                )
                .eq("date", date)
                .execute()
            )
            return {row["race_id"]: row for row in (result.data or [])}
        except Exception as exc:
            logger.warning("[LearningEngine] sigma_audits query failed: %s", exc)
            return {}

    @staticmethod
    def _predicted_position(runners: list[dict], horse_id: str) -> int | None:
        """Look up finishing position of predicted horse from full field runners list."""
        for r in runners:
            if r.get("horse_id") == horse_id:
                pos = r.get("position")
                try:
                    return int(pos)
                except (TypeError, ValueError):
                    pass
        return None

    # ── Event building ────────────────────────────────────────────────────────

    def create_learning_events(self, date: str) -> list[dict]:
        logger.info("[LearningEngine] Building learning events for %s", date)

        verdicts = self._load_verdicts(date)
        results_index = self._load_results_index(date)
        sigma_index = self._load_sigma_audits(date)

        if not sigma_index:
            logger.warning("[LearningEngine] No sigma_audits for %s — zero events built", date)
            return []

        events: list[dict] = []

        for verdict in verdicts:
            race_id = verdict.get("race_id")
            if not race_id:
                continue

            sigma = sigma_index.get(race_id)
            if not sigma:
                # Tier X blocked, no result, or race unscored — skip
                continue

            result = results_index.get(race_id)
            top = verdict.get("top") or {}

            horse_id: str = top.get("horse_id") or ""
            predicted_horse: str = top.get("horse") or ""

            event_id = _make_event_id(date, race_id, horse_id, "sigma_reconciliation")
            consumption_id = f"{event_id}:{self.target_state}"

            missing_hfs, hfs_quality, hfs_reason = _classify_hfs_context(top)

            # ── Prediction JSONB ──────────────────────────────────────────────
            velo_prime_prob = float(top.get("velo_prime_prob") or 0.0)
            prediction_blob: dict[str, Any] = {
                "predicted_horse": predicted_horse,
                "horse_id": horse_id or None,
                "velo_prime_prob": velo_prime_prob,
                "decision_tier": verdict.get("tier"),
                "vp30": velo_prime_prob >= 0.30,
                "mds_high": float(top.get("market_deception_score") or 0) > 0.50,
                "improve_high": float(top.get("improvement_score") or 0) > 0.40,
                "cash_run_flag": bool(top.get("cash_run_flag", False)),
            }

            # ── Result JSONB ──────────────────────────────────────────────────
            outcome = sigma.get("outcome", "")
            actual_winner_name = sigma.get("actual_winner_name") or (result or {}).get("winner_name")
            actual_winner_id = sigma.get("actual_winner_id") or (result or {}).get("winner_id")
            actual_sp = sigma.get("actual_winner_sp")
            if actual_sp is None and result:
                actual_sp = result.get("winner_sp")
            bsp = (result or {}).get("winner_bsp")
            finishing_pos = (
                self._predicted_position(result["runners"], horse_id)
                if result and horse_id
                else None
            )

            result_blob: dict[str, Any] = {
                "actual_winner": actual_winner_name,
                "actual_winner_id": actual_winner_id,
                "won": outcome == "WIN",
                "placed": outcome in ("WIN", "PLACED"),
                "sp": actual_sp,
                "bsp": bsp,
                "finishing_position": finishing_pos,
                "result_source": "sigma_audits+results_json" if result else "sigma_audits",
            }

            # ── Sidecars JSONB ────────────────────────────────────────────────
            # mpi/chaos recorded with sources — proxy-derived, not fabricated.
            mpi_val = top.get("mpi")
            chaos_val = top.get("chaos_bloom")
            mpi_source = top.get("mpi_source")
            chaos_source = top.get("chaos_bloom_source")

            # race_context preserved for Phase 3B — Playbook G must receive full context.
            race_context: dict[str, Any] = {
                "race_id": race_id,
                "course": verdict.get("course"),
                "off_time": verdict.get("off_time") or sigma.get("off_time"),
                "mpi": mpi_val,
                "mpi_source": mpi_source,
                "chaos_bloom": chaos_val,
                "chaos_bloom_source": chaos_source,
                "narrative_disruption": None,
                "narrative_disruption_source": None,
                "hfs_context_quality": hfs_quality,
                "missing_hfs_context": missing_hfs,
                "runners": [],
            }

            sidecars_blob: dict[str, Any] = {
                "market_deception_score": top.get("market_deception_score"),
                "improvement_score": top.get("improvement_score"),
                "sqpe": top.get("sqpe_v17_prob"),
                "cashrun": bool(top.get("cash_run_flag", False)),
                "mpi": mpi_val,
                "mpi_source": mpi_source,
                "chaos_bloom": chaos_val,
                "chaos_bloom_source": chaos_source,
                "narrative_disruption": None,
                "narrative_disruption_source": None,
                "hfs_context_quality": hfs_quality,
                "missing_hfs_context": missing_hfs,
                "missing_hfs_reason": hfs_reason,
                "race_context": race_context,
            }

            events.append({
                "run_date": date,
                "race_id": race_id,
                "horse_id": horse_id or None,
                "event_type": "sigma_reconciliation",
                "event_id": event_id,
                "target_state_name": self.target_state,
                "consumption_id": consumption_id,
                "prediction": prediction_blob,
                "result": result_blob,
                "sidecars": sidecars_blob,
                "learning_allowed": True,   # shadow-eligible; consumed_live never set
                "missing_hfs_context": missing_hfs,
                "consumed_shadow": False,
                "consumed_live": False,
            })

        logger.info("[LearningEngine] Built %d learning events for %s", len(events), date)
        return events

    # ── DB write ──────────────────────────────────────────────────────────────

    def write_events_to_db(
        self, events: list[dict], sample_size: int | None = None
    ) -> dict[str, Any]:
        """
        Upsert events into velo_learning_events.
        Idempotent: ignore_duplicates=True — re-run never creates duplicates.
        consumed_shadow and consumed_live are NEVER set here — Phase 3B only.
        """
        if not self.execute:
            return {"written": 0, "skipped": 0, "status": "dry_run"}

        batch = events[:sample_size] if sample_size else events
        written = 0
        skipped = 0
        event_ids: list[str] = []

        for event in batch:
            row = {
                "run_date": event["run_date"],
                "race_id": event["race_id"],
                "horse_id": event.get("horse_id"),
                "event_type": event["event_type"],
                "event_id": event["event_id"],
                "target_state_name": event["target_state_name"],
                "consumption_id": event["consumption_id"],
                "prediction": event["prediction"],
                "result": event["result"],
                "sidecars": event["sidecars"],
                "learning_allowed": event["learning_allowed"],
                "missing_hfs_context": event["missing_hfs_context"],
                "consumed_shadow": False,
                "consumed_live": False,
            }
            try:
                res = (
                    self._get_sb().client
                    .table("velo_learning_events")
                    .upsert(row, on_conflict="event_id,target_state_name", ignore_duplicates=True)
                    .execute()
                )
                if res.data:
                    written += 1
                    event_ids.append(event["event_id"])
                else:
                    skipped += 1  # already existed — idempotent skip
            except Exception as exc:
                logger.warning("[LearningEngine] upsert failed for %s: %s", event["event_id"], exc)
                skipped += 1

        return {
            "written": written,
            "skipped": skipped,
            "event_ids": event_ids,
            "status": "ok",
        }

    # ── Phase 3B ──────────────────────────────────────────────────────────────

    def read_unconsumed_events(self, date: str) -> list[dict]:
        """Read velo_learning_events rows that are not yet shadow-consumed for this date + target_state."""
        try:
            result = (
                self._get_sb().client
                .table("velo_learning_events")
                .select("*")
                .eq("run_date", date)
                .eq("target_state_name", self.target_state)
                .eq("consumed_shadow", False)
                .eq("learning_allowed", True)
                .execute()
            )
            rows = result.data or []
            logger.info(
                "[LearningEngine] Found %d unconsumed events for %s / %s",
                len(rows), date, self.target_state,
            )
            return rows
        except Exception as exc:
            logger.warning("[LearningEngine] read_unconsumed_events failed: %s", exc)
            return []

    def generate_daily_report(
        self,
        date: str,
        pipeline: dict,
        preflight: dict,
        consume_result: dict,
        warnings: list[str],
    ) -> dict[str, Any]:
        """
        Assemble the Phase 4 forensic report.
        Always attempts DB reads (read-only); degrades gracefully if unavailable.
        Does not write or mutate any state.
        """
        # ── File state (post-run) ─────────────────────────────────────────────
        live_path = ROOT / "data" / "sentient_state.json"
        live_hash_before = preflight.get("live_state", {}).get("hash")
        live_state: dict[str, Any] = {"exists": False}
        if live_path.exists():
            raw = live_path.read_bytes()
            ld = json.loads(raw)
            live_hash_now = hashlib.md5(raw).hexdigest()
            live_state = {
                "races": ld.get("total_races_observed", 0),
                "last_updated": ld.get("last_updated"),
                "hash": live_hash_now,
                "touched": (live_hash_now != live_hash_before) if live_hash_before else False,
            }

        shadow_path = ROOT / "data" / f"sentient_state_{self.target_state}.json"
        shadow_state: dict[str, Any] = {"exists": False}
        if shadow_path.exists():
            raw = shadow_path.read_bytes()
            sd = json.loads(raw)
            shadow_state = {
                "races": sd.get("total_races_observed", 0),
                "last_updated": sd.get("last_updated"),
                "hash": hashlib.md5(raw).hexdigest(),
            }

        # ── DB reads (always attempted) ───────────────────────────────────────
        event_counts: dict[str, Any] = {}
        cloud_backup: dict[str, Any] = {}
        try:
            r = (
                self._get_sb().client
                .table("velo_learning_events")
                .select("consumed_shadow,consumed_live,missing_hfs_context,sidecars")
                .eq("run_date", date)
                .eq("target_state_name", self.target_state)
                .execute()
            )
            rows = r.data or []
            event_counts = {
                "total": len(rows),
                "consumed_shadow_true": sum(1 for x in rows if x["consumed_shadow"]),
                "consumed_shadow_false": sum(1 for x in rows if not x["consumed_shadow"]),
                "consumed_live_true": sum(1 for x in rows if x["consumed_live"]),
                "missing_hfs_context_all": all(x["missing_hfs_context"] for x in rows) if rows else None,
                "hfs_quality_proxy_all": all(
                    (x.get("sidecars") or {}).get("hfs_context_quality") == "proxy_derived"
                    for x in rows
                ) if rows else None,
            }
        except Exception as exc:
            event_counts = {"error": str(exc)}

        try:
            cb = (
                self._get_sb().client
                .table("learned_patterns")
                .select("occurrences,last_observed,updated_at")
                .eq("pattern_name", "SENTIENT_STATE_BACKUP")
                .execute()
            )
            cloud_backup = cb.data[0] if cb.data else {"exists": False}
        except Exception as exc:
            cloud_backup = {"error": str(exc)}

        # ── Overall status (DB ground truth) ──────────────────────────────────
        consumed_live_any = event_counts.get("consumed_live_true", 0) > 0
        sigma_failed = pipeline.get("sigma", {}).get("status") == "FAIL"
        all_consumed = (
            event_counts.get("consumed_shadow_false", None) == 0
            and event_counts.get("total", 0) > 0
        )
        no_events_in_db = event_counts.get("total", 0) == 0
        partial_consume = consume_result.get("skipped", 0) > 0 or (
            event_counts.get("consumed_shadow_false", 0) > 0
        )

        if consumed_live_any:
            overall = "SAFETY_VIOLATION"
        elif sigma_failed:
            overall = "SIGMA_FAILED"
        elif no_events_in_db:
            overall = "ZERO_EVENTS"
        elif all_consumed:
            overall = "SHADOW_CYCLE_CLOSED"
        elif partial_consume:
            overall = "PARTIAL"
        else:
            overall = "SHADOW_CYCLE_CLOSED"

        before_races = preflight.get("shadow_state", {}).get("races") or consume_result.get("before_race_count")
        after_races = shadow_state.get("races", 0)

        cloud_backup_touched = None
        preflight_cloud_ts = preflight.get("cloud_backup", {}).get("updated_at")
        current_cloud_ts = cloud_backup.get("updated_at")
        if preflight_cloud_ts and current_cloud_ts:
            cloud_backup_touched = current_cloud_ts != preflight_cloud_ts

        return {
            "report_date": date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_version": "phase4_v1",
            "pipeline": pipeline,
            "shadow_ledger": {
                "target_state": self.target_state,
                "before_races": before_races,
                "after_races": after_races,
                "delta": (after_races - before_races) if before_races is not None else None,
                "last_updated": shadow_state.get("last_updated"),
                "total_events": event_counts.get("total", 0),
                "consumed_shadow": event_counts.get("consumed_shadow_true", 0),
                "consumed_live": event_counts.get("consumed_live_true", 0),
                "missing_hfs_context_all": event_counts.get("missing_hfs_context_all"),
                "hfs_context_quality_all": "proxy_derived",
            },
            "live_state_audit": live_state,
            "safety_audit": {
                "consumed_live_any": consumed_live_any,
                "live_state_touched": live_state.get("touched", False),
                "cloud_backup_touched": cloud_backup_touched,
                "playbook_g_promoted": False,
                "scoring_changed": False,
            },
            "cloud_backup": cloud_backup,
            "overall_status": overall,
            "warnings": warnings,
            "stop_reason": None,
        }

    def consume_events_into_shadow(self, events: list[dict]) -> dict[str, Any]:
        """
        Phase 3B — consume learning events into shadow Playbook G state.
        Loads data/sentient_state_{target_state}.json via SentientLoopbackEngine
        with disable_cloud_backup=True. Marks consumed_shadow=True per row after
        each successful observe_race_outcome call. consumed_live is never set.
        """
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine  # noqa: PLC0415

        if not events:
            logger.info("[LearningEngine] consume_events_into_shadow: no events to consume")
            return {"consumed": 0, "skipped": 0, "status": "no_events", "before_race_count": 0, "after_race_count": 0}

        shadow_path = str(ROOT / "data" / f"sentient_state_{self.target_state}.json")
        g = SentientLoopbackEngine(state_file=shadow_path, disable_cloud_backup=True)
        before_count = g.state.get("total_races_observed", 0)

        consumed = 0
        skipped = 0
        consumed_ids: list[str] = []

        for event in events:
            event_id = event.get("event_id", "?")
            pred_blob = event.get("prediction") or {}
            result_blob = event.get("result") or {}
            sidecars = event.get("sidecars") or {}
            race_ctx = sidecars.get("race_context") or {}

            race_data: dict[str, Any] = {
                "race_id": race_ctx.get("race_id") or event.get("race_id"),
                "course": race_ctx.get("course"),
                "off_time": race_ctx.get("off_time"),
                # Coerce None to safe numeric defaults — SentientLoopbackEngine uses > / < comparisons.
                # mpi/chaos_bloom are proxy-derived (0–1 scale) or absent; 0 / 0 won't trigger thresholds.
                "mpi": race_ctx.get("mpi") or 0,
                "mpi_source": race_ctx.get("mpi_source"),
                "chaos_bloom": race_ctx.get("chaos_bloom") or 0,
                "chaos_bloom_source": race_ctx.get("chaos_bloom_source"),
                "narrative_disruption": race_ctx.get("narrative_disruption") or 0,
                "integrity_score": race_ctx.get("integrity_score") or 100,
                "hfs_context_quality": race_ctx.get("hfs_context_quality"),
                "missing_hfs_context": race_ctx.get("missing_hfs_context"),
            }

            prediction: dict[str, Any] = {
                "power_anchor": pred_blob.get("predicted_horse", ""),
                "confidence": float(pred_blob.get("velo_prime_prob") or 0.0),
            }

            actual_result: dict[str, Any] = {
                "winner": result_blob.get("actual_winner", ""),
                "sp": float(result_blob.get("sp") or 0.0),
                "won": bool(result_blob.get("won", False)),
                "placed": bool(result_blob.get("placed", False)),
                "finishing_position": result_blob.get("finishing_position"),
                "favourite_won": False,  # not tracked in sigma_audits
                "winner_profile": {},    # not available at this stage
            }

            try:
                g.observe_race_outcome(race_data, prediction, actual_result)
                if self.execute:
                    self._get_sb().client.table("velo_learning_events").update(
                        {"consumed_shadow": True}
                    ).eq("event_id", event_id).eq("target_state_name", self.target_state).execute()
                consumed += 1
                consumed_ids.append(event_id)
                logger.info(
                    "[LearningEngine] Consumed event %s (horse=%s won=%s)",
                    event_id, prediction["power_anchor"], actual_result["won"],
                )
            except Exception as exc:
                logger.warning("[LearningEngine] consume failed for event %s: %s", event_id, exc)
                skipped += 1

        after_count = g.state.get("total_races_observed", 0)
        logger.info(
            "[LearningEngine] Shadow consume complete: consumed=%d skipped=%d races %d→%d",
            consumed, skipped, before_count, after_count,
        )

        return {
            "consumed": consumed,
            "skipped": skipped,
            "consumed_ids": consumed_ids,
            "before_race_count": before_count,
            "after_race_count": after_count,
            "status": "ok" if consumed > 0 else "nothing_consumed",
        }
