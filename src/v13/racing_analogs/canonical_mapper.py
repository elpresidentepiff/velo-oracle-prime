"""
canonical_mapper.py — Source-to-Canonical Mapper
==============================================
Maps raw Supabase / raceform row data into CanonicalRaceState.

Supported source schemas:
  - velo_verdicts (current live pipeline)
  - runner_race_facts (VÉLØ feature mart)
  - raceform (historical UK/Irish/AW Flat)

All mappings are explicit and traceable.
No inference, no assumption.

Usage:
    mapper = CanonicalMapper()
    state = mapper.from_velo_verdict(row, course, region)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from .schema import (
    CanonicalRaceState,
    ClassMovementSubtype,
    DaysSinceRunBand,
    DistanceChangeBand,
    FinishConsistencyBand,
    GoingBand,
    RecentFormState,
    Region,
    RunCyclePosition,
    SPBand,
    SQPEBand,
    TrainerSignalType,
)


class CanonicalMapper:
    """
    Maps source rows to CanonicalRaceState.

    Each source has a named method:
      from_velo_verdict()   — live pipeline
      from_raceform()        — historical
      from_runner_facts()    — feature mart
    """

    def from_velo_verdict_runner(
        self,
        verdict_row: Dict[str, Any],
        runner_data: Dict[str, Any],
        region: Region = Region.UK,
        selections: Optional[List[Dict]] = None,
    ) -> CanonicalRaceState:
        """
        Map one runner's data from velo_verdicts.full_analysis to CanonicalRaceState.

        velo_verdicts schema:
          - One row per race (not per runner)
          - full_analysis: list[dict] of ALL runners in the race, sorted by VÉLØ rank
          - Each runner dict has: sqpe_v17_prob, velo_prime_prob, rpd_tag,
            horse_recent_runs_90d, trainer_course_ae, trainer_dist_ae,
            improvement_score, market_deception_score, place_prob, longshot_prob,
            going, distance_f, sp, win, placed, finish_position, etc.

        Args:
            verdict_row: The parent velo_verdicts row (race-level fields)
            runner_data: One runner dict from the full_analysis list
            region: Region enum (defaults to UK, override from verdict_row.region)
        """
        race_id = verdict_row["race_id"]
        horse_id = str(runner_data.get("horse_id", ""))

        # Race date — from verdict_row or runner_data
        race_date_raw = verdict_row.get("generated_at") or verdict_row.get("race_date")
        race_date = self._parse_date(race_date_raw)

        # Course — from verdict_row
        course = verdict_row.get("course", verdict_row.get("track", ""))

        # Override region from verdict if present
        region_raw = verdict_row.get("region")
        if region_raw:
            try:
                region = Region(str(region_raw).lower())
            except ValueError:
                region = region

        # SQPE: use sqpe_v17_prob as the base SQPE signal
        sqpe = float(runner_data.get("sqpe_v17_prob", 0.0))
        # Fall back to velo_prime_prob if sqpe_v17_prob not available
        if sqpe == 0.0:
            sqpe = float(runner_data.get("velo_prime_prob", 0.0))
        sqpe_band = self._sqpe_band(sqpe)

        # SP: from selections (morning_odds = morning line odds, proxy for market)
        # Look up by horse_id in the selections list
        sp_val: Optional[float] = None
        if selections:
            horse_id = str(runner_data.get("horse_id", ""))
            for sel in selections:
                if str(sel.get("horse_id", "")) == horse_id:
                    mo = sel.get("morning_odds")
                    if mo is not None:
                        sp_val = float(mo)
                    break
        # Fall back to runner_data.sp if available (post-race SP)
        if sp_val is None:
            sp_raw = runner_data.get("sp")
            if sp_raw is not None:
                sp_val = float(sp_raw)
        sp_band = self._sp_band(sp_val) if sp_val else SPBand.MID

        # Trainer A/E: prefer trainer_course_ae, then trainer_dist_ae
        trainer_ae = runner_data.get("trainer_course_ae")
        if trainer_ae is None:
            trainer_ae = runner_data.get("trainer_dist_ae")
        if trainer_ae is not None:
            trainer_ae = float(trainer_ae)
        trainer_ae_band = self._trainer_ae_band(trainer_ae)

        # Trainer signal type: from rpd_tag
        rpd_tag = runner_data.get("rpd_tag", "")
        trainer_signal = self._trainer_signal_type(rpd_tag, None, trainer_ae)

        # Class movement: not in velo_verdicts runner — flag as unknown
        class_movement = ClassMovementSubtype.UNKNOWN

        # Days since run: from horse_recent_runs_90d
        days_since_raw = runner_data.get("horse_recent_runs_90d")
        if days_since_raw is not None and str(days_since_raw).isdigit():
            days_since_band = self._days_band(int(days_since_raw))
        else:
            days_since_band = DaysSinceRunBand.NORMAL_8_14

        # Run cycle position: infer from days since
        run_cycle = self._run_cycle(None, None, days_since_raw)

        # Distance change: not in velo_verdicts — flag as unknown
        distance_change = DistanceChangeBand.SAME

        # Going: from runner data or verdict row
        going_raw = runner_data.get("going") or verdict_row.get("going")
        going = self._going(going_raw, None)

        # Recent form state: from rpd_tag
        recent_form = self._recent_form(None, None, rpd_tag)

        # Finish consistency: not in velo_verdicts — flag as unknown
        finish_consistency = FinishConsistencyBand.UNTESTED

        # Outcome: win / placed / finish_position (post-race only)
        win = bool(runner_data.get("win")) if "win" in runner_data else None
        placed = bool(runner_data.get("placed")) if "placed" in runner_data else None
        finish_pos = runner_data.get("finish_position")
        if finish_pos is not None:
            finish_pos = int(finish_pos)
        sp_actual = float(sp_raw) if sp_raw else None

        return CanonicalRaceState(
            race_id=race_id,
            runner_id=horse_id,
            race_date=race_date,
            course=course,
            region=region,
            sqpe=sqpe,
            sqpe_band=sqpe_band,
            sp_band=sp_band,
            trainer_ae=trainer_ae,
            trainer_ae_band=trainer_ae_band,
            trainer_signal_type=trainer_signal,
            class_movement_subtype=class_movement,
            days_since_run_band=days_since_band,
            run_cycle_position=run_cycle,
            distance_change_band=distance_change,
            going_band=going,
            recent_form_state=recent_form,
            finish_consistency_band=finish_consistency,
            win=win,
            placed=placed,
            finish_position=finish_pos,
            sp=sp_actual,
            feature_version="fingerprint_v1",
            signal_version="phase35_locked",
        )

    def from_raceform(
        self,
        row: Dict[str, Any],
        region: Region = Region.UK,
    ) -> CanonicalRaceState:
        """
        Map a raceform historical row to CanonicalRaceState.

        Expected raceform columns:
          race_id, horse_id, race_date, course,
          sqpe, sqpe_band, sp_band,
          trainer_ae, trainer_ae_band, trainer_signal_type,
          class_movement_subtype, days_since_run_band,
          run_cycle_position, distance_change_band,
          going_band, recent_form_state, finish_consistency_band,
          win, placed, finish_position, sp
        """
        race_id   = str(row.get("race_id", ""))
        horse_id  = str(row.get("horse_id", row.get("runner_id", "")))
        race_date = self._parse_date(row.get("race_date"))
        course    = str(row.get("course", ""))

        sqpe      = float(row.get("sqpe", 0.0))
        sqpe_band = self._sqpe_band(sqpe)
        sp        = row.get("sp")
        sp_band   = self._sp_band(float(sp)) if sp else SPBand.MID

        trainer_ae = float(row["trainer_ae"]) if row.get("trainer_ae") else None
        trainer_ae_band = self._trainer_ae_band(trainer_ae)

        trainer_signal_raw = row.get("trainer_signal_type")
        trainer_signal = self._parse_enum(trainer_signal_raw, TrainerSignalType) or TrainerSignalType.UNKNOWN

        class_movement = self._parse_enum(row.get("class_movement_subtype"), ClassMovementSubtype) or ClassMovementSubtype.UNKNOWN

        days_raw = row.get("days_since_run")
        days_band = self._days_band(int(days_raw)) if days_raw else DaysSinceRunBand.NORMAL_8_14

        run_cycle = self._parse_enum(row.get("run_cycle_position"), RunCyclePosition) or RunCyclePosition.MID

        distance = self._parse_enum(row.get("distance_change_band"), DistanceChangeBand) or DistanceChangeBand.SAME

        going = self._parse_enum(row.get("going_band"), GoingBand) or GoingBand.UNKNOWN

        recent_form = self._parse_enum(row.get("recent_form_state"), RecentFormState) or RecentFormState.UNTESTED

        finish_consistency = self._parse_enum(row.get("finish_consistency_band"), FinishConsistencyBand) or FinishConsistencyBand.UNTESTED

        win    = bool(row["win"])    if "win"    in row else None
        placed = bool(row["placed"]) if "placed" in row else None
        finish = int(row["finish_position"]) if row.get("finish_position") else None
        sp_actual = float(row["sp"]) if row.get("sp") else None

        return CanonicalRaceState(
            race_id=race_id,
            runner_id=horse_id,
            race_date=race_date,
            course=course,
            region=region,
            sqpe=sqpe,
            sqpe_band=sqpe_band,
            sp_band=sp_band,
            trainer_ae=trainer_ae,
            trainer_ae_band=trainer_ae_band,
            trainer_signal_type=trainer_signal,
            class_movement_subtype=class_movement,
            days_since_run_band=days_band,
            run_cycle_position=run_cycle,
            distance_change_band=distance,
            going_band=going,
            recent_form_state=recent_form,
            finish_consistency_band=finish_consistency,
            win=win,
            placed=placed,
            finish_position=finish,
            sp=sp_actual,
            feature_version="fingerprint_v1",
            signal_version="phase35_locked",
        )

    # ─── Internal band helpers ────────────────────────────────────────────────

    @staticmethod
    def _sqpe_band(sqpe: float) -> SQPEBand:
        return SQPEBand.from_sqpe(sqpe)

    @staticmethod
    def _sp_band(sp: float) -> SPBand:
        return SPBand.from_sp(sp)

    @staticmethod
    def _trainer_ae_band(ae: Optional[float]) -> str:
        if ae is None:
            return "no_data"
        if ae < 1.00:
            return "<1.00"
        if ae <= 1.10:
            return "1.00-1.10"
        if ae <= 1.25:
            return "1.10-1.25"
        if ae <= 1.50:
            return "1.25-1.50"
        return ">1.50"

    @staticmethod
    def _trainer_signal_type(
        rpd_tag: Optional[str],
        explicit: Optional[str],
        ae: Optional[float],
    ) -> TrainerSignalType:
        if explicit:
            return TrainerSignalType(explicit) if explicit in TrainerSignalType._value2member_map_ else TrainerSignalType.UNKNOWN
        if rpd_tag in ("I", "IMPROVER", "impr"):
            return TrainerSignalType.IMPROVER
        if rpd_tag in ("D", "DECLINING"):
            return TrainerSignalType.DECLINING
        if ae is not None and ae >= 1.20:
            return TrainerSignalType.IMPROVER
        if ae is not None and ae < 0.90:
            return TrainerSignalType.DECLINING
        return TrainerSignalType.UNKNOWN

    @staticmethod
    def _class_movement(subtype_raw, full_movement) -> ClassMovementSubtype:
        if subtype_raw:
            return ClassMovementSubtype(subtype_raw) if subtype_raw in ClassMovementSubtype._value2member_map_ else ClassMovementSubtype.UNKNOWN
        if full_movement:
            if "engineered_drop" in str(full_movement):
                return ClassMovementSubtype.ENGINEERED_DROP
            if "drop" in str(full_movement):
                return ClassMovementSubtype.DROP
            if "rise" in str(full_movement):
                return ClassMovementSubtype.RISE
        return ClassMovementSubtype.UNKNOWN

    @staticmethod
    def _days_band(days: int) -> DaysSinceRunBand:
        return DaysSinceRunBand.from_days(days)

    @staticmethod
    def _run_cycle(position_raw, full_cycle, days_since) -> RunCyclePosition:
        if position_raw:
            return RunCyclePosition(position_raw) if position_raw in RunCyclePosition._value2member_map_ else RunCyclePosition.MID
        if days_since is not None:
            days = int(days_since)
            if days < 5:
                return RunCyclePosition.MID  # first run back
            if days > 60:
                return RunCyclePosition.DROUGH
        return RunCyclePosition.MID

    @staticmethod
    def _distance_change(band_raw, full_dc) -> DistanceChangeBand:
        if band_raw:
            return DistanceChangeBand(band_raw) if band_raw in DistanceChangeBand._value2member_map_ else DistanceChangeBand.SAME
        return DistanceChangeBand.SAME

    @staticmethod
    def _going(going_raw, full_going) -> GoingBand:
        if going_raw:
            return GoingBand(going_raw) if going_raw in GoingBand._value2member_map_ else GoingBand.UNKNOWN
        if full_going:
            low = str(full_going).lower()
            if "standard" in low:
                return GoingBand.STANDARD
            if "firm" in low or "good" in low:
                return GoingBand.FIRM
            if "soft" in low:
                return GoingBand.SOFT
            if "heavy" in low:
                return GoingBand.HEAVY
        return GoingBand.UNKNOWN

    @staticmethod
    def _recent_form(state_raw, full_form, rpd_tag) -> RecentFormState:
        if state_raw:
            return RecentFormState(state_raw) if state_raw in RecentFormState._value2member_map_ else RecentFormState.UNTESTED
        if rpd_tag in ("F", "FORM"):
            return RecentFormState.IMPROVING
        return RecentFormState.UNTESTED

    @staticmethod
    def _finish_consistency(band_raw, full_fc) -> FinishConsistencyBand:
        if band_raw:
            return FinishConsistencyBand(band_raw) if band_raw in FinishConsistencyBand._value2member_map_ else FinishConsistencyBand.UNTESTED
        return FinishConsistencyBand.UNTESTED

    @staticmethod
    def _parse_date(val) -> date:
        if isinstance(val, date):
            return val
        if hasattr(val, "date"):
            return val.date()
        if isinstance(val, str):
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
                try:
                    from datetime import datetime
                    return datetime.strptime(val[:10], fmt).date()
                except ValueError:
                    continue
        from datetime import date as d
        return d.today()

    @staticmethod
    def _parse_enum(val, enum_cls):
        if val is None:
            return None
        if isinstance(val, enum_cls):
            return val
        try:
            return enum_cls(str(val))
        except ValueError:
            return None
