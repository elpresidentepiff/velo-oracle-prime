#!/usr/bin/env python3
"""Governed ACCA oracle research and local append-only PAPER/SIM packets.

The oracle report measures opportunity coverage with hindsight.  Forward packets
are a different artifact: a small, predeclared set of tickets frozen before the
first leg.  Neither artifact is an execution instruction.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import random
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_VERSION = "governed-acca-research-v1"
RULE_VERSION = "acca-forward-rule-v1"
SETTLEMENT_RULE = "NR_OR_WD_VOID_LEG_REDUCES_FOLD;TERMINAL_STARTER_LOSES;UNKNOWN_FAILS_CLOSED"
TERMINAL_LOSS_CODES = {"F", "PU", "UR", "BD", "RO", "REF", "DSQ"}
VOID_CODES = {"NR", "WD"}
APPROVED_ROLES = {"BANKER", "GLUE"}
MAX_LEGS_PER_MODEL_FAMILY = 1
RACING_TIMEZONE = "Europe/London"
NO_ACCA_REASON = "NO_PREDECLARED_TEMPLATE_QUALIFIED"
TEMPLATES = (
    {"template": "2_BANKER", "fold": 2, "roles": ("BANKER", "BANKER"), "experimental": False},
    {"template": "3_BANKER", "fold": 3, "roles": ("BANKER", "BANKER", "BANKER"), "experimental": False},
    {"template": "2_BANKER_GLUE", "fold": 2, "roles": ("BANKER", "GLUE"), "experimental": False},
    {"template": "3_BANKER_GLUE", "fold": 3, "roles": ("BANKER", "BANKER", "GLUE"), "experimental": False},
    *tuple(
        {"template": f"EXPERIMENTAL_{fold}_FOLD", "fold": fold, "roles": (), "experimental": True}
        for fold in range(4, 10)
    ),
)


def _template_contracts() -> list[dict[str, Any]]:
    return [
        {**template, "roles": list(template["roles"])}
        for template in TEMPLATES
    ]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _aware(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo is not None else None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_card_artifact(card_artifact_path: Path, race_date: str) -> dict[str, Any]:
    artifact_path = card_artifact_path.resolve()
    if not artifact_path.is_file():
        raise ValueError("AUTHORITATIVE_CARD_ARTIFACT_MISSING")
    raw = artifact_path.read_bytes()
    artifact_hash = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("AUTHORITATIVE_CARD_ARTIFACT_JSON_INVALID") from None
    if not isinstance(payload, dict) or payload.get("race_date") != race_date:
        raise ValueError("AUTHORITATIVE_CARD_RACE_DATE_MISMATCH")
    if payload.get("timezone") != RACING_TIMEZONE:
        raise ValueError("AUTHORITATIVE_CARD_TIMEZONE_MISMATCH")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or not str(provenance.get("source") or "").strip():
        raise ValueError("AUTHORITATIVE_CARD_PROVENANCE_REQUIRED")
    schedule = payload.get("races")
    if not isinstance(schedule, list) or not schedule:
        raise ValueError("AUTHORITATIVE_CARD_SCHEDULE_REQUIRED")
    normalized = []
    seen = set()
    for row in schedule:
        race_id = str(row.get("race_id") or "")
        off = _aware(row.get("off_ts"))
        if not race_id or race_id in seen or off is None:
            raise ValueError("AUTHORITATIVE_CARD_SCHEDULE_INVALID")
        if off.astimezone(ZoneInfo(RACING_TIMEZONE)).date().isoformat() != race_date:
            raise ValueError("CARD_OFF_NOT_ON_RACING_LOCAL_DATE")
        seen.add(race_id)
        normalized.append({"race_id": race_id, "off_ts": off.isoformat()})
    normalized.sort(key=lambda row: (row["off_ts"], row["race_id"]))
    schedule_hash = _hash(normalized)
    return {
        "artifact_path": str(artifact_path), "artifact_sha256": artifact_hash,
        "provenance": provenance, "race_schedule": normalized,
        "race_schedule_hash": schedule_hash, "first_off_ts": normalized[0]["off_ts"],
        "local_storage_semantics": "LOCAL_APPEND_ONLY_EXCLUSIVE_CREATE",
        "integrity_property": "TAMPER_EVIDENT_WHEN_ANCHORED_AND_REVALIDATED",
        "external_trusted_ledger_or_database_anchor": "NOT_PRESENT",
    }


def _revalidate_embedded_card_evidence(card_evidence: dict[str, Any], race_date: str) -> dict[str, Any]:
    if not isinstance(card_evidence, dict):
        raise ValueError("AUTHORITATIVE_CARD_EVIDENCE_REQUIRED")
    expected = _load_card_artifact(Path(str(card_evidence.get("artifact_path") or "")), race_date)
    if expected != card_evidence:
        raise ValueError("PACKET_CARD_EVIDENCE_NOT_DERIVED_FROM_ARTIFACT")
    return expected


def _truth_index(rows: Iterable[dict[str, Any]]) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, str]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    source_hashes: dict[str, str] = {}
    for row in rows:
        date = str(row.get("date") or row.get("run_date") or "")
        race_id = str(row.get("race_id") or "")
        horse_id = str(row.get("horse_id") or "")
        if not date or not race_id or not horse_id:
            raise ValueError("CANONICAL_IDENTITY_MISSING")
        if row.get("result_source_complete") is not True:
            raise ValueError(f"CANONICAL_RESULT_SOURCE_INCOMPLETE:{date}")
        source_hash = str(row.get("result_source_hash") or "")
        if not source_hash or (date in source_hashes and source_hashes[date] != source_hash):
            raise ValueError(f"CANONICAL_RESULT_SOURCE_HASH_CONFLICT:{date}")
        source_hashes[date] = source_hash
        key = (date, race_id, horse_id)
        if key in index and _canonical(index[key]) != _canonical(row):
            raise ValueError(f"CANONICAL_IDENTITY_CONFLICT:{date}:{race_id}:{horse_id}")
        index[key] = row
    return index, source_hashes


def _outcome(row: dict[str, Any]) -> str:
    if not isinstance(row, dict):
        return "UNKNOWN"
    code = str(row.get("subject_outcome_code") or row.get("position_text") or "").upper().strip()
    status = str(row.get("subject_outcome_status") or "").upper().strip()
    settlement = str(row.get("settlement_status") or "").upper().strip()
    non_runner = row.get("subject_is_non_runner")
    stake_void = row.get("stake_void")
    if code in VOID_CODES:
        if status != "NON_RUNNER" or settlement != "VOID" or non_runner is not True or stake_void is not True:
            return "UNRESOLVED_CONFLICT"
        return "VOID"
    if code in TERMINAL_LOSS_CODES:
        if status != "TERMINAL" or settlement != "SETTLED" or non_runner is not False or stake_void is not False:
            return "UNRESOLVED_CONFLICT"
        return "LOSS"
    if code.isdigit():
        if status != "FINISHED" or settlement != "SETTLED" or non_runner is not False or stake_void is not False:
            return "UNRESOLVED_CONFLICT"
        if row.get("win") is not (int(code) == 1):
            return "UNRESOLVED_CONFLICT"
        return "WIN" if int(code) == 1 else "LOSS"
    if code or status != "UNKNOWN" or settlement != "UNSETTLED" or non_runner is not False or stake_void is not False:
        return "UNRESOLVED_CONFLICT"
    if row.get("win") not in {False, None}:
        return "UNRESOLVED_CONFLICT"
    if status == "UNKNOWN":
        return "UNKNOWN"
    return "UNKNOWN"


def _validate_selection(
    selection: dict[str, Any], race_date: str, *, require_price: bool, require_probability: bool = True
) -> dict[str, Any]:
    race_id = str(selection.get("race_id") or "")
    horse_id = str(selection.get("horse_id") or "")
    if not race_id or not horse_id:
        raise ValueError("SELECTION_IDENTITY_MISSING")
    off = _aware(selection.get("off_ts"))
    selected_at = _aware(selection.get("selection_ts") or selection.get("snapshot_created_at"))
    if off is None or selected_at is None or selected_at >= off:
        raise ValueError(f"SELECTION_NOT_STRICTLY_PRE_OFF:{race_id}:{horse_id}")
    if off.astimezone(ZoneInfo(RACING_TIMEZONE)).date().isoformat() != race_date:
        raise ValueError(f"LEG_OFF_NOT_ON_RACING_LOCAL_DATE:{race_id}:{horse_id}")
    odds = _number(selection.get("captured_odds_dec"))
    price_ts = _aware(selection.get("odds_capture_ts")) if odds is not None else None
    price_valid = odds is not None and odds > 1 and price_ts is not None and price_ts < off
    price_source = str(selection.get("price_source") or "").strip()
    if price_valid and not price_source:
        price_valid = False
    if require_price and not price_valid:
        raise ValueError(f"CAPTURED_PRICE_NOT_STRICTLY_PRE_OFF:{race_id}:{horse_id}")
    if not price_valid:
        odds = None
        price_ts = None
    probability = _number(selection.get("probability"))
    if require_probability and (probability is None or probability < 0 or probability > 1):
        raise ValueError(f"SELECTION_PROBABILITY_INVALID:{race_id}:{horse_id}")
    return {
        **selection,
        "race_date": race_date,
        "race_id": race_id,
        "horse_id": horse_id,
        "off_ts": off.isoformat(),
        "selection_ts": selected_at.isoformat(),
        "captured_odds_dec": odds if odds is not None and odds > 1 else None,
        "odds_capture_ts": price_ts.isoformat() if price_ts is not None else None,
        "price_source": price_source if price_valid else None,
        "probability": probability,
    }


def build_oracle_ceiling(
    *, race_date: str, model_selections: Iterable[dict[str, Any]], canonical_rows: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Exhaust the historical union; this is explicitly not a selectable policy."""
    truth, source_hashes = _truth_index(canonical_rows)
    by_race: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for raw in model_selections:
        row = _validate_selection(raw, race_date, require_price=False, require_probability=False)
        key = (race_date, row["race_id"], row["horse_id"])
        if key not in truth:
            raise ValueError(f"ORACLE_TRUTH_MISSING:{row['race_id']}:{row['horse_id']}")
        existing = by_race[row["race_id"]].get(row["horse_id"])
        provenance = {
            "model_name": row.get("model_name"),
            "model_version": row.get("model_version"),
            "packet_hash": row.get("packet_hash"),
        }
        if existing is None:
            by_race[row["race_id"]][row["horse_id"]] = {**row, "model_provenance": [provenance]}
        else:
            existing["model_provenance"].append(provenance)
    races = sorted(by_race)
    fold_reports = []
    all_returns = 0.0
    total_tickets = 0
    winning_tickets = 0
    smallest_winning_fold = None
    for fold in range(2, min(9, len(races)) + 1):
        fold_total = fold_wins = 0
        fold_return = 0.0
        for race_ids in itertools.combinations(races, fold):
            pools = [sorted(by_race[rid].values(), key=lambda x: x["horse_id"]) for rid in race_ids]
            for legs in itertools.product(*pools):
                fold_total += 1
                outcomes = [_outcome(truth[(race_date, leg["race_id"], leg["horse_id"])]) for leg in legs]
                if "UNKNOWN" in outcomes:
                    continue
                active = [leg for leg, outcome in zip(legs, outcomes, strict=True) if outcome != "VOID"]
                won = bool(active) and all(outcome in {"WIN", "VOID"} for outcome in outcomes)
                if not won:
                    continue
                fold_wins += 1
                if smallest_winning_fold is None:
                    smallest_winning_fold = fold
                prices = [leg.get("captured_odds_dec") for leg in active]
                if prices and all(price is not None for price in prices):
                    fold_return += math.prod(float(price) for price in prices)
        total_tickets += fold_total
        winning_tickets += fold_wins
        all_returns += fold_return
        fold_reports.append(
            {
                "fold": fold,
                "tickets": fold_total,
                "winning_tickets": fold_wins,
                "winning_ticket_pct": fold_wins / fold_total if fold_total else None,
                "genuine_captured_price_return": fold_return,
            }
        )
    body = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "ORACLE_CEILING_OPPORTUNITY_COVERAGE",
        "race_date": race_date,
        "selectability_claim": False,
        "warning": "HINDSIGHT COMPLETE SEARCH; NOT A FORWARD TICKET OR STRATEGY",
        "eligible_races": len(races),
        "candidates_per_race": {race_id: len(by_race[race_id]) for race_id in races},
        "total_combinatorial_tickets": total_tickets,
        "smallest_winning_fold": smallest_winning_fold,
        "winning_tickets": winning_tickets,
        "winning_ticket_pct": winning_tickets / total_tickets if total_tickets else None,
        "complete_search_outlay": float(total_tickets),
        "genuine_captured_price_return": all_returns,
        "net_complete_search_result": all_returns - total_tickets,
        "folds": fold_reports,
        "result_source_hash": source_hashes.get(race_date),
        "safety": {"paper_sim_only": True, "execution_allowed": False, "promotion_authorized": False},
    }
    return {**body, "report_hash": _hash(body)}


