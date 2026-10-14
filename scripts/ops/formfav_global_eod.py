#!/usr/bin/env python3
"""FormFav global end-of-day: settle results, then run shadow sigma.

SHADOW ONLY. Writes ``formfav_sigma_audits`` (and a JSON artifact) and nothing
else: never ``sigma_audits``, ``velo_verdicts``, ``pipeline_runs``, model
weights or Telegram. International results must not feed the UK learning loop.

Two steps per race day:

1. settle  - re-fetch every race whose stored result is missing or not yet
             ``final`` (the live worker stops polling 180 min after the off, so
             many races stay ``interim``/``pending`` forever).
2. sigma   - reconcile the stored model prediction against the stored result.
             ``final`` results and ``provisional`` ones (provider still says
             interim, placings present) are labelled separately; races with no
             usable result are ``no_result`` and excluded from any strike rate.

The live worker injects its own Supabase and provider helpers so this module
shares its rate-limit cooldown instead of opening a second one.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SETTLE_PACE_SECONDS = 0.7
SETTLE_MAX_CALLS_PER_PASS = 150
IN_CHUNK = 40


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def reconcile_race(
    race: dict[str, Any],
    prediction: dict[str, Any] | None,
    result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return one ``formfav_sigma_audits`` row, or None when nothing was predicted."""
    if not prediction:
        return None
    preds = (prediction.get("predictions_payload") or {}).get("predictions") or []
    preds = [p for p in preds if isinstance(p, dict)]
    if not preds:
        return None
    preds.sort(key=lambda p: _int(p.get("modelRank")) or 10**6)
    top1 = preds[0]
    top3 = preds[:3]
    by_number = {_int(p.get("number")): p for p in preds if _int(p.get("number")) is not None}

    placings = [
        p for p in ((result or {}).get("results_payload") or {}).get("placings") or []
        if isinstance(p, dict)
    ]
    live = [p for p in placings if not p.get("scratched")]
    winners = [p for p in live if _int(p.get("position")) == 1]

    if not result or not winners:
        basis = "no_result"
    elif result.get("interim") is False:
        basis = "final"
    else:
        basis = "provisional"

    row: dict[str, Any] = {
        "provider_race_key": race["provider_race_key"],
        "race_date": race.get("race_date"),
        "country": race.get("country"),
        "track": race.get("track"),
        "race_number": race.get("race_number"),
        "start_time": race.get("start_time"),
        "basis": basis,
        "result_stage": (result or {}).get("result_stage"),
        "model_version": prediction.get("model_version"),
        "confidence": prediction.get("confidence"),
        "field_size": len(preds),
        "top1_name": top1.get("name"),
        "top1_number": _int(top1.get("number")),
        "top1_win_prob": _num(top1.get("winProb")),
        "top1_finish_position": None,
        "top1_scratched": False,
        "top1_hit": None,
        "top3_names": [p.get("name") for p in top3],
        "winner_names": None,
        "winner_numbers": None,
        "dead_heat": False,
        "winner_in_top3": None,
        "winner_model_rank": None,
        "winner_win_prob": None,
        "details": {},
        "computed_at": datetime.now(UTC).isoformat(),
    }
    if basis == "no_result":
        row["details"] = {"placings": len(placings)}
        return row

    top1_number = _int(top1.get("number"))
    top1_placing = next((p for p in placings if _int(p.get("number")) == top1_number), None)
    row["top1_scratched"] = bool(top1_placing and top1_placing.get("scratched"))
    row["top1_finish_position"] = _int(top1_placing.get("position")) if top1_placing else None

    winner_numbers = [_int(p.get("number")) for p in winners]
    row["winner_numbers"] = winner_numbers
    row["winner_names"] = [p.get("name") for p in winners]
    row["dead_heat"] = len(winners) > 1
    top3_numbers = {_int(p.get("number")) for p in top3}
    row["top1_hit"] = top1_number in winner_numbers
    row["winner_in_top3"] = any(n in top3_numbers for n in winner_numbers)
    ranks = [
        _int(by_number[n].get("modelRank")) for n in winner_numbers
        if n in by_number and _int(by_number[n].get("modelRank")) is not None
    ]
    row["winner_model_rank"] = min(ranks) if ranks else None
    best = by_number.get(winner_numbers[0]) if winner_numbers else None
    row["winner_win_prob"] = _num(best.get("winProb")) if best else None
    row["details"] = {
        "placings": len(placings),
        "all_correct_weight": bool(placings) and all(
            p.get("resultStage") == "correct_weight" for p in live
        ),
    }
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for r in rows:
        bucket = out.setdefault(r.get("country") or "?", {}).setdefault(
            r["basis"], {"races": 0, "top1_wins": 0, "winner_in_top3": 0, "top1_scratched": 0}
        )
        bucket["races"] += 1
        bucket["top1_wins"] += 1 if r.get("top1_hit") else 0
        bucket["winner_in_top3"] += 1 if r.get("winner_in_top3") else 0
        bucket["top1_scratched"] += 1 if r.get("top1_scratched") else 0
    return out


