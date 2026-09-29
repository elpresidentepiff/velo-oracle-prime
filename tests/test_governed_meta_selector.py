import copy
import json
from datetime import date, timedelta

import pytest

from scripts.research.governed_meta_selector import (
    _meta_hash,
    evaluate_policy_records,
    freeze_meta_policy,
    make_purged_rolling_splits,
    meta_build_feature_matrix,
    meta_cli_main,
    score_frozen_meta_policy,
    select_transparent_candidates,
    train_calibrated_meta_policy,
    write_immutable_meta_artifact,
)


def source_rows(days=9):
    rows = []
    start = date(2026, 9, 1)
    for offset in range(days):
        race_date = (start + timedelta(days=offset)).isoformat()
        daily = []
        for idx, (horse, prod, captain, odds) in enumerate((("h1", .55, .35, 2.5), ("h2", .3, .5, 4.0), ("h3", .15, .15, 7.0)), 1):
            daily.append({
                "race_date": race_date, "race_id": f"r{offset}", "horse_id": horse,
                "snapshot_created_at": f"{race_date}T10:00:00+00:00",
                "off_ts": f"{race_date}T14:00:00+00:00", "captured_odds_dec": odds,
                "odds_capture_ts": f"{race_date}T09:59:00+00:00",
                "model_probabilities": {"PRODUCTION": prod, "CAPTAIN": captain},
                "model_ranks": {"PRODUCTION": idx, "CAPTAIN": 2 if idx == 1 else (1 if idx == 2 else 3)},
                "race_type": "FLAT", "field_size": 3, "course": "TEST", "going": "GOOD",
                "race_class": 3, "pace": .4, "shape": .6, "campaign_state": .2,
                "trainer_context": .3, "jockey_context": .4,
            })
        packet = {"race_date": race_date, "feature_payloads": daily, "paper_sim_only": True}
        packet_hash = _meta_hash(packet)
        rows.extend({**payload, "packet_hash": packet_hash, "source_packet": packet} for payload in daily)
    return rows


def truths(days=9):
    rows = []
    start = date(2026, 9, 1)
    for offset in range(days):
        race_date = (start + timedelta(days=offset)).isoformat()
        winner = "h2" if offset % 3 else "h1"
        for horse in ("h1", "h2", "h3"):
            rows.append({"race_date": race_date, "race_id": f"r{offset}", "horse_id": horse,
                         "settlement_status": "SETTLED", "official_evaluation_eligible": True,
                         "result_source_complete": True, "win": horse == winner})
    return rows


def repack_source_rows(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["race_date"], []).append(row)
    for race_date, field in grouped.items():
        payloads = [{key: value for key, value in row.items() if key not in {"packet_hash", "source_packet"}} for row in field]
        packet = {"race_date": race_date, "feature_payloads": payloads, "paper_sim_only": True}
        packet_hash = _meta_hash(packet)
        for row in field:
            row["source_packet"] = packet
            row["packet_hash"] = packet_hash
    return rows


@pytest.mark.parametrize("field", ["result", "sp_dec", "post_off_price", "future_form", "finish_position"])
def test_rejects_result_sp_postoff_and_future_features(field):
    rows = source_rows(1)
    rows[0][field] = 1
    with pytest.raises(ValueError, match="FORBIDDEN_FEATURE_FIELD"):
        meta_build_feature_matrix(rows)


def test_requires_strict_preoff_feature_and_price_times():
    rows = source_rows(1)
    rows[0]["snapshot_created_at"] = rows[0]["off_ts"]
    with pytest.raises(ValueError, match="STRICTLY_PRE_OFF"):
        meta_build_feature_matrix(rows)
    rows = source_rows(1)
    rows[0]["odds_capture_ts"] = rows[0]["off_ts"]
    with pytest.raises(ValueError, match="CAPTURE_PRICE"):
        meta_build_feature_matrix(rows)


def test_matrix_derives_only_prerace_features():
    matrix = meta_build_feature_matrix(source_rows(1))
    assert matrix[0]["market_probability"] == pytest.approx(.4)
    assert matrix[0]["disagreement_range"] == pytest.approx(.2)
    assert not any("result" in key or key.startswith("sp") for key in matrix[0])


def test_purged_rolling_split_has_strict_date_separation():
    matrix = meta_build_feature_matrix(source_rows())
    splits = make_purged_rolling_splits(matrix, min_train_days=3, tune_days=1, score_days=1, purge_days=1)
    assert splits
    for split in splits:
        assert max(split["train_dates"]) < min(split["tune_dates"]) < min(split["score_dates"])
        assert split["train_tune_purge_dates"] and split["tune_score_purge_dates"]


