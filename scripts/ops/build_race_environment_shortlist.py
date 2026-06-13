"""Apply the governed race-environment filter to a daily Old VELO card.

Research/paper only. This script never places bets or changes model scores.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.audit.race_environment_edge_audit import norm_course
from scripts.ops.run_results_sigma import _duplicate_alias_race_ids


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    tag = args.date.replace("-", "_")

    policy_path = ROOT / "data" / "reports" / "race_environment_edge_audit_latest.json"
    cards_path = ROOT / "data" / f"racecards_{tag}_standard.json"
    verdicts_path = ROOT / "data" / f"velo_prime_verdicts_{tag}.json"
    if not policy_path.exists() or not cards_path.exists() or not verdicts_path.exists():
        raise SystemExit("Missing policy, standard racecard, or Old VELO verdict artifact.")

    policy = json.loads(policy_path.read_text())
    weak_tracks = {
        norm_course(row["course"])
        for row in policy["track_evidence"]["weak"]
        if row["classification"] == "WEAK_EXCLUDE"
    }
    cards = {str(row["race_id"]): row for row in json.loads(cards_path.read_text())}
    verdicts = json.loads(verdicts_path.read_text())
    identity = {
        str(row.get("race_id", "")): {"course": row.get("course", ""), "off_time": row.get("off_time", "")}
        for row in verdicts
    }
    aliases = _duplicate_alias_race_ids(identity)

    rows = []
    for verdict in verdicts:
        race_id = str(verdict.get("race_id", ""))
        if race_id in aliases or race_id not in cards:
            continue
        card = cards[race_id]
        top = verdict.get("top") or {}
        region = str(card.get("region", "")).upper()
        surface = str(card.get("surface", "")).upper()
        field_size = int(card.get("field_size") or len(card.get("runners") or []))
        vp = float(top.get("velo_prime_prob") or 0)
        course_key = norm_course(card.get("course", ""))
        going = str(card.get("going", "")).upper()

        reasons = []
        status = "NO_BET"
        if region != "GB":
            reasons.append("IRE_NO_BET")
        if field_size >= 10:
            reasons.append("FIELD_10_PLUS_NO_BET")
        if vp < 0.20:
            reasons.append("VP_LT_20_NO_BET")
        if course_key in weak_tracks:
            reasons.append("WEAK_EXCLUDE_TRACK")

        blocked = bool(reasons)
        if not blocked and surface != "AW" and 7 <= field_size <= 9:
            status = "PAPER_BET"
            reasons.append("CORE_GB_TURF_OR_JUMPS_FIELD_7_9")
        elif not blocked and region == "GB" and "GOOD" in going:
            status = "WATCH_CHALLENGER"
            reasons.append("GB_GOOD_GOING_CHALLENGER")
        elif not blocked and region == "GB" and 2 <= field_size <= 6:
            status = "WATCH"
            reasons.append("GB_SMALL_FIELD_WATCH")
        else:
            reasons.append("NO_PERMISSION_RULE")

        rows.append(
            {
                "date": args.date,
                "race_id": race_id,
                "course": card.get("course"),
                "off_time": card.get("off_time"),
                "race_name": card.get("race_name"),
                "region": region,
                "surface": surface,
                "field_size": field_size,
                "going": card.get("going"),
                "horse": top.get("horse"),
                "velo_prime_prob": vp,
                "status": status,
                "reasons": reasons,
                "live_bet_allowed": False,
            }
        )

    order = {"PAPER_BET": 0, "WATCH_CHALLENGER": 1, "WATCH": 2, "NO_BET": 3}
    rows.sort(key=lambda row: (order[row["status"]], row["off_time"] or ""))
    summary = {status: sum(row["status"] == status for row in rows) for status in order}
    output = {
        "date": args.date,
        "status": "FORWARD_PAPER_ONLY_NOT_LIVE",
        "policy": policy["proposed_forward_paper_policy"],
        "summary": summary,
        "rows": rows,
    }
    out_dir = ROOT / "data" / "reports"
    json_path = out_dir / f"race_environment_shortlist_{tag}.json"
    md_path = out_dir / f"race_environment_shortlist_{tag}.md"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    lines = [
        f"# Race-Environment Shortlist: {args.date}",
        "",
        "**PAPER ONLY. Live betting remains blocked.**",
        "",
        f"- PAPER_BET: {summary['PAPER_BET']}",
        f"- WATCH_CHALLENGER: {summary['WATCH_CHALLENGER']}",
        f"- WATCH: {summary['WATCH']}",
        f"- NO_BET: {summary['NO_BET']}",
        "",
        "| Status | Time | Course | Horse | Field | VP | Reason |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['status']} | {row['off_time']} | {row['course']} | {row['horse']} | {row['field_size']} | "
            f"{row['velo_prime_prob']:.1%} | {', '.join(row['reasons'])} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