def _role_match(combo: tuple[dict[str, Any], ...], required: tuple[str, ...]) -> bool:
    if not required:
        return all(leg.get("role") in APPROVED_ROLES for leg in combo)
    actual = sorted(str(leg.get("role") or "") for leg in combo)
    return actual == sorted(required)


def _correlation(combo: tuple[dict[str, Any], ...]) -> tuple[list[str], float]:
    flags = set()
    attributes = {
        "MODEL_FAMILY": "model_family",
        "VENUE": "venue",
        "RACE_TYPE": "race_type",
        "TRAINER": "trainer_id",
        "JOCKEY": "jockey_id",
    }
    for left, right in itertools.combinations(combo, 2):
        for label, key in attributes.items():
            if left.get(key) and left.get(key) == right.get(key):
                flags.add(f"SHARED_{label}")
        if left.get("meeting_id") and left.get("meeting_id") == right.get("meeting_id"):
            flags.add("SAME_MEETING")
    effective = max(1.0, len(combo) - 0.25 * len(flags))
    return sorted(flags), round(effective, 4)


def _ticket(template: dict[str, Any], combo: tuple[dict[str, Any], ...], rule_version: str) -> dict[str, Any]:
    flags, effective = _correlation(combo)
    raw_probability = math.prod(float(leg["probability"]) for leg in combo)
    stress_score = min(1.0, 0.1 * len(flags))
    product_price = math.prod(float(leg["captured_odds_dec"]) for leg in combo)
    legs = [
        {
            key: leg.get(key)
            for key in (
                "race_id", "horse_id", "horse", "off_ts", "selection_ts", "role", "model_name", "model_version",
                "model_family", "probability", "captured_odds_dec", "odds_capture_ts", "price_source",
                "venue", "meeting_id", "race_type", "trainer_id", "jockey_id",
                "comparators",
            )
        }
        for leg in combo
    ]
    identity = {"template": template["template"], "rule_version": rule_version, "legs": legs}
    return {
        "ticket_id": _hash(identity),
        "template": template["template"],
        "template_version": rule_version,
        "experimental": template["experimental"],
        "nominal_fold": len(legs),
        "legs": legs,
        "product_price": product_price,
        "independence_product_reference": raw_probability,
        "independence_reference_status": "UNVALIDATED_INDEPENDENCE_REFERENCE",
        "correlation_adjusted_probability": None,
        "correlation_adjustment_status": "UNAVAILABLE_UNCALIBRATED",
        "correlation_stress_score": stress_score,
        "correlation_flags": flags,
        "effective_independent_legs": effective,
        "effective_independent_legs_status": "HEURISTIC_STRESS_ONLY_NOT_CALIBRATED",
        "paper_sim_only": True,
    }


