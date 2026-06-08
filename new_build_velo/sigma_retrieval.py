"""
Shadow-only sigma retrieval corpus utilities.

This module standardises old VÉLØ sigma memory into discrete, regime-aware
records for future KNN/Bayesian evidence layers. It does not score races, write
live tables, or alter any live/shadow runtime state.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "sigma_retrieval_corpus_v1"
UNKNOWN = "UNKNOWN"
DEFAULT_KNN_WEIGHTS = {
    "mds_band": 5.0,
    "vp_band": 4.0,
    "improvement_band": 3.0,
    "release_band": 3.0,
    "longshot_specialty": 2.5,
    "sp_band": 2.0,
    "place_band": 1.5,
    "sidecar_tier": 1.5,
    "course_type": 1.0,
    "g_adjustment_applied": 1.0,
    "regime_id": 0.5,
}
DEFAULT_WIN_PRIOR_ALPHA = 1.0
DEFAULT_WIN_PRIOR_BETA = 4.0
DEFAULT_FRAME_PRIOR_RATE = 0.48
DEFAULT_FRAME_PRIOR_STRENGTH = 5.0
DEFAULT_DOCTRINE_DIMS = (
    "mds_band",
    "vp_band",
    "improvement_band",
    "release_band",
    "place_band",
    "sidecar_tier",
    "course_type",
    # sp_band intentionally excluded: market consensus, not a VELO signal.
    # SP patterns inflate lift artificially (SP_LT_2 base rate = ~63% win).
    # Include sp_band in KNN retrieval weights but not in doctrine mining.
)


def load_sp_enrichment(csv_path: Path) -> dict[str, float]:
    """Load {race_id: sp_decimal} from an innovation protocol CSV."""
    if not csv_path.exists():
        return {}
    result: dict[str, float] = {}
    try:
        with csv_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                rid = str(row.get("race_id") or "").strip()
                sp_raw = str(row.get("sp_decimal") or "").strip()
                if rid and sp_raw:
                    try:
                        result[rid] = float(sp_raw)
                    except ValueError:
                        pass
    except Exception:
        pass
    return result


@dataclass(frozen=True)
class BuildPaths:
    root: Path
    sigma_dump: Path
    verdict_glob: str = "velo_prime_verdicts_*.json"
    observability_glob: str = "velo_run_observability_*.json"
    output_jsonl: Path | None = None
    report_json: Path | None = None
    report_md: Path | None = None
    sp_enrichment_csv: Path | None = None

    def resolved(self) -> "BuildPaths":
        base = self.root / "data" / "sigma_memory"
        default_sp = self.root / "data" / "velo_innovation_protocol_1k_deduped.csv"
        return BuildPaths(
            root=self.root,
            sigma_dump=self.sigma_dump,
            verdict_glob=self.verdict_glob,
            observability_glob=self.observability_glob,
            output_jsonl=self.output_jsonl or base / "sigma_retrieval_corpus_v1.jsonl",
            report_json=self.report_json or base / "sigma_retrieval_corpus_v1_report.json",
            report_md=self.report_md or base / "sigma_retrieval_corpus_v1_report.md",
            sp_enrichment_csv=self.sp_enrichment_csv if self.sp_enrichment_csv is not None else default_sp,
        )


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def norm_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\([a-z]{2,3}\)", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or UNKNOWN


def date_from_name(path: Path) -> str | None:
    match = re.search(r"(\d{4})[_-](\d{2})[_-](\d{2})", path.name)
    if not match:
        return None
    return "-".join(match.groups())


def band_prob(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return UNKNOWN
    if v < 0.10:
        return "P00_10"
    if v < 0.20:
        return "P10_20"
    if v < 0.30:
        return "P20_30"
    if v < 0.40:
        return "P30_40"
    if v < 0.50:
        return "P40_50"
    return "P50_PLUS"


def g_adjustment_applied(verdict: dict[str, Any] | None) -> bool | None:
    if not verdict:
        return None
    vp = verdict.get("vp")
    g_base = verdict.get("g_base_prob")
    try:
        vp_f = float(vp)
        base_f = float(g_base)
    except (TypeError, ValueError):
        return None
    return abs(vp_f - base_f) >= 0.005


def longshot_specialty(value: Any, sp_value: Any = None) -> str:
    try:
        prob = float(value)
    except (TypeError, ValueError):
        return UNKNOWN
    sp_band_value = band_sp(sp_value)
    if prob >= 0.50 and sp_band_value in {"SP_8_16", "SP_16_PLUS", UNKNOWN}:
        return "LONGSHOT_HIGH"
    if prob >= 0.25:
        return "LONGSHOT_MEDIUM"
    return "LONGSHOT_LOW"


def band_sp(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return UNKNOWN
    if v < 2:
        return "SP_LT_2"
    if v < 4:
        return "SP_2_4"
    if v < 8:
        return "SP_4_8"
    if v < 16:
        return "SP_8_16"
    return "SP_16_PLUS"


def course_type(value: Any) -> str:
    text = str(value or "").lower()
    if "(aw)" in text or " aw" in text or "all-weather" in text:
        return "AW"
    return UNKNOWN


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def derive_outcome(row: dict[str, Any]) -> str:
    outcome = str(row.get("outcome") or "").strip().upper()
    if outcome in {"WIN", "WON"}:
        return "WIN"
    if outcome in {"PLACED", "PLACE", "FRAME", "FRAMED"}:
        return "FRAME"
    if outcome in {"MISS", "LOST", "LOSE"}:
        return "MISS"
    correct = row.get("top_strike_correct")
    if correct is True:
        return "WIN"
    if correct is False:
        return "MISS"
    return UNKNOWN


def outcome_bool(outcome: str) -> tuple[bool | None, bool | None]:
    if outcome == "WIN":
        return True, True
    if outcome == "FRAME":
        return False, True
    if outcome == "MISS":
        return False, False
    return None, None


def miss_type(row: dict[str, Any], outcome: str) -> str:
    reason = norm_text(row.get("miss_reason"))
    if outcome == "WIN":
        return "NONE"
    if outcome == "FRAME":
        return "FRAME_NOT_WIN"
    if reason != UNKNOWN:
        return reason.upper()
    if outcome == "MISS":
        return "MISS_UNCLASSIFIED"
    return UNKNOWN


def load_observability_by_date(root: Path, glob: str) -> dict[str, dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "data").glob(glob)):
        payload = load_json(path, {})
        date = payload.get("date") or date_from_name(path)
        if not date:
            continue
        current = by_date.get(date)
        current_ts = str(current.get("timestamp") if current else "")
        payload_ts = str(payload.get("timestamp") or "")
        if current is None or payload_ts >= current_ts:
            by_date[date] = payload
    return by_date


def extract_g_threshold(flags: Iterable[Any]) -> str | None:
    for flag in flags or []:
        match = re.search(r"g_threshold:([0-9.]+)", str(flag))
        if match:
            return f"G_THRESHOLD_{match.group(1)}"
    return None


def load_verdict_top_by_race(root: Path, glob: str) -> dict[str, dict[str, Any]]:
    by_race: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "data").glob(glob)):
        date = date_from_name(path)
        payload = load_json(path, [])
        if not isinstance(payload, list):
            continue
        for race in payload:
            if not isinstance(race, dict):
                continue
            race_id = str(race.get("race_id") or "")
            top = race.get("top") if isinstance(race.get("top"), dict) else {}
            signal_stack = race.get("signal_stack") if isinstance(race.get("signal_stack"), dict) else {}
            if not race_id:
                continue
            flags = top.get("verdict_flags") or []
            by_race[race_id] = {
                "date": date,
                "course": race.get("course"),
                "off_time": race.get("off_time"),
                "race_name": race.get("race_name"),
                "horse": top.get("horse"),
                "horse_id": top.get("horse_id"),
                "vp": top.get("velo_prime_prob", signal_stack.get("vp")),
                "tier": race.get("tier") or signal_stack.get("tier"),
                "mds": top.get("market_deception_score", signal_stack.get("mds")),
                "improvement_score": top.get("improvement_score", signal_stack.get("improvement")),
                "place_prob": top.get("place_prob", signal_stack.get("place_prob")),
                "release_day_prob": top.get("release_day_prob"),
                "longshot_prob": top.get("longshot_prob"),
                "g_base_prob": top.get("g_base_prob"),
                "active_components": top.get("active_components", []),
                "excluded_from_ensemble": top.get("excluded_from_ensemble", []),
                "ensemble_version": top.get("ensemble_version"),
                "signal_contract_version": top.get("signal_contract_version"),
                "doctrines_fired": top.get("doctrines_fired", []),
                "threshold": extract_g_threshold(flags),
                "source_file": str(path.relative_to(root)),
            }
    return by_race


def infer_regime(
    date: str | None,
    verdict: dict[str, Any] | None,
    observability_by_date: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    obs = observability_by_date.get(date or "") or {}
    active_formula = obs.get("active_formula") or UNKNOWN
    source_truth = obs.get("source_truth") or UNKNOWN
    feature_health = obs.get("feature_health") or UNKNOWN
    learning_gate = obs.get("learning_gate") or UNKNOWN
    git_sha = obs.get("git_commit_sha") or obs.get("extra", {}).get("git_commit_sha")
    model_version = (
        (verdict or {}).get("ensemble_version")
        or active_formula
        or UNKNOWN
    )
    doctrine_version = (
        (verdict or {}).get("signal_contract_version")
        or active_formula
        or "REGIME_UNKNOWN"
    )
    threshold = (verdict or {}).get("threshold") or "VP_GATE_UNKNOWN"
    if threshold == "VP_GATE_UNKNOWN":
        tier = (verdict or {}).get("tier")
        if tier:
            threshold = f"TIER_{tier}_LEGACY_GATE_UNKNOWN"
    parts = [str(doctrine_version), str(model_version), str(threshold), str(source_truth), str(feature_health), str(git_sha or "NO_SHA")]
    regime_id = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    confidence = "HIGH" if obs and git_sha else "MEDIUM" if obs else "LOW_REGIME_INFERRED"
    return {
        "doctrine_version": doctrine_version,
        "model_version": model_version,
        "threshold_at_race_time": threshold,
        "regime_id": regime_id,
        "regime_confidence": confidence,
        "git_commit_sha": git_sha,
        "source_truth": source_truth,
        "feature_health": feature_health,
        "learning_gate": learning_gate,
        "active_formula": active_formula,
    }


def standardise_record(
    row: dict[str, Any],
    verdict_by_race: dict[str, dict[str, Any]],
    observability_by_date: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    race_id = str(row.get("race_id") or "")
    verdict = verdict_by_race.get(race_id, {})
    date = row.get("date") or verdict.get("date")
    course = row.get("track") or row.get("course") or verdict.get("course")
    outcome = derive_outcome(row)
    won, framed = outcome_bool(outcome)
    regime = infer_regime(date, verdict, observability_by_date)
    vp = row.get("verdict_score")
    if vp is None:
        vp = verdict.get("vp")
    mds = verdict.get("mds")
    improvement = verdict.get("improvement_score")
    release_day = verdict.get("release_day_prob")
    longshot = verdict.get("longshot_prob")
    place = verdict.get("place_prob")
    g_applied = g_adjustment_applied(verdict)
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_record_type": "old_velo_sigma_audit",
        "shadow_only": True,
        "live_velo_impact": False,
        "shadow_velo_impact": False,
        "new_build_velo_impact": False,
        "race_id": race_id,
        "race_date": date,
        "course": course,
        "off_time": row.get("off_time") or verdict.get("off_time"),
        "horse": verdict.get("horse"),
        "horse_id": verdict.get("horse_id"),
        "outcome": outcome,
        "won": won,
        "framed": framed,
        "miss_type_outcome": miss_type(row, outcome),
        "outcome_confidence": "HIGH_SIGMA_AUDIT" if outcome != UNKNOWN else "OUTCOME_UNKNOWN",
        "vp": vp,
        "vp_band": band_prob(vp),
        "sp_band": band_sp(row.get("sp")),
        "mds": mds,
        "mds_band": band_prob(mds),
        "improvement_score": improvement,
        "improvement_band": band_prob(improvement),
        "release_day_prob": release_day,
        "release_band": band_prob(release_day),
        "longshot_prob": longshot,
        "longshot_band": band_prob(longshot),
        "longshot_specialty": longshot_specialty(longshot, row.get("sp")),
        "place_prob": place,
        "place_band": band_prob(place),
        "g_base_prob": verdict.get("g_base_prob"),
        "g_adjustment_applied": g_applied,
        "sidecar_tier_at_race_time": row.get("decision_tier") or verdict.get("tier") or UNKNOWN,
        "markov_state": band_prob(release_day),
        "or_band": UNKNOWN,
        "course_type": course_type(course),
        "going_code": UNKNOWN,
        "class_band": UNKNOWN,
        "distance_bucket": UNKNOWN,
        "latent_concepts_fired": verdict.get("doctrines_fired", []),
        "active_components": verdict.get("active_components", []),
        "excluded_from_ensemble": verdict.get("excluded_from_ensemble", []),
        "retrieval_state_vector": {
            "regime_id": regime["regime_id"],
            "markov_state": UNKNOWN,
            "vp_band": band_prob(vp),
            "sp_band": band_sp(row.get("sp")),
            "mds_band": band_prob(mds),
            "improvement_band": band_prob(improvement),
            "release_band": band_prob(release_day),
            "longshot_band": band_prob(longshot),
            "longshot_specialty": longshot_specialty(longshot, row.get("sp")),
            "place_band": band_prob(place),
            "g_adjustment_applied": str(g_applied) if g_applied is not None else UNKNOWN,
            "sidecar_tier": row.get("decision_tier") or verdict.get("tier") or UNKNOWN,
            "course_type": course_type(course),
            "miss_type": miss_type(row, outcome),
        },
        "retrieval_eligible": outcome != UNKNOWN and bool(date),
        "retrieval_blocker": None if outcome != UNKNOWN and date else "OUTCOME_OR_DATE_MISSING",
        "rpr_policy": "RPR_NOT_INCLUDED",
        "forbidden_model_fields_present": [],
        **regime,
    }
    return record


def build_sigma_retrieval_corpus(paths: BuildPaths) -> dict[str, Any]:
    paths = paths.resolved()
    sigma_rows = load_json(paths.sigma_dump, [])
    if not isinstance(sigma_rows, list):
        raise ValueError(f"Expected list in {paths.sigma_dump}")

    sp_by_race = load_sp_enrichment(paths.sp_enrichment_csv) if paths.sp_enrichment_csv else {}
    verdict_by_race = load_verdict_top_by_race(paths.root, paths.verdict_glob)
    observability_by_date = load_observability_by_date(paths.root, paths.observability_glob)

    seen: set[tuple[str, str | None]] = set()
    records: list[dict[str, Any]] = []
    sp_enriched_count = 0
    for row in sigma_rows:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("race_id") or ""), row.get("date"))
        if key in seen:
            continue
        seen.add(key)
        if row.get("sp") is None and sp_by_race:
            sp_val = sp_by_race.get(str(row.get("race_id") or ""))
            if sp_val is not None:
                row = {**row, "sp": sp_val}
                sp_enriched_count += 1
        records.append(standardise_record(row, verdict_by_race, observability_by_date))

    paths.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with paths.output_jsonl.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    report = summarise_records(records)
    report.update(
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "schema_version": SCHEMA_VERSION,
            "input_sigma_dump": str(paths.sigma_dump.relative_to(paths.root)),
            "output_jsonl": str(paths.output_jsonl.relative_to(paths.root)),
            "shadow_only": True,
            "live_velo_impact": False,
            "sp_enrichment_applied": sp_enriched_count,
            "sp_enrichment_source": str(paths.sp_enrichment_csv.relative_to(paths.root)) if paths.sp_enrichment_csv else None,
        }
    )
    paths.report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    paths.report_md.write_text(render_report_md(report), encoding="utf-8")
    return report


def summarise_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_outcome = Counter(r["outcome"] for r in records)
    by_conf = Counter(r["regime_confidence"] for r in records)
    by_blocker = Counter(r["retrieval_blocker"] or "NONE" for r in records)
    by_regime = Counter(r["regime_id"] for r in records)
    date_counts: dict[str, int] = defaultdict(int)
    for r in records:
        if r.get("race_date"):
            date_counts[str(r["race_date"])] += 1

    return {
        "total_records": len(records),
        "retrieval_eligible_records": sum(1 for r in records if r["retrieval_eligible"]),
        "outcome_counts": dict(sorted(by_outcome.items())),
        "regime_confidence_counts": dict(sorted(by_conf.items())),
        "retrieval_blocker_counts": dict(sorted(by_blocker.items())),
        "regime_count": len(by_regime),
        "top_regimes": by_regime.most_common(10),
        "date_min": min(date_counts) if date_counts else None,
        "date_max": max(date_counts) if date_counts else None,
        "date_count": len(date_counts),
        "rpr_violations": 0,
        "forbidden_model_field_violations": 0,
        "classification": "SIGMA_RETRIEVAL_CORPUS_READY_SHADOW_ONLY",
    }


def _date_value(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(str(value) + "T00:00:00+00:00")
        except ValueError:
            return None


def recency_weight(record_date: Any, query_date: Any = None, half_life_days: float = 90.0) -> float:
    if not query_date:
        return 1.0
    rec_dt = _date_value(record_date)
    query_dt = _date_value(query_date)
    if not rec_dt or not query_dt:
        return 1.0
    days = max((query_dt - rec_dt).days, 0)
    return 0.5 ** (days / half_life_days)


def weighted_state_similarity(
    query_vector: dict[str, Any],
    record_vector: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> float:
    return weighted_state_match(query_vector, record_vector, weights)["similarity"]


def weighted_state_match(
    query_vector: dict[str, Any],
    record_vector: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    weights = weights or DEFAULT_KNN_WEIGHTS
    total = 0.0
    matched = 0.0
    possible = sum(weights.values())
    for key, weight in weights.items():
        qv = query_vector.get(key, UNKNOWN)
        rv = record_vector.get(key, UNKNOWN)
        if qv == UNKNOWN or rv == UNKNOWN or qv is None or rv is None:
            continue
        total += weight
        if str(qv) == str(rv):
            matched += weight
    similarity = matched / total if total > 0 else 0.0
    coverage = total / possible if possible > 0 else 0.0
    return {
        "similarity": similarity,
        "coverage": coverage,
        "matched_weight": matched,
        "compared_weight": total,
    }


def retrieve_sigma_neighbors(
    query_vector: dict[str, Any],
    corpus_records: list[dict[str, Any]],
    *,
    query_date: str | None = None,
    k: int = 50,
    min_similarity: float = 0.05,
    min_weight_coverage: float = 0.25,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    neighbors: list[dict[str, Any]] = []
    for record in corpus_records:
        if not record.get("retrieval_eligible"):
            continue
        vector = record.get("retrieval_state_vector") or {}
        match = weighted_state_match(query_vector, vector, weights)
        similarity = match["similarity"]
        if similarity < min_similarity:
            continue
        if match["coverage"] < min_weight_coverage:
            continue
        recency = recency_weight(record.get("race_date"), query_date)
        score = similarity * recency
        neighbors.append(
            {
                "race_id": record.get("race_id"),
                "race_date": record.get("race_date"),
                "course": record.get("course"),
                "horse": record.get("horse"),
                "outcome": record.get("outcome"),
                "miss_type_outcome": record.get("miss_type_outcome"),
                "regime_id": record.get("regime_id"),
                "regime_confidence": record.get("regime_confidence"),
                "similarity": round(similarity, 4),
                "evidence_coverage": round(match["coverage"], 4),
                "matched_weight": round(match["matched_weight"], 4),
                "compared_weight": round(match["compared_weight"], 4),
                "recency_weight": round(recency, 4),
                "weighted_score": round(score, 4),
                "state_vector": vector,
            }
        )
    neighbors.sort(key=lambda row: row["weighted_score"], reverse=True)
    selected = neighbors[:k]
    outcomes = Counter(row["outcome"] for row in selected)
    miss_types = Counter(row["miss_type_outcome"] for row in selected)
    n = len(selected)
    result = {
        "schema_version": "sigma_knn_retrieval_v1",
        "shadow_only": True,
        "live_velo_impact": False,
        "query_vector": query_vector,
        "k_requested": k,
        "neighbors_returned": n,
        "win_rate": round(outcomes.get("WIN", 0) / n, 4) if n else None,
        "frame_rate": round((outcomes.get("WIN", 0) + outcomes.get("FRAME", 0)) / n, 4) if n else None,
        "miss_rate": round(outcomes.get("MISS", 0) / n, 4) if n else None,
        "outcome_counts": dict(sorted(outcomes.items())),
        "miss_type_counts": dict(sorted(miss_types.items())),
        "neighbors": selected,
    }
    result["bayesian_posterior"] = bayesian_posterior_from_knn(result)
    return result


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def bayesian_posterior_from_knn(
    knn_result: dict[str, Any],
    *,
    win_alpha: float = DEFAULT_WIN_PRIOR_ALPHA,
    win_beta: float = DEFAULT_WIN_PRIOR_BETA,
    frame_prior_rate: float = DEFAULT_FRAME_PRIOR_RATE,
    frame_prior_strength: float = DEFAULT_FRAME_PRIOR_STRENGTH,
) -> dict[str, Any]:
    """Convert KNN neighbor evidence into a shadow-only Bayesian posterior."""
    neighbors = knn_result.get("neighbors") or []
    weighted_win = 0.0
    weighted_frame = 0.0
    weighted_n = 0.0
    coverages: list[float] = []
    for neighbor in neighbors:
        coverage = float(neighbor.get("evidence_coverage") or 0.0)
        weighted_n += coverage
        coverages.append(coverage)
        outcome = neighbor.get("outcome")
        if outcome == "WIN":
            weighted_win += coverage
            weighted_frame += coverage
        elif outcome == "FRAME":
            weighted_frame += coverage

    frame_alpha = frame_prior_rate * frame_prior_strength
    frame_beta = (1.0 - frame_prior_rate) * frame_prior_strength
    posterior_win = (weighted_win + win_alpha) / (weighted_n + win_alpha + win_beta) if weighted_n else win_alpha / (win_alpha + win_beta)
    posterior_frame = (
        (weighted_frame + frame_alpha) / (weighted_n + frame_alpha + frame_beta)
        if weighted_n
        else frame_alpha / (frame_alpha + frame_beta)
    )
    median_coverage = _median(coverages)
    n = len(neighbors)
    if n >= 10 and (median_coverage or 0.0) >= 0.4:
        evidence_quality = "HIGH"
    elif n >= 5:
        evidence_quality = "MEDIUM"
    elif n > 0:
        evidence_quality = "LOW"
    else:
        evidence_quality = "NO_EVIDENCE"

    return {
        "schema_version": "sigma_bayesian_posterior_v1",
        "shadow_only": True,
        "live_velo_impact": False,
        "prior_win_prob": round(win_alpha / (win_alpha + win_beta), 4),
        "prior_frame_prob": round(frame_prior_rate, 4),
        "posterior_win_prob": round(posterior_win, 4),
        "posterior_frame_prob": round(posterior_frame, 4),
        "lift_over_prior_win": round(posterior_win - (win_alpha / (win_alpha + win_beta)), 4),
        "lift_over_prior_frame": round(posterior_frame - frame_prior_rate, 4),
        "weighted_wins": round(weighted_win, 4),
        "weighted_frames": round(weighted_frame, 4),
        "weighted_n": round(weighted_n, 4),
        "analogues_n": n,
        "median_evidence_coverage": round(median_coverage, 4) if median_coverage is not None else None,
        "evidence_quality": evidence_quality,
        "classification": "BAYESIAN_POSTERIOR_SHADOW_ONLY",
    }


def _top_matching_dims(
    query_vector: dict[str, Any],
    neighbors: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
    top_n: int = 4,
) -> list[dict[str, Any]]:
    """Return per-dimension match rate info across neighbors, ordered by weighted match rate."""
    weights = weights or DEFAULT_KNN_WEIGHTS
    n = len(neighbors)
    if not n:
        return []
    dim_info = []
    for dim, weight in weights.items():
        qv = query_vector.get(dim)
        if qv is None or str(qv) == UNKNOWN:
            continue
        match_count = sum(
            1 for nb in neighbors
            if str((nb.get("state_vector") or {}).get(dim, UNKNOWN)) == str(qv)
        )
        dim_info.append({
            "dim": dim,
            "query_value": str(qv),
            "match_count": match_count,
            "match_rate": round(match_count / n, 2),
            "weight": weight,
            "weighted_match_rate": round((match_count / n) * weight, 3),
        })
    return sorted(dim_info, key=lambda x: x["weighted_match_rate"], reverse=True)[:top_n]


def _dominant_miss_type(neighbors: list[dict[str, Any]]) -> str | None:
    miss_types = Counter(
        nb.get("miss_type_outcome")
        for nb in neighbors
        if nb.get("outcome") == "MISS" and nb.get("miss_type_outcome") not in (None, UNKNOWN, "NONE")
    )
    if not miss_types:
        return None
    top, count = miss_types.most_common(1)[0]
    total_misses = sum(miss_types.values())
    return f"{top} ({round(count / total_misses * 100):.0f}% of misses)"


def _regime_warning(neighbors: list[dict[str, Any]]) -> str | None:
    if not neighbors:
        return None
    low_regime = sum(1 for nb in neighbors if nb.get("regime_confidence") == "LOW_REGIME_INFERRED")
    if low_regime == len(neighbors):
        return "All analogues LOW_REGIME_INFERRED — doctrine provenance weak, pre-observability era data"
    if low_regime > len(neighbors) * 0.7:
        return f"{low_regime}/{len(neighbors)} analogues LOW_REGIME_INFERRED — treat evidence as indicative"
    return None


def build_evidence_explanation(
    knn_result: dict[str, Any],
    *,
    race_context: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Build a shadow-only explanation report from KNN retrieval result.
    Surfaces which dimensions matched, outcome patterns, miss archetypes,
    and posterior vs prior comparison.

    Does not modify scores, staking, routing, or any live system.
    """
    neighbors = knn_result.get("neighbors") or []
    posterior = knn_result.get("bayesian_posterior") or {}
    query_vector = knn_result.get("query_vector") or {}
    n = len(neighbors)

    post_win = posterior.get("posterior_win_prob")
    post_frame = posterior.get("posterior_frame_prob")
    prior_win = posterior.get("prior_win_prob", 0.2)
    prior_frame = posterior.get("prior_frame_prob", 0.48)
    lift_win = round((post_win - prior_win) * 100, 1) if post_win is not None else None
    lift_frame = round((post_frame - prior_frame) * 100, 1) if post_frame is not None else None
    evidence_quality = posterior.get("evidence_quality", "NO_EVIDENCE")

    top_dims = _top_matching_dims(query_vector, neighbors, weights)
    dominant_miss = _dominant_miss_type(neighbors)
    regime_warn = _regime_warning(neighbors)

    dates = sorted(nb["race_date"] for nb in neighbors if nb.get("race_date"))
    date_range = f"{dates[0]} to {dates[-1]}" if len(dates) >= 2 else (dates[0] if dates else None)

    outcome_counts = knn_result.get("outcome_counts") or {}
    wins = outcome_counts.get("WIN", 0)
    frames = outcome_counts.get("FRAME", 0)
    misses = outcome_counts.get("MISS", 0)

    if post_win is not None and lift_win is not None:
        lift_win_str = f"+{lift_win:.1f}pp" if lift_win >= 0 else f"{lift_win:.1f}pp"
        lift_frame_str = f"+{lift_frame:.1f}pp" if (lift_frame or 0) >= 0 else f"{lift_frame:.1f}pp"
        summary_line = (
            f"{n} analogues: {knn_result.get('win_rate', 0) * 100:.0f}% win, "
            f"{knn_result.get('frame_rate', 0) * 100:.0f}% frame vs "
            f"{prior_win * 100:.0f}% prior — {evidence_quality} evidence quality"
        )
    else:
        summary_line = f"No evidence retrieved — {evidence_quality}"
        lift_win_str = "n/a"
        lift_frame_str = "n/a"

    dim_summary = ", ".join(
        f"{d['dim']}={d['query_value']} ({d['match_count']}/{n})" for d in top_dims
    ) if top_dims else "no matching dimensions"

    narrative_lines = [
        "## Evidence Report — Sigma Bayesian Posterior V1",
        "",
    ]
    if race_context:
        ctx_parts = [str(v) for k, v in race_context.items() if v]
        if ctx_parts:
            narrative_lines += [f"**Query**: {' | '.join(ctx_parts)}", ""]
    narrative_lines += [
        f"**{n} analogues found** ({date_range or 'unknown date range'})",
        "",
        f"**Posterior**: Win {post_win * 100:.1f}% (prior {prior_win * 100:.0f}%, {lift_win_str}) | "
        f"Frame {post_frame * 100:.1f}% (prior {prior_frame * 100:.0f}%, {lift_frame_str})"
        if post_win is not None else "**Posterior**: No evidence",
        f"**Evidence quality**: {evidence_quality}"
        + (f" (n={n}, median coverage={posterior.get('median_evidence_coverage', 'n/a')})" if n else ""),
        "",
        f"**Matched on**: {dim_summary}",
        "",
        f"**Outcome distribution**: {wins} WIN / {frames} FRAME / {misses} MISS",
    ]
    if dominant_miss:
        narrative_lines.append(f"**Dominant miss**: {dominant_miss}")
    if regime_warn:
        narrative_lines += ["", f"**Regime warning**: {regime_warn}"]
    narrative_lines += [
        "",
        "**Boundaries**: Shadow evidence only. Does not modify score, staking, routing, or Telegram.",
    ]

    classification = "EVIDENCE_EXPLANATION_NO_ANALOGUES" if not n else (
        "EVIDENCE_EXPLANATION_LOW_QUALITY" if evidence_quality in ("LOW", "NO_EVIDENCE") else
        "EVIDENCE_EXPLANATION_SHADOW_READY"
    )

    return {
        "schema_version": "sigma_evidence_explanation_v1",
        "shadow_only": True,
        "live_velo_impact": False,
        "classification": classification,
        "summary_line": summary_line,
        "analogues_n": n,
        "evidence_quality": evidence_quality,
        "posterior_win_prob": post_win,
        "posterior_frame_prob": post_frame,
        "prior_win_prob": prior_win,
        "prior_frame_prob": prior_frame,
        "lift_win_pp": lift_win,
        "lift_frame_pp": lift_frame,
        "outcome_distribution": {"WIN": wins, "FRAME": frames, "MISS": misses},
        "dominant_miss_type": dominant_miss,
        "top_matching_dims": top_dims,
        "date_range": date_range,
        "regime_warning": regime_warn,
        "narrative_md": "\n".join(narrative_lines),
        "rpr_policy": "RPR_NOT_INCLUDED",
    }


