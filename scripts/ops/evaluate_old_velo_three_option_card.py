"""ROLE-EVAL-01: dedicated evening evaluator for the Old VELO WIN/PLACE/LONGSHOT card.

Problem this replaces: build_old_velo_three_option_card.py mixed selection
(morning, pre-race) and result evaluation (evening, post-race) in one script.
Its own result join was also keyed by RP's raw numeric race_id while looking
it up with the rp_{COURSE_CODE}_{date}_{dot_time} scheme the runner snapshot
uses -- the join always missed, so role_metrics stayed zero regardless of
whether real results existed. The close harness then re-ran the same builder
after results arrived, which just regenerated the same pre-race selections
(no results ever get joined by that script) instead of evaluating them.

This script is read-only against the frozen morning card. It never rebuilds
or reorders the WIN/PLACE/LONGSHOT selections -- it only joins the exact
selections already made to the actual result, in this priority order:

  1. Exact race_id match (results are keyed by RP's raw numeric race_id;
     matched directly if the card ever carries that same id).
  2. Venue-code/full-course-name (via the shared course-abbreviation table)
     plus exact off_time match -- only if exactly one result race shares
     that (course, minute) key.
  3. A unique +/-3 minute fallback on the same course code -- only applied
     if exactly one candidate falls in that window; two or more candidates
     is an ambiguous match and is blocked, not guessed.

Runner identity within a matched race: the pick's horse_id first (works only
when it's a real RP numeric id, since the three-option card can carry a
synthetic rp_{course}_{slug} placeholder id that will never match), then a
normalised horse name (country-suffix and punctuation stripped) as fallback.

No live scoring change. No model or router change. No Supabase writes. No
Telegram. No promotion. No Racing API. Shadow/operator evidence only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Same course full-name -> code table used by new_build_dashboard_server.py's
# numeric_to_velo race_id bridge, kept in sync deliberately rather than
# imported, since that module pulls in unrelated dashboard-server dependencies.
COURSE_ABBR = {
    "Curragh": "CUR",
    "Uttoxeter": "UTT",
    "Cartmel": "CRT",
    "Wolverhampton": "WOL",
    "Wolverhampton (AW)": "WOL",
    "Kempton": "KEM",
    "Kempton (AW)": "KEM",
    "Chelmsford": "CHE",
    "Chelmsford City": "CHE",
    "Lingfield": "LIN",
    "Lingfield (AW)": "LIN",
    "Southwell": "SOW",
    "Southwell (AW)": "SOW",
    "Newcastle": "NCS",
    "Newcastle (AW)": "NCS",
    "Dundalk": "DUN",
    "Dundalk (AW)": "DUN",
    "Tramore": "TRM",
    "Brighton": "BRI",
    "Pontefract": "PON",
    "Newmarket": "NMK",
    "Newmarket (July)": "NMK",
    "Newmarket (Rowley Mile)": "NMK",
    "Worcester": "WOR",
    "Cork": "COR",
    "Chester": "CHS",
    "Kilbeggan": "KLB",
    "Ascot": "ASC",
    "York": "YOR",
    "Chester (AW)": "CHS",
}

NON_RUNNER_POSITIONS = {"NR", "WD", "VOID", "RO", "REF", ""}


def _date_tag(date: str) -> str:
    return date.replace("-", "_")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _course_code(name: str) -> str:
    # NOTE: deliberately no CHE->CHS-style venue-code alias here. That
    # collision in run_multimodel_sigma.py corrected a specific upstream feed
    # mislabeling Chester as "CHE"; applying it unconditionally to every
    # course-name lookup would incorrectly merge genuine Chelmsford (CHE)
    # results into Chester (CHS). Only add a venue alias here backed by a
    # confirmed real mislabeling in the data this script actually reads.
    code = COURSE_ABBR.get(name)
    if code:
        return code
    return re.sub(r"[^A-Za-z]", "", str(name or ""))[:3].upper()


def _parse_time_to_minutes(value: str) -> int | None:
    """Handle ISO ("...T13:35:00..."), 24h ("13.35"/"13:35"), and racing
    dot-time ("1.35" meaning 13:35, "8.00" meaning 20:00) formats.

    Racing dot-time convention: hour digits 1-9 with no context always mean
    the PM equivalent for UK/IRE afternoon/evening racing (there is no
    1am-9am racing), so they get +12. 10/11/12 are left as-is (10am-12pm
    starts exist for some jumps fixtures).
    """
    if not value:
        return None
    s = str(value)
    m = re.search(r"T(\d{2}):(\d{2})", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    sep = ":" if ":" in s else ("." if "." in s else None)
    if sep is None:
        return None
    parts = s.split(sep)
    try:
        h = int(parts[0])
        mi = int(parts[1])
    except (ValueError, IndexError):
        return None
    if h < 10:
        h += 12
    return h * 60 + mi


def _norm_horse(value: Any) -> str:
    s = str(value or "")
    s = re.sub(r"\s*\([A-Za-z]{2,4}\)\s*$", "", s)  # strip country suffix e.g. "(IRE)"
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_card(date: str) -> tuple[dict, Path]:
    path = DATA / "reports" / f"old_velo_three_option_card_{_date_tag(date)}.json"
    if not path.exists():
        raise SystemExit(f"ROLE_EVAL_BLOCKED: frozen card not found: {path}")
    return json.loads(path.read_text(encoding="utf-8")), path


def load_results(date: str) -> tuple[dict, Path]:
    path = DATA / "results" / f"rp_results_{_date_tag(date)}.json"
    if not path.exists():
        raise SystemExit(f"ROLE_EVAL_BLOCKED: results not found: {path}")
    return json.loads(path.read_text(encoding="utf-8")), path


class ResultIndex:
    """Three lookup structures over the canonical results payload, built once."""

    def __init__(self, results_payload: dict):
        self.by_id: dict[str, dict] = {}
        self._by_course_time: dict[tuple[str, int], list[dict]] = {}
        self._by_course: dict[str, list[tuple[int, dict]]] = {}

        for race in results_payload.get("results") or []:
            rid = str(race.get("race_id") or "")
            if rid:
                self.by_id[rid] = race
            code = _course_code(race.get("course", ""))
            minutes = _parse_time_to_minutes(race.get("off") or race.get("off_time") or "")
            if minutes is None:
                continue
            self._by_course_time.setdefault((code, minutes), []).append(race)
            self._by_course.setdefault(code, []).append((minutes, race))

        self._unique_course_time = {k: v[0] for k, v in self._by_course_time.items() if len(v) == 1}
        self._ambiguous_course_time = {k for k, v in self._by_course_time.items() if len(v) > 1}

    def find(self, card_race: dict) -> tuple[dict | None, str]:
        race_id = str(card_race.get("race_id") or "")
        if race_id and race_id in self.by_id:
            return self.by_id[race_id], "EXACT_RACE_ID"

        code = _course_code(card_race.get("course", ""))
        minutes = _parse_time_to_minutes(card_race.get("off_time", ""))
        if minutes is None:
            return None, "UNRESOLVED_NO_TIME"

        key = (code, minutes)
        if key in self._ambiguous_course_time:
            return None, "AMBIGUOUS_COURSE_TIME"
        if key in self._unique_course_time:
            return self._unique_course_time[key], "COURSE_TIME_EXACT"

        candidates = [r for (m, r) in self._by_course.get(code, []) if abs(m - minutes) <= 3]
        if len(candidates) == 1:
            return candidates[0], "COURSE_TIME_FALLBACK_3MIN"
        if len(candidates) > 1:
            return None, "AMBIGUOUS_FALLBACK_3MIN"
        return None, "UNRESOLVED_NO_MATCH"


def _find_runner(result_race: dict, pick: dict) -> tuple[dict | None, str]:
    runners = result_race.get("runners") or result_race.get("full_runners") or []
    pick_id = str(pick.get("horse_id") or "")
    if pick_id and not pick_id.startswith("rp_"):
        for runner in runners:
            if str(runner.get("horse_id") or "") == pick_id:
                return runner, "HORSE_ID"

    target = _norm_horse(pick.get("horse"))
    if target:
        for runner in runners:
            if _norm_horse(runner.get("horse")) == target:
                return runner, "HORSE_NAME"
    return None, "IDENTITY_MISS"


def evaluate(card: dict, results_payload: dict) -> dict:
    index = ResultIndex(results_payload)
    role_stats: dict[str, dict[str, Any]] = {
        role: {"evaluated": 0, "wins": 0, "frames": 0, "non_runners": 0, "identity_misses": 0, "profit_gbp": 0.0}
        for role in ("WIN", "PLACE", "LONGSHOT")
    }
    race_reports: list[dict] = []
    unresolved_races: list[dict] = []

    for race in card.get("races", []):
        result_race, method = index.find(race)
        report: dict[str, Any] = {
            "race_id": race.get("race_id"),
            "course": race.get("course"),
            "off_time": race.get("off_time"),
            "join_method": method,
        }
        if result_race is None:
            report["status"] = "UNRESOLVED"
            unresolved_races.append(report)
            race_reports.append(report)
            continue

        report["status"] = "RESOLVED"
        report["matched_result_race_id"] = result_race.get("race_id")
        picks_eval = []
        for pick in race.get("picks", []):
            role = pick.get("role")
            entry: dict[str, Any] = {"role": role, "horse": pick.get("horse")}
            runner, id_method = _find_runner(result_race, pick)
            entry["identity_method"] = id_method
            if runner is None:
                entry["status"] = "IDENTITY_MISS"
                role_stats[role]["identity_misses"] += 1
                picks_eval.append(entry)
                continue

            pos = str(runner.get("position") or "").strip().upper()
            is_non_runner = bool(runner.get("non_runner")) or pos in NON_RUNNER_POSITIONS
            if is_non_runner:
                entry["status"] = "NON_RUNNER"
                role_stats[role]["non_runners"] += 1
                picks_eval.append(entry)
                continue

            sp_dec = float(runner.get("sp_dec") or 0.0)
            win = pos == "1"
            frame = pos in ("1", "2", "3")
            entry.update(
                {
                    "status": "EVALUATED",
                    "position": pos,
                    "sp_dec": sp_dec,
                    "win": win,
                    "frame": frame,
                }
            )
            stats = role_stats[role]
            stats["evaluated"] += 1
            stats["wins"] += int(win)
            stats["frames"] += int(frame)
            stats["profit_gbp"] += (sp_dec - 1.0) if win else -1.0
            picks_eval.append(entry)

        report["picks"] = picks_eval
        race_reports.append(report)

    for _role, stats in role_stats.items():
        n = stats["evaluated"]
        stats["strike_rate"] = round(stats["wins"] / n, 4) if n else 0.0
        stats["frame_rate"] = round(stats["frames"] / n, 4) if n else 0.0
        stats["roi"] = round(stats["profit_gbp"] / n, 4) if n else 0.0
        stats["profit_gbp"] = round(stats["profit_gbp"], 2)

    return {
        "role_metrics": role_stats,
        "races": race_reports,
        "unresolved_races": unresolved_races,
    }


def write_outputs(date: str, card_path: Path, results_path: Path, evaluation: dict) -> tuple[Path, Path]:
    out_dir = DATA / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = _date_tag(date)
    json_path = out_dir / f"old_velo_role_evaluation_{tag}.json"
    md_path = out_dir / f"old_velo_role_evaluation_{tag}.md"

    payload = {
        "schema_version": "old_velo_role_evaluation_v1",
        "date": date,
        "generated_at": datetime.now(UTC).isoformat(),
        "frozen_card_path": str(card_path.relative_to(ROOT)),
        "frozen_card_sha256": _sha256_file(card_path),
        "results_path": str(results_path.relative_to(ROOT)),
        "results_sha256": _sha256_file(results_path),
        "no_scoring_change": True,
        "no_model_change": True,
        "no_router_change": True,
        "no_supabase_writes": True,
        "no_telegram": True,
        "no_promotion": True,
        **evaluation,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# Old VELO Role Evaluation — {date}",
        "",
        f"- Frozen card: `{payload['frozen_card_path']}` (sha256 `{payload['frozen_card_sha256'][:12]}...`)",
        f"- Results: `{payload['results_path']}` (sha256 `{payload['results_sha256'][:12]}...`)",
        "- Boundary: shadow/operator evidence only. No scoring, model, router, or Supabase change.",
        "",
        "## Role Metrics",
        "| Role | Evaluated | Wins | Frames | SR | Frame Rate | Non-Runners | Identity Misses | £1 P&L | ROI |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for role, stats in evaluation["role_metrics"].items():
        lines.append(
            f"| {role} | {stats['evaluated']} | {stats['wins']} | {stats['frames']} | "
            f"{stats['strike_rate']:.1%} | {stats['frame_rate']:.1%} | {stats['non_runners']} | "
            f"{stats['identity_misses']} | £{stats['profit_gbp']:.2f} | {stats['roi']:.1%} |"
        )

    unresolved = evaluation["unresolved_races"]
    lines.extend(["", f"## Unresolved Races ({len(unresolved)})"])
    if unresolved:
        lines.append("| Race ID | Course | Off Time | Reason |")
        lines.append("|---|---|---|---|")
        for r in unresolved:
            lines.append(f"| {r['race_id']} | {r['course']} | {r['off_time']} | {r['join_method']} |")
    else:
        lines.append("(none)")

    lines.extend(
        [
            "",
            "## Join Method Per Race",
            "| Race ID | Course | Off Time | Status | Join Method |",
            "|---|---|---|---|---|",
        ]
    )
    for r in evaluation["races"]:
        lines.append(f"| {r['race_id']} | {r['course']} | {r['off_time']} | {r['status']} | {r['join_method']} |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen Old VELO WIN/PLACE/LONGSHOT card against results. "
        "Never recomputes or reorders the morning selections."
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any race is unresolved or ambiguous, instead of "
        "silently completing with a partial reconciliation.",
    )
    args = parser.parse_args()

    card, card_path = load_card(args.date)
    results_payload, results_path = load_results(args.date)
    evaluation = evaluate(card, results_payload)

    json_path, md_path = write_outputs(args.date, card_path, results_path, evaluation)

    n_unresolved = len(evaluation["unresolved_races"])
    print(f"OLD_VELO_ROLE_EVALUATION_COMPLETE date={args.date} races={len(card['races'])} unresolved={n_unresolved}")
    for role, stats in evaluation["role_metrics"].items():
        print(
            f"  {role:10s} evaluated={stats['evaluated']:3d} wins={stats['wins']:3d} "
            f"frames={stats['frames']:3d} SR={stats['strike_rate']:.1%} "
            f"frame_rate={stats['frame_rate']:.1%} ROI={stats['roi']:.1%}"
        )
    print(f"json={json_path}")
    print(f"md={md_path}")

    if args.strict and n_unresolved:
        print(f"ROLE_EVAL_STRICT_FAIL: {n_unresolved} race(s) unresolved or ambiguous", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
