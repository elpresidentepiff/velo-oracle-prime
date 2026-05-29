"""
new_build_race_day_readiness.py
Generates a race-day readiness report for a target date.

Checks:
  - Paper predictions scored (from new_build_paper_predictions_latest.json)
  - Capture status for target date and next 2 days
  - Passport coverage by race
  - RPR/SP violation gates
  - Intent coverage note (expected 0% for current-card)

Usage:
  python scripts/ops/new_build_race_day_readiness.py --date 2026-05-30 [--execute]
"""
import argparse
import json
from datetime import datetime, date, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_raw"
INJ_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"
PAPER_REPORT = REPORT_DIR / "new_build_paper_predictions_latest.json"
REGISTRY_PATH = ROOT / "data" / "new_build" / "models" / "champion" / "champion_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _date_status(target_date: str) -> dict:
    raw_dir = PARSED_ROOT / target_date
    inj_path = INJ_ROOT / target_date / "racecard_injection.json"

    raw_exists = raw_dir.exists()
    inj_exists = inj_path.exists()

    if not inj_exists:
        return {
            "date": target_date,
            "raw_captured": raw_exists,
            "injection_exists": False,
            "races_count": 0,
            "runners_count": 0,
            "status": "NOT_CAPTURED",
            "action_required": "Capture RP racecard HTML pages for this date",
        }

    inj = _load_json(inj_path, {})
    races_count = inj.get("races_count", 0)
    runners_count = inj.get("runners_count", 0)
    skipped = len(inj.get("skipped", []))

    if races_count == 0 and skipped > 0:
        return {
            "date": target_date,
            "raw_captured": raw_exists,
            "injection_exists": True,
            "races_count": 0,
            "runners_count": 0,
            "skipped_html_files": skipped,
            "status": "CAPTURED_BUT_EMPTY",
            "action_required": (
                f"Re-capture: {skipped} HTML files parsed as NOT_RACECARD_PAYLOAD. "
                "Runners may not have been declared at capture time."
            ),
        }

    return {
        "date": target_date,
        "raw_captured": raw_exists,
        "injection_exists": True,
        "races_count": races_count,
        "runners_count": runners_count,
        "status": "READY",
        "action_required": None,
    }


