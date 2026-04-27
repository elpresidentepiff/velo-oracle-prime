"""
VÉLØ Batch Reconstructor (Phase 3.5) - TURBO SPEC
------------------------------------------------
Maximum throughput via multiprocessing + HTTP batching.

Historical archive note:
- Block 001 bridge rows are intentionally sparse.
- This reconstructor rehydrates missing runner context from `raceform`
  so historical rows can be scored without mutating the bridge payload.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dotenv import load_dotenv
from supabase import Client, create_client

# ---- Project imports ----
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import _build_live_features, score_race_velo_prime
from app.services.model_manager import get_model_manager
from scripts.integrity_hooks import log_integrity, run_integrity_checks_via_rpc
from src.intelligence.macro_regime.bha_macro_context import get_macro_context_for_race

# ---- Configuration ----
RECONSTRUCTION_VERSION = "V17_B1"
HISTORICAL_SOURCE = "historical_raceform"
LOG = logging.getLogger("backfill_historical_feature_store")


@dataclass
class RunStats:
    races_attempted: int = 0
    runners_attempted: int = 0
    rows_generated: int = 0
    rows_written: int = 0
    rows_skipped_local: int = 0
    batches_processed: int = 0
    started_ts: float = field(default_factory=time.time)

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_ts

    @property
    def sec_per_race(self) -> float:
        return self.elapsed / self.races_attempted if self.races_attempted > 0 else 0.0


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Historical rebuilds can touch many rows; suppress client request spam and keep only audit logs.
    for noisy_logger in ("httpx", "httpcore", "postgrest", "supabase"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_sb_client() -> Client:
    load_dotenv(ROOT / ".env", override=False)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


def batched(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def build_event_key(race_id: Any, course: Any, race_date: Any) -> str:
    return f"{str(race_id)}|{str(course or '')}|{str(race_date or '')[:10]}"


def load_manifest_payload(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_manifest_race_ids(path: str | None) -> list[str] | None:
    payload = load_manifest_payload(path)
    if not payload:
        return None
    race_ids = payload.get("race_ids") or []
    return [str(rid) for rid in race_ids]


def load_manifest_race_events(path: str | None) -> list[dict[str, Any]] | None:
    payload = load_manifest_payload(path)
    if not payload:
        return None
    race_events = payload.get("race_events") or []
    normalized: list[dict[str, Any]] = []
    for event in race_events:
        normalized.append(
            {
                "race_id": str(event.get("race_id")),
                "course": event.get("course"),
                "race_date": str(event.get("race_date") or "")[:10],
                "jurisdiction": event.get("jurisdiction"),
                "event_key": event.get("event_key")
                or build_event_key(event.get("race_id"), event.get("course"), event.get("race_date")),
            }
        )
    return normalized


def clean_horse_name(name: Any) -> str:
    if not name:
        return ""
    text = str(name).strip().upper()
    text = text.replace("–", "-")
    for suffix in ("(GB)", "(IRE)", "(FR)", "(USA)", "(AUS)", "(NZ)", "(JPN)", "(HK)"):
        text = text.replace(suffix, "")
    return " ".join(text.split())


def safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "-", "–"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> Optional[int]:
    if value in (None, "", "-", "–"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_weight_lbs(value: Any) -> Optional[float]:
    if value in (None, "", "-", "–"):
        return None
    text = str(value).strip()
    if "-" in text:
        try:
            stone_s, lbs_s = text.split("-", 1)
            return float(int(stone_s) * 14 + int(lbs_s))
        except ValueError:
            return None
    return safe_float(value)


def is_historical_race(race: dict[str, Any]) -> bool:
    raw = race.get("raw") or {}
    if isinstance(raw, dict):
        return raw.get("source") == HISTORICAL_SOURCE
    return False


SIGNAL_CONTRACT_VERSION = "HISTORICAL_SIGNAL_PROXY_V1"
MPI_SOURCE_MARKET = "archive_proxy_market_rank_v1"
CHAOS_SOURCE_MARKET = "archive_proxy_market_entropy_going_v1"
BASE_MACRO_CONTEXT_VERSION = "BHA_MACRO_2012_2024_V1"


def _runner_implied_probs(norm_runners: Sequence[dict[str, Any]]) -> list[float]:
    probs: list[float] = []
    for runner in norm_runners:
        odds = safe_float(runner.get("best_odds_decimal"))
        if odds and odds > 0:
            probs.append(1.0 / odds)
        else:
            probs.append(0.0)
    return probs


def compute_archive_mpi_proxies(norm_runners: Sequence[dict[str, Any]]) -> dict[str, float]:
    """
    Leakage-free historical MPI proxy.

    Uses only pre-race market state:
    - runner sp_dec / implied probability
    - field implied probability distribution

    Higher MPI = stronger market pressure on that runner.
    """
    implied_probs = _runner_implied_probs(norm_runners)
    positive_probs = [p for p in implied_probs if p > 0]
    if not positive_probs:
        return {}

    total = sum(positive_probs)
    norm_probs = [(p / total) if p > 0 and total > 0 else 0.0 for p in implied_probs]
    field_size = max(len(norm_runners), 1)
    order = sorted(
        range(len(norm_runners)),
        key=lambda idx: norm_probs[idx],
        reverse=True,
    )
    rank_lookup = {idx: rank + 1 for rank, idx in enumerate(order)}
    max_prob = max(norm_probs) if norm_probs else 0.0

    out: dict[str, float] = {}
    for idx, runner in enumerate(norm_runners):
        horse_id = str(runner["horse_id"]).strip()
        rank = rank_lookup[idx]
        rank_pressure = 1.0 if field_size <= 1 else 1.0 - ((rank - 1) / (field_size - 1))
        share_pressure = (norm_probs[idx] / max_prob) if max_prob > 0 else 0.0
        mpi = 100.0 * ((0.6 * rank_pressure) + (0.4 * share_pressure))
        out[horse_id] = round(max(0.0, min(100.0, mpi)), 4)
    return out


def _going_uncertainty_factor(going: str) -> float:
    text = (going or "").lower()
    if not text:
        return 0.4
    if "heavy" in text:
        return 1.0
    if "soft" in text and "good to soft" not in text:
        return 0.8
    if "yield" in text and "good to yielding" not in text:
        return 0.65
    if "good to soft" in text:
        return 0.55
    if "good to yielding" in text:
        return 0.45
    if "good to firm" in text:
        return 0.2
    if "firm" in text:
        return 0.1
    if "good" in text:
        return 0.3
    return 0.4


def compute_archive_chaos_proxy(race: dict[str, Any], norm_runners: Sequence[dict[str, Any]]) -> Optional[float]:
    """
    Leakage-free historical chaos proxy.

    Uses only:
    - pre-race implied probability distribution
    - field size
    - going metadata
    """
    field_size = max(len(norm_runners), 1)
    implied_probs = _runner_implied_probs(norm_runners)
    positive_probs = [p for p in implied_probs if p > 0]
    if positive_probs:
        total = sum(positive_probs)
        norm_probs = [p / total for p in positive_probs]
        if len(norm_probs) > 1:
            entropy = -sum(p * math.log(p) for p in norm_probs if p > 0) / math.log(len(norm_probs))
        else:
            entropy = 0.0
    else:
        entropy = 0.0

    field_factor = min(1.0, max(0.0, (field_size - 2) / 14.0))
    going_factor = _going_uncertainty_factor(str(race.get("going") or ""))
    chaos = 100.0 * ((0.5 * entropy) + (0.35 * going_factor) + (0.15 * field_factor))
    return round(max(0.0, min(100.0, chaos)), 4)


def resolve_race_date_str(race: dict[str, Any]) -> Optional[str]:
    raw = race.get("raw") or {}
    for candidate in (
        race.get("date"),
        race.get("race_date"),
        raw.get("race_date"),
        raw.get("date"),
    ):
        if candidate:
            return str(candidate)[:10]
    if race.get("reconciled_at"):
        return str(race["reconciled_at"])[:10]
    return None


def macro_year_from_race_date(race_date: Optional[str]) -> Optional[int]:
    try:
        return int(str(race_date)[:4])
    except (TypeError, ValueError):
        return None


def infer_macro_race_code(race_type: Any) -> str:
    text = str(race_type or "").lower()
    return "jump" if any(token in text for token in ("hurdle", "chase", "nh flat")) else "flat"


def derive_macro_context_metadata(race_date: Optional[str], race_type: Any) -> dict[str, Any]:
    race_year = macro_year_from_race_date(race_date)
    race_code = infer_macro_race_code(race_type)
    metadata = {
        "macro_year_used": race_year,
        "macro_year_source": "race_date",
        "macro_year_fallback": False,
        "macro_context_version": BASE_MACRO_CONTEXT_VERSION,
        "macro_proxy_source": None,
        "macro_proxy_approved": None,
    }
    if not race_date:
        return metadata
    try:
        ctx = get_macro_context_for_race(race_date, race_code)
    except Exception:
        return metadata

    metadata.update(
        {
            "macro_year_used": ctx.year,
            "macro_year_source": ctx.macro_year_source,
            "macro_year_fallback": bool(ctx.macro_year_fallback),
            "macro_context_version": ctx.macro_context_version,
            "macro_proxy_source": ctx.macro_proxy_source,
            "macro_proxy_approved": ctx.macro_proxy_approved,
        }
    )
    return metadata


def load_horse_name_lookup(sb: Client, horse_ids: Sequence[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for chunk in batched(list(horse_ids), 500):
        rows = sb.table("racing_horses").select("id,name").in_("id", list(chunk)).execute().data or []
        for row in rows:
            lookup[str(row["id"]).strip()] = row.get("name") or ""
    return lookup


def fetch_historical_runner_context(
    sb: Client,
    race_refs: Sequence[Any],
    runners_by_race: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Rehydrate sparse historical runner rows from raceform without mutating bridge data.
    Maps race_id -> horse_id -> source context.
    """
    race_events: list[dict[str, Any]] = []
    for ref in race_refs:
        if isinstance(ref, dict):
            race_events.append(
                {
                    "race_id": str(ref["race_id"]),
                    "course": ref.get("course"),
                    "race_date": str(ref.get("race_date") or "")[:10],
                }
            )
        else:
            race_events.append({"race_id": str(ref), "course": None, "race_date": None})

    all_horse_ids = {
        str(rr["horse_id"]).strip()
        for event in race_events
        for rid in [event["race_id"]]
        for rr in runners_by_race.get(str(rid), [])
        if rr.get("horse_id") is not None
    }
    horse_name_lookup = load_horse_name_lookup(sb, list(all_horse_ids))

    raceform_by_race: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for event in race_events:
        query = sb.table("raceform").select("*").eq("race_id", event["race_id"])
        if event.get("course"):
            query = query.eq("course", event["course"])
        if event.get("race_date"):
            query = query.eq("date", event["race_date"])
        rows = query.execute().data or []
        for row in rows:
            rid = str(row["race_id"])
            raceform_by_race[rid][clean_horse_name(row.get("horse"))] = row

    enriched: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for event in race_events:
        rid_s = str(event["race_id"])
        source_lookup = raceform_by_race.get(rid_s, {})
        for rr in runners_by_race.get(rid_s, []):
            horse_id = str(rr["horse_id"]).strip()
            canonical_name = horse_name_lookup.get(horse_id, "")
            source_row = source_lookup.get(clean_horse_name(canonical_name))
            if not source_row:
                continue
            enriched[rid_s][horse_id] = {
                "horse_name": source_row.get("horse") or canonical_name,
                "draw": safe_int(source_row.get("draw")),
                "age": safe_int(source_row.get("age")),
                "weight_lbs": parse_weight_lbs(source_row.get("wgt")),
                "official_rating": safe_int(source_row.get("or_rating")),
                "rpr": safe_int(source_row.get("rpr")),
                "ts": safe_int(source_row.get("ts")),
                "source_row": source_row,
            }
    return enriched


