"""
VÉLØ Unified Evidence Corpus V1
===============================

Build one canonical evidence corpus for signal promotion, router audit,
sidecar audit, and paper-execution governance.

Outputs:
  - data/velo_unified_evidence_corpus_v1.csv
  - data/velo_unified_evidence_corpus_v1.md

This is an audit/governance script only.
It does not change scoring, routing, staking, Telegram, or execution.
"""

from __future__ import annotations

import csv
import glob
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_CSV = DATA / "velo_unified_evidence_corpus_v1.csv"
OUT_MD = DATA / "velo_unified_evidence_corpus_v1.md"
RUN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

SIGNAL_FIELDS = [
    "velo_prime_prob",
    "sqpe_v17_prob",
    "market_deception_score",
    "improvement_score",
    "place_prob",
    "longshot_prob",
    "release_day_prob",
    "comment_intel_score",
    "g_shadow_mode",
    "router_v1_shadow_pass",
    "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist",
    "racing_api_enrichment_shadow_score",
    "power_anchor_mode",
    "b_low_vp_suppress",
]

CORPUS_FIELDS = [
    "canonical_key",
    "race_id",
    "horse_id",
    "horse",
    "horse_norm",
    "date",
    "course",
    "off_time",
    "decision_tier",
    "confidence_level",
    "assigned_product",
    "result_position",
    "won",
    "placed",
    "sp_decimal",
    "actual_winner_sp",
    "result_matched",
    "canonical_identity_source",
    "canonical_result_source",
    "canonical_signal_source",
    "identity_unresolved",
    "conflict_types",
    "conflict_count",
    "serious_conflict_count",
    "velo_prime_prob",
    "sqpe_v17_prob",
    "market_deception_score",
    "improvement_score",
    "place_prob",
    "longshot_prob",
    "release_day_prob",
    "comment_intel_score",
    "g_shadow_mode",
    "router_v1_shadow_pass",
    "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist",
    "router_shadow_lane",
    "racing_api_connection_shadow_score",
    "racing_api_course_shadow_score",
    "racing_api_distance_shadow_score",
    "racing_api_enrichment_shadow_score",
    "power_anchor_mode",
    "watch_only_mode",
    "b_low_vp_suppress",
    "from_supabase_sigma",
    "from_supabase_verdict",
    "from_local_verdict",
    "from_local_result",
    "from_innovation_protocol",
    "from_racing_api_shadow",
    "from_execution_bridge",
    "source_count",
    "source_names",
]

IDENTITY_FIELDS = {"horse_id", "horse", "horse_norm"}
RESULT_FIELDS = {"result_position", "won", "placed", "sp_decimal", "actual_winner_sp", "result_matched"}
SIGNAL_FIELDS_SET = set(SIGNAL_FIELDS)
ROUTER_FIELDS = {"router_v1_shadow_pass", "router_v2_class4_shadow_pass", "router_v6_gold_seam_watchlist", "router_shadow_lane", "b_low_vp_suppress"}
EXECUTION_FIELDS = {"power_anchor_mode", "watch_only_mode"}
RACING_API_FIELDS = {
    "racing_api_connection_shadow_score",
    "racing_api_course_shadow_score",
    "racing_api_distance_shadow_score",
    "racing_api_enrichment_shadow_score",
}
SOURCE_FLAGS = [
    "from_supabase_sigma",
    "from_supabase_verdict",
    "from_local_verdict",
    "from_local_result",
    "from_innovation_protocol",
    "from_racing_api_shadow",
    "from_execution_bridge",
]

FIELD_GROUP_PRECEDENCE = {
    "identity": ["local_verdict", "innovation_protocol", "racing_api_shadow", "execution_bridge", "supabase_verdict", "fallback"],
    "result": ["local_result", "innovation_protocol", "execution_bridge", "racing_api_shadow", "supabase_sigma"],
    "signal": ["local_verdict", "innovation_protocol", "supabase_verdict", "racing_api_shadow"],
    "router": ["innovation_protocol", "local_verdict", "racing_api_shadow"],
    "execution": ["execution_bridge"],
    "racing_api": ["racing_api_shadow", "local_verdict"],
    "meta": ["local_verdict", "innovation_protocol", "execution_bridge", "racing_api_shadow", "supabase_verdict", "supabase_sigma", "fallback"],
}


