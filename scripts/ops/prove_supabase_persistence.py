#!/usr/bin/env python3
"""
Supabase Persistence Proof — READ-ONLY
=======================================
Independently proves (or disproves) that a scoring day landed in Supabase.
Replaces "the run said it persisted" with an out-of-process read-back.

ONE_TRUTH law 2026-06-10: Supabase is connected and must be verified,
not assumed.

Usage:
    PYTHONPATH=. python scripts/ops/prove_supabase_persistence.py --date YYYY-MM-DD

Outputs:
    data/reports/supabase_persistence_proof_{date}.json
    data/reports/supabase_persistence_proof_{date}.md

Hard constraints:
  - GET requests only. No INSERT/UPDATE/DELETE/RPC. Ever.
  - No scoring imports. No model loads.
  - Exit 0 = proof PASS, exit 1 = proof FAIL, exit 2 = could not check.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> dict:
    env: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class SupabaseReader:
    """GET-only REST reader. Refuses to exist in any other form."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    def get(self, path: str, extra_headers: dict | None = None) -> tuple[int | None, dict, str]:
        h = dict(self.headers)
        if extra_headers:
            h.update(extra_headers)
        req = urllib.request.Request(f"{self.url}/rest/v1/{path}", headers=h, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, dict(resp.headers), resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode()[:300]
        except Exception as e:  # network/timeout
            return None, {}, str(e)[:300]

    def count(self, table: str, filt: str = "") -> int | None:
        q = f"{table}?select=id&limit=1" + (f"&{filt}" if filt else "")
        status, headers, _ = self.get(q, {"Prefer": "count=exact", "Range": "0-0"})
        if status in (200, 206):
            cr = headers.get("Content-Range") or headers.get("content-range", "")
            try:
                return int(cr.split("/")[-1])
            except ValueError:
                return None
        return None

    def rows(self, path: str) -> list | None:
        status, _, body = self.get(path)
        if status == 200:
            try:
                return json.loads(body)
            except Exception:
                return None
        return None


def build_proof(date_str: str) -> dict:
    env = _load_env()
    url = env.get("SUPABASE_URL") or (
        f"https://{env['SUPABASE_PROJECT_ID']}.supabase.co" if env.get("SUPABASE_PROJECT_ID") else ""
    )
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_KEY") or ""
    proof: dict = {
        "date": date_str,
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only_confirmed": True,
        "checks": {},
        "gaps": [],
        "status": "UNCHECKED",
    }
    if not url or not key:
        proof["status"] = "CANNOT_CHECK_NO_CREDENTIALS"
        return proof

    sb = SupabaseReader(url, key)
    day_filter = f"generated_at=gte.{date_str}T00:00:00&generated_at=lt.{date_str}T23:59:59"
    c = proof["checks"]

    c["verdict_count"] = sb.count("velo_verdicts", day_filter)
    c["null_decision_tier"] = sb.count("velo_verdicts", f"{day_filter}&decision_tier=is.null")
    c["null_git_commit_sha"] = sb.count("velo_verdicts", f"{day_filter}&git_commit_sha=is.null")
    c["rpdc_primary_tag_present"] = sb.count("velo_verdicts", f"{day_filter}&rpdc_primary_tag=not.is.null")
    c["active_components_present"] = sb.count("velo_verdicts", f"{day_filter}&active_components=not.is.null")
    c["rpdc_candidates_for_date"] = sb.count("runner_release_candidates", f"run_date=eq.{date_str}")

    latest = sb.rows("velo_verdicts?select=generated_at,git_commit_sha,engine_version&order=generated_at.desc&limit=1")
    c["latest_verdict"] = latest[0] if latest else None

    sample = sb.rows(
        "velo_verdicts?select=race_id,decision_tier,active_components,excluded_from_ensemble,"
        f"rpdc_primary_tag,rpdc_tag_count&{day_filter}&limit=3"
    )
    c["sample"] = sample or []

    # Schema truth — columns the operator wants on-row but that may not exist yet.
    missing_cols = []
    for col in ("source_truth", "feature_degraded"):
        status, _, body = sb.get(f"velo_verdicts?select={col}&limit=1")
        if status == 400:
            missing_cols.append(col)
    c["schema_missing_columns"] = missing_cols

    # Expected race count from the local injection/backup, if available.
    expected = None
    local_backup = ROOT / "data" / f"velo_prime_verdicts_{date_str.replace('-', '_')}.json"
    local_rpdc_attached = None
    if local_backup.exists():
        try:
            races = json.loads(local_backup.read_text())
            races = races if isinstance(races, list) else races.get("races", [])
            expected = len(races)
            local_rpdc_attached = sum(
                1 for r in races if (r.get("top") or {}).get("rpdc_lookup_status") == "attached"
            )
        except Exception:
            pass
    c["expected_race_count_local_backup"] = expected
    c["local_backup_rpdc_attached"] = local_rpdc_attached

    # ── Verdict ───────────────────────────────────────────────────────────
    vc = c["verdict_count"]
    if vc is None:
        proof["status"] = "CANNOT_CHECK_QUERY_FAILED"
        return proof
    if vc == 0:
        proof["gaps"].append("NO_VERDICTS_FOR_DATE")
    if expected is not None and vc != expected:
        proof["gaps"].append(f"COUNT_MISMATCH local={expected} supabase={vc}")
    if c["null_decision_tier"]:
        proof["gaps"].append(f"NULL_DECISION_TIER={c['null_decision_tier']}")
    if c["null_git_commit_sha"]:
        proof["gaps"].append(f"NULL_GIT_COMMIT_SHA={c['null_git_commit_sha']}")
    if (
        local_rpdc_attached
        and c["rpdc_primary_tag_present"] is not None
        and c["rpdc_primary_tag_present"] == 0
    ):
        proof["gaps"].append(
            f"RPDC_PERSIST_GAP local_attached={local_rpdc_attached} supabase_tagged=0"
        )
    if missing_cols:
        proof["gaps"].append(f"SCHEMA_MISSING={','.join(missing_cols)} (migration pending)")

    hard_gaps = [g for g in proof["gaps"] if not g.startswith("SCHEMA_MISSING")]
    proof["status"] = "PASS" if (vc > 0 and not hard_gaps) else "FAIL"
    return proof


def write_reports(proof: dict) -> Path:
    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    date_str = proof["date"]
    json_path = out_dir / f"supabase_persistence_proof_{date_str}.json"
    json_path.write_text(json.dumps(proof, indent=2))
    # Loop 4 status artifact — consumed by check_loop_health.py (loop registry L4)
    current_dir = ROOT / "data" / "current"
    current_dir.mkdir(parents=True, exist_ok=True)
    (current_dir / "persistence_proof_latest.json").write_text(json.dumps(proof, indent=2))
    c = proof["checks"]
    md = [
        f"# Supabase Persistence Proof — {date_str}",
        "",
        f"**Status:** {proof['status']}  ·  Generated {proof['generated_at']}  ·  READ-ONLY",
        "",
        "| Check | Value |",
        "|---|---|",
        f"| Verdicts persisted | {c.get('verdict_count')} |",
        f"| Expected (local backup) | {c.get('expected_race_count_local_backup')} |",
        f"| Null decision_tier | {c.get('null_decision_tier')} |",
        f"| Null git_commit_sha | {c.get('null_git_commit_sha')} |",
        f"| RPDC primary tag present | {c.get('rpdc_primary_tag_present')} |",
        f"| Local backup RPDC attached | {c.get('local_backup_rpdc_attached')} |",
        f"| active_components present | {c.get('active_components_present')} |",
        f"| RPDC candidate rows (date) | {c.get('rpdc_candidates_for_date')} |",
        f"| Missing schema columns | {', '.join(c.get('schema_missing_columns') or []) or 'none'} |",
        "",
        "## Gaps",
        *([f"- {g}" for g in proof["gaps"]] or ["- none"]),
    ]
    (out_dir / f"supabase_persistence_proof_{date_str}.md").write_text("\n".join(md))
    return json_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    proof = build_proof(args.date)
    path = write_reports(proof)
    print(f"Supabase persistence proof: {proof['status']}")
    for gap in proof["gaps"]:
        print(f"  GAP: {gap}")
    print(f"  -> {path}")
    if proof["status"] == "PASS":
        return 0
    if proof["status"].startswith("CANNOT_CHECK"):
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
