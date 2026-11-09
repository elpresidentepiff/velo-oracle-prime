#!/usr/bin/env python3
"""Read-only audit of persisted Rich Context packet wiring for one race day."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.velo.rich_context_challenger_features_v2 import APPROVED_FAMILIES, FEATURE_SCHEMA_HASH


def audit_packets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = Counter()
    schema_mismatch = 0
    vector_missing = 0
    fully_enriched = 0
    provider_prediction_consumed = 0
    production_influence = 0
    for row in rows:
        families = row.get("families") or {}
        for family in APPROVED_FAMILIES:
            if families.get(family):
                coverage[family] += 1
        contract = row.get("enriched_feature_contract") or {}
        schema_mismatch += int(contract.get("feature_schema_hash") != FEATURE_SCHEMA_HASH)
        vector_missing += int(not contract.get("vector"))
        fully_enriched += int(contract.get("fully_enriched") is True)
        provider_prediction_consumed += int(row.get("provider_predictions_consumed") is not False)
        production_influence += int(row.get("production_influence") is not False)
    count = len(rows)
    return {
        "packet_count": count,
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "family_coverage": {
            family: {"present": coverage[family], "pct": round(100 * coverage[family] / count, 2) if count else 0.0}
            for family in APPROVED_FAMILIES
        },
        "fully_enriched_packets": fully_enriched,
        "schema_mismatch_packets": schema_mismatch,
        "missing_vector_packets": vector_missing,
        "provider_prediction_contract_violations": provider_prediction_consumed,
        "production_influence_contract_violations": production_influence,
        "wiring_pass": bool(count) and schema_mismatch == vector_missing == provider_prediction_consumed == production_influence == 0,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet_jsonl", type=Path)
    args = parser.parse_args()
    report = audit_packets(_read_jsonl(args.packet_jsonl))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["wiring_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