def test_transparent_policies_include_all_baselines_and_abstain():
    matrix = meta_build_feature_matrix(source_rows(1))
    records = select_transparent_candidates(matrix, captain_gate={"min_odds": 3, "max_odds": 5})
    assert {row["policy"] for row in records} == {"PRODUCTION", "CAPTAIN", "MARKET_FAVOURITE", "AGREEMENT", "GATED_CAPTAIN", "ABSTAIN"}
    assert next(row for row in records if row["policy"] == "ABSTAIN")["abstained"]
    assert next(row for row in records if row["policy"] == "GATED_CAPTAIN")["selection_horse_id"] == "h2"


def test_policy_freeze_and_untouched_forward_scoring():
    matrix = meta_build_feature_matrix(source_rows())
    split = make_purged_rolling_splits(matrix, min_train_days=3, tune_days=1, score_days=1, purge_days=1)[0]
    policy = train_calibrated_meta_policy(matrix, truths(), split)
    assert freeze_meta_policy(policy)["policy_hash"] == policy["policy_hash"]
    assert policy["calibration"]["method"] == "PLATT_ON_PURGED_TUNE_DATES"
    assert policy["training_feature_hash"] and policy["training_truth_hash"] and policy["source_packet_hashes"]
    forward = [row for row in matrix if row["race_date"] in split["score_dates"]]
    scored = score_frozen_meta_policy(policy, forward, split["score_dates"])
    assert scored and all(row["policy_hash"] == policy["policy_hash"] for row in scored)
    with pytest.raises(ValueError, match="STRICTLY_AFTER_FREEZE"):
        score_frozen_meta_policy(policy, [row for row in matrix if row["race_date"] in split["tune_dates"]], split["tune_dates"])
    forged = copy.deepcopy(policy)
    forged["threshold"] = .99
    with pytest.raises(ValueError, match="POLICY_FREEZE_INVALID"):
        freeze_meta_policy(forged)
    incomplete = truths()
    incomplete[0]["result_source_complete"] = False
    with pytest.raises(ValueError, match="TRUTH_NOT_COMPLETE_AND_ELIGIBLE"):
        train_calibrated_meta_policy(matrix, incomplete, split)


def test_meta_policy_can_abstain():
    matrix = meta_build_feature_matrix(source_rows())
    split = make_purged_rolling_splits(matrix, min_train_days=3, tune_days=1, score_days=1, purge_days=1)[0]
    policy = train_calibrated_meta_policy(matrix, truths(), split)
    body = {key: value for key, value in policy.items() if key != "policy_hash"}
    body["threshold"] = 1.0
    policy = {**body, "policy_hash": _meta_hash(body)}
    forward = [row for row in matrix if row["race_date"] in split["score_dates"]]
    assert all(row["abstained"] for row in score_frozen_meta_policy(policy, forward, split["score_dates"]))


def test_evaluation_reports_uncertainty_drawdown_and_ex_big_winner():
    matrix = meta_build_feature_matrix(source_rows(4))
    records = [row for row in select_transparent_candidates(matrix) if row["policy"] == "CAPTAIN"]
    metrics = evaluate_policy_records(records, truths(4), bootstrap_samples=50)["CAPTAIN"]["metrics"]
    assert metrics["days"] == 4 and metrics["bootstrap"]["days"] == 4
    assert metrics["bootstrap"]["profit_95pct"] is not None
    assert "max_drawdown" in metrics and "profit_ex_largest_winner" in metrics
    no_price_source = source_rows(4)
    no_price_source[1]["captured_odds_dec"] = None
    no_price_source[1]["odds_capture_ts"] = None
    repack_source_rows(no_price_source)
    no_price_records = [row for row in select_transparent_candidates(meta_build_feature_matrix(no_price_source)) if row["policy"] == "CAPTAIN"]
    no_price_metrics = evaluate_policy_records(no_price_records, truths(4), bootstrap_samples=0)["CAPTAIN"]["metrics"]
    assert no_price_metrics["captured_price_settled"] == metrics["settled"] - 1


def test_immutable_artifact_conflict(tmp_path):
    body = {"schema_version": "x", "paper_sim_only": True}
    payload = {**body, "artifact_hash": _meta_hash(body)}
    assert write_immutable_meta_artifact(payload, tmp_path)[0] == "CREATED"
    assert write_immutable_meta_artifact(payload, tmp_path)[0] == "VALIDATED_IDENTICAL"
    forged = dict(payload)
    forged["paper_sim_only"] = False
    with pytest.raises(ValueError, match="ARTIFACT_HASH_MISMATCH"):
        write_immutable_meta_artifact(forged, tmp_path)


