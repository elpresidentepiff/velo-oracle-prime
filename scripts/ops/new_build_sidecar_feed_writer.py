"""
new_build_sidecar_feed_writer.py
Write read-only New Build sidecar feed artifact for a target date.

Output: data/new_build/sidecar_feed/new_build_signal_YYYY_MM_DD.jsonl
        data/new_build/sidecar_feed/new_build_signal_latest.jsonl

Each row is a horse-level signal record. This file is read-only intelligence —
it does NOT alter Old VELO scoring, triggers no Telegram, no staking.

Usage:
  python scripts/ops/new_build_sidecar_feed_writer.py --date 2026-05-29 [--execute]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRED_DIR = ROOT / "data" / "new_build" / "paper_predictions"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"
SIDECAR_DIR = ROOT / "data" / "new_build" / "sidecar_feed"

INTENT_GATE = 80.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _load_predictions(date_str: str) -> list[dict]:
    tag = date_str.replace("-", "_")
    specific = PRED_DIR / f"new_build_predictions_{tag}.jsonl"
    rows = _read_jsonl(specific)
    if not rows:
        latest = PRED_DIR / "new_build_predictions_latest.jsonl"
        rows = [r for r in _read_jsonl(latest) if str(r.get("race_date", ""))[:10] == date_str]
    return rows


def _load_readiness(date_str: str) -> dict:
    tag = date_str.replace("-", "_")
    path = REPORT_DIR / f"two_lane_readiness_{tag}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_sidecar(date_str: str, execute: bool = False) -> dict:
    preds = _load_predictions(date_str)
    readiness = _load_readiness(date_str)

    if not preds:
        return {
            "status": "NO_DATA",
            "target_date": date_str,
            "records": [],
            "meta": {"error": f"No predictions found for {date_str}"},
        }

    # Determine intent coverage from readiness report
    intent_pct = readiness.get("intent_pct", 0.0)
    intent_gate_passed = intent_pct >= INTENT_GATE
    operational_lane = readiness.get("operational_lane", "LANE_A_CORE_PASSPORT")
    model_lane = "LANE_B_CHALLENGER_V1" if intent_gate_passed else "LANE_A_CORE_PASSPORT"

    # Passport coverage by race
    race_passport: dict[str, dict] = {}
    for r in preds:
        rid = str(r.get("race_id") or "")
        if not rid:
            continue
        if rid not in race_passport:
            race_passport[rid] = {"total": 0, "found": 0}
        race_passport[rid]["total"] += 1
        if r.get("passport_found"):
            race_passport[rid]["found"] += 1

    records: list[dict] = []
    for row in preds:
        rid = str(row.get("race_id") or "")
        rp_data = race_passport.get(rid, {"total": 1, "found": 0})
        pp_pct = rp_data["found"] / rp_data["total"] if rp_data["total"] > 0 else 0.0
        weak_data = pp_pct < 0.5

        # RPR violation: any feature key containing 'rpr' that is not an allowed policy key
        allowed_rpr = {"rpr_policy", "rp_rpr_velo_allowed", "rpr_feature_allowed"}
        rpr_violation = any(
            "rpr" in k.lower() and k not in allowed_rpr and bool(v)
            for k, v in row.items()
        )

        pp_sum = row.get("passport_summary") or {}

        records.append({
            "generated_at": _utc_now(),
            "target_date": date_str,
            "race_id": rid,
            "rp_uid": str(row.get("rp_uid") or ""),
            "horse": row.get("horse") or "",
            "course": row.get("course") or "",
            "off_time": row.get("off_time") or "",
            "champion_rank": int(row.get("champion_rank") or 99),
            "champion_probability": float(row.get("champion_probability") or 0.0),
            "passport_found": bool(row.get("passport_found")),
            "passport_strength_score": row.get("passport_strength_score"),
            "pp_best_ts_last6": pp_sum.get("pp_best_ts_last6"),
            "pp_ts_trajectory": pp_sum.get("pp_ts_trajectory"),
            "passport_coverage_flag": "STRONG" if pp_pct >= 0.80 else ("WEAK" if pp_pct < 0.50 else "MODERATE"),
            "intent_coverage_flag": "GATE_PASSED" if intent_gate_passed else "BELOW_GATE_MEDIAN_FILLED",
            "intent_score": row.get("intent_score"),
            "intent_features_available": bool(row.get("intent_features_available")),
            "weak_data_flag": weak_data,
            "rpr_violation_flag": rpr_violation,
            "model_lane_used": model_lane,
            "reason_codes": row.get("reason_codes") or [],
            "paper_only": True,
            "velo_scoring_allowed": False,
            "live_velo_impact": False,
            "shadow_velo_impact": False,
            "new_build_signal_type": "NEW_BUILD_PAPER_SIGNAL",
            "old_velo_untouched": True,
        })

    # Sort by race time then rank
    records.sort(key=lambda r: (r.get("off_time") or "", r.get("race_id") or "", r.get("champion_rank") or 99))

    meta = {
        "generated_at": _utc_now(),
        "target_date": date_str,
        "total_records": len(records),
        "total_races": len(race_passport),
        "intent_coverage_pct": intent_pct,
        "intent_gate_passed": intent_gate_passed,
        "model_lane": model_lane,
        "operational_lane": operational_lane,
        "rpr_violations": sum(1 for r in records if r["rpr_violation_flag"]),
        "weak_data_races": sum(1 for r in records if r["weak_data_flag"]),
        "passport_found_pct": round(sum(1 for r in records if r["passport_found"]) / len(records), 4) if records else 0.0,
        "signal_type": "NEW_BUILD_PAPER_SIGNAL",
        "old_velo_untouched": True,
        "shadow_untouched": True,
        "telegram_sent": False,
        "staking": False,
        "auc_status": "OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY",
    }

    result = {"status": "SIDECAR_READY", "meta": meta, "records": records}

    if execute:
        SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
        tag = date_str.replace("-", "_")
        out_path = SIDECAR_DIR / f"new_build_signal_{tag}.jsonl"
        latest_path = SIDECAR_DIR / "new_build_signal_latest.jsonl"
        lines = [json.dumps(r, ensure_ascii=False) for r in records]
        content = "\n".join(lines)
        out_path.write_text(content, encoding="utf-8")
        latest_path.write_text(content, encoding="utf-8")
        # Also write a meta header file
        meta_path = SIDECAR_DIR / f"new_build_signal_{tag}_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Written: {out_path} ({len(records)} records)")
        print(f"Written: {latest_path}")
        print(f"Written: {meta_path}")

    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    result = build_sidecar(args.date, execute=args.execute)
    meta = result.get("meta", {})
    print(f"Status: {result['status']}")
    print(f"Records: {meta.get('total_records', 0)} runners / {meta.get('total_races', 0)} races")
    print(f"Lane: {meta.get('model_lane', 'UNKNOWN')}")
    print(f"RPR violations: {meta.get('rpr_violations', 0)}")
    print(f"AUC status: {meta.get('auc_status', 'UNKNOWN')}")


if __name__ == "__main__":
    main()
