import inspect
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.research.forward_model_lab as lab
from scripts.research.forward_model_lab import (
    build_forward_model_packet,
    day_block_bootstrap,
    evaluate_forward_packets,
    write_immutable_evaluation,
    write_immutable_packet,
)


def field(date="2026-09-29", rid="r1", created="2026-09-29T12:00:00+01:00", off="2.00", run="run1", prices=True):
    values = [("h1", "Alpha", 0.5, 0.2, 2.0), ("h2", "Beta", 0.3, 0.6, 4.0), ("h3", "Gamma", 0.2, 0.2, 8.0)]
    return [
        {
            "run_id": run,
            "created_at": created,
            "race_date": date,
            "race_id": rid,
            "course": "Ayr",
            "off_time": off,
            "horse_id": h,
            "horse": n,
            "main_prob": p,
            "captain_prob": c,
            **({"captured_odds_dec": o, "odds_capture_ts": created, "price_source": "SNAP"} if prices else {}),
        }
        for h, n, p, c, o in values
    ]


def source(tmp_path, rows, name="source.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def build_at(now, **kwargs):
    with patch.object(lab, "_utc_now", return_value=datetime.fromisoformat(now)):
        return build_forward_model_packet(**kwargs)


def packet(tmp_path, *, rows=None, now="2026-09-29T12:05:00+01:00", date="2026-09-29", versions=None):
    rows = rows or field(date=date)
    path = source(tmp_path, rows, f"source_{date}.jsonl")
    return build_at(
        now,
        race_date=date,
        selected_fields={rows[0]["race_id"]: rows},
        model_fields={"MAIN_VELO_PRIME": "main_prob", "CAPTAIN": "captain_prob"},
        model_versions=versions or {"MAIN_VELO_PRIME": "g1", "CAPTAIN": "c1"},
        source_paths=[path],
        commit="abc",
    )


def captain_packet(tmp_path, version="c2"):
    rows = field()
    path = source(tmp_path, rows, "captain_source.jsonl")
    return build_at(
        "2026-09-29T12:05:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": rows},
        model_fields={"CAPTAIN": "captain_prob"},
        model_versions={"CAPTAIN": version},
        source_paths=[path],
        commit="abc",
    )


def truth(date="2026-09-29", rid="r1", complete=True, prices=(2.2, 3.5, 10.0)):
    return [
        {
            "date": date,
            "race_id": rid,
            "horse_id": h,
            "result_source_complete": complete,
            "result_source_hash": f"hash-{date}",
            "subject_outcome_status": "FINISHED",
            "settlement_status": "SETTLED",
            "dashboard_metrics_eligible": True,
            "official_evaluation_eligible": True,
            "win": h == "h2",
            "frame": h in {"h1", "h2"},
            "settled_sp_dec": sp,
        }
        for h, sp in zip(("h1", "h2", "h3"), prices, strict=True)
    ]


def cohort(out, model="CAPTAIN", version="c1", kind="GENUINELY_FORWARD"):
    return out["evidence"][kind][model][version]


def test_forward_is_derived_and_has_source_hashes(tmp_path):
    p = packet(tmp_path)
    assert p["evidence_class"] == "GENUINELY_FORWARD"
    assert p["source_files"][0]["sha256"]
    assert p["selected_source_hash"]
    assert p["packet_identity_hash"]


def test_historical_and_same_day_late_are_derived_not_asserted(tmp_path):
    assert packet(tmp_path, now="2026-09-30T10:00:00+01:00")["evidence_class"] == "RETROSPECTIVE"
    assert packet(tmp_path, now="2026-09-29T15:00:00+01:00")["evidence_class"] == "BACKFILLED"


def test_source_bytes_and_mutation_are_proven(tmp_path):
    rows = field()
    path = source(tmp_path, rows)
    with pytest.raises(ValueError, match="SELECTED_ROW_NOT_IN_SOURCE_BYTES"):
        build_at(
            "2026-09-29T12:05:00+01:00",
            race_date="2026-09-29",
            selected_fields={"r1": [{**r, "horse": "Forged"} for r in rows]},
            model_fields={"M": "main_prob"},
            source_paths=[path],
        )
    first = packet(tmp_path)
    rows[0]["horse"] = "Changed"
    second = packet(tmp_path, rows=rows)
    assert first["source_files"][0]["sha256"] != second["source_files"][0]["sha256"]


