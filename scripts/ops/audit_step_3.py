import json
from pathlib import Path

def audit_step_3():
    path = Path('data/racecards_2026_06_06_standard.json')
    if not path.exists():
        print("FAIL: standard cache missing")
        return
        
    d = json.loads(path.read_text(encoding='utf-8'))
    races = d if isinstance(d, list) else d.get('races', d)
    
    if isinstance(races, list):
        print(f'RACE COUNT: {len(races)}')
        null_off = [r.get('course') for r in races if not r.get('off_time')]
        print(f'NULL OFF_TIME: {len(null_off)} — {null_off[:5]}')
        courses = sorted(set(r.get('course','?') for r in races))
        print(f'COURSES ({len(courses)}): {courses}')
    else:
        print(f'UNEXPECTED FORMAT: {type(races)}')

if __name__ == "__main__":
    audit_step_3()