def build_readiness(target_date: str, execute: bool = False) -> dict:
    paper = _load_json(PAPER_REPORT, {})
    registry = _load_json(REGISTRY_PATH, {})

    # Paper predictions metadata
    paper_class = paper.get("classification", "UNKNOWN")
    champion_version = paper.get("champion_version", registry.get("champion_version", "UNKNOWN"))
    rpr_violations = paper.get("rpr_violations", 0)
    intent_coverage = paper.get("intent_current_card_coverage", {})
    ff_counts = paper.get("feature_median_fill_counts", {})
    race_reports = paper.get("race_reports", [])

    # Filter races for target date and tomorrow
    target_races = [r for r in race_reports if r.get("race_date", "")[:10] == target_date]

    # Date windows: target_date is 2026-05-30, we look at 29, 30, 31, 01
    td = date.fromisoformat(target_date)
    yesterday = str(td.replace(day=td.day - 1)) if td.day > 1 else None
    # For simplicity build status for the 3 requested dates
    from datetime import timedelta
    dates_to_check = [
        str(td - timedelta(days=1)),  # yesterday = May 29
        str(td),                       # target = May 30
        str(td + timedelta(days=1)),   # +1 = May 31
        str(td + timedelta(days=2)),   # +2 = Jun 01
    ]
    date_statuses = {d: _date_status(d) for d in dates_to_check}

    # May 29 races from paper
    may29_date = str(td - timedelta(days=1))
    may29_races = [r for r in race_reports if r.get("race_date", "")[:10] == may29_date]

    # Quality gates
    gates = {
        "rpr_violations": rpr_violations == 0,
        "sp_in_features": "sp_dec" not in ff_counts and "log_sp" not in ff_counts,
        "champion_registered": bool(champion_version),
        "paper_predictions_present": bool(paper.get("paper_predictions_created")),
        "passport_coverage_above_50pct": (
            paper.get("current_card_feed", {}).get("passport_coverage", {}).get("coverage_pct", 0) >= 50
        ),
    }
    gates_pass = all(gates.values())

    def _extract_time(val: str | None) -> str | None:
        if not val:
            return None
        # Handle "2026-05-29T14:00:00+01:00" or "14:00"
        if "T" in val:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(val)
                return dt.strftime("%H:%M")
            except Exception:
                pass
        return val[:5] if len(val) >= 5 else val

    # Build May 29 race scorecards
    scorecards = []
    for race in sorted(may29_races, key=lambda r: r.get("off_time", "")):
        top3 = race.get("top_3", [])
        scorecards.append({
            "race_date": race.get("race_date", "")[:10],
            "off_time": _extract_time(race.get("off_time")),
            "course": race.get("course"),
            "race_title": race.get("race_title"),
            "runner_count": race.get("runner_count"),
            "passport_coverage": f"{race.get('passport_coverage')}/{race.get('runner_count')}",
            "top_3": [
                {
                    "rank": i + 1,
                    "horse": row.get("horse"),
                    "probability": row.get("champion_probability"),
                }
                for i, row in enumerate(top3[:3])
            ],
            "warnings": [w for w in race.get("missing_data_warnings", []) if w],
        })

    overall_status = "READY" if (date_statuses[may29_date]["status"] == "READY" and gates_pass) else "PARTIAL"

    payload = {
        "generated_at": _utc_now(),
        "target_date": target_date,
        "overall_status": overall_status,
        "model": {
            "champion_version": champion_version,
            "classification": paper_class,
            "rpr_violations": rpr_violations,
            "intent_coverage_pct": intent_coverage.get("coverage_pct", 0),
            "intent_note": "Expected 0% for current-card. Intent features filled from training medians.",
        },
        "quality_gates": gates,
        "gates_pass": gates_pass,
        "date_capture_status": date_statuses,
        "scoring_summary": {
            "2026-05-29_chepstow": {
                "races_scored": len(may29_races),
                "runners_scored": sum(r.get("runner_count", 0) for r in may29_races),
                "passport_coverage_pct": round(
                    sum(r.get("passport_coverage", 0) for r in may29_races)
                    / max(sum(r.get("runner_count", 1) for r in may29_races), 1) * 100, 1
                ),
                "status": "SCORED" if may29_races else "NO_DATA",
            },
        },
        "race_day_scorecards_2026_05_29": scorecards,
        "data_capture_actions": [
            s["action_required"]
            for s in date_statuses.values()
            if s.get("action_required")
        ],
        "rules": {
            "paper_only": True,
            "no_live_engine": True,
            "no_telegram": True,
            "old_live_velo_untouched": True,
            "shadow_velo_untouched": True,
            "no_staking": True,
            "rpr_archive_only": True,
        },
    }

    md_lines = [
        f"# Race Day Readiness: {target_date}",
        f"Generated: {payload['generated_at']}",
        "",
        f"**Overall Status:** `{overall_status}`",
        f"**Model:** `{champion_version}` — `{paper_class}`",
        f"**RPR violations:** {rpr_violations}",
        f"**Gates pass:** {gates_pass}",
        "",
        "## Quality Gates",
        "| Gate | Pass |",
        "|---|---|",
    ]
    for gate, passed in gates.items():
        md_lines.append(f"| {gate} | {'✓' if passed else '✗'} |")

    md_lines += ["", "## Date Capture Status"]
    for d, status in date_statuses.items():
        icon = "✓" if status["status"] == "READY" else "✗"
        action = f" — _{status.get('action_required', '')}_" if status.get("action_required") else ""
        md_lines.append(
            f"- **{d}**: `{status['status']}` — {status['races_count']} races, "
            f"{status['runners_count']} runners{action}"
        )

    md_lines += [
        "",
        "## Intent Coverage",
        f"- Intent current-card: **{intent_coverage.get('coverage_pct', 0)}%** — `{intent_coverage.get('status', 'UNKNOWN')}`",
        "- Expected 0% for current-card rows (model scores on Core+Passport; Intent median-fill applied).",
        "",
        "## Race Day Scorecards — 2026-05-29 Chepstow",
    ]
    for sc in scorecards:
        top3_str = ", ".join(
            f"{r['horse']} ({r['probability']:.3f})" for r in sc["top_3"]
        )
        md_lines += [
            "",
            f"### {sc['off_time']} {sc['course']} — {sc.get('race_title', '')[:50]}",
            f"- Runners: {sc['runner_count']} | Passport: {sc['passport_coverage']}",
            f"- **Top 3:** {top3_str}",
        ]
        if sc["warnings"]:
            md_lines.append(f"- Warnings: {'; '.join(sc['warnings'])}")

    md_lines += [
        "",
        "## Actions Required for May 30–Jun 01",
    ]
    for action in payload["data_capture_actions"]:
        md_lines.append(f"- {action}")
    if not payload["data_capture_actions"]:
        md_lines.append("- None")

    md_lines += [
        "",
        "## Boundaries",
        "- Paper-only intelligence. No betting instruction.",
        "- No Telegram, staking, live scoring table writes, or official-pick override.",
        "- Old Live VÉLØ and Shadow VÉLØ untouched.",
        "- RPR remains archive-only and is not a model input.",
    ]

    if execute:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_DIR / f"tomorrow_race_day_readiness_{target_date.replace('-', '_')}.json"
        md_path = REPORT_DIR / f"tomorrow_race_day_readiness_{target_date.replace('-', '_')}.md"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"Written: {json_path}")
        print(f"Written: {md_path}")
    else:
        print("DRY RUN — pass --execute to write reports.")

    return payload


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="Target race date YYYY-MM-DD")
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    result = build_readiness(args.date, execute=args.execute)
    print(f"\nOverall status: {result['overall_status']}")
    print(f"Gates pass: {result['gates_pass']}")
    print(f"May 29 races scored: {result['scoring_summary']['2026-05-29_chepstow']['races_scored']}")
    print(f"Actions required: {len(result['data_capture_actions'])}")
    for action in result["data_capture_actions"]:
        print(f"  - {action}")


if __name__ == "__main__":
    main()
