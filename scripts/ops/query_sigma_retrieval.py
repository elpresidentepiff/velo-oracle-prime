"""
Query the shadow-only Sigma Retrieval Corpus V1.

Examples:
python scripts/ops/query_sigma_retrieval.py --query-json '{"vp_band":"P30_40","mds_band":"P20_30"}'
python scripts/ops/query_sigma_retrieval.py --query-file data/sigma_memory/query.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.sigma_retrieval import build_evidence_explanation, load_jsonl, retrieve_sigma_neighbors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query shadow-only sigma KNN corpus")
    parser.add_argument(
        "--corpus",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_retrieval_corpus_v1.jsonl"),
        help="Sigma retrieval corpus JSONL",
    )
    parser.add_argument(
        "--query-json",
        default=None,
        help="JSON object containing retrieval_state_vector fields",
    )
    parser.add_argument("--query-file", default=None, help="Path to JSON object containing retrieval_state_vector fields")
    parser.add_argument("--query-date", default=None, help="Optional YYYY-MM-DD date for recency weighting")
    parser.add_argument("--k", type=int, default=50, help="Number of neighbors")
    parser.add_argument(
        "--min-weight-coverage",
        type=float,
        default=0.25,
        help="Minimum fraction of weighted dimensions that must be comparable",
    )
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "data" / "sigma_memory" / "sigma_knn_query_latest.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        default=False,
        help="Print the evidence explanation narrative instead of raw KNN JSON",
    )
    parser.add_argument(
        "--race-context-json",
        default=None,
        help="Optional JSON object with race context (course, date, horse, etc.) for explanation header",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.query_file:
        try:
            query_vector = json.loads(Path(args.query_file).read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --query-file JSON: {exc}") from exc
    elif args.query_json:
        try:
            query_vector = json.loads(args.query_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --query-json: {exc}") from exc
    else:
        raise SystemExit("Pass either --query-json or --query-file")
    if not isinstance(query_vector, dict):
        raise SystemExit("--query-json must decode to an object")

    race_context = None
    if args.race_context_json:
        try:
            race_context = json.loads(args.race_context_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --race-context-json: {exc}") from exc

    corpus = load_jsonl(Path(args.corpus))
    result = retrieve_sigma_neighbors(
        query_vector,
        corpus,
        query_date=args.query_date,
        k=args.k,
        min_weight_coverage=args.min_weight_coverage,
    )
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.explain:
        explanation = build_evidence_explanation(result, race_context=race_context)
        expl_path = output_path.with_name(output_path.stem + "_explanation.json")
        expl_path.write_text(json.dumps(explanation, indent=2, ensure_ascii=False), encoding="utf-8")
        print(explanation["narrative_md"])
        print(f"\nClassification: {explanation['classification']}")
        print(f"Saved: {expl_path}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