def test_cli_requires_explicit_invocation_and_writes_governed_artifact(tmp_path, capsys):
    features = tmp_path / "features.json"
    truth = tmp_path / "truth.json"
    output = tmp_path / "artifacts"
    features.write_text(json.dumps(source_rows()), encoding="utf-8")
    truth.write_text(json.dumps(truths()), encoding="utf-8")
    meta_cli_main([
        "--features", str(features), "--truth", str(truth),
        "--output-root", str(output), "--bootstrap-samples", "5",
    ])
    response = json.loads(capsys.readouterr().out)
    artifact = json.loads((output / f"{response['artifact_hash']}.json").read_text(encoding="utf-8"))
    assert artifact["safety"] == {"paper_sim_only": True, "production_changed": False}
    assert artifact["evidence_class"] == "PURGED_OOS_BACKTEST" and artifact["fresh_forward"] is False
    assert artifact["runs"] and artifact["runs"][0]["oos_score_dates"]
    assert "transparent_evaluation" in artifact["runs"][0] and "meta_evaluation" in artifact["runs"][0]


def test_truth_coverage_duplicates_and_boolean_fail_closed():
    matrix = meta_build_feature_matrix(source_rows())
    split = make_purged_rolling_splits(matrix, min_train_days=3, tune_days=1, score_days=1, purge_days=1)[0]
    governed = set(split["train_dates"] + split["tune_dates"])
    base = [row for row in truths() if row["race_date"] in governed]
    with pytest.raises(ValueError, match="DUPLICATE"):
        train_calibrated_meta_policy(matrix, base + [copy.deepcopy(base[0])], split)
    with pytest.raises(ValueError, match="COVERAGE_MISMATCH"):
        train_calibrated_meta_policy(matrix, base[:-1], split)
    extra = copy.deepcopy(base)
    extra.append({**base[0], "horse_id": "extra"})
    with pytest.raises(ValueError, match="COVERAGE_MISMATCH"):
        train_calibrated_meta_policy(matrix, extra, split)
    bad_boolean = copy.deepcopy(base)
    bad_boolean[0]["win"] = "false"
    with pytest.raises(ValueError, match="OUTCOME_NOT_CANONICAL"):
        train_calibrated_meta_policy(matrix, bad_boolean, split)


def test_empirical_correlation_pruning_train_only_order_invariant():
    rows = source_rows()
    for row in rows:
        row["model_probabilities"]["CAPTAIN"] = row["model_probabilities"]["PRODUCTION"]
        row["model_ranks"]["CAPTAIN"] = row["model_ranks"]["PRODUCTION"]
    repack_source_rows(rows)
    matrix = meta_build_feature_matrix(rows)
    split = make_purged_rolling_splits(matrix, min_train_days=3, tune_days=1, score_days=1, purge_days=1)[0]
    first = train_calibrated_meta_policy(matrix, truths(), split)
    second = train_calibrated_meta_policy(list(reversed(matrix)), list(reversed(truths())), split)
    control = first["train_only_correlation_control"]
    assert "prob:PRODUCTION" in control["pruned_features"]
    assert control["representative_by_feature"]["prob:PRODUCTION"] == control["representative_by_feature"]["prob:CAPTAIN"]
    assert first["policy_hash"] == second["policy_hash"]


def test_date_and_timestamp_chain_fail_closed():
    rows = source_rows(1)
    rows[0]["race_date"] = "2026-9-1"
    with pytest.raises(ValueError, match="STRICT_ISO"):
        meta_build_feature_matrix(rows)
    rows = source_rows(1)
    rows[0]["off_ts"] = "2026-09-02T14:00:00+00:00"
    with pytest.raises(ValueError, match="STRICTLY_PRE_OFF"):
        meta_build_feature_matrix(rows)
    rows = source_rows(1)
    rows[0]["odds_capture_ts"] = "2026-09-01T10:01:00+00:00"
    with pytest.raises(ValueError, match="CAPTURE_PRICE"):
        meta_build_feature_matrix(rows)
    rows = source_rows(1)
    rows[0]["snapshot_created_at"] = "2026-09-01T10:00:00"
    with pytest.raises(ValueError, match="STRICTLY_PRE_OFF"):
        meta_build_feature_matrix(rows)


