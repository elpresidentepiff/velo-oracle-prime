import json
from pathlib import Path

def check_standard_cache():
    path = Path("data/racecards_2026_06_06_standard.json")
    if not path.exists():
        print("Standard cache not found")
        return
    
    data = json.loads(path.read_text(encoding='utf-8'))
    print(f"Total races in standard cache: {len(data)}")
    
    for r in data:
        if r.get("course") == "Worcester":
            time = r.get("race_time") or r.get("off_time")
            runners = [run.get("horse") for run in r.get("runners", [])]
            print(f"Time: {time} | Runners: {len(runners)} | {runners[:3]}...")

if __name__ == "__main__":
    check_standard_cache()
