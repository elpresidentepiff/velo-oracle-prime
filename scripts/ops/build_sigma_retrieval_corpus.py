"""
Build the shadow-only Sigma Retrieval Corpus V1.

This standardises old VÉLØ sigma memory into discrete, regime-aware records for
future KNN/Bayesian retrieval. It is report/output only and has no live scoring
impact.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.sigma_retrieval import BuildPaths, build_sigma_retrieval_corpus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shadow-only sigma retrieval corpus")
    parser.add_argument(
        "--sigma-dump",
        default=str(ROOT / "data" / "sigma_audits_dump.json"),
        help="Path to old VÉLØ sigma audit dump JSON",
    )
    parser.add_argument(
        "--output-jsonl",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_retrieval_corpus_v1.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument(
        "--report-json",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_retrieval_corpus_v1_report.json"),
        help="Output report JSON path",
    )
    parser.add_argument(
        "--report-md",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_retrieval_corpus_v1_report.md"),
        help="Output report Markdown path",
    )
    parser.add_argument(
        "--require-through-date",
        default=None,
        help="Fail if the built corpus date_max is earlier than YYYY-MM-DD.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = BuildPaths(
        root=ROOT,
        sigma_dump=Path(args.sigma_dump),
        output_jsonl=Path(args.output_jsonl),
        report_json=Path(args.report_json),
        report_md=Path(args.report_md),
    )
    report = build_sigma_retrieval_corpus(paths)
    if args.require_through_date:
        report["required_through_date"] = args.require_through_date
        report["freshness_gate_passed"] = bool(
            report.get("date_max") and report["date_max"] >= args.require_through_date
        )
        paths.report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        if not report["freshness_gate_passed"]:
            print(json.dumps(report, indent=2, ensure_ascii=False))
            print(
                "SIGMA_RETRIEVAL_FRESHNESS_BLOCKED: "
                f"date_max={report.get('date_max')} required={args.require_through_date}"
            )
            return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
