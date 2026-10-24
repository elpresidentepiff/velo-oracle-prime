"""CLI for the read-only historical crosswalk and Evo² replay."""

from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from src.intelligence.challenger_lab import evaluate_market_value
from src.intelligence.challenger_policy_replay import audit_midprice_actions, audit_new_build
from src.intelligence.challenger_research_cycle import propose_calibration_review, reflect
from src.intelligence.historical_runner_crosswalk import (
    PROBABILITY_FIELDS,
    SourceBundle,
    build_crosswalk,
    canonical_sha256,
    frozen_holdout,
    frozen_model_holdout,
)

TABLE_SELECTS = {
    "runner_prediction_snapshots": "*",
    "velo_verdicts": "id,race_id,generated_at,git_commit_sha,full_analysis",
    "canonical_model_scorecards": (
        "run_date,race_id,course,off_time,model_name,lane_name,rank,horse,horse_id,score,"
        "result_position,win,frame,subject_is_non_runner,settlement_status,result_source_hash,"
        "result_source_complete,official_evaluation_eligible,evaluation_ineligible_reason,created_at"
    ),
    "velo_race_truth": (
        "race_id,race_date,course,off_time,predicted_runner_id,velo_prime_prob,scored_at,"
        "result_outcome,finish_pos,actual_winner_id,winner_name,reconciled_date,"
        "outcome_missing,verdict_generated_at,sigma_reconciled_at"
    ),
}


class ReadOnlyPostgrest:
    """Minimal allowlisted PostgREST reader; the only HTTP verb is GET."""

    def __init__(self, url: str, key: str, *, page_size: int = 1000) -> None:
        if not url.startswith("https://"):
            raise ValueError("SUPABASE_URL must use https")
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = key
        self.page_size = page_size

    def fetch(self, table: str) -> list[dict[str, Any]]:
        if table not in TABLE_SELECTS:
            raise ValueError(f"table not allowlisted: {table}")
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            query = urlencode({"select": TABLE_SELECTS[table]})
            request = Request(
                f"{self.base}/{table}?{query}",
                method="GET",
                headers={
                    "apikey": self.key,
                    "Authorization": f"Bearer {self.key}",
                    "Range": f"{offset}-{offset + self.page_size - 1}",
                    "Accept": "application/json",
                },
            )
            with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS Supabase origin
                batch = json.loads(response.read().decode("utf-8"))
            if not isinstance(batch, list):
                raise RuntimeError(f"unexpected response for {table}")
            rows.extend(batch)
            if len(batch) < self.page_size:
                return rows
            offset += self.page_size


def _bundle_from_dict(payload: dict[str, Any]) -> SourceBundle:
    missing = [name for name in TABLE_SELECTS if not isinstance(payload.get(name), list)]
    if missing:
        raise ValueError(f"source export missing list(s): {', '.join(missing)}")
    return SourceBundle(**{name: payload[name] for name in TABLE_SELECTS})


def _load_bundle(args: argparse.Namespace) -> SourceBundle:
    if args.source_export:
        bundle = _bundle_from_dict(json.loads(args.source_export.read_text(encoding="utf-8")))
    else:
        if args.env_file:
            load_dotenv(args.env_file, override=False)
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise SystemExit("read-only Supabase URL/key environment variables are required")
        reader = ReadOnlyPostgrest(url, key)
        source_payload = {table: reader.fetch(table) for table in TABLE_SELECTS}
        if args.source_cache:
            args.source_cache.parent.mkdir(parents=True, exist_ok=True)
            args.source_cache.write_text(json.dumps(source_payload, ensure_ascii=False) + "\n", encoding="utf-8")
        bundle = SourceBundle(**source_payload)

    if args.snapshot_jsonl_dir:
        rows: list[dict[str, Any]] = []
        file_hashes: dict[str, str] = {}
        for path in sorted(args.snapshot_jsonl_dir.glob("runner_snapshots_*.jsonl")):
            raw = path.read_bytes()
            file_hashes[path.name] = sha256(raw).hexdigest()
            for line_number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"non-object JSONL row: {path.name}:{line_number}")
                rows.append(row)
        bundle = replace(
            bundle,
            local_runner_prediction_snapshots=rows,
            local_snapshot_file_hashes=file_hashes,
        )
    return bundle