def build_norm_runner(
    rr: dict[str, Any],
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    context = context or {}
    return {
        "horse_id": str(rr["horse_id"]).strip(),
        "horse_name": rr.get("horse_name") or context.get("horse_name"),
        "draw": safe_int(rr.get("draw")) if rr.get("draw") is not None else context.get("draw"),
        "age": safe_int(rr.get("age")) if rr.get("age") is not None else context.get("age"),
        "weight_lbs": (
            safe_float(rr.get("weight_lbs"))
            if rr.get("weight_lbs") is not None
            else context.get("weight_lbs")
        ),
        "official_rating": (
            safe_int(rr.get("official_rating"))
            if rr.get("official_rating") is not None
            else context.get("official_rating")
        ),
        "rpr": safe_int(rr.get("rpr")) if rr.get("rpr") is not None else context.get("rpr"),
        "ts": safe_int(rr.get("ts")) if rr.get("ts") is not None else context.get("ts"),
        "best_odds_decimal": safe_float(rr.get("sp_dec")),
        "is_winner": bool(rr.get("is_winner")),
        "position": rr.get("position"),
        "pdf_intel": {},
    }


def reconstruct_race_payload(
    race: dict[str, Any],
    runners: Sequence[dict[str, Any]],
    existing_keys: set[tuple[str, str]],
    historical_context: Optional[dict[str, dict[str, Any]]] = None,
    trace_mode: bool = False,
) -> tuple[list[dict[str, Any]], int, int, int, list[dict[str, Any]]]:
    global _global_mm

    rid = str(race["race_id"])
    historical_context = historical_context or {}

    missing_hids = [
        str(r["horse_id"]).strip()
        for r in runners
        if (rid, str(r["horse_id"]).strip()) not in existing_keys
    ]
    if not missing_hids:
        return [], 0, len(runners), 0, []

    norm_runners = [
        build_norm_runner(rr, historical_context.get(str(rr["horse_id"]).strip()))
        for rr in runners
    ]

    raw_meta = race.get("raw") or {}
    race_date = resolve_race_date_str(race)
    nrace = {
        "race_id": rid,
        "date": race_date,
        "race_date": race_date,
        "course": race.get("course"),
        "going": race.get("going"),
        "race_class": str(race.get("class", "")),
        "type": race.get("race_type") or race.get("type") or raw_meta.get("race_type"),
        "distance_f": float(race["distance_f"]) if race.get("distance_f") is not None else None,
        "jurisdiction": race.get("jurisdiction") or raw_meta.get("jurisdiction") or "UK/IRE",
        "runners": norm_runners,
    }

    historical = is_historical_race(race)
    archive_mpi_map = compute_archive_mpi_proxies(norm_runners) if historical else {}
    archive_chaos = compute_archive_chaos_proxy(race, norm_runners) if historical else None
    archive_macro_meta = derive_macro_context_metadata(race_date, nrace.get("type")) if historical else {}

    rows: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    preds = score_race_velo_prime(nrace, sentient_state=None)
    pred_map: dict[str, dict[str, Any]] = {}
    for pred in preds:
        horse_id = pred.get("horse_id")
        if horse_id is None:
            continue
        pred_map.setdefault(str(horse_id).strip(), pred)

    for raw_runner, r_norm in zip(runners, norm_runners):
        hid = r_norm["horse_id"]
        if (rid, hid) in existing_keys:
            continue

        pred = dict(pred_map.get(hid) or {})
        prediction_present = bool(pred)
        if not pred:
            pred = {"scoring_status": "missing_prediction", "source_runner_present": True}

        feats = _build_live_features(r_norm, nrace, [], [])
        pred["strictly_ordered_vector"] = [feats.get(k, 0.0) for k in _global_mm.ALL_V17_FEATURES]

        mpi_value = pred.get("mpi")
        mpi_source = "prediction_output" if mpi_value is not None else None
        chaos_value = pred.get("chaos_bloom")
        chaos_source = "prediction_output" if chaos_value is not None else None

        if historical:
            pred["event_key"] = raw_meta.get("event_key") or build_event_key(rid, nrace.get("course"), race_date)
            pred["event_identity_contract"] = raw_meta.get("event_identity_contract") or "race_id_course_race_date"
            pred["data_owner_confirmed"] = raw_meta.get("data_owner_confirmed")
            pred["training_eligible"] = raw_meta.get("training_eligible")
            pred["archive_exhausted"] = raw_meta.get("archive_exhausted")
            pred["source"] = raw_meta.get("source") or HISTORICAL_SOURCE
            pred["bridge_version"] = raw_meta.get("bridge_version")
            pred["discovery_version"] = raw_meta.get("discovery_version")
            pred["source_table"] = raw_meta.get("source_table")
            pred["source_race_id"] = raw_meta.get("source_race_id") or rid
            pred.setdefault("expected_historical_null", True)
            pred.setdefault("story_anchor", None)
            pred.setdefault("narrative_disruption", None)
            pred["signal_contract_version"] = SIGNAL_CONTRACT_VERSION
            pred["macro_year_used"] = archive_macro_meta.get("macro_year_used")
            pred["macro_year_source"] = archive_macro_meta.get("macro_year_source") or "race_date"
            pred["macro_year_fallback"] = bool(archive_macro_meta.get("macro_year_fallback", False))
            pred["macro_context_version"] = archive_macro_meta.get("macro_context_version")
            if archive_macro_meta.get("macro_proxy_source") is not None:
                pred["macro_proxy_source"] = archive_macro_meta.get("macro_proxy_source")
            if archive_macro_meta.get("macro_proxy_approved") is not None:
                pred["macro_proxy_approved"] = archive_macro_meta.get("macro_proxy_approved")

            if mpi_value is None and hid in archive_mpi_map:
                mpi_value = archive_mpi_map[hid]
                mpi_source = MPI_SOURCE_MARKET
                pred["mpi"] = mpi_value
            if chaos_value is None and archive_chaos is not None:
                chaos_value = archive_chaos
                chaos_source = CHAOS_SOURCE_MARKET
                pred["chaos_bloom"] = chaos_value

        if mpi_source:
            pred["mpi_source"] = mpi_source
        if chaos_source:
            pred["chaos_bloom_source"] = chaos_source

        payload = {
            "race_id": rid,
            "horse_id": hid,
            "horse_name": r_norm["horse_name"],
            "reconstruction_version": RECONSTRUCTION_VERSION,
            "race_date": race_date,
            "course": nrace["course"],
            "jurisdiction": nrace["jurisdiction"],
            "distance_f": nrace["distance_f"],
            "going": nrace["going"],
            "race_class": nrace["race_class"],
            "field_size": len(runners),
            "draw": r_norm["draw"],
            "age": r_norm["age"],
            "weight_lbs": r_norm["weight_lbs"],
            "official_rating": r_norm["official_rating"],
            "rpr": r_norm["rpr"],
            "ts": r_norm["ts"],
            "sp_dec": r_norm["best_odds_decimal"],
            "implied_prob": (1.0 / r_norm["best_odds_decimal"])
            if (r_norm["best_odds_decimal"] and r_norm["best_odds_decimal"] > 0)
            else None,
            "or_vs_field": pred.get("or_vs_field"),
            "rpr_vs_field": pred.get("rpr_vs_field"),
            "draw_pct": pred.get("draw_pct"),
            "mpi": mpi_value,
            "chaos_bloom": chaos_value,
            "integrity_score": pred.get("integrity_score"),
            "power_anchor": pred.get("power_anchor"),
            "plot_conviction": pred.get("plot_conviction"),
            "or_delta_to_best_win": pred.get("or_delta_to_best_win"),
            "winner_flag": r_norm["is_winner"],
            "placed_flag": bool(r_norm["position"] in [2, 3]),
            "finish_position": r_norm["position"],
            "is_synthetic": True,
            "source_tables": ["races", "runner_results"],
            "feature_json": pred,
        }
        rows.append(payload)

        if trace_mode:
            context = historical_context.get(hid) or {}
            traces.append(
                {
                    "race_id": rid,
                    "horse_id": hid,
                    "raw_runner_results": raw_runner,
                    "raw_race_results": {
                        "race_id": rid,
                        "reconciled_at": race.get("reconciled_at"),
                    },
                    "reconstruction_input": r_norm,
                    "prediction_present": prediction_present,
                    "prediction_object": pred_map.get(hid),
                    "feature_json_before_insert": pred,
                    "final_payload": payload,
                    "historical_source_row": context.get("source_row"),
                    "mpi_source": mpi_source,
                    "chaos_bloom_source": chaos_source,
                }
            )

    return rows, len(rows), len(runners) - len(rows), 1, traces


_global_mm = None


def init_worker():
    global _global_mm
    _global_mm = get_model_manager()


def score_single_race_worker(
    race: dict[str, Any],
    runners: Sequence[dict[str, Any]],
    existing_keys: set[tuple[str, str]],
    historical_context: Optional[dict[str, dict[str, Any]]] = None,
):
    try:
        rows, generated, skipped, attempted, _ = reconstruct_race_payload(
            race,
            runners,
            existing_keys,
            historical_context=historical_context,
            trace_mode=False,
        )
        return rows, generated, skipped, attempted
    except Exception:
        return [], 0, 0, 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-races", type=int, default=1000)
    parser.add_argument("--batch-races", type=int, default=50)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--heartbeat-every", type=int, default=10)
    parser.add_argument("--manifest-file", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args()
    configure_logging()

    sb = get_sb_client()
    run_id = None
    if not args.dry_run:
        res = sb.table("historical_feature_backfill_runs").insert(
            {"reconstruction_version": RECONSTRUCTION_VERSION}
        ).execute()
        run_id = res.data[0]["id"]

    stats = RunStats()
    offset = 0
    limit_remaining = args.limit_races
    manifest_race_events = load_manifest_race_events(args.manifest_file)
    manifest_race_ids = load_manifest_race_ids(args.manifest_file)
    manifest_offset = 0

    executor_cm = (
        ProcessPoolExecutor(max_workers=args.workers, initializer=init_worker)
        if args.workers > 1
        else None
    )

    if args.workers <= 1:
        init_worker()

    with (executor_cm if executor_cm is not None else nullcontext()) as executor:
        while limit_remaining > 0:
            batch_size = min(args.batch_races, limit_remaining)
            manifest_event_batch = None
            if manifest_race_events is not None:
                manifest_event_batch = manifest_race_events[manifest_offset : manifest_offset + batch_size]
                race_ids = [str(event["race_id"]) for event in manifest_event_batch]
                if not race_ids:
                    break
                res = sb.table("race_results").select("race_id,reconciled_at").in_("race_id", race_ids).execute()
                res_lookup = {str(r["race_id"]): r for r in (res.data or [])}
                ordered_res = [res_lookup[str(event["race_id"])] for event in manifest_event_batch if str(event["race_id"]) in res_lookup]
            elif manifest_race_ids is not None:
                race_ids = manifest_race_ids[manifest_offset : manifest_offset + batch_size]
                if not race_ids:
                    break
                res = sb.table("race_results").select("race_id,reconciled_at").in_("race_id", race_ids).execute()
                res_lookup = {str(r["race_id"]): r for r in (res.data or [])}
                ordered_res = [res_lookup[str(rid)] for rid in race_ids if str(rid) in res_lookup]
            else:
                res = (
                    sb.table("race_results")
                    .select("race_id,reconciled_at")
                    .order("reconciled_at", desc=True)
                    .range(offset, offset + batch_size - 1)
                    .execute()
                )
                ordered_res = res.data or []
                race_ids = [str(r["race_id"]) for r in ordered_res]
            if not race_ids:
                break

            m_res = (
                sb.table("races")
                .select("race_id,course,going,class,distance_f,date,raw")
                .in_("race_id", race_ids)
                .execute()
            )
            m_lookup = {str(r["race_id"]): r for r in (m_res.data or [])}

            races = []
            for r in ordered_res:
                meta = dict(m_lookup.get(str(r["race_id"]), {}))
                if manifest_event_batch is not None:
                    manifest_meta = next(
                        (event for event in manifest_event_batch if str(event["race_id"]) == str(r["race_id"])),
                        None,
                    )
                    if manifest_meta:
                        meta["course"] = manifest_meta.get("course") or meta.get("course")
                        meta["date"] = manifest_meta.get("race_date") or meta.get("date")
                        meta["race_date"] = manifest_meta.get("race_date") or meta.get("race_date")
                        meta["event_key"] = manifest_meta.get("event_key")
                raw_meta = meta.get("raw") or {}
                if isinstance(raw_meta, dict) and raw_meta.get("jurisdiction") and "jurisdiction" not in meta:
                    meta["jurisdiction"] = raw_meta.get("jurisdiction")
                races.append({**r, **meta})

            if args.replace_existing:
                existing_keys: set[tuple[str, str]] = set()
            else:
                existing_res = (
                    sb.table("historical_feature_store")
                    .select("race_id, horse_id")
                    .in_("race_id", race_ids)
                    .eq("reconstruction_version", RECONSTRUCTION_VERSION)
                    .execute()
                )
                existing_keys = {
                    (str(r["race_id"]), str(r["horse_id"]).strip())
                    for r in (existing_res.data or [])
                }

            runners_res = sb.table("runner_results").select("*").in_("race_id", race_ids).execute()
            runners_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in runners_res.data or []:
                runners_by_race[str(row["race_id"])].append(row)

            historical_race_ids = [str(r["race_id"]) for r in races if is_historical_race(r)]
            historical_event_batch = [
                event
                for event in (manifest_event_batch or [])
                if str(event["race_id"]) in historical_race_ids
            ]
            historical_context_map: dict[str, dict[str, dict[str, Any]]] = {}
            if historical_race_ids:
                historical_context_map = fetch_historical_runner_context(
                    sb,
                    historical_event_batch or historical_race_ids,
                    runners_by_race,
                )

            batch_rows: list[dict[str, Any]] = []
            if executor is None:
                for race in races:
                    rows, generated, skipped, attempted = score_single_race_worker(
                        race,
                        runners_by_race.get(str(race["race_id"]), []),
                        existing_keys,
                        historical_context_map.get(str(race["race_id"]), {}),
                    )
                    batch_rows.extend(rows)
                    stats.rows_generated += generated
                    stats.rows_skipped_local += skipped
                    stats.races_attempted += attempted
            else:
                futs = [
                    executor.submit(
                        score_single_race_worker,
                        race,
                        runners_by_race.get(str(race["race_id"]), []),
                        existing_keys,
                        historical_context_map.get(str(race["race_id"]), {}),
                    )
                    for race in races
                ]
                for fut in as_completed(futs):
                    rows, generated, skipped, attempted = fut.result()
                    batch_rows.extend(rows)
                    stats.rows_generated += generated
                    stats.rows_skipped_local += skipped
                    stats.races_attempted += attempted

            if batch_rows and not args.dry_run:
                sb.table("historical_feature_store").upsert(
                    batch_rows,
                    on_conflict="race_id,horse_id,reconstruction_version",
                ).execute()
                stats.rows_written += len(batch_rows)

            stats.batches_processed += 1
            if manifest_race_events is not None or manifest_race_ids is not None:
                manifest_offset += len(race_ids)
            else:
                offset += len(race_ids)
            limit_remaining -= len(race_ids)

            if run_id and stats.batches_processed % args.heartbeat_every == 0:
                integrity = run_integrity_checks_via_rpc(sb, RECONSTRUCTION_VERSION, min(race_ids), max(race_ids))
                log_integrity(integrity)
                sb.table("historical_feature_backfill_runs").update(
                    {
                        "rows_written": stats.rows_written,
                        "rows_attempted": stats.rows_generated,
                        "rows_skipped": stats.rows_skipped_local,
                    }
                ).eq("id", run_id).execute()
                LOG.info("Turbo: %.3fs/race | %s total upserted", stats.sec_per_race, stats.rows_written)

    if run_id:
        sb.table("historical_feature_backfill_runs").update(
            {"status": "completed", "finished_at": datetime.now().isoformat()}
        ).eq("id", run_id).execute()
    LOG.info("DONE. Avg=%.3fs/race", stats.sec_per_race)


if __name__ == "__main__":
    main()
