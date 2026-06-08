import json
from pathlib import Path

def audit_step_4():
    files = sorted(Path('data/racecard_merged').glob('*2026-06-06.json'))
    print(f'MERGED FILE COUNT: {len(files)}')
    for f in files:
        d = json.load(open(f))
        races = d.get('races', {})
        times = sorted(races.keys())
        print(f'  {f.name}: {len(races)} races — {times}')
        
        # Verify racecard_CHP_2026-06-06.json has first time key 5.10
        if f.name == 'racecard_CHP_2026-06-06.json':
            if '5.10' not in times:
                print("FAIL: Chepstow 5.10 missing")
            else:
                print("CONFIRMED: Chepstow 5.10 present")

if __name__ == "__main__":
    audit_step_4()
