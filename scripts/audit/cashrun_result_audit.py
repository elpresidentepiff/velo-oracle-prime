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
        self.idx_race_horse_id = {}
        self.idx_race_horse_name = {}
        self.idx_course_time_name = {}
        self.idx_global_name = {}
        self.global_name_counts = {}
        self.results_race_ids = set()
        self.results_horse_ids = set()
        
        # Leakage Status
        self.leakage_status = "TUNED_ON_SAME_DAY_DATA" if date_str == "2026-05-01" else "PRE_OUTCOME_RULES"
        self.performance_status = "DEV_ONLY_NOT_EVIDENCE" if self.leakage_status == "TUNED_ON_SAME_DAY_DATA" else "FORWARD_TEST_ELIGIBLE"

    def _normalize_name(self, name: str) -> str:
        return name.upper().split("(")[0].strip()

    def _normalize_time(self, time_str: str) -> str:
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
                if race_id: self.results_race_ids.add(race_id)
                course = race.get("course", "").upper().split("(")[0].strip()
                off_time = self._normalize_time(race.get("off", ""))
                
                for runner in race.get("runners", []):
                    horse_id = runner.get("horse_id")
                    if horse_id: self.results_horse_ids.add(horse_id)
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
                    
                    if race_id and horse_id:
                        self.idx_race_horse_id[f"{race_id}_{horse_id}"] = res_obj
                    if race_id:
                        self.idx_race_horse_name[f"{race_id}_{horse_clean}"] = res_obj
                    self.idx_course_time_name[f"{course}_{off_time}_{horse_clean}"] = res_obj
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
        for key, res in self.idx_course_time_name.items():
            k_course, k_time, k_horse = key.split("_", 2)
            if (venue in k_course or k_course.startswith(venue)) and k_time == race_time and k_horse == horse_clean:
                return res, "MATCH_COURSE_TIME_NAME", key
                    
        if self.global_name_counts.get(horse_clean, 0) == 1:
            return self.idx_global_name[horse_clean], "MATCH_GLOBAL_UNIQUE", horse_clean
            
        if self.global_name_counts.get(horse_clean, 0) > 1:
            return None, "AMBIGUOUS", "NONE"
            
        return None, "NO_MATCH", "NONE"

    def run_audit(self):
        csv_path = self.repo_root / f"data/cashrun_report_{self.date_str}.csv"
        unmatched_rows = []
        
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
                else:
                    row["won"] = False
                    row["placed"] = False
                    row["place_rule"] = "NONE"
                    row["sp_dec"] = 0.0
                    row["result_found"] = False
                    
                    if match_status == "NO_MATCH":
                        unmatched_info = {
                            "race_id": row.get("race_id"),
                            "horse_id": row.get("horse_id"),
                            "horse": row.get("horse"),
                            "course": row.get("course"),
                            "off_time": row.get("off_time"),
                            "reason": "NOT_IN_RESULT_FILE",
                            "race_id_exists": row.get("race_id") in self.results_race_ids,
                            "horse_id_exists": row.get("horse_id") in self.results_horse_ids
                        }
                        unmatched_rows.append(unmatched_info)
                    
                self.audit_data.append(row)
        
        self._save_unmatched(unmatched_rows)
        self._generate_summary()

    def _save_unmatched(self, rows: List[Dict]):
        out_path = self.repo_root / f"data/cashrun_unmatched_{self.date_str}.csv"
        if rows:
            keys = rows[0].keys()
            with open(out_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
            print(f"Unmatched rows logged to {out_path}")

    def _calculate_metrics(self, subset):
        n = len(subset)
        wins = len([r for r in subset if str(r["won"]).lower() == 'true'])
        places = len([r for r in subset if str(r["placed"]).lower() == 'true'])
        pnl = -n
        for r in subset:
            if str(r["won"]).lower() == 'true':
                try: pnl += float(r["sp_dec"])
                except: pass
        return {
            "n": n, "wins": wins, "places": places,
            "sr": (wins / n * 100) if n > 0 else 0,
            "frame": (places / n * 100) if n > 0 else 0,
            "roi": (pnl / n * 100) if n > 0 else 0
        }

    def _generate_summary(self):
        classes = ["CASHRUN_READY", "CASHRUN_WATCH", "WEAK_SIGNAL", "SUPPRESS"]
        id_grade_stats = ["MATCH_RACE_HORSE_ID", "MATCH_RACE_HORSE_NAME"]
        fallback_stats = ["MATCH_COURSE_TIME_NAME", "MATCH_GLOBAL_UNIQUE"]
        
        md_path = self.repo_root / f"data/cashrun_result_audit_{self.date_str}.md"
        with open(md_path, 'w') as f:
            f.write(f"# CASHRUN Result Audit — {self.date_str}\n\n")
            f.write(f"**LEAKAGE_STATUS:** {self.leakage_status}\n")
            f.write(f"**PERFORMANCE_STATUS:** {self.performance_status}\n\n")
            
            f.write("## 1. Match Breakdown\n")
            match_counts = {}
            for r in self.audit_data:
                s = r["result_match_status"]
                match_counts[s] = match_counts.get(s, 0) + 1
            
            for s in id_grade_stats + fallback_stats + ["AMBIGUOUS", "NO_MATCH"]:
                f.write(f"- {s}: {match_counts.get(s, 0)}\n")

            f.write("\n## 2. Performance Summary\n")
            
            for group_name, statuses in [("IDENTITY-GRADE ONLY", id_grade_stats), ("FALLBACK MATCHES ONLY", fallback_stats), ("COMBINED (ID + FALLBACK)", id_grade_stats + fallback_stats)]:
                f.write(f"### {group_name}\n")
                f.write("| Class | n | Winners | Placed | SR | Frame | ROI |\n")
                f.write("|---|---:|---:|---:|---:|---:|---:|\n")
                for c in classes:
                    subset = [r for r in self.audit_data if r["label"] == c and r["result_match_status"] in statuses]
                    m = self._calculate_metrics(subset)
                    f.write(f"| {c} | {m['n']} | {m['wins']} | {m['places']} | {m['sr']:.1f}% | {m['frame']:.1f}% | {m['roi']:.1f}% |\n")
                f.write("\n")

            f.write("## 3. Governance Checks\n")
            krg = next((r for r in self.audit_data if self._normalize_name(r["horse"]) == "KING RASKO GREY"), None)
            if krg:
                outcome = "WON" if str(krg["won"]).lower() == 'true' else ("PLACED" if str(krg["placed"]).lower() == 'true' else "LOST")
                f.write(f"- **King Rasko Grey** Match: {krg['result_match_status']} ({krg['result_match_key']})\n")
                f.write(f"- **King Rasko Grey** Outcome: {outcome}\n")

        print(f"Audit summary written to {md_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    repo_root = Path(__file__).parent.parent
    audit = CashrunResultAudit(args.date, repo_root)
    if audit.load_results():
        audit.run_audit()