def _baseline_leg(leg: dict[str, Any], name: str) -> dict[str, Any] | None:
    value = (leg.get("comparators") or {}).get(name)
    if not isinstance(value, dict) or not value.get("horse_id"):
        return None
    return {"race_id": leg["race_id"], "horse_id": str(value["horse_id"]), "source": name}


def _identical_card_baselines(ticket: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name in ("market_favourite", "production", "random_market_weighted", "top_probability"):
        legs = [_baseline_leg(leg, name) for leg in ticket["legs"]]
        out[name] = {
            "available": all(legs),
            "race_ids": [leg["race_id"] for leg in ticket["legs"]],
            "legs": legs if all(legs) else [],
        }
    return out


def build_forward_acca_packet(
    *, race_date: str, candidates: Iterable[dict[str, Any]], card_artifact_path: Path, max_tickets: int = 12,
    rule_version: str = RULE_VERSION,
) -> dict[str, Any]:
    if max_tickets < 0:
        raise ValueError("TICKET_CAP_INVALID")
    now = _utc_now()
    if now.tzinfo is None:
        raise ValueError("TRUSTED_CLOCK_MUST_BE_AWARE")
    local_now = now.astimezone(ZoneInfo(RACING_TIMEZONE))
    if local_now.date().isoformat() != race_date:
        raise ValueError("HISTORICAL_FORWARD_PACKET_REFUSED_USE_ORACLE")
    card = _load_card_artifact(card_artifact_path, race_date)
    first_off = _aware(card["first_off_ts"])
    if now >= first_off:
        raise ValueError("PACKET_NOT_FROZEN_BEFORE_AUTHORITATIVE_FIRST_OFF")
    validated = [_validate_selection(row, race_date, require_price=True) for row in candidates]
    schedule = {row["race_id"]: row["off_ts"] for row in card["race_schedule"]}
    for row in validated:
        if schedule.get(row["race_id"]) != row["off_ts"]:
            raise ValueError(f"LEG_NOT_IN_AUTHORITATIVE_CARD_SCHEDULE:{row['race_id']}")
    if validated:
        selections = [_aware(row["selection_ts"]) for row in validated]
        captures = [_aware(row["odds_capture_ts"]) for row in validated]
        offs = [_aware(row["off_ts"]) for row in validated]
        if now >= min(offs):
            raise ValueError("PACKET_NOT_FROZEN_BEFORE_FIRST_LEG")
        if any(stamp > now for stamp in selections):
            raise ValueError("SELECTION_TIMESTAMP_AFTER_PACKET")
        if any(stamp > now for stamp in captures):
            raise ValueError("PRICE_TIMESTAMP_AFTER_PACKET")
    identities = set()
    for row in validated:
        identity = (row["race_id"], row["horse_id"])
        if identity in identities:
            raise ValueError(f"DUPLICATE_CANDIDATE_IDENTITY:{identity[0]}:{identity[1]}")
        identities.add(identity)
        if row.get("role") not in APPROVED_ROLES:
            raise ValueError(f"FORWARD_ROLE_NOT_APPROVED:{row.get('role')}")
        if not row.get("model_name") or not row.get("model_version") or not row.get("model_family"):
            raise ValueError("MODEL_PROVENANCE_INCOMPLETE")
    validated.sort(key=lambda row: (-float(row.get("score", row["probability"])), row["race_id"], row["horse_id"]))
    tickets = []
    for template in TEMPLATES:
        if len(tickets) >= max_tickets:
            break
        for combo in itertools.combinations(validated, template["fold"]):
            if len({leg["race_id"] for leg in combo}) != len(combo) or not _role_match(combo, template["roles"]):
                continue
            family_counts = defaultdict(int)
            for leg in combo:
                family_counts[str(leg["model_family"])] += 1
            if max(family_counts.values(), default=0) > MAX_LEGS_PER_MODEL_FAMILY:
                continue
            ticket = _ticket(template, combo, rule_version)
            ticket["identical_card_baselines"] = _identical_card_baselines(ticket)
            tickets.append(ticket)
            break
    status = "TICKETS_FROZEN" if tickets else "NO_ACCA"
    identity = {
        "schema_version": SCHEMA_VERSION,
        "race_date": race_date,
        "rule_version": rule_version,
        "templates": _template_contracts(),
        "max_tickets": max_tickets,
        "max_legs_per_model_family": MAX_LEGS_PER_MODEL_FAMILY,
    }
    body = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "FORWARD_EXECUTABLE_SHADOW_TICKETS",
        "race_date": race_date,
        "generated_at": now.isoformat(),
        "clock_provenance": "SYSTEM_UTC_INTERNAL",
        "racing_timezone": RACING_TIMEZONE,
        "operational_race_date": local_now.date().isoformat(),
        "authoritative_card_evidence": card,
        "evidence_class": "GENUINELY_FORWARD" if validated else "GENUINELY_FORWARD_ZERO_TICKET_DAY",
        "status": status,
        "packet_identity": identity,
        "packet_identity_hash": _hash(identity),
        "rule_version": rule_version,
        "settlement_rule": SETTLEMENT_RULE,
        "templates": _template_contracts(),
        "daily_ticket_cap": max_tickets,
        "max_legs_per_model_family": MAX_LEGS_PER_MODEL_FAMILY,
        "tickets": tickets,
        "no_acca_reason": NO_ACCA_REASON if not tickets else None,
        "research_declarations": {
            "holdout_required": True,
            "multiple_testing_correction": "BENJAMINI_HOCHBERG_OR_MORE_CONSERVATIVE",
            "identical_card_baselines_required": True,
            "minimum_forward_days_before_promotion_discussion": 30,
            "operator_decision_required": True,
        },
        "safety": {
            "paper_sim_only": True, "execution_allowed": False, "bets_placed": False,
            "stakes_generated": False, "production_learning_allowed": False, "promotion_authorized": False,
        },
        "storage_governance": {
            "local_semantics": "LOCAL_APPEND_ONLY_EXCLUSIVE_CREATE",
            "integrity": "TAMPER_EVIDENT_WHEN_ANCHORED_AND_REVALIDATED",
            "external_trusted_ledger_or_database_anchor": "NOT_PRESENT",
        },
    }
    return {**body, "packet_hash": _hash(body)}


