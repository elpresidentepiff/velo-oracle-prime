"""
horse_passport.py — Horse Passport V2
Shadow/archive only. velo_scoring_allowed = False.
Builds a rolling career profile from RP form history runs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
from typing import Optional, List

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _frac_sp(sp_raw: str) -> Optional[float]:
    if not sp_raw:
        return None
    try:
        s = str(sp_raw).strip().lower().replace("f", "").replace("j", "")
        if s in ("evs", "evens", "1/1"):
            return 2.0
        if "/" in s:
            n, d = s.split("/")
            return round(int(n) / int(d) + 1, 2)
        return float(s)
    except Exception:
        return None


def _parse_date(d: str) -> Optional[date]:
    try:
        if isinstance(d, date):
            return d
        return date.fromisoformat(d.split("T")[0])
    except Exception:
        return None

def _dist_to_f(d: str) -> Optional[float]:
    if not d:
        return None
    try:
        d = str(d).lower()
        m_match = re.search(r"(\d+)m", d)
        f_match = re.search(r"(\d+)f", d)
        
        total_f = 0.0
        if m_match:
            total_f += float(m_match.group(1)) * 8
        if f_match:
            total_f += float(f_match.group(1))
            
        if not m_match and not f_match:
            val_match = re.search(r"(\d+\.?\d*)", d)
            return float(val_match.group(1)) if val_match else None
            
        return total_f
    except Exception:
        return None

def _margin_to_float(m: str | float | None) -> Optional[float]:
    if m is None: return None
    if isinstance(m, (int, float)): return float(m)
    
    s = str(m).lower().strip()
    if not s: return None
    
    # Handle common shorthands
    if s in ("sh", "sht-hd", "short-head"): return 0.1
    if s in ("hd", "head"): return 0.2
    if s in ("nk", "neck"): return 0.3
    
    try:
        # Handle fractions and "L" suffix
        # e.g. "¾L", "1½L", "10L"
        val = 0.0
        
        # Extract numeric part
        numeric_part = re.search(r"(\d+)", s)
        if numeric_part:
            val += float(numeric_part.group(1))
            
        # Add fractions
        if "¼" in s: val += 0.25
        if "½" in s: val += 0.5
        if "¾" in s: val += 0.75
        
        if val == 0 and not numeric_part:
            # Try parsing direct float if no L or fractions
            return float(s)
            
        return val
    except Exception:
        return None


@dataclass
class HorsePassport:
    horse_name: str
    horse_rp_uid: Optional[int]

    career_runs: int = 0
    wins: int = 0
    places: int = 0
    win_rate: float = 0.0
    place_rate: float = 0.0

    # Layoff
    last_run_date: Optional[str] = None
    days_since_last_run: Optional[int] = None
    avg_days_between_runs: Optional[float] = None
    layoff_flag: Optional[str] = None

    # Course
    course_repeat: bool = False
    course_switch: bool = False
    unique_courses: int = 0
    course_affinity: Optional[str] = None

    # Distance
    distance_repeat: bool = False
    distance_switch: bool = False
    distance_trend: Optional[str] = None

    # Going
    going_preference: Optional[str] = None
    aw_specialist: bool = False

    # Jockey
    jockey_continuity: bool = False
    jockey_change: bool = False
    career_jockeys: int = 0

    # SP
    sp_trajectory: Optional[str] = None
    avg_sp_last5: Optional[float] = None
    well_fancied_rate: float = 0.0
    well_fancied_failure_rate: float = 0.0

    # Quality
    avg_beaten_margin: Optional[float] = None
    margin_trend: Optional[str] = None

    # Class
    class_movement: Optional[str] = None

    # Field size
    avg_field_size: Optional[float] = None

    # OR trajectory
    or_trajectory: Optional[str] = None
    current_or: Optional[int] = None
    or_change_last3: Optional[int] = None

    # Intent signals
    cash_run_candidate: bool = False
    setup_run_candidate: bool = False

    # V2 Window Stats
    win_rate_last3: float = 0.0
    win_rate_last6: float = 0.0
    win_rate_last12: float = 0.0
    place_rate_last3: float = 0.0
    place_rate_last6: float = 0.0
    avg_beaten_margin_last3: Optional[float] = None
    avg_beaten_margin_last6: Optional[float] = None
    avg_sp_last3: Optional[float] = None
    runs_in_last_90d: int = 0
    runs_in_last_180d: int = 0

    # V2 Form Shape
    beaten_margin_slope: Optional[float] = None
    position_trend: Optional[str] = None

    # V2 Context Counts
    career_wins_flat: int = 0
    career_wins_aw: int = 0
    career_win_rate_6f_under: float = 0.0
    career_win_rate_7f_8f: float = 0.0
    career_win_rate_9f_plus: float = 0.0

    # TS Enrichment
    pp_best_ts_last6: Optional[float] = None
    pp_ts_trajectory: Optional[float] = None
    ts_last6_array: List[float] = field(default_factory=list)

    trust_policy: str = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
    velo_scoring_allowed: bool = False
    built_at: str = ""


class HorsePassportBuilder:
    def build(self, runs: list[dict], as_of_date: date | None = None) -> HorsePassport:
        if not runs:
            raise ValueError("No runs provided")

        horse_name = runs[0].get("horse_name", "")
        horse_rp_uid = runs[0].get("horse_rp_uid")

        # Sort runs by date descending
        dated = []
        for r in runs:
            d = _parse_date(r.get("race_date", ""))
            if d:
                dated.append((d, r))
        dated.sort(key=lambda x: x[0], reverse=True)

        if not dated:
            return HorsePassport(horse_name=horse_name, horse_rp_uid=horse_rp_uid,
                                 built_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

        sorted_runs = [r for _, r in dated]
        sorted_dates = [d for d, _ in dated]

        career_runs = len(sorted_runs)
        wins = sum(1 for r in sorted_runs if r.get("position") == 1)
        places = sum(1 for r in sorted_runs if r.get("position") is not None and r["position"] <= 3)
        win_rate = round(wins / career_runs, 4) if career_runs else 0.0
        place_rate = round(places / career_runs, 4) if career_runs else 0.0

        # Last Run Date
        last_run_date_obj = sorted_dates[0]
        last_run_date_str = last_run_date_obj.isoformat()

        # Layoff logic
        days_since = None
        layoff_flag = None
        if as_of_date:
            days_since = (as_of_date - last_run_date_obj).days
            if days_since >= 180:
                layoff_flag = "FRESH_180"
            elif days_since >= 90:
                layoff_flag = "FRESH_90"
            elif days_since >= 60:
                layoff_flag = "FRESH_60"
            elif days_since >= 30:
                layoff_flag = "FRESH_30"
            else:
                layoff_flag = "ACTIVE"

        if len(sorted_dates) >= 2:
            gaps = [(sorted_dates[i] - sorted_dates[i + 1]).days for i in range(len(sorted_dates) - 1)]
            avg_gap = round(mean(gaps), 1)
        else:
            avg_gap = None

        # Course
        courses = [r.get("course_name") or r.get("course_key") for r in sorted_runs]
        courses = [c for c in courses if c]
        unique_courses = len(set(courses))
        course_repeat = len(courses) >= 2 and courses[0] == courses[1]
        course_switch = len(courses) >= 2 and courses[0] != courses[1]

        from collections import Counter
        course_wins: Counter = Counter()
        course_runs_count: Counter = Counter()
        for r in sorted_runs:
            c = r.get("course_name") or r.get("course_key")
            if c:
                course_runs_count[c] += 1
                if r.get("position") == 1:
                    course_wins[c] += 1
        course_affinity = None
        best_wr = 0.0
        for c, cnt in course_runs_count.items():
            if cnt >= 3:
                wr = course_wins[c] / cnt
                if wr > best_wr:
                    best_wr = wr
                    course_affinity = c

        # Distance
        dists = [r.get("distance") for r in sorted_runs if r.get("distance")]
        distance_repeat = len(dists) >= 2 and dists[0] == dists[1]
        distance_switch = len(dists) >= 2 and dists[0] != dists[1]

        dist_nums = [_dist_to_f(d) for d in dists[:5] if d]
        dist_nums = [d for d in dist_nums if d is not None]
        if len(dist_nums) >= 3:
            if dist_nums[0] > dist_nums[-1] + 1:
                distance_trend = "STEPPING_UP"
            elif dist_nums[0] < dist_nums[-1] - 1:
                distance_trend = "STEPPING_DOWN"
            else:
                distance_trend = "CONSISTENT"
        else:
            distance_trend = None

        # Going preference
        going_wins: Counter = Counter()
        going_runs_c: Counter = Counter()
        aw_runs = 0
        career_wins_flat = 0
        career_wins_aw = 0
        
        runs_6f_under = 0
        wins_6f_under = 0
        runs_7f_8f = 0
        wins_7f_8f = 0
        runs_9f_plus = 0
        wins_9f_plus = 0

        for r in sorted_runs:
            g = r.get("going")
            pos = r.get("position")
            c_name = r.get("course_name") or ""
            is_win = (pos == 1)
            
            if g:
                going_runs_c[g] += 1
                if is_win:
                    going_wins[g] += 1
            
            # Context Counts
            if "AW" in c_name:
                aw_runs += 1
                if is_win:
                    career_wins_aw += 1
            else:
                if is_win:
                    career_wins_flat += 1
            
            d_str = r.get("distance")
            df = _dist_to_f(d_str) if d_str else None
            if df is not None:
                if df < 6.5:
                    runs_6f_under += 1
                    if is_win: wins_6f_under += 1
                elif df < 8.5:
                    runs_7f_8f += 1
                    if is_win: wins_7f_8f += 1
                else:
                    runs_9f_plus += 1
                    if is_win: wins_9f_plus += 1

        career_win_rate_6f_under = round(wins_6f_under / runs_6f_under, 4) if runs_6f_under > 0 else 0.0
        career_win_rate_7f_8f = round(wins_7f_8f / runs_7f_8f, 4) if runs_7f_8f > 0 else 0.0
        career_win_rate_9f_plus = round(wins_9f_plus / runs_9f_plus, 4) if runs_9f_plus > 0 else 0.0

        going_preference = None
        best_gwr = 0.0
        for g, cnt in going_runs_c.items():
            if cnt >= 3:
                gwr = going_wins[g] / cnt
                if gwr > best_gwr:
                    best_gwr = gwr
                    going_preference = g
        aw_specialist = career_runs > 0 and (aw_runs / career_runs) >= 0.70

        # Jockey
        jockeys = [r.get("jockey_name") for r in sorted_runs if r.get("jockey_name")]
        career_jockeys = len(set(jockeys))
        if len(jockeys) >= 4:
            recent3 = set(jockeys[:3])
            jockey_continuity = len(recent3) == 1
            jockey_change = jockeys[0] != jockeys[1] if len(jockeys) >= 2 else False
        elif len(jockeys) >= 2:
            jockey_continuity = len(set(jockeys[:2])) == 1
            jockey_change = jockeys[0] != jockeys[1]
        else:
            jockey_continuity = False
            jockey_change = False

        # SP
        sps = [_frac_sp(r.get("sp_raw", "")) for r in sorted_runs]
        sps_valid = [s for s in sps if s is not None]
        avg_sp_last5 = round(mean(sps_valid[:5]), 2) if sps_valid[:5] else None
        avg_sp_last3 = round(mean(sps_valid[:3]), 2) if sps_valid[:3] else None

        well_fancied_runs = [r for r, s in zip(sorted_runs, sps) if s is not None and s <= 4.0]
        well_fancied_rate = round(len(well_fancied_runs) / career_runs, 4) if career_runs else 0.0
        wf_failures = [r for r in well_fancied_runs if r.get("position") != 1]
        well_fancied_failure_rate = round(len(wf_failures) / len(well_fancied_runs), 4) if well_fancied_runs else 0.0

        sp_trajectory = None
        if len(sps_valid) >= 4:
            recent2_avg = mean(sps_valid[:2])
            older_avg = mean(sps_valid[2:5]) if len(sps_valid) >= 5 else mean(sps_valid[2:])
            if older_avg > 0:
                ratio = recent2_avg / older_avg
                if ratio < 0.80:
                    sp_trajectory = "SHORTENING"
                elif ratio > 1.20:
                    sp_trajectory = "DRIFTING"
                else:
                    sp_trajectory = "STABLE"

        # Beaten margin
        margins = [_margin_to_float(r.get("beaten_margin")) for r in sorted_runs]
        margins_float = [m for m in margins if m is not None]
        avg_beaten_margin = round(mean(margins_float), 2) if margins_float else None
        
        # Windowed margins
        avg_beaten_margin_last3 = round(mean(margins_float[:3]), 2) if len(margins_float) >= 1 else None
        avg_beaten_margin_last6 = round(mean(margins_float[:6]), 2) if len(margins_float) >= 1 else None
        
        # Slope
        beaten_margin_slope = None
        if len(margins_float) >= 3:
            m_subset = margins_float[:6]
            beaten_margin_slope = round((m_subset[0] - m_subset[-1]) / len(m_subset), 3)

        margin_trend = None
        if len(margins_float) >= 4:
            recent2_m = mean(margins_float[:2])
            older_m = mean(margins_float[2:5]) if len(margins_float) >= 5 else mean(margins_float[2:])
            if recent2_m < older_m - 1:
                margin_trend = "IMPROVING"
            elif recent2_m > older_m + 1:
                margin_trend = "DECLINING"
            else:
                margin_trend = "STABLE"

        # Position Trend
        positions = [r.get("position") for r in sorted_runs if r.get("position") is not None]
        position_trend = None
        if len(positions) >= 4:
            p_recent = mean(positions[:3])
            p_older = mean(positions[3:6]) if len(positions) >= 6 else mean(positions[3:])
            if p_recent < p_older - 0.5:
                position_trend = "IMPROVING"
            elif p_recent > p_older + 0.5:
                position_trend = "DECLINING"
            else:
                position_trend = "STABLE"

        # Windowed Win/Place Rates
        def get_rate(runs_list, limit, key, value):
            subset = runs_list[:limit]
            if not subset: return 0.0
            count = sum(1 for r in subset if r.get(key) == value or (value == 3 and r.get(key) is not None and r.get(key) <= 3))
            return round(count / len(subset), 4)

        win_rate_last3 = get_rate(sorted_runs, 3, "position", 1)
        win_rate_last6 = get_rate(sorted_runs, 6, "position", 1)
        win_rate_last12 = get_rate(sorted_runs, 12, "position", 1)
        place_rate_last3 = get_rate(sorted_runs, 3, "position", 3)
        place_rate_last6 = get_rate(sorted_runs, 6, "position", 3)

        # Runs in last X days
        runs_in_last_90d = 0
        runs_in_last_180d = 0
        if as_of_date:
            cutoff_90 = as_of_date - timedelta(days=90)
            cutoff_180 = as_of_date - timedelta(days=180)
            runs_in_last_90d = sum(1 for d in sorted_dates if d >= cutoff_90)
            runs_in_last_180d = sum(1 for d in sorted_dates if d >= cutoff_180)

        # Class movement (via OR if available, else positional)
        ors = [r.get("or_rating") for r in sorted_runs[:3] if r.get("or_rating") is not None]
        try:
            ors = [int(o) for o in ors if o is not None]
        except Exception:
            ors = []
        current_or = ors[0] if ors else None
        or_change_last3 = (ors[0] - ors[-1]) if len(ors) >= 2 else None
        or_trajectory = None
        if len(ors) >= 3:
            if ors[0] > ors[2] + 2:
                or_trajectory = "RISING"
            elif ors[0] < ors[2] - 2:
                or_trajectory = "FALLING"
            else:
                or_trajectory = "STABLE"

        # TS Enrichment
        ts_values = []
        for r in sorted_runs[:6]:
            val = r.get("ts_rating") or r.get("ts")
            try:
                if val is not None:
                    ts_values.append(float(val))
                else:
                    ts_values.append(None)
            except (ValueError, TypeError):
                ts_values.append(None)
        
        valid_ts = [v for v in ts_values if v is not None]
        pp_best_ts_last6 = max(valid_ts) if valid_ts else None
        
        # Trajectory (Slope)
        pp_ts_trajectory = None
        if len(valid_ts) >= 3:
            try:
                import numpy as np
                # We need chronological order for slope
                # sorted_runs is date descending, so valid_ts is too
                # reverse it for slope calculation
                y = np.array(valid_ts[::-1])
                x = np.arange(len(y))
                slope, _ = np.polyfit(x, y, 1)
                pp_ts_trajectory = round(float(slope), 3)
            except Exception:
                pass

        class_movement = None
        if or_change_last3 is not None:
            if or_change_last3 > 3:
                class_movement = "UP"
            elif or_change_last3 < -3:
                class_movement = "DOWN"
            else:
                class_movement = "CONSISTENT"

        # Field size
        field_sizes = [r.get("field_size") for r in sorted_runs if r.get("field_size") is not None]
        try:
            field_sizes = [int(f) for f in field_sizes]
        except Exception:
            field_sizes = []
        avg_field_size = round(mean(field_sizes), 1) if field_sizes else None

        # Cash run candidate
        cash_run_candidate = False
        if sorted_runs and sps:
            last_sp = sps[0]
            last_pos = sorted_runs[0].get("position")
            last_fs = sorted_runs[0].get("field_size")
            if (last_sp is not None and last_pos is not None and last_fs is not None
                    and last_sp <= 3.0 and last_pos > int(last_fs) * 0.5):
                cash_run_candidate = True

        # Setup run candidate
        setup_run_candidate = False
        if sorted_runs:
            last_margin_str = sorted_runs[0].get("beaten_margin")
            last_margin = _margin_to_float(last_margin_str)
            if last_margin is not None and last_margin >= 10:
                setup_run_candidate = True
            if or_change_last3 is not None and or_change_last3 < -5:
                setup_run_candidate = True

        return HorsePassport(
            horse_name=horse_name,
            horse_rp_uid=horse_rp_uid,
            career_runs=career_runs,
            wins=wins,
            places=places,
            win_rate=win_rate,
            place_rate=place_rate,
            last_run_date=last_run_date_str,
            days_since_last_run=days_since,
            avg_days_between_runs=avg_gap,
            layoff_flag=layoff_flag,
            course_repeat=course_repeat,
            course_switch=course_switch,
            unique_courses=unique_courses,
            course_affinity=course_affinity,
            distance_repeat=distance_repeat,
            distance_switch=distance_switch,
            distance_trend=distance_trend,
            going_preference=going_preference,
            aw_specialist=aw_specialist,
            jockey_continuity=jockey_continuity,
            jockey_change=jockey_change,
            career_jockeys=career_jockeys,
            sp_trajectory=sp_trajectory,
            avg_sp_last5=avg_sp_last5,
            well_fancied_rate=well_fancied_rate,
            well_fancied_failure_rate=well_fancied_failure_rate,
            avg_beaten_margin=avg_beaten_margin,
            margin_trend=margin_trend,
            class_movement=class_movement,
            avg_field_size=avg_field_size,
            or_trajectory=or_trajectory,
            current_or=current_or,
            or_change_last3=or_change_last3,
            cash_run_candidate=cash_run_candidate,
            setup_run_candidate=setup_run_candidate,
            win_rate_last3=win_rate_last3,
            win_rate_last6=win_rate_last6,
            win_rate_last12=win_rate_last12,
            place_rate_last3=place_rate_last3,
            place_rate_last6=place_rate_last6,
            avg_beaten_margin_last3=avg_beaten_margin_last3,
            avg_beaten_margin_last6=avg_beaten_margin_last6,
            avg_sp_last3=avg_sp_last3,
            runs_in_last_90d=runs_in_last_90d,
            runs_in_last_180d=runs_in_last_180d,
            beaten_margin_slope=beaten_margin_slope,
            position_trend=position_trend,
            career_wins_flat=career_wins_flat,
            career_wins_aw=career_wins_aw,
            career_win_rate_6f_under=career_win_rate_6f_under,
            career_win_rate_7f_8f=career_win_rate_7f_8f,
            career_win_rate_9f_plus=career_win_rate_9f_plus,
            pp_best_ts_last6=pp_best_ts_last6,
            pp_ts_trajectory=pp_ts_trajectory,
            ts_last6_array=[v for v in ts_values if v is not None],
            built_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
