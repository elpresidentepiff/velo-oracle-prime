#!/usr/bin/env python3
"""
persist_daily_artifacts.py

Idempotent upserts of VELO data that until 2026-09-13 lived only as local files
(operator-approved 2026-09-13). Writes only to the tables created by
supabase/migrations/20260913_001_velo_daily_artifacts.sql:

  council        data/council_runs/council_run_YYYY-MM-DD.json      -> velo_council_runs
  mission        data/mission_control/YYYY-MM-DD_mission_control.json -> velo_mission_control
  ledger         data/model_comparison_ledger.csv                   -> velo_model_comparison_ledger
  passports      data/new_build/passports/horse_passports_v1.jsonl  -> new_build_horse_passports
  reports        dashboard report files (see REPORTS)               -> velo_report_artifacts

Every kind verifies its own write by reading the row count back and comparing it
with the count built from the local source; a shortfall exits non-zero.

Default is --dry-run. --execute is required to write.

Usage:
  PYTHONPATH=. python scripts/ops/persist_daily_artifacts.py --kind all --date 2026-09-11 --execute
  PYTHONPATH=. python scripts/ops/persist_daily_artifacts.py --kind all --all-dates --execute
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("council", "mission", "ledger", "passports", "reports")

# artifact_type -> (dated path pattern or None, undated "latest" path or None)
REPORTS = {
    "llm_brief_suggestions":      ("data/reports/llm_brief_suggestions_{tag}.json", None),
    "llm_brief_eod":              ("data/reports/llm_brief_eod_{tag}.json", None),
    "midprice_shadow":            ("data/reports/midprice_shadow_{tag}.json", None),
    "mds_heavy_shadow":           ("data/reports/mds_heavy_shadow_{tag}.json", None),
    "old_velo_three_option_card": ("data/reports/old_velo_three_option_card_{tag}.json", None),
    "rpdc_gate_card":             ("data/reports/rpdc_gate_card_{tag}.json", "data/reports/rpdc_gate_card_latest.json"),
    "velo_prime_verdicts":        ("data/velo_prime_verdicts_{tag}.json", None),
    "doctrine_scorecard":         (None, "data/doctrine_scorecard_latest.json"),
    "sidecar_stack":              (None, "app/static/dashboard/sidecar_stack_latest.json"),
}

LEDGER_NUMERIC = {"norpr_prob", "nb_prob", "champion_prob", "mp_prob", "nbc_prob", "winner_sp"}


# ── Supabase REST ─────────────────────────────────────────────────────────────
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


def _headers(key: str, **extra: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", **extra}


def _upsert(table: str, rows: list[dict], conflict: str, batch: int = 200) -> int:
    url, key = _env()
    written = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        req = urllib.request.Request(
            f"{url}/rest/v1/{table}?on_conflict={conflict}",
            data=json.dumps(chunk, default=str).encode(),
            headers=_headers(key, Prefer="resolution=merge-duplicates,return=minimal"),
        )
        try:
            urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"UPSERT_FAILED {table} batch@{i}: HTTP {e.code} {e.read().decode(errors='replace')[:400]}") from None
        written += len(chunk)
    return written


def _count(table: str, filters: str = "") -> int:
    url, key = _env()
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}?select=*{('&' + filters) if filters else ''}",
        headers=_headers(key, Prefer="count=exact", Range="0-0"), method="HEAD",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Range"].split("/")[-1])


# ── helpers ───────────────────────────────────────────────────────────────────
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _dates_from(pattern: str) -> list[str]:
    out = set()
    for f in glob.glob(str(ROOT / pattern)):
        m = re.search(r"(\d{4})[-_](\d\d)[-_](\d\d)", Path(f).name)
        if m:
            out.add("-".join(m.groups()))
    return sorted(out)


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


# ── kinds ─────────────────────────────────────────────────────────────────────
def build_council(dates: list[str]) -> list[dict]:
    rows = []
    for d in dates:
        p = ROOT / "data" / "council_runs" / f"council_run_{d}.json"
        if not p.exists():
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        rows.append({
            "run_date": d, "council_status": j.get("council_status"), "council_verdict": j.get("council_verdict"),
            "final_report": j.get("final_report"), "metadata": j.get("metadata"), "evidence_packet": j.get("evidence_packet"),
            "agent_responses": j.get("agent_responses"), "verifications": j.get("verifications"),
            "source_path": _rel(p), "source_sha256": _sha(p),
        })
    return rows


def build_mission(dates: list[str]) -> list[dict]:
    rows = []
    for d in dates:
        p = ROOT / "data" / "mission_control" / f"{d}_mission_control.json"
        if not p.exists():
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        rows.append({
            "run_date": d, "generated_at": j.get("generated_at"), "source_truth": j.get("source_truth"),
            "learning_gate_status": j.get("learning_gate_status"), "promotion_gate_status": j.get("promotion_gate_status"),
            "council_verdict": j.get("council_verdict"), "flatline_count": j.get("flatline_count"),
            "identity_failure_count": j.get("identity_failure_count"), "runners_snapshotted": j.get("runners_snapshotted"),
            "gate_reasons": j.get("gate_reasons"), "payload": j, "source_path": _rel(p), "source_sha256": _sha(p),
        })
    return rows


def build_ledger(dates: list[str] | None) -> list[dict]:
    p = ROOT / "data" / "model_comparison_ledger.csv"
    rows: dict[tuple, dict] = {}
    with p.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if dates is not None and r["date"] not in dates:
                continue
            row = {("run_date" if k == "date" else "off_time" if k == "off" else k):
                   (_num(v) if k in LEDGER_NUMERIC else (v or None)) for k, v in r.items()}
            rows[(row["run_date"], row["race_id"])] = row   # append-only ledger: last write for a race wins
    return list(rows.values())


def build_passports() -> list[dict]:
    p = ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"
    sha = _sha(p)
    rows: dict[int, dict] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        j = json.loads(line)
        uid = j.get("horse_rp_uid")
        if uid in (None, ""):
            continue
        lr = str(j.get("last_run_date") or "")[:10]
        rows[int(uid)] = {
            "horse_rp_uid": int(uid), "horse_name": j.get("horse_name"),
            "last_run_date": lr if re.match(r"^\d{4}-\d\d-\d\d$", lr) else None,
            "career_runs": j.get("career_runs"), "wins": j.get("wins"), "win_rate": j.get("win_rate"),
            "passport": j, "source_sha256": sha,
        }
    return list(rows.values())


def build_reports(dates: list[str] | None) -> list[dict]:
    rows = []
    for atype, (dated, latest) in REPORTS.items():
        candidates: list[tuple[str, Path]] = []
        if dated:
            ds = dates if dates is not None else _dates_from(dated.replace("{tag}", "*"))
            candidates += [(d, ROOT / dated.format(tag=d.replace("-", "_"))) for d in ds]
        if latest and (ROOT / latest).exists():
            lp = ROOT / latest
            payload = json.loads(lp.read_text(encoding="utf-8"))
            gen = str(payload.get("generated_at") or payload.get("date") or "")[:10] if isinstance(payload, dict) else ""
            d = gen if re.match(r"^\d{4}-\d\d-\d\d$", gen) else datetime.fromtimestamp(lp.stat().st_mtime).date().isoformat()
            if dates is None or d in dates:
                # a dated file for the same day is the better source; latest only fills the gap
                if not any(cd == d and cp.exists() for cd, cp in candidates):
                    candidates.append((d, lp))
        for d, path in candidates:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f"  [WARN] unreadable JSON skipped: {_rel(path)}")
                continue
            rows.append({
                "artifact_type": atype, "run_date": d, "payload": payload, "source_path": _rel(path),
                "source_mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
                "source_sha256": _sha(path),
            })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Persist local-only VELO artifacts to Supabase.")
    ap.add_argument("--kind", action="append", choices=KINDS + ("all",), required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--date")
    g.add_argument("--all-dates", action="store_true")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    kinds = KINDS if "all" in args.kind else tuple(dict.fromkeys(args.kind))
    one = [args.date] if args.date else None

    summary, failed = [], False
    for kind in kinds:
        if kind == "council":
            rows, table, conflict = build_council(one or _dates_from("data/council_runs/council_run_*.json")), "velo_council_runs", "run_date"
        elif kind == "mission":
            rows, table, conflict = build_mission(one or _dates_from("data/mission_control/*_mission_control.json")), "velo_mission_control", "run_date"
        elif kind == "ledger":
            rows, table, conflict = build_ledger(one), "velo_model_comparison_ledger", "run_date,race_id"
        elif kind == "passports":
            rows, table, conflict = build_passports(), "new_build_horse_passports", "horse_rp_uid"
        else:
            rows, table, conflict = build_reports(one), "velo_report_artifacts", "artifact_type,run_date"

        rec = {"kind": kind, "table": table, "rows_built": len(rows)}
        if not rows:
            rec["status"] = "NOTHING_TO_WRITE"
        elif not args.execute:
            rec["status"] = "DRY_RUN"
        else:
            batch = 500 if kind == "passports" else (20 if kind == "reports" else 200)
            rec["written"] = _upsert(table, rows, conflict, batch=batch)
            # Read back: every built key must now exist.
            if kind in ("council", "mission"):
                ds = sorted({r["run_date"] for r in rows})
                present = _count(table, f"run_date=in.({','.join(ds)})")
            elif kind == "ledger":
                ds = sorted({r["run_date"] for r in rows})
                present = sum(_count(table, f"run_date=eq.{d}") for d in ds)
            elif kind == "passports":
                present = _count(table)
            else:
                present = 0
                by_type: dict[str, list[str]] = {}
                for r in rows:
                    by_type.setdefault(r["artifact_type"], []).append(r["run_date"])
                for t, ds in by_type.items():
                    present += _count(table, f"artifact_type=eq.{t}&run_date=in.({','.join(sorted(set(ds)))})")
            rec["rows_present_after"] = present
            rec["status"] = "OK" if present >= len(rows) else "COUNT_MISMATCH"
            failed |= rec["status"] != "OK"
        summary.append(rec)
        print(json.dumps(rec))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
