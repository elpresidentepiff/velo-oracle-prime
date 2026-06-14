import json
from pathlib import Path

def check_ts_coverage():
    feed_path = Path("data/new_build/current_cards/current_card_passport_feed_latest.jsonl")
    if not feed_path.exists():
        print("Feed not found")
        return

    date_target = "2026-06-03"
    total_runners = 0
    ts_hits = 0
    traj_hits = 0
    
    for line in feed_path.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row = json.loads(line)
        if str(row.get("race_date", ""))[:10] != date_target:
            continue
            
        total_runners += 1
        pp = row.get("passport_summary", {})
        if pp.get("pp_best_ts_last6") is not None:
            ts_hits += 1
        if pp.get("pp_ts_trajectory") is not None:
            traj_hits += 1
            
    print(f"June 3rd Runners: {total_runners}")
    print(f"pp_best_ts_last6 coverage: {ts_hits} / {total_runners} ({ts_hits/total_runners:.1%})")
    print(f"pp_ts_trajectory coverage: {traj_hits} / {total_runners} ({traj_hits/total_runners:.1%})")

if __name__ == "__main__":
    check_ts_coverage()