def _validate_packet(packet: dict[str, Any]) -> None:
    body = {key: value for key, value in packet.items() if key != "packet_hash"}
    if packet.get("packet_hash") != _hash(body):
        raise ValueError("PACKET_HASH_MISMATCH")
    identity = {
        "schema_version": SCHEMA_VERSION,
        "race_date": packet.get("race_date"),
        "rule_version": packet.get("rule_version"),
        "templates": _template_contracts(),
        "max_tickets": packet.get("daily_ticket_cap"),
        "max_legs_per_model_family": MAX_LEGS_PER_MODEL_FAMILY,
    }
    if packet.get("packet_identity") != identity or packet.get("packet_identity_hash") != _hash(identity):
        raise ValueError("PACKET_IDENTITY_MISMATCH")
    if packet.get("safety", {}).get("paper_sim_only") is not True or packet.get("safety", {}).get("execution_allowed") is not False:
        raise ValueError("PACKET_SAFETY_CONTRACT_INVALID")
    if len(packet.get("tickets", [])) > packet.get("daily_ticket_cap", -1):
        raise ValueError("PACKET_TICKET_CAP_BREACH")
    tickets = packet.get("tickets", [])
    status = packet.get("status")
    reason = packet.get("no_acca_reason")
    if tickets:
        if status != "TICKETS_FROZEN" or reason is not None:
            raise ValueError("PACKET_STATUS_TICKETS_REASON_CONTRACT_INVALID")
    elif status != "NO_ACCA" or reason != NO_ACCA_REASON:
        raise ValueError("PACKET_STATUS_TICKETS_REASON_CONTRACT_INVALID")
    generated = _aware(packet.get("generated_at"))
    if packet.get("clock_provenance") != "SYSTEM_UTC_INTERNAL":
        raise ValueError("PACKET_CLOCK_PROVENANCE_INVALID")
    if packet.get("racing_timezone") != RACING_TIMEZONE:
        raise ValueError("PACKET_RACING_TIMEZONE_INVALID")
    card = _revalidate_embedded_card_evidence(packet.get("authoritative_card_evidence"), str(packet.get("race_date") or ""))
    if generated is None or generated >= _aware(card["first_off_ts"]):
        raise ValueError("PACKET_AFTER_AUTHORITATIVE_FIRST_OFF")
    if generated.astimezone(ZoneInfo(RACING_TIMEZONE)).date().isoformat() != packet.get("operational_race_date"):
        raise ValueError("PACKET_OPERATIONAL_DATE_MISMATCH")
    for ticket in packet.get("tickets", []):
        legs = ticket.get("legs", [])
        if len({leg.get("race_id") for leg in legs}) != len(legs):
            raise ValueError("TICKET_DUPLICATE_RACE")
        families = [leg.get("model_family") for leg in legs]
        if any(families.count(family) > MAX_LEGS_PER_MODEL_FAMILY for family in set(families)):
            raise ValueError("TICKET_MODEL_FAMILY_CAP_BREACH")
        if generated is None or any(generated >= _aware(leg.get("off_ts")) for leg in legs):
            raise ValueError("PACKET_TIME_LEAKAGE")
        for leg in legs:
            validated = _validate_selection(leg, packet["race_date"], require_price=True)
            schedule = {row["race_id"]: row["off_ts"] for row in card["race_schedule"]}
            if schedule.get(str(leg.get("race_id") or "")) != validated["off_ts"]:
                raise ValueError("TICKET_LEG_NOT_IN_DERIVED_CARD_SCHEDULE")
            if _aware(validated["selection_ts"]) > generated or _aware(validated["odds_capture_ts"]) > generated:
                raise ValueError("PACKET_EVIDENCE_AFTER_FREEZE")
        expected = _ticket(
            next(template for template in TEMPLATES if template["template"] == ticket.get("template")),
            tuple(legs), packet["rule_version"],
        )
        if any(ticket.get(key) != expected.get(key) for key in (
            "ticket_id", "product_price", "independence_product_reference", "independence_reference_status",
            "correlation_adjusted_probability",
            "correlation_adjustment_status", "correlation_stress_score", "correlation_flags",
            "effective_independent_legs", "effective_independent_legs_status",
        )):
            raise ValueError("TICKET_DERIVATION_MISMATCH")


