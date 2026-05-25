"""
horse_passport.py — Horse Passport V1
Shadow/archive only. velo_scoring_allowed = False.
Builds a rolling career profile from RP form history runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Optional

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False
AS_OF_DATE = date(2026, 5, 25)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _frac_sp(sp_raw: str) -> Optional[float]:
    if not sp_raw:
        return None
    try:
        s = sp_raw.strip().lower().replace("f", "").replace("j", "")
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
        return date.fromisoformat(d)
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

    trust_policy: str = TRUST_POLICY
    velo_scoring_allowed: bool = VELO_SCORING_ALLOWED
    built_at: str = ""


class HorsePassportBuilder:
    def build(self, runs: list[dict]) -> HorsePassport:
        if not runs:
            raise ValueError("No runs provided")

        horse_name = runs[0].get("horse_name", "")
        horse_rp_uid = runs[0].get("horse_rp_uid")

        # Sort runs by date descending (most recent first — form history is already this way)
        dated = []
        for r in runs:
            d = _parse_date(r.get("race_date", ""))
            if d:
                dated.append((d, r))
        dated.sort(key=lambda x: x[0], reverse=True)

        if not dated:
            return HorsePassport(horse_name=horse_name, horse_rp_uid=horse_rp_uid,
                                 built_at=datetime.now(timezone.utc).isoformat())

        sorted_runs = [r for _, r in dated]
        sorted_dates = [d for d, _ in dated]

        career_runs = len(sorted_runs)
        wins = sum(1 for r in sorted_runs if r.get("position") == 1)
        places = sum(1 for r in sorted_runs if r.get("position") is not None and r["position"] <= 3)
        win_rate = round(wins / career_runs, 4) if career_runs else 0.0
        place_rate = round(places / career_runs, 4) if career_runs else 0.0

        # Layoff
        last_date = sorted_dates[0]
        days_since = (AS_OF_DATE - last_date).days
        if len(sorted_dates) >= 2:
            gaps = [(sorted_dates[i] - sorted_dates[i + 1]).days for i in range(len(sorted_dates) - 1)]
            avg_gap = round(mean(gaps), 1)
        else:
            avg_gap = None

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

        def _dist_to_f(d: str) -> Optional[float]:
            if not d:
                return None
            try:
                import re
                m = re.search(r"(\d+\.?\d*)", d.replace("f", "").replace("m", ""))
                return float(m.group(1)) if m else None
            except Exception:
                return None

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
        for r in sorted_runs:
            g = r.get("going")
            if g:
                going_runs_c[g] += 1
                if r.get("position") == 1:
                    going_wins[g] += 1
            if r.get("course_name") and "(AW)" in r.get("course_name", ""):
                aw_runs += 1

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
        sps = [s for s in sps if s is not None]
        avg_sp_last5 = round(mean(sps[:5]), 2) if sps[:5] else None

        well_fancied_runs = [r for r, s in zip(sorted_runs, sps) if s is not None and s <= 4.0]
        well_fancied_rate = round(len(well_fancied_runs) / career_runs, 4) if career_runs else 0.0
        wf_failures = [r for r in well_fancied_runs if r.get("position") != 1]
        well_fancied_failure_rate = round(len(wf_failures) / len(well_fancied_runs), 4) if well_fancied_runs else 0.0

        sp_trajectory = None
        if len(sps) >= 4:
            recent2_avg = mean(sps[:2])
            older_avg = mean(sps[2:5]) if len(sps) >= 5 else mean(sps[2:])
            if older_avg > 0:
                ratio = recent2_avg / older_avg
                if ratio < 0.80:
                    sp_trajectory = "SHORTENING"
                elif ratio > 1.20:
                    sp_trajectory = "DRIFTING"
                else:
                    sp_trajectory = "STABLE"

        # Beaten margin trend
        margins = [r.get("beaten_margin") for r in sorted_runs if r.get("beaten_margin") is not None]
        try:
            margins_float = [float(m) if not isinstance(m, float) else m for m in margins]
        except Exception:
            margins_float = []
        avg_beaten_margin = round(mean(margins_float), 2) if margins_float else None
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

        # Cash run candidate: last run at SP <= 3.0, finished outside top half
        cash_run_candidate = False
        if sorted_runs and sps:
            last_sp = sps[0]
            last_pos = sorted_runs[0].get("position")
            last_fs = sorted_runs[0].get("field_size")
            if (last_sp is not None and last_pos is not None and last_fs is not None
                    and last_sp <= 3.0 and last_pos > int(last_fs) * 0.5):
                cash_run_candidate = True

        # Setup run candidate: last run beaten margin >= 10 OR OR dropped significantly after last run
        setup_run_candidate = False
        if sorted_runs:
            last_margin = sorted_runs[0].get("beaten_margin")
            try:
                if last_margin is not None and float(last_margin) >= 10:
                    setup_run_candidate = True
            except Exception:
                pass
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
            built_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