def _f(value, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _i(value, default=None):
    if value in (None, ""):
        return default
    try:
        return int(value)
    except Exception:
        return default


def _b(value) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return None


def _norm_name(name) -> str:
    text = re.sub(r"\s+", " ", str(name or "").strip().lower())
    return re.sub(r"[^a-z0-9 ]+", "", text)


def _norm_course(name) -> str:
    text = re.sub(r"\(.*?\)", "", str(name or "").strip().lower())
    return re.sub(r"\s+", " ", text).strip()


def _canonical_key(race_id: str | None, horse_id: str | None, horse: str | None) -> str | None:
    race_id = str(race_id or "").strip()
    horse_id = str(horse_id or "").strip()
    if race_id and horse_id:
        return f"{race_id}::{horse_id}"
    horse_norm = _norm_name(horse)
    if race_id and horse_norm:
        return f"{race_id}::{horse_norm}"
    return None


def _classify_field_group(field: str) -> str:
    if field in IDENTITY_FIELDS:
        return "identity"
    if field in RESULT_FIELDS:
        return "result"
    if field in SIGNAL_FIELDS_SET:
        return "signal"
    if field in ROUTER_FIELDS:
        return "router"
    if field in EXECUTION_FIELDS:
        return "execution"
    if field in RACING_API_FIELDS:
        return "racing_api"
    return "meta"


def _precedence_rank(source_name: str, field: str) -> int:
    group = _classify_field_group(field)
    order = FIELD_GROUP_PRECEDENCE[group]
    try:
        return order.index(source_name)
    except ValueError:
        return len(order)


def _conflict_type(field: str, old, new) -> str:
    if old in ("", None) or new in ("", None):
        return "null_fill_conflict"
    if field in IDENTITY_FIELDS:
        return "identity_conflict"
    if field in RESULT_FIELDS:
        return "result_conflict"
    if field in SIGNAL_FIELDS_SET or field in ROUTER_FIELDS or field in EXECUTION_FIELDS or field in RACING_API_FIELDS:
        return "signal_conflict"
    if field in {"date", "off_time"}:
        return "source_timestamp_conflict"
    return "signal_conflict"


def _safe_corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _flat_roi(rows: list[dict]) -> tuple[float | None, float | None, int | None]:
    pnl = []
    for row in rows:
        sp = _f(row.get("sp_decimal"))
        won = _b(row.get("won"))
        if sp is None or won is None:
            continue
        pnl.append((sp - 1.0) if won else -1.0)
    if not pnl:
        return None, None, None
    curve = 0.0
    peak = 0.0
    max_dd = 0.0
    losing_run = 0
    longest = 0
    for x in pnl:
        curve += x
        peak = max(peak, curve)
        max_dd = min(max_dd, curve - peak)
        if x < 0:
            losing_run += 1
            longest = max(longest, losing_run)
        else:
            losing_run = 0
    return sum(pnl) / len(pnl), max_dd, longest


def _improve_metrics(rows: list[dict]) -> dict:
    matched = [r for r in rows if _b(r.get("result_matched"))]
    wins = sum(1 for r in matched if _b(r.get("won")))
    places = sum(1 for r in matched if _b(r.get("placed")))
    roi, max_dd, longest = _flat_roi(matched)
    return {
        "raw_n": len(rows),
        "matched_n": len(matched),
        "wins": wins,
        "places": places,
        "strike_rate": (wins / len(matched) * 100.0) if matched else None,
        "frame_rate": (places / len(matched) * 100.0) if matched else None,
        "roi": roi,
        "max_drawdown": max_dd,
        "longest_losing_run": longest,
    }


def get_sb():
    load_dotenv(ROOT / ".env")
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def fetch_all(sb, table: str, fields: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        batch = sb.table(table).select(fields).range(offset, offset + 999).execute().data
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def load_supabase_sigma() -> list[dict]:
    sb = get_sb()
    return fetch_all(
        sb,
        "sigma_audits",
        "id,race_id,date,track,off_time,outcome,miss_reason,confidence_level,decision_tier,actual_winner_sp,top_pick_position,actual_winner_name",
    )


def load_supabase_verdicts() -> list[dict]:
    sb = get_sb()
    rows = fetch_all(
        sb,
        "velo_verdicts",
        "id,race_id,velo_prime_prob,decision_tier,confidence_level_effective,assigned_product,"
        "improvement_score,market_deception_score,place_prob,generated_at",
    )
    rows.sort(key=lambda r: str(r.get("generated_at") or ""), reverse=True)
    deduped = {}
    for row in rows:
        race_id = row.get("race_id")
        if race_id and race_id not in deduped:
            deduped[race_id] = row
    return list(deduped.values())


def load_local_verdict_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(DATA.glob("velo_prime_verdicts_2026_*.json")):
        try:
            verdicts = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        file_date = re.search(r"(\d{4}_\d{2}_\d{2})", path.name)
        file_date = file_date.group(1).replace("_", "-") if file_date else ""
        for verdict in verdicts:
            top = verdict.get("top") or {}
            rows.append(
                {
                    "race_id": verdict.get("race_id"),
                    "horse_id": top.get("horse_id"),
                    "horse": top.get("horse"),
                    "date": file_date,
                    "course": verdict.get("course"),
                    "off_time": verdict.get("off_time"),
                    "decision_tier": verdict.get("tier"),
                    "confidence_level": top.get("confidence_level"),
                    "velo_prime_prob": _f(top.get("velo_prime_prob")),
                    "sqpe_v17_prob": _f(top.get("sqpe_v17_prob")),
                    "market_deception_score": _f(top.get("market_deception_score")),
                    "improvement_score": _f(top.get("improvement_score")),
                    "place_prob": _f(top.get("place_prob")),
                    "longshot_prob": _f(top.get("longshot_prob")),
                    "release_day_prob": _f(top.get("release_day_prob")),
                    "comment_intel_score": _f(top.get("comment_intel_score")),
                    "g_shadow_mode": _b(top.get("g_shadow_mode")),
                    "b_low_vp_suppress": verdict.get("tier") == "B" and (_f(top.get("velo_prime_prob"), 0.0) or 0.0) < 0.30,
                }
            )
    return rows


def load_local_results_map() -> dict[tuple[str, str], dict]:
    by_key: dict[tuple[str, str], dict] = {}
    for path in sorted(DATA.glob("results_2026_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for race in payload.get("results", []):
            race_id = race.get("race_id")
            for runner in race.get("runners", []):
                horse_id = runner.get("horse_id")
                if race_id and horse_id:
                    by_key[(race_id, horse_id)] = {
                        "horse": runner.get("horse"),
                        "result_position": runner.get("position"),
                        "won": str(runner.get("position") or "").strip() == "1",
                        "placed": str(runner.get("position") or "").strip() in {"1", "2", "3"},
                        "sp_decimal": _f(runner.get("sp_dec")),
                        "actual_winner_sp": None,
                    }
    return by_key


def load_innovation_rows() -> list[dict]:
    path = DATA / "velo_innovation_protocol_1k_deduped.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_shadow_rows() -> list[dict]:
    path = DATA / "racing_api_shadow_forward_ledger.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_execution_rows() -> list[dict]:
    path = DATA / "velo_execution_bridge_paper_ledger.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_corpus() -> tuple[list[dict], dict]:
    supabase_sigma = load_supabase_sigma()
    supabase_verdicts = load_supabase_verdicts()
    local_verdicts = load_local_verdict_rows()
    local_results = load_local_results_map()
    innovation_rows = load_innovation_rows()
    shadow_rows = load_shadow_rows()
    execution_rows = load_execution_rows()

    source_rows = {
        "supabase_sigma": len(supabase_sigma),
        "supabase_verdict": len(supabase_verdicts),
        "local_verdict": len(local_verdicts),
        "local_result": len(local_results),
        "innovation_protocol": len(innovation_rows),
        "racing_api_shadow": len(shadow_rows),
        "execution_bridge": len(execution_rows),
    }

    rows_by_key: dict[str, dict] = {}
    provenance = defaultdict(set)
    duplicate_groups = Counter()
    conflicts: list[dict] = []
    missing_fields = defaultdict(set)

    def ensure_row(race_id: str | None, horse_id: str | None, horse: str | None) -> dict | None:
        race_id = str(race_id or "").strip()
        horse_id = str(horse_id or "").strip()
        horse_norm = _norm_name(horse)
        id_key = f"{race_id}::{horse_id}" if race_id and horse_id else None
        name_key = f"{race_id}::{horse_norm}" if race_id and horse_norm else None
        if id_key and id_key in rows_by_key:
            return rows_by_key[id_key]
        if id_key and name_key and name_key in rows_by_key:
            row = rows_by_key.pop(name_key)
            row["canonical_key"] = id_key
            row["horse_id"] = horse_id
            row["horse"] = row.get("horse") or horse or ""
            row["horse_norm"] = _norm_name(row.get("horse") or horse)
            rows_by_key[id_key] = row
            return row
        key = id_key or name_key
        if not key:
            return None
        row = rows_by_key.get(key)
        if row is None:
            row = {field: "" for field in CORPUS_FIELDS}
            row["canonical_key"] = key
            row["race_id"] = race_id
            row["horse_id"] = horse_id
            row["horse"] = horse or ""
            row["horse_norm"] = horse_norm
            row["source_names"] = ""
            row["source_count"] = 0
            row["canonical_identity_source"] = ""
            row["canonical_result_source"] = ""
            row["canonical_signal_source"] = ""
            row["identity_unresolved"] = False
            row["conflict_types"] = ""
            row["conflict_count"] = 0
            row["serious_conflict_count"] = 0
            row["_field_sources"] = {}
            row["_conflict_types"] = []
            row["_provenance"] = set()
            for flag in SOURCE_FLAGS:
                row[flag] = False
            rows_by_key[key] = row
        return row

    def apply_values(row: dict, values: dict, source_name: str, field_names: list[str]) -> None:
        field_sources = row["_field_sources"]
        for field in field_names:
            new = values.get(field)
            if new in ("", None):
                missing_fields[source_name].add(field)
                continue
            old = row.get(field)
            old_source = field_sources.get(field, "fallback")
            if old in ("", None):
                row[field] = new
                field_sources[field] = source_name
                continue
            if old == new:
                continue
            conflict_type = _conflict_type(field, old, new)
            row["_conflict_types"].append(conflict_type)
            conflicts.append(
                {
                    "canonical_key": row["canonical_key"],
                    "field": field,
                    "old": old,
                    "new": new,
                    "source": source_name,
                    "old_source": old_source,
                    "conflict_type": conflict_type,
                    "serious": conflict_type != "null_fill_conflict",
                }
            )
            if _precedence_rank(source_name, field) < _precedence_rank(old_source, field):
                row[field] = new
                field_sources[field] = source_name

    def mark_source(row: dict, source_name: str) -> None:
        flag_name = f"from_{source_name}"
        if flag_name in row and not row[flag_name]:
            row[flag_name] = True
        provenance[row["canonical_key"]].add(source_name)
        row["_provenance"].add(source_name)
        duplicate_groups[row["canonical_key"]] += 1

    for src in innovation_rows:
        row = ensure_row(src.get("race_id"), src.get("horse_id"), src.get("horse"))
        if not row:
            continue
        mark_source(row, "innovation_protocol")
        apply_values(
            row,
            {
                "date": src.get("date"),
                "course": src.get("course"),
                "off_time": src.get("race_time"),
                "decision_tier": src.get("tier"),
                "velo_prime_prob": _f(src.get("model_probability")),
                "sp_decimal": _f(src.get("sp_decimal")),
                "won": _b(src.get("won")),
                "placed": _b(src.get("placed")),
                "result_position": src.get("result_position"),
                "result_matched": src.get("result_position") not in ("", None),
                "router_v1_shadow_pass": _b(src.get("router_v1_shadow_pass")),
                "router_v2_class4_shadow_pass": _b(src.get("router_v2_class4_shadow_pass")),
                "router_v6_gold_seam_watchlist": _b(src.get("router_v6_gold_seam_watchlist")),
                "router_shadow_lane": src.get("router_shadow_lane"),
                "b_low_vp_suppress": (src.get("tier") == "B" and (_f(src.get("model_probability"), 0.0) or 0.0) < 0.30),
            },
            "innovation_protocol",
            [
                "date", "course", "off_time", "decision_tier", "velo_prime_prob",
                "sp_decimal", "won", "placed", "result_position", "result_matched",
                "router_v1_shadow_pass", "router_v2_class4_shadow_pass",
                "router_v6_gold_seam_watchlist", "router_shadow_lane", "b_low_vp_suppress",
            ],
        )

    for src in local_verdicts:
        row = ensure_row(src.get("race_id"), src.get("horse_id"), src.get("horse"))
        if not row:
            continue
        mark_source(row, "local_verdict")
        apply_values(row, src, "local_verdict", [
            "date", "course", "off_time", "decision_tier", "confidence_level",
            "velo_prime_prob", "sqpe_v17_prob", "market_deception_score",
            "improvement_score", "place_prob", "longshot_prob", "release_day_prob",
            "comment_intel_score", "g_shadow_mode", "b_low_vp_suppress",
        ])

    for src in shadow_rows:
        row = ensure_row(src.get("race_id"), src.get("horse_id"), src.get("horse"))
        if not row:
            continue
        mark_source(row, "racing_api_shadow")
        apply_values(
            row,
            {
                "date": src.get("date"),
                "course": src.get("course"),
                "off_time": src.get("off_time"),
                "horse_id": src.get("horse_id"),
                "velo_prime_prob": _f(src.get("velo_prime_prob")),
                "decision_tier": src.get("tier"),
                "racing_api_connection_shadow_score": _f(src.get("racing_api_connection_shadow_score")),
                "racing_api_course_shadow_score": _f(src.get("racing_api_course_shadow_score")),
                "racing_api_distance_shadow_score": _f(src.get("racing_api_distance_shadow_score")),
                "racing_api_enrichment_shadow_score": _f(src.get("racing_api_enrichment_shadow_score")),
                "router_shadow_lane": src.get("router_shadow_lane"),
                "result_position": src.get("result_position"),
                "won": _b(src.get("won")),
                "placed": _b(src.get("placed")),
                "sp_decimal": _f(src.get("sp_decimal")),
                "result_matched": src.get("result_position") not in ("", None),
            },
            "racing_api_shadow",
            [
                "date", "course", "off_time", "velo_prime_prob", "decision_tier",
                "racing_api_connection_shadow_score", "racing_api_course_shadow_score",
                "racing_api_distance_shadow_score", "racing_api_enrichment_shadow_score",
                "router_shadow_lane", "result_position", "won", "placed", "sp_decimal",
                "result_matched",
            ],
        )

    for src in execution_rows:
        row = ensure_row(src.get("race_id"), src.get("horse_id"), src.get("horse"))
        if not row:
            continue
        mark_source(row, "execution_bridge")
        directive = str(src.get("directive_type") or "")
        apply_values(
            row,
            {
                "date": src.get("date"),
                "course": src.get("course"),
                "off_time": src.get("off_time"),
                "velo_prime_prob": _f(src.get("velo_prime_prob")),
                "decision_tier": src.get("tier"),
                "market_deception_score": _f(src.get("market_deception_score")),
                "improvement_score": _f(src.get("improvement_score")),
                "place_prob": _f(src.get("place_prob")),
                "racing_api_enrichment_shadow_score": _f(src.get("racing_api_enrichment_shadow_score")),
                "power_anchor_mode": directive == "POWER_ANCHOR_MODE",
                "watch_only_mode": directive == "WATCH_ONLY",
                "router_shadow_lane": src.get("router_shadow_lane"),
                "result_position": src.get("result_position"),
                "won": _b(src.get("won")),
                "placed": _b(src.get("placed")),
                "sp_decimal": _f(src.get("sp_decimal")),
                "result_matched": src.get("result_position") not in ("", None),
            },
            "execution_bridge",
            [
                "date", "course", "off_time", "velo_prime_prob", "decision_tier",
                "market_deception_score", "improvement_score", "place_prob",
                "racing_api_enrichment_shadow_score", "power_anchor_mode",
                "watch_only_mode", "router_shadow_lane", "result_position",
                "won", "placed", "sp_decimal", "result_matched",
            ],
        )

    race_to_keys: dict[str, list[str]] = defaultdict(list)
    for key, row in rows_by_key.items():
        if row["race_id"]:
            race_to_keys[row["race_id"]].append(key)

    for src in supabase_verdicts:
        race_id = src.get("race_id")
        for key in race_to_keys.get(race_id, []):
            row = rows_by_key[key]
            mark_source(row, "supabase_verdict")
            apply_values(
                row,
                {
                    "velo_prime_prob": _f(src.get("velo_prime_prob")),
                    "decision_tier": src.get("decision_tier"),
                    "confidence_level": src.get("confidence_level_effective"),
                    "assigned_product": src.get("assigned_product"),
                    "improvement_score": _f(src.get("improvement_score")),
                    "market_deception_score": _f(src.get("market_deception_score")),
                    "place_prob": _f(src.get("place_prob")),
                },
                "supabase_verdict",
                [
                    "velo_prime_prob",
                    "decision_tier",
                    "confidence_level",
                    "assigned_product",
                    "improvement_score",
                    "market_deception_score",
                    "place_prob",
                ],
            )

    sigma_by_race = {}
    for src in supabase_sigma:
        race_id = src.get("race_id")
        if race_id and race_id not in sigma_by_race:
            sigma_by_race[race_id] = src
    for race_id, src in sigma_by_race.items():
        for key in race_to_keys.get(race_id, []):
            row = rows_by_key[key]
            mark_source(row, "supabase_sigma")
            outcome = src.get("outcome")
            placed = outcome in {"WIN", "PLACED"} if outcome not in (None, "") else None
            won = outcome == "WIN" if outcome not in (None, "") else None
            result_position = "1" if outcome == "WIN" else ("2/3" if outcome == "PLACED" else "")
            apply_values(
                row,
                {
                    "date": src.get("date"),
                    "course": src.get("track"),
                    "off_time": src.get("off_time"),
                    "decision_tier": src.get("decision_tier"),
                    "confidence_level": src.get("confidence_level"),
                    "actual_winner_sp": _f(src.get("actual_winner_sp")),
                    "won": won,
                    "placed": placed,
                    "result_position": result_position,
                    "result_matched": outcome not in (None, ""),
                },
                "supabase_sigma",
                [
                    "date", "course", "off_time", "decision_tier",
                    "confidence_level", "actual_winner_sp", "won",
                    "placed", "result_position", "result_matched",
                ],
            )

    for (race_id, horse_id), res in local_results.items():
        key = _canonical_key(race_id, horse_id, None)
        row = rows_by_key.get(key)
        if not row:
            continue
        mark_source(row, "local_result")
        apply_values(
            row,
            {
                "result_position": res.get("result_position"),
                "won": res.get("won"),
                "placed": res.get("placed"),
                "sp_decimal": res.get("sp_decimal"),
                "result_matched": True,
            },
            "local_result",
            ["result_position", "won", "placed", "sp_decimal", "result_matched"],
        )

    verdict_name_map = {}
    innovation_name_map = {}
    shadow_name_map = {}
    execution_name_map = {}
    result_name_map = {}

    def _add_name_map(target: dict, src_rows: list[dict], horse_key: str = "horse"):
        for src in src_rows:
            race_id = str(src.get("race_id") or "").strip()
            horse_norm = _norm_name(src.get(horse_key))
            horse_id = str(src.get("horse_id") or "").strip()
            if race_id and horse_norm and horse_id:
                target.setdefault((race_id, horse_norm), set()).add(horse_id)

    _add_name_map(verdict_name_map, local_verdicts)
    _add_name_map(innovation_name_map, innovation_rows)
    _add_name_map(shadow_name_map, shadow_rows)
    _add_name_map(execution_name_map, execution_rows)
    for (race_id, horse_id), res in local_results.items():
        horse_norm = _norm_name(res.get("horse"))
        if race_id and horse_norm and horse_id:
            result_name_map.setdefault((race_id, horse_norm), set()).add(horse_id)

    for row in rows_by_key.values():
        if row.get("horse_id"):
            continue
        race_id = row.get("race_id")
        horse_norm = row.get("horse_norm")
        if not race_id or not horse_norm:
            row["identity_unresolved"] = True
            row["_conflict_types"].append("identity_conflict")
            continue
        identity_sources = [
            ("local_verdict", verdict_name_map),
            ("local_result", result_name_map),
            ("innovation_protocol", innovation_name_map),
            ("racing_api_shadow", shadow_name_map),
            ("execution_bridge", execution_name_map),
        ]
        hydrated = None
        for source_name, mapping in identity_sources:
            matches = mapping.get((race_id, horse_norm), set())
            if len(matches) == 1:
                hydrated = (next(iter(matches)), source_name)
                break
            if len(matches) > 1:
                row["_conflict_types"].append("identity_conflict")
        if hydrated:
            row["horse_id"] = hydrated[0]
            row["canonical_identity_source"] = hydrated[1]
        else:
            row["identity_unresolved"] = True

    remapped = {}
    for old_key, row in list(rows_by_key.items()):
        new_key = _canonical_key(row.get("race_id"), row.get("horse_id"), row.get("horse"))
        if not new_key:
            new_key = old_key
        if new_key in remapped and remapped[new_key] is not row:
            row["_conflict_types"].append("identity_conflict")
            conflicts.append(
                {
                    "canonical_key": row["canonical_key"],
                    "field": "canonical_key",
                    "old": remapped[new_key]["canonical_key"],
                    "new": row["canonical_key"],
                    "source": "hydration_merge",
                    "old_source": "hydration_merge",
                    "conflict_type": "identity_conflict",
                    "serious": True,
                }
            )
            continue
        row["canonical_key"] = new_key
        remapped[new_key] = row
    rows_by_key = remapped

    rows = []
    for row in rows_by_key.values():
        source_names = sorted(row.pop("_provenance", set()))
        row["source_names"] = ",".join(source_names)
        row["source_count"] = len(source_names)
        field_sources = row.pop("_field_sources", {})
        cts = row.pop("_conflict_types", [])
        row["conflict_types"] = ",".join(sorted(set(cts)))
        row["conflict_count"] = len(cts)
        row["serious_conflict_count"] = sum(1 for c in cts if c != "null_fill_conflict")
        if not row.get("canonical_identity_source"):
            row["canonical_identity_source"] = field_sources.get("horse_id", "fallback" if row.get("horse_id") else "")
        if not row.get("canonical_result_source"):
            for field in ("result_position", "won", "placed", "sp_decimal"):
                if field_sources.get(field):
                    row["canonical_result_source"] = field_sources[field]
                    break
        if not row.get("canonical_signal_source"):
            for field in ("improvement_score", "market_deception_score", "place_prob", "velo_prime_prob"):
                if field_sources.get(field):
                    row["canonical_signal_source"] = field_sources[field]
                    break
        rows.append(row)

    rows.sort(key=lambda r: (r.get("date") or "", r.get("race_id") or "", r.get("horse") or ""))
    duplicate_removed = sum(max(0, count - 1) for count in duplicate_groups.values())
    conflict_type_counts = Counter(c["conflict_type"] for c in conflicts)
    serious_conflicts = sum(1 for c in conflicts if c["serious"])
    unresolved_identity = sum(1 for r in rows if _b(r.get("identity_unresolved")))

    stats = {
        "source_rows": source_rows,
        "canonical_row_count": len(rows),
        "result_matched_count": sum(1 for r in rows if _b(r.get("result_matched"))),
        "duplicate_groups_removed": duplicate_removed,
        "source_conflicts_found": len(conflicts),
        "serious_conflicts_found": serious_conflicts,
        "conflict_type_counts": dict(conflict_type_counts),
        "unresolved_identity_rows": unresolved_identity,
        "fields_missing_by_source": {k: sorted(v) for k, v in missing_fields.items()},
        "sample_20_rows": rows[:20],
        "conflicts_preview": conflicts[:20],
    }
    return rows, stats


def write_outputs(rows: list[dict], stats: dict) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CORPUS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CORPUS_FIELDS})

    improve_rows = [r for r in rows if (_f(r.get("improvement_score"), 0.0) or 0.0) > 0.40]
    improve = _improve_metrics(improve_rows)

    old_n = 62
    board_n = 31
    before_canonical = 1246
    before_matched = 1042
    before_conflicts = 3024
    lines = [
        "# VÉLØ Unified Evidence Corpus V1",
        "",
        f"Generated: {RUN_TS}",
        "",
        "## Source Counts",
        "",
    ]
    for name, count in stats["source_rows"].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(
        [
            "",
            "## Canonical Summary",
            "",
            f"- Deduped canonical row count: `{before_canonical} -> {stats['canonical_row_count']}`",
            f"- Result-matched count: `{before_matched} -> {stats['result_matched_count']}`",
            f"- Duplicate groups removed: `{stats['duplicate_groups_removed']}`",
            f"- Source conflicts found: `{before_conflicts} -> {stats['source_conflicts_found']}`",
            f"- Serious conflicts found: `{stats['serious_conflicts_found']}`",
            f"- Unresolved horse_id rows: `{stats['unresolved_identity_rows']}`",
            "",
            "## Conflict Taxonomy",
            "",
            f"- null_fill_conflict: `{stats['conflict_type_counts'].get('null_fill_conflict', 0)}`",
            f"- identity_conflict: `{stats['conflict_type_counts'].get('identity_conflict', 0)}`",
            f"- result_conflict: `{stats['conflict_type_counts'].get('result_conflict', 0)}`",
            f"- signal_conflict: `{stats['conflict_type_counts'].get('signal_conflict', 0)}`",
            f"- source_timestamp_conflict: `{stats['conflict_type_counts'].get('source_timestamp_conflict', 0)}`",
            "",
            "## Missing Fields By Source",
            "",
        ]
    )
    for source, fields in sorted(stats["fields_missing_by_source"].items()):
        lines.append(f"- `{source}`: {', '.join(fields) if fields else 'none'}")
    lines.extend(
        [
            "",
            "## Canonical IMPROVE_HIGH",
            "",
            f"- Definition: `improvement_score > 0.40`",
            f"- Old evidence n: `{old_n}`",
            f"- Board-safe local raw n: `{board_n}`",
            f"- Unified corpus raw n: `{improve['raw_n']}`",
            f"- Unified corpus matched n: `{improve['matched_n']}`",
            f"- Wins: `{improve['wins']}`",
            f"- Places: `{improve['places']}`",
            f"- SR: `{'' if improve['strike_rate'] is None else round(improve['strike_rate'], 2)}`",
            f"- Frame: `{'' if improve['frame_rate'] is None else round(improve['frame_rate'], 2)}`",
            f"- ROI: `{'' if improve['roi'] is None else round(improve['roi'] * 100, 2)}%`",
            "",
            "## Top 20 Serious Conflict Examples",
            "",
            "| canonical_key | field | old_source | source | conflict_type | old | new |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for c in [c for c in stats["conflicts_preview"] if c.get("serious")][:20]:
        lines.append(
            f"| {c.get('canonical_key','')} | {c.get('field','')} | {c.get('old_source','')} | "
            f"{c.get('source','')} | {c.get('conflict_type','')} | {c.get('old','')} | {c.get('new','')} |"
        )
    lines.extend(
        [
            "",
            "## Sample 20 Canonical Rows",
            "",
            "| race_id | horse_id | horse | date | tier | VP | improve | MDS | place | matched | sources |",
            "|---|---|---|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in stats["sample_20_rows"]:
        lines.append(
            f"| {row.get('race_id','')} | {row.get('horse_id','')} | {row.get('horse','')} | "
            f"{row.get('date','')} | {row.get('decision_tier','')} | {row.get('velo_prime_prob','')} | "
            f"{row.get('improvement_score','')} | {row.get('market_deception_score','')} | "
            f"{row.get('place_prob','')} | {row.get('result_matched','')} | {row.get('source_names','')} |"
        )

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows, stats = build_corpus()
    write_outputs(rows, stats)
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