def _canonical_truth_artifact(result_source_artifact_path: Path, race_date: str | None = None) -> dict[str, Any]:
    source_path = result_source_artifact_path.resolve()
    if not source_path.is_file():
        raise ValueError("RESULT_SOURCE_ARTIFACT_MISSING")
    raw = source_path.read_bytes()
    source_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("RESULT_SOURCE_ARTIFACT_JSON_INVALID") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("result_source"), dict):
        raise ValueError("RESULT_SOURCE_ARTIFACT_SCHEMA_INVALID")
    date = str(payload.get("race_date") or "")
    if not date or (race_date is not None and date != race_date):
        raise ValueError("RESULT_SOURCE_RACE_DATE_MISMATCH")
    if payload.get("complete") is not True:
        raise ValueError("RESULT_SOURCE_NOT_COMPLETE")
    metadata = payload["result_source"]
    if not str(metadata.get("name") or "").strip():
        raise ValueError("RESULT_SOURCE_METADATA_INVALID")
    included_hash = metadata.get("source_file_sha256")
    if included_hash is not None and (len(str(included_hash)) != 64 or included_hash != source_sha256):
        raise ValueError("RESULT_SOURCE_INCLUDED_HASH_MISMATCH")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("RESULT_SOURCE_ROWS_REQUIRED")
    row_list = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise ValueError("RESULT_SOURCE_ROW_INVALID")
        row = dict(raw_row)
        row["date"] = date
        row["result_source_complete"] = True
        row["result_source_hash"] = source_sha256
        row_list.append(row)
    row_list.sort(key=lambda row: (str(row.get("race_id")), str(row.get("horse_id"))))
    _truth_index(row_list)
    body = {
        "schema_version": SCHEMA_VERSION, "artifact_type": "AUTHORITATIVE_CANONICAL_ACCA_TRUTH",
        "race_date": date, "result_source_hash": source_sha256,
        "result_source_artifact_path": str(source_path), "result_source_artifact_sha256": source_sha256,
        "result_source_metadata": metadata,
        "canonical_rows": row_list, "canonical_rows_content_hash": _hash(row_list),
        "local_storage_semantics": "LOCAL_APPEND_ONLY_EXCLUSIVE_CREATE",
        "integrity_property": "TAMPER_EVIDENT_WHEN_SOURCE_AND_ANCHORS_REVALIDATED",
        "external_trusted_ledger_or_database_anchor": "NOT_PRESENT",
    }
    return {**body, "artifact_hash": _hash(body)}


def write_canonical_truth_artifact(result_source_artifact_path: Path, evidence_root: Path) -> tuple[str, Path]:
    artifact = _canonical_truth_artifact(result_source_artifact_path)
    path = evidence_root / "truth" / artifact["race_date"] / "canonical_truth.json"
    return _atomic_immutable_json(artifact, path), path


def _load_verified_anchors(packet: dict[str, Any], evidence_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    race_date = str(packet.get("race_date") or "")
    lock_path = evidence_root / "packets" / race_date / "day_lock.json"
    if not lock_path.is_file():
        raise ValueError("AUTHORITATIVE_DAY_LOCK_MISSING")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock_body = {key: value for key, value in lock.items() if key != "manifest_hash"}
    if lock.get("manifest_hash") != _hash(lock_body):
        raise ValueError("AUTHORITATIVE_DAY_LOCK_HASH_MISMATCH")
    if (
        lock.get("race_date") != race_date
        or lock.get("packet_hash") != packet.get("packet_hash")
        or lock.get("packet_identity_hash") != packet.get("packet_identity_hash")
    ):
        raise ValueError("AUTHORITATIVE_DAY_LOCK_PACKET_MISMATCH")
    packet_path = Path(str(lock.get("authoritative_packet_path") or ""))
    if not packet_path.is_file():
        raise ValueError("AUTHORITATIVE_FROZEN_PACKET_MISSING")
    persisted_packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if persisted_packet != packet:
        raise ValueError("AUTHORITATIVE_FROZEN_PACKET_BODY_MISMATCH")
    _validate_packet(persisted_packet)
    truth_path = evidence_root / "truth" / race_date / "canonical_truth.json"
    if not truth_path.is_file():
        raise ValueError("AUTHORITATIVE_CANONICAL_TRUTH_MISSING")
    truth_artifact = json.loads(truth_path.read_text(encoding="utf-8"))
    truth_body = {key: value for key, value in truth_artifact.items() if key != "artifact_hash"}
    if truth_artifact.get("artifact_hash") != _hash(truth_body):
        raise ValueError("AUTHORITATIVE_CANONICAL_TRUTH_HASH_MISMATCH")
    expected_truth = _canonical_truth_artifact(Path(str(truth_artifact.get("result_source_artifact_path") or "")), race_date)
    if truth_artifact != expected_truth:
        raise ValueError("AUTHORITATIVE_CANONICAL_TRUTH_BODY_MISMATCH")
    anchors = {
        "day_lock_path": str(lock_path.resolve()), "day_lock_manifest_hash": lock["manifest_hash"],
        "packet_path": str(packet_path.resolve()), "packet_hash": packet["packet_hash"],
        "canonical_truth_path": str(truth_path.resolve()),
        "canonical_truth_artifact_hash": truth_artifact["artifact_hash"],
        "canonical_rows_content_hash": truth_artifact["canonical_rows_content_hash"],
        "result_source_hash": truth_artifact["result_source_hash"],
    }
    return anchors, truth_artifact["canonical_rows"]


def settle_forward_packet(packet: dict[str, Any], *, evidence_root: Path) -> dict[str, Any]:
    _validate_packet(packet)
    anchors, canonical_rows = _load_verified_anchors(packet, evidence_root)
    truth, source_hashes = _truth_index(canonical_rows)
    date = packet["race_date"]
    settlements = []
    for ticket in packet.get("tickets", []):
        outcomes = []
        active_prices = []
        for leg in ticket["legs"]:
            row = truth.get((date, str(leg["race_id"]), str(leg["horse_id"])))
            outcome = _outcome(row) if row is not None else "UNKNOWN"
            outcomes.append({"race_id": leg["race_id"], "horse_id": leg["horse_id"], "outcome": outcome})
            if outcome != "VOID":
                active_prices.append(float(leg["captured_odds_dec"]))
        codes = [row["outcome"] for row in outcomes]
        if any(code in {"UNKNOWN", "UNRESOLVED_CONFLICT"} for code in codes):
            status, returned = "UNRESOLVED", None
        elif "LOSS" in codes:
            status, returned = "LOST", 0.0
        elif not active_prices:
            status, returned = "VOID", 1.0
        else:
            status, returned = "WON", math.prod(active_prices)
        baseline_settlements = {}
        for name, baseline in ticket.get("identical_card_baselines", {}).items():
            if baseline.get("available") is not True:
                baseline_settlements[name] = {"status": "UNAVAILABLE", "return": None, "profit": None}
                continue
            baseline_codes = []
            for leg in baseline.get("legs", []):
                row = truth.get((date, str(leg.get("race_id")), str(leg.get("horse_id"))))
                baseline_codes.append(_outcome(row) if row is not None else "UNKNOWN")
            if any(code in {"UNKNOWN", "UNRESOLVED_CONFLICT"} for code in baseline_codes):
                baseline_status, baseline_return = "UNRESOLVED", None
            elif "LOSS" in baseline_codes:
                baseline_status, baseline_return = "LOST", 0.0
            elif not [code for code in baseline_codes if code != "VOID"]:
                baseline_status, baseline_return = "VOID", 1.0
            else:
                # Comparator prices are deliberately not borrowed from the selected
                # ticket.  A result can be compared for hit rate while price/P&L
                # remains unavailable until its own frozen price is supplied.
                baseline_status, baseline_return = "WON_UNPRICED", None
            baseline_settlements[name] = {
                "status": baseline_status,
                "return": baseline_return,
                "profit": None if baseline_return is None else baseline_return - 1.0,
            }
        settlements.append(
            {
                "ticket_id": ticket["ticket_id"], "template": ticket["template"], "status": status,
                "nominal_fold": len(outcomes), "settled_fold": len(active_prices), "leg_outcomes": outcomes,
                "stake": 1.0, "return": returned, "profit": None if returned is None else returned - 1.0,
                "effective_independent_legs": ticket["effective_independent_legs"],
                "identical_card_baselines": baseline_settlements,
            }
        )
    settlement_identity = {
        "schema_version": SCHEMA_VERSION,
        "race_date": date,
        "packet_hash": packet["packet_hash"],
        "packet_identity_hash": packet["packet_identity_hash"],
        "result_source_hash": source_hashes.get(date),
        "settlement_rule": SETTLEMENT_RULE,
        "ticket_settlements_hash": _hash(settlements),
    }
    body = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "FORWARD_ACCA_SETTLEMENT",
        "evidence_anchors": anchors,
        "settlement_identity": settlement_identity,
        "settlement_identity_hash": _hash(settlement_identity),
        "race_date": date,
        "packet_hash": packet["packet_hash"],
        "packet_identity_hash": packet["packet_identity_hash"],
        "packet_generated_at": packet["generated_at"],
        "result_source_hash": source_hashes.get(date),
        "settlement_rule": SETTLEMENT_RULE,
        "status": "NO_ACCA" if packet["status"] == "NO_ACCA" else (
            "UNRESOLVED" if any(row["status"] == "UNRESOLVED" for row in settlements) else "SETTLED"
        ),
        "tickets": settlements,
        "safety": {"paper_sim_only": True, "execution_allowed": False, "promotion_authorized": False},
        "storage_governance": {
            "local_semantics": "LOCAL_APPEND_ONLY_EXCLUSIVE_CREATE",
            "integrity": "TAMPER_EVIDENT_WHEN_ANCHORED_AND_REVALIDATED",
            "external_trusted_ledger_or_database_anchor": "NOT_PRESENT",
        },
    }
    return {**body, "settlement_hash": _hash(body)}


