#!/usr/bin/env python3
"""
persist_nightly_learning_events.py

Idempotent upsert of the nightly EOD learning runner's events
(data/nightly_eod_learning_events_YYYY_MM_DD.jsonl) into Supabase
public.velo_learning_events ONLY. Writes nowhere else.

Why: velo_learning_events stopped at 2026-05-22 while the runner kept writing
events to local jsonl every night, so 41 dates of learning existed only on one
laptop (found 2026-09-13).

Mapping (the table's existing conventions):
  event_id           <- idempotency_key            ("919917:2026-06-10")
  target_state_name  <- basename of sentient_state_target, no extension
  consumption_id     <- "{event_id}:{target_state_name}"   (unique key)
  prediction         <- prediction_snapshot
  result             <- result_snapshot + prediction_result + loss_type + confidence_error + market_snapshot
  sidecars           <- learning_mode / permission / hfs flags / sources / source_file
  consumed_shadow    <- the runner's status file for that date reports engine updates applied

Records without an event_type or event_date are partial writes and are skipped.
A date that already has rows in velo_learning_events is skipped unless --force,
because pre-2026-05-23 rows use a different event_id scheme and would duplicate.

Default is --dry-run. --execute is required to write.

Usage:
  PYTHONPATH=. python scripts/ops/persist_nightly_learning_events.py --date 2026-09-11 --execute
  PYTHONPATH=. python scripts/ops/persist_nightly_learning_events.py --all-missing --execute
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLE = "velo_learning_events"


def _env() -> tuple[str, str]:
    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    return url, key


def _count_for_date(date: str) -> int:
    url, key = _env()
    req = urllib.request.Request(
        f"{url}/rest/v1/{TABLE}?select=id&run_date=eq.{date}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact", "Range": "0-0"},
        method="HEAD",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Range"].split("/")[-1])


def _upsert(rows: list[dict]) -> int:
    url, key = _env()
    written = 0
    for i in range(0, len(rows), 200):
        batch = rows[i:i + 200]
        req = urllib.request.Request(
            f"{url}/rest/v1/{TABLE}?on_conflict=consumption_id",
            data=json.dumps(batch).encode(),
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        try:
            urllib.request.urlopen(req, timeout=60)
            written += len(batch)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"UPSERT_FAILED batch {i}: HTTP {e.code} {e.read().decode(errors='replace')[:400]}") from None
    return written


def _target_name(raw: str | None) -> str:
    base = re.split(r"[\\/]", raw or "")[-1]
    return base.rsplit(".", 1)[0] or "unknown_target"


def _applied(date_tag: str) -> bool:
    p = ROOT / "data" / f"nightly_eod_learning_status_{date_tag}.json"
    try:
        s = json.loads(p.read_text())
        return int(s.get("engine_updates_applied_first_run") or 0) > 0
    except Exception:
        return False


def build_rows(date: str) -> tuple[list[dict], dict]:
    tag = date.replace("-", "_")
    path = ROOT / "data" / f"nightly_eod_learning_events_{tag}.jsonl"
    audit = {"date": date, "source": str(path.relative_to(ROOT)), "records": 0, "skipped_partial": 0}
    if not path.exists():
        audit["status"] = "NO_SOURCE_FILE"
        return [], audit
    applied = _applied(tag)
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        audit["records"] += 1
        if not e.get("event_type") or not e.get("event_date"):
            audit["skipped_partial"] += 1
            continue
        pred = e.get("prediction_snapshot") or {}
        target = _target_name(e.get("sentient_state_target"))
        event_id = str(e.get("idempotency_key") or f"{e.get('race_id')}:{e.get('event_date')}")
        cid = f"{event_id}:{target}"
        rows[cid] = {
            "run_date": e["event_date"],
            "race_id": str(e.get("race_id") or ""),
            "horse_id": str(pred.get("horse_id") or ""),
            "event_type": e["event_type"],
            "event_id": event_id,
            "target_state_name": target,
            "consumption_id": cid,
            "prediction": pred,
            "result": {
                "result_snapshot": e.get("result_snapshot"),
                "prediction_result": e.get("prediction_result"),
                "loss_type": e.get("loss_type"),
                "confidence_error": e.get("confidence_error"),
                "market_snapshot": e.get("market_snapshot"),
            },
            "sidecars": {
                "learning_mode": e.get("learning_mode"),
                "learning_permission_reason": e.get("learning_permission_reason"),
                "hfs_training_safe": e.get("hfs_training_safe"),
                "hfs_features_used": e.get("hfs_features_used"),
                "source_prediction": e.get("source_prediction"),
                "source_result": e.get("source_result"),
                "source_file": audit["source"],
                "persisted_by": "persist_nightly_learning_events.py",
            },
            "learning_allowed": bool(e.get("learning_allowed")),
            "missing_hfs_context": not bool(e.get("hfs_features_used")),
            "consumed_shadow": applied,
            "consumed_live": False,
        }
    audit["rows"] = len(rows)
    audit["duplicates_collapsed"] = audit["records"] - audit["skipped_partial"] - len(rows)
    return list(rows.values()), audit


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--date")
    g.add_argument("--all-missing", action="store_true", help="every local jsonl date with 0 rows in the table")
    ap.add_argument("--force", action="store_true", help="write even if the date already has rows")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    if args.all_missing:
        dates = sorted(
            "-".join(re.search(r"(\d{4})_(\d\d)_(\d\d)", f).groups())
            for f in glob.glob(str(ROOT / "data" / "nightly_eod_learning_events_20*.jsonl"))
        )
    else:
        dates = [args.date]

    summary = []
    for d in dates:
        rows, audit = build_rows(d)
        existing = _count_for_date(d)
        audit["existing_rows"] = existing
        if audit.get("status") == "NO_SOURCE_FILE":
            pass
        elif existing and not args.force:
            audit["status"] = "SKIPPED_DATE_ALREADY_PRESENT"
        elif not rows:
            audit["status"] = "NO_ROWS"
        elif not args.execute:
            audit["status"] = "DRY_RUN"
        else:
            audit["written"] = _upsert(rows)
            audit["rows_after"] = _count_for_date(d)
            audit["status"] = "OK" if audit["rows_after"] >= len(rows) else "COUNT_MISMATCH"
        summary.append(audit)
        print(json.dumps(audit))
    bad = [a for a in summary if a["status"] in ("COUNT_MISMATCH",)]
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
