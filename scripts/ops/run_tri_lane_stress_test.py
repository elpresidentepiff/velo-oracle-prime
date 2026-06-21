"""
Build a paper-only Tri-Lane VÉLØ stress-test packet.

The packet combines:
  - Old VÉLØ: candidate and probability stack
  - New Build / Passport: lane A/B top-3 and weak-data evidence
  - Shadow VÉLØ: action router and win/frame gates

This script never writes live tables, never changes scoring, and never stakes.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.radical.passport_feed import normalize_name  # noqa: E402

DATA_DIR = ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"
NEW_BUILD_REPORT_DIR = DATA_DIR / "new_build" / "reports"
SIGMA_DIR = DATA_DIR / "sigma_results"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(date: str) -> str:
    return date.replace("-", "_")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _norm(value: Any) -> str:
    return normalize_name(value)


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_old_verdicts(date: str) -> dict[str, dict]:
    rows = _load_json(DATA_DIR / f"velo_prime_verdicts_{_slug(date)}.json", [])
    if not isinstance(rows, list):
        return {}
    return {str(row.get("race_id")): row for row in rows if row.get("race_id")}


def _load_new_build(date: str) -> dict[str, dict]:
    data = _load_json(NEW_BUILD_REPORT_DIR / f"two_lane_readiness_{_slug(date)}.json", {})
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict] = {}
    for card in data.get("race_day_scorecards") or []:
        rid = str(card.get("race_id") or "")
        if rid:
            out[rid] = card
    return out


def _load_shadow(date: str) -> dict[str, dict]:
    data = _load_json(REPORT_DIR / f"radical_shadow_{_slug(date)}.json", {})
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict] = {}
    for row in data.get("decisions") or []:
        rid = str(row.get("race_id") or "")
        if rid:
            out[rid] = row
    return out


def _load_sigma(date: str) -> dict[str, dict]:
    data = _load_json(SIGMA_DIR / f"sigma_results_{_slug(date)}.json", {})
    rows = data.get("rows", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return {}
    return {str(row.get("race_id")): row for row in rows if row.get("race_id")}


def _names(rows: list[dict]) -> list[str]:
    return [str(row.get("horse") or "") for row in rows if row.get("horse")]


def _alignment(old_top: str, nb_card: dict) -> dict[str, Any]:
    lane_a = nb_card.get("lane_a_top3") or []
    lane_b = nb_card.get("lane_b_top3") or []
    old_norm = _norm(old_top)
    lane_a_names = _names(lane_a)
    lane_b_names = _names(lane_b)
    a_norm = [_norm(n) for n in lane_a_names]
    b_norm = [_norm(n) for n in lane_b_names]
    return {
        "old_in_lane_a_top3": old_norm in a_norm if old_top else None,
        "old_in_lane_b_top3": old_norm in b_norm if old_top else None,
        "lane_a_top": lane_a_names[0] if lane_a_names else None,
        "lane_b_top": lane_b_names[0] if lane_b_names else None,
        "lane_a_top3": lane_a_names[:3],
        "lane_b_top3": lane_b_names[:3],
        "lane_a_decision": lane_a[0].get("nb_decision_lane") if lane_a else None,
        "lane_b_decision": lane_b[0].get("nb_decision_lane") if lane_b else None,
    }


def _final_action(old_row: dict, nb_card: dict, shadow_row: dict, align: dict) -> tuple[str, list[str]]:
    top = old_row.get("top") or {}
    radical = shadow_row.get("radical") or {}
    passport = shadow_row.get("passport") or {}
    shadow_action = radical.get("action") or "UNKNOWN"
    midprice = (radical.get("midprice_shadow_action") or top.get("midprice_shadow_action") or "").upper()
    field_band = radical.get("field_band") or top.get("midprice_shadow_field_band") or ""
    win_gate = _float(shadow_row.get("win_gate_probability"), 0.0) or 0.0
    frame_gate = _float(shadow_row.get("frame_gate_probability"), 0.0) or 0.0
    passport_strength = _float(passport.get("passport_strength_score"), None)
    passport_ok = bool(passport.get("passport_available")) and (passport_strength is not None and passport_strength >= 1.0)
    weak_data = bool(nb_card.get("weak_data"))
    tier = str(old_row.get("tier") or "")
    reasons: list[str] = []

    if shadow_action == "PASS":
        reasons.append("shadow_hard_pass")
        return "TRI_PASS", reasons
    if midprice == "MIDPRICE_NO_EDGE":
        reasons.append("midprice_no_edge")
        return "TRI_PASS", reasons
    if midprice == "MIDPRICE_SUPPRESS_TOP" and field_band == "FS_13_PLUS":
        reasons.append("suppress_top_large_field")
        return "TRI_PASS", reasons
    if weak_data and not passport_ok:
        reasons.append("new_build_weak_data_without_passport_support")
        return "TRI_WATCH", reasons

    if shadow_action == "WIN_CANDIDATE_SHADOW":
        if tier == "A" and passport_ok and (align["old_in_lane_a_top3"] or align["old_in_lane_b_top3"]):
            reasons.extend(["old_tier_a", "passport_support", "new_build_alignment", "shadow_win_candidate"])
            return "TRI_WIN", reasons
        reasons.append("shadow_win_candidate_but_tri_confirmation_missing")
        return "TRI_WATCH", reasons

    if shadow_action == "CASH_RUN":
        if frame_gate >= 0.62:
            reasons.append("shadow_cash_run_frame_gate")
            if passport_ok:
                reasons.append("passport_support")
            return "TRI_CASH_RUN", reasons
        reasons.append("cash_run_without_frame_gate")
        return "TRI_WATCH", reasons

    if shadow_action in {"PASS_OR_WATCH", "WATCHLIST_SHADOW", "NO_BET_SHADOW"}:
        reasons.append(f"shadow_{shadow_action.lower()}")
        return "TRI_WATCH", reasons

    reasons.append("no_tri_lane_edge")
    return "TRI_NO_BET", reasons


def _final_action_v2(old_row: dict, nb_card: dict, shadow_row: dict, align: dict) -> tuple[str, list[str]]:
    """
    Tri-Lane v2 paper rules.

    v1 treated New Build weak_data as an early WATCH. The review board showed
    that this hid too many strong cash-run / Tier A signals. v2 keeps hard
    passes, but treats weak_data as a warning unless the rest of the stack is
    also weak.
    """
    top = old_row.get("top") or {}
    radical = shadow_row.get("radical") or {}
    passport = shadow_row.get("passport") or {}
    shadow_action = radical.get("action") or "UNKNOWN"
    midprice = (radical.get("midprice_shadow_action") or top.get("midprice_shadow_action") or "").upper()
    field_band = radical.get("field_band") or top.get("midprice_shadow_field_band") or ""
    odds_band = radical.get("odds_band") or ""
    win_gate = _float(shadow_row.get("win_gate_probability"), 0.0) or 0.0
    frame_gate = _float(shadow_row.get("frame_gate_probability"), 0.0) or 0.0
    passport_strength = _float(passport.get("passport_strength_score"), None)
    passport_ok = bool(passport.get("passport_available")) and (passport_strength is not None and passport_strength >= 1.0)
    weak_data = bool(nb_card.get("weak_data"))
    tier = str(old_row.get("tier") or "")
    vp = _float(top.get("velo_prime_prob"), 0.0) or 0.0
    mds = _float(top.get("market_deception_score"), 0.0) or 0.0
    place_prob = _float(top.get("place_prob"), 0.0) or 0.0
    rpdc_release = _float(top.get("rpdc_release_score"), 0.0) or 0.0
    rpdc_cash = bool(top.get("rpdc_cash_window_flag"))
    aligned = bool(align.get("old_in_lane_a_top3") or align.get("old_in_lane_b_top3"))
    reasons: list[str] = []

    # Permanent hard-pass zone.
    if shadow_action == "PASS":
        return "TRI_PASS", ["shadow_hard_pass"]
    if midprice == "MIDPRICE_NO_EDGE":
        return "TRI_PASS", ["midprice_no_edge"]
    if midprice == "MIDPRICE_SUPPRESS_TOP" and field_band == "FS_13_PLUS":
        return "TRI_PASS", ["suppress_top_large_field"]
    if odds_band == "LONGSHOT_15_PLUS" and field_band in {"FS_9_12", "FS_13_PLUS"}:
        return "TRI_PASS", ["longshot_large_field_toxic"]

    if weak_data:
        reasons.append("weak_data_warning_not_auto_pass")

    win_support = [
        tier == "A",
        shadow_action == "WIN_CANDIDATE_SHADOW",
        win_gate >= 0.58,
        vp >= 0.45,
        passport_ok or mds >= 0.30 or rpdc_release >= 0.70,
    ]
    if all(win_support):
        reasons.extend(["tier_a", "shadow_win_candidate", "win_gate", "vp_support"])
        if passport_ok:
            reasons.append("passport_support")
        if mds >= 0.30:
            reasons.append("mds_gold")
        if rpdc_release >= 0.70:
            reasons.append("rpdc_release")
        if aligned:
            reasons.append("new_build_alignment")
        return "TRI_WIN", reasons

    cash_support = (
        shadow_action == "CASH_RUN"
        and frame_gate >= 0.62
        and (
            place_prob >= 0.62
            or passport_ok
            or rpdc_cash
            or rpdc_release >= 0.70
            or tier == "A"
            or vp >= 0.30
        )
    )
    if cash_support:
        reasons.extend(["shadow_cash_run", "frame_gate"])
        if place_prob >= 0.62:
            reasons.append("place_prob_support")
        if passport_ok:
            reasons.append("passport_support")
        if rpdc_cash:
            reasons.append("rpdc_cash_window")
        if rpdc_release >= 0.70:
            reasons.append("rpdc_release")
        if tier == "A":
            reasons.append("tier_a")
        return "TRI_CASH_RUN", reasons

    # Strong non-cash watch: useful for agent review, not execution.
    if tier == "A" and (vp >= 0.45 or mds >= 0.30 or place_prob >= 0.62):
        reasons.extend(["tier_a_signal_watch"])
        if mds >= 0.30:
            reasons.append("mds_gold")
        return "TRI_WATCH_STRONG", reasons

    if shadow_action in {"PASS_OR_WATCH", "WATCHLIST_SHADOW", "NO_BET_SHADOW", "WIN_CANDIDATE_SHADOW", "CASH_RUN"}:
        reasons.append(f"shadow_{shadow_action.lower()}")
        return "TRI_WATCH", reasons

    return "TRI_NO_BET", ["no_tri_lane_edge"]


def build_packet(date: str, ruleset: str = "v1") -> dict:
    old = _load_old_verdicts(date)
    new = _load_new_build(date)
    shadow = _load_shadow(date)
    sigma = _load_sigma(date)

    race_ids = sorted(set(old) | set(new) | set(shadow))
    rows = []
    obstacles = []
    for required, label in [(old, "OLD_VELO"), (new, "NEW_BUILD"), (shadow, "SHADOW_VELO")]:
        if not required:
            obstacles.append(f"{label}_MISSING")

    for rid in race_ids:
        old_row = old.get(rid, {})
        nb_card = new.get(rid, {})
        shadow_row = shadow.get(rid, {})
        sigma_row = sigma.get(rid, {})
        top = old_row.get("top") or {}
        old_top = top.get("horse") or ""
        align = _alignment(old_top, nb_card) if nb_card else {
            "old_in_lane_a_top3": None,
            "old_in_lane_b_top3": None,
            "lane_a_top": None,
            "lane_b_top": None,
            "lane_a_top3": [],
            "lane_b_top3": [],
            "lane_a_decision": None,
            "lane_b_decision": None,
        }
        if old_row and shadow_row:
            action_fn = _final_action_v2 if ruleset == "v2" else _final_action
            final_action, reasons = action_fn(old_row, nb_card, shadow_row, align)
        else:
            final_action, reasons = "TRI_INCOMPLETE", ["missing_old_or_shadow"]
        actual = sigma_row.get("actual_name") or sigma_row.get("winner")
        outcome = sigma_row.get("outcome")
        rows.append({
            "date": date,
            "race_id": rid,
            "course": old_row.get("course") or nb_card.get("course") or shadow_row.get("course") or "",
            "off_time": old_row.get("off_time") or nb_card.get("off_time") or shadow_row.get("off_time") or "",
            "race_name": old_row.get("race_name") or nb_card.get("race_title") or shadow_row.get("race_name") or "",
            "old_velo": {
                "top": old_top or None,
                "tier": old_row.get("tier"),
                "velo_prime_prob": top.get("velo_prime_prob"),
                "mds": top.get("market_deception_score"),
                "improvement": top.get("improvement_score"),
                "place_prob": top.get("place_prob"),
                "sp_dec": top.get("sp_dec"),
                "midprice_shadow_action": top.get("midprice_shadow_action"),
                "spotlight_score": top.get("spotlight_score"),
                "rpd_tag": top.get("rpd_tag"),
                "rpd_confidence": top.get("rpd_confidence"),
                "rpd_evidence_codes": top.get("rpd_evidence_codes") or [],
                "rpdc_release_score": top.get("rpdc_release_score"),
                "rpdc_cash_window_flag": top.get("rpdc_cash_window_flag"),
                "rpdc_primary_tag": top.get("rpdc_primary_tag"),
                "rpdc_tags": top.get("rpdc_tags") or [],
                "bha_or_diff": top.get("bha_or_diff"),
                "bha_or_diff_flag": top.get("bha_or_diff_flag"),
                "bha_or_diff_magnitude": top.get("bha_or_diff_magnitude"),
                "candidate_execution_lane": top.get("candidate_execution_lane"),
                "candidate_execution_reason": top.get("candidate_execution_reason") or [],
                "horse_state": top.get("horse_state") or {},
            },
            "new_build": {
                "weak_data": nb_card.get("weak_data"),
                "passport_coverage": nb_card.get("passport_coverage"),
                "passport_coverage_pct": nb_card.get("passport_coverage_pct"),
                **align,
            },
            "shadow": {
                "action": (shadow_row.get("radical") or {}).get("action"),
                "confidence": (shadow_row.get("radical") or {}).get("confidence"),
                "field_band": (shadow_row.get("radical") or {}).get("field_band"),
                "odds_band": (shadow_row.get("radical") or {}).get("odds_band"),
                "win_gate_probability": shadow_row.get("win_gate_probability"),
                "frame_gate_probability": shadow_row.get("frame_gate_probability"),
                "passport_available": (shadow_row.get("passport") or {}).get("passport_available"),
                "passport_strength_score": (shadow_row.get("passport") or {}).get("passport_strength_score"),
                "passport_reason_codes": (shadow_row.get("passport") or {}).get("reason_codes") or [],
                "passport_live_features": (shadow_row.get("passport") or {}).get("passport_live_features") or {},
                "warnings": (shadow_row.get("radical") or {}).get("warnings") or [],
                "reasons": (shadow_row.get("radical") or {}).get("reasons") or [],
            },
            "tri_lane": {
                "final_action": final_action,
                "reasons": reasons,
                "ruleset": ruleset,
                "paper_only": True,
                "live_execution_allowed": False,
            },
            "outcome": {
                "available": bool(sigma_row),
                "actual_winner": actual,
                "winner_sp": sigma_row.get("winner_sp"),
                "old_pick_outcome": outcome,
                "tri_win_hit": final_action == "TRI_WIN" and str(outcome).upper() == "WIN",
                "tri_frame_hit": final_action in {"TRI_WIN", "TRI_CASH_RUN"} and str(outcome).upper() in {"WIN", "PLACED"},
            },
        })

    counts = Counter(row["tri_lane"]["final_action"] for row in rows)
    evaluated = [row for row in rows if row["outcome"]["available"]]
    by_action = []
    for action in sorted(counts):
        sub = [row for row in evaluated if row["tri_lane"]["final_action"] == action]
        n = len(sub)
        wins = sum(1 for row in sub if str(row["outcome"]["old_pick_outcome"]).upper() == "WIN")
        frames = sum(1 for row in sub if str(row["outcome"]["old_pick_outcome"]).upper() in {"WIN", "PLACED"})
        by_action.append({
            "action": action,
            "races": counts[action],
            "evaluated": n,
            "wins": wins,
            "strike_rate": round(wins / n * 100, 2) if n else None,
            "frames": frames,
            "frame_rate": round(frames / n * 100, 2) if n else None,
        })

    return {
        "generated_at": _utc_now(),
        "date": date,
        "ruleset": ruleset,
        "status": f"TRI_LANE_STRESS_TEST_ONLY_{ruleset.upper()}",
        "live_writes": False,
        "racing_api_used": False,
        "inputs": {
            "old_velo_races": len(old),
            "new_build_races": len(new),
            "shadow_races": len(shadow),
            "sigma_outcomes": len(sigma),
        },
        "obstacles": obstacles,
        "summary": {
            "total_races": len(rows),
            "action_counts": dict(counts),
            "evaluated_races": len(evaluated),
            "by_action": by_action,
        },
        "races": rows,
    }


def _available_dates(start_date: str, end_date: str) -> list[str]:
    dates = set()
    for path in DATA_DIR.glob("velo_prime_verdicts_20??_??_??.json"):
        stem = path.stem.replace("velo_prime_verdicts_", "")
        date = stem.replace("_", "-")
        if start_date <= date <= end_date:
            dates.add(date)
    return sorted(dates)


def build_multi_day_packet(start_date: str, end_date: str, ruleset: str = "v1") -> dict:
    packets = []
    obstacles = []
    for date in _available_dates(start_date, end_date):
        packet = build_packet(date, ruleset=ruleset)
        has_all_core = (
            packet["inputs"]["old_velo_races"] > 0
            and packet["inputs"]["new_build_races"] > 0
            and packet["inputs"]["shadow_races"] > 0
        )
        if not has_all_core:
            obstacles.append(f"{date}:MISSING_CORE_LANE:{packet['inputs']}")
        packets.append(packet)

    rows = []
    inputs = Counter()
    for packet in packets:
        for key, value in packet["inputs"].items():
            inputs[key] += int(value or 0)
        rows.extend(packet["races"])
        obstacles.extend(f"{packet['date']}:{item}" for item in packet.get("obstacles") or [])

    counts = Counter(row["tri_lane"]["final_action"] for row in rows)
    evaluated = [row for row in rows if row["outcome"]["available"]]
    by_action = []
    for action in sorted(counts):
        sub = [row for row in evaluated if row["tri_lane"]["final_action"] == action]
        n = len(sub)
        wins = sum(1 for row in sub if str(row["outcome"]["old_pick_outcome"]).upper() == "WIN")
        frames = sum(1 for row in sub if str(row["outcome"]["old_pick_outcome"]).upper() in {"WIN", "PLACED"})
        by_action.append({
            "action": action,
            "races": counts[action],
            "evaluated": n,
            "wins": wins,
            "strike_rate": round(wins / n * 100, 2) if n else None,
            "frames": frames,
            "frame_rate": round(frames / n * 100, 2) if n else None,
        })

    by_date = []
    for packet in packets:
        by_date.append({
            "date": packet["date"],
            "inputs": packet["inputs"],
            "action_counts": packet["summary"]["action_counts"],
            "by_action": packet["summary"]["by_action"],
            "obstacles": packet.get("obstacles") or [],
        })

    return {
        "generated_at": _utc_now(),
        "date": f"{start_date}_to_{end_date}",
        "start_date": start_date,
        "end_date": end_date,
        "ruleset": ruleset,
        "status": f"TRI_LANE_STRESS_TEST_ONLY_MULTI_DAY_{ruleset.upper()}",
        "live_writes": False,
        "racing_api_used": False,
        "inputs": dict(inputs),
        "obstacles": obstacles,
        "summary": {
            "days_scanned": len(packets),
            "total_races": len(rows),
            "action_counts": dict(counts),
            "evaluated_races": len(evaluated),
            "by_action": by_action,
        },
        "by_date": by_date,
        "races": rows,
    }


def _markdown(packet: dict) -> str:
    lines = [
        f"# Tri-Lane VÉLØ Stress Test - {packet['date']}",
        f"Generated: {packet['generated_at']}",
        "",
        f"- Status: `{packet['status']}`",
        f"- Live writes: `{packet['live_writes']}`",
        f"- Racing API used: `{packet['racing_api_used']}`",
        "",
        "## Inputs",
        "| Input | Races |",
        "|---|---:|",
    ]
    for key, value in packet["inputs"].items():
        lines.append(f"| {key} | {value} |")
    if packet["obstacles"]:
        lines.extend(["", "## Obstacles"])
        for obstacle in packet["obstacles"]:
            lines.append(f"- {obstacle}")
    lines.extend([
        "",
        "## Action Summary",
        "| Final action | Races | Evaluated | Wins | SR | Frames | Frame |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in packet["summary"]["by_action"]:
        lines.append(
            f"| {row['action']} | {row['races']} | {row['evaluated']} | {row['wins']} | "
            f"{row['strike_rate']}% | {row['frames']} | {row['frame_rate']}% |"
        )
    lines.extend([
        "",
        "## Race Decisions",
        "| Date | Time | Course | Old pick | New Build A/B | Shadow | Final | Outcome |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for row in packet["races"]:
        old = row["old_velo"]
        nb = row["new_build"]
        shadow = row["shadow"]
        outcome = row["outcome"]
        lines.append(
            f"| {row.get('date') or packet['date']} | {row['off_time']} | {row['course']} | "
            f"{old.get('top') or '-'} ({old.get('tier') or '-'}) | "
            f"A:{nb.get('lane_a_top') or '-'} / B:{nb.get('lane_b_top') or '-'} | "
            f"{shadow.get('action') or '-'} | "
            f"{row['tri_lane']['final_action']} | "
            f"{outcome.get('old_pick_outcome') or '-'} / {outcome.get('actual_winner') or '-'} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "- Stress test only. No live execution, no staking, no production promotion.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--ruleset", choices=["v1", "v2"], default="v1")
    args = parser.parse_args()

    if args.date:
        packet = build_packet(args.date, ruleset=args.ruleset)
        slug = f"{_slug(args.date)}_{args.ruleset}"
        title = args.date
    else:
        if not args.start_date or not args.end_date:
            parser.error("provide --date or both --start-date and --end-date")
        packet = build_multi_day_packet(args.start_date, args.end_date, ruleset=args.ruleset)
        slug = f"{_slug(args.start_date)}_to_{_slug(args.end_date)}_{args.ruleset}"
        title = f"{args.start_date}_to_{args.end_date}"

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"tri_lane_stress_test_{slug}.json"
    md_path = REPORT_DIR / f"tri_lane_stress_test_{slug}.md"
    json_blob = json.dumps(packet, indent=2, ensure_ascii=False)
    md = _markdown(packet)
    json_path.write_text(json_blob + "\n", encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    (REPORT_DIR / "tri_lane_stress_test_latest.json").write_text(json_blob + "\n", encoding="utf-8")
    (REPORT_DIR / "tri_lane_stress_test_latest.md").write_text(md, encoding="utf-8")

    print(f"TRI_LANE_STRESS_TEST_COMPLETE date={title} races={packet['summary']['total_races']}")
    print(f"actions={packet['summary']['action_counts']}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
