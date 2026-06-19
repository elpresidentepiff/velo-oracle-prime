"""
new_build_old_velo_comparison.py
Fair comparison evaluator: Old VELO vs New Build vs OR baseline.

For each race on a target date:
  A. Old VELO top pick  (from velo_prime_verdicts_YYYY_MM_DD.json)
  B. New Build top pick  (from new_build_predictions_YYYY_MM_DD.jsonl)
  C. OR baseline top pick  (highest official_rating in race, from New Build feed)
  D. New Build top 3
  E. Old VELO top pick inside New Build top 3 (alignment check)
  F. Winner / placed horses (from sigma results if available)

Rules:
  - Read-only. No Old VELO writes. No model changes. No Telegram. No staking.
  - If Old VELO verdict absent: classify OLD_VELO_ABSENT.
  - If sigma results absent: classify OUTCOME_PENDING.
  - AUC is NOT computed here — that requires same-split historical replay.

Usage:
  python scripts/ops/new_build_old_velo_comparison.py --date 2026-05-29 [--execute]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"
PRED_DIR = ROOT / "data" / "new_build" / "paper_predictions"
SIGMA_DIR = DATA_DIR / "sigma_results"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default=None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _fmt_time(val: str | None) -> str | None:
    if not val:
        return None
    if "T" in str(val):
        try:
            return datetime.fromisoformat(val).strftime("%H:%M")
        except Exception:
            pass
    return str(val)[:5] if len(str(val)) >= 5 else val


def _norm(s: str | None) -> str:
    return (s or "").upper().strip()


def _load_old_velo(date_str: str) -> dict[str, dict]:
    """Load Old VELO top picks keyed by race_id."""
    tag = date_str.replace("-", "_")
    path = DATA_DIR / f"velo_prime_verdicts_{tag}.json"
    if not path.exists():
        return {}
    rows = _load_json(path, [])
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        if not rid:
            continue
        top = row.get("top") or {}
        result[rid] = {
            "race_id": rid,
            "course": row.get("course") or "",
            "off_time": row.get("off_time") or "",
            "race_name": row.get("race_name") or "",
            "tier": row.get("tier") or "",
            "horse": top.get("horse") or "",
            "velo_prime_prob": top.get("velo_prime_prob"),
            "sqpe_prob": top.get("sqpe_v17_prob"),
        }
    return result


def _load_new_build(date_str: str) -> dict[str, list[dict]]:
    """Load New Build predictions grouped by race_id, sorted by rank."""
    tag = date_str.replace("-", "_")
    specific = PRED_DIR / f"new_build_predictions_{tag}.jsonl"
    rows = _read_jsonl(specific)
    if not rows:
        latest = PRED_DIR / "new_build_predictions_latest.jsonl"
        rows = [r for r in _read_jsonl(latest) if str(r.get("race_date", ""))[:10] == date_str]
    by_race: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            by_race[rid].append(row)
    for rid in by_race:
        by_race[rid].sort(key=lambda r: int(r.get("champion_rank") or 99))
    return dict(by_race)


def _load_sigma(date_str: str) -> dict[str, dict]:
    """Load sigma results (winners) keyed by race_id if available."""
    tag = date_str.replace("-", "_")
    path = SIGMA_DIR / f"sigma_results_{tag}.json"
    data = _load_json(path, None)
    if data is None:
        return {}
    rows = data if isinstance(data, list) else data.get("rows") or data.get("results") or data.get("verdicts") or []
    result: dict[str, dict] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            result[rid] = row
    return result


def _or_baseline_top(nb_runners: list[dict]) -> str | None:
    """Top pick by highest official_rating in the race (OR baseline)."""
    rated = [(r, float(r.get("official_rating") or 0)) for r in nb_runners]
    if not any(v > 0 for _, v in rated):
        return None
    return max(rated, key=lambda x: x[1])[0].get("horse")


def compare(date_str: str, execute: bool = False) -> dict:
    old_by_race = _load_old_velo(date_str)
    nb_by_race = _load_new_build(date_str)
    sigma_by_race = _load_sigma(date_str)

    old_velo_present = bool(old_by_race)
    outcomes_present = bool(sigma_by_race)

    all_race_ids = sorted(set(list(old_by_race.keys()) + list(nb_by_race.keys())))

    race_evals = []
    for rid in all_race_ids:
        nb_runners = nb_by_race.get(rid, [])
        old_row = old_by_race.get(rid, {})
        sigma_row = sigma_by_race.get(rid, {})

        nb_top = nb_runners[0].get("horse") if nb_runners else None
        nb_top_prob = float(nb_runners[0].get("champion_probability") or 0) if nb_runners else None
        nb_top3 = [r.get("horse") for r in nb_runners[:3]]

        old_top = old_row.get("horse") or None
        old_prob = old_row.get("velo_prime_prob")

        or_top = _or_baseline_top(nb_runners)

        # Alignment: is Old VELO pick inside New Build top 3?
        alignment = (
            _norm(old_top) in [_norm(h) for h in nb_top3]
            if old_top and nb_top3 else None
        )

        # Outcome
        winner = sigma_row.get("actual_name") or sigma_row.get("winner") or sigma_row.get("horse") if sigma_row else None
        placed = sigma_row.get("placed") or [] if sigma_row else []

        nb_win = _norm(nb_top) == _norm(winner) if nb_top and winner else None
        old_win = _norm(old_top) == _norm(winner) if old_top and winner else None
        or_win = _norm(or_top) == _norm(winner) if or_top and winner else None
        nb_placed = _norm(nb_top) in [_norm(h) for h in placed] if nb_top and placed else None

        course = nb_runners[0].get("course") if nb_runners else old_row.get("course", "")
        off_time = _fmt_time(nb_runners[0].get("off_time")) if nb_runners else old_row.get("off_time", "")

        race_evals.append({
            "race_id": rid,
            "course": course,
            "off_time": off_time,
            "runners_in_new_build": len(nb_runners),
            "old_velo_present": bool(old_row),
            "old_velo_top": old_top,
            "old_velo_prob": old_prob,
            "nb_top": nb_top,
            "nb_top_prob": nb_top_prob,
            "nb_top3": nb_top3,
            "or_baseline_top": or_top,
            "old_velo_in_nb_top3": alignment,
            "winner": winner,
            "placed": placed,
            "nb_top_win": nb_win,
            "old_velo_top_win": old_win,
            "or_baseline_win": or_win,
            "nb_top_placed": nb_placed,
            "outcome_available": bool(sigma_row),
        })

    # Summary stats
    races_with_both = [e for e in race_evals if e["old_velo_present"] and e["nb_top"]]
    aligned_count = sum(1 for e in races_with_both if e["old_velo_in_nb_top3"])
    decided = [e for e in race_evals if e["outcome_available"]]
    nb_wins = sum(1 for e in decided if e["nb_top_win"])
    old_wins = sum(1 for e in decided if e["old_velo_top_win"])
    or_wins = sum(1 for e in decided if e["or_baseline_win"])

    classification_parts = []
    if not old_velo_present:
        classification_parts.append("OLD_VELO_ABSENT")
    if not outcomes_present:
        classification_parts.append("OUTCOME_PENDING")
    if not classification_parts:
        classification_parts.append("OUTCOME_EVAL_COMPLETE")
    classification = "_".join(classification_parts)

    payload = {
        "generated_at": _utc_now(),
        "target_date": date_str,
        "classification": classification,
        "old_velo_present": old_velo_present,
        "outcomes_present": outcomes_present,
        "auc_comparison_status": (
            "OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY"
            if not old_velo_present
            else "OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY"
        ),
        "auc_note": (
            "AUC comparison requires same-split historical replay on identical races/runners/targets. "
            "Single-day SR/win comparison is indicative only, not statistically valid."
        ),
        "summary": {
            "total_races": len(all_race_ids),
            "races_with_both_signals": len(races_with_both),
            "alignment_old_in_nb_top3": aligned_count,
            "alignment_pct": round(aligned_count / len(races_with_both) * 100, 1) if races_with_both else None,
            "races_with_outcomes": len(decided),
            "nb_sr": round(nb_wins / len(decided), 4) if decided else None,
            "old_velo_sr": round(old_wins / len(decided), 4) if decided else None,
            "or_baseline_sr": round(or_wins / len(decided), 4) if decided else None,
        },
        "race_evaluations": race_evals,
        "rules": {
            "old_velo_untouched": True,
            "no_model_changes": True,
            "no_telegram": True,
            "no_staking": True,
            "paper_only": True,
        },
    }

    if execute:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_DIR / f"old_vs_new_build_outcome_eval_{date_str.replace('-', '_')}.json"
        md_path = REPORT_DIR / f"old_vs_new_build_outcome_eval_{date_str.replace('-', '_')}.md"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(_markdown(payload), encoding="utf-8")
        # Also write latest alias
        (REPORT_DIR / "old_vs_new_build_outcome_eval_latest.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        (REPORT_DIR / "old_vs_new_build_outcome_eval_latest.md").write_text(
            _markdown(payload), encoding="utf-8")
        print(f"Written: {json_path}")
        print(f"Written: {md_path}")

    return payload


def _markdown(p: dict) -> str:
    s = p["summary"]
    lines = [
        f"# Old VELO vs New Build Outcome Evaluation: {p['target_date']}",
        f"Generated: {p['generated_at']}",
        "",
        f"**Classification:** `{p['classification']}`",
        f"**AUC Status:** `{p['auc_comparison_status']}`",
        "",
        f"> {p['auc_note']}",
        "",
        "## Summary",
        "| Metric | Value |",
        "|---|---|",
        f"| Total races | {s['total_races']} |",
        f"| Races with both signals | {s['races_with_both_signals']} |",
        f"| Old VELO in NB top-3 (alignment) | {s['alignment_old_in_nb_top3']} / {s['races_with_both_signals']} ({s['alignment_pct']}%) |",
        f"| Races with outcomes | {s['races_with_outcomes']} |",
        f"| New Build SR | {s['nb_sr']} |",
        f"| Old VELO SR | {s['old_velo_sr']} |",
        f"| OR baseline SR | {s['or_baseline_sr']} |",
        "",
        "## AUC Comparison Requirement",
        "AUC is `NOT_COMPARABLE` until historical replay is run on the same split.",
        "See: `data/new_build/reports/historical_replay_requirement.md`",
        "",
        "## Race-by-Race Evaluation",
        "| Race | Course | Old VELO | New Build | NB Top-3 | OR Base | Winner | NB Win | Old Win |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for e in p["race_evaluations"]:
        nb_top3_str = ", ".join(e["nb_top3"][:3]) if e["nb_top3"] else "-"
        win = e["winner"] or ("PENDING" if not e["outcome_available"] else "N/A")
        nb_win = "Y" if e["nb_top_win"] else ("N" if e["nb_top_win"] is False else "-")
        old_win = "Y" if e["old_velo_top_win"] else ("N" if e["old_velo_top_win"] is False else "-")
        lines.append(
            f"| {e['race_id']} | {e['off_time']} {e['course']} | "
            f"{e['old_velo_top'] or '-'} | {e['nb_top'] or '-'} | "
            f"{nb_top3_str} | {e['or_baseline_top'] or '-'} | "
            f"{win} | {nb_win} | {old_win} |"
        )
    lines += [
        "",
        "## Boundaries",
        "- Read-only comparison. Old VELO model and scoring pipeline untouched.",
        "- No Telegram, staking, or live table writes.",
        "- AUC comparison requires same-split historical replay — not done here.",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    result = compare(args.date, execute=args.execute)
    s = result["summary"]
    print(f"Classification: {result['classification']}")
    print(f"Total races: {s['total_races']}")
    print(f"Old VELO present: {result['old_velo_present']}")
    print(f"Outcomes present: {result['outcomes_present']}")
    print(f"Alignment (old in NB top-3): {s['alignment_old_in_nb_top3']}/{s['races_with_both_signals']}")
    if s["nb_sr"] is not None:
        print(f"NB SR: {s['nb_sr']}  Old SR: {s['old_velo_sr']}  OR SR: {s['or_baseline_sr']}")


if __name__ == "__main__":
    main()
