"""
CASHRUN Activation Audit — evidence-only, no live weighting.

Reads all historical cashrun CSVs + results JSONs.
Measures per-bucket performance: SR, place rate, ROI, avg SP, overlaps.
Output: data/reports/cashrun_activation_audit_latest.json + .md
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"

DNF = {"PU", "F", "UR", "BD", "RO", "DSQ", "SU", "CO", "REF", "WV", "NR"}
PLACE_POSITIONS = {"1", "2", "3"}


def _norm_name(s: str) -> str:
    return re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", str(s or "")).upper().split("(")[0].strip()


def _parse_sp(sp_str: str) -> float | None:
    s = str(sp_str or "").strip()
    if not s or s in {"-", "–", ""}:
        return None
    # decimal SP
    try:
        return float(s)
    except ValueError:
        pass
    # fractional SP e.g. "7/2"
    m = re.match(r"^(\d+)/(\d+)$", s)
    if m:
        return int(m.group(1)) / int(m.group(2)) + 1.0
    return None


def _load_results() -> dict[str, dict[str, dict]]:
    """Build index: {date: {race_id: {horse_name_upper: {pos, sp_dec}}}}"""
    index: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    for path in sorted(DATA_DIR.glob("results_*.json")):
        m = re.search(r"results_(\d{4})[_-](\d{2})[_-](\d{2})", path.name)
        if not m:
            continue
        date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        races = payload if isinstance(payload, list) else payload.get("results", [])
        for race in (races or []):
            race_id = race.get("race_id", "")
            for runner in race.get("runners", []):
                name = _norm_name(runner.get("horse", ""))
                pos = str(runner.get("position", "")).strip()
                sp_dec = runner.get("sp_dec") or runner.get("sp")
                index[date_str][race_id][name] = {
                    "pos": pos,
                    "sp_dec": _parse_sp(str(sp_dec or "")),
                }
    return index


def _load_cashrun_rows() -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple] = set()
    for path in sorted(DATA_DIR.glob("cashrun_report_*.csv")):
        try:
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row.get("date", ""), row.get("race_id", ""), row.get("horse_id", ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(row)
        except Exception:
            continue
    return rows


def _bucket_stats(rows: list[dict]) -> dict[str, Any]:
    wins = places = total = 0
    roi_sum = 0.0
    sps: list[float] = []
    vp30_overlap = mds_overlap = 0

    for r in rows:
        total += 1
        pos = r.get("_pos", "")
        sp = r.get("_sp_dec")
        vp30 = str(r.get("vp30_overlap", "")).strip() in {"True", "true", "1", "yes"}
        mds = str(r.get("racing_api_positive_overlap", "")).strip() in {"True", "true", "1", "yes"}

        if vp30:
            vp30_overlap += 1
        if mds:
            mds_overlap += 1

        if pos in DNF or not pos:
            continue

        if pos == "1":
            wins += 1
            places += 1
            if sp is not None:
                roi_sum += sp - 1.0
                sps.append(sp)
        elif pos in PLACE_POSITIONS:
            places += 1
            if sp is not None:
                roi_sum -= 1.0
                sps.append(sp)
        else:
            if sp is not None:
                roi_sum -= 1.0
                sps.append(sp)

    with_result = len([r for r in rows if r.get("_pos")])
    sr = wins / with_result if with_result else 0.0
    place_rate = places / with_result if with_result else 0.0
    roi = roi_sum / with_result if with_result else 0.0
    avg_sp = sum(sps) / len(sps) if sps else 0.0

    return {
        "n": total,
        "with_result": with_result,
        "wins": wins,
        "places": places,
        "sr": round(sr, 4),
        "place_rate": round(place_rate, 4),
        "roi": round(roi, 4),
        "avg_sp": round(avg_sp, 2),
        "vp30_overlap_n": vp30_overlap,
        "vp30_overlap_pct": round(vp30_overlap / total, 4) if total else 0.0,
        "mds_overlap_n": mds_overlap,
        "mds_overlap_pct": round(mds_overlap / total, 4) if total else 0.0,
    }


def _verdict(bucket: str, stats: dict) -> str:
    n = stats["with_result"]
    if n < 20:
        return "INSUFFICIENT_SAMPLE"
    sr = stats["sr"]
    roi = stats["roi"]
    if roi > 0.05 and sr >= 0.20:
        return "BOOSTER_CANDIDATE"
    if roi >= 0 and sr >= 0.15:
        return "FILTER_WATCHLIST"
    if roi < 0 and bucket == "CASHRUN_READY":
        return "SUPPRESS_REVIEW_REQUIRED"
    return "EVIDENCE_BUILDING"


def run_cashrun_activation_audit() -> dict[str, Any]:
    print("Loading results index...")
    results_idx = _load_results()
    print(f"  Dates with results: {len(results_idx)}")

    print("Loading cashrun rows...")
    rows = _load_cashrun_rows()
    print(f"  Total rows: {len(rows)}")

    # Attach result to each row
    matched = unmatched = 0
    for row in rows:
        date = row.get("date", "")
        race_id = row.get("race_id", "")
        horse = _norm_name(row.get("horse", ""))
        result = results_idx.get(date, {}).get(race_id, {}).get(horse)
        if result:
            row["_pos"] = result["pos"]
            row["_sp_dec"] = result["sp_dec"]
            matched += 1
        else:
            row["_pos"] = ""
            row["_sp_dec"] = None
            unmatched += 1

    print(f"  Matched: {matched} / {len(rows)} ({unmatched} unmatched)")

    # Group by cashrun_class
    buckets: dict[str, list] = defaultdict(list)
    for row in rows:
        cls = row.get("cashrun_class", "UNKNOWN")
        buckets[cls].append(row)

    bucket_order = ["CASHRUN_READY", "CASHRUN_WATCH", "WEAK_SIGNAL", "SUPPRESS"]
    results_out: dict[str, Any] = {}
    for bucket in bucket_order:
        bucket_rows = buckets.get(bucket, [])
        stats = _bucket_stats(bucket_rows)
        stats["verdict"] = _verdict(bucket, stats)
        results_out[bucket] = stats

    # VP30 overlap analysis across all buckets
    def _is_vp30(r: dict) -> bool:
        return str(r.get("vp30_overlap", "")).strip() in {"True", "true", "1", "yes"}

    vp30_all = [r for r in rows if _is_vp30(r)]
    vp30_watch = [r for r in vp30_all if r.get("cashrun_class") == "CASHRUN_WATCH"]
    vp30_weak = [r for r in vp30_all if r.get("cashrun_class") == "WEAK_SIGNAL"]
    vp30_suppress = [r for r in vp30_all if r.get("cashrun_class") == "SUPPRESS"]
    vp30_stats = _bucket_stats(vp30_all)
    conv_stats = _bucket_stats(vp30_watch)

    # Date range
    dates = sorted({r.get("date", "") for r in rows if r.get("date")})

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_version": "CASHRUN_ACTIVATION_AUDIT_V1",
        "date_range": {"from": dates[0] if dates else None, "to": dates[-1] if dates else None},
        "total_rows": len(rows),
        "matched_rows": matched,
        "unmatched_rows": unmatched,
        "buckets": results_out,
        "crossover_analysis": {
            "cashrun_watch_plus_vp30": conv_stats,
            "cashrun_weak_plus_vp30": _bucket_stats(vp30_weak),
            "cashrun_suppress_plus_vp30": _bucket_stats(vp30_suppress),
            "any_cashrun_plus_vp30": vp30_stats,
        },
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "cashrun_activation_audit_latest.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Write markdown report
    md_lines = [
        "# CASHRUN Activation Audit",
        "",
        f"**Generated:** {payload['generated_at']}",
        f"**Date range:** {dates[0] if dates else '?'} → {dates[-1] if dates else '?'}",
        f"**Total rows:** {len(rows)} | **Matched to results:** {matched}",
        "",
        "## Bucket Performance",
        "",
        "| Bucket | n | Results | SR | Place% | ROI | Avg SP | VP30% | Verdict |",
        "|--------|---|---------|-----|--------|-----|--------|-------|---------|",
    ]
    for bucket in bucket_order:
        s = results_out.get(bucket, {})
        md_lines.append(
            f"| {bucket} | {s.get('n',0)} | {s.get('with_result',0)} | "
            f"{s.get('sr',0):.1%} | {s.get('place_rate',0):.1%} | "
            f"{s.get('roi',0):+.3f} | {s.get('avg_sp',0):.1f} | "
            f"{s.get('vp30_overlap_pct',0):.1%} | {s.get('verdict','—')} |"
        )
    md_lines += [
        "",
        "## Crossover Analysis",
        "",
        "| Signal | n | Results | SR | Place% | ROI |",
        "|--------|---|---------|-----|--------|-----|",
    ]
    for label, s in [
        ("WATCH + VP30", conv_stats),
        ("WEAK + VP30", _bucket_stats(vp30_weak)),
        ("SUPPRESS + VP30", _bucket_stats(vp30_suppress)),
        ("Any + VP30", vp30_stats),
    ]:
        md_lines.append(
            f"| {label} | {s.get('n',0)} | {s.get('with_result',0)} | "
            f"{s.get('sr',0):.1%} | {s.get('place_rate',0):.1%} | "
            f"{s.get('roi',0):+.3f} |"
        )
    md_lines += [
        "",
        "## Verdict Key",
        "- `BOOSTER_CANDIDATE` — ROI >5% at n≥20, consider signal weighting",
        "- `FILTER_WATCHLIST` — Positive direction, accumulate more evidence",
        "- `EVIDENCE_BUILDING` — n<20 or mixed signal, continue accumulation",
        "- `SUPPRESS_REVIEW_REQUIRED` — Negative ROI at n≥20, review scoring rules",
        "- `INSUFFICIENT_SAMPLE` — n<20 results, no conclusion possible",
        "",
        "**No live weighting applied. Evidence accumulation only.**",
    ]
    md_path = REPORTS_DIR / "cashrun_activation_audit_latest.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return payload


def main() -> None:
    payload = run_cashrun_activation_audit()
    buckets = payload["buckets"]
    print()
    print("CASHRUN ACTIVATION AUDIT")
    print("=" * 60)
    for bucket in ["CASHRUN_READY", "CASHRUN_WATCH", "WEAK_SIGNAL", "SUPPRESS"]:
        s = buckets.get(bucket, {})
        print(
            f"  {bucket:<18} n={s.get('n',0):>4}  results={s.get('with_result',0):>4}"
            f"  SR={s.get('sr',0):.1%}  Place={s.get('place_rate',0):.1%}"
            f"  ROI={s.get('roi',0):+.3f}  AvgSP={s.get('avg_sp',0):.1f}"
            f"  → {s.get('verdict','—')}"
        )
    print()
    cx = payload["crossover_analysis"]
    for label, key in [
        ("WATCH+VP30", "cashrun_watch_plus_vp30"),
        ("WEAK+VP30", "cashrun_weak_plus_vp30"),
        ("SUPPRESS+VP30", "cashrun_suppress_plus_vp30"),
        ("Any+VP30", "any_cashrun_plus_vp30"),
    ]:
        s = cx[key]
        print(
            f"  {label:<18} n={s.get('n',0):>4}  results={s.get('with_result',0):>4}"
            f"  SR={s.get('sr',0):.1%}  ROI={s.get('roi',0):+.3f}"
        )
    print()
    print(f"  Output: data/reports/cashrun_activation_audit_latest.json")
    print(f"  Output: data/reports/cashrun_activation_audit_latest.md")


if __name__ == "__main__":
    main()
