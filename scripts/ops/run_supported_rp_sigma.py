#!/usr/bin/env python3
"""RP-supported Sigma reconciliation.

Calculates strike/frame from the UK-only supported RP learning inputs. This is
the local, API-free Sigma path used for backfill and daily RP scraper learning.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", ""}


def norm(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("(aw)", "").replace(" aw", "")
    return re.sub(r"[^a-z0-9]", "", text)


def parse_pos(value: Any) -> str:
    return str(value or "").strip().upper()


def parse_sp(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().lower()
    if text in {"evens", "evensf", "evs", "evsf", "even", "evenf"}:
        return 2.0
    cleaned = re.sub(r"[^0-9./]", "", text)
    try:
        if "/" in cleaned:
            n, d = cleaned.split("/", 1)
            return round(float(n) / float(d) + 1.0, 2)
        return float(cleaned)
    except Exception:
        return 0.0


def miss_class(winner_sp: float) -> str:
    if 0 < winner_sp <= 3.0:
        return "short_fav_won"
    if winner_sp > 10.0:
        return "outsider_won"
    return "mid_priced_won"


def load_payload(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("results", []) if isinstance(raw, dict) else raw


def reconcile(day: str, verdicts_file: Path | None = None, results_file: Path | None = None) -> dict[str, Any]:
    tag = day.replace("-", "_")
    verdicts_path = verdicts_file or DATA / "learning_inputs" / f"velo_prime_verdicts_{tag}_supported.json"
    results_path = results_file or DATA / "learning_inputs" / f"results_{tag}_supported.json"
    if not verdicts_path.exists():
        raise FileNotFoundError(verdicts_path)
    if not results_path.exists():
        raise FileNotFoundError(results_path)

    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    results = load_payload(results_path)
    results_by_id = {str(r.get("race_id") or ""): r for r in results if r.get("race_id")}

    wins = frames = misses = true_non_runners = identity_failures = no_result = 0
    high_conf_n = high_conf_wins = 0
    hit_probs: list[float] = []
    miss_probs: list[float] = []
    miss_classes: dict[str, int] = {}
    rows: list[dict[str, Any]] = []

    for verdict in verdicts:
        race_id = str(verdict.get("race_id") or "")
        result = results_by_id.get(race_id)
        if not result:
            no_result += 1
            continue

        top = verdict.get("top") or {}
        pick = top.get("horse") or ""
        vp = float(top.get("velo_prime_prob") or 0)
        if vp >= 0.30:
            high_conf_n += 1

        runners = result.get("runners") or result.get("full_runners") or []
        runner = next((r for r in runners if norm(r.get("horse")) == norm(pick)), None)
        if not runner:
            pick_id = norm(top.get("horse_id") or "")
            if pick_id:
                runner = next((r for r in runners if norm(r.get("horse_id") or r.get("horse_rp_uid")) == pick_id), None)
        if not runner:
            non_runners = result.get("non_runners") or []
            if any(norm(nr.get("horse") if isinstance(nr, dict) else nr) == norm(pick) for nr in non_runners):
                true_non_runners += 1
                continue
            # Some older recovered caches only preserve placed/top-three runners.
            # If the pick is absent there, it is still a valid non-frame MISS.
            is_legacy_top3_only = not result.get("field_size") and 0 < len(runners) <= 3
            if is_legacy_top3_only:
                winner_name = result.get("winner_horse") or result.get("winner_name") or ""
                winner_sp = parse_sp(result.get("winner_sp"))
                if not winner_name and runners:
                    winner_name = runners[0].get("horse") or ""
                    winner_sp = parse_sp(runners[0].get("sp_dec") or runners[0].get("sp"))
                misses += 1
                miss_probs.append(vp)
                mclass = miss_class(winner_sp)
                miss_classes[mclass] = miss_classes.get(mclass, 0) + 1
                rows.append({
                    "race_id": race_id,
                    "course": result.get("course") or verdict.get("course"),
                    "off": result.get("off") or verdict.get("off_time"),
                    "predicted": pick,
                    "actual_name": winner_name,
                    "winner_sp": winner_sp,
                    "velo_prime_prob": vp,
                    "outcome": "MISS",
                    "miss_class": mclass,
                    "reconciliation_note": "legacy_top3_only_pick_absent",
                })
                continue
            identity_failures += 1
            no_result += 1
            continue

        pos = parse_pos(runner.get("position"))
        if pos in DNF_POSITIONS:
            true_non_runners += 1
            continue

        winner_name = result.get("winner_horse") or result.get("winner_name") or ""
        winner_sp = parse_sp(result.get("winner_sp"))
        if not winner_name:
            for r in runners:
                if parse_pos(r.get("position")) == "1":
                    winner_name = r.get("horse") or ""
                    winner_sp = parse_sp(r.get("sp_dec") or r.get("sp"))
                    break

        if pos == "1":
            wins += 1
            hit_probs.append(vp)
            outcome = "WIN"
            if vp >= 0.30:
                high_conf_wins += 1
            mclass = "n/a"
        elif pos in {"2", "3"}:
            frames += 1
            outcome = "PLACED"
            mclass = "n/a"
        else:
            misses += 1
            miss_probs.append(vp)
            outcome = "MISS"
            mclass = miss_class(winner_sp)
            miss_classes[mclass] = miss_classes.get(mclass, 0) + 1

        rows.append({
            "race_id": race_id,
            "course": result.get("course") or verdict.get("course"),
            "off": result.get("off") or verdict.get("off_time"),
            "predicted": pick,
            "actual_name": winner_name,
            "winner_sp": winner_sp,
            "velo_prime_prob": vp,
            "outcome": outcome,
            "miss_class": mclass,
        })

    evaluated = wins + frames + misses
    sr = wins / evaluated if evaluated else 0.0
    frame_rate = (wins + frames) / evaluated if evaluated else 0.0
    high_conf_sr = high_conf_wins / high_conf_n if high_conf_n else 0.0
    sigma_status = "PASS" if evaluated and no_result == 0 and identity_failures == 0 else "PARTIAL_RESULTS_DIAGNOSTIC_ONLY"
    if evaluated and sr < 0.15:
        sigma_note = "BELOW BASELINE - check miss_class distribution"
    elif evaluated and sr < 0.25:
        sigma_note = "AT BASELINE - review miss classes for pattern"
    else:
        sigma_note = "ABOVE BASELINE - model calibration healthy"

    artifact = {
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_predictions": len(verdicts),
        "result_races": len(results),
        "evaluated_count": evaluated,
        "wins": wins,
        "frames": frames,
        "misses": misses,
        "true_non_runners": true_non_runners,
        "identity_failures": identity_failures,
        "no_result_count": no_result,
        "total_reviewed": evaluated,
        "sr": round(sr, 4),
        "frame_rate": round(frame_rate, 4),
        "miss_class_breakdown": miss_classes,
        "high_conf_n": high_conf_n,
        "high_conf_sr": round(high_conf_sr, 4),
        "avg_hit_prob": round(sum(hit_probs) / len(hit_probs), 4) if hit_probs else 0,
        "avg_miss_prob": round(sum(miss_probs) / len(miss_probs), 4) if miss_probs else 0,
        "source": "racing_post_supported_sigma",
        "sigma_status": sigma_status,
        "sigma_note": sigma_note,
        "learning_candidate_rows": evaluated,
        "unresolved_rows": no_result,
        "raw_sigma_audits_preserved": True,
        "local_only_no_racing_api": True,
        "rows": rows,
    }
    return artifact


def write_outputs(artifact: dict[str, Any]) -> None:
    day = artifact["date"]
    tag = day.replace("-", "_")
    out_dir = DATA / "sigma_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"sigma_results_{tag}.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    md_path = out_dir / f"sigma_results_{tag}.md"
    md_path.write_text(
        "\n".join([
            f"# VELO Supported RP Sigma - {day}",
            f"",
            f"Status: {artifact['sigma_status']}",
            f"Source: {artifact['source']}",
            f"",
            f"| Metric | Value |",
            f"|---|---:|",
            f"| Evaluated | {artifact['evaluated_count']} |",
            f"| Wins | {artifact['wins']} |",
            f"| Frames | {artifact['frames']} |",
            f"| SR | {artifact['sr']:.1%} |",
            f"| Frame rate | {artifact['frame_rate']:.1%} |",
            f"| Non-runners excluded | {artifact['true_non_runners']} |",
            f"| No-result | {artifact['no_result_count']} |",
        ]),
        encoding="utf-8",
    )
    print(f"Written {json_path}")
    print(f"SR={artifact['sr']:.1%} Frame={artifact['frame_rate']:.1%} n={artifact['evaluated_count']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run API-free Sigma against supported RP learning inputs.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--verdicts-file")
    parser.add_argument("--results-file")
    args = parser.parse_args()
    artifact = reconcile(
        args.date,
        Path(args.verdicts_file) if args.verdicts_file else None,
        Path(args.results_file) if args.results_file else None,
    )
    write_outputs(artifact)


if __name__ == "__main__":
    main()
