#!/usr/bin/env python3
"""Governed, immutable, PAPER/SIM-only forward-model laboratory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.analysis.playbook_g_full_field_benchmark import (  # noqa: E402
    _off_datetime,
    _parse_created_at,
    select_latest_pre_off_fields,
)

SCHEMA_VERSION = "forward-model-lab-v2"
EVIDENCE_CLASSES = ("GENUINELY_FORWARD", "BACKFILLED", "RETROSPECTIVE")
EPSILON = 1e-12
LAB_ROOT = ROOT / "data" / "research" / "forward_model_lab"
CONTAMINATED_RUN_MARKERS = {"32cc27f9", "847964a6"}


def _canonical(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(v):
    return hashlib.sha256(_canonical(v).encode()).hexdigest()


def _aware(v):
    p = _parse_created_at(v)
    return p if p is not None and p.tzinfo is not None else None


def _number(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _git_commit():
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _utc_now():
    return datetime.now(UTC)


def _select_authoritative_run(source_rows, race_date, race_id):
    groups = defaultdict(list)
    for row in source_rows:
        if str(row.get("race_date") or "") != race_date or str(row.get("race_id") or "") != str(race_id):
            continue
        run_id = str(row.get("run_id") or "")
        if (
            not run_id
            or any(marker in run_id for marker in CONTAMINATED_RUN_MARKERS)
            or row.get("live_scoring_changed") is True
        ):
            continue
        key = (run_id, str(row.get("created_at") or ""), str(row.get("off_time") or ""))
        groups[key].append(row)
    eligible = []
    for key, rows in groups.items():
        created = _aware(key[1])
        off = _off_datetime(race_date, key[2])
        unique = {}
        for row in rows:
            horse_id = str(row.get("horse_id") or "")
            if horse_id:
                unique[horse_id] = row
        expected_sizes = {
            int(value)
            for row in rows
            for value in (row.get("field_size"), row.get("runner_count"))
            if str(value or "").isdigit()
        }
        if len(expected_sizes) > 1:
            raise ValueError(f"CONTRADICTORY_FIELD_SIZE_DECLARATIONS:{race_id}:{key[0]}")
        complete = len(unique) >= 3 and (not expected_sizes or len(unique) == max(expected_sizes))
        if created is not None and off is not None and created < off and complete:
            eligible.append((created, key, list(unique.values())))
    if not eligible:
        raise ValueError(f"NO_COMPLETE_PRE_OFF_SOURCE_RUN:{race_id}")
    eligible.sort(key=lambda item: (item[0], item[1]))
    return eligible[-1]


def _source_provenance(paths: list[Path], fields: dict[str, list[dict]], race_date: str):
    if fields and not paths:
        raise ValueError("SOURCE_BYTES_REQUIRED")
    observed = set()
    source_rows = []
    result = []
    for path in sorted({p.resolve() for p in paths}, key=str):
        raw = path.read_bytes()
        result.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        for line in raw.decode().splitlines():
            if line.strip():
                row = json.loads(line)
                if isinstance(row, dict):
                    observed.add(_canonical(row))
                    source_rows.append(row)
    selected = [row for field in fields.values() for row in field]
    if any(_canonical(row) not in observed for row in selected):
        raise ValueError("SELECTED_ROW_NOT_IN_SOURCE_BYTES")
    evidence = {}
    for race_id, field in fields.items():
        created, key, chosen = _select_authoritative_run(source_rows, race_date, race_id)
        selected_ids = {str(row.get("horse_id") or "") for row in field}
        chosen_ids = {str(row.get("horse_id") or "") for row in chosen}
        if selected_ids != chosen_ids:
            raise ValueError(f"SELECTED_FIELD_NOT_EXACT_AUTHORITATIVE_RUN:{race_id}")
        selected_key = (
            str(field[0].get("run_id") or ""),
            str(field[0].get("created_at") or ""),
            str(field[0].get("off_time") or ""),
        )
        if selected_key != key:
            raise ValueError(f"SELECTED_RUN_NOT_LATEST_COMPLETE_PRE_OFF:{race_id}")
        normalized = sorted(chosen, key=lambda row: str(row.get("horse_id") or ""))
        evidence[str(race_id)] = {
            "run_id": key[0],
            "created_at": key[1],
            "off_time": key[2],
            "horse_ids": sorted(chosen_ids),
            "rows": normalized,
            "rows_hash": _hash(normalized),
            "latest_complete_attested": True,
        }
    return result, _hash(evidence), evidence


def _derive_evidence(now, race_date, captures, offs):
    if not offs:
        return "BACKFILLED", "ZERO_SELECTION_UNPROVEN_WITHOUT_TRUSTED_LEDGER"
    if now >= max(captures) and all(now < off for off in offs):
        return "GENUINELY_FORWARD", "TRUSTED_CLOCK_AFTER_SOURCE_BEFORE_ALL_OFFS"
    if now.date().isoformat() == race_date:
        return "BACKFILLED", "CREATED_OUTSIDE_FORWARD_WINDOW"
    return "RETROSPECTIVE", "HISTORICAL_AT_CREATION_TIME"


def build_forward_model_packet(
    *,
    race_date: str,
    selected_fields: dict[str, list[dict]],
    model_fields: dict[str, str],
    model_versions: dict[str, str] | None = None,
    source_paths: list[Path] | None = None,
    commit: str | None = None,
    diagnostics: dict | None = None,
) -> dict:
    now = _utc_now()
    if now.tzinfo is None:
        raise ValueError("TRUSTED_CLOCK_MUST_BE_AWARE")
    sources, selected_hash, source_evidence = _source_provenance(source_paths or [], selected_fields, race_date)
    captures = []
    offs = []
    validated = {}
    for rid, field in sorted(selected_fields.items()):
        if len(field) < 3:
            raise ValueError(f"INCOMPLETE_FIELD:{rid}")
        first = field[0]
        expected = (
            race_date,
            str(rid),
            str(first.get("run_id") or ""),
            str(first.get("off_time") or ""),
            str(first.get("created_at") or ""),
        )
        ids = set()
        if not all(expected):
            raise ValueError(f"SOURCE_RUN_IDENTITY_MISSING:{rid}")
        for row in field:
            actual = tuple(
                str(x or "")
                for x in (
                    row.get("race_date"),
                    row.get("race_id"),
                    row.get("run_id"),
                    row.get("off_time"),
                    row.get("created_at"),
                )
            )
            if actual != expected:
                raise ValueError(f"MIXED_SOURCE_RUN:{rid}")
            hid = str(row.get("horse_id") or "")
            if not hid or hid in ids:
                raise ValueError(f"RUNNER_IDENTITY_INVALID:{rid}")
            ids.add(hid)
            capture = _aware(row.get("created_at"))
            off = _off_datetime(race_date, row.get("off_time"))
            if capture is None or off is None or capture >= off:
                raise ValueError(f"SNAPSHOT_NOT_STRICTLY_PRE_OFF:{rid}:{hid}")
            captures.append(capture)
            offs.append(off)
        validated[str(rid)] = field
    evidence, reason = _derive_evidence(now, race_date, captures, offs)
    versions = model_versions or {}
    models = []
    for name, prob_field in sorted(model_fields.items()):
        races = []
        exclusions = []
        for rid, field in validated.items():
            probs = [_number(row.get(prob_field)) for row in field]
            if any(p is None or p < 0 or p > 1 for p in probs):
                exclusions.append({"race_id": rid, "reason": "MISSING_OR_INVALID_PROBABILITY"})
                continue
            if not math.isclose(sum(probs), 1, abs_tol=1e-6):
                exclusions.append({"race_id": rid, "reason": "PROBABILITIES_DO_NOT_SUM_TO_ONE", "sum": sum(probs)})
                continue
            runners = []
            for row, p in zip(field, probs, strict=True):
                odds = _number(row.get("captured_odds_dec"))
                odds = odds if odds is not None and odds > 1 else None
                ots = _aware(row.get("odds_capture_ts")) if odds is not None else None
                off = _off_datetime(race_date, row["off_time"])
                if odds is not None and (ots is None or ots >= off):
                    raise ValueError(f"CAPTURE_PRICE_TIME_INVALID:{rid}:{row['horse_id']}")
                runners.append(
                    {
                        "horse_id": str(row["horse_id"]),
                        "horse": row.get("horse"),
                        "probability": p,
                        "captured_odds_dec": odds,
                        "odds_capture_ts": ots.isoformat() if ots else None,
                        "price_source": row.get("price_source") if odds else None,
                    }
                )
            runners.sort(key=lambda r: (-r["probability"], r["horse_id"]))
            prices = [r["captured_odds_dec"] for r in runners]
            favs = None
            if all(p is not None for p in prices):
                m = min(prices)
                favs = sorted(r["horse_id"] for r in runners if r["captured_odds_dec"] == m)
            first = field[0]
            off = _off_datetime(race_date, first["off_time"])
            races.append(
                {
                    "race_id": rid,
                    "course": first.get("course"),
                    "off_time": first["off_time"],
                    "off_ts": off.isoformat(),
                    "snapshot_run_id": first["run_id"],
                    "snapshot_created_at": _aware(first["created_at"]).isoformat(),
                    "snapshot_strictly_pre_off": True,
                    "field_size": len(runners),
                    "selection_horse_id": runners[0]["horse_id"],
                    "market_favourite_horse_ids": favs,
                    "runners": runners,
                }
            )
        models.append(
            {
                "model_name": name,
                "model_version": versions.get(name, "UNSPECIFIED"),
                "probability_field": prob_field,
                "probability_contract": "NORMALIZED_PROBABILITY_SUM_ONE",
                "race_count": len(races),
                "selection_count": len(races),
                "zero_selection_day": not races,
                "exclusions": exclusions,
                "races": races,
            }
        )
    identity = {
        "race_date": race_date,
        "models": [{"model_name": m["model_name"], "model_version": m["model_version"]} for m in models],
        "schema_version": SCHEMA_VERSION,
    }
    body = {
        "schema_version": SCHEMA_VERSION,
        "packet_identity": identity,
        "packet_identity_hash": _hash(identity),
        "race_date": race_date,
        "created_at": now.isoformat(),
        "clock_provenance": "SYSTEM_UTC",
        "evidence_class": evidence,
        "evidence_reason": reason,
        "commit": commit or _git_commit(),
        "source_files": sources,
        "selected_source_hash": selected_hash,
        "selected_source_evidence": source_evidence,
        "selection_contract": "verified source bytes; authoritative latest complete coherent run strictly before exact off",
        "diagnostics": diagnostics or {},
        "models": models,
        "safety": {
            "paper_sim_only": True,
            "execution_allowed": False,
            "production_learning_allowed": False,
            "weights_changed": False,
        },
    }
    return {**body, "packet_hash": _hash(body)}


def _expected_packet_identity(packet):
    models = packet.get("models")
    if not isinstance(models, list):
        raise ValueError("PACKET_MODELS_MISSING")
    return {
        "race_date": packet.get("race_date"),
        "models": [{"model_name": m.get("model_name"), "model_version": m.get("model_version")} for m in models],
        "schema_version": SCHEMA_VERSION,
    }


def canonical_packet_path(packet, lab_root):
    return lab_root / "packets" / packet["race_date"] / f"{packet['packet_identity_hash']}.json"


def _atomic_immutable_json(payload, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    tmp = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        tmp = Path(tmp_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            if path.read_bytes() == raw:
                return "VALIDATED_IDENTICAL"
            raise FileExistsError(f"IMMUTABLE_CONFLICT:{path}") from None
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            os.fsync(directory_fd)
            os.close(directory_fd)
        except OSError:
            pass
        return "CREATED"
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass


def write_immutable_packet(packet: dict, lab_root: Path) -> tuple[str, Path]:
    body = {k: v for k, v in packet.items() if k != "packet_hash"}
    if packet.get("packet_hash") != _hash(body):
        raise ValueError("PACKET_HASH_MISMATCH")
    expected = _expected_packet_identity(packet)
    if packet.get("packet_identity") != expected or packet.get("packet_identity_hash") != _hash(expected):
        raise ValueError("PACKET_IDENTITY_MISMATCH")
    path = canonical_packet_path(packet, lab_root)
    return _atomic_immutable_json(packet, path), path


def write_immutable_evaluation(evaluation, lab_root):
    expected_identity = {
        "schema_version": evaluation.get("schema_version"),
        "packet_hashes": evaluation.get("packet_hashes"),
        "result_source_hashes_by_date": evaluation.get("result_source_hashes_by_date"),
        "methodology": evaluation.get("methodology"),
    }
    identity = evaluation.get("evaluation_identity")
    identity_hash = evaluation.get("evaluation_identity_hash")
    if identity != expected_identity or identity_hash != _hash(expected_identity):
        raise ValueError("EVALUATION_IDENTITY_MISMATCH")
    body = {key: value for key, value in evaluation.items() if key != "evaluation_hash"}
    if evaluation.get("evaluation_hash") != _hash(body):
        raise ValueError("EVALUATION_HASH_MISMATCH")
    path = lab_root / "evaluations" / f"{identity_hash}.json"
    return _atomic_immutable_json(evaluation, path), path


def _truth_index(rows):
    index = {}
    hashes = {}
    for row in rows:
        date = str(row.get("date") or row.get("run_date") or "")
        race = str(row.get("race_id") or "")
        horse = str(row.get("horse_id") or "")
        if not date or not race or not horse:
            raise ValueError("TRUTH_IDENTITY_MISSING")
        if row.get("result_source_complete") is not True:
            raise ValueError(f"RESULT_SOURCE_INCOMPLETE:{date}")
        h = str(row.get("result_source_hash") or "")
        if not h or (date in hashes and hashes[date] != h):
            raise ValueError(f"RESULT_SOURCE_HASH_AMBIGUOUS:{date}")
        hashes[date] = h
        key = (date, race, horse)
        if key in index:
            facts = (
                "subject_outcome_status",
                "settlement_status",
                "win",
                "frame",
                "settled_sp_dec",
                "sp_dec",
                "official_evaluation_eligible",
                "dashboard_metrics_eligible",
            )
            if any(index[key].get(x) != row.get(x) for x in facts):
                raise ValueError(f"TRUTH_IDENTITY_CONFLICT:{date}:{race}:{horse}")
        else:
            index[key] = row
    return index, hashes


def _ece(obs, bins=10):
    if not obs:
        return None, []
    error = 0
    out = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        b = [(p, y) for p, y in obs if lo <= p < hi or (i == bins - 1 and p == 1)]
        if b:
            pm = statistics.fmean(p for p, _ in b)
            rate = statistics.fmean(y for _, y in b)
            error += len(b) / len(obs) * abs(pm - rate)
            out.append({"lower": lo, "upper": hi, "count": len(b), "predicted_mean": pm, "observed_rate": rate})
    return error, out


def _drawdown(pnls):
    equity = peak = dd = 0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    return dd


def _comparator(rows, prefix):
    available = [r for r in rows if r[prefix + "_available"]]
    settled = [r for r in available if r[prefix + "_settled"]]
    pnls = [r[prefix + "_pnl"] for r in settled if r[prefix + "_pnl"] is not None]
    return {
        "selections": len(rows),
        "available": len(available),
        "settled": len(settled),
        "wins": sum(r[prefix + "_win"] is True for r in settled),
        "priced": len(pnls),
        "profit": sum(pnls),
        "roi": sum(pnls) / len(pnls) if pnls else None,
    }


def _metrics(rows, zero_days):
    settled = [r for r in rows if r["settlement_status"] == "SETTLED"]
    captured = [r for r in settled if r["captured_pnl"] is not None]
    sp = [r for r in settled if r["sp_pnl"] is not None]
    pnls = [r["captured_pnl"] for r in captured]
    winner_pnls = [r["captured_pnl"] for r in captured if r["win"]]
    profit = sum(pnls)
    ece, bins = _ece([(r["selected_probability"], int(r["win"])) for r in settled])
    returns = [r["captured_return"] for r in captured]
    return {
        "days": len({r["race_date"] for r in rows} | zero_days),
        "zero_selection_days": len(zero_days),
        "races": len(rows),
        "selections": len(rows),
        "settled": len(settled),
        "void": sum(r["settlement_status"] == "VOID" for r in rows),
        "wins": sum(r["win"] is True for r in settled),
        "frames": sum(r["frame"] is True for r in settled),
        "hit_rate": statistics.fmean(float(r["win"]) for r in settled) if settled else None,
        "frame_rate": statistics.fmean(float(r["frame"]) for r in settled) if settled else None,
        "brier_multiclass_full_field": statistics.fmean(r["brier"] for r in settled) if settled else None,
        "log_loss_multiclass_winner_probability": statistics.fmean(r["log_loss"] for r in settled) if settled else None,
        "calibration_error_top_selection": ece,
        "calibration_bins": bins,
        "captured_profit": profit,
        "captured_roi": profit / len(captured) if captured else None,
        "sp_profit": sum(r["sp_pnl"] for r in sp),
        "sp_roi": sum(r["sp_pnl"] for r in sp) / len(sp) if sp else None,
        "mean_clv_price_ratio": statistics.fmean(
            r["clv_price_ratio"] for r in settled if r["clv_price_ratio"] is not None
        )
        if any(r["clv_price_ratio"] is not None for r in settled)
        else None,
        "max_drawdown": _drawdown(pnls),
        "largest_return_concentration": max(returns, default=0) / sum(returns) if sum(returns) > 0 else None,
        "leave_largest_winner_out_profit": profit - max(winner_pnls, default=0),
        "leave_largest_winner_out_roi": (profit - max(winner_pnls, default=0))
        / max(1, len(captured) - (1 if winner_pnls else 0)),
        "production_comparator": _comparator(rows, "production"),
        "market_favourite_comparator": _comparator(rows, "market"),
    }


def day_block_bootstrap(records, *, zero_days=None, samples=1000, seed=1981):
    days = defaultdict(list)
    for r in records:
        days[r["race_date"]].append(r)
    all_days = sorted(set(days) | set(zero_days or set()))
    out = {
        "days": len(all_days),
        "races": len(records),
        "selections": len(records),
        "zero_selection_days": len(set(zero_days or set())),
        "samples": samples,
        "seed": seed,
        "intervals_95pct": {},
    }
    if not all_days or samples <= 0:
        return out
    rng = random.Random(seed)
    series = defaultdict(list)
    for _ in range(samples):
        sample = [r for _i in all_days for r in days.get(all_days[rng.randrange(len(all_days))], [])]
        m = _metrics(sample, set())
        series["captured_daily_profit"].append(sum((r["captured_pnl"] or 0) for r in sample) / len(all_days))
        for k in (
            "hit_rate",
            "brier_multiclass_full_field",
            "log_loss_multiclass_winner_probability",
            "captured_roi",
            "sp_roi",
        ):
            if m[k] is not None:
                series[k].append(m[k])
    for k, v in series.items():
        v.sort()
        out["intervals_95pct"][k] = [v[int(0.025 * (len(v) - 1))], v[int(0.975 * (len(v) - 1))]]
    return out


def evaluate_forward_packets(
    packets, canonical_rows, *, production_model="MAIN_VELO_PRIME", bootstrap_samples=1000, bootstrap_seed=1981
):
    truth, truth_hashes = _truth_index(canonical_rows)
    unique = {}
    identities = {}
    claims = {}
    for p in packets:
        body = {k: v for k, v in p.items() if k != "packet_hash"}
        if p.get("packet_hash") != _hash(body):
            raise ValueError("PACKET_HASH_MISMATCH")
        expected_identity = _expected_packet_identity(p)
        identity = p.get("packet_identity_hash")
        if p.get("packet_identity") != expected_identity or identity != _hash(expected_identity):
            raise ValueError("PACKET_IDENTITY_MISMATCH")
        source_evidence = p.get("selected_source_evidence")
        if not isinstance(source_evidence, dict) or p.get("selected_source_hash") != _hash(source_evidence):
            raise ValueError("SELECTED_SOURCE_EVIDENCE_HASH_MISMATCH")
        if identity in identities and identities[identity] != p["packet_hash"]:
            raise ValueError("CONFLICTING_PACKET_IDENTITY")
        for model in p.get("models", []):
            claim = (p.get("race_date"), model.get("model_name"), model.get("model_version"))
            if claim in claims and claims[claim] != p["packet_hash"]:
                raise ValueError("CONFLICTING_MODEL_DATE_VERSION_PACKET")
            claims[claim] = p["packet_hash"]
        identities[identity] = p["packet_hash"]
        unique[p["packet_hash"]] = p
    packets = sorted(unique.values(), key=lambda p: (p["race_date"], p["packet_identity_hash"], p["packet_hash"]))
    records = defaultdict(list)
    zero = defaultdict(set)
    production = {}
    for p in packets:
        ev = p.get("evidence_class")
        if ev not in EVIDENCE_CLASSES or (not p.get("source_files") and any(m["races"] for m in p["models"])):
            raise ValueError("PACKET_PROVENANCE_INVALID")
        if p.get("clock_provenance") != "SYSTEM_UTC":
            raise ValueError("CLOCK_PROVENANCE_INVALID")
        for model in p["models"]:
            cohort = (ev, model["model_name"], model["model_version"])
            if model["zero_selection_day"]:
                zero[cohort].add(p["race_date"])
            for race in model["races"]:
                snap, off, created = (
                    _aware(race["snapshot_created_at"]),
                    _aware(race["off_ts"]),
                    _aware(p["created_at"]),
                )
                if snap is None or off is None or snap >= off or race.get("snapshot_strictly_pre_off") is not True:
                    raise ValueError("POST_OFF_OR_UNPROVEN_SNAPSHOT")
                if ev == "GENUINELY_FORWARD" and (created is None or created < snap or created >= off):
                    raise ValueError("FORGED_FORWARD_TIMING")
                probabilities = [_number(r.get("probability")) for r in race["runners"]]
                if any(value is None or value < 0 or value > 1 for value in probabilities) or not math.isclose(
                    sum(probabilities), 1, abs_tol=1e-6
                ):
                    raise ValueError("PACKET_PROBABILITY_CONTRACT_INVALID")
                for runner in race["runners"]:
                    odds = _number(runner.get("captured_odds_dec"))
                    if odds is not None:
                        capture = _aware(runner.get("odds_capture_ts"))
                        if odds <= 1 or capture is None or capture >= off:
                            raise ValueError("PACKET_CAPTURE_PRICE_CONTRACT_INVALID")
                proof = p["selected_source_evidence"].get(str(race["race_id"]))
                if (
                    not isinstance(proof, dict)
                    or proof.get("latest_complete_attested") is not True
                    or proof.get("rows_hash") != _hash(proof.get("rows"))
                ):
                    raise ValueError("SELECTED_SOURCE_ATTESTATION_INVALID")
                proof_ids = {str(row.get("horse_id") or "") for row in proof["rows"]}
                packet_ids = {str(row.get("horse_id") or "") for row in race["runners"]}
                if (
                    proof_ids != packet_ids
                    or proof.get("horse_ids") != sorted(packet_ids)
                    or proof.get("run_id") != race.get("snapshot_run_id")
                    or proof.get("created_at") != str(proof["rows"][0].get("created_at"))
                    or proof.get("off_time") != race.get("off_time")
                ):
                    raise ValueError("SELECTED_SOURCE_PACKET_MISMATCH")
                source_by_id = {str(row["horse_id"]): row for row in proof["rows"]}
                for runner in race["runners"]:
                    source = source_by_id[str(runner["horse_id"])]
                    source_odds = _number(source.get("captured_odds_dec"))
                    source_odds = source_odds if source_odds is not None and source_odds > 1 else None
                    source_capture = _aware(source.get("odds_capture_ts")) if source_odds is not None else None
                    if (
                        _number(source.get(model.get("probability_field"))) != _number(runner.get("probability"))
                        or source_odds != _number(runner.get("captured_odds_dec"))
                        or (source_capture.isoformat() if source_capture else None) != runner.get("odds_capture_ts")
                    ):
                        raise ValueError("PACKET_SELECTION_NOT_DERIVED_FROM_EMBEDDED_SOURCE")
                expected_selection = sorted(
                    race["runners"], key=lambda row: (-float(row["probability"]), str(row["horse_id"]))
                )[0]["horse_id"]
                if race.get("selection_horse_id") != expected_selection:
                    raise ValueError("PACKET_SELECTION_NOT_DERIVED_FROM_EMBEDDED_SOURCE")
                key = (p["race_date"], str(race["race_id"]), ev)
                if model["model_name"] == production_model:
                    production_id = str(race["selection_horse_id"])
                    production_runner = next(
                        runner for runner in race["runners"] if str(runner["horse_id"]) == production_id
                    )
                    value = {
                        "model_version": model["model_version"],
                        "selection_horse_id": production_id,
                        "packet_hash": p["packet_hash"],
                        "selected_runner": production_runner,
                        "snapshot_created_at": race["snapshot_created_at"],
                        "off_ts": race["off_ts"],
                        "selected_source_hash": p["selected_source_hash"],
                    }
                    if key in production and production[key] != value:
                        raise ValueError("PRODUCTION_COMPARATOR_CONFLICT")
                    production[key] = value
    for p in packets:
        date = p["race_date"]
        ev = p["evidence_class"]
        if date not in truth_hashes and any(m["races"] for m in p["models"]):
            raise ValueError(f"MISSING_TRUTH_DATE:{date}")
        for model in p["models"]:
            cohort = (ev, model["model_name"], model["model_version"])
            for race in model["races"]:
                rid = str(race["race_id"])
                field = []
                packet_horse_ids = {str(runner["horse_id"]) for runner in race["runners"]}
                truth_horse_ids = {
                    horse for (truth_date, truth_race, horse) in truth if truth_date == date and truth_race == rid
                }
                if packet_horse_ids != truth_horse_ids:
                    raise ValueError(f"CANONICAL_RACE_FIELD_MISMATCH:{date}:{rid}")
                for runner in race["runners"]:
                    row = truth.get((date, rid, str(runner["horse_id"])))
                    if row is None:
                        raise ValueError(f"CANONICAL_RACE_COVERAGE_INCOMPLETE:{date}:{rid}")
                    if (
                        row.get("subject_outcome_status") == "UNKNOWN"
                        or row.get("settlement_status") not in {"SETTLED", "VOID"}
                        or row.get("dashboard_metrics_eligible") is not True
                    ):
                        raise ValueError(f"CANONICAL_RACE_NOT_GOVERNED:{date}:{rid}")
                    field.append(row)
                winners = {
                    str(r["horse_id"]) for r, t in zip(race["runners"], field, strict=True) if t.get("win") is True
                }
                if len(winners) != 1:
                    raise ValueError(f"CANONICAL_WINNER_UNRESOLVED:{date}:{rid}")
                sid = str(race["selection_horse_id"])
                selected = next(r for r in race["runners"] if str(r["horse_id"]) == sid)
                st = truth[(date, rid, sid)]
                settlement = st["settlement_status"]
                if settlement == "SETTLED" and st.get("official_evaluation_eligible") is not True:
                    raise ValueError(f"CANONICAL_SELECTION_INELIGIBLE:{date}:{rid}")
                win = st.get("win") is True
                captured = _number(selected.get("captured_odds_dec"))
                sp = _number(st.get("settled_sp_dec") or st.get("sp_dec"))
                sp = sp if sp is not None and sp > 1 else None
                cr = None if captured is None or settlement == "VOID" else captured if win else 0
                sr = None if sp is None or settlement == "VOID" else sp if win else 0
                wp = sum(float(r["probability"]) for r in race["runners"] if str(r["horse_id"]) in winners)
                production_value = production.get((date, rid, ev))
                pid = production_value["selection_horse_id"] if production_value else None
                ptruth = truth.get((date, rid, pid)) if pid else None
                prunner = production_value["selected_runner"] if production_value else None
                favs = race.get("market_favourite_horse_ids")
                fid = favs[0] if isinstance(favs, list) and len(favs) == 1 else None
                ftruth = truth.get((date, rid, fid)) if fid else None
                frunner = next((r for r in race["runners"] if str(r["horse_id"]) == fid), None)

                def comp(cid, runner, trow):
                    available = cid is not None and trow is not None
                    settled = (
                        available
                        and trow.get("settlement_status") == "SETTLED"
                        and trow.get("official_evaluation_eligible") is True
                    )
                    won = trow.get("win") is True if settled else None
                    odds = _number(runner.get("captured_odds_dec")) if runner and settled else None
                    return available, settled, won, (odds - 1 if won else -1) if odds is not None else None

                pa, ps, pw, pp = comp(pid, prunner, ptruth)
                ma, ms, mw, mp = comp(fid, frunner, ftruth)
                records[cohort].append(
                    {
                        "race_date": date,
                        "race_id": rid,
                        "off_ts": race["off_ts"],
                        "selection_horse_id": sid,
                        "packet_hash": p["packet_hash"],
                        "selected_probability": float(selected["probability"]),
                        "brier": sum(
                            (float(r["probability"]) - (1 if str(r["horse_id"]) in winners else 0)) ** 2
                            for r in race["runners"]
                        ),
                        "log_loss": -math.log(max(wp, EPSILON)),
                        "settlement_status": settlement,
                        "win": win if settlement == "SETTLED" else None,
                        "frame": st.get("frame") if settlement == "SETTLED" else None,
                        "captured_return": cr,
                        "captured_pnl": None if cr is None else cr - 1,
                        "sp_pnl": None if sr is None else sr - 1,
                        "clv_price_ratio": captured / sp if captured and sp else None,
                        "production_available": pa,
                        "production_settled": ps,
                        "production_win": pw,
                        "production_pnl": pp,
                        "production_packet_hash": production_value["packet_hash"] if production_value else None,
                        "production_captured_odds_dec": prunner.get("captured_odds_dec") if prunner else None,
                        "production_price_source": prunner.get("price_source") if prunner else None,
                        "production_odds_capture_ts": prunner.get("odds_capture_ts") if prunner else None,
                        "production_snapshot_created_at": production_value["snapshot_created_at"]
                        if production_value
                        else None,
                        "market_available": ma,
                        "market_settled": ms,
                        "market_win": mw,
                        "market_pnl": mp,
                    }
                )
    evidence = {k: {} for k in EVIDENCE_CLASSES}
    for ev, name, version in sorted(set(records) | set(zero)):
        rows = sorted(
            records[(ev, name, version)],
            key=lambda r: (_aware(r["off_ts"]), r["race_id"], r["selection_horse_id"], r["packet_hash"]),
        )
        evidence[ev].setdefault(name, {})[version] = {
            "metrics": _metrics(rows, zero[(ev, name, version)]),
            "day_block_bootstrap": day_block_bootstrap(
                rows, zero_days=zero[(ev, name, version)], samples=bootstrap_samples, seed=bootstrap_seed
            ),
            "records": rows,
        }
    methodology = {
        "evaluator_version": "forward-model-evaluator-v2",
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": bootstrap_seed,
        "production_model": production_model,
        "calibration_bins": 10,
        "brier_convention": "MULTICLASS_FULL_FIELD_SUM_SQUARED_ERROR",
        "log_loss_convention": "NEGATIVE_LOG_WINNER_PROBABILITY",
    }
    evaluation_identity = {
        "schema_version": SCHEMA_VERSION,
        "packet_hashes": sorted(unique),
        "result_source_hashes_by_date": dict(sorted(truth_hashes.items())),
        "methodology": methodology,
    }
    out = {
        "schema_version": SCHEMA_VERSION,
        "evaluation_identity": evaluation_identity,
        "evaluation_identity_hash": _hash(evaluation_identity),
        "methodology": methodology,
        "evaluation_contract": "frozen packet plus complete governed canonical truth only",
        "result_source_hashes_by_date": dict(sorted(truth_hashes.items())),
        "packet_hashes": sorted(unique),
        "evidence": evidence,
        "safety": {"paper_sim_only": True, "production_learning_allowed": False, "promotion_authorized": False},
    }
    return {**out, "evaluation_hash": _hash(out)}


def _read_scorecard(path):
    with path.open(newline="", encoding="utf-8") as h:
        rows = list(csv.DictReader(h))
    for row in rows:
        for key in (
            "result_source_complete",
            "win",
            "frame",
            "official_evaluation_eligible",
            "dashboard_metrics_eligible",
        ):
            row[key] = str(row.get(key) or "").lower() == "true"
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--date", required=True)
    b.add_argument("--data-dir", type=Path, required=True)
    b.add_argument("--model", action="append", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--packet", type=Path, action="append", required=True)
    e.add_argument("--scorecard", type=Path, required=True)
    e.add_argument("--bootstrap-samples", type=int, default=1000)
    args = parser.parse_args()
    if args.command == "build":
        fields, diag = select_latest_pre_off_fields(args.data_dir, args.date, args.date)
        mf = {}
        versions = {}
        for spec in args.model:
            name, rest = spec.split("=", 1)
            parts = rest.split(":", 1)
            mf[name] = parts[0]
            versions[name] = parts[1] if len(parts) == 2 else "UNSPECIFIED"
        packet = build_forward_model_packet(
            race_date=args.date,
            selected_fields=fields,
            model_fields=mf,
            model_versions=versions,
            source_paths=sorted(args.data_dir.glob(f"runner_snapshots_{args.date.replace('-', '_')}*.jsonl")),
            diagnostics=diag,
        )
        status, path = write_immutable_packet(packet, LAB_ROOT)
        print(status, path)
        return 0
    packets = [json.loads(p.read_text(encoding="utf-8")) for p in args.packet]
    out = evaluate_forward_packets(packets, _read_scorecard(args.scorecard), bootstrap_samples=args.bootstrap_samples)
    status, path = write_immutable_evaluation(out, LAB_ROOT)
    print(status, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
