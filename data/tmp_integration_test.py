import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.velo.racecard_loader import load_rp_merged_as_racecards
from workers.racing_api_normalizer import normalize_race
from app.services.velo_prime_service import score_race_velo_prime
import asyncio
from app.optim.async_scheduler import run_chains_parallel
from src.intelligence.nds import NDS
import pandas as pd

races = load_rp_merged_as_racecards('2026-06-18', pathlib.Path('data'))
yar_races = [r for r in races if 'yarmouth' in (r.get('course') or '').lower()]

for raw_race in yar_races:
    if '3.50' not in str(raw_race.get('off_time', '')):
        continue
    race = normalize_race(raw_race)
    preds = score_race_velo_prime(race)
    print('RACE 3:50 Yarmouth -', len(preds), 'runners')

    # NDS
    nds_engine = NDS()
    runners_df = pd.DataFrame([{
        'sp_decimal': float(p.get('sp_dec') or 10.0),
        'horse': p.get('horse', '?'),
        'date': '2026-06-18',
        'course': 'yarmouth',
        'num': i + 1
    } for i, p in enumerate(preds)])
    nds_results = nds_engine.analyze_race(runners_df, pd.DataFrame())
    print('\nNDS results:')
    for nr in nds_results:
        print('  %-18s narrative=%-15s nds=%.3f fade=%s' % (
            nr.horse_name[:18], nr.narrative_type.value, nr.nds_score, nr.is_fade_opportunity))

    # Chains
    chain_result = asyncio.run(run_chains_parallel(race, race.get('runners', [])))
    pace = chain_result.get('pace', {}).get('signals', {}).get('race_shape', {}).get('shape', '?')
    narr = chain_result.get('narrative', {}).get('signals', {}).get('primary_narrative', {}).get('narrative_type', '?')
    mkt = chain_result.get('market', {}).get('status', '?')
    print('\nChains: pace_shape=%s narrative=%s market=%s' % (pace, narr, mkt))

    print('\nTop 4 predictions:')
    for p in sorted(preds, key=lambda x: x.get('velo_prime_prob', 0), reverse=True)[:4]:
        name = p.get('horse', '?')
        vp = p.get('velo_prime_prob', 0)
        sp = p.get('sp_dec', 0)
        print('  %-20s vp=%.3f sp_dec=%.2f' % (name[:20], vp, sp))