def _validate_settlement(settlement: dict[str, Any], evidence_root: Path) -> None:
    body = {key: value for key, value in settlement.items() if key != "settlement_hash"}
    if settlement.get("settlement_hash") != _hash(body):
        raise ValueError("SETTLEMENT_HASH_MISMATCH")
    expected_identity = {
        "schema_version": SCHEMA_VERSION,
        "race_date": settlement.get("race_date"),
        "packet_hash": settlement.get("packet_hash"),
        "packet_identity_hash": settlement.get("packet_identity_hash"),
        "result_source_hash": settlement.get("result_source_hash"),
        "settlement_rule": settlement.get("settlement_rule"),
        "ticket_settlements_hash": _hash(settlement.get("tickets")),
    }
    if (
        settlement.get("settlement_identity") != expected_identity
        or settlement.get("settlement_identity_hash") != _hash(expected_identity)
    ):
        raise ValueError("SETTLEMENT_IDENTITY_MISMATCH")
    if settlement.get("safety", {}).get("paper_sim_only") is not True:
        raise ValueError("SETTLEMENT_SAFETY_INVALID")
    race_date = str(settlement.get("race_date") or "")
    lock_path = evidence_root / "packets" / race_date / "day_lock.json"
    truth_path = evidence_root / "truth" / race_date / "canonical_truth.json"
    if not lock_path.is_file() or not truth_path.is_file():
        raise ValueError("SETTLEMENT_AUTHORITATIVE_EVIDENCE_MISSING")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    packet_path = Path(str(lock.get("authoritative_packet_path") or ""))
    if not packet_path.is_file():
        raise ValueError("SETTLEMENT_FROZEN_PACKET_MISSING")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    expected = settle_forward_packet(packet, evidence_root=evidence_root)
    if expected != settlement:
        raise ValueError("SETTLEMENT_NOT_REPRODUCIBLE_FROM_ANCHORED_EVIDENCE")


def _bh_adjust(p_values: list[float]) -> list[float]:
    count = len(p_values)
    adjusted = [1.0] * count
    running = 1.0
    for rank, index in reversed(list(enumerate(sorted(range(count), key=lambda i: p_values[i]), start=1))):
        running = min(running, p_values[index] * count / rank)
        adjusted[index] = min(1.0, running)
    return adjusted


def _sign_flip_p_value(day_profits: dict[str, float], *, seed: int, samples: int) -> float | None:
    values = list(day_profits.values())
    if not values:
        return None
    observed = sum(values) / len(values)
    rng = random.Random(seed)
    exceed = 1
    for _ in range(samples):
        statistic = sum(value * (1 if rng.random() >= 0.5 else -1) for value in values) / len(values)
        exceed += int(statistic >= observed)
    return exceed / (samples + 1)


def _settlement_artifact_path(settlement: dict[str, Any], evidence_root: Path) -> Path:
    identity = _hash({"packet_hash": settlement.get("packet_hash"), "result_source_hash": settlement.get("result_source_hash")})
    return evidence_root / "settlements" / settlement["race_date"] / f"{identity}.json"


