import json
import csv
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# CASHRUN GOVERNANCE LOCK
CASHRUN_VERSION = "CASHRUN_V1_DEV_LOCK"
# Hash of the logic logic: OR norm, keywords, triplet bonus, thresholds
SCORING_RULES_HASH = "8e9f2a4b1c" 
CREATED_AT = "2026-05-03"

class CashrunDetector:
    def __init__(self, date_str: str, repo_root: Path):
        self.date_str = date_str
        self.repo_root = repo_root
        self.scored_horses = []
        self.mode = "SHADOW_OPERATOR_ONLY"
        self.tuned_on_same_day = (date_str == "2026-05-01")
        self.field_coverage = {
            "venues": set(),
            "horses_scanned": 0,
            "or_history_n": 0,
            "ts_history_n": 0,
            "spotlight_n": 0,
            "postdata_n": 0
        }
        # THRESHOLDS
        self.thresholds = {
            "READY": 75,
            "WATCH": 55,
            "WEAK": 35
        }
        self.identity_map = {} # (course, time, horse) -> (race_id, horse_id)

    def _normalize_name(self, name: str) -> str:
        return name.upper().split("(")[0].strip()

    def _normalize_time(self, time_str: str) -> str:
        return time_str.replace(".", ":").strip()

    def _load_identity_enrichment(self):
        """Loads race_id and horse_id from standard racecard JSON."""
        api_card_path = self.repo_root / f"data/racecards_{self.date_str.replace('-', '_')}_standard.json"
        if api_card_path.exists():
            try:
                with open(api_card_path, 'r') as f:
                    full_data = json.load(f)
                    cards = full_data.get("racecards", [])
                    for race in cards:
                        r_id = race.get("race_id")
                        course = race.get("course", "").upper().split("(")[0].strip()
                        off_time = self._normalize_time(race.get("off_time", ""))
                        for runner in race.get("runners", []):
                            h_id = runner.get("horse_id")
                            h_name = self._normalize_name(runner.get("horse", ""))
                            # Map by course-time-horse
                            key = (course, off_time, h_name)
                            self.identity_map[key] = (r_id, h_id)
            except Exception as e:
                print(f"Warning: Failed to load identity enrichment: {e}")

    def run_daily_detection(self):
        """Main entry point for daily CASHRUN detection."""
        self._load_identity_enrichment()
        
        merged_dir = self.repo_root / "data/racecard_merged"
        merged_files = list(merged_dir.glob(f"racecard_*_{self.date_str}.json"))
        
        for file_path in merged_files:
            with open(file_path, 'r') as f:
                card = json.load(f)
                self._process_venue_card(card)

        self._save_reports()
        return self.scored_horses

    def _process_venue_card(self, card: Dict):
        venue = card.get("venue")
        course_name = card.get("course_name") or venue # Usually merged cards have venue code only
        self.field_coverage["venues"].add(venue)
        
        for race_time, race_data in card.get("races", {}).items():
            race_name = race_data.get("race_name", "")
            norm_time = self._normalize_time(race_time)
            
            for horse in race_data.get("horses", []):
                self.field_coverage["horses_scanned"] += 1
                
                h_name = self._normalize_name(horse.get("horse_name", ""))
                
                # Attempt identity join
                race_id, horse_id = "", ""
                # Try exact course if known, else iterate identity_map for venue matches
                match_found = False
                for (c, t, h), (rid, hid) in self.identity_map.items():
                    if t == norm_time and h == h_name:
                        if venue in c or c.startswith(venue):
                            race_id, horse_id = rid, hid
                            match_found = True
                            break
                
                # Inject identity into horse for output
                horse["_race_id"] = race_id
                horse["_horse_id"] = horse_id
                horse["_course"] = course_name
                horse["_off_time"] = race_time
                horse["_venue"] = venue
                horse["_race_name"] = race_name
                
                scored = self._score_horse(horse, venue, race_time)
                self.scored_horses.append(scored)

    def _score_horse(self, horse: Dict, venue: str, race_time: str) -> Dict:
        name = horse.get("horse_name")
        current_or = horse.get("current_or")
        
        or_score, last_win_or = self._calculate_or_compression(horse)
        ts_rpr_score = self._calculate_ts_rpr_hidden_form(horse)
        setup_score = self._calculate_setup_pattern(horse)
        intent_score = self._calculate_intent(horse)
        sp_pd_score, evidence_phrases = self._calculate_sp_pd_score(horse)
        
        raw_total = or_score + ts_rpr_score + setup_score + intent_score + sp_pd_score
        total_score = min(100.0, raw_total)
        
        label = "SUPPRESS"
        if total_score >= self.thresholds["READY"]: label = "CASHRUN_READY"
        elif total_score >= self.thresholds["WATCH"]: label = "CASHRUN_WATCH"
        elif total_score >= self.thresholds["WEAK"]: label = "WEAK_SIGNAL"
        
        if horse.get("or_run_history"): self.field_coverage["or_history_n"] += 1
        if horse.get("ts_run_history"): self.field_coverage["ts_history_n"] += 1
        if horse.get("spotlight_comment"): self.field_coverage["spotlight_n"] += 1
        if horse.get("postdata_score") is not None: self.field_coverage["postdata_n"] += 1

        missing_fields = []
        if not horse.get("or_run_history"): missing_fields.append("OR_HISTORY")
        if not horse.get("ts_run_history"): missing_fields.append("TS_HISTORY")
        if not horse.get("spotlight_comment"): missing_fields.append("SPOTLIGHT")

        return {
            "date": self.date_str,
            "race_id": horse.get("_race_id", ""),
            "horse_id": horse.get("_horse_id", ""),
            "course": horse.get("_course", ""),
            "off_time": horse.get("_off_time", ""),
            "race_name": horse.get("_race_name", ""),
            "venue": horse.get("_venue", ""),
            "horse": name,
            "cashrun_version": CASHRUN_VERSION,
            "scoring_rules_hash": SCORING_RULES_HASH,
            "total_score": total_score,
            "label": label,
            "or_score": or_score,
            "ts_rpr_score": ts_rpr_score,
            "setup_score": setup_score,
            "intent_score": intent_score,
            "spotlight_postdata_score": sp_pd_score,
            "current_or": current_or,
            "last_win_or": last_win_or,
            "trainer": horse.get("trainer"),
            "jockey": horse.get("jockey"),
            "missing_fields": "|".join(missing_fields),
            "evidence_phrases": "|".join(evidence_phrases),
            "mode": self.mode,
            "tuned_on_same_day": self.tuned_on_same_day,
            "date_run": datetime.now().strftime("%Y-%m-%d")
        }

    def _calculate_or_compression(self, horse: Dict) -> (float, Optional[int]):
        current_or = horse.get("current_or")
        history = horse.get("or_run_history", [])
        if not current_or or not history: return 0.0, None
        last_win_or = None
        for run in history:
            if run.get("pos") == 1:
                val = run.get("or")
                if val is not None:
                    try: last_win_or = int(val)
                    except: pass
                if last_win_or: break
        score = 0.0
        if last_win_or:
            if current_or > 40 and last_win_or < 40: last_win_or *= 10
            diff = last_win_or - current_or
            if diff >= 0: score = min(30.0, 20.0 + (diff * 2.0))
        if horse.get("or_trend_drops", 0) > 3: score = max(score, 15.0)
        return score, last_win_or

    def _calculate_ts_rpr_hidden_form(self, horse: Dict) -> float:
        score = 0.0
        ts_master = horse.get("ts_master", 0)
        current_or = horse.get("current_or", 0)
        if ts_master and current_or and ts_master > current_or: score += 10.0
        if horse.get("ts_trend_signal", 0) > 0.1: score += 10.0
        return min(20.0, score)

    def _calculate_setup_pattern(self, horse: Dict) -> float:
        score, flags = 0.0, 0
        if horse.get("going_flag") == "positive": score += 5; flags += 1
        if horse.get("distance_flag") == "positive": score += 5; flags += 1
        if horse.get("course_flag") == "positive": score += 5; flags += 1
        if flags == 3: score += 5
        if "all_systems_go" in (horse.get("intent_signals") or []): score += 5
        return min(25.0, score)

    def _calculate_intent(self, horse: Dict) -> float:
        score = 0.0
        if horse.get("trainer_form") == "positive": score += 5
        if horse.get("headgear_cc"): score += 5
        jc = horse.get("jockey_claim")
        if jc is not None and jc > 0: score += 5
        return min(15.0, score)

    def _calculate_sp_pd_score(self, horse: Dict) -> (float, List[str]):
        score, phrases = 0.0, []
        if horse.get("is_postdata_pick"): score += 7.5; phrases.append("POSTDATA_PICK")
        if horse.get("is_topspeed_pick"): score += 7.5; phrases.append("TS_PICK")
        spotlight = horse.get("spotlight_comment", "").lower()
        targets = ["down in trip", "well treated", "dropped in grade", "bold show", "big run", "strong claims", "interesting", "career low", "unexposed", "leading contender"]
        for p in targets:
            if p in spotlight: score += 2.0; phrases.append(p.upper().replace(" ", "_"))
        return min(25.0, score), phrases

    def _save_reports(self):
        md_path = self.repo_root / f"data/cashrun_report_{self.date_str}.md"
        csv_path = self.repo_root / f"data/cashrun_report_{self.date_str}.csv"
        sorted_horses = sorted(self.scored_horses, key=lambda x: x["total_score"], reverse=True)
        with open(md_path, 'w') as f:
            f.write(f"# VÉLØ CASHRUN REPORT — {self.date_str}\n\n")
            f.write(f"Version: {CASHRUN_VERSION} | Hash: {SCORING_RULES_HASH} | Mode: {self.mode}\n")
            if self.tuned_on_same_day: f.write("> **WARNING: TUNED_ON_SAME_DAY_DATA** — forward validation required.\n\n")
            for label in ["CASHRUN_READY", "CASHRUN_WATCH", "WEAK_SIGNAL"]:
                subset = [h for h in sorted_horses if h["label"] == label]
                f.write(f"### {label} ({len(subset)} horses)\n")
                for h in subset:
                    f.write(f"- **{h['horse']}** | {h['venue']} {h['off_time']} | score={h['total_score']} | OR {h['current_or']} (win OR was {h['last_win_or']}) | {h['evidence_phrases']}\n")
                f.write("\n")
        if self.scored_horses:
            keys = self.scored_horses[0].keys()
            with open(csv_path, 'w', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(self.scored_horses)

    def print_summary(self):
        print(f"--- CASHRUN Detection Summary: {self.date_str} ---")
        print(f"Version:         {CASHRUN_VERSION}")
        print(f"Rules Hash:      {SCORING_RULES_HASH}")
        print(f"Horses scanned:  {self.field_coverage['horses_scanned']}")
        def pct(n): return f"{(n/self.field_coverage['horses_scanned']*100):.1f}%" if self.field_coverage['horses_scanned'] > 0 else "0.0%"
        print(f"Spotlight:       {pct(self.field_coverage['spotlight_n'])}")
        ready = len([h for h in self.scored_horses if h["label"] == "CASHRUN_READY"])
        watch = len([h for h in self.scored_horses if h["label"] == "CASHRUN_WATCH"])
        print(f"CASHRUN_READY:   {ready}")
        print(f"CASHRUN_WATCH:   {watch}")
        if self.tuned_on_same_day: print("!!! TUNED_ON_SAME_DAY_DATA detected")
        print(f"----------------------------------------")

if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).parent.parent
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    detector = CashrunDetector(date, repo_root)
    detector.run_daily_detection()
    detector.print_summary()
