from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def _date_tag(date: str) -> str:
    return date.replace("-", "_")


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
        return out
    except (TypeError, ValueError):
        return default


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _latest_runner_snapshot(date: str) -> Path | None:
    tag = _date_tag(date)
    candidates = sorted(
        DATA.glob(f"runner_snapshots_{tag}_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_results(date: str) -> dict[str, dict[str, Any]]:
    path = DATA / "results" / f"rp_results_{_date_tag(date)}.json"
    payload = _load_json(path, {})
    return {str(r.get("race_id") or ""): r for r in payload.get("results") or [] if r.get("race_id")}


def _runner_outcome(result_race: dict[str, Any] | None, horse: str) -> dict[str, Any]:
    if not result_race:
        return {"status": "NO_RESULT"}
    horse_key = _norm(horse)
    for runner in result_race.get("runners") or []:
        if _norm(runner.get("horse")) != horse_key:
            continue
        pos = str(runner.get("position") or "").upper()
        non_runner = bool(runner.get("non_runner")) or pos == "NR"
        return {
            "status": "NON_RUNNER" if non_runner else "RESULT",
            "position": pos,
            "sp_dec": _num(runner.get("sp_dec")),
            "win": pos == "1",
            "frame": pos in {"1", "2", "3"},
        }
    return {"status": "UNMATCHED"}


def _pick_win(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(rows, key=lambda r: (_num(r.get("velo_prime_prob")), -int(r.get("rank") or 999)), default=None)


def _pick_place(rows: list[dict[str, Any]], used: set[str]) -> dict[str, Any] | None:
    candidates = [r for r in rows if str(r.get("horse_id") or r.get("horse")) not in used]
    if not candidates:
        candidates = rows
    return max(
        candidates,
        key=lambda r: (
            _num(r.get("place_prob")),
            _num(r.get("velo_prime_prob")),
            _num(r.get("market_deception_score")),
        ),
        default=None,
    )


def _longshot_score(row: dict[str, Any]) -> float:
    odds = _num(row.get("sp_dec"), 10.0)
    odds_band = 0.0
    if 6.0 <= odds <= 16.0:
        odds_band = 0.20
    elif 16.0 < odds <= 34.0:
        odds_band = 0.12
    elif 4.5 <= odds < 6.0:
        odds_band = 0.08
    return (
        _num(row.get("longshot_prob")) * 0.45
        + _num(row.get("market_deception_score")) * 0.25
        + _num(row.get("improvement_score")) * 0.15
        + _num(row.get("sqpe_no_rpr_shadow_prob")) * 0.10
        + odds_band
    )


def _pick_longshot(rows: list[dict[str, Any]], used: set[str]) -> dict[str, Any] | None:
    candidates = [
        r
        for r in rows
        if str(r.get("horse_id") or r.get("horse")) not in used
        and _num(r.get("sp_dec"), 10.0) >= 4.5
    ]
    if not candidates:
        candidates = [r for r in rows if str(r.get("horse_id") or r.get("horse")) not in used] or rows
    return max(candidates, key=_longshot_score, default=None)


def _role_payload(role: str, row: dict[str, Any] | None, result_race: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    outcome = _runner_outcome(result_race, str(row.get("horse") or ""))
    return {
        "role": role,
        "horse": row.get("horse"),
        "horse_id": row.get("horse_id"),
        "rank": row.get("rank"),
        "velo_prime_prob": _num(row.get("velo_prime_prob")),
        "place_prob": _num(row.get("place_prob")),
        "longshot_prob": _num(row.get("longshot_prob")),
        "market_deception_score": _num(row.get("market_deception_score")),
        "improvement_score": _num(row.get("improvement_score")),
        "sqpe_no_rpr_shadow_prob": _num(row.get("sqpe_no_rpr_shadow_prob")),
        "sp_dec": _num(row.get("sp_dec"), 10.0),
        "longshot_role_score": round(_longshot_score(row), 4),
        "cash_run_flag": bool(row.get("cash_run_flag")),
        "rpdc_primary_tag": row.get("rpdc_primary_tag"),
        "rpdc_release_score": row.get("rpdc_release_score"),
        "midprice_shadow_action": row.get("midprice_shadow_action"),
        "midprice_shadow_evidence": row.get("midprice_shadow_evidence"),
        "outcome": outcome,
    }


def build_card(date: str) -> dict[str, Any]:
    snapshot_path = _latest_runner_snapshot(date)
    if not snapshot_path:
        raise SystemExit(f"OLD_VELO_THREE_OPTION_BLOCKED: no runner snapshot for {date}")
    rows = [r for r in _read_jsonl(snapshot_path) if str(r.get("race_date") or "")[:10] == date]
    if not rows:
        raise SystemExit(f"OLD_VELO_THREE_OPTION_BLOCKED: snapshot has no rows for {date}")

    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_race[str(row.get("race_id") or "")].append(row)

    results = _load_results(date)
    races: list[dict[str, Any]] = []
    role_metrics: dict[str, dict[str, int]] = {
        "WIN": {"evaluated": 0, "wins": 0, "frames": 0},
        "PLACE": {"evaluated": 0, "wins": 0, "frames": 0},
        "LONGSHOT": {"evaluated": 0, "wins": 0, "frames": 0},
    }

    for race_id, race_rows in sorted(by_race.items(), key=lambda item: (item[1][0].get("course"), item[1][0].get("off_time"))):
        race_rows = sorted(race_rows, key=lambda r: int(r.get("rank") or 999))
        result_race = results.get(race_id)
        used: set[str] = set()
        win = _pick_win(race_rows)
        if win:
            used.add(str(win.get("horse_id") or win.get("horse")))
        place = _pick_place(race_rows, used)
        if place:
            used.add(str(place.get("horse_id") or place.get("horse")))
        longshot = _pick_longshot(race_rows, used)

        picks = [
            _role_payload("WIN", win, result_race),
            _role_payload("PLACE", place, result_race),
            _role_payload("LONGSHOT", longshot, result_race),
        ]
        for pick in [p for p in picks if p]:
            outcome = pick.get("outcome") or {}
            if outcome.get("status") != "RESULT":
                continue
            metric = role_metrics[pick["role"]]
            metric["evaluated"] += 1
            metric["wins"] += int(bool(outcome.get("win")))
            metric["frames"] += int(bool(outcome.get("frame")))

        races.append(
            {
                "race_id": race_id,
                "course": race_rows[0].get("course"),
                "off_time": race_rows[0].get("off_time"),
                "tier": race_rows[0].get("tier"),
                "runner_count": len(race_rows),
                "winner": (result_race or {}).get("winner_horse"),
                "winner_sp": (result_race or {}).get("winner_sp"),
                "result_status": "RESULT" if result_race else "NO_RESULT",
                "picks": [p for p in picks if p],
            }
        )

    return {
        "schema_version": "old_velo_three_option_card_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date,
        "source_snapshot": str(snapshot_path.relative_to(ROOT)),
        "races": races,
        "role_metrics": role_metrics,
        "rules": {
            "win": "highest velo_prime_prob",
            "place": "highest place_prob, distinct from WIN when possible",
            "longshot": "highest longshot/value score, prefers sp_dec >= 4.5 and distinct from WIN/PLACE when possible",
            "shadow_only": True,
            "live_scoring_changed": False,
            "staking": False,
        },
    }


def write_outputs(card: dict[str, Any]) -> tuple[Path, Path]:
    date = card["date"]
    tag = _date_tag(date)
    out_dir = DATA / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"old_velo_three_option_card_{tag}.json"
    md_path = out_dir / f"old_velo_three_option_card_{tag}.md"
    latest_json = out_dir / "old_velo_three_option_card_latest.json"
    latest_md = out_dir / "old_velo_three_option_card_latest.md"

    json_text = json.dumps(card, indent=2, ensure_ascii=False)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    lines = [
        f"# Old VELO Three-Option Card - {date}",
        "",
        f"- Source snapshot: `{card['source_snapshot']}`",
        "- Roles: WIN / PLACE / LONGSHOT",
        "- Boundary: shadow/operator card only. No scoring change, no staking.",
        "",
        "## Role Metrics",
        "| Role | Evaluated | Wins | SR | Frames | Frame |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for role, metric in card["role_metrics"].items():
        n = metric["evaluated"]
        sr = (metric["wins"] / n) if n else 0.0
        fr = (metric["frames"] / n) if n else 0.0
        lines.append(f"| {role} | {n} | {metric['wins']} | {sr:.1%} | {metric['frames']} | {fr:.1%} |")

    lines.extend(
        [
            "",
            "## Race Picks",
            "| Time | Course | Winner (SP) | WIN | W Pos | PLACE | P Pos | LONGSHOT | L Pos |",
            "|---|---|---:|---|---:|---|---:|---|---:|",
        ]
    )
    for race in card["races"]:
        by_role = {p["role"]: p for p in race["picks"]}

        def cell(role: str) -> tuple[str, str]:
            pick = by_role.get(role) or {}
            outcome = pick.get("outcome") or {}
            detail = (
                f"{pick.get('horse')} "
                f"(VP {pick.get('velo_prime_prob', 0):.3f}, PL {pick.get('place_prob', 0):.3f}, "
                f"LS {pick.get('longshot_prob', 0):.3f}, odds {pick.get('sp_dec', 0):.2f})"
                if pick
                else "-"
            )
            return detail, str(outcome.get("position") or outcome.get("status") or "-")

        win, win_pos = cell("WIN")
        place, place_pos = cell("PLACE")
        longshot, longshot_pos = cell("LONGSHOT")
        lines.append(
            f"| {race['off_time']} | {race['course']} | {race.get('winner')} ({race.get('winner_sp')}) | "
            f"{win} | {win_pos} | {place} | {place_pos} | {longshot} | {longshot_pos} |"
        )

    md_text = "\n".join(lines) + "\n"
    md_path.write_text(md_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Old VELO WIN/PLACE/LONGSHOT operator card from runner snapshots.")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    card = build_card(args.date)
    json_path, md_path = write_outputs(card)
    print(f"OLD_VELO_THREE_OPTION_COMPLETE date={args.date} races={len(card['races'])}")
    print(f"json={json_path}")
    print(f"md={md_path}")


if __name__ == "__main__":
    main()
