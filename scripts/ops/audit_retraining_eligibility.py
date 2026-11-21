#!/usr/bin/env python3
"""Fail-closed retraining inventory for canonical historical features.

Run with a Supabase connection in a controlled environment. No model writes.
The historic reconstruction is NOT automatically a point-in-time training set.
"""
from __future__ import annotations
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.parse import quote

TABLE = "historical_feature_store"
COLUMNS = "race_id,is_synthetic,training_safe,prediction_timestamp,leakage_status,feature_status"

def classify(rows):
    n = len(rows)
    safe = [r for r in rows if r.get("is_synthetic") is False
            and r.get("training_safe") is True
            and r.get("prediction_timestamp")
            and r.get("leakage_status") in ("PASS", "VERIFIED_PRE_OFF")]
    return {
        "rows_examined": n,
        "distinct_races_examined": len({r["race_id"] for r in rows}),
        "synthetic_rows": sum(r.get("is_synthetic") is True for r in rows),
        "missing_prediction_timestamp": sum(not r.get("prediction_timestamp") for r in rows),
        "training_safe_true": sum(r.get("training_safe") is True for r in rows),
        "point_in_time_eligible_rows": len(safe),
        "point_in_time_eligible_races": len({r["race_id"] for r in safe}),
        "training_authorised": False,  # Inventory is not approval to fit models.
    }

def main():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and server-side Supabase key required")
    headers = {"apikey": key, "Authorization": "Bearer " + key, "Accept": "application/json"}
    rows = []
    start = 0
    while True:
        req = Request(f"{url}/rest/v1/{TABLE}?select={quote(COLUMNS, safe=',')}&order=id.asc",
                      headers={**headers, "Range": f"{start}-{start+999}"})
        with urlopen(req, timeout=60) as resp:
            batch = json.load(resp)
        rows.extend(batch)
        if len(batch) < 1000:
            break
        start += len(batch)
    report = classify(rows)
    print(json.dumps(report, indent=2))
    if not report["point_in_time_eligible_rows"]:
        print("BLOCKED: zero verified point-in-time training rows", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
