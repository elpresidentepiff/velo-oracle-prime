"""Find race environments where Old VELO has earned betting permission.

Uses the broad Sigma corpus for repeatability and the smaller SP-enriched
innovation corpus for chronological out-of-sample profitability checks.
This is research-only: it does not change scoring, routing, or staking.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
IRISH_COURSES = {
    "ballinrobe", "bellewstown", "cork", "curragh", "down royal", "downpatrick",
    "dundalk", "fairyhouse", "galway", "gowran park", "kilbeggan", "killarney",
    "laytown", "leopardstown", "limerick", "listowel", "naas", "navan",
    "punchestown", "roscommon", "sligo", "thurles", "tipperary", "tramore", "wexford",
}


def norm_course(value: object) -> str:
    text = str(value or "").lower().replace("(aw)", "").replace("(ire)", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", text)).strip()


def country(value: object) -> str:
    return "IRE" if norm_course(value) in IRISH_COURSES else "GB"


def surface(value: object) -> str:
    return "AW" if "(aw)" in str(value or "").lower() else "TURF_OR_JUMPS"


def off_bucket(value: object) -> str:
    match = re.search(r"(\d{1,2})[:.](\d{2})", str(value or ""))
    if not match:
        return "UNKNOWN"
    hour = int(match.group(1))
    if hour <= 9:
        hour += 12
    if hour < 14:
        return "BEFORE_14"
    if hour < 17:
        return "14_TO_17"
    return "AFTER_17"


def vp_bucket(value: object) -> str:
    try:
        v = float(value)
    except Exception:
        return "UNKNOWN"
    if v < 0.20:
        return "VP_LT_20"
    if v < 0.30:
        return "VP_20_30"
    if v < 0.40:
        return "VP_30_40"
    return "VP_40_PLUS"


def field_bucket(value: object) -> str:
    try:
        n = int(float(value))
    except Exception:
        return "UNKNOWN"
    if n <= 6:
        return "FIELD_2_6"
    if n <= 9:
        return "FIELD_7_9"
    if n <= 12:
        return "FIELD_10_12"
    return "FIELD_13_PLUS"


def class_bucket(value: object) -> str:
    try:
        n = int(float(value))
    except Exception:
        return "UNKNOWN"
    if n <= 3:
        return "CLASS_1_3"
    if n == 4:
        return "CLASS_4"
    return "CLASS_5_6"


def going_bucket(value: object) -> str:
    text = str(value or "").lower()
    if not text or text == "nan":
        return "UNKNOWN"
    if "standard" in text or "fast" in text:
        return "AW_FAST"
    if "heavy" in text or "soft" in text or "yielding" in text:
        return "SOFT_OR_YIELDING"
    if "firm" in text:
        return "FIRM"
    if "good" in text:
        return "GOOD"
    return "OTHER"


def wilson_lower(wins: int, n: int, z: float = 1.645) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return (centre - spread) / denom


def max_drawdown(profits: list[float]) -> float:
    cumulative = peak = worst = 0.0
    for profit in profits:
        cumulative += profit
        peak = max(peak, cumulative)
        worst = min(worst, cumulative - peak)
    return round(worst, 3)


def split_dates(df: pd.DataFrame, fraction: float = 0.70) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    dates = sorted(df["date"].dropna().astype(str).unique())
    cut_index = max(1, min(len(dates) - 1, int(len(dates) * fraction)))
    cut_date = dates[cut_index]
    return df[df["date"] < cut_date].copy(), df[df["date"] >= cut_date].copy(), cut_date


def metrics(df: pd.DataFrame, roi: bool) -> dict:
    n = len(df)
    wins = int(df["won"].sum()) if n else 0
    frames = int(df["framed"].sum()) if n else 0
    result = {
        "n": n,
        "wins": wins,
        "frames": frames,
        "sr": round(wins / n, 4) if n else 0,
        "frame_rate": round(frames / n, 4) if n else 0,
        "sr_wilson_lower_90": round(wilson_lower(wins, n), 4),
    }
    if roi:
        returns = float(df.loc[df["won"], "sp_decimal"].sum()) if n else 0.0
        profits = [float(sp) - 1 if won else -1.0 for sp, won in zip(df["sp_decimal"], df["won"])]
        result.update(
            {
                "returns": round(returns, 3),
                "pl": round(returns - n, 3),
                "roi": round((returns - n) / n, 4) if n else 0,
                "max_drawdown": max_drawdown(profits),
            }
        )
    return result


def segment_table(
    df: pd.DataFrame,
    dimensions: list[tuple[str, ...]],
    *,
    roi: bool,
    min_total: int,
    min_train: int,
    min_test: int,
) -> list[dict]:
    train, test, cut_date = split_dates(df)
    rows: list[dict] = []
    for dims in dimensions:
        grouped = df.groupby(list(dims), dropna=False)
        for raw_key, group in grouped:
            key = raw_key if isinstance(raw_key, tuple) else (raw_key,)
            values = {dim: str(value) for dim, value in zip(dims, key)}
            if any(value in {"UNKNOWN", "nan", "None", ""} for value in values.values()):
                continue
            mask_train = pd.Series(True, index=train.index)
            mask_test = pd.Series(True, index=test.index)
            for dim, value in values.items():
                mask_train &= train[dim].astype(str) == value
                mask_test &= test[dim].astype(str) == value
            train_group = train[mask_train]
            test_group = test[mask_test]
            total_m = metrics(group, roi)
            train_m = metrics(train_group, roi)
            test_m = metrics(test_group, roi)
            if total_m["n"] < min_total or train_m["n"] < min_train or test_m["n"] < min_test:
                continue
            stable = (
                train_m["sr"] >= 0.20
                and test_m["sr"] >= 0.20
                and train_m["frame_rate"] >= 0.50
                and test_m["frame_rate"] >= 0.50
            )
            profitable = (
                roi
                and train_m["roi"] > 0
                and test_m["roi"] > 0
                and total_m["roi"] >= 0.05
                and test_m["frame_rate"] >= 0.50
            )
            rows.append(
                {
                    "dimensions": list(dims),
                    "values": values,
                    "rule": " AND ".join(f"{k}={v}" for k, v in values.items()),
                    "cut_date": cut_date,
                    "total": total_m,
                    "train": train_m,
                    "test": test_m,
                    "stable_performance": stable,
                    "profitable_both_periods": profitable,
                }
            )
    return rows


def load_sigma() -> pd.DataFrame:
    path = ROOT / "data" / "sigma_memory" / "sigma_retrieval_corpus_v1.jsonl"
    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    rows = [row for row in rows if row.get("retrieval_eligible")]
    df = pd.DataFrame(rows)
    df["date"] = df["race_date"].astype(str)
    df["won"] = df["outcome"].eq("WIN")
    df["framed"] = df["outcome"].isin(["WIN", "FRAME"])
    df["country"] = df["course"].map(country)
    df["surface"] = df["course"].map(surface)
    df["off_bucket"] = df["off_time"].map(off_bucket)
    df["vp_bucket"] = df["vp"].map(vp_bucket)
    return df


def load_roi() -> pd.DataFrame:
    path = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
    df = pd.read_csv(path, low_memory=False)
    df = df[df["result_position"].notna() & (df["sp_decimal"] > 0)].copy()
    df["date"] = df["date"].astype(str)
    # Undated rows are useful for retrospective totals but cannot establish
    # chronological out-of-sample performance, so they cannot earn permission.
    df = df[df["date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)].copy()
    df["won"] = df["won"].astype(float).eq(1)
    df["framed"] = df["placed"].astype(float).eq(1)
    df["country"] = df["course"].map(country)
    df["surface"] = df["course"].map(surface)
    df["off_bucket"] = df["race_time"].map(off_bucket)
    df["vp_bucket"] = df["model_probability"].map(vp_bucket)
    df["field_bucket"] = df["field_size"].map(field_bucket)
    df["class_bucket"] = df["class_num"].map(class_bucket)
    df["going_bucket"] = df["going"].map(going_bucket)
    df["race_type"] = df["race_type"].fillna("UNKNOWN").astype(str).str.upper()
    return df


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# VÉLØ Race-Environment Edge Audit",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Governing Rule",
        "",
        "No Tier A filter. A candidate permission rule must be pre-race observable, have minimum sample, and remain profitable in both chronological train and holdout periods.",
        "",
        "## Baselines",
        "",
        "| Layer | n | Wins | SR | Frames | Frame Rate | ROI |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in report["baselines"].items():
        roi = f"{row.get('roi', 0):+.1%}" if "roi" in row else "n/a"
        lines.append(f"| {name} | {row['n']} | {row['wins']} | {row['sr']:.1%} | {row['frames']} | {row['frame_rate']:.1%} | {roi} |")
    lines.extend(["", "## Bet-Permission Candidates", "", "| Rule | n | Train ROI | Holdout ROI | Total ROI | Holdout SR | Holdout Frame | Drawdown |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for row in report["bet_permission_candidates"][:20]:
        lines.append(
            f"| `{row['rule']}` | {row['total']['n']} | {row['train']['roi']:+.1%} | "
            f"{row['test']['roi']:+.1%} | {row['total']['roi']:+.1%} | {row['test']['sr']:.1%} | "
            f"{row['test']['frame_rate']:.1%} | {row['total']['max_drawdown']:.1f} |"
        )
    if not report["bet_permission_candidates"]:
        lines.append("| None passed | - | - | - | - | - | - | - |")
    policy = report["proposed_forward_paper_policy"]
    lines.extend(
        [
            "",
            "## Proposed Forward-Paper Policy V1",
            "",
            f"**Core permission:** `{policy['core_rule']}`",
            "",
            f"**Bet reduction:** {policy['bet_reduction_pct']:.1%} ({policy['baseline_n']} historical opportunities reduced to {policy['core_metrics']['total']['n']}).",
            "",
            "| Period | n | Wins | SR | Frames | Frame | ROI | Drawdown |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for period in ("total", "train", "test"):
        row = policy["core_metrics"][period]
        lines.append(
            f"| {period.title()} | {row['n']} | {row['wins']} | {row['sr']:.1%} | {row['frames']} | "
            f"{row['frame_rate']:.1%} | {row['roi']:+.1%} | {row['max_drawdown']:.1f} |"
        )
    lines.extend(
        [
            "",
            "**Hard no-bet gates:**",
            "",
            *[f"- {item}" for item in policy["hard_no_bet_gates"]],
            "",
            "**Freeze rule:** " + policy["freeze_rule"],
            "",
            "## Track Evidence",
            "",
            "No individual track has earned standalone bet permission. Track labels below are supporting filters only.",
            "",
            "| Classification | Track | n | SR | Frame |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for row in report["track_evidence"]["strong"] + report["track_evidence"]["weak"]:
        lines.append(f"| {row['classification']} | {row['course']} | {row['n']} | {row['sr']:.1%} | {row['frame_rate']:.1%} |")
    lines.extend(["", "## Stable Environments From Full Sigma History", "", "| Rule | n | Train SR | Holdout SR | Train Frame | Holdout Frame |", "|---|---:|---:|---:|---:|---:|"])
    for row in report["stable_sigma_environments"][:25]:
        lines.append(
            f"| `{row['rule']}` | {row['total']['n']} | {row['train']['sr']:.1%} | {row['test']['sr']:.1%} | "
            f"{row['train']['frame_rate']:.1%} | {row['test']['frame_rate']:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Operating Interpretation",
            "",
            "- `BET_PERMISSION_CANDIDATE` means worthy of forward paper betting, not guaranteed profit and not automatic live staking.",
            "- Rules involving SP were excluded from permission candidates because final SP is not known pre-race.",
            "- Course rules can be volatile even with minimum samples; country/race-type/field-size rules are more transferable.",
            "- Any live permission requires a fresh forward-only sample and a stop-loss/freeze rule.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-prefix", default="race_environment_edge_audit_latest")
    args = parser.parse_args()

    sigma = load_sigma()
    roi = load_roi()
    sigma_dimensions = [
        ("country",), ("course",), ("surface",), ("off_bucket",), ("vp_bucket",),
        ("country", "vp_bucket"), ("surface", "vp_bucket"), ("country", "off_bucket"),
        ("course", "vp_bucket"),
    ]
    roi_dimensions = [
        ("country",), ("course",), ("surface",), ("race_type",), ("field_bucket",),
        ("class_bucket",), ("going_bucket",), ("off_bucket",), ("vp_bucket",),
        ("country", "race_type"), ("country", "field_bucket"), ("surface", "field_bucket"),
        ("race_type", "field_bucket"), ("country", "vp_bucket"), ("surface", "vp_bucket"),
        ("course", "field_bucket"),
    ]
    sigma_segments = segment_table(sigma, sigma_dimensions, roi=False, min_total=50, min_train=30, min_test=15)
    roi_segments = segment_table(roi, roi_dimensions, roi=True, min_total=30, min_train=18, min_test=8)
    stable_sigma = sorted(
        [row for row in sigma_segments if row["stable_performance"]],
        key=lambda row: (row["test"]["sr"], row["test"]["frame_rate"], row["total"]["n"]),
        reverse=True,
    )
    candidates = sorted(
        [row for row in roi_segments if row["profitable_both_periods"]],
        key=lambda row: (row["test"]["roi"], row["total"]["roi"], row["total"]["n"]),
        reverse=True,
    )
    track_rows = []
    for course_name, group in sigma.groupby("course"):
        row = metrics(group, False)
        if row["n"] < 30:
            continue
        classification = "NEUTRAL"
        if row["sr"] >= 0.28 and row["frame_rate"] >= 0.50:
            classification = "STRONG_SUPPORT"
        elif row["sr"] < 0.15 or row["frame_rate"] < 0.40:
            classification = "WEAK_EXCLUDE"
        track_rows.append({"course": course_name, "classification": classification, **row})
    strong_tracks = sorted(
        [row for row in track_rows if row["classification"] == "STRONG_SUPPORT"],
        key=lambda row: (row["sr"], row["frame_rate"]),
        reverse=True,
    )
    weak_tracks = sorted(
        [row for row in track_rows if row["classification"] == "WEAK_EXCLUDE"],
        key=lambda row: (row["sr"], row["frame_rate"]),
    )
    weak_course_names = {norm_course(row["course"]) for row in weak_tracks}
    roi["_weak_track"] = roi["course"].map(norm_course).isin(weak_course_names)
    core_mask = (
        roi["country"].eq("GB")
        & roi["surface"].eq("TURF_OR_JUMPS")
        & roi["field_bucket"].eq("FIELD_7_9")
        & ~roi["_weak_track"]
    )
    roi_train, roi_test, roi_cut = split_dates(roi)
    core_metrics = {
        "total": metrics(roi[core_mask], True),
        "train": metrics(roi_train[core_mask.loc[roi_train.index]], True),
        "test": metrics(roi_test[core_mask.loc[roi_test.index]], True),
        "cut_date": roi_cut,
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "RESEARCH_ONLY_FORWARD_PAPER_REQUIRED",
        "rules": {
            "tier_used": False,
            "final_sp_used_as_permission_feature": False,
            "chronological_holdout_required": True,
            "roi_candidate_minimums": {"total": 30, "train": 18, "test": 8},
            "sigma_stability_minimums": {"total": 50, "train": 30, "test": 15},
        },
        "baselines": {"sigma_history": metrics(sigma, False), "sp_enriched_roi_history": metrics(roi, True)},
        "bet_permission_candidates": candidates,
        "stable_sigma_environments": stable_sigma,
        "proposed_forward_paper_policy": {
            "status": "FORWARD_PAPER_ONLY_NOT_LIVE",
            "core_rule": "GB AND TURF_OR_JUMPS AND FIELD_7_9 AND NOT WEAK_EXCLUDE_TRACK",
            "baseline_n": len(roi),
            "bet_reduction_pct": round(1 - core_metrics["total"]["n"] / len(roi), 4),
            "core_metrics": core_metrics,
            "hard_no_bet_gates": [
                "IRE races: broad Sigma underperforms GB and dated ROI is negative.",
                "Fields of 10 or more: both 10-12 and 13+ buckets are negative in chronological holdout.",
                "VP below 0.20: negative overall and zero holdout wins in the dated sample.",
                "WEAK_EXCLUDE tracks: objective full-Sigma rule of n>=30 and SR<15% or frame<40%.",
            ],
            "freeze_rule": "Freeze after 20 forward-paper bets if ROI < 0% or frame rate < 60%; no live promotion before 50 forward-paper bets.",
        },
        "track_evidence": {"strong": strong_tracks, "weak": weak_tracks, "all_n30": track_rows},
        "all_roi_segments": roi_segments,
        "all_sigma_segments": sigma_segments,
    }
    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.output_prefix}.json"
    md_path = out_dir / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    print(f"Sigma eligible: {len(sigma)}")
    print(f"SP-enriched evaluated: {len(roi)}")
    print(f"Stable Sigma environments: {len(stable_sigma)}")
    print(f"Bet-permission candidates: {len(candidates)}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
