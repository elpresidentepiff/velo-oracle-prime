"""
raceform_feature_deriver.py — Raw Raceform → Canonical State
============================================================
Derives the 13 locked fingerprint features from raw raceform columns.

Source:     raceform table (1.3M+ historical rows)
Output:     dict of derived features, consumable by canonical_mapper.from_raceform()
            OR by ShadowRunner._map_rows() directly

Scope:      UK/Irish/AW Flat only (Phase 3.5 scope)
Feature set: LOCKED to fingerprint_v1 — no widening

Derivation strategy
--------------------
Where direct data exists: use it
Where inference is needed: best-effort heuristic, flagged with confidence
Where derivation is not possible: NULL with derivation_note field

Usage:
    from raceform_feature_deriver import RaceformFeatureDeriver
    deriver = RaceformFeatureDeriver()
    for row in raceform_rows:
        features = deriver.derive(row)
        state = deriver.to_canonical(row, features)
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

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


# ─── Constants ────────────────────────────────────────────────────────────────

PHASE3_5_MIN_SQPE = 0.50
PHASE3_5_MAX_SQPE = 0.60
SWEET_SP_MIN = 5.0
SWEET_SP_MAX = 13.0
TRAINER_AE_MIN_EDGE = 1.05

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_enum_value(enum_cls: type, val: Any, default: Any) -> Any:
    """
    Safely parse a string value into a string-valued Enum member.

    For str(Enum) subclasses, Enum(value) searches by VALUE, not by name.
    This helper wraps the lookup with a fallback.

    Args:
        enum_cls:  The enum class e.g. RunCyclePosition
        val:       The string value to look up
        default:   Fallback value if lookup fails

    Returns:
        The enum member or default
    """
    if val is None:
        return default
    try:
        return enum_cls(val)
    except (ValueError, TypeError):
        return default


def _parse_date(val: Any) -> Optional[date]:
    """Parse date from string 'YYYY-MM-DD' or date object."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_float(val: Any) -> Optional[float]:
    """Parse float, return None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_int(val: Any) -> Optional[int]:
    """Parse int, return None on failure."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parse_sp(sp_str: Any) -> Optional[float]:
    """
    Parse Betfair SP string to decimal.
    Handles: '5/1', '5.0', '28/1', 'Evens', 'Evs', '9/4', '11/8'
    """
    if sp_str is None:
        return None
    s = str(sp_str).strip().lower()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    # Fractional odds: '5/1' -> 6.0, '9/4' -> 3.25
    m = re.match(r"(\d+)/(\d+)", s)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        if den != 0:
            return num / den + 1.0
    # 'evens' or 'evs' -> 2.0
    if s in ("evens", "ev", "evs"):
        return 2.0
    return None


def _parse_place(place_str: Any) -> Optional[int]:
    """Parse finishing position from pos string. '1'->1, '2'->2, 'PU'->None, 'F'->None."""
    if place_str is None:
        return None
    s = str(place_str).strip()
    try:
        return int(s)
    except ValueError:
        return None


def _going_band(going_raw: Any) -> GoingBand:
    """Map raw going string to GoingBand."""
    if going_raw is None:
        return GoingBand.UNKNOWN
    g = str(going_raw).lower()
    if "standard" in g or "slow" in g:
        return GoingBand.STANDARD
    if "good" in g and "soft" not in g and "firm" not in g:
        return GoingBand.FIRM
    if "firm" in g or "fast" in g or "hard" in g:
        return GoingBand.FIRM
    if "soft" in g or "heavy" in g or "yielding" in g:
        return GoingBand.SOFT
    if "heavy" in g:
        return GoingBand.HEAVY
    return GoingBand.UNKNOWN


def _distance_to_furlongs(dist_str: Any) -> Optional[float]:
    """Convert distance string like '6f', '1m2f', '1m4½f' to furlongs float."""
    if dist_str is None:
        return None
    s = str(dist_str).lower().strip()
    try:
        return float(s.rstrip("fF"))
    except ValueError:
        pass
    # Handle '1m2f' format
    m = re.match(r"(\d+)m(\d*)f?", s)
    if m:
        miles = float(m.group(1)) if m.group(1) else 0.0
        fur = float(m.group(2)) if m.group(2) else 0.0
        return miles * 8 + fur
    return None


