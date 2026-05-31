"""
passport_lookup.py — Live Join Module for Horse Passports
Provides fast in-memory lookup of passport features for a list of runners.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[1]
_PASSPORT_JSONL = _ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"
_COVERAGE_REPORT = _ROOT / "data" / "new_build" / "reports" / "passport_coverage_latest.json"

_by_uid: Dict[int, Dict] = {}
_by_name: Dict[str, Dict] = {}
_loaded = False

class PassportCoverageLogger:
    """Tracks hits/misses across a batch scoring session."""
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.miss_names: List[str] = []
        self.start_time = datetime.now(timezone.utc)

    def log_hit(self, horse_name: str, horse_rp_uid: Optional[int]):
        self.hits += 1

    def log_miss(self, horse_name: str, horse_rp_uid: Optional[int]):
        self.misses += 1
        if horse_name and horse_name not in self.miss_names:
            if len(self.miss_names) < 50:
                self.miss_names.append(horse_name)

    def summary(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        coverage = (self.hits / total * 100.0) if total > 0 else 0.0
        return {
            "scored_at": self.start_time.isoformat().replace("+00:00", "Z"),
            "total_runners": total,
            "passport_hits": self.hits,
            "passport_misses": self.misses,
            "coverage_pct": round(coverage, 1),
            "miss_names": self.miss_names,
        }

    def write_report(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.summary(), f, indent=2)

def load_index():
    """Loads the passport JSONL into memory indexes."""
    global _by_uid, _by_name, _loaded
    if _loaded:
        return

    path = _PASSPORT_JSONL
    if not path.exists():
        print(f"WARNING: Passport index missing at {path}")
        _loaded = True
        return

    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                p = json.loads(line)
                uid = p.get("horse_rp_uid")
                name = p.get("horse_name")
                
                if uid:
                    _by_uid[int(uid)] = p
                if name:
                    _by_name[name.strip().lower()] = p
                count += 1
            except Exception:
                continue
    
    print(f"Passport index loaded: {count} horses")
    _loaded = True

def _null_features() -> Dict[str, Any]:
    """Returns a dict with all pp_* keys set to None."""
    return {
        # Champion Model Keys (11)
        "pp_career_runs": None,
        "pp_win_rate": None,
        "pp_place_rate": None,
        "pp_days_since_last": None,
        "pp_layoff": None,
        "pp_avg_sp_last5": None,
        "pp_jockey_continuity": None,
        "pp_course_seen": None,
        "pp_or_change_3": None,
        "pp_class_moved_up": None,
        "pp_class_moved_down": None,
        
        # V2 Additive Keys
        "pp_win_rate_last3": None,
        "pp_win_rate_last6": None,
        "pp_place_rate_last3": None,
        "pp_avg_beaten_margin_last3": None,
        "pp_avg_sp_last3": None,
        "pp_beaten_margin_slope": None,
        "pp_position_trend_num": None,
        "pp_runs_in_last_90d": None,
    }

def lookup_passport_features(
    horse_rp_uid: int | None,
    horse_name: str | None,
    as_of_date: date | None = None,
    target_course: str | None = None,
    target_going_code: float | None = None,
    target_dist_f: float | None = None,
) -> Dict[str, Any]:
    """Looks up passport and computes model-ready features."""
    load_index()
    
    as_of_date = as_of_date or date.today()
    
    passport = None
    if horse_rp_uid and int(horse_rp_uid) in _by_uid:
        passport = _by_uid[int(horse_rp_uid)]
    elif horse_name and horse_name.strip().lower() in _by_name:
        passport = _by_name[horse_name.strip().lower()]
        
    if not passport:
        # Log at debug if horse_name is available
        # if horse_name: logger.debug(f"PASSPORT_MISS: {horse_name}")
        return _null_features()

    # Base features from V1 fields
    res = _null_features()
    res["pp_career_runs"] = passport.get("career_runs")
    res["pp_win_rate"] = passport.get("win_rate")
    res["pp_place_rate"] = passport.get("place_rate")
    
    # Dynamic days since last run
    last_run_str = passport.get("last_run_date")
    days_since = None
    layoff_val = None
    if last_run_str:
        try:
            last_run_date = date.fromisoformat(last_run_str)
            days_since = (as_of_date - last_run_date).days
            
            # Encode layoff_flag as int
            if days_since >= 180: layoff_val = 4
            elif days_since >= 90: layoff_val = 3
            elif days_since >= 60: layoff_val = 2
            elif days_since >= 30: layoff_val = 1
            else: layoff_val = 0
        except Exception:
            pass
            
    res["pp_days_since_last"] = float(days_since) if days_since is not None else None
    res["pp_layoff"] = float(layoff_val) if layoff_val is not None else None
    
    res["pp_avg_sp_last5"] = passport.get("avg_sp_last5")
    res["pp_jockey_continuity"] = 1.0 if passport.get("jockey_continuity") else 0.0
    res["pp_course_seen"] = 1.0 if passport.get("course_repeat") else 0.0
    res["pp_or_change_3"] = float(passport.get("or_change_last3")) if passport.get("or_change_last3") is not None else None
    
    class_mv = passport.get("class_movement")
    res["pp_class_moved_up"] = 1.0 if class_mv == "UP" else 0.0
    res["pp_class_moved_down"] = 1.0 if class_mv == "DOWN" else 0.0

    # V2 Fields
    res["pp_win_rate_last3"] = passport.get("win_rate_last3")
    res["pp_win_rate_last6"] = passport.get("win_rate_last6")
    res["pp_place_rate_last3"] = passport.get("place_rate_last3")
    res["pp_avg_beaten_margin_last3"] = passport.get("avg_beaten_margin_last3")
    res["pp_avg_sp_last3"] = passport.get("avg_sp_last3")
    res["pp_beaten_margin_slope"] = passport.get("beaten_margin_slope")
    
    trend = passport.get("position_trend")
    trend_map = {"IMPROVING": -1, "STABLE": 0, "DECLINING": 1}
    res["pp_position_trend_num"] = float(trend_map.get(trend)) if trend in trend_map else None
    
    # Recalculate runs in last 90d if we could? 
    # No, we only store the counts from the build as_of_date. 
    # But Task 1 said store runs_in_last_90d based on as_of_date parameter.
    # The JSONL contains what was computed at BUILD time.
    # We return what's in the passport.
    res["pp_runs_in_last_90d"] = passport.get("runs_in_last_90d")

    return res

def batch_lookup(
    runners: List[Dict],
    as_of_date: date | None = None,
) -> Tuple[List[Dict], Dict]:
    """Enriches a list of runners with passport features and returns coverage summary."""
    load_index()
    
    as_of_date = as_of_date or date.today()
    cov_logger = PassportCoverageLogger()
    
    enriched = []
    for r in runners:
        uid = r.get("horse_rp_uid")
        name = r.get("horse_name")
        
        feats = lookup_passport_features(uid, name, as_of_date=as_of_date)
        
        # Check if we actually found a passport (using career_runs as proxy for data)
        if feats.get("pp_career_runs") is not None:
            cov_logger.log_hit(name, uid)
        else:
            cov_logger.log_miss(name, uid)
            
        new_r = r.copy()
        new_r.update(feats)
        enriched.append(new_r)
        
    summary = cov_logger.summary()
    
    cov_logger.write_report(_COVERAGE_REPORT)
    
    # Log coverage thresholds
    pct = summary["coverage_pct"]
    if pct >= 80:
        print(f"PASSPORT_COVERAGE: GOOD ({pct:.1f}%)")
    elif pct >= 50:
        print(f"PASSPORT_COVERAGE: PARTIAL ({pct:.1f}%) — consider passport queue refresh")
    else:
        print(f"PASSPORT_COVERAGE: LOW ({pct:.1f}%) — passport bank needs growth")
        
    return enriched, summary