def run(args: argparse.Namespace) -> dict[str, Any]:
    bundle = _load_bundle(args)
    report = build_crosswalk(bundle)
    observations, manifest = frozen_holdout(report, holdout_start=args.holdout_start, holdout_end=args.holdout_end)
    proposal = propose_calibration_review(baseline_ref=args.baseline_ref)
    replay: dict[str, Any] = {
        "proposal": asdict(proposal),
        "manifest": manifest,
        "executable": len(observations) >= args.min_runners,
        "minimum_runner_count": args.min_runners,
    }
    if replay["executable"]:
        replay["result"] = reflect(proposal, observations, min_runners=args.min_runners)
    else:
        replay["blocker"] = "INSUFFICIENT_COMPLETE_VERIFIED_RUNNERS"

    model_replays: dict[str, Any] = {}
    min_market_races = getattr(args, "min_market_races", 30)
    for probability_field in PROBABILITY_FIELDS:
        model_observations, _, model_manifest = frozen_model_holdout(
            report,
            challenger_field=probability_field,
            holdout_start=args.holdout_start,
            holdout_end=args.holdout_end,
        )
        market_rows, market_observations, market_manifest = frozen_model_holdout(
            report,
            challenger_field=probability_field,
            holdout_start=args.holdout_start,
            holdout_end=args.holdout_end,
            require_market_price=True,
        )
        model_proposal = propose_calibration_review(baseline_ref=f"{args.baseline_ref}:{probability_field}")
        entry: dict[str, Any] = {
            "manifest": model_manifest,
            "executable": len(model_observations) >= args.min_runners,
            "minimum_runner_count": args.min_runners,
            "market_manifest": market_manifest,
            "market_executable": (
                len({row.race_id for row in market_rows}) >= min_market_races
                and len(market_observations) == len(market_rows)
            ),
            "minimum_market_race_count": min_market_races,
        }
        if entry["executable"]:
            entry["result"] = reflect(model_proposal, model_observations, min_runners=args.min_runners)
        else:
            entry["blocker"] = "INSUFFICIENT_COMPLETE_VERIFIED_RUNNERS"
        if entry["market_executable"]:
            entry["market_result"] = evaluate_market_value(market_observations, min_races=min_market_races)
        else:
            entry["market_blocker"] = "INSUFFICIENT_COMPLETE_PRE_RACE_PRICE_COHORT"
        model_replays[probability_field] = entry

    # Optional offline policy artifacts; no assumptions about unavailable lane files.
    policy_replays: dict[str, Any] = {}
    readiness_dir = getattr(args, "new_build_readiness_dir", None)
    if readiness_dir is not None:
        paths = sorted(readiness_dir.glob("two_lane_readiness_*.json"))
        readiness = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        policy_replays["new_build"] = audit_new_build(readiness, report)
        policy_replays["new_build"]["input_files_sha256"] = {
            path.name: sha256(path.read_bytes()).hexdigest() for path in paths
        }
    ledger_path = getattr(args, "midprice_ledger_csv", None)
    if ledger_path is not None:
        with ledger_path.open(encoding="utf-8", newline="") as stream:
            entries = list(csv.DictReader(stream))
        for entry in entries:
            for field_name in ("execution_allowed", "live_scoring_changed"):
                raw = str(entry.get(field_name) or "").strip().lower()
                entry[field_name] = {"true": True, "false": False}.get(raw)
        policy_replays["midprice"] = audit_midprice_actions(entries, report)
        policy_replays["midprice"]["source_file_sha256"] = sha256(ledger_path.read_bytes()).hexdigest()

    output = report.to_dict()
    output["evo2_policy_replays"] = policy_replays
    output["evo2_replay"] = replay
    output["evo2_model_replays"] = model_replays
    output["requested_model_evidence_gaps"] = {
        "mds_heavy": "NO_CAPTURED_RUNNER_WIN_PROBABILITY_CROSSWALKED",
        "calibrated_g": "NO_CAPTURED_RUNNER_WIN_PROBABILITY_CROSSWALKED",
        "passport_strength": "NO_CAPTURED_RUNNER_WIN_PROBABILITY_CROSSWALKED",
        "new_build_lane_a": "SEPARATE_HISTORICAL_ARTIFACT_NOT_YET_CROSSWALKED",
        "new_build_lane_b": "SEPARATE_HISTORICAL_ARTIFACT_NOT_YET_CROSSWALKED",
        "mid_price_hunter": "CAPTURED_ACTION_IS_NOT_A_RUNNER_WIN_PROBABILITY",
    }
    output["artifact_sha256"] = canonical_sha256(output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-export", type=Path)
    source.add_argument("--supabase-readonly", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--source-cache", type=Path)
    parser.add_argument("--snapshot-jsonl-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--holdout-start", required=True)
    parser.add_argument("--holdout-end")
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--min-runners", type=int, default=300)
    parser.add_argument("--min-market-races", type=int, default=30)
    parser.add_argument("--new-build-readiness-dir", type=Path)
    parser.add_argument("--midprice-ledger-csv", type=Path)
    args = parser.parse_args()
    payload = run(args)
    summary = {
        "output": str(args.output),
        "artifact_sha256": payload["artifact_sha256"],
        "source_counts": payload["source_counts"],
        "evo2_replay": payload["evo2_replay"],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