def test_selected_run_must_be_latest_preoff_in_source_bytes(tmp_path):
    early = field(run="early", created="2026-09-29T11:00:00+01:00")
    latest = field(run="latest", created="2026-09-29T12:00:00+01:00")
    path = source(tmp_path, early + latest)
    with pytest.raises(ValueError, match="SELECTED_RUN_NOT_LATEST_COMPLETE_PRE_OFF"):
        build_at(
            "2026-09-29T12:05:00+01:00",
            race_date="2026-09-29",
            selected_fields={"r1": early},
            model_fields={"M": "main_prob"},
            source_paths=[path],
        )


def test_later_partial_contaminated_and_live_changed_runs_do_not_displace_complete(tmp_path):
    good = field(run="good", created="2026-09-29T11:00:00+01:00")
    partial = field(run="partial", created="2026-09-29T12:00:00+01:00")[:2]
    contaminated = field(run="2026_32cc27f9_bad", created="2026-09-29T12:30:00+01:00")
    live = field(run="live", created="2026-09-29T12:45:00+01:00")
    for row in live:
        row["live_scoring_changed"] = True
    path = source(tmp_path, good + partial + contaminated + live)
    p = build_at(
        "2026-09-29T13:00:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": good},
        model_fields={"M": "main_prob"},
        source_paths=[path],
    )
    assert p["selected_source_evidence"]["r1"]["run_id"] == "good"


def test_contradictory_declared_field_sizes_rejected(tmp_path):
    rows = field()
    for row in rows:
        row["field_size"] = 3
    rows[0]["field_size"] = 4
    path = source(tmp_path, rows)
    with pytest.raises(ValueError, match="CONTRADICTORY_FIELD_SIZE_DECLARATIONS"):
        build_at(
            "2026-09-29T12:05:00+01:00",
            race_date="2026-09-29",
            selected_fields={"r1": rows},
            model_fields={"M": "main_prob"},
            source_paths=[path],
        )


def test_selected_subset_of_authoritative_field_rejected(tmp_path):
    rows = field()
    path = source(tmp_path, rows)
    with pytest.raises(ValueError, match="SELECTED_FIELD_NOT_EXACT_AUTHORITATIVE_RUN"):
        build_at(
            "2026-09-29T12:05:00+01:00",
            race_date="2026-09-29",
            selected_fields={"r1": rows[:2]},
            model_fields={"M": "main_prob"},
            source_paths=[path],
        )


@pytest.mark.parametrize(
    "key,value",
    [
        ("run_id", "other"),
        ("race_id", "r2"),
        ("off_time", "2.01"),
        ("created_at", "2026-09-29T12:01:00+01:00"),
        ("race_date", "2026-09-30"),
    ],
)
def test_mixed_source_rows_rejected(tmp_path, key, value):
    rows = field()
    rows[1][key] = value
    path = source(tmp_path, rows)
    with pytest.raises(ValueError, match="MIXED_SOURCE_RUN|NO_COMPLETE_PRE_OFF_SOURCE_RUN"):
        build_forward_model_packet(
            race_date="2026-09-29", selected_fields={"r1": rows}, model_fields={"M": "main_prob"}, source_paths=[path]
        )


@pytest.mark.parametrize("created", ["2026-09-29T14:00:00+01:00", "2026-09-29T14:01:00+01:00", ""])
def test_each_snapshot_must_be_aware_and_strictly_preoff(tmp_path, created):
    rows = field(created=created)
    path = source(tmp_path, rows)
    with pytest.raises(
        ValueError, match="SNAPSHOT_NOT_STRICTLY_PRE_OFF|SOURCE_RUN_IDENTITY_MISSING|NO_COMPLETE_PRE_OFF_SOURCE_RUN"
    ):
        build_forward_model_packet(
            race_date="2026-09-29", selected_fields={"r1": rows}, model_fields={"M": "main_prob"}, source_paths=[path]
        )