def _pattern_key(record: dict[str, Any], dims: tuple[str, ...]) -> tuple[tuple[str, str], ...] | None:
    vector = record.get("retrieval_state_vector") or {}
    parts: list[tuple[str, str]] = []
    for dim in dims:
        value = vector.get(dim, UNKNOWN)
        if value in (None, UNKNOWN):
            return None
        parts.append((dim, str(value)))
    return tuple(parts)


def _pattern_label(pattern: tuple[tuple[str, str], ...]) -> str:
    return " | ".join(f"{dim}={value}" for dim, value in pattern)


def _candidate_strength(win_rate: float, frame_rate: float, miss_rate: float, n: int) -> tuple[str, str]:
    if n < 30:
        return "INSUFFICIENT_SUPPORT", "SUPPRESSED_BELOW_N30"
    if win_rate >= 0.34 and frame_rate >= 0.62:
        return "WIN_FRAME_POSITIVE_PATTERN", "DOCTRINE_CANDIDATE_ONLY"
    if frame_rate >= 0.68:
        return "FRAME_POSITIVE_PATTERN", "DOCTRINE_CANDIDATE_ONLY"
    if miss_rate >= 0.68:
        return "MISS_TRAP_PATTERN", "DOCTRINE_CANDIDATE_ONLY"
    return "WATCHLIST_PATTERN", "DOCTRINE_CANDIDATE_ONLY"