def build_holdout_multiplicity_evidence(
    *, development_dates: Iterable[str], holdout_dates: Iterable[str],
    predeclared_hypotheses: Iterable[dict[str, Any]], settlements: Iterable[dict[str, Any]],
    evidence_root: Path, resampling_samples: int = 4096, resampling_seed: int = 1981,
) -> dict[str, Any]:
    development = sorted(set(development_dates))
    holdout = sorted(set(holdout_dates))
    if not development or not holdout:
        raise ValueError("DEVELOPMENT_AND_HOLDOUT_DATES_REQUIRED")
    if set(development) & set(holdout) or max(development) >= min(holdout):
        raise ValueError("DEVELOPMENT_HOLDOUT_OVERLAP_OR_ORDER_INVALID")
    hypotheses = sorted((dict(row) for row in predeclared_hypotheses), key=lambda row: str(row.get("hypothesis_id")))
    if not hypotheses or any(not row.get("hypothesis_id") or not row.get("template") for row in hypotheses):
        raise ValueError("PREDECLARED_HYPOTHESIS_INVALID")
    if len({row["hypothesis_id"] for row in hypotheses}) != len(hypotheses):
        raise ValueError("PREDECLARED_HYPOTHESIS_DUPLICATE")
    for row in hypotheses:
        declared = _aware(row.get("predeclared_at"))
        if declared is None or declared.date().isoformat() >= min(holdout):
            raise ValueError("HYPOTHESIS_NOT_PREDECLARED_BEFORE_HOLDOUT")
    days = {}
    for settlement in settlements:
        _validate_settlement(settlement, evidence_root)
        date = str(settlement.get("race_date") or "")
        if date in days and days[date]["settlement_hash"] != settlement["settlement_hash"]:
            raise ValueError(f"CONFLICTING_SETTLEMENT_DAY:{date}")
        days[date] = settlement
    if any(date not in days for date in holdout):
        raise ValueError("HOLDOUT_SETTLEMENT_COVERAGE_INCOMPLETE")
    settlement_artifacts = []
    for date in holdout:
        path = _settlement_artifact_path(days[date], evidence_root)
        if not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != days[date]:
            raise ValueError(f"HOLDOUT_SETTLEMENT_NOT_IMMUTABLY_PERSISTED:{date}")
        settlement_artifacts.append({"race_date": date, "path": str(path.resolve()), "settlement_hash": days[date]["settlement_hash"]})
    metrics = []
    p_values = []
    for index, hypothesis in enumerate(hypotheses):
        template = hypothesis["template"]
        tickets = [
            (date, ticket)
            for date in holdout
            for ticket in days[date].get("tickets", [])
            if ticket.get("template") == template and ticket.get("status") in {"WON", "LOST"}
        ]
        profits = [float(ticket["profit"]) for _, ticket in tickets]
        by_day = defaultdict(float)
        for date, ticket in tickets:
            by_day[date] += float(ticket["profit"])
        p_value = _sign_flip_p_value(by_day, seed=resampling_seed + index, samples=resampling_samples)
        p_values.append(1.0 if p_value is None else p_value)
        metrics.append(
            {
                "hypothesis_id": hypothesis["hypothesis_id"], "template": template,
                "holdout_days": len(holdout), "ticket_days": len(by_day), "tickets": len(tickets),
                "wins": sum(ticket["status"] == "WON" for _, ticket in tickets),
                "profit": sum(profits), "roi": sum(profits) / len(profits) if profits else None,
                "resampling_statistic": "ONE_SIDED_DAY_BLOCK_SIGN_FLIP_MEAN_PROFIT",
                "raw_p_value": p_value,
            }
        )
    adjusted = _bh_adjust(p_values)
    for row, value in zip(metrics, adjusted, strict=True):
        row["bh_adjusted_p_value"] = value if row["raw_p_value"] is not None else None
    methodology = {
        "split": "EARLIER_DEVELOPMENT_LATER_UNTOUCHED_HOLDOUT",
        "no_tuning_on_holdout": True,
        "multiplicity_method": "BENJAMINI_HOCHBERG",
        "resampling_samples": resampling_samples,
        "resampling_seed": resampling_seed,
    }
    identity = {
        "schema_version": SCHEMA_VERSION,
        "development_dates": development,
        "holdout_dates": holdout,
        "predeclared_hypotheses": hypotheses,
        "settlement_hashes": [days[date]["settlement_hash"] for date in holdout],
        "settlement_artifacts": settlement_artifacts,
        "methodology": methodology,
    }
    body = {
        "schema_version": SCHEMA_VERSION, "artifact_type": "ACCA_HOLDOUT_MULTIPLICITY_EVIDENCE",
        "evidence_identity": identity, "evidence_identity_hash": _hash(identity),
        "development_dates": development, "holdout_dates": holdout,
        "hypothesis_count": len(hypotheses), "predeclared_hypotheses": hypotheses,
        "settlement_artifacts": settlement_artifacts,
        "methodology": methodology, "metrics": metrics,
        "safety": {"paper_sim_only": True, "promotion_authorized": False, "operator_decision_required": True},
        "storage_governance": {
            "local_semantics": "LOCAL_APPEND_ONLY_EXCLUSIVE_CREATE",
            "integrity": "TAMPER_EVIDENT_WHEN_ANCHORED_AND_REVALIDATED",
            "external_trusted_ledger_or_database_anchor": "NOT_PRESENT",
        },
    }
    return {**body, "evidence_hash": _hash(body)}


def _validate_holdout_evidence(evidence: dict[str, Any], evidence_root: Path) -> None:
    body = {key: value for key, value in evidence.items() if key != "evidence_hash"}
    if evidence.get("evidence_hash") != _hash(body):
        raise ValueError("HOLDOUT_EVIDENCE_HASH_MISMATCH")
    identity = evidence.get("evidence_identity")
    if evidence.get("evidence_identity_hash") != _hash(identity):
        raise ValueError("HOLDOUT_EVIDENCE_IDENTITY_MISMATCH")
    settlements = []
    for artifact in identity.get("settlement_artifacts", []):
        path = Path(str(artifact.get("path") or ""))
        if not path.is_file():
            raise ValueError("HOLDOUT_SETTLEMENT_ARTIFACT_MISSING")
        settlement = json.loads(path.read_text(encoding="utf-8"))
        if settlement.get("settlement_hash") != artifact.get("settlement_hash"):
            raise ValueError("HOLDOUT_SETTLEMENT_ARTIFACT_HASH_MISMATCH")
        settlements.append(settlement)
    expected = build_holdout_multiplicity_evidence(
        development_dates=identity["development_dates"], holdout_dates=identity["holdout_dates"],
        predeclared_hypotheses=identity["predeclared_hypotheses"], settlements=settlements,
        evidence_root=evidence_root, resampling_samples=identity["methodology"]["resampling_samples"],
        resampling_seed=identity["methodology"]["resampling_seed"],
    )
    if expected != evidence:
        raise ValueError("HOLDOUT_EVIDENCE_NOT_REPRODUCIBLE")


def _day_block_roi_lcb(day_profits: dict[str, list[float]], *, samples: int, seed: int) -> float | None:
    dates = sorted(day_profits)
    if not dates:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        selected = [dates[rng.randrange(len(dates))] for _ in dates]
        profits = [profit for date in selected for profit in day_profits[date]]
        values.append(sum(profits) / len(profits) if profits else 0.0)
    values.sort()
    return values[int(0.025 * (len(values) - 1))]


