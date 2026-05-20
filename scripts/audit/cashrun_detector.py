import json
import csv
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# CASHRUN GOVERNANCE LOCK
CASHRUN_VERSION = "CASHRUN_V1_DEV_LOCK"
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
            "spotlight_n": 0,
            "postdata_n": 0,
            "or_current_n": 0,
            "ts_current_n": 0,
            "rpr_current_n": 0,
            "or_last6_n": 0,
            "ts_last6_n": 0,
            "rpr_last6_n": 0,
            "trainer_n": 0,
            "jockey_n": 0,
            "class_n": 0,
            "distance_n": 0,
            "going_n": 0
        }
        self.thresholds = {"READY": 75, "WATCH": 55, "WEAK": 35}
        self.identity_map = {}

    def _normalize_name(self, name: str) -> str:
        return name.upper().split("(")[0].strip()

    def _normalize_time(self, time_str: str) -> str:
        return time_str.replace(".", ":").strip()

    def _load_identity_enrichment(self):
        api_card_path = self.repo_root / f"data/racecards_{self.date_str.replace('-', '_')}_standard.json"
        if api_card_path.exists():
            try:
                with open(api_card_path, 'r') as f:
                    full_data = json.load(f)
                    for race in full_data.get("racecards", []):
                        r_id = race.get("race_id")
                        course = race.get("course", "").upper().split("(")[0].strip()
                        off_time = self._normalize_time(race.get("off_time", ""))
                        for runner in race.get("runners", []):
                            h_id = runner.get("horse_id")
                            h_name = self._normalize_name(runner.get("horse", ""))
                            self.identity_map[(course, off_time, h_name)] = (r_id, h_id)
            except Exception as e:
                print(f"Warning: Failed to load identity enrichment: {e}")

    def run_daily_detection(self):
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
        course_name = card.get("course_name") or venue
        self.field_coverage["venues"].add(venue)
        
        for race_time, race_data in card.get("races", {}).items():
            norm_time = self._normalize_time(race_time)
            for horse in race_data.get("horses", []):
                self.field_coverage["horses_scanned"] += 1
                
                h_name = self._normalize_name(horse.get("horse_name", ""))
                race_id, horse_id = "", ""
                for (c, t, h), (rid, hid) in self.identity_map.items():
                    if t == norm_time and h == h_name and (venue in c or c.startswith(venue)):
                        race_id, horse_id = rid, hid
                        break
                
                # Global coverage tracking
                if horse.get("spotlight_comment"): self.field_coverage["spotlight_n"] += 1
                if horse.get("postdata_score") is not None: self.field_coverage["postdata_n"] += 1
                if horse.get("current_or"): self.field_coverage["or_current_n"] += 1
                if horse.get("ts_master"): self.field_coverage["ts_current_n"] += 1
                if horse.get("rpr_master"): self.field_coverage["rpr_current_n"] += 1
                if horse.get("or_run_history"): self.field_coverage["or_last6_n"] += 1
                if horse.get("ts_run_history"): self.field_coverage["ts_last6_n"] += 1
                if horse.get("rpr_run_history"): self.field_coverage["rpr_last6_n"] += 1
                if horse.get("trainer"): self.field_coverage["trainer_n"] += 1
                if horse.get("jockey"): self.field_coverage["jockey_n"] += 1
                if race_data.get("race_class"): self.field_coverage["class_n"] += 1
                if race_data.get("distance"): self.field_coverage["distance_n"] += 1
                if race_data.get("going"): self.field_coverage["going_n"] += 1

                # Inject metadata
                horse["_race_id"] = race_id
                horse["_horse_id"] = horse_id
                horse["_course"] = course_name
                horse["_off_time"] = race_time
                horse["_venue"] = venue
                horse["_race_name"] = race_data.get("race_name", "")
                
                scored = self._score_horse(horse, venue, race_time)
                self.scored_horses.append(scored)

    def _score_horse(self, horse: Dict, venue: str, race_time: str) -> Dict:
        or_score, last_win_or = self._calculate_or_compression(horse)
        ts_rpr_score = self._calculate_ts_rpr_hidden_form(horse)
        setup_score = self._calculate_setup_pattern(horse)
        intent_score = self._calculate_intent(horse)
        sp_pd_score, evidence_phrases = self._calculate_sp_pd_score(horse)
        
        total_score = min(100.0, or_score + ts_rpr_score + setup_score + intent_score + sp_pd_score)
        
        label = "SUPPRESS"
        if total_score >= self.thresholds["READY"]: label = "CASHRUN_READY"
        elif total_score >= self.thresholds["WATCH"]: label = "CASHRUN_WATCH"
        elif total_score >= self.thresholds["WEAK"]: label = "WEAK_SIGNAL"
        
        # Evidence trails
        or_h = [str(r.get('or', 'M')) for r in horse.get('or_run_history', [])[:6]]
        ts_h = [str(r.get('ts', 'M')) for r in horse.get('ts_run_history', [])[:6]]
        rpr_h = [str(r.get('rpr', 'M')) for r in horse.get('rpr_run_history', [])[:6]]

        return {
            "date": self.date_str,
            "race_id": horse.get("_race_id", ""),
            "horse_id": horse.get("_horse_id", ""),
            "course": horse.get("_course", ""),
            "off_time": horse.get("_off_time", ""),
            "race_name": horse.get("_race_name", ""),
            "venue": horse.get("_venue", ""),
            "horse": horse.get("horse_name", ""),
            "total_score": total_score,
            "label": label,
            "or_score": or_score,
            "ts_rpr_score": ts_rpr_score,
            "setup_score": setup_score,
            "intent_score": intent_score,
            "sp_pd_score": sp_pd_score,
            "last_6_or": "|".join(or_h) if or_h else "MISSING",
            "last_6_ts": "|".join(ts_h) if ts_h else "MISSING",
            "last_6_rpr": "|".join(rpr_h) if rpr_h else "MISSING",
            "spotlight_evidence": horse.get("spotlight_comment", "MISSING"),
            "postdata_evidence": "PRESENT" if horse.get("is_postdata_pick") else "MISSING",
            "evidence_phrases": "|".join(evidence_phrases),
            "cashrun_version": CASHRUN_VERSION,
            "scoring_rules_hash": SCORING_RULES_HASH,
            "mode": self.mode,
            "tuned_on_same_day": self.tuned_on_same_day,
            "date_run": datetime.now().strftime("%Y-%m-%d")
        }

    def _calculate_or_compression(self, horse: Dict) -> (float, Optional[int]):
        current_or, history = horse.get("current_or"), horse.get("or_run_history", [])
        if not current_or or not history: return 0.0, None
        last_win_or = None
        for run in history:
            if run.get("pos") == 1:
                try: 
                    last_win_or = int(run.get("or"))
                    if current_or > 40 and last_win_or < 40: last_win_or *= 10
                    break
                except: pass
        score = 0.0
        if last_win_or and (last_win_or - current_or) >= 0:
            score = min(30.0, 20.0 + ((last_win_or - current_or) * 2.0))
        if horse.get("or_trend_drops", 0) > 3: score = max(score, 15.0)
        return score, last_win_or

    def _calculate_ts_rpr_hidden_form(self, horse: Dict) -> float:
        score = 0.0
        ts, current_or = horse.get("ts_master", 0), horse.get("current_or", 0)
        if ts and current_or and ts > current_or: score += 10.0
        if horse.get("ts_trend_signal", 0) > 0.1: score += 10.0
        return min(20.0, score)

    def _calculate_setup_pattern(self, horse: Dict) -> float:
        score, flags = 0.0, 0
        for f in ["going_flag", "distance_flag", "course_flag"]:
            if horse.get(f) == "positive": score += 5; flags += 1
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
            f.write(f"Version: {CASHRUN_VERSION} | Rules Hash: {SCORING_RULES_HASH}\n")
            f.write(f"Leakage Status: {'TUNED_ON_SAME_DAY_DATA' if self.tuned_on_same_day else 'PRE_OUTCOME_RULES'}\n\n")
            
            f.write("## 1. Field Coverage\n")
            total = self.field_coverage["horses_scanned"]
            def pct(n): return f"{(n/total*100):.1f}%" if total > 0 else "0.0%"
            f.write(f"- Horses scanned: {total}\n")
            f.write(f"- Spotlight: {pct(self.field_coverage['spotlight_n'])}\n")
            f.write(f"- Postdata: {pct(self.field_coverage['postdata_n'])}\n")
            f.write(f"- Current OR: {pct(self.field_coverage['or_current_n'])}\n")
            f.write(f"- Last 6 OR: {pct(self.field_coverage['or_last6_n'])}\n")
            f.write(f"- Last 6 TS: {pct(self.field_coverage['ts_last6_n'])}\n")
            
            f.write("\n## 2. Signal Readiness\n")
            for label in ["CASHRUN_READY", "CASHRUN_WATCH"]:
                subset = [h for h in sorted_horses if h["label"] == label]
                f.write(f"### {label} ({len(subset)})\n")
                for h in subset:
                    f.write(f"#### {h['horse']} ({h['venue']} {h['off_time']})\n")
                    f.write(f"- **Score:** {h['total_score']} (OR: {h['or_score']}, TS: {h['ts_rpr_score']}, Setup: {h['setup_score']}, Intent: {h['intent_score']}, SP/PD: {h['sp_pd_score']})\n")
                    f.write(f"- **L6 OR:** `{h['last_6_or']}` | **L6 TS:** `{h['last_6_ts']}`\n")
                    f.write(f"- **Spotlight:** {h['spotlight_evidence']}\n")
                    f.write(f"- **Postdata:** {h['postdata_evidence']}\n")
                    f.write(f"- **Phrases:** {h['evidence_phrases']}\n\n")

        if self.scored_horses:
            keys = self.scored_horses[0].keys()
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(self.scored_horses)

    def print_summary(self):
        print(f"--- CASHRUN Detection Summary: {self.date_str} ---")
        print(f"READY: {len([h for h in self.scored_horses if h['label'] == 'CASHRUN_READY'])}")
        print(f"WATCH: {len([h for h in self.scored_horses if h['label'] == 'CASHRUN_WATCH'])}")
        print(f"Report: data/cashrun_report_{self.date_str}.md")

if __name__ == "__main__":
    import sys
    repo_root = Path(__file__).parent.parent.parent
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    detector = CashrunDetector(date, repo_root)
    detector.run_daily_detection()
    detector.print_summary()