def _candidate_stats_signature(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        candidate["support_n"],
        candidate["wins"],
        candidate["frames"],
        candidate["misses"],
        candidate["win_rate"],
        candidate["frame_rate"],
        candidate["miss_rate"],
        candidate["dominant_miss_type"],
        candidate["date_min"],
        candidate["date_max"],
    )


def _dedupe_parsimonious_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Drop statistically identical supersets and keep the simplest pattern."""
    ordered = sorted(
        candidates,
        key=lambda row: (
            _candidate_stats_signature(row),
            len(row["pattern"]),
            row["pattern_label"],
        ),
    )
    kept: list[dict[str, Any]] = []
    removed = 0
    by_signature: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for candidate in ordered:
        signature = _candidate_stats_signature(candidate)
        pattern_items = set(candidate["pattern"].items())
        duplicate_of = None
        for existing in by_signature[signature]:
            if set(existing["pattern"].items()).issubset(pattern_items):
                duplicate_of = existing
                break
        if duplicate_of:
            removed += 1
            continue
        candidate["dedupe_policy"] = "PARSIMONIOUS_PATTERN_KEPT"
        kept.append(candidate)
        by_signature[signature].append(candidate)
    return kept, removed


def mine_doctrine_candidates(
    corpus_records: list[dict[str, Any]],
    *,
    min_support: int = 30,
    max_dims: int = 3,
    dims: tuple[str, ...] = DEFAULT_DOCTRINE_DIMS,
    dedupe_parsimonious: bool = True,
) -> dict[str, Any]:
    """
    Mine recurring Sigma retrieval patterns as human-review candidates only.

    This is a pattern aggregation pass over closed Sigma evidence. It does not
    promote doctrine, change scores, write live tables, or modify runtime state.
    """
    buckets: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = defaultdict(list)
    for record in corpus_records:
        if not record.get("retrieval_eligible"):
            continue
        for size in range(2, max_dims + 1):
            for dim_combo in itertools.combinations(dims, size):
                key = _pattern_key(record, dim_combo)
                if key:
                    buckets[key].append(record)

    candidates: list[dict[str, Any]] = []
    for pattern, records in buckets.items():
        n = len(records)
        if n < min_support:
            continue
        outcomes = Counter(record.get("outcome") for record in records)
        wins = outcomes.get("WIN", 0)
        frames = wins + outcomes.get("FRAME", 0)
        misses = outcomes.get("MISS", 0)
        win_rate = wins / n if n else 0.0
        frame_rate = frames / n if n else 0.0
        miss_rate = misses / n if n else 0.0
        miss_types = Counter(
            record.get("miss_type_outcome")
            for record in records
            if record.get("outcome") == "MISS" and record.get("miss_type_outcome") not in (None, UNKNOWN, "NONE")
        )
        regime_conf = Counter(record.get("regime_confidence", UNKNOWN) for record in records)
        pattern_type, classification = _candidate_strength(win_rate, frame_rate, miss_rate, n)
        candidates.append(
            {
                "schema_version": "sigma_doctrine_candidate_v1",
                "candidate_only": True,
                "shadow_only": True,
                "live_velo_impact": False,
                "shadow_velo_impact": False,
                "new_build_velo_impact": False,
                "rpr_policy": "RPR_NOT_INCLUDED",
                "promotion_status": "NOT_PROMOTED",
                "classification": classification,
                "pattern_type": pattern_type,
                "pattern": dict(pattern),
                "pattern_label": _pattern_label(pattern),
                "support_n": n,
                "wins": wins,
                "frames": frames,
                "misses": misses,
                "win_rate": round(win_rate, 4),
                "frame_rate": round(frame_rate, 4),
                "miss_rate": round(miss_rate, 4),
                "lift_over_prior_win": round(win_rate - (DEFAULT_WIN_PRIOR_ALPHA / (DEFAULT_WIN_PRIOR_ALPHA + DEFAULT_WIN_PRIOR_BETA)), 4),
                "lift_over_prior_frame": round(frame_rate - DEFAULT_FRAME_PRIOR_RATE, 4),
                "dominant_miss_type": miss_types.most_common(1)[0][0] if miss_types else None,
                "dominant_miss_type_share": round(miss_types.most_common(1)[0][1] / misses, 4) if miss_types and misses else None,
                "regime_confidence_counts": dict(sorted(regime_conf.items())),
                "date_min": min(str(record.get("race_date")) for record in records if record.get("race_date")),
                "date_max": max(str(record.get("race_date")) for record in records if record.get("race_date")),
                "review_gate": "HUMAN_REVIEW_REQUIRED_N30_FORWARD_VALIDATION_REQUIRED",
            }
        )

    deduped_count = 0
    if dedupe_parsimonious:
        candidates, deduped_count = _dedupe_parsimonious_candidates(candidates)

    candidates.sort(
        key=lambda row: (
            row["classification"] != "DOCTRINE_CANDIDATE_ONLY",
            -row["lift_over_prior_win"],
            -row["lift_over_prior_frame"],
            -row["support_n"],
        )
    )
    return {
        "schema_version": "sigma_doctrine_miner_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_only": True,
        "shadow_only": True,
        "live_velo_impact": False,
        "shadow_velo_impact": False,
        "new_build_velo_impact": False,
        "rpr_policy": "RPR_NOT_INCLUDED",
        "min_support": min_support,
        "max_dims": max_dims,
        "dedupe_policy": "PARSIMONIOUS_IDENTICAL_STATS" if dedupe_parsimonious else "NONE",
        "deduped_candidate_count": deduped_count,
        "dimensions_considered": list(dims),
        "corpus_records": len(corpus_records),
        "eligible_records": sum(1 for record in corpus_records if record.get("retrieval_eligible")),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "classification": "DOCTRINE_MINER_CANDIDATES_READY_SHADOW_ONLY",
    }


def render_doctrine_miner_md(report: dict[str, Any], *, top_n: int = 20) -> str:
    lines = [
        "# Sigma Doctrine Miner V1",
        "",
        f"Generated: {report['generated_at']}",
        f"Classification: {report['classification']}",
        f"Candidate only: {report['candidate_only']}",
        f"Live VÉLØ impact: {report['live_velo_impact']}",
        f"RPR policy: {report['rpr_policy']}",
        "",
        f"Corpus records: {report['corpus_records']}",
        f"Eligible records: {report['eligible_records']}",
        f"Min support: {report['min_support']}",
        f"Candidates: {report['candidate_count']}",
        f"Dedupe policy: {report['dedupe_policy']}",
        f"Deduped candidate shells: {report['deduped_candidate_count']}",
        "",
        "## Top Candidates",
        "",
    ]
    for idx, candidate in enumerate(report["candidates"][:top_n], start=1):
        lines.extend(
            [
                f"### {idx}. {candidate['pattern_type']}",
                "",
                f"- Pattern: `{candidate['pattern_label']}`",
                f"- Support: {candidate['support_n']}",
                f"- Win rate: {candidate['win_rate']:.1%} ({candidate['wins']} wins)",
                f"- Frame rate: {candidate['frame_rate']:.1%} ({candidate['frames']} frames)",
                f"- Miss rate: {candidate['miss_rate']:.1%} ({candidate['misses']} misses)",
                f"- Lift over prior win: {candidate['lift_over_prior_win']:+.1%}",
                f"- Lift over prior frame: {candidate['lift_over_prior_frame']:+.1%}",
                f"- Dominant miss: {candidate['dominant_miss_type'] or 'NONE'}",
                f"- Status: {candidate['promotion_status']} / {candidate['classification']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundaries",
            "",
            "- Shadow/operator evidence only.",
            "- No scoring, staking, routing, Telegram, or live table writes.",
            "- Doctrine candidates require human review and forward validation before any promotion.",
            "- RPR is not included.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# Sigma Retrieval Corpus V1",
        "",
        "Shadow-only standardised memory for future KNN/Bayesian evidence retrieval.",
        "",
        "## Summary",
        "",
        f"- Total records: {report['total_records']}",
        f"- Retrieval eligible records: {report['retrieval_eligible_records']}",
        f"- Date range: {report['date_min']} to {report['date_max']}",
        f"- Regime count: {report['regime_count']}",
        f"- RPR violations: {report['rpr_violations']}",
        f"- Live VÉLØ impact: {report['live_velo_impact']}",
        "",
        "## Outcome Counts",
        "",
    ]
    for key, value in report["outcome_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Regime Confidence", ""])
    for key, value in report["regime_confidence_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Retrieval Blockers", ""])
    for key, value in report["retrieval_blocker_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Regimes", ""])
    for regime_id, count in report["top_regimes"]:
        lines.append(f"- {regime_id}: {count}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- This corpus is shadow-only evidence.",
            "- It does not write live scoring tables.",
            "- It does not change model weights, formula, router, staking, Telegram, or Playbook G.",
            "- RPR is not included in the retrieval vector.",
            "- Rows without clear date/outcome remain blocked from retrieval.",
            "",
            f"Classification: `{report['classification']}`",
            "",
        ]
    )
    return "\n".join(lines)
