"""Read-only completeness and paired-model coverage audit on exported scorecard JSON.

No database connection, no mutation, no performance promotion. Use an external
read-only export of canonical_model_scorecards for a single date. The score field
is deliberately NOT interpreted as a probability.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path


def audit_scorecard_export(path: Path) -> dict:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("expected JSON array")
    grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    eligible = defaultdict(int)
    rejected = defaultdict(int)
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("all records must be objects")
        model = row.get("model_name")
        race = row.get("race_id")
        horse = row.get("horse_id")
        if not all(isinstance(x, str) and x.strip() for x in (model, race, horse)):
            raise ValueError("model_name, race_id and horse_id required")
        if row.get("official_evaluation_eligible") is True and row.get("result_source_complete") is True:
            eligible[model] += 1
            grouped[model][race].add(horse)
        else:
            rejected[model] += 1
    models = sorted(set(eligible) | set(rejected))
    comparisons = []
    for i, first in enumerate(models):
        for second in models[i + 1:]:
            common = set(grouped[first]) & set(grouped[second])
            full = sorted(r for r in common if grouped[first][r] == grouped[second][r])
            comparisons.append({"model_a": first, "model_b": second,
                                "shared_races": len(common), "identical_runner_cohort_races": len(full)})
    return {"models": {m: {"eligible_rows": eligible[m], "rejected_rows": rejected[m],
                            "eligible_races": len(grouped[m])} for m in models},
            "pair_coverage": comparisons, "performance_verified": False,
            "promotion": "NOT_AUTHORISED"}


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(audit_scorecard_export(args.input), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