def test_selection_price_and_provenance_tamper_rejected():
    matrix = meta_build_feature_matrix(source_rows(1))
    records = [row for row in select_transparent_candidates(matrix) if row["policy"] == "CAPTAIN"]
    tampered = copy.deepcopy(records)
    tampered[0]["captured_odds_dec"] = 1000.0
    with pytest.raises(ValueError, match="PROVENANCE_TAMPERED"):
        evaluate_policy_records(tampered, truths(1), bootstrap_samples=0)
    tampered = copy.deepcopy(records)
    tampered[0]["source_feature_row"]["captured_odds_dec"] = 1000.0
    with pytest.raises(ValueError, match="FEATURE_HASH_MISMATCH"):
        evaluate_policy_records(tampered, truths(1), bootstrap_samples=0)
    tampered_row = tampered[0]["source_feature_row"]
    tampered_row["source_feature_hash"] = _meta_hash({
        key: value for key, value in tampered_row.items() if key != "source_feature_hash"
    })
    tampered[0]["source_feature_hash"] = tampered_row["source_feature_hash"]
    tampered[0]["captured_odds_dec"] = 1000.0
    with pytest.raises(ValueError, match="PACKET_LINKAGE_INVALID"):
        evaluate_policy_records(tampered, truths(1), bootstrap_samples=0)


def test_model_schema_missingness_rejected():
    rows = source_rows(1)
    del rows[0]["model_probabilities"]["CAPTAIN"]
    repack_source_rows(rows)
    with pytest.raises(ValueError, match="MODEL_FEATURE_SCHEMA_INCONSISTENT"):
        meta_build_feature_matrix(rows)


def test_conditional_regions_are_predeclared_and_reported():
    matrix = meta_build_feature_matrix(source_rows(1))
    records = [row for row in select_transparent_candidates(matrix) if row["policy"] == "CAPTAIN"]
    report = evaluate_policy_records(records, truths(1), bootstrap_samples=0)["CAPTAIN"]
    assert "SMALL_FIELD" in report["conditional_regions"]
    assert report["conditional_regions"]["SMALL_FIELD"]["support_races"] == 1
    assert records[0]["regions"]


def test_tampered_competitor_rejected_before_decision():
    matrix = meta_build_feature_matrix(source_rows(1))
    record = copy.deepcopy(next(row for row in select_transparent_candidates(matrix) if row["policy"] == "PRODUCTION"))
    competitor = next(row for row in record["governed_field_rows"] if row["horse_id"] == "h2")
    competitor["model_probabilities"]["PRODUCTION"] = .99
    with pytest.raises(ValueError, match="FIELD_FEATURE_HASH_MISMATCH"):
        evaluate_policy_records([record], truths(1), bootstrap_samples=0)


def test_forced_abstention_with_stale_competitor_rejected():
    matrix = meta_build_feature_matrix(source_rows(1))
    record = copy.deepcopy(next(row for row in select_transparent_candidates(matrix) if row["policy"] == "ABSTAIN"))
    record["governed_field_rows"][1]["packet_hash"] = "0" * 64
    with pytest.raises(ValueError, match="FIELD_FEATURE_HASH_MISMATCH|FIELD_PACKET_HASH_MISMATCH|PACKET_OR_SNAPSHOT_CHIMERA"):
        evaluate_policy_records([record], truths(1), bootstrap_samples=0)


def test_arbitrary_authentic_horse_substitution_rejected():
    matrix = meta_build_feature_matrix(source_rows(1))
    record = copy.deepcopy(next(row for row in select_transparent_candidates(matrix) if row["policy"] == "CAPTAIN"))
    substitute = next(row for row in record["governed_field_rows"] if row["horse_id"] == "h1")
    record.update({
        "selection_horse_id": substitute["horse_id"], "captured_odds_dec": substitute["captured_odds_dec"],
        "odds_capture_ts": substitute["odds_capture_ts"], "snapshot_created_at": substitute["snapshot_created_at"],
        "off_ts": substitute["off_ts"], "packet_hash": substitute["packet_hash"],
        "source_feature_hash": substitute["source_feature_hash"], "source_feature_row": substitute,
    })
    with pytest.raises(ValueError, match="DECLARED_DECISION_DOES_NOT_REPRODUCE"):
        evaluate_policy_records([record], truths(1), bootstrap_samples=0)