def test_sp_is_never_capture_fallback_and_bad_odds_unavailable(tmp_path):
    rows = field(prices=False)
    rows[0]["sp_dec"] = 12
    rows[1]["captured_odds_dec"] = 1
    path = source(tmp_path, rows)
    p = build_at(
        "2026-09-29T12:05:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": rows},
        model_fields={"M": "main_prob"},
        source_paths=[path],
    )
    r = p["models"][0]["races"][0]
    assert all(x["captured_odds_dec"] is None for x in r["runners"])
    assert r["market_favourite_horse_ids"] is None


def test_invalid_capture_time_rejected(tmp_path):
    rows = field()
    rows[0]["odds_capture_ts"] = "2026-09-29T14:00:00+01:00"
    path = source(tmp_path, rows)
    with pytest.raises(ValueError, match="CAPTURE_PRICE_TIME_INVALID"):
        build_at(
            "2026-09-29T12:05:00+01:00",
            race_date="2026-09-29",
            selected_fields={"r1": rows},
            model_fields={"M": "main_prob"},
            source_paths=[path],
        )


@pytest.mark.parametrize("probs", [(1.1, -0.1, 0), (0.5, 0.3, "bad"), (0.5, 0.3, 0.3), (None, 0.5, 0.5)])
def test_invalid_probabilities_explicitly_excluded(tmp_path, probs):
    rows = field()
    for row, p in zip(rows, probs, strict=True):
        row["main_prob"] = p
    path = source(tmp_path, rows)
    p = build_at(
        "2026-09-29T12:05:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": rows},
        model_fields={"M": "main_prob"},
        source_paths=[path],
    )
    m = p["models"][0]
    assert m["zero_selection_day"] and len(m["exclusions"]) == 1


