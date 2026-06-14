import json
from pathlib import Path

def audit_step_6():
    f = Path('data/new_build/reports/two_lane_readiness_2026_06_06.json')
    if not f.exists():
        print('FAIL: two_lane_readiness missing')
        return
        
    d = json.load(open(f))
    print(f'STATUS: {d.get("overall_status")}')
    print(f'RACES SCORED: {d.get("races_scored")}')
    print(f'RUNNERS SCORED: {d.get("runners_scored")}')
    print(f'LANE: {d.get("operational_lane")}')

if __name__ == "__main__":
    audit_step_6()