def test_policy_label_and_config_tamper_rejected():
    matrix = meta_build_feature_matrix(source_rows(1))
    original = next(row for row in select_transparent_candidates(matrix) if row["policy"] == "PRODUCTION")
    relabelled = copy.deepcopy(original)
    relabelled["policy"] = "CAPTAIN"
    with pytest.raises(ValueError, match="POLICY_RELABELLED"):
        evaluate_policy_records([relabelled], truths(1), bootstrap_samples=0)
    reconfigured = copy.deepcopy(original)
    reconfigured["decision_contract"]["selector_config"]["production_model"] = "CAPTAIN"
    with pytest.raises(ValueError, match="DECISION_INPUT_HASH_MISMATCH"):
        evaluate_policy_records([reconfigured], truths(1), bootstrap_samples=0)
    full_matrix = meta_build_feature_matrix(source_rows())
    split = make_purged_rolling_splits(full_matrix, min_train_days=3, tune_days=1, score_days=1, purge_days=1)[0]
    frozen = train_calibrated_meta_policy(full_matrix, truths(), split)
    forward = [row for row in full_matrix if row["race_date"] in split["score_dates"]]
    meta_record = score_frozen_meta_policy(frozen, forward, split["score_dates"])[0]
    meta_record["decision_contract"]["frozen_policy"]["threshold"] = .999
    score_truth = [row for row in truths() if row["race_date"] in split["score_dates"]]
    with pytest.raises(ValueError, match="DECISION_INPUT_HASH_MISMATCH"):
        evaluate_policy_records([meta_record], score_truth, bootstrap_samples=0)


def test_transparent_full_field_omission_rejected():
    matrix = meta_build_feature_matrix(source_rows(1))
    record = copy.deepcopy(next(row for row in select_transparent_candidates(matrix) if row["policy"] == "PRODUCTION"))
    record["governed_field_rows"] = record["governed_field_rows"][:-1]
    with pytest.raises(ValueError, match="NOT_COMPLETE_PACKET_FIELD"):
        evaluate_policy_records([record], truths(1), bootstrap_samples=0)


def test_meta_full_field_omission_rejected():
    matrix = meta_build_feature_matrix(source_rows())
    split = make_purged_rolling_splits(matrix, min_train_days=3, tune_days=1, score_days=1, purge_days=1)[0]
    policy = train_calibrated_meta_policy(matrix, truths(), split)
    forward = [row for row in matrix if row["race_date"] in split["score_dates"]]
    record = score_frozen_meta_policy(policy, forward, split["score_dates"])[0]
    record["governed_field_rows"] = record["governed_field_rows"][:-1]
    score_truth = [row for row in truths() if row["race_date"] in split["score_dates"]]
    with pytest.raises(ValueError, match="NOT_COMPLETE_PACKET_FIELD"):
        evaluate_policy_records([record], score_truth, bootstrap_samples=0)


def test_mixed_packet_snapshot_chimera_rejected():
    original = meta_build_feature_matrix(source_rows(1))
    alternate_source = source_rows(1)
    for row in alternate_source:
        row["snapshot_created_at"] = "2026-09-01T09:00:00+00:00"
        row["odds_capture_ts"] = "2026-09-01T08:59:00+00:00"
    repack_source_rows(alternate_source)
    alternate = meta_build_feature_matrix(alternate_source)
    record = copy.deepcopy(next(row for row in select_transparent_candidates(original) if row["policy"] == "PRODUCTION"))
    record["governed_field_rows"][2] = alternate[2]
    with pytest.raises(ValueError, match="PACKET_OR_SNAPSHOT_CHIMERA"):
        evaluate_policy_records([record], truths(1), bootstrap_samples=0)


def test_other_race_packet_injection_rejected():
    rows = source_rows(1)
    injected = []
    for row in rows:
        payload = {key: copy.deepcopy(value) for key, value in row.items() if key not in {"packet_hash", "source_packet"}}
        payload["race_id"] = "other-race"
        injected.append(payload)
    combined_payloads = [
        {key: copy.deepcopy(value) for key, value in row.items() if key not in {"packet_hash", "source_packet"}}
        for row in rows
    ] + injected
    packet = {"race_date": "2026-09-01", "feature_payloads": combined_payloads, "paper_sim_only": True}
    packet_hash = _meta_hash(packet)
    combined = [{**payload, "packet_hash": packet_hash, "source_packet": packet} for payload in combined_payloads]
    matrix = meta_build_feature_matrix(combined)
    with pytest.raises(ValueError, match="PACKET_CONTAINS_OTHER_RACE"):
        select_transparent_candidates(matrix)