def _chunks(items: list[str], n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _get_json(sb_request: Callable[..., bytes], path: str) -> list[dict[str, Any]]:
    raw = sb_request("GET", path)
    return json.loads(raw.decode("utf-8")) if raw else []


def load_day(sb_request: Callable[..., bytes], race_date: str) -> tuple[list, dict, dict]:
    qs = urllib.parse.urlencode({
        "race_date": f"eq.{race_date}",
        "select": "provider_race_key,race_date,country,track,race_number,start_time,timezone,meeting_slug",
        "order": "start_time.asc",
        "limit": "5000",
    })
    races = _get_json(sb_request, f"formfav_races?{qs}")
    keys = [r["provider_race_key"] for r in races]
    preds: dict[str, dict] = {}
    results: dict[str, dict] = {}
    for chunk in _chunks(keys, IN_CHUNK):
        in_list = "in.(" + ",".join(f'"{k}"' for k in chunk) + ")"
        for table, dest, cols in (
            ("formfav_predictions", preds, "provider_race_key,model_version,confidence,predictions_payload"),
            ("formfav_results", results, "provider_race_key,result_stage,interim,results_payload"),
        ):
            qs = urllib.parse.urlencode({"provider_race_key": in_list, "select": cols})
            for row in _get_json(sb_request, f"{table}?{qs}"):
                dest[row["provider_race_key"]] = row
    return races, preds, results


def settle_day(
    race_date: str,
    *,
    races: list[dict[str, Any]],
    results: dict[str, dict],
    preds: dict[str, dict],
    fetch_result: Callable[[dict[str, Any]], dict[str, Any]],
    persist_result: Callable[[str, dict[str, Any]], None],
    is_final: Callable[[dict[str, Any]], bool],
    on_error: Callable[[BaseException], bool],
    attempts: dict[str, int],
    max_attempts: int = 3,
    started_before: datetime | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Re-fetch results for predicted races that are not yet final."""
    now = started_before or datetime.now(UTC)
    todo = []
    for r in races:
        key = r["provider_race_key"]
        if key not in preds:
            continue
        res = results.get(key)
        if res is not None and res.get("interim") is False:
            continue
        start = r.get("start_time")
        if start and datetime.fromisoformat(str(start).replace("Z", "+00:00")) > now:
            continue  # not off yet
        if attempts.get(key, 0) >= max_attempts:
            continue
        todo.append(r)
    report = {"date": race_date, "candidates": len(todo), "fetched": 0, "upgraded_to_final": 0,
              "no_data": 0, "stopped_rate_limited": False}
    for r in todo[:SETTLE_MAX_CALLS_PER_PASS]:
        key = r["provider_race_key"]
        attempts[key] = attempts.get(key, 0) + 1
        try:
            payload = fetch_result(r)
        except Exception as exc:  # noqa: BLE001 - provider errors are per-race data gaps
            if on_error(exc):
                report["stopped_rate_limited"] = True
                break
            report["no_data"] += 1
            continue
        if not isinstance(payload, dict) or not payload.get("placings"):
            report["no_data"] += 1
            sleep(SETTLE_PACE_SECONDS)
            continue
        persist_result(key, payload)
        report["fetched"] += 1
        if is_final(payload):
            report["upgraded_to_final"] += 1
        sleep(SETTLE_PACE_SECONDS)
    return report


def run_day(
    race_date: str,
    *,
    sb_request: Callable[..., bytes],
    upsert: Callable[[str, list[dict[str, Any]], str], None],
    settle: dict[str, Any] | None,
    write_artifact: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Settle (when ``settle`` deps are supplied) then reconcile one race date."""
    races, preds, results = load_day(sb_request, race_date)
    settle_report = None
    if settle is not None and not dry_run:
        settle_report = settle_day(race_date, races=races, results=results, preds=preds, **settle)
        if settle_report["fetched"]:
            _, _, results = load_day(sb_request, race_date)
    rows = [
        row for r in races
        if (row := reconcile_race(r, preds.get(r["provider_race_key"]), results.get(r["provider_race_key"])))
    ]
    if rows and not dry_run:
        for chunk in _chunks_rows(rows, 200):
            upsert("formfav_sigma_audits", chunk, "provider_race_key")
    summary = summarise(rows)
    report = {
        "date": race_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "shadow_only": True,
        "races_in_db": len(races),
        "races_predicted": len(preds),
        "rows_written": 0 if dry_run else len(rows),
        "settle": settle_report,
        "by_country": summary,
    }
    if write_artifact and not dry_run:
        out_dir = ROOT / "data" / "sigma_results"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"formfav_global_sigma_{race_date.replace('-', '_')}.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
        except OSError:
            pass  # container FS is a convenience mirror; the DB rows are the record
    return report


def _chunks_rows(rows: list[dict[str, Any]], n: int):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def format_report(report: dict[str, Any]) -> str:
    lines = [f"[FORMFAV-EOD] {report['date']} rows={report['rows_written']} "
             f"predicted={report['races_predicted']}/{report['races_in_db']}"]
    if report.get("settle"):
        s = report["settle"]
        lines.append(
            f"[FORMFAV-EOD]   settle candidates={s['candidates']} fetched={s['fetched']} "
            f"final={s['upgraded_to_final']} no_data={s['no_data']} rate_limited={s['stopped_rate_limited']}"
        )
    for country, bases in sorted(report["by_country"].items()):
        for basis, b in sorted(bases.items()):
            lines.append(
                f"[FORMFAV-EOD]   {country} {basis}: races={b['races']} top1_wins={b['top1_wins']} "
                f"winner_in_top3={b['winner_in_top3']}"
            )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True, help="YYYY-MM-DD race date")
    ap.add_argument("--settle", action="store_true", help="re-fetch non-final results first")
    ap.add_argument("--dry-run", action="store_true", help="compute and print only; write nothing")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT))
    from scripts.ops import formfav_live_worker as worker
    from src.velo.formfav_client import FormFavClient

    settle_deps = None
    if args.settle:
        client = FormFavClient()
        settle_deps = {
            "fetch_result": lambda r: client.results(
                date=r["race_date"], track=r.get("meeting_slug") or r["track"],
                race=int(r["race_number"]), country=r["country"],
                timezone=r.get("timezone") or "UTC",
            ),
            "persist_result": worker._persist_result,
            "is_final": worker._looks_final,
            "on_error": worker._activate_provider_backoff,
            "attempts": {},
        }
    report = run_day(
        args.date, sb_request=worker._sb_request, upsert=worker._upsert,
        settle=settle_deps, dry_run=args.dry_run,
    )
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
