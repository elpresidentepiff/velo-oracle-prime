import json
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

class CashrunResultAudit:
    def __init__(self, date_str: str, repo_root: Path):
        self.date_str = date_str
        self.repo_root = repo_root
        self.results_data = []
        self.audit_data = []
        # Index dictionaries for different matching strategies
        self.idx_race_horse_id = {}
        self.idx_race_horse_name = {}
        self.idx_course_time_name = {}
        self.idx_global_name = {}
        self.global_name_counts = {}

    def _normalize_name(self, name: str) -> str:
        return name.upper().split("(")[0].strip()

    def _normalize_time(self, time_str: str) -> str:
        # e.g., "9:30" or "4.30" -> normalize to "HH:MM" format if possible or just strip
        return time_str.replace(".", ":").strip()

    def load_results(self):
        res_path = self.repo_root / f"data/results_{self.date_str.replace('-', '_')}.json"
        if not res_path.exists():
            print(f"Results file not found: {res_path}")
            return False
            
        with open(res_path, 'r') as f:
            full_data = json.load(f)
            self.results_data = full_data.get("results", [])
            
            for race in self.results_data:
                race_id = race.get("race_id")
                course = race.get("course", "").upper().split("(")[0].strip()
                off_time = self._normalize_time(race.get("off", ""))
                
                for runner in race.get("runners", []):
                    horse_id = runner.get("horse_id")
                    raw_horse = runner.get("horse", "")
                    horse_clean = self._normalize_name(raw_horse)
                    
                    pos = runner.get("position", "0")
                    won = (pos == "1")
                    placed = False
                    place_rule = "NONE"
                    
                    try:
                        p_val = int(pos)
                        if 1 <= p_val <= 3:
                            placed = True
                            place_rule = "TOP3_PROVISIONAL"
                    except ValueError:
                        pass
                        
                    res_obj = {
                        "won": won,
                        "placed": placed,
                        "place_rule": place_rule,
                        "sp_dec": runner.get("sp_dec", 0.0),
                        "horse_clean": horse_clean,
                        "race_id": race_id,
                        "horse_id": horse_id,
                        "course": course,
                        "off_time": off_time
                    }
                    
                    # 1. race_id + horse_id
                    if race_id and horse_id:
                        self.idx_race_horse_id[f"{race_id}_{horse_id}"] = res_obj
                    
                    # 2. race_id + normalized horse name
                    if race_id:
                        self.idx_race_horse_name[f"{race_id}_{horse_clean}"] = res_obj
                        
                    # 3. course + off_time + normalized horse name
                    self.idx_course_time_name[f"{course}_{off_time}_{horse_clean}"] = res_obj
                    
                    # 4. global name fallback
                    self.idx_global_name[horse_clean] = res_obj
                    self.global_name_counts[horse_clean] = self.global_name_counts.get(horse_clean, 0) + 1
                    
        return True

    def _find_match(self, row: Dict) -> (Optional[Dict], str, str):
        horse_name = row.get("horse", "")
        horse_clean = self._normalize_name(horse_name)
        venue = row.get("venue", "").upper()
        race_time = self._normalize_time(row.get("off_time", ""))
        race_id = row.get("race_id", "")
        horse_id = row.get("horse_id", "")
        
        # 1. race_id + horse_id
        if race_id and horse_id:
            key = f"{race_id}_{horse_id}"
            if key in self.idx_race_horse_id:
                return self.idx_race_horse_id[key], "MATCH_RACE_HORSE_ID", key
        
        # 2. race_id + normalized horse name
        if race_id:
            key = f"{race_id}_{horse_clean}"
            if key in self.idx_race_horse_name:
                return self.idx_race_horse_name[key], "MATCH_RACE_HORSE_NAME", key
        
        # 3. course + off_time + normalized horse name
        # Try to find matching course in results based on venue code
        for key, res in self.idx_course_time_name.items():
            k_course, k_time, k_horse = key.split("_", 2)
            if (venue in k_course or k_course.startswith(venue)) and k_time == race_time and k_horse == horse_clean:
                return res, "MATCH_COURSE_TIME_NAME", key
                    
        # Strategy 4: fallback global horse name ONLY if unique
        if self.global_name_counts.get(horse_clean, 0) == 1:
            return self.idx_global_name[horse_clean], "MATCH_GLOBAL_UNIQUE", horse_clean
            
        # Ambiguous or missing
        if self.global_name_counts.get(horse_clean, 0) > 1:
            return None, "AMBIGUOUS", "NONE"
            
        return None, "NO_MATCH", "NONE"

    def run_audit(self):
        csv_path = self.repo_root / f"data/cashrun_report_{self.date_str}.csv"
        if not csv_path.exists():
            print(f"CASHRUN report CSV not found: {csv_path}")
            return
            
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                result, match_status, match_key = self._find_match(row)
                
                row["result_match_status"] = match_status
                row["result_match_key"] = match_key
                
                if result:
                    row["won"] = result["won"]
                    row["placed"] = result["placed"]
                    row["place_rule"] = result["place_rule"]
                    row["sp_dec"] = result["sp_dec"]
                    row["result_found"] = True
                    row["result_race_id"] = result["race_id"]
                    row["result_horse_id"] = result["horse_id"]
                    row["result_course"] = result["course"]
                    row["result_off_time"] = result["off_time"]
                else:
                    row["won"] = False
                    row["placed"] = False
                    row["place_rule"] = "NONE"
                    row["sp_dec"] = 0.0
                    row["result_found"] = False
                    row["result_race_id"] = ""
                    row["result_horse_id"] = ""
                    row["result_course"] = ""
                    row["result_off_time"] = ""
                    
                self.audit_data.append(row)
                
        self._generate_summary()

    def _generate_summary(self):
        classes = ["CASHRUN_READY", "CASHRUN_WATCH", "WEAK_SIGNAL", "SUPPRESS"]
        summary = {}
        
        total_rows = len(self.audit_data)
        match_stats = {
            "MATCH_RACE_HORSE_ID": 0,
            "MATCH_RACE_HORSE_NAME": 0,
            "MATCH_COURSE_TIME_NAME": 0,
            "MATCH_GLOBAL_UNIQUE": 0,
            "AMBIGUOUS": 0,
            "NO_MATCH": 0
        }
        
        for r in self.audit_data:
            match_stats[r["result_match_status"]] += 1
            
        for c in classes:
            # ONLY count non-ambiguous valid matches
            subset = [r for r in self.audit_data if r["label"] == c and r["result_found"]]
            n = len(subset)
            wins = len([r for r in subset if str(r["won"]).lower() == 'true'])
            places = len([r for r in subset if str(r["placed"]).lower() == 'true'])
            
            pnl = -n
            for r in subset:
                if str(r["won"]).lower() == 'true':
                    try: pnl += float(r["sp_dec"])
                    except ValueError: pass
                    
            summary[c] = {
                "n": n,
                "wins": wins,
                "places": places,
                "sr": (wins / n * 100) if n > 0 else 0,
                "frame": (places / n * 100) if n > 0 else 0,
                "roi": (pnl / n * 100) if n > 0 else 0
            }

        md_path = self.repo_root / f"data/cashrun_result_audit_{self.date_str}.md"
        with open(md_path, 'w') as f:
            f.write(f"# CASHRUN Result Audit — {self.date_str}\n\n")
            f.write("## Match Statistics\n")
            f.write(f"- Total rows: {total_rows}\n")
            f.write(f"- Matched by race_id + horse_id: {match_stats['MATCH_RACE_HORSE_ID']}\n")
            f.write(f"- Matched by race_id + horse_name: {match_stats['MATCH_RACE_HORSE_NAME']}\n")
            f.write(f"- Matched by course/time/horse: {match_stats['MATCH_COURSE_TIME_NAME']}\n")
            f.write(f"- Matched by unique global fallback: {match_stats['MATCH_GLOBAL_UNIQUE']}\n")
            f.write(f"- Ambiguous rows: {match_stats['AMBIGUOUS']}\n")
            f.write(f"- Unmatched rows: {match_stats['NO_MATCH']}\n\n")
            
            f.write("## Performance Summary (Clean Matches Only)\n")
            f.write("| Class | n | Winners | Placed | SR | Frame | ROI |\n")
            f.write("|---|---:|---:|---:|---:|---:|---:|\n")
            for c in classes:
                s = summary[c]
                f.write(f"| {c} | {s['n']} | {s['wins']} | {s['places']} | {s['sr']:.1f}% | {s['frame']:.1f}% | {s['roi']:.1f}% |\n")
            
            f.write("\n## Governance Checks\n")
            ready_sr = summary["CASHRUN_READY"]["sr"]
            watch_sr = summary["CASHRUN_WATCH"]["sr"]
            weak_sr = summary["WEAK_SIGNAL"]["sr"]
            
            monotonic = (ready_sr >= watch_sr >= weak_sr)
            f.write(f"- Monotonic SR: {'PASS' if monotonic else 'FAIL'}\n")
            
            krg = next((r for r in self.audit_data if self._normalize_name(r["horse"]) == "KING RASKO GREY"), None)
            if krg:
                outcome = "WON" if str(krg["won"]).lower() == 'true' else ("PLACED" if str(krg["placed"]).lower() == 'true' else "LOST")
                f.write(f"- **King Rasko Grey** Match Key: {krg['result_match_key']}\n")
                f.write(f"- **King Rasko Grey** Outcome: {outcome} (Score: {krg.get('total_score', 'N/A')})\n")

        print(f"Audit summary written to {md_path}")
        
        # Save enriched CSV
        out_csv_path = self.repo_root / f"data/cashrun_result_audit_{self.date_str}.csv"
        if self.audit_data:
            keys = self.audit_data[0].keys()
            with open(out_csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(self.audit_data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).parent.parent
    audit = CashrunResultAudit(args.date, repo_root)
    if audit.load_results():
        audit.run_audit()
