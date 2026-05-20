
import os
import json
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MERGED_DIR = DATA_DIR / "racecard_merged"
DATE = "2026-05-03"

def audit_coverage():
    files = glob.glob(str(MERGED_DIR / f"*_{DATE}.json"))
    
    scanned_horses = 0
    stats = {
        "or": 0, "ts": 0, "rpr": 0, "last_6_runs": 0, "last_6_or": 0,
        "last_6_ts": 0, "last_6_rpr": 0, "spotlight": 0, "postdata": 0,
        "weight": 0, "class": 0, "distance": 0, "going": 0, "draw": 0,
        "headgear": 0, "trainer": 0, "jockey": 0
    }
    
    missing_report = []
    
    for f in files:
        with open(f) as j:
            data = json.load(j)
            venue = data.get("venue")
            for r_time, race in data.get("races", {}).items():
                r_class = race.get("race_info", "")
                for h in race.get("horses", []):
                    scanned_horses += 1
                    h_name = h.get("horse_name")
                    
                    if h.get("current_or"): stats["or"] += 1
                    if h.get("ts_run_history"): stats["ts"] += 1
                    # Note: RPR and detailed class/dist often come from the standard API card
                    # We are auditing what came from the PDFs specifically.
                    
                    hist = h.get("or_run_history", [])
                    if hist: stats["last_6_runs"] += 1
                    if any(x.get("or") for x in hist): stats["last_6_or"] += 1
                    
                    ts_hist = h.get("ts_run_history", [])
                    if any(x.get("ts") for x in ts_hist): stats["last_6_ts"] += 1
                    
                    if h.get("spotlight_verdict"): stats["spotlight"] += 1
                    if h.get("postdata_score"): stats["postdata"] += 1
                    
                    if not h.get("current_or"):
                        missing_report.append(f"{h_name} ({venue} {r_time}) - Missing OR")

    # Write Markdown
    output_path = DATA_DIR / f"racing_post_field_coverage_{DATE.replace('-', '_')}.md"
    with open(output_path, "w") as f:
        f.write(f"# Racing Post Field Coverage Audit — {DATE}\n\n")
        f.write(f"**Horses Scanned:** {scanned_horses}\n\n")
        f.write("| Field | Coverage % | Count |\n")
        f.write("|---|---:|---:|\n")
        for k, v in stats.items():
            pct = (v / scanned_horses * 100) if scanned_horses else 0
            f.write(f"| {k.upper()} | {pct:.1f}% | {v} |\n")
            
    print(f"Audit complete. Scanned {scanned_horses} horses.")
    print(f"Report saved to {output_path}")

if __name__ == "__main__":
    audit_coverage()
