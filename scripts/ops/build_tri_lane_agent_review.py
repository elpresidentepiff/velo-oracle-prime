"""
Build an agent-facing review board from Tri-Lane VÉLØ stress packets.

This is not an LLM caller. It creates the structured brief an agent should use
to inspect each race after prediction: BHA/OR, Spotlight, RPDC/RPD, passport,
MDS, cash-run and final tri-lane context.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return bool(value) and str(value).lower() not in {"false", "0", "none", "null"}


def _risk_and_support(row: dict) -> tuple[list[str], list[str], list[str]]:
    old = row.get("old_velo") or {}
    new = row.get("new_build") or {}
    shadow = row.get("shadow") or {}
    tri = row.get("tri_lane") or {}
    support: list[str] = []
    risk: list[str] = []
    questions: list[str] = []

    tier = old.get("tier")
    vp = _float(old.get("velo_prime_prob"))
    mds = _float(old.get("mds"))
    place = _float(old.get("place_prob"))
    spotlight = _float(old.get("spotlight_score"))
    rpdc_release = _float(old.get("rpdc_release_score"))
    passport_strength = _float(shadow.get("passport_strength_score"), -1.0)
    frame_gate = _float(shadow.get("frame_gate_probability"))
    win_gate = _float(shadow.get("win_gate_probability"))

    if tier == "A":
        support.append("OLD_TIER_A")
    if vp >= 0.45:
        support.append(f"VP_HIGH:{vp:.3f}")
    if mds >= 0.30:
        support.append(f"MDS_GOLD:{mds:.3f}")
    elif mds <= 0.05:
        risk.append(f"MDS_FLAT:{mds:.3f}")
    if place >= 0.62:
        support.append(f"PLACE_FRAME:{place:.3f}")
    if spotlight >= 0.65:
        support.append(f"SPOTLIGHT_POSITIVE:{spotlight:.2f}")
    elif spotlight and spotlight < 0.35:
        risk.append(f"SPOTLIGHT_WEAK:{spotlight:.2f}")
    if old.get("rpdc_cash_window_flag"):
        support.append("RPDC_CASH_WINDOW")
    if rpdc_release >= 0.70:
        support.append(f"RPDC_RELEASE:{rpdc_release:.2f}")
    if old.get("rpd_tag") and old.get("rpd_tag") != "S":
        support.append(f"RPD_TAG:{old.get('rpd_tag')}")
    if old.get("bha_or_diff_flag"):
        flag = old.get("bha_or_diff_flag")
        mag = old.get("bha_or_diff_magnitude")
        support.append(f"BHA_OR_DIFF:{flag}:{mag}")
    if passport_strength >= 1.0:
        support.append(f"PASSPORT_SUPPORT:{passport_strength:.2f}")
    if frame_gate >= 0.62:
        support.append(f"FRAME_GATE:{frame_gate:.3f}")
    if win_gate >= 0.58:
        support.append(f"WIN_GATE:{win_gate:.3f}")
    if old.get("candidate_execution_lane") and old.get("candidate_execution_lane") != "NO_BET":
        support.append(f"OLD_CANDIDATE_LANE:{old.get('candidate_execution_lane')}")

    if new.get("weak_data"):
        risk.append("NEW_BUILD_WEAK_DATA")
    if old.get("midprice_shadow_action") in {"MIDPRICE_NO_EDGE", "MIDPRICE_SUPPRESS_TOP"}:
        risk.append(old.get("midprice_shadow_action"))
    if shadow.get("field_band") in {"FS_9_12", "FS_13_PLUS"} and old.get("midprice_shadow_action") != "MIDPRICE_CLEAN":
        risk.append(f"FIELD_TRAP:{shadow.get('field_band')}")
    if shadow.get("odds_band") in {"EIGHT_TO_FOURTEEN", "LONGSHOT_15_PLUS"}:
        risk.append(f"ODDS_RISK:{shadow.get('odds_band')}")
    if not shadow.get("passport_available"):
        risk.append("PASSPORT_NOT_AVAILABLE")
    if tri.get("final_action") == "TRI_WATCH" and ("MDS_GOLD" in " ".join(support) or frame_gate >= 0.62):
        questions.append("WATCH contains strong signal: should it be CASH_RUN or WIN?")
    if tri.get("final_action") == "TRI_CASH_RUN" and win_gate >= 0.58 and passport_strength >= 1.0:
        questions.append("Cash-run has win-gate plus passport: check if upgraded WIN is justified.")
    if old.get("bha_or_diff_flag") and not old.get("bha_or_diff_magnitude"):
        questions.append("BHA flag exists but magnitude missing: verify parser/source.")
    if old.get("spotlight_score") is None:
        questions.append("Spotlight missing: check RP parser coverage.")

    return support, risk, questions


def _priority(row: dict, support: list[str], risk: list[str], questions: list[str]) -> tuple[int, str]:
    tri_action = (row.get("tri_lane") or {}).get("final_action")
    old = row.get("old_velo") or {}
    if tri_action in {"TRI_CASH_RUN", "TRI_WIN"}:
        return 1, "EXECUTION_REVIEW"
    if old.get("tier") == "A" and (_float(old.get("mds")) >= 0.30 or _float(old.get("place_prob")) >= 0.62):
        return 2, "TIER_A_SIGNAL_REVIEW"
    if questions:
        return 3, "CONFLICT_REVIEW"
    if tri_action == "TRI_PASS" and len(support) >= 3:
        return 4, "PASS_WITH_SUPPORT_REVIEW"
    return 9, "LOW_PRIORITY"


def build_review(packet_path: Path, include_low_priority: bool = False) -> dict:
    packet = _load_json(packet_path, {})
    rows = []
    for row in packet.get("races") or []:
        support, risk, questions = _risk_and_support(row)
        priority_num, priority_label = _priority(row, support, risk, questions)
        if priority_num >= 9 and not include_low_priority:
            continue
        old = row.get("old_velo") or {}
        shadow = row.get("shadow") or {}
        review = {
            "date": row.get("date") or packet.get("date"),
            "race_id": row.get("race_id"),
            "course": row.get("course"),
            "off_time": row.get("off_time"),
            "race_name": row.get("race_name"),
            "horse": old.get("top"),
            "tri_action": (row.get("tri_lane") or {}).get("final_action"),
            "priority": priority_label,
            "priority_num": priority_num,
            "support": support,
            "risk": risk,
            "agent_questions": questions,
            "agent_instruction": (
                "Review this race using BHA/OR movement, Spotlight/RPD/RPDC, passport strength, "
                "MDS, field/odds regime, and outcome if available. Do not change live execution."
            ),
            "core_numbers": {
                "tier": old.get("tier"),
                "vp": old.get("velo_prime_prob"),
                "mds": old.get("mds"),
                "place_prob": old.get("place_prob"),
                "sp_dec": old.get("sp_dec"),
                "spotlight_score": old.get("spotlight_score"),
                "rpd_tag": old.get("rpd_tag"),
                "rpdc_release_score": old.get("rpdc_release_score"),
                "bha_or_diff": old.get("bha_or_diff"),
                "bha_or_diff_flag": old.get("bha_or_diff_flag"),
                "passport_strength_score": shadow.get("passport_strength_score"),
                "win_gate_probability": shadow.get("win_gate_probability"),
                "frame_gate_probability": shadow.get("frame_gate_probability"),
            },
            "new_build": row.get("new_build") or {},
            "shadow": shadow,
            "horse_state": old.get("horse_state") or {},
            "outcome": row.get("outcome") or {},
        }
        rows.append(review)

    rows.sort(key=lambda r: (r["priority_num"], str(r.get("date")), str(r.get("off_time"))))
    counts = Counter(r["priority"] for r in rows)
    return {
        "generated_at": _utc_now(),
        "source_packet": str(packet_path),
        "status": "AGENT_REVIEW_BOARD_PAPER_ONLY",
        "live_writes": False,
        "racing_api_used": False,
        "summary": {
            "review_cards": len(rows),
            "priority_counts": dict(counts),
        },
        "review_cards": rows,
    }


def _markdown(report: dict) -> str:
    lines = [
        "# Tri-Lane Agent Review Board",
        f"Generated: {report['generated_at']}",
        "",
        f"- Source: `{report['source_packet']}`",
        f"- Status: `{report['status']}`",
        f"- Live writes: `{report['live_writes']}`",
        "",
        "## Summary",
        "| Priority | Count |",
        "|---|---:|",
    ]
    for key, value in sorted(report["summary"]["priority_counts"].items()):
        lines.append(f"| {key} | {value} |")
    lines.extend([
        "",
        "## Review Cards",
        "| Date | Time | Course | Horse | Tri | Priority | Support | Risk | Questions |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for row in report["review_cards"][:200]:
        lines.append(
            f"| {row.get('date')} | {row.get('off_time')} | {row.get('course')} | "
            f"{row.get('horse')} | {row.get('tri_action')} | {row.get('priority')} | "
            f"{', '.join(row.get('support') or []) or '-'} | "
            f"{', '.join(row.get('risk') or []) or '-'} | "
            f"{' / '.join(row.get('agent_questions') or []) or '-'} |"
        )
    lines.extend([
        "",
        "## Agent Contract",
        "- The agent reviews and explains. It does not execute, stake, or promote.",
        "- Any proposed rule change must go back through Sigma replay and Mission Control.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", default=str(REPORT_DIR / "tri_lane_stress_test_latest.json"))
    parser.add_argument("--include-low-priority", action="store_true")
    args = parser.parse_args()

    packet_path = Path(args.packet)
    report = build_review(packet_path, include_low_priority=args.include_low_priority)
    suffix = packet_path.stem.replace("tri_lane_stress_test_", "")
    json_path = REPORT_DIR / f"tri_lane_agent_review_{suffix}.json"
    md_path = REPORT_DIR / f"tri_lane_agent_review_{suffix}.md"
    blob = json.dumps(report, indent=2, ensure_ascii=False)
    md = _markdown(report)
    json_path.write_text(blob + "\n", encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    (REPORT_DIR / "tri_lane_agent_review_latest.json").write_text(blob + "\n", encoding="utf-8")
    (REPORT_DIR / "tri_lane_agent_review_latest.md").write_text(md, encoding="utf-8")
    print(f"TRI_LANE_AGENT_REVIEW_COMPLETE cards={report['summary']['review_cards']}")
    print(f"priorities={report['summary']['priority_counts']}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
