#!/usr/bin/env python3
"""Run Radical Velo shadow decision packet for a race day."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.radical.decision_packet import build_packet, render_markdown
from src.velo.radical.passport_feed import load_passport_feed, normalize_name, passport_snapshot
from src.velo.radical.regime_router import route_regime, safe_float
from src.velo.radical.sigma_gate import SigmaGate, build_sigma_feature_row
from src.velo.midprice_hunter import evaluate_race as evaluate_midprice_race

DATA = ROOT / "data"
REPORT_DIR = DATA / "reports"
MODEL_DIR = ROOT / "models" / "radical_sigma_gate_staging"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Radical Velo shadow packet.")
    parser.add_argument("--date", required=True, help="Race date in YYYY-MM-DD format.")
    parser.add_argument("--source", default=None, help="Optional explicit velo_prime_verdicts JSON path.")
    return parser.parse_args()


def _date_slug(date: str) -> str:
    return date.replace("-", "_")


def _load_verdicts(date: str, source: str | None) -> tuple[list[dict[str, Any]], Path]:
    path = Path(source) if source else DATA / f"velo_prime_verdicts_{_date_slug(date)}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing verdict source: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("verdicts") or rows.get("races") or []
    if not isinstance(rows, list):
        raise ValueError(f"Verdict source is not a list: {path}")
    return rows, path


def _parse_class_num(race_name: str | None) -> int:
    if not race_name:
        return 0
    match = re.search(r"\bClass\s+([1-7])\b", race_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    lowered = race_name.lower()
    if "group 1" in lowered or "grade 1" in lowered:
        return 1
    if "group 2" in lowered or "grade 2" in lowered:
        return 2
    if "group 3" in lowered or "grade 3" in lowered or "listed" in lowered:
        return 3
    return 0


def _packet_row(
    verdict: dict[str, Any],
    *,
    win_gate: SigmaGate,
    frame_gate: SigmaGate,
    passport_rows: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    top = verdict.get("top") or {}
    passport_row = passport_rows.get((str(verdict.get("race_id") or ""), normalize_name(top.get("horse"))))
    passport = passport_snapshot(passport_row)
    class_num = _parse_class_num(verdict.get("race_name"))
    if not class_num:
        class_num = int(safe_float(passport.get("race_class"), 0))
    features = build_sigma_feature_row(verdict, class_num)
    if not features["sp_decimal"]:
        features["sp_decimal"] = safe_float(passport.get("forecast_odds"), 0.0)
        features["implied_probability"] = (1.0 / features["sp_decimal"]) if features["sp_decimal"] > 0 else 0.0
        features["edge"] = features["model_probability"] - features["implied_probability"]
    win_prob = win_gate.predict(features)
    frame_prob = frame_gate.predict(features)
    midprice_action = top.get("midprice_shadow_action")
    midprice_evidence = top.get("midprice_shadow_evidence")
    midprice_field_band = top.get("midprice_shadow_field_band")
    midprice_rule_version = top.get("midprice_shadow_rule_version")
    if not midprice_action:
        midprice = evaluate_midprice_race(
            race_id=str(verdict.get("race_id") or ""),
            race_date=str(verdict.get("date") or ""),
            course=str(verdict.get("course") or ""),
            off_time=str(verdict.get("off_time") or ""),
            tier=str(verdict.get("tier") or ""),
            top_pick=str(top.get("horse") or ""),
            top_vp=safe_float(top.get("velo_prime_prob"), 0.0),
            top_mds=safe_float(top.get("market_deception_score"), 0.0),
            top_improvement=safe_float(top.get("improvement_score"), 0.0),
            top_place_prob=safe_float(top.get("place_prob"), 0.0),
            field_size=int(safe_float(verdict.get("scored"), 0)),
            class_num=class_num,
            sp_dec=features["sp_decimal"],
        )
        midprice_action = midprice.get("shadow_action")
        midprice_evidence = midprice.get("evidence")
        midprice_field_band = midprice.get("field_band")
        midprice_rule_version = midprice.get("rule_version")
    radical = route_regime(
        sp_decimal=features["sp_decimal"],
        model_probability=features["model_probability"],
        field_size=features["field_size"],
        class_num=class_num,
        win_gate_probability=win_prob,
        frame_gate_probability=frame_prob,
        passport_available=bool(passport.get("passport_available")),
        passport_strength_score=passport.get("passport_strength_score"),
        midprice_shadow_action=midprice_action,
        midprice_shadow_evidence=midprice_evidence,
    )
    return {
        "race_id": verdict.get("race_id"),
        "course": verdict.get("course"),
        "off_time": verdict.get("off_time"),
        "race_name": verdict.get("race_name"),
        "horse": top.get("horse"),
        "tier": verdict.get("tier"),
        "field_size": int(safe_float(verdict.get("scored"), 0)),
        "class_num": class_num,
        "sp_decimal": features["sp_decimal"],
        "velo_prime_prob": features["model_probability"],
        "old_velo_top": {
            "horse": top.get("horse"),
            "velo_prime_prob": top.get("velo_prime_prob"),
            "sqpe_v17_prob": top.get("sqpe_v17_prob"),
            "sqpe_no_rpr_shadow_prob": top.get("sqpe_no_rpr_shadow_prob"),
            "market_deception_score": top.get("market_deception_score"),
            "place_prob": top.get("place_prob"),
            "cash_run_flag": top.get("cash_run_flag"),
            "setup_run_flag": top.get("setup_run_flag"),
            "midprice_shadow_action": midprice_action,
            "midprice_shadow_evidence": midprice_evidence,
            "midprice_shadow_field_band": midprice_field_band,
            "midprice_shadow_rule_version": midprice_rule_version,
            "execution_allowed": top.get("execution_allowed"),
            "candidate_execution_lane": top.get("candidate_execution_lane"),
        },
        "passport": passport,
        "sigma_features": features,
        "win_gate_probability": round(win_prob, 4) if win_prob is not None else None,
        "frame_gate_probability": round(frame_prob, 4) if frame_prob is not None else None,
        "radical": radical,
    }


def main() -> int:
    args = parse_args()
    obstacles: list[str] = []
    verdicts, source_path = _load_verdicts(args.date, args.source)

    passport_rows, passport_status = load_passport_feed(DATA, args.date)
    if not passport_status.get("loaded"):
        obstacles.append(f"PASSPORT_FEED_NOT_LOADED:{passport_status.get('error')}")
    elif passport_status.get("selected_kind") != "dated":
        obstacles.append("PASSPORT_DATED_FEED_MISSING: using latest feed only")

    win_gate = SigmaGate(MODEL_DIR / "sigma_win_gate.pkl")
    frame_gate = SigmaGate(MODEL_DIR / "sigma_frame_gate.pkl")
    if not win_gate.loaded:
        obstacles.append(f"WIN_GATE_NOT_LOADED:{win_gate.error or win_gate.model_path}")
    if not frame_gate.loaded:
        obstacles.append(f"FRAME_GATE_NOT_LOADED:{frame_gate.error or frame_gate.model_path}")

    decisions = [
        _packet_row(
            verdict,
            win_gate=win_gate,
            frame_gate=frame_gate,
            passport_rows=passport_rows,
        )
        for verdict in verdicts
    ]
    passport_matches = sum(1 for row in decisions if row.get("passport", {}).get("matched"))
    passport_available = sum(1 for row in decisions if row.get("passport", {}).get("passport_available"))
    action_order = {
        "WIN_CANDIDATE_SHADOW": 0,
        "CASH_RUN": 1,
        "WATCHLIST_SHADOW": 2,
        "PASS_OR_WATCH": 3,
        "NO_BET_SHADOW": 4,
        "PASS": 5,
    }
    decisions.sort(
        key=lambda row: (
            action_order.get(row["radical"]["action"], 99),
            -(row.get("win_gate_probability") or 0),
            -(row.get("frame_gate_probability") or 0),
        )
    )

    packet = build_packet(
        date=args.date,
        source_path=str(source_path),
        decisions=decisions,
        obstacles=obstacles,
        gate_status={
            "win_gate_loaded": win_gate.loaded,
            "win_gate_error": win_gate.error,
            "frame_gate_loaded": frame_gate.loaded,
            "frame_gate_error": frame_gate.error,
            "shadow_only": True,
            "passport_feed": passport_status,
            "passport_matches": passport_matches,
            "passport_available_on_top_picks": passport_available,
        },
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _date_slug(args.date)
    json_path = REPORT_DIR / f"radical_shadow_{slug}.json"
    md_path = REPORT_DIR / f"radical_shadow_{slug}.md"
    latest_json = REPORT_DIR / "radical_shadow_latest.json"
    latest_md = REPORT_DIR / "radical_shadow_latest.md"
    json_blob = json.dumps(packet, indent=2, ensure_ascii=False)
    markdown = render_markdown(packet)
    json_path.write_text(json_blob + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    latest_json.write_text(json_blob + "\n", encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")

    print(f"RADICAL_SHADOW_COMPLETE date={args.date} races={len(decisions)}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    if obstacles:
        print("obstacles=" + "; ".join(obstacles))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
