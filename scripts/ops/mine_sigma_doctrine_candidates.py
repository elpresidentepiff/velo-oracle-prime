"""
Mine shadow-only Sigma doctrine candidates.

This script aggregates recurring retrieval-state patterns from the Sigma corpus.
It writes review reports only and never promotes doctrine or changes scoring.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.sigma_retrieval import load_jsonl, mine_doctrine_candidates, render_doctrine_miner_md


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine shadow-only Sigma doctrine candidates")
    parser.add_argument(
        "--corpus",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_retrieval_corpus_v1.jsonl"),
        help="Sigma retrieval corpus JSONL",
    )
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_doctrine_candidates_latest.json"),
        help="Output JSON report",
    )
    parser.add_argument(
        "--output-md",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_doctrine_candidates_latest.md"),
        help="Output Markdown report",
    )
    parser.add_argument("--min-support", type=int, default=30, help="Minimum support for a candidate")
    parser.add_argument("--max-dims", type=int, default=3, help="Maximum dimensions per mined pattern")
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        default=False,
        help="Disable parsimonious dedupe of statistically identical supersets",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus = load_jsonl(Path(args.corpus))
    report = mine_doctrine_candidates(
        corpus,
        min_support=args.min_support,
        max_dims=args.max_dims,
        dedupe_parsimonious=not args.no_dedupe,
    )

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    output_md.write_text(render_doctrine_miner_md(report), encoding="utf-8")

    print(
        f"DOCTRINE_MINER_CANDIDATE_ONLY PASS candidates={report['candidate_count']} "
        f"eligible={report['eligible_records']} min_support={report['min_support']} "
        f"deduped={report['deduped_candidate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
