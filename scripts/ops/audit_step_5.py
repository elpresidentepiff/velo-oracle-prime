import json
from pathlib import Path

def audit_step_5():
    f = Path('data/velo_prime_verdicts_2026_06_06.json')
    if not f.exists():
        print('FAIL: verdicts file missing')
        return
        
    d = json.load(open(f))
    verdicts = d if isinstance(d, list) else d.get('verdicts', d.get('races', []))
    print(f'VERDICT COUNT: {len(verdicts)}')
    courses = sorted(set(v.get('course') or v.get('venue') for v in verdicts if isinstance(v, dict)))
    print(f'COURSES: {courses}')
    chep = [v for v in verdicts if isinstance(v,dict) and 'hep' in str(v.get('course',''))]
    print(f'CHEPSTOW VERDICTS: {len(chep)}')
    if chep:
        times = sorted(set(v.get('off_time') or v.get('off') for v in chep))
        print(f'  TIMES: {times}')

if __name__ == "__main__":
    audit_step_5()
