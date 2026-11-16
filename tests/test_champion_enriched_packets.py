"""Safety and identity contracts for the non-scoring enriched Champion Intent packets."""
from scripts.ops.build_champion_enriched_packets import make_packets, FF_FIELDS

def test_factual_join_does_not_consume_provider_predictions():
    champ = [{"race_id": "123", "horse": "L' Étoile", "rp_uid": "9",
              "champion_intent_shadow_prob": "0.1", "rank_in_race": "1"}]
    ff = {"races": [{"race_id": "123", "runners": [{
        "horse_name": "L Etoile", "ff_quality_score": 0.8,
        "ff_training_eligible": 1.0, "provider_prediction": "WIN",
        "actual_finish": 1}]}]}
    rows, counts = make_packets(champ, ff)
    assert counts == {"MATCHED": 1}
    row = rows[0]
    assert row["feature_values"]["ff_quality_score"] == 0.8
    assert row["feature_values"]["ff_speedmap_present_missing"] == 1
    assert row["eligible_for_fit"] is False
    assert row["ineligibility_reason"] == "PRE_OFF_PROVENANCE_UNVERIFIED"
    assert row["production_influence"] is False
    assert row["provider_predictions_consumed"] is False
    assert "provider_prediction" not in str(row)
    assert "actual_finish" not in str(row)
    assert set(row["feature_values"]) == set(FF_FIELDS) | {x + "_missing" for x in FF_FIELDS}

def test_ambiguous_and_missing_names_fail_closed():
    champ = [{"race_id": "123", "horse": "A"}, {"race_id": "123", "horse": "B"}]
    ff = {"races": [{"race_id": "123", "runners": [
        {"horse_name": "A", "ff_training_eligible": 1.0},
        {"horse_name": "A", "ff_training_eligible": 1.0}]}]}
    rows, counts = make_packets(champ, ff, pre_off_verified=True)
    assert counts == {"AMBIGUOUS": 1, "MISSING": 1}
    assert all(not row["eligible_for_fit"] for row in rows)
    assert all(all(row["feature_values"][field] is None for field in FF_FIELDS) for row in rows)

def test_race_id_is_mandatory_for_identity():
    rows, counts = make_packets(
        [{"race_id": "777", "horse": "Same Name"}],
        {"races": [{"race_id": "778", "runners": [{"horse_name": "Same Name"}]}]})
    assert counts == {"MISSING": 1}
    assert rows[0]["eligible_for_fit"] is False
