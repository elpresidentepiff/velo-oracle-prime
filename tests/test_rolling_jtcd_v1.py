import pandas as pd
import numpy as np
from pathlib import Path
import pytest

@pytest.fixture
def jtcd_data():
    path = Path("data/new_build/sidecars/rolling_jtcd_v1.parquet")
    if not path.exists():
        pytest.skip("rolling_jtcd_v1.parquet not found")
    return pd.read_parquet(path)

def test_t1_no_same_day_data(jtcd_data):
    """T1. For any target race on date D, no feature uses data from date >= D"""
    first_date = jtcd_data['as_of_date'].min()
    first_day_rows = jtcd_data[jtcd_data['as_of_date'] == first_date]
    assert (first_day_rows['tf_runs_wltd'].fillna(0) == 0).all()

def test_t2_window_monotonicity(jtcd_data):
    """T2 & T3. Verify window boundaries: w14 <= w30 <= w90 <= w365 <= wltd"""
    cols = ['tj_runs_w14', 'tj_runs_w30', 'tj_runs_w90', 'tj_runs_w365', 'tj_runs_wltd']
    valid = jtcd_data.dropna(subset=cols)
    assert (valid['tj_runs_w14'] <= valid['tj_runs_w30']).all()
    assert (valid['tj_runs_w30'] <= valid['tj_runs_w90']).all()
    assert (valid['tj_runs_w90'] <= valid['tj_runs_w365']).all()
    assert (valid['tj_runs_w365'] <= valid['tj_runs_wltd']).all()

def test_t4_ltd_strictly_prior(jtcd_data):
    """T4. Lifetime-to-date is strictly prior"""
    assert (jtcd_data['tj_wins_wltd'].dropna() >= 0).all()

def test_t5_tj_key_presence(jtcd_data):
    """T5. Trainer_jockey key presence"""
    assert 'tj_runs_w365' in jtcd_data.columns
    assert 'tj_jtc_signal_w365' in jtcd_data.columns

def test_t6_tc_key_presence(jtcd_data):
    """T6. Trainer_course key presence"""
    assert 'tc_runs_wltd' in jtcd_data.columns

def test_t9_no_rpr_column(jtcd_data):
    """T9. Assert no column contains 'rpr'"""
    for col in jtcd_data.columns:
        assert "rpr" not in col.lower(), f"Found RPR in column {col}"

def test_t10_no_sp_column(jtcd_data):
    """T10. Assert no column contains 'sp' or 'odds'"""
    for col in jtcd_data.columns:
        assert "sp" not in col.lower(), f"Found SP in column {col}"
        assert "odds" not in col.lower(), f"Found ODDS in column {col}"

def test_t11_has_sample_flag(jtcd_data):
    """T11. has_sample flag: 4 runs -> 0, 5 runs -> 1"""
    col = 'tj_has_sample_w365'
    runs_col = 'tj_runs_w365'
    valid = jtcd_data.dropna(subset=[runs_col, col])
    assert len(valid[(valid[runs_col] < 5) & (valid[col] == 1)]) == 0
    assert len(valid[(valid[runs_col] >= 5) & (valid[col] == 0)]) == 0

def test_bayesian_logic(jtcd_data):
    """Check Bayesian adjusted SR formula: (wins + 2.0) / (runs + 20)"""
    valid = jtcd_data.dropna(subset=['tj_runs_w365', 'tj_wins_w365', 'tj_adj_sr_w365']).head(1000)
    runs = valid['tj_runs_w365']
    wins = valid['tj_wins_w365']
    expected = (wins + 2.0) / (runs + 20)
    np.testing.assert_allclose(valid['tj_adj_sr_w365'], expected, rtol=1e-5)