def promotion_gate(
    settlements: Iterable[dict[str, Any]], holdout_evidence: dict[str, Any], *, evidence_root: Path,
    minimum_tickets: int = 30,
    max_drawdown_threshold: float = 20.0, min_effective_legs: float = 1.5,
    max_largest_return_concentration: float = 0.5, bootstrap_samples: int = 2000, bootstrap_seed: int = 1981,
) -> dict[str, Any]:
    _validate_holdout_evidence(holdout_evidence, evidence_root)
    settlement_list = list(settlements)
    for settlement in settlement_list:
        _validate_settlement(settlement, evidence_root)
    allowed_hashes = set(holdout_evidence["evidence_identity"]["settlement_hashes"])
    if not allowed_hashes <= {row["settlement_hash"] for row in settlement_list}:
        raise ValueError("PROMOTION_SETTLEMENTS_DO_NOT_COVER_HOLDOUT_EVIDENCE")
    holdout_dates = set(holdout_evidence["holdout_dates"])
    predeclared_templates = {row["template"] for row in holdout_evidence["predeclared_hypotheses"]}
    rows = [
        (day["race_date"], ticket)
        for day in settlement_list
        for ticket in day.get("tickets", [])
        if day["race_date"] in holdout_dates
        and ticket.get("template") in predeclared_templates
        and ticket.get("status") in {"WON", "LOST"}
    ]
    days = holdout_dates
    profits = [float(row["profit"]) for _, row in rows]
    returns = [float(row["return"]) for _, row in rows if row.get("return") is not None]
    largest_return = max(returns, default=0.0)
    total_return = sum(returns)
    concentration = largest_return / total_return if total_return > 0 else None
    equity = peak = drawdown = 0.0
    for _, row in sorted(rows, key=lambda item: item[0]):
        equity += float(row["profit"])
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    day_profits = defaultdict(list)
    for date, row in rows:
        day_profits[date].append(float(row["profit"]))
    lcb = _day_block_roi_lcb(day_profits, samples=bootstrap_samples, seed=bootstrap_seed)
    effective = [float(row.get("effective_independent_legs") or 0) for _, row in rows]
    ex_largest = sum(profits) - (largest_return - 1.0 if largest_return else 0.0)
    evaluations = {
        "minimum_30_forward_days": {"value": len(days), "threshold": 30, "status": "PASS" if len(days) >= 30 else "FAIL"},
        "minimum_predeclared_tickets": {"value": len(rows), "threshold": minimum_tickets, "status": "PASS" if len(rows) >= minimum_tickets else "FAIL"},
        "positive_captured_roi": {"value": sum(profits) / len(rows) if rows else None, "threshold": 0.0, "status": "PASS" if rows and sum(profits) > 0 else "FAIL"},
        "roi_lower_confidence_bound": {"value": lcb, "threshold": 0.0, "status": "PASS" if lcb is not None and lcb >= 0 else "FAIL"},
        "maximum_drawdown": {"value": drawdown, "threshold": max_drawdown_threshold, "status": "PASS" if drawdown <= max_drawdown_threshold else "FAIL"},
        "effective_independent_legs": {"value": min(effective) if effective else None, "threshold": min_effective_legs, "status": "PASS" if effective and min(effective) >= min_effective_legs else "FAIL"},
        "largest_return_concentration": {"value": concentration, "threshold": max_largest_return_concentration, "status": "PASS" if concentration is not None and concentration <= max_largest_return_concentration else "FAIL"},
        "positive_ex_largest_return": {"value": ex_largest, "threshold": 0.0, "status": "PASS" if ex_largest > 0 else "FAIL"},
        "holdout_multiplicity_evidence": {"value": holdout_evidence.get("hypothesis_count"), "threshold": 1, "status": "PASS" if holdout_evidence.get("hypothesis_count", 0) > 0 else "FAIL"},
        "operator_decision": {"value": None, "threshold": "REQUIRED", "status": "REQUIRED"},
    }
    return {
        "promotion_authorized": False, "operator_decision_required": True,
        "forward_days": len(days), "settled_tickets": len(rows), "captured_profit": sum(profits),
        "captured_roi": sum(profits) / len(rows) if rows else None, "roi_lcb_95pct": lcb,
        "max_drawdown": drawdown, "largest_return_concentration": concentration,
        "profit_ex_largest_return": ex_largest, "gate_evaluations": evaluations,
        "overall_status": "BLOCKED_PENDING_OPERATOR_AND_ALL_EVIDENCE",
    }


def _atomic_immutable_json(payload: dict[str, Any], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    temp_path = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError:
            if path.read_bytes() == raw:
                return "VALIDATED_IDENTICAL"
            raise FileExistsError(f"IMMUTABLE_CONFLICT:{path}") from None
        return "CREATED"
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def write_immutable_forward_packet(packet: dict[str, Any], research_root: Path) -> tuple[str, Path]:
    _validate_packet(packet)
    day_root = research_root / "packets" / packet["race_date"]
    path = day_root / f"{packet['packet_identity_hash']}.json"
    manifest_path = day_root / "day_lock.json"
    manifest_body = {
        "schema_version": SCHEMA_VERSION,
        "race_date": packet["race_date"],
        "rule_version": packet["rule_version"],
        "daily_ticket_cap": packet["daily_ticket_cap"],
        "packet_identity_hash": packet["packet_identity_hash"],
        "packet_hash": packet["packet_hash"],
        "authoritative_packet_path": str(path.resolve()),
    }
    manifest = {**manifest_body, "manifest_hash": _hash(manifest_body)}
    manifest_status = _atomic_immutable_json(manifest, manifest_path)
    try:
        packet_status = _atomic_immutable_json(packet, path)
    except Exception:
        # The day lock is intentionally authoritative.  A crash after locking
        # leaves an explicit incomplete day requiring operator investigation;
        # it must never permit a replacement packet.
        raise
    status = "VALIDATED_IDENTICAL" if manifest_status == packet_status == "VALIDATED_IDENTICAL" else "CREATED"
    return status, path


def write_immutable_settlement(settlement: dict[str, Any], research_root: Path) -> tuple[str, Path]:
    _validate_settlement(settlement, research_root)
    path = _settlement_artifact_path(settlement, research_root)
    return _atomic_immutable_json(settlement, path), path


def write_immutable_holdout_evidence(evidence: dict[str, Any], research_root: Path) -> tuple[str, Path]:
    _validate_holdout_evidence(evidence, research_root)
    path = research_root / "holdout_evidence" / f"{evidence['evidence_identity_hash']}.json"
    return _atomic_immutable_json(evidence, path), path