# ─── Trainer A/E Computation ──────────────────────────────────────────────────

class TrainerStatsCache:
    """
    In-memory trainer A/E stats computed from raceform data.
    Populated by RaceformFeatureDeriver.build_trainer_stats() on first load.
    """

    def __init__(self):
        self._stats: Dict[str, Dict[str, float]] = {}  # trainer -> {runs, wins, ae}

    def get(self, trainer: str) -> Optional[float]:
        if not trainer or trainer == "NR":
            return None
        return self._stats.get(trainer, {}).get("ae")

    def get_signal(self, trainer: str) -> TrainerSignalType:
        ae = self.get(trainer)
        if ae is None:
            return TrainerSignalType.UNKNOWN
        if ae >= 1.20:
            return TrainerSignalType.IMPROVER
        if ae <= 0.85:
            return TrainerSignalType.DECLINING
        return TrainerSignalType.CONSISTENT


# ─── Main Deriver ─────────────────────────────────────────────────────────────

class RaceformFeatureDeriver:
    """
    Derives the 13 locked fingerprint features from raw raceform rows.

    Feature derivation map:
    ┌─────────────────────────────────────┬────────────────────────────────────┐
    │ Fingerprint Feature                 │ Derivation Source                   │
    ├─────────────────────────────────────┼────────────────────────────────────┤
    │ sqpe                               │ 0.0 (unavailable in raw; placeholder)│
    │ sqpe_band                          │ derived from sqpe                   │
    │ sp_band                            │ derived from sp (fractional→decimal) │
    │ trainer_ae                         │ computed from raceform trainer stats │
    │ trainer_ae_band                    │ derived from trainer_ae             │
    │ trainer_signal_type                │ derived from trainer_ae + form      │
    │ class_movement_subtype             │ compared with horse's previous class │
    │ days_since_run_band                │ computed from date + prior runs     │
    │ run_cycle_position                 │ derived from days_since_run         │
    │ distance_change_band               │ compared with horse's previous dist │
    │ going_band                        │ mapped from going string            │
    │ recent_form_state                 │ derived from last 5 finish positions │
    │ finish_consistency_band            │ variance of last N finish positions  │
    └─────────────────────────────────────┴────────────────────────────────────┘

    Post-race outcome fields (always available in raceform):
      win = (pos == 1)
      placed = (1 <= pos <= 3)
      finish_position = parsed from pos string
      sp = parsed from sp string (fractional→decimal)
    """

    def __init__(self, trainer_cache: Optional[TrainerStatsCache] = None):
        self._trainer_cache = trainer_cache or TrainerStatsCache()
        self._horse_history: Dict[str, List[Dict]] = {}  # horse -> sorted prior runs
        self._derived_count = 0
        self._skipped_count = 0

    # ─── Trainer stats builder ─────────────────────────────────────────────────

    def build_trainer_stats(self, rows: List[Dict[str, Any]]) -> None:
        """
        Pre-scan raceform rows to compute per-trainer A/E ratios.
        Call this once before derive() when processing a batch.

        A/E = (actual_wins / expected_wins)
        Expected wins = total_runs × base_win_rate (0.10 for flat)
        """
        from collections import defaultdict

        trainer_runs: Dict[str, int] = defaultdict(int)
        trainer_wins: Dict[str, int] = defaultdict(int)
        BASE_WIN_RATE = 0.10

        for row in rows:
            trainer = str(row.get("trainer", "")).strip()
            if not trainer or trainer == "NR":
                continue
            pos = _parse_place(row.get("pos"))
            trainer_runs[trainer] += 1
            if pos == 1:
                trainer_wins[trainer] += 1

        stats = {}
        for trainer, runs in trainer_runs.items():
            if runs < 5:  # minimum sample size
                ae = None
            else:
                expected = runs * BASE_WIN_RATE
                ae = trainer_wins[trainer] / expected if expected > 0 else None
            stats[trainer] = {"runs": runs, "wins": trainer_wins[trainer], "ae": ae}

        self._trainer_cache._stats = stats

    # ─── Core derive method ────────────────────────────────────────────────────

    def derive(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Derive the 13 locked fingerprint features from one raw raceform row.

        Returns a dict with keys matching the canonical_mapper.from_raceform()
        expected inputs, PLUS derivation notes for transparency.
        """
        horse = str(row.get("horse", "")).strip()
        trainer = str(row.get("trainer", "")).strip()
        race_dt = _parse_date(row.get("date"))
        course = str(row.get("course", "")).strip()
        dist_raw = row.get("dist", "")
        going_raw = row.get("going", "")
        pos_raw = row.get("pos", "")
        sp_raw = row.get("sp", "")
        class_raw = str(row.get("class_raw", ""))
        rpr_raw = row.get("rpr", "")
        ts_raw = row.get("ts", "")
        num_raw = row.get("num", "")
        ovr_btn_raw = row.get("ovr_btn", "")
        wgt_raw = row.get("wgt", "")

        # ── Outcome fields (always available) ────────────────────────────────
        pos_int = _parse_place(pos_raw)
        sp_decimal = _parse_sp(sp_raw)
        win = pos_int == 1
        placed = pos_int is not None and 1 <= pos_int <= 3

        # ── SP band ─────────────────────────────────────────────────────────
        sp_val = sp_decimal
        if sp_val is None:
            sp_band = SPBand.MID  # default when SP unavailable
        else:
            sp_band = SPBand.from_sp(sp_val)

        # ── Trainer A/E ─────────────────────────────────────────────────────
        trainer_ae = self._trainer_cache.get(trainer)
        trainer_ae_band = self._trainer_ae_band(trainer_ae)
        trainer_signal = self._trainer_cache.get_signal(trainer)

        # ── Days since run ───────────────────────────────────────────────────
        days_since = self._compute_days_since(horse, race_dt)
        days_band = DaysSinceRunBand.from_days(days_since) if days_since is not None else DaysSinceRunBand.NORMAL_8_14

        # ── Run cycle position ───────────────────────────────────────────────
        run_cycle = self._run_cycle(days_since)

        # ── Distance change ─────────────────────────────────────────────────
        prev_dist = self._get_prev_distance(horse)
        curr_dist = _distance_to_furlongs(dist_raw)
        dist_change = self._distance_change(prev_dist, curr_dist)

        # ── Going band ──────────────────────────────────────────────────────
        going_band = _going_band(going_raw)

        # ── Recent form state ───────────────────────────────────────────────
        recent_form = self._recent_form_state(horse, race_dt)

        # ── Finish consistency ───────────────────────────────────────────────
        finish_consistency = self._finish_consistency(horse)

        # ── Class movement ───────────────────────────────────────────────────
        class_movement = self._class_movement(horse, class_raw)

        # ── sqpe proxy ─────────────────────────────────────────────────────
        # sqpe cannot be sourced from raw raceform directly.
        # We construct a best-effort proxy using the same signal chain VÉLØ uses:
        #   sqpe_proxy = trainer_ae × base_win_rate × recent_form_modifier × days_modifier
        #
        # This is NOT the VÉLØ sqpe. It is a racing-context proxy for the analog layer.
        # It enables the analog index to differentiate runners by signal strength.
        sqpe, sqpe_note = self._derive_sqpe(
            trainer_ae=trainer_ae,
            trainer_signal=trainer_signal,
            recent_form=recent_form,
            days_band=days_band,
            sp_val=sp_val,
        )
        sqpe_band = SQPEBand.from_sqpe(sqpe)

        # ── Horse history tracking (for context; not a fingerprint feature) ──
        self._update_horse_history(horse, row, race_dt)

        self._derived_count += 1

        return {
            # Canonical fields
            "sqpe": sqpe,
            "sqpe_band": sqpe_band.value,
            "sp_band": sp_band.value,
            "trainer_ae": trainer_ae,
            "trainer_ae_band": trainer_ae_band,
            "trainer_signal_type": trainer_signal.value,
            "class_movement_subtype": class_movement.value,
            "days_since_run_band": days_band.value,
            "run_cycle_position": run_cycle.value,
            "distance_change_band": dist_change.value,
            "going_band": going_band.value,
            "recent_form_state": recent_form.value,
            "finish_consistency_band": finish_consistency.value,
            # Outcomes
            "win": win,
            "placed": placed,
            "finish_position": pos_int,
            "sp": sp_val,
            # Context
            "horse": horse,
            "trainer": trainer,
            "course": course,
            "race_date": race_dt,
            "race_id": str(row.get("race_id", "")),
            "horse_id": str(row.get("id", "")),
            # Derivation quality notes
            "_derivation": {
                "sqpe_derived": sqpe_note != "no_signal",
                "sqpe_note": sqpe_note,
                "trainer_ae_note": "computed from raceform sample within batch" if trainer_ae else "insufficient data",
                "days_since_note": f"{days_since} days" if days_since is not None else "no prior run found",
                "dist_change_note": f"{prev_dist}→{curr_dist}f" if prev_dist and curr_dist else "no prior distance",
            },
        }

    # ─── To CanonicalRaceState ────────────────────────────────────────────────

    def to_canonical(
        self,
        row: Dict[str, Any],
        features: Dict[str, Any],
        region: Region = Region.UK,
    ) -> CanonicalRaceState:
        """
        Convert raw raceform row + derived features into CanonicalRaceState.
        """
        return CanonicalRaceState(
            race_id=str(row.get("race_id", "")),
            runner_id=str(row.get("id", "")),
            race_date=features["race_date"] or date.today(),
            course=features["course"],
            region=region,
            # Fingerprint features
            sqpe=features["sqpe"],
            sqpe_band=_parse_enum_value(SQPEBand, features["sqpe_band"], SQPEBand.VERY_LOW),
            sp_band=_parse_enum_value(SPBand, features["sp_band"], SPBand.MID),
            trainer_ae=features["trainer_ae"],
            trainer_ae_band=features["trainer_ae_band"],
            trainer_signal_type=_parse_enum_value(TrainerSignalType, features["trainer_signal_type"], TrainerSignalType.UNKNOWN),
            class_movement_subtype=_parse_enum_value(ClassMovementSubtype, features["class_movement_subtype"], ClassMovementSubtype.UNKNOWN),
            days_since_run_band=_parse_enum_value(DaysSinceRunBand, features["days_since_run_band"], DaysSinceRunBand.NORMAL_8_14),
            run_cycle_position=_parse_enum_value(RunCyclePosition, features["run_cycle_position"], RunCyclePosition.MID),
            distance_change_band=_parse_enum_value(DistanceChangeBand, features["distance_change_band"], DistanceChangeBand.SAME),
            going_band=_parse_enum_value(GoingBand, features["going_band"], GoingBand.UNKNOWN),
            recent_form_state=_parse_enum_value(RecentFormState, features["recent_form_state"], RecentFormState.UNTESTED),
            finish_consistency_band=_parse_enum_value(FinishConsistencyBand, features["finish_consistency_band"], FinishConsistencyBand.UNTESTED),
            # Outcomes
            win=features["win"],
            placed=features["placed"],
            finish_position=features["finish_position"],
            sp=features["sp"],
            # Versioning
            feature_version="fingerprint_v1",
            signal_version="phase35_locked",
        )

    # ─── Internal helpers ──────────────────────────────────────────────────────

    def _trainer_ae_band(self, ae: Optional[float]) -> str:
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
    def _derive_sqpe(
        trainer_ae: Optional[float],
        trainer_signal: TrainerSignalType,
        recent_form: RecentFormState,
        days_band: DaysSinceRunBand,
        sp_val: Optional[float] = None,
    ) -> Tuple[float, str]:
        """
        Derive a sqpe proxy for the analog layer from available racing signals.

        Primary formula (when trainer A/E is available):
          sqpe_proxy = trainer_ae × base_win_rate × recent_form_modifier × days_modifier

        Fallback formula (when trainer A/E is unavailable):
          sqpe_proxy = market_probability_from_sp × recent_form_modifier × days_modifier

        base_win_rate = 0.10 (10% flat baseline)

        Args:
            trainer_ae:  trainer A/E ratio from batch stats
            trainer_signal: improver / consistent / declining / unknown
            recent_form: improving / consistent / declining / untested / mixed
            days_band:   layoff category
            sp_val:      Betfair SP as decimal (for fallback computation)

        Returns:
            (sqpe_proxy float, derivation_note string)

        Note:
            This is NOT VÉLØ sqpe. It is a racing-context proxy for analog
            similarity scoring only. It enables the analog index to separate
            signal strength across runners even when no HDTA scores exist.
        """
        BASE_WIN_RATE = 0.10
        MAX_SQPE_PROXY = 0.80  # cap above Phase 3.5 sweet spot ceiling

        if trainer_ae is None or trainer_ae <= 0:
            # Fallback: SP-derived market probability as a quality proxy.
            # SP encodes the market's collective assessment of the runner's win chance.
            # Works for ~99% of raceform rows (vs ~25% with trainer A/E data).
            sqpe = RaceformFeatureDeriver._sp_to_sqpe_proxy(
                trainer_signal, recent_form, days_band, sp_val
            )
            note = f"sp_fallback={sqpe:.3f} [{trainer_signal.value}/{recent_form.value}/{days_band.value}]"
            return round(sqpe, 4), note

        # ── recent form modifier ────────────────────────────────────────────
        if recent_form == RecentFormState.IMPROVING:
            form_mod = 1.20
        elif recent_form == RecentFormState.CONSISTENT:
            form_mod = 1.00
        elif recent_form == RecentFormState.MIXED:
            form_mod = 0.90
        elif recent_form == RecentFormState.DECLINING:
            form_mod = 0.80
        else:
            form_mod = 0.95  # untested — slight discount

        # ── days since run modifier ────────────────────────────────────────
        if days_band == DaysSinceRunBand.NORMAL_8_14:
            days_mod = 1.10  # sweet spot — peak fitness window
        elif days_band == DaysSinceRunBand.QUICK_5_7:
            days_mod = 1.05  # sharp
        elif days_band == DaysSinceRunBand.VERY_QUICK:
            days_mod = 0.85  # possibly rusty
        elif days_band == DaysSinceRunBand.LAYOFF_14_30:
            days_mod = 0.95  # slight rust
        else:
            days_mod = 0.70  # layoff_30plus — significant rust risk

        sqpe = trainer_ae * BASE_WIN_RATE * form_mod * days_mod
        sqpe = min(sqpe, MAX_SQPE_PROXY)

        # Build derivation note
        signal_name = trainer_signal.value
        form_name = recent_form.value
        band_name = days_band.value
        return round(sqpe, 4), f"ae={trainer_ae:.2f}×{BASE_WIN_RATE}×{form_mod}×{days_mod}={sqpe:.3f} [{signal_name}/{form_name}/{band_name}]"

    @staticmethod
    def _sp_to_sqpe_proxy(
        trainer_signal: TrainerSignalType,
        recent_form: RecentFormState,
        days_band: DaysSinceRunBand,
        sp_val: Optional[float] = None,
    ) -> float:
        """
        SP-based market probability proxy for sqpe when trainer A/E is unavailable.

        SP → market implied probability → multiply by modifiers
        Since the market is a well-calibrated aggregator of information,
        this captures a similar signal to trainer A/E × base_rate
        but works for ~99% of runners vs ~25% with trainer A/E data.

        Args:
            trainer_signal: used in the derivation note (pass through)
            recent_form: form modifier
            days_band: days modifier
            sp_val: Betfair SP as decimal odds (e.g. 5.0 = 5/1)

        Returns:
            sqpe_proxy float [0.0, 0.80]
        """
        MAX_SQPE_PROXY = 0.80
        BASE_WIN_RATE = 0.10

        # Form and days modifiers (same as trainer A/E path)
        if recent_form == RecentFormState.IMPROVING:
            form_mod = 1.20
        elif recent_form == RecentFormState.CONSISTENT:
            form_mod = 1.00
        elif recent_form == RecentFormState.MIXED:
            form_mod = 0.90
        elif recent_form == RecentFormState.DECLINING:
            form_mod = 0.80
        else:
            form_mod = 0.95

        if days_band == DaysSinceRunBand.NORMAL_8_14:
            days_mod = 1.10
        elif days_band == DaysSinceRunBand.QUICK_5_7:
            days_mod = 1.05
        elif days_band == DaysSinceRunBand.VERY_QUICK:
            days_mod = 0.85
        elif days_band == DaysSinceRunBand.LAYOFF_14_30:
            days_mod = 0.95
        else:
            days_mod = 0.70

        if sp_val is None or sp_val <= 1.0:
            # No usable SP — use base rate only
            sqpe = BASE_WIN_RATE * form_mod * days_mod
        else:
            # SP is decimal odds → implied probability = 1/odds
            market_prob = 1.0 / sp_val
            # Scale to a competitive range (max ~0.20 for short-priced runners)
            sqpe = market_prob * form_mod * days_mod
            sqpe = min(sqpe, MAX_SQPE_PROXY)

        return sqpe

    def _compute_days_since(self, horse: str, race_dt: Optional[date]) -> Optional[int]:
        """Look up horse's previous run date from in-memory history."""
        if not horse or race_dt is None:
            return None
        history = self._horse_history.get(horse, [])
        for prior_run in reversed(history):
            prior_dt = prior_run.get("race_date")
            if prior_dt and prior_dt < race_dt:
                return (race_dt - prior_dt).days
        return None

    def _get_prev_distance(self, horse: str) -> Optional[float]:
        """Get horse's most recent previous distance."""
        history = self._horse_history.get(horse, [])
        if history:
            return _distance_to_furlongs(history[0].get("dist"))
        return None

    def _run_cycle(self, days_since: Optional[int]) -> RunCyclePosition:
        if days_since is None:
            return RunCyclePosition.MID
        if days_since < 5:
            return RunCyclePosition.MID
        if days_since <= 14:
            return RunCyclePosition.PEAK
        if days_since <= 30:
            return RunCyclePosition.LATE
        if days_since <= 60:
            return RunCyclePosition.EARLY
        return RunCyclePosition.DROUGHT

    def _distance_change(
        self, prev: Optional[float], curr: Optional[float]
    ) -> DistanceChangeBand:
        if prev is None or curr is None:
            return DistanceChangeBand.SAME
        diff = curr - prev
        if abs(diff) < 1.0:
            return DistanceChangeBand.SAME
        if diff >= 4.0:
            return DistanceChangeBand.SIGNIFICANT_UP
        if diff >= 2.0:
            return DistanceChangeBand.UP
        if diff <= -4.0:
            return DistanceChangeBand.SIGNIFICANT_DOWN
        if diff <= -2.0:
            return DistanceChangeBand.DOWN
        return DistanceChangeBand.SAME

    def _recent_form_state(self, horse: str, race_dt: Optional[date]) -> RecentFormState:
        """Infer recent form from last 3 finish positions."""
        history = self._horse_history.get(horse, [])
        recent = [h for h in history if h.get("race_date") != race_dt][:3]
        positions = [h.get("finish_position") for h in recent if h.get("finish_position") is not None]
        if len(positions) < 2:
            return RecentFormState.UNTESTED
        wins = sum(1 for p in positions if p == 1)
        places = sum(1 for p in positions if 1 <= p <= 3)
        win_rate = wins / len(positions)
        if win_rate >= 0.40:
            return RecentFormState.IMPROVING
        if places / len(positions) >= 0.60:
            return RecentFormState.CONSISTENT
        if win_rate < 0.10 and len(positions) >= 3:
            return RecentFormState.DECLINING
        return RecentFormState.MIXED

    def _finish_consistency(self, horse: str) -> FinishConsistencyBand:
        """Compute finish position variance over last 5 runs."""
        history = self._horse_history.get(horse, [])
        positions = [h.get("finish_position") for h in history[:5] if h.get("finish_position") is not None]
        if len(positions) < 3:
            return FinishConsistencyBand.UNTESTED
        mean = sum(positions) / len(positions)
        variance = sum((p - mean) ** 2 for p in positions) / len(positions)
        std_dev = math.sqrt(variance)
        if std_dev <= 1.5:
            return FinishConsistencyBand.CONSISTENT
        if std_dev <= 3.0:
            return FinishConsistencyBand.AVERAGE
        return FinishConsistencyBand.VARIABLE

    def _class_movement(self, horse: str, current_class: str) -> ClassMovementSubtype:
        """
        Detect class movement from horse's last run class vs current class.
        Crude heuristic: compare class string keywords.
        """
        history = self._horse_history.get(horse, [])
        if not history:
            return ClassMovementSubtype.UNKNOWN
        prev_class = str(history[0].get("class_raw", ""))
        # Simple class level detection by number in string
        curr_level = self._class_level(current_class)
        prev_level = self._class_level(prev_class)
        if curr_level is None or prev_level is None:
            return ClassMovementSubtype.UNKNOWN
        if curr_level > prev_level:
            return ClassMovementSubtype.RISE
        if curr_level < prev_level:
            # Check for "engineered drop" — trainer deliberately dropping class
            if prev_level - curr_level >= 2:
                return ClassMovementSubtype.ENGINEERED_DROP
            return ClassMovementSubtype.DROP
        return ClassMovementSubtype.SAME

    @staticmethod
    def _class_level(class_str: str) -> Optional[int]:
        """Extract numeric class level from 'Class 4', 'Class 2', etc."""
        if not class_str:
            return None
        m = re.search(r"Class\s*(\d+)", class_str, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _update_horse_history(
        self,
        horse: str,
        row: Dict[str, Any],
        race_dt: Optional[date],
    ) -> None:
        """Append current run to horse's in-memory history, sorted newest-first."""
        if horse not in self._horse_history:
            self._horse_history[horse] = []
        # Prepend (newest first)
        run_record = {
            "race_date": race_dt,
            "dist": row.get("dist"),
            "class_raw": row.get("class_raw"),
            "going": row.get("going"),
            "finish_position": _parse_place(row.get("pos")),
            "sp": _parse_sp(row.get("sp")),
        }
        self._horse_history[horse].insert(0, run_record)
        # Keep last 10 runs per horse
        self._horse_history[horse] = self._horse_history[horse][:10]

    # ─── Stats ────────────────────────────────────────────────────────────────

    @property
    def stats(self) -> Dict[str, int]:
        return {"derived": self._derived_count, "skipped": self._skipped_count}


# ─── Convenience batch function ───────────────────────────────────────────────

def derive_batch(
    rows: List[Dict[str, Any]],
    trainer_ae_from_batch: bool = True,
) -> Tuple[List[Dict[str, Any]], RaceformFeatureDeriver]:
    """
    Derive features for a batch of raw raceform rows.

    Args:
        rows: List of raw raceform rows
        trainer_ae_from_batch: If True, compute trainer A/E from the batch itself.
                              If False, use pre-computed trainer cache.

    Returns:
        (list of derived feature dicts, deriver instance)
    """
    deriver = RaceformFeatureDeriver()
    if trainer_ae_from_batch:
        deriver.build_trainer_stats(rows)

    results = []
    for row in rows:
        try:
            features = deriver.derive(row)
            results.append(features)
        except Exception:
            deriver._skipped_count += 1
            continue

    return results, deriver
