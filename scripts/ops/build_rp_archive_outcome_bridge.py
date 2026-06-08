#!/usr/bin/env python3
"""Bridge RP archive horses to Velo predictions and outcome truth where available."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"
BRIDGE_PATH = PARSED_ROOT / "horse_identity_bridge.json"
OUT_PATH = PARSED_ROOT / "rp_archive_outcome_bridge.json"
POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
RPR_POLICY = "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _dossier_index() -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for day in sorted(p for p in PARSED_ROOT.glob("20*-*-*") if p.is_dir()):
        payload = _load(day / "horse_dossiers.json", {})
        for row in payload.get("dossiers") or []:
            out[(day.name, _norm(row.get("horse")))] = row
    return out


def _race_dossier_index() -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for day in sorted(p for p in PARSED_ROOT.glob("20*-*-*") if p.is_dir()):
        payload = _load(day / "race_dossiers.json", {})
        for race in payload.get("dossiers") or []:
            out[(day.name, str(race.get("course") or ""), str(race.get("race_time") or ""))] = race
    return out


def _runner_snapshots() -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for path in ROOT.glob("data/runner_snapshots_*.jsonl"):
        for row in _iter_jsonl(path):
            if row.get("race_date") and row.get("horse"):
                out[(row["race_date"], _norm(row["horse"]))].append(row)
    return out


def _velo_top_index() -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for path in ROOT.glob("data/velo_prime_verdicts_20*.json"):
        date = path.stem.replace("velo_prime_verdicts_", "").replace("_", "-")
        payload = _load(path, [])
        if not isinstance(payload, list):
            continue
        for race in payload:
            top = race.get("top") or {}
            if top.get("horse"):
                row = dict(top)
                row["race_date"] = date
                row["race_id"] = race.get("race_id") or top.get("race_id")
                row["course"] = race.get("course")
                row["off_time"] = race.get("off_time")
                row["tier"] = race.get("tier") or top.get("tier")
                out[(date, _norm(top["horse"]))] = row
    return out


def _sigma_index() -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for path in ROOT.glob("data/sigma_results/sigma_results_20*.json"):
        payload = _load(path, {})
        date = payload.get("date") or path.stem.replace("sigma_results_", "").replace("_", "-")
        rows = payload.get("learning_candidate_rows") or payload.get("raw_sigma_audits_preserved") or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            horse = row.get("horse") or row.get("selection") or row.get("top_horse")
            if horse:
                out[(date, _norm(horse))] = row
    return out


def _bool_win(row: dict[str, Any] | None) -> bool | None:
    if not row:
        return None
    value = str(row.get("result") or row.get("outcome") or row.get("finish_position") or "").lower()
    if value in {"win", "winner", "1", "1st", "won"} or row.get("won") is True:
        return True
    if value:
        return False
    return None


def _bool_frame(row: dict[str, Any] | None) -> bool | None:
    if not row:
        return None
    if _bool_win(row) is True:
        return True
    value = str(row.get("result") or row.get("outcome") or row.get("finish_position") or "").lower()
    if value in {"frame", "placed", "place", "2", "2nd", "3", "3rd"} or row.get("framed") is True:
        return True
    if value:
        return False
    return None


def _classify(identity: dict[str, Any], prediction: dict[str, Any] | None, outcome: dict[str, Any] | None) -> str:
    if identity.get("classification") == "MULTI_MATCH_AMBIGUOUS":
        return "IDENTITY_AMBIGUOUS"
    if outcome and prediction:
        return "OUTCOME_CONFIRMED"
    if prediction and not outcome:
        return "PREDICTION_ONLY_NO_RESULT"
    if outcome and not prediction:
        return "RESULT_ONLY_NO_PREDICTION"
    if identity.get("classification") == "RP_ONLY":
        return "RP_ONLY_NO_VELO"
    return "OUTCOME_MISSING"


def build(execute: bool) -> dict[str, Any]:
    identity_payload = _load(BRIDGE_PATH, {})
    identities = identity_payload.get("bridge") or []
    dossiers = _dossier_index()
    race_dossiers = _race_dossier_index()
    snapshots = _runner_snapshots()
    velo_tops = _velo_top_index()
    sigma = _sigma_index()
    rows: list[dict[str, Any]] = []

    for identity in identities:
        date = identity.get("source_date")
        key = identity.get("normalized_name")
        dossier = dossiers.get((date, key), {})
        snap_candidates = snapshots.get((date, key), [])
        snapshot = snap_candidates[0] if len(snap_candidates) == 1 else None
        top = velo_tops.get((date, key))
        outcome = sigma.get((date, key))
        race_id = (snapshot or top or {}).get("race_id")
        course = dossier.get("course") or (snapshot or top or {}).get("course")
        off_time = dossier.get("race_time") or (snapshot or top or {}).get("off_time")
        race_ctx = race_dossiers.get((date, str(course or ""), str(off_time or "")), {})
        prediction = snapshot or top
        classification = _classify(identity, prediction, outcome)
        outcome_confidence = 0.95 if outcome else 0.0
        blocker = None
        if classification == "PREDICTION_ONLY_NO_RESULT":
            blocker = "RESULT_OR_SIGMA_MISSING"
        elif classification == "RP_ONLY_NO_VELO":
            blocker = "NO_VELO_PREDICTION_OR_RUNNER_SNAPSHOT"
        elif classification == "IDENTITY_AMBIGUOUS":
            blocker = identity.get("blocker_reason") or "IDENTITY_AMBIGUOUS"
        elif classification == "OUTCOME_MISSING":
            blocker = "OUTCOME_MISSING"
        rows.append({
            "rp_horse_id": identity.get("rp_horse_id"),
            "rp_horse_name": identity.get("rp_horse_name"),
            "normalized_name": key,
            "race_date": date,
            "race_id": race_id,
            "course": course,
            "off_time": off_time,
            "velo_horse_id": identity.get("velo_horse_id") or (prediction or {}).get("horse_id"),
            "rpdc_horse_id": identity.get("rpdc_horse_id"),
            "sigma_outcome": (outcome or {}).get("result") or (outcome or {}).get("outcome"),
            "finishing_position": (outcome or {}).get("finish_position") or (outcome or {}).get("position"),
            "won": _bool_win(outcome),
            "framed": _bool_frame(outcome),
            "sp": (outcome or {}).get("sp") or (outcome or {}).get("sp_dec") or (prediction or {}).get("sp_dec"),
            "velo_top_pick": bool(prediction and prediction.get("top_pick_name") == prediction.get("horse")),
            "velo_rank": (prediction or {}).get("rank"),
            "velo_tier": (prediction or {}).get("decision_tier") or (prediction or {}).get("tier"),
            "velo_probability": (prediction or {}).get("velo_prime_prob"),
            "archive_context_flags": dossier.get("archive_flags") or race_ctx.get("archive_intelligence_flags") or [],
            "identity_confidence": identity.get("identity_confidence", 0.0),
            "identity_classification": identity.get("classification"),
            "outcome_confidence": outcome_confidence,
            "classification": classification,
            "blocker_reason": blocker,
            "trust_policy": POLICY,
            "velo_scoring_allowed": False,
            "rpr_policy": RPR_POLICY,
        })

    counts = Counter(row["classification"] for row in rows)
    payload = {
        "generated_at": _utc_now(),
        "horse_race_count": len(rows),
        "classification_counts": dict(counts),
        "outcome_confirmed_count": counts.get("OUTCOME_CONFIRMED", 0),
        "prediction_only_count": counts.get("PREDICTION_ONLY_NO_RESULT", 0),
        "rp_only_count": counts.get("RP_ONLY_NO_VELO", 0),
        "ambiguous_count": counts.get("IDENTITY_AMBIGUOUS", 0),
        "scoring_impact": "NONE",
        "rows": rows,
    }
    if execute:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        json_path = REPORT_ROOT / "rp_archive_outcome_bridge_latest.json"
        md_path = REPORT_ROOT / "rp_archive_outcome_bridge_latest.md"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [
            "# RP Archive Outcome Bridge",
            "",
            f"- Horse/race rows: `{len(rows)}`",
            f"- Outcome confirmed: `{payload['outcome_confirmed_count']}`",
            f"- Prediction only/no result: `{payload['prediction_only_count']}`",
            f"- RP only/no VÉLØ: `{payload['rp_only_count']}`",
            f"- Ambiguous: `{payload['ambiguous_count']}`",
            "- Scoring impact: `NONE`",
            "",
            "## Classification Counts",
        ]
        for name, count in counts.most_common():
            lines.append(f"- {name}: `{count}`")
        lines += ["", "## Blocked Rows Sample"]
        for row in rows:
            if row.get("blocker_reason"):
                lines.append(f"- **{row['rp_horse_name']}** ({row['race_date']}): {row['classification']} - {row['blocker_reason']}")
                if len(lines) > 90:
                    break
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _write_bow_echo_profile(rows)
        payload["status"] = "PASS"
        payload["output_path"] = str(OUT_PATH)
        payload["json_path"] = str(json_path)
        payload["md_path"] = str(md_path)
    else:
        payload["status"] = "DRY_RUN"
    return payload


def _write_bow_echo_profile(rows: list[dict[str, Any]]) -> None:
    bow = next((row for row in rows if row.get("normalized_name") == "bowecho"), None)
    path = REPORT_ROOT / "bow_echo_source_profile.md"
    if not bow:
        return
    lines = [
        "# Bow Echo Source Profile",
        "",
        "- Scoring impact: `NONE`",
        "- RPR policy: `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`",
        "",
        "- Horse: **Bow Echo**",
        f"- RP horse id: `{bow.get('rp_horse_id')}`",
        f"- Identity status: `{bow.get('identity_classification')}`",
        f"- Outcome status: `{bow.get('classification')}`",
        f"- Blocker: `{bow.get('blocker_reason')}`",
        "",
        "## Current Read",
        "",
        "Bow Echo remains `RP_ONLY` / `NO_LOCAL_OUTCOME_MATCH`. We have Racing Post profile context, but no local VÉLØ runner snapshot, Racing API/local identity, Sigma result, or horse_runs outcome linked yet.",
        "",
        "## Required To Make Bow Echo Measurable",
        "",
        "- VÉLØ runner snapshot",
        "- Racing API/local identity",
        "- result/Sigma outcome",
        "- horse_runs record",
        "",
        "## Keep Out Of Scoring",
        "",
        "- RPR, RP comments, tip count, and RP opinion fields remain archive/context only.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RP archive outcome bridge.")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
