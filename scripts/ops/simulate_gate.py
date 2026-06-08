import sys, json, tempfile
from pathlib import Path
import os

# Ensure the correct path for imports
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ops.velo_race_day_button import _preflight_injection_gate

def simulate_gate():
    # Inject a bad race with null off_time
    bad = {'races': [
        {'course': 'Ascot', 'off_time': '14:30'},
        {'course': 'Chepstow', 'off_time': None},   # THE BUG
        {'course': 'Newbury', 'off_time': '15:00'},
        {'course': 'York', 'off_time': '15:30'},
    ]}
    
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(bad, f)
        tmp = f.name
        
    try:
        fails = _preflight_injection_gate(Path(tmp), '2026-06-06')
        print('GATE RESULT:', fails)
        assert any('OFF_TIME_NULL' in x for x in fails), 'GATE DID NOT FIRE — CRITICAL BUG'
        print('CONFIRMED: gate fires on null off_time')
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

if __name__ == "__main__":
    simulate_gate()
