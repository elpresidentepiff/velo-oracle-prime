"""
VELO E2E Prediction Test — Phase 3 verification
Run from repo root:  python scripts/test_e2e_prediction.py
"""
import sys
sys.path.insert(0, '.')

from app.services.model_manager import get_model_manager
from app.services.v17_feature_extractor import V17FeatureExtractor
from app.services.feature_engineering import extract_features

# Sample runner and race
runner = {
    'horse_id': 'hrs_28707063',
    'horse': 'Hellfire Princess',
    'sp': 6.0,
    'odds': 6.0,
    'or': 100,
    'rpr': 99,
    'ts': 92,
    'wgt': '12-0',
    'draw': 0,
    'age': 9,
    'jockey': 'Benjamin Macey',
    'sp_rank': 3,
    'is_fav': 0,
}
race = {
    'course': 'Ffos Las',
    'going': 'Soft',
    'dist': '2m4f',
    'distance_f': 20.0,
    'class': 'Class 5',
    'ran': 6,
}
race_context = {
    'course': 'Ffos Las',
    'going': 'Soft',
    'dist_f': 20.0,
    'or_num': 100,
    'sp_dec': 6.0,
    'jockey': 'Benjamin Macey',
    'is_fav': 0,
}

mm = get_model_manager()
extractor = V17FeatureExtractor()

base_features = extract_features(runner, race, historical=None)
doctrine = extractor.extract('hrs_28707063', race_context)
base_features.update(doctrine)

prob = mm.predict_sqpe(base_features, runner=runner, race=race)
print(f'SQPE v17 prob for Hellfire Princess: {prob:.4f}')
print(f'Model version: {mm.model_versions}')
print(f'Doctrine features present: {list(doctrine.keys())}')
assert 0 < prob < 1, f'Probability out of range: {prob}'
print('E2E TEST PASSED')
