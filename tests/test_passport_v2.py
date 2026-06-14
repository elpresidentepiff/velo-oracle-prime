import json
import pytest
from datetime import date, timedelta
from pathlib import Path
from new_build_velo.horse_passport import HorsePassport, HorsePassportBuilder
from new_build_velo.passport_lookup import lookup_passport_features, batch_lookup

@pytest.fixture
def sample_runs():
    return [
        {"horse_name": "Test Horse", "horse_rp_uid": 12345, "race_date": "2026-05-20", "position": 1, "beaten_margin": 0, "sp_raw": "2/1", "distance": "7f", "course_name": "Ascot"},
        {"horse_name": "Test Horse", "horse_rp_uid": 12345, "race_date": "2026-05-10", "position": 2, "beaten_margin": 1, "sp_raw": "4/1", "distance": "7f", "course_name": "Ascot"},
        {"horse_name": "Test Horse", "horse_rp_uid": 12345, "race_date": "2026-05-01", "position": 1, "beaten_margin": 0, "sp_raw": "3/1", "distance": "7f", "course_name": "Newmarket"},
        {"horse_name": "Test Horse", "horse_rp_uid": 12345, "race_date": "2026-04-15", "position": 4, "beaten_margin": 5, "sp_raw": "10/1", "distance": "8f", "course_name": "York"},
    ]

def test_t1_v2_fields_exist():
    """T1. V2 fields exist on rebuilt passport"""
    path = Path("data/new_build/passports/horse_passports_v1.jsonl")
    if not path.exists():
        pytest.skip("Passport bank not built")
    with open(path, "r") as f:
        p = json.loads(f.readline())
        assert "win_rate_last3" in p
        assert "last_run_date" in p
        assert "beaten_margin_slope" in p
        assert "runs_in_last_90d" in p

def test_t2_dynamic_days_since():
    """T2. Dynamic days_since: build a passport and check lookup"""
    builder = HorsePassportBuilder()
    runs = [{"horse_name": "Dynamic", "horse_rp_uid": 999, "race_date": "2026-05-01", "position": 1}]
    # We can't easily inject this into the lookup module's index without writing to file,
    # so we'll test the logic directly in the lookup function if we mock the index.
    import new_build_velo.passport_lookup as pl
    p_data = builder.build(runs)
    pl._by_uid[999] = json.loads(json.dumps(p_data.__dict__)) # Mock index
    
    scoring_date = date(2026, 5, 15)
    feats = pl.lookup_passport_features(999, "Dynamic", as_of_date=scoring_date)
    assert feats["pp_days_since_last"] == 14

def test_t3_null_features_unknown():
    """T3. Null features for unknown horse"""
    feats = lookup_passport_features(horse_rp_uid=888888888, horse_name="NoSuchHorse")
    # 11 champion keys + V2 keys
    keys = ["pp_career_runs", "pp_win_rate", "pp_place_rate", "pp_days_since_last", 
            "pp_layoff", "pp_avg_sp_last5", "pp_jockey_continuity", "pp_course_seen", 
            "pp_or_change_3", "pp_class_moved_up", "pp_class_moved_down"]
    for k in keys:
        assert feats[k] is None

def test_t4_pp_layoff_encoding():
    """T4. pp_layoff encodes correctly"""
    import new_build_velo.passport_lookup as pl
    # ACTIVE (0-29 days)
    pl._by_uid[101] = {"last_run_date": "2026-05-25", "career_runs": 1}
    f0 = pl.lookup_passport_features(101, None, as_of_date=date(2026, 5, 30))
    assert f0["pp_layoff"] == 0
    
    # FRESH_30 (30-59 days)
    pl._by_uid[102] = {"last_run_date": "2026-04-20", "career_runs": 1}
    f1 = pl.lookup_passport_features(102, None, as_of_date=date(2026, 5, 30))
    assert f1["pp_layoff"] == 1

def test_t5_batch_lookup_coverage():
    """T5. batch_lookup returns coverage"""
    import new_build_velo.passport_lookup as pl
    pl._by_uid[201] = {"career_runs": 5}
    pl._by_uid[202] = {"career_runs": 5}
    pl._by_uid[203] = {"career_runs": 5}
    
    runners = [
        {"horse_rp_uid": 201, "horse_name": "H1"},
        {"horse_rp_uid": 202, "horse_name": "H2"},
        {"horse_rp_uid": 203, "horse_name": "H3"},
        {"horse_rp_uid": 204, "horse_name": "M1"},
        {"horse_rp_uid": 205, "horse_name": "M2"},
    ]
    _, summary = batch_lookup(runners)
    assert summary["passport_hits"] == 3
    assert summary["passport_misses"] == 2
    assert summary["coverage_pct"] == 60.0

def test_t6_no_rpr_keys():
    """T6. No RPR keys in output"""
    feats = lookup_passport_features(12345, "Any")
    for k in feats.keys():
        assert "rpr" not in k.lower()

def test_t7_no_sp_keys():
    """T7. No SP keys in output (except allowed historical averages)"""
    feats = lookup_passport_features(12345, "Any")
    for k in feats.keys():
        if k == "pp_avg_sp_last5" or k == "pp_avg_sp_last3":
            continue
        assert "sp_dec" not in k.lower()
        assert "odds" not in k.lower()

def test_t8_win_rate_last3():
    """T8. win_rate_last3 uses only last 3 runs"""
    builder = HorsePassportBuilder()
    runs = [
        {"race_date": "2026-05-20", "position": 1},
        {"race_date": "2026-05-15", "position": 1},
        {"race_date": "2026-05-10", "position": 1},
    ] + [{"race_date": f"2026-04-{i:02d}", "position": 5} for i in range(1, 8)]
    
    p = builder.build(runs)
    assert p.career_runs == 10
    assert p.win_rate == 0.3
    assert p.win_rate_last3 == 1.0

def test_t9_beaten_margin_slope():
    """T9. beaten_margin_slope direction (negative = improving)"""
    builder = HorsePassportBuilder()
    # Improving: index 0 is most recent and smallest margin
    runs = [
        {"race_date": "2026-05-20", "beaten_margin": 1},
        {"race_date": "2026-05-15", "beaten_margin": 2},
        {"race_date": "2026-05-10", "beaten_margin": 3},
        {"race_date": "2026-05-05", "beaten_margin": 4},
        {"race_date": "2026-05-01", "beaten_margin": 5},
        {"race_date": "2026-04-25", "beaten_margin": 6},
    ]
    p = builder.build(runs)
    # (1 - 6) / 6 = -0.833
    assert p.beaten_margin_slope < 0

def test_t10_name_fallback():
    """T10. Passport name fallback"""
    import new_build_velo.passport_lookup as pl
    pl._by_name["sea of charm"] = {"career_runs": 42}
    feats = pl.lookup_passport_features(horse_rp_uid=None, horse_name="Sea Of Charm")
    assert feats["pp_career_runs"] == 42