def test_canonical_path_and_immutable_identity(tmp_path):
    p = packet(tmp_path)
    status, path = write_immutable_packet(p, tmp_path / "lab")
    assert status == "CREATED" and p["packet_identity_hash"] in str(path)
    assert write_immutable_packet(p, tmp_path / "lab")[0] == "VALIDATED_IDENTICAL"
    changed = json.loads(json.dumps(p))
    changed["commit"] = "x"
    body = {k: v for k, v in changed.items() if k != "packet_hash"}
    import hashlib

    changed["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(FileExistsError):
        write_immutable_packet(changed, tmp_path / "lab")


def test_zero_day_retained(tmp_path):
    p = build_at(
        "2026-09-29T08:00:00+01:00",
        race_date="2026-09-29",
        selected_fields={},
        model_fields={"CAPTAIN": "captain_prob"},
        model_versions={"CAPTAIN": "c1"},
    )
    assert p["evidence_class"] == "BACKFILLED"
    out = evaluate_forward_packets([p], [], bootstrap_samples=5)
    c = cohort(out, kind="BACKFILLED")
    assert c["metrics"]["days"] == 1 and c["metrics"]["zero_selection_days"] == 1 and c["metrics"]["races"] == 0
    assert c["day_block_bootstrap"]["days"] == 1


def test_public_builder_has_no_clock_authority():
    assert "clock" not in inspect.signature(build_forward_model_packet).parameters


def test_evaluation_metrics_comparators_bins_and_loo(tmp_path):
    out = evaluate_forward_packets([packet(tmp_path)], truth(), bootstrap_samples=5)
    c = cohort(out)
    m = c["metrics"]
    assert m["wins"] == 1 and m["captured_profit"] == 3 and m["sp_profit"] == 2.5
    assert m["leave_largest_winner_out_profit"] == 0
    assert m["production_comparator"]["settled"] == 1 and m["production_comparator"]["wins"] == 0
    assert m["market_favourite_comparator"]["settled"] == 1 and m["market_favourite_comparator"]["wins"] == 0
    assert m["calibration_bins"][0]["count"] == 1


def test_missing_favourite_is_unavailable_not_loss(tmp_path):
    p = packet(tmp_path, rows=field(prices=False))
    m = cohort(evaluate_forward_packets([p], truth(), bootstrap_samples=0))["metrics"]["market_favourite_comparator"]
    assert m["available"] == 0 and m["settled"] == 0 and m["roi"] is None


def test_void_selection_is_accounting_only(tmp_path):
    rows = truth()
    rows[0]["win"] = True
    rows[1].update(
        {
            "win": False,
            "frame": False,
            "subject_outcome_status": "NON_RUNNER",
            "settlement_status": "VOID",
            "official_evaluation_eligible": False,
        }
    )
    m = cohort(evaluate_forward_packets([packet(tmp_path)], rows, bootstrap_samples=0))["metrics"]
    assert m["void"] == 1 and m["settled"] == 0 and m["captured_profit"] == 0


def test_truth_key_includes_date_and_full_coverage(tmp_path):
    p = packet(tmp_path)
    with pytest.raises(ValueError, match="CANONICAL_RACE_FIELD_MISMATCH"):
        evaluate_forward_packets([p], truth()[:-1])
    with pytest.raises(ValueError, match="RESULT_SOURCE_INCOMPLETE"):
        evaluate_forward_packets([p], truth(complete=False))
    p2 = packet(
        tmp_path,
        rows=field(date="2026-09-30", rid="r1", created="2026-09-30T12:00:00+01:00"),
        date="2026-09-30",
        now="2026-09-30T12:05:00+01:00",
    )
    out = evaluate_forward_packets([p, p2], truth() + truth(date="2026-09-30"), bootstrap_samples=0)
    assert out["result_source_hashes_by_date"] == {"2026-09-29": "hash-2026-09-29", "2026-09-30": "hash-2026-09-30"}


def test_extra_canonical_runner_rejected(tmp_path):
    extra = {**truth()[0], "horse_id": "h4", "win": False}
    with pytest.raises(ValueError, match="CANONICAL_RACE_FIELD_MISMATCH"):
        evaluate_forward_packets([packet(tmp_path)], truth() + [extra])


def test_invalid_sp_is_unavailable_for_sp_pnl_and_clv(tmp_path):
    rows = truth()
    rows[1]["settled_sp_dec"] = 1
    metrics = cohort(evaluate_forward_packets([packet(tmp_path)], rows, bootstrap_samples=0))["metrics"]
    assert metrics["sp_profit"] == 0 and metrics["sp_roi"] is None and metrics["mean_clv_price_ratio"] is None


def test_forged_forward_timing_rejected_even_with_rehashed_packet(tmp_path):
    p = packet(tmp_path)
    p["created_at"] = "2026-09-29T15:00:00+01:00"
    import hashlib

    body = {k: v for k, v in p.items() if k != "packet_hash"}
    p["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="FORGED_FORWARD_TIMING"):
        evaluate_forward_packets([p], truth())


def test_evaluation_is_portable_after_original_source_mutation_or_removal(tmp_path):
    p = packet(tmp_path)
    source_path = Path(p["source_files"][0]["path"])
    source_path.write_text("mutated\n", encoding="utf-8")
    assert cohort(evaluate_forward_packets([p], truth(), bootstrap_samples=0))["metrics"]["races"] == 1
    source_path.unlink()
    assert cohort(evaluate_forward_packets([p], truth(), bootstrap_samples=0))["metrics"]["races"] == 1


def test_evaluation_revalidates_probability_and_price_contracts(tmp_path):
    import hashlib

    p = packet(tmp_path)
    p["models"][0]["races"][0]["runners"][0]["probability"] = 2
    body = {k: v for k, v in p.items() if k != "packet_hash"}
    p["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="PACKET_PROBABILITY_CONTRACT_INVALID"):
        evaluate_forward_packets([p], truth())
    p = packet(tmp_path)
    p["models"][0]["races"][0]["runners"][0]["captured_odds_dec"] = 1
    body = {k: v for k, v in p.items() if k != "packet_hash"}
    p["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="PACKET_CAPTURE_PRICE_CONTRACT_INVALID"):
        evaluate_forward_packets([p], truth())


def test_embedded_selected_source_mutation_rejected_even_if_packet_rehashed(tmp_path):
    import hashlib

    p = packet(tmp_path)
    p["selected_source_evidence"]["r1"]["rows"][0]["horse"] = "Forged"
    body = {k: v for k, v in p.items() if k != "packet_hash"}
    p["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="SELECTED_SOURCE_EVIDENCE_HASH_MISMATCH"):
        evaluate_forward_packets([p], truth())


def test_rehashed_selection_change_cannot_escape_embedded_source(tmp_path):
    import hashlib

    p = packet(tmp_path)
    p["models"][1]["races"][0]["runners"][0]["probability"] = 0.7
    p["models"][1]["races"][0]["runners"][1]["probability"] = 0.1
    body = {k: v for k, v in p.items() if k != "packet_hash"}
    p["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="PACKET_SELECTION_NOT_DERIVED_FROM_EMBEDDED_SOURCE"):
        evaluate_forward_packets([p], truth())


def test_packet_identity_recomputed_from_actual_models(tmp_path):
    import hashlib

    p = packet(tmp_path)
    p["models"][0]["model_version"] = "forged"
    body = {k: v for k, v in p.items() if k != "packet_hash"}
    p["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="PACKET_IDENTITY_MISMATCH"):
        evaluate_forward_packets([p], truth())


def test_duplicate_dedup_order_invariance_and_version_cohorts(tmp_path):
    p = packet(tmp_path)
    p2 = captain_packet(tmp_path)
    a = evaluate_forward_packets([p, p, p2], truth(), bootstrap_samples=3)
    b = evaluate_forward_packets([p2, p], list(reversed(truth())), bootstrap_samples=3)
    assert a["evaluation_hash"] == b["evaluation_hash"]
    assert set(a["evidence"]["GENUINELY_FORWARD"]["CAPTAIN"]) == {"c1", "c2"}


def test_conflicting_identity_and_production_conflict_rejected(tmp_path):
    p = packet(tmp_path)
    changed = json.loads(json.dumps(p))
    changed["models"][1]["races"][0]["selection_horse_id"] = "h3"
    import hashlib

    body = {k: v for k, v in changed.items() if k != "packet_hash"}
    changed["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="CONFLICTING_PACKET_IDENTITY"):
        evaluate_forward_packets([p, changed], truth())


def test_cross_packet_production_comparator_and_version_conflict(tmp_path):
    rows = field()
    prod_path = source(tmp_path, rows, "prod.jsonl")
    captain_path = source(tmp_path, rows, "cap.jsonl")
    prod = build_at(
        "2026-09-29T12:05:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": rows},
        model_fields={"MAIN_VELO_PRIME": "main_prob"},
        model_versions={"MAIN_VELO_PRIME": "g1"},
        source_paths=[prod_path],
    )
    cap = build_at(
        "2026-09-29T12:05:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": rows},
        model_fields={"CAPTAIN": "captain_prob"},
        model_versions={"CAPTAIN": "c1"},
        source_paths=[captain_path],
    )
    metrics = cohort(evaluate_forward_packets([cap, prod], truth(), bootstrap_samples=0))["metrics"]
    assert metrics["production_comparator"]["available"] == 1 and metrics["production_comparator"]["wins"] == 0
    prod2 = json.loads(json.dumps(prod))
    prod2["models"][0]["model_version"] = "g2"
    prod2["packet_identity"]["models"][0]["model_version"] = "g2"
    import hashlib

    prod2["packet_identity_hash"] = hashlib.sha256(
        json.dumps(prod2["packet_identity"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    body = {k: v for k, v in prod2.items() if k != "packet_hash"}
    prod2["packet_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="PRODUCTION_COMPARATOR_CONFLICT"):
        evaluate_forward_packets([prod, prod2], truth())


def test_cross_packet_production_uses_production_packet_price_and_snapshot(tmp_path):
    prod_rows = field(created="2026-09-29T11:00:00+01:00")
    prod_rows[0]["captured_odds_dec"] = 9.0
    prod_rows[0]["odds_capture_ts"] = "2026-09-29T10:55:00+01:00"
    cap_rows = field(created="2026-09-29T12:00:00+01:00")
    prod_path = source(tmp_path, prod_rows, "production_price.jsonl")
    cap_path = source(tmp_path, cap_rows, "captain_price.jsonl")
    prod = build_at(
        "2026-09-29T12:05:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": prod_rows},
        model_fields={"MAIN_VELO_PRIME": "main_prob"},
        model_versions={"MAIN_VELO_PRIME": "g1"},
        source_paths=[prod_path],
    )
    cap = build_at(
        "2026-09-29T12:05:00+01:00",
        race_date="2026-09-29",
        selected_fields={"r1": cap_rows},
        model_fields={"CAPTAIN": "captain_prob"},
        model_versions={"CAPTAIN": "c1"},
        source_paths=[cap_path],
    )
    rows = truth()
    rows[0]["win"] = True
    rows[1]["win"] = False
    captain = cohort(evaluate_forward_packets([cap, prod], rows, bootstrap_samples=0))
    record = captain["records"][0]
    assert captain["metrics"]["production_comparator"]["profit"] == 8.0
    assert record["production_packet_hash"] == prod["packet_hash"]
    assert record["production_captured_odds_dec"] == 9.0
    assert record["production_odds_capture_ts"] == "2026-09-29T10:55:00+01:00"
    assert record["production_snapshot_created_at"] == "2026-09-29T11:00:00+01:00"


def test_atomic_packet_and_evaluation_writers_use_governed_paths(tmp_path):
    p = packet(tmp_path)
    assert write_immutable_packet(p, tmp_path / "lab")[0] == "CREATED"
    assert write_immutable_packet(p, tmp_path / "lab")[0] == "VALIDATED_IDENTICAL"
    evaluation = evaluate_forward_packets([p], truth(), bootstrap_samples=0)
    status, path = write_immutable_evaluation(evaluation, tmp_path / "lab")
    assert status == "CREATED" and path.parent.name == "evaluations"
    assert write_immutable_evaluation(evaluation, tmp_path / "lab")[0] == "VALIDATED_IDENTICAL"
    assert not list((tmp_path / "lab").rglob("*.tmp"))


def test_evaluation_identity_and_path_include_methodology(tmp_path):
    p = packet(tmp_path)
    first = evaluate_forward_packets([p], truth(), bootstrap_samples=3, bootstrap_seed=7)
    second = evaluate_forward_packets([p], truth(), bootstrap_samples=4, bootstrap_seed=7)
    third = evaluate_forward_packets([p], truth(), bootstrap_samples=3, bootstrap_seed=8)
    fourth = evaluate_forward_packets([p], truth(), bootstrap_samples=3, bootstrap_seed=7, production_model="OTHER")
    assert len({item["evaluation_identity_hash"] for item in (first, second, third, fourth)}) == 4
    paths = {write_immutable_evaluation(item, tmp_path / "lab")[1] for item in (first, second, third, fourth)}
    assert len(paths) == 4
    assert first["methodology"]["calibration_bins"] == 10
    assert first["methodology"]["evaluator_version"] == "forward-model-evaluator-v2"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("methodology", {"forged": True}),
        ("packet_hashes", ["forged-packet"]),
        ("result_source_hashes_by_date", {"2026-09-29": "forged-result"}),
    ],
)
def test_evaluation_writer_rejects_top_level_tamper_with_stale_identity(tmp_path, field, replacement):
    import hashlib

    evaluation = evaluate_forward_packets([packet(tmp_path)], truth(), bootstrap_samples=0)
    evaluation[field] = replacement
    body = {key: value for key, value in evaluation.items() if key != "evaluation_hash"}
    evaluation["evaluation_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="EVALUATION_IDENTITY_MISMATCH"):
        write_immutable_evaluation(evaluation, tmp_path / "lab")


def test_bootstrap_zero_days_reproducible():
    row = {
        "race_date": "2026-09-29",
        "settlement_status": "SETTLED",
        "win": True,
        "frame": True,
        "brier": 0.2,
        "log_loss": 0.4,
        "selected_probability": 0.6,
        "captured_pnl": 2.0,
        "captured_return": 3.0,
        "sp_pnl": 1.0,
        "clv_price_ratio": 1.1,
        "production_available": False,
        "production_settled": False,
        "production_win": None,
        "production_pnl": None,
        "market_available": False,
        "market_settled": False,
        "market_win": None,
        "market_pnl": None,
    }
    a = day_block_bootstrap([row], zero_days={"2026-09-28"}, samples=20, seed=7)
    assert a == day_block_bootstrap([row], zero_days={"2026-09-28"}, samples=20, seed=7)
    assert a["days"] == 2 and a["zero_selection_days"] == 1 and "captured_daily_profit" in a["intervals_95pct"]
