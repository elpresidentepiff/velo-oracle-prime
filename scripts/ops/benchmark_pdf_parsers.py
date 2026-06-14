#!/usr/bin/env python3
"""
PDF Parser Benchmark — current vs LiteParse vs null control
=============================================================
Ground truth: the racecard injection JSON of the same date (real runner
names per course from the HTML path). A parser is only as good as its
runner-name recall on the documents that broke VÉLØ before.

Usage:
    PYTHONPATH=. python scripts/ops/benchmark_pdf_parsers.py \
        --pdf-dir incoming/2026-06-09-pdfs --date 2026-06-09

Outputs:
    data/current/pdf_parser_benchmark_latest.json
    data/reports/pdf_parser_benchmark_latest.md
Read-only except its two outputs. No scoring integration.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.velo.parsing.pdf_parser_adapter import ADAPTERS  # noqa: E402

VENUE_MAP = {"BRI": "brighton", "CRL": "carlisle", "SAL": "salisbury", "SLI": "sligo", "STH": "southwell"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_ground_truth(date_str: str) -> dict[str, set[str]]:
    """course(lower) -> set of normalized runner names from injection JSON."""
    out: dict[str, set[str]] = {}
    for inj in sorted((ROOT / "data" / "racing_post_account_parsed").glob(f"*{date_str}*/racecard_injection.json")):
        races = json.loads(inj.read_text())
        races = races.get("races", races if isinstance(races, list) else [])
        for r in races:
            course = (r.get("course") or "").lower().split(" (")[0]
            names = out.setdefault(course, set())
            for h in r.get("runners", []) or r.get("horses", []):
                n = _norm(h.get("horse") or h.get("horse_name") or "")
                if n:
                    names.add(n)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    truth = load_ground_truth(args.date)
    pdfs = sorted(glob.glob(str(ROOT / args.pdf_dir / "*.pdf")))
    if args.limit:
        pdfs = pdfs[: args.limit]

    results = {name: {"docs": 0, "parse_ok": 0, "runtime_total": 0.0, "pages": 0,
                      "names_expected": 0, "names_found": 0, "race_times_found": 0,
                      "failures": []} for name in ("current", "liteparse", "null")}
    per_doc = []

    adapters = {k: cls() for k, cls in ADAPTERS.items()}
    for pdf in pdfs:
        p = Path(pdf)
        venue_code = p.name[:3]
        course = VENUE_MAP.get(venue_code, "")
        expected = truth.get(course, set())
        doc_row = {"file": p.name, "course": course, "expected_names": len(expected)}
        for name, adapter in adapters.items():
            r = adapter.parse(p)
            agg = results[name]
            agg["docs"] += 1
            agg["runtime_total"] += r["runtime_sec"]
            agg["pages"] += r["page_count"]
            ok = bool(r["text"]) and not any("failed" in w for w in r["warnings"])
            if ok:
                agg["parse_ok"] += 1
            else:
                if r["warnings"]:
                    agg["failures"].append({"file": p.name, "warnings": r["warnings"][:2]})
            norm_text = _norm(r["text"])
            found = sum(1 for n in expected if n and n in norm_text)
            agg["names_expected"] += len(expected)
            agg["names_found"] += found
            agg["race_times_found"] += len(set(re.findall(r"\b\d{1,2}\.\d{2}\b", r["text"])))
            doc_row[name] = {"ok": ok, "runtime": r["runtime_sec"], "name_recall": f"{found}/{len(expected)}"}
        per_doc.append(doc_row)

    for name, agg in results.items():
        agg["parse_success_rate"] = round(agg["parse_ok"] / max(agg["docs"], 1), 3)
        agg["avg_runtime_sec"] = round(agg["runtime_total"] / max(agg["docs"], 1), 2)
        agg["name_recall"] = round(agg["names_found"] / max(agg["names_expected"], 1), 4)

    out = {
        "generated_at": datetime.now(UTC).isoformat(),
        "date": args.date,
        "pdf_dir": args.pdf_dir,
        "docs": len(pdfs),
        "ground_truth_courses": {k: len(v) for k, v in truth.items()},
        "summary": results,
        "per_doc": per_doc,
        "read_only_confirmed": True,
    }
    (ROOT / "data/current/pdf_parser_benchmark_latest.json").write_text(json.dumps(out, indent=2))
    lines = [f"# PDF Parser Benchmark — {args.date} ({len(pdfs)} docs)", "",
             "| Parser | success | name recall | avg runtime | race-times found |",
             "|---|---|---|---|---|"]
    for name, agg in results.items():
        lines.append(f"| {name} | {agg['parse_success_rate']:.0%} | {agg['name_recall']:.1%} "
                     f"({agg['names_found']}/{agg['names_expected']}) | {agg['avg_runtime_sec']}s | {agg['race_times_found']} |")
    (ROOT / "data/reports/pdf_parser_benchmark_latest.md").write_text("\n".join(lines))
    print(json.dumps({k: {x: v[x] for x in ("parse_success_rate", "name_recall", "avg_runtime_sec")} for k, v in results.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
