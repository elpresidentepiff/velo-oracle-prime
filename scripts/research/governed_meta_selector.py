#!/usr/bin/env python3
"""Leakage-safe, frozen, PAPER/SIM-only conditional selector research."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from operator import itemgetter
from pathlib import Path

SCHEMA_VERSION = "governed-meta-selector-v1"
NUMERIC_CONTEXT = ("field_size", "race_class", "pace", "shape", "campaign_state", "trainer_context", "jockey_context")
CATEGORICAL_CONTEXT = ("race_type", "course", "going")
CORRELATION_THRESHOLD = 0.98
PREDECLARED_REGIONS = {
    "LOW_DISAGREEMENT": {"field": "disagreement_range", "operator": "LE", "value": 0.10},
    "MID_PRICE": {"field": "captured_odds_dec", "operator": "BETWEEN", "lower": 3.0, "upper": 10.0},
    "SMALL_FIELD": {"field": "field_size", "operator": "LE", "value": 8.0},
}
FORBIDDEN_TOKENS = (
    "result", "settled", "settlement", "outcome", "position", "finish", "winner", "won",
    "sp", "bsp", "post_off", "future", "pnl", "profit", "return", "label", "target",
)


def _meta_canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _meta_hash(value):
    return hashlib.sha256(_meta_canonical(value).encode()).hexdigest()


def _meta_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _meta_parse_ts(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _meta_validate_race_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("RACE_DATE_NOT_STRICT_ISO")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("RACE_DATE_NOT_STRICT_ISO") from None
    if parsed.isoformat() != value:
        raise ValueError("RACE_DATE_NOT_STRICT_ISO")
    return parsed


def _meta_source_payload(row):
    return {key: value for key, value in row.items() if key not in {"packet_hash", "source_packet"}}


def _meta_validate_source_row(row):
    def walk(value, path=""):
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key).lower()
                if any(token in normalized for token in FORBIDDEN_TOKENS):
                    raise ValueError(f"FORBIDDEN_FEATURE_FIELD:{path}{key}")
                walk(item, f"{path}{key}.")
        elif isinstance(value, list):
            for item in value:
                walk(item, path)

    walk(row)
    required = ("race_date", "race_id", "horse_id", "snapshot_created_at", "off_ts", "packet_hash")
    if any(not row.get(key) for key in required):
        raise ValueError("FEATURE_IDENTITY_OR_PROVENANCE_MISSING")
    race_date = _meta_validate_race_date(row["race_date"])
    captured = _meta_parse_ts(row["snapshot_created_at"])
    off = _meta_parse_ts(row["off_ts"])
    if captured is None or off is None or off.date() != race_date or captured.date() != race_date or captured >= off:
        raise ValueError("FEATURE_SNAPSHOT_NOT_STRICTLY_PRE_OFF")
    odds = _meta_number(row.get("captured_odds_dec"))
    if odds is not None:
        odds_ts = _meta_parse_ts(row.get("odds_capture_ts"))
        if odds <= 1 or odds_ts is None or odds_ts.date() != race_date or odds_ts > captured or odds_ts >= off:
            raise ValueError("CAPTURE_PRICE_NOT_STRICTLY_PRE_OFF")
    packet_hash = str(row["packet_hash"])
    packet_body = row.get("source_packet")
    if not re.fullmatch(r"[0-9a-f]{64}", packet_hash) or not isinstance(packet_body, dict) or _meta_hash(packet_body) != packet_hash:
        raise ValueError("SOURCE_PACKET_HASH_UNVERIFIED")
    payload = _meta_source_payload(row)
    declared_payloads = packet_body.get("feature_payloads")
    if not isinstance(declared_payloads, list) or _meta_canonical(payload) not in {_meta_canonical(item) for item in declared_payloads}:
        raise ValueError("FEATURE_NOT_LINKED_TO_SOURCE_PACKET")


def meta_build_feature_matrix(source_rows):
    """Normalize pre-race rows; labels must be supplied separately to evaluators."""
    matrix = []
    seen = set()
    for source in source_rows:
        if not isinstance(source, dict):
            raise ValueError("FEATURE_ROW_NOT_OBJECT")
        _meta_validate_source_row(source)
        identity = (str(source["race_date"]), str(source["race_id"]), str(source["horse_id"]))
        if identity in seen:
            raise ValueError(f"DUPLICATE_FEATURE_IDENTITY:{identity}")
        seen.add(identity)
        probabilities = source.get("model_probabilities") or {}
        ranks = source.get("model_ranks") or {}
        if not isinstance(probabilities, dict) or not isinstance(ranks, dict):
            raise ValueError("MODEL_FEATURES_MUST_BE_MAPPINGS")
        clean_probs = {}
        clean_ranks = {}
        for name, value in sorted(probabilities.items()):
            number = _meta_number(value)
            if number is None or not 0 <= number <= 1:
                raise ValueError(f"INVALID_MODEL_PROBABILITY:{name}")
            clean_probs[str(name)] = number
        for name, value in sorted(ranks.items()):
            number = _meta_number(value)
            if number is None or number < 1 or not number.is_integer():
                raise ValueError(f"INVALID_MODEL_RANK:{name}")
            clean_ranks[str(name)] = int(number)
        if not clean_probs:
            raise ValueError("MODEL_PROBABILITIES_MISSING")
        implied = None
        odds = _meta_number(source.get("captured_odds_dec"))
        if odds is not None:
            implied = 1.0 / odds
        values = list(clean_probs.values())
        row = {
            "race_date": identity[0], "race_id": identity[1], "horse_id": identity[2],
            "packet_hash": str(source["packet_hash"]),
            "source_packet": source["source_packet"],
            "source_payload_hash": _meta_hash(_meta_source_payload(source)),
            "snapshot_created_at": str(source["snapshot_created_at"]), "off_ts": str(source["off_ts"]),
            "odds_capture_ts": str(source.get("odds_capture_ts") or "") or None,
            "captured_odds_dec": odds, "market_probability": implied,
            "model_probabilities": clean_probs, "model_ranks": clean_ranks,
            "disagreement_range": max(values) - min(values),
            "disagreement_variance": sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values),
        }
        for key in NUMERIC_CONTEXT:
            row[key] = _meta_number(source.get(key))
        for key in CATEGORICAL_CONTEXT:
            row[key] = str(source.get(key) or "UNKNOWN")
        row["source_feature_hash"] = _meta_hash({key: value for key, value in row.items() if key != "source_feature_hash"})
        matrix.append(row)
    matrix.sort(key=lambda row: (row["race_date"], row["race_id"], row["horse_id"]))
    schemas = {(tuple(row["model_probabilities"]), tuple(row["model_ranks"])) for row in matrix}
    if len(schemas) > 1 or any(probabilities != ranks for probabilities, ranks in schemas):
        raise ValueError("MODEL_FEATURE_SCHEMA_INCONSISTENT")
    grouped = defaultdict(list)
    for row in matrix:
        grouped[(row["race_date"], row["race_id"])].append(row)
    for identity, field in grouped.items():
        for model in field[0]["model_probabilities"]:
            if not math.isclose(sum(row["model_probabilities"][model] for row in field), 1.0, abs_tol=1e-6):
                raise ValueError(f"MODEL_PROBABILITIES_NOT_NORMALIZED:{identity}:{model}")
            ranks = [row["model_ranks"][model] for row in field]
            if sorted(ranks) != list(range(1, len(field) + 1)):
                raise ValueError(f"MODEL_RANKS_NOT_COMPLETE:{identity}:{model}")
    return matrix


def make_purged_rolling_splits(rows, *, min_train_days=3, tune_days=1, score_days=1, purge_days=1):
    dates = sorted({row["race_date"] for row in rows})
    needed = min_train_days + purge_days + tune_days + purge_days + score_days
    if len(dates) < needed:
        raise ValueError(f"INSUFFICIENT_DATES_FOR_PURGED_SPLIT:{len(dates)}<{needed}")
    splits = []
    score_start = min_train_days + purge_days + tune_days + purge_days
    while score_start < len(dates):
        train_end = score_start - purge_days - tune_days - purge_days
        tune_start = train_end + purge_days
        tune_end = tune_start + tune_days
        score_end = min(score_start + score_days, len(dates))
        split = {
            "train_dates": dates[:train_end], "train_tune_purge_dates": dates[train_end:tune_start],
            "tune_dates": dates[tune_start:tune_end], "tune_score_purge_dates": dates[tune_end:score_start],
            "score_dates": dates[score_start:score_end],
        }
        if split["train_dates"] and split["tune_dates"] and split["score_dates"]:
            splits.append(split)
        score_start = score_end
    return splits


def _meta_regions(row, config):
    regions = []
    for name, rule in sorted(config.items()):
        value = _meta_number(row.get(rule["field"]))
        if value is None:
            continue
        if rule["operator"] == "LE" and value <= rule["value"]:
            regions.append(name)
        elif rule["operator"] == "BETWEEN" and rule["lower"] <= value <= rule["upper"]:
            regions.append(name)
    return regions


def _meta_authenticate_matrix_row(row):
    body = {key: value for key, value in row.items() if key != "source_feature_hash"}
    if row.get("source_feature_hash") != _meta_hash(body):
        raise ValueError("FIELD_FEATURE_HASH_MISMATCH")
    packet = row.get("source_packet")
    if not isinstance(packet, dict) or _meta_hash(packet) != row.get("packet_hash"):
        raise ValueError("FIELD_PACKET_HASH_MISMATCH")
    payloads = packet.get("feature_payloads")
    if not isinstance(payloads, list):
        raise ValueError("FIELD_PACKET_PAYLOADS_MISSING")
    rebuilt = meta_build_feature_matrix([
        {**payload, "packet_hash": row["packet_hash"], "source_packet": packet} for payload in payloads
    ])
    matches = [candidate for candidate in rebuilt if (candidate["race_date"], candidate["race_id"], candidate["horse_id"])
               == (row["race_date"], row["race_id"], row["horse_id"])]
    if len(matches) != 1 or matches[0] != row:
        raise ValueError("FIELD_PACKET_LINKAGE_INVALID")


def _meta_validate_field_rows(field_rows):
    if not field_rows:
        raise ValueError("DECISION_FIELD_EMPTY")
    ordered = sorted(field_rows, key=itemgetter("horse_id"))
    if field_rows != ordered:
        raise ValueError("DECISION_FIELD_NOT_STABLY_ORDERED")
    identities = {(row["race_date"], row["race_id"]) for row in field_rows}
    if len(identities) != 1 or len({row["horse_id"] for row in field_rows}) != len(field_rows):
        raise ValueError("DECISION_FIELD_IDENTITY_INVALID")
    packet_hashes = {row["packet_hash"] for row in field_rows}
    snapshots = {row["snapshot_created_at"] for row in field_rows}
    off_times = {row["off_ts"] for row in field_rows}
    if len(packet_hashes) != 1 or len(snapshots) != 1 or len(off_times) != 1:
        raise ValueError("DECISION_FIELD_PACKET_OR_SNAPSHOT_CHIMERA")
    schemas = {(tuple(row["model_probabilities"]), tuple(row["model_ranks"])) for row in field_rows}
    if len(schemas) != 1 or any(probabilities != ranks for probabilities, ranks in schemas):
        raise ValueError("DECISION_FIELD_SCHEMA_INCONSISTENT")
    for row in field_rows:
        _meta_authenticate_matrix_row(row)
    packet = field_rows[0]["source_packet"]
    payloads = packet.get("feature_payloads")
    rebuilt = meta_build_feature_matrix([
        {**payload, "packet_hash": field_rows[0]["packet_hash"], "source_packet": packet} for payload in payloads
    ])
    race_date, race_id = next(iter(identities))
    if any((row["race_date"], row["race_id"]) != (race_date, race_id) for row in rebuilt):
        raise ValueError("DECISION_PACKET_CONTAINS_OTHER_RACE")
    rebuilt.sort(key=itemgetter("horse_id"))
    if rebuilt != ordered:
        raise ValueError("DECISION_FIELD_NOT_COMPLETE_PACKET_FIELD")
    probabilities, _ = next(iter(schemas))
    for model in probabilities:
        if not math.isclose(sum(row["model_probabilities"][model] for row in ordered), 1.0, abs_tol=1e-6):
            raise ValueError(f"DECISION_MODEL_PROBABILITIES_NOT_NORMALIZED:{model}")
        observed_ranks = sorted(row["model_ranks"][model] for row in ordered)
        if observed_ranks != list(range(1, len(ordered) + 1)):
            raise ValueError(f"DECISION_MODEL_RANKS_NOT_COMPLETE:{model}")
    return ordered


def _meta_decision_input_hash(field_rows, decision_contract):
    ordered = _meta_validate_field_rows(field_rows)
    body = {
        "race_date": ordered[0]["race_date"], "race_id": ordered[0]["race_id"],
        "field_rows": ordered,
        "packet_hashes": sorted({row["packet_hash"] for row in ordered}),
        "source_feature_hashes": [row["source_feature_hash"] for row in ordered],
        "decision_contract": decision_contract,
    }
    return _meta_hash(body)


def _meta_transparent_decisions(field, config):
    production_model, captain_model = config["production_model"], config["captain_model"]
    gate = config["captain_gate"]
    eligible_production = [row for row in field if production_model in row["model_probabilities"]]
    eligible_captain = [row for row in field if captain_model in row["model_probabilities"]]
    production = min((-row["model_probabilities"][production_model], row["horse_id"], row) for row in eligible_production)[2] if eligible_production else None
    captain = min((-row["model_probabilities"][captain_model], row["horse_id"], row) for row in eligible_captain)[2] if eligible_captain else None
    priced = [row for row in field if row["captured_odds_dec"] is not None]
    favourite = min((row["captured_odds_dec"], row["horse_id"], row) for row in priced)[2] if priced else None
    agreement = production if production and captain and production["horse_id"] == captain["horse_id"] else None
    gated = None
    if captain:
        probability, odds = captain["model_probabilities"][captain_model], captain["captured_odds_dec"]
        maximum = gate["max_odds"]
        if (odds is not None and gate["min_probability"] <= probability and gate["min_odds"] <= odds
                and (maximum is None or odds <= maximum) and captain["disagreement_range"] <= gate["max_disagreement"]):
            gated = captain
    return {"PRODUCTION": production, "CAPTAIN": captain, "MARKET_FAVOURITE": favourite,
            "AGREEMENT": agreement, "GATED_CAPTAIN": gated, "ABSTAIN": None}


def _meta_selection_record(date, race_id, policy, selected, *, probability=None, policy_hash=None, regions=None,
                           governed_identities=None, field_rows=None, decision_contract=None):
    governed_field = sorted(field_rows or [], key=itemgetter("horse_id"))
    record = {
        "race_date": date, "race_id": race_id, "policy": policy,
        "selection_horse_id": selected["horse_id"] if selected else None,
        "abstained": selected is None,
        "captured_odds_dec": selected["captured_odds_dec"] if selected else None,
        "odds_capture_ts": selected["odds_capture_ts"] if selected else None,
        "snapshot_created_at": selected["snapshot_created_at"] if selected else None,
        "off_ts": selected["off_ts"] if selected else None,
        "packet_hash": selected["packet_hash"] if selected else None,
        "source_feature_hash": selected["source_feature_hash"] if selected else None,
        "source_feature_row": selected if selected else None,
        "regions": sorted(regions or []),
        "governed_feature_identities": sorted(governed_identities or []),
        "governed_field_rows": governed_field,
        "decision_contract": decision_contract,
        "decision_input_hash": _meta_decision_input_hash(governed_field, decision_contract),
    }
    if probability is not None:
        record["calibrated_probability"] = probability
    if policy_hash is not None:
        record["policy_hash"] = policy_hash
    return record


def _meta_rederive_decision(record):
    field = record.get("governed_field_rows")
    contract = record.get("decision_contract")
    if not isinstance(field, list) or not isinstance(contract, dict):
        raise ValueError("DECISION_EVIDENCE_MISSING")
    field = _meta_validate_field_rows(field)
    if record.get("decision_input_hash") != _meta_decision_input_hash(field, contract):
        raise ValueError("DECISION_INPUT_HASH_MISMATCH")
    if contract.get("policy") != record.get("policy"):
        raise ValueError("DECISION_POLICY_RELABELLED")
    if contract.get("kind") == "TRANSPARENT":
        config = contract.get("selector_config")
        if not isinstance(config, dict):
            raise ValueError("TRANSPARENT_SELECTOR_CONFIG_MISSING")
        decisions = _meta_transparent_decisions(field, config)
        if record["policy"] not in decisions:
            raise ValueError("TRANSPARENT_POLICY_UNKNOWN")
        selected, probability = decisions[record["policy"]], None
        regions = _meta_regions(selected, config["conditional_regions"]) if selected else []
    elif contract.get("kind") == "META":
        policy = freeze_meta_policy(contract.get("frozen_policy") or {})
        if record.get("policy_hash") != policy["policy_hash"]:
            raise ValueError("META_POLICY_IDENTITY_MISMATCH")
        selected, probability, regions = _meta_score_field(policy, field)
    else:
        raise ValueError("DECISION_CONTRACT_KIND_INVALID")
    return selected, probability, sorted(regions)


def _meta_validate_selection_record(record):
    selected, probability, regions = _meta_rederive_decision(record)
    expected_id = selected["horse_id"] if selected else None
    if record.get("selection_horse_id") != expected_id or record.get("abstained") is not (selected is None):
        raise ValueError("DECLARED_DECISION_DOES_NOT_REPRODUCE")
    if record.get("regions") != regions:
        raise ValueError("DECLARED_DECISION_REGIONS_DO_NOT_REPRODUCE")
    if probability is None:
        if "calibrated_probability" in record:
            raise ValueError("DECLARED_DECISION_PROBABILITY_INVALID")
    elif record.get("calibrated_probability") != probability:
        raise ValueError("DECLARED_DECISION_PROBABILITY_INVALID")
    if selected is None:
        forbidden = ("source_feature_row", "captured_odds_dec", "packet_hash", "source_feature_hash",
                     "odds_capture_ts", "snapshot_created_at", "off_ts")
        if any(record.get(key) is not None for key in forbidden):
            raise ValueError("ABSTAIN_PROVENANCE_INVALID")
        return
    row = record.get("source_feature_row")
    if not isinstance(row, dict):
        raise ValueError("SELECTION_FEATURE_PROVENANCE_MISSING")
    body = {key: value for key, value in row.items() if key != "source_feature_hash"}
    if row.get("source_feature_hash") != _meta_hash(body):
        raise ValueError("SELECTION_FEATURE_HASH_MISMATCH")
    packet = row.get("source_packet")
    if not isinstance(packet, dict) or _meta_hash(packet) != row.get("packet_hash"):
        raise ValueError("SELECTION_PACKET_LINKAGE_INVALID")
    payloads = packet.get("feature_payloads")
    if not isinstance(payloads, list):
        raise ValueError("SELECTION_PACKET_LINKAGE_INVALID")
    rebuilt = meta_build_feature_matrix([
        {**payload, "packet_hash": row["packet_hash"], "source_packet": packet} for payload in payloads
    ])
    matches = [candidate for candidate in rebuilt if (candidate["race_date"], candidate["race_id"], candidate["horse_id"])
               == (row["race_date"], row["race_id"], row["horse_id"])]
    if len(matches) != 1 or matches[0] != row:
        raise ValueError("SELECTION_PACKET_LINKAGE_INVALID")
    exact = {
        "race_date": row["race_date"], "race_id": row["race_id"], "selection_horse_id": row["horse_id"],
        "captured_odds_dec": row["captured_odds_dec"], "odds_capture_ts": row["odds_capture_ts"],
        "snapshot_created_at": row["snapshot_created_at"], "off_ts": row["off_ts"],
        "packet_hash": row["packet_hash"], "source_feature_hash": row["source_feature_hash"],
    }
    if any(record.get(key) != value for key, value in exact.items()):
        raise ValueError("SELECTION_PROVENANCE_TAMPERED")
    race_date = _meta_validate_race_date(row["race_date"])
    snapshot, off = (_meta_parse_ts(row[key]) for key in ("snapshot_created_at", "off_ts"))
    odds_ts = _meta_parse_ts(row.get("odds_capture_ts"))
    odds = _meta_number(row["captured_odds_dec"])
    if (snapshot is None or off is None or off.date() != race_date or snapshot.date() != race_date or snapshot >= off):
        raise ValueError("SELECTION_PRICE_OR_TIMING_INVALID")
    if odds is None:
        if odds_ts is not None:
            raise ValueError("SELECTION_PRICE_OR_TIMING_INVALID")
    elif odds <= 1 or odds_ts is None or odds_ts.date() != race_date or odds_ts > snapshot or odds_ts >= off:
        raise ValueError("SELECTION_PRICE_OR_TIMING_INVALID")
    if not re.fullmatch(r"[0-9a-f]{64}", row["packet_hash"]):
        raise ValueError("SELECTION_PACKET_HASH_INVALID")


def select_transparent_candidates(rows, *, production_model="PRODUCTION", captain_model="CAPTAIN", captain_gate=None,
                                  region_config=None):
    gate = {"min_probability": 0.0, "min_odds": 1.0, "max_odds": None, "max_disagreement": 1.0,
            **(captain_gate or {})}
    config = {"production_model": production_model, "captain_model": captain_model,
              "captain_gate": gate, "conditional_regions": region_config or PREDECLARED_REGIONS}
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["race_date"], row["race_id"])].append(row)
    records = []
    for (date, race_id), field in sorted(grouped.items()):
        field = sorted(field, key=itemgetter("horse_id"))
        _meta_validate_field_rows(field)
        decisions = _meta_transparent_decisions(field, config)
        for policy, selected in decisions.items():
            contract = {"kind": "TRANSPARENT", "policy": policy, "selector_config": config}
            records.append(_meta_selection_record(
                date, race_id, policy, selected,
                regions=_meta_regions(selected, config["conditional_regions"]) if selected else [],
                governed_identities=[f"{r['race_date']}|{r['race_id']}|{r['horse_id']}" for r in field],
                field_rows=field, decision_contract=contract,
            ))
    return records


def _meta_truth_index(truth_rows, expected_identities):
    truth = {}
    for row in truth_rows:
        key = (str(row.get("race_date") or row.get("date") or ""), str(row.get("race_id") or ""), str(row.get("horse_id") or ""))
        _meta_validate_race_date(key[0])
        if not key[1] or not key[2] or key in truth:
            raise ValueError("TRUTH_IDENTITY_DUPLICATE_OR_INVALID")
        if row.get("result_source_complete") is not True or row.get("official_evaluation_eligible") is not True:
            raise ValueError("TRUTH_NOT_COMPLETE_AND_ELIGIBLE")
        if row.get("settlement_status") != "SETTLED" or type(row.get("win")) is not bool:
            raise ValueError("TRUTH_OUTCOME_NOT_CANONICAL")
        truth[key] = row
    actual = {"|".join(key) for key in truth}
    if actual != set(expected_identities):
        missing = sorted(set(expected_identities) - actual)
        extra = sorted(actual - set(expected_identities))
        raise ValueError(f"TRUTH_FEATURE_COVERAGE_MISMATCH:missing={missing}:extra={extra}")
    return truth


def _meta_max_drawdown(daily):
    equity = peak = drawdown = 0.0
    for value in daily:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def _meta_day_bootstrap(records, *, samples=500, seed=17):
    days = sorted({row["race_date"] for row in records})
    if not days or samples <= 0:
        return {"days": len(days), "samples": 0, "profit_95pct": None}
    by_day = {day: sum(row["pnl"] for row in records if row["race_date"] == day) for day in days}
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        estimates.append(sum(by_day[rng.choice(days)] for _ in days))
    estimates.sort()
    return {"days": len(days), "samples": samples, "profit_95pct": [estimates[int(.025 * (samples - 1))], estimates[int(.975 * (samples - 1))]]}


def _meta_metrics(records, *, bootstrap_samples=500, bootstrap_seed=17):
    selected = [row for row in records if not row["abstained"]]
    settled = [row for row in selected if row["settled"]]
    priced = [row for row in settled if row["price_available"]]
    profits = [row["pnl"] for row in priced]
    daily = [sum(row["pnl"] for row in priced if row["race_date"] == day) for day in sorted({r["race_date"] for r in records})]
    biggest = max((row["pnl"] for row in priced if row["pnl"] > 0), default=0.0)
    total = sum(profits)
    return {
        "days": len({row["race_date"] for row in records}), "races": len(records), "selections": len(selected),
        "abstentions": len(records) - len(selected), "settled": len(settled), "wins": sum(bool(row["win"]) for row in settled),
        "captured_price_settled": len(priced), "profit": total, "roi": total / len(priced) if priced else None,
        "max_drawdown": _meta_max_drawdown(daily), "largest_winner_profit": biggest,
        "profit_ex_largest_winner": total - biggest,
        "bootstrap": _meta_day_bootstrap(settled, samples=bootstrap_samples, seed=bootstrap_seed),
    }


def _meta_region_report(records, *, bootstrap_samples, bootstrap_seed):
    report = {}
    for region in sorted({region for row in records for region in row.get("regions", [])}):
        subset = [row for row in records if region in row.get("regions", [])]
        report[region] = {
            "support_races": len(subset),
            "metrics": _meta_metrics(subset, bootstrap_samples=bootstrap_samples, bootstrap_seed=bootstrap_seed),
        }
    return report


def evaluate_policy_records(records, truth_rows, *, bootstrap_samples=500, bootstrap_seed=17):
    expected_sets = {tuple(row.get("governed_feature_identities") or []) for row in records}
    expected = {identity for identities in expected_sets for identity in identities}
    if not expected:
        raise ValueError("GOVERNED_EVALUATION_IDENTITIES_MISSING")
    truth = _meta_truth_index(truth_rows, expected)
    evaluated = []
    for record in records:
        item = dict(record)
        _meta_validate_selection_record(item)
        if item["abstained"]:
            item.update({"settled": False, "win": None, "price_available": False, "pnl": 0.0})
        else:
            fact = truth.get((item["race_date"], item["race_id"], item["selection_horse_id"]))
            if not fact or fact.get("result_source_complete") is not True:
                raise ValueError("COMPLETE_CANONICAL_TRUTH_MISSING")
            settled = fact.get("settlement_status") == "SETTLED" and fact.get("official_evaluation_eligible") is True
            won = bool(fact.get("win")) if settled else None
            odds = item.get("captured_odds_dec")
            price_available = settled and odds is not None and odds > 1
            item.update({"settled": settled, "win": won, "price_available": price_available,
                         "pnl": ((odds - 1) if won else -1.0) if price_available else 0.0})
        evaluated.append(item)
    policies = {}
    for policy in sorted({row["policy"] for row in evaluated}):
        subset = [row for row in evaluated if row["policy"] == policy]
        policies[policy] = {
            "metrics": _meta_metrics(subset, bootstrap_samples=bootstrap_samples, bootstrap_seed=bootstrap_seed),
            "conditional_regions": _meta_region_report(
                subset, bootstrap_samples=bootstrap_samples, bootstrap_seed=bootstrap_seed
            ),
            "records": subset,
        }
    return policies


def _meta_sigmoid(value):
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


def _meta_fit_logistic(x_rows, labels, penalties, *, iterations=800, learning_rate=.05):
    if not x_rows or len(x_rows) != len(labels):
        raise ValueError("TRAINING_ROWS_INVALID")
    weights = [0.0] * len(x_rows[0])
    bias = 0.0
    n = len(x_rows)
    for _ in range(iterations):
        errors = [
            _meta_sigmoid(bias + sum(w * x for w, x in zip(weights, row, strict=True))) - y
            for row, y in zip(x_rows, labels, strict=True)
        ]
        bias -= learning_rate * sum(errors) / n
        for idx in range(len(weights)):
            gradient = (
                sum(error * row[idx] for error, row in zip(errors, x_rows, strict=True)) / n
                + penalties[idx] * weights[idx]
            )
            weights[idx] -= learning_rate * gradient
    return bias, weights


def _meta_pearson(left, right):
    if len(left) != len(right) or not left:
        raise ValueError("CORRELATION_INPUT_INVALID")
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right, strict=True))
    left_var = sum((a - mean_left) ** 2 for a in left)
    right_var = sum((b - mean_right) ** 2 for b in right)
    if left_var == 0 or right_var == 0:
        return 0.0
    return numerator / math.sqrt(left_var * right_var)


def _meta_correlation_prune(feature_names, x_rows, *, threshold=CORRELATION_THRESHOLD):
    components = [{name} for name in feature_names]
    correlations = []
    for left_idx, left in enumerate(feature_names):
        for right_idx in range(left_idx + 1, len(feature_names)):
            right = feature_names[right_idx]
            value = _meta_pearson([row[left_idx] for row in x_rows], [row[right_idx] for row in x_rows])
            correlations.append({"left": left, "right": right, "pearson": value})
            if abs(value) >= threshold:
                matching = [component for component in components if left in component or right in component]
                if len(matching) == 2:
                    merged = matching[0] | matching[1]
                    components = [component for component in components if component not in matching] + [merged]
    mapping = {name: min(component) for component in components for name in component}
    kept = [name for name in feature_names if mapping[name] == name]
    return {"threshold": threshold, "matrix": correlations, "representative_by_feature": mapping,
            "kept_features": kept, "pruned_features": sorted(name for name in feature_names if name not in kept)}


def train_calibrated_meta_policy(matrix, truth_rows, split, *, threshold_grid=(.45, .5, .55, .6), l2=.02):
    governed_dates = set(split["train_dates"]) | set(split["tune_dates"])
    relevant_truth = [r for r in truth_rows if str(r.get("race_date") or r.get("date")) in governed_dates]
    train = sorted((r for r in matrix if r["race_date"] in split["train_dates"]), key=itemgetter("race_date", "race_id", "horse_id"))
    tune = sorted((r for r in matrix if r["race_date"] in split["tune_dates"]), key=itemgetter("race_date", "race_id", "horse_id"))
    if not train or not tune:
        raise ValueError("EMPTY_TRAIN_OR_TUNE_PARTITION")
    expected = {f"{r['race_date']}|{r['race_id']}|{r['horse_id']}" for r in train + tune}
    truth_rows_index = _meta_truth_index(relevant_truth, expected)
    truth = {key: int(row["win"]) for key, row in truth_rows_index.items()}
    model_names = sorted({name for row in train for name in row["model_probabilities"]})
    required_schema = {"probabilities": model_names, "ranks": model_names}
    if any(sorted(row["model_probabilities"]) != model_names or sorted(row["model_ranks"]) != model_names for row in matrix):
        raise ValueError("MODEL_FEATURE_SCHEMA_INCONSISTENT")
    categories = {key: sorted({row[key] for row in train}) for key in CATEGORICAL_CONTEXT}
    feature_names = ([f"prob:{name}" for name in model_names] + [f"rank:{name}" for name in model_names]
                     + ["market_probability", "disagreement_range", "disagreement_variance"] + list(NUMERIC_CONTEXT)
                     + [f"cat:{key}:{value}" for key in CATEGORICAL_CONTEXT for value in categories[key]])
    def encode(row):
        values = ([row["model_probabilities"].get(name, 0.0) for name in model_names]
                  + [1.0 / row["model_ranks"].get(name, 999) for name in model_names]
                  + [row["market_probability"] or 0.0, row["disagreement_range"], row["disagreement_variance"]]
                  + [row[key] or 0.0 for key in NUMERIC_CONTEXT]
                  + [1.0 if row[key] == value else 0.0 for key in CATEGORICAL_CONTEXT for value in categories[key]])
        return values
    usable_train = [r for r in train if (r["race_date"], r["race_id"], r["horse_id"]) in truth]
    encoded_train = [encode(r) for r in usable_train]
    correlation = _meta_correlation_prune(feature_names, encoded_train)
    kept_indices = [feature_names.index(name) for name in correlation["kept_features"]]
    kept_feature_names = correlation["kept_features"]
    pruned_train = [[row[idx] for idx in kept_indices] for row in encoded_train]
    family_sizes = defaultdict(int)
    for name in kept_feature_names:
        family_sizes[name.split(":", 1)[0]] += 1
    penalties = [l2 * family_sizes[name.split(":", 1)[0]] for name in kept_feature_names]
    bias, weights = _meta_fit_logistic(pruned_train, [truth[(r["race_date"], r["race_id"], r["horse_id"])] for r in usable_train], penalties)
    tune_raw = [
        (r, bias + sum(w * encode(r)[idx] for w, idx in zip(weights, kept_indices, strict=True)))
        for r in tune
        if (r["race_date"], r["race_id"], r["horse_id"]) in truth
    ]
    calibration_bias, calibration_weights = _meta_fit_logistic(
        [[raw] for _, raw in tune_raw],
        [truth[(r["race_date"], r["race_id"], r["horse_id"])] for r, _ in tune_raw],
        [l2],
    )
    tune_scored = [
        (r, _meta_sigmoid(calibration_bias + calibration_weights[0] * raw))
        for r, raw in tune_raw
    ]
    grouped = defaultdict(list)
    for row, probability in tune_scored:
        grouped[(row["race_date"], row["race_id"])].append((row, probability))
    best = None
    for threshold in threshold_grid:
        choices = [max(field, key=lambda pair: (pair[1], pair[0]["horse_id"])) for field in grouped.values()]
        choices = [pair for pair in choices if pair[1] >= threshold and (pair[0]["race_date"], pair[0]["race_id"], pair[0]["horse_id"]) in truth]
        score = (sum(truth[(r["race_date"], r["race_id"], r["horse_id"])] for r, _ in choices) / len(choices)) if choices else 0.0
        candidate = (score, -threshold, threshold)
        if best is None or candidate > best:
            best = candidate
    policy = {
        "schema_version": SCHEMA_VERSION, "policy_type": "CALIBRATED_LOGISTIC_WITH_ABSTAIN",
        "candidate_feature_names": feature_names, "feature_names": kept_feature_names,
        "model_names": model_names, "required_model_schema": required_schema, "categories": categories,
        "bias": bias, "weights": weights, "family_penalties": penalties,
        "train_only_correlation_control": correlation,
        "calibration": {"method": "PLATT_ON_PURGED_TUNE_DATES", "bias": calibration_bias, "slope": calibration_weights[0]},
        "threshold": best[2],
        "train_dates": split["train_dates"], "tune_dates": split["tune_dates"],
        "purged_dates": split["train_tune_purge_dates"] + split["tune_score_purge_dates"],
        "training_feature_hash": _meta_hash(train), "tune_feature_hash": _meta_hash(tune),
        "training_truth_hash": _meta_hash([truth_rows_index[key] for key in sorted(truth_rows_index) if key[0] in split["train_dates"]]),
        "tune_truth_hash": _meta_hash([truth_rows_index[key] for key in sorted(truth_rows_index) if key[0] in split["tune_dates"]]),
        "source_packet_hashes": sorted({row["packet_hash"] for row in train + tune}),
        "conditional_regions": PREDECLARED_REGIONS,
        "methodology": {"evidence_class": "PURGED_OOS_BACKTEST", "correlation_source": "TRAIN_ONLY",
                        "calibration_source": "PURGED_TUNE_ONLY", "region_boundaries": "PREDECLARED_FIXED",
                        "same_day_adaptation": False},
        "frozen_through_date": max(split["tune_dates"]), "paper_sim_only": True, "production_change_allowed": False,
    }
    return {**policy, "policy_hash": _meta_hash(policy)}


def freeze_meta_policy(policy):
    body = {key: value for key, value in policy.items() if key != "policy_hash"}
    if policy.get("policy_hash") != _meta_hash(body) or not policy.get("paper_sim_only") or policy.get("production_change_allowed"):
        raise ValueError("POLICY_FREEZE_INVALID")
    return json.loads(_meta_canonical(policy))


def _meta_score_field(policy, field):
    field = _meta_validate_field_rows(sorted(field, key=itemgetter("horse_id")))
    if any(sorted(row["model_probabilities"]) != policy["required_model_schema"]["probabilities"]
           or sorted(row["model_ranks"]) != policy["required_model_schema"]["ranks"] for row in field):
        raise ValueError("MODEL_FEATURE_SCHEMA_INCONSISTENT")
    encoded_rows = []
    for row in field:
        encoded_rows.append(
            [row["model_probabilities"][name] for name in policy["model_names"]]
            + [1.0 / row["model_ranks"][name] for name in policy["model_names"]]
            + [row["market_probability"] or 0.0, row["disagreement_range"], row["disagreement_variance"]]
            + [row[key] or 0.0 for key in NUMERIC_CONTEXT]
            + [1.0 if row[key] == value else 0.0 for key in CATEGORICAL_CONTEXT for value in policy["categories"][key]]
        )
    kept_indices = [policy["candidate_feature_names"].index(name) for name in policy["feature_names"]]
    scored = []
    for row, encoded in zip(field, encoded_rows, strict=True):
        raw = policy["bias"] + sum(
            weight * encoded[index] for weight, index in zip(policy["weights"], kept_indices, strict=True)
        )
        probability = _meta_sigmoid(
            policy["calibration"]["bias"] + policy["calibration"]["slope"] * raw
        )
        scored.append((probability, row["horse_id"], row))
    probability, _, candidate = max(scored)
    selected = candidate if probability >= policy["threshold"] else None
    return selected, probability, _meta_regions(candidate, policy["conditional_regions"])


def score_frozen_meta_policy(policy, matrix, score_dates):
    policy = freeze_meta_policy(policy)
    if not score_dates or any(date <= policy["frozen_through_date"] for date in score_dates):
        raise ValueError("SCORE_DATES_NOT_STRICTLY_AFTER_FREEZE")
    if any(row["race_date"] not in score_dates for row in matrix):
        raise ValueError("MATRIX_CONTAINS_NON_SCORE_DATE")
    if any(sorted(row["model_probabilities"]) != policy["required_model_schema"]["probabilities"]
           or sorted(row["model_ranks"]) != policy["required_model_schema"]["ranks"] for row in matrix):
        raise ValueError("MODEL_FEATURE_SCHEMA_INCONSISTENT")
    grouped = defaultdict(list)
    for row in matrix:
        grouped[(row["race_date"], row["race_id"])].append(row)
    records = []
    for (date, race_id), field in sorted(grouped.items()):
        field = sorted(field, key=itemgetter("horse_id"))
        selected, probability, regions = _meta_score_field(policy, field)
        contract = {"kind": "META", "policy": "META", "frozen_policy": policy}
        records.append(_meta_selection_record(
            date, race_id, "META", selected, probability=probability,
            policy_hash=policy["policy_hash"], regions=regions,
            governed_identities=[f"{candidate['race_date']}|{candidate['race_id']}|{candidate['horse_id']}" for candidate in field],
            field_rows=field, decision_contract=contract,
        ))
    return records


def write_immutable_meta_artifact(payload, root):
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    if payload.get("artifact_hash") != _meta_hash(body):
        raise ValueError("ARTIFACT_HASH_MISMATCH")
    path = Path(root) / f"{payload['artifact_hash']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            if path.read_bytes() == raw:
                return "VALIDATED_IDENTICAL", path
            raise FileExistsError(f"IMMUTABLE_CONFLICT:{path}") from None
        return "CREATED", path
    finally:
        tmp.unlink(missing_ok=True)


def _meta_load_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return value if isinstance(value, list) else value.get("rows", [])


def meta_cli_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True)
    parser.add_argument("--truth", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=500)
    args = parser.parse_args(argv)
    matrix = meta_build_feature_matrix(_meta_load_json(args.features))
    splits = make_purged_rolling_splits(matrix)
    truth = _meta_load_json(args.truth)
    runs = []
    for split in splits:
        policy = train_calibrated_meta_policy(matrix, truth, split)
        forward = [row for row in matrix if row["race_date"] in split["score_dates"]]
        score_truth = [
            row for row in truth
            if str(row.get("race_date") or row.get("date")) in split["score_dates"]
        ]
        transparent = select_transparent_candidates(forward, region_config=policy["conditional_regions"])
        records = score_frozen_meta_policy(policy, forward, split["score_dates"])
        runs.append({
            "split": split,
            "evidence_class": "PURGED_OOS_BACKTEST",
            "oos_score_dates": split["score_dates"],
            "policy": policy,
            "transparent_evaluation": evaluate_policy_records(
                transparent, score_truth, bootstrap_samples=args.bootstrap_samples
            ),
            "meta_evaluation": evaluate_policy_records(
                records, score_truth, bootstrap_samples=args.bootstrap_samples
            ),
        })
    body = {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": "PURGED_OOS_BACKTEST",
        "fresh_forward": False,
        "runs": runs,
        "safety": {"paper_sim_only": True, "production_changed": False},
    }
    artifact = {**body, "artifact_hash": _meta_hash(body)}
    status, path = write_immutable_meta_artifact(artifact, Path(args.output_root))
    print(json.dumps({"status": status, "path": str(path), "artifact_hash": artifact["artifact_hash"]}, indent=2))


if __name__ == "__main__":
    meta_cli_main()
