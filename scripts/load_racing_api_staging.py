"""
Phase 2 — Load RACING_API_ANALYSIS_V1 staging JSONL into Supabase via REST API.
Duplicate-safe upsert. Batched at 500 rows per request.
"""
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests


if sys.platform == "win32":
    WORKROOT = Path(r"C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix")
else:
    WORKROOT = Path("/mnt/c/Users/puror/OneDrive/Documents/New project/velo_feature_v10_launch_fix")

STAGING_DIR = WORKROOT / "data" / "racing_api_staging"
EXTRACTION_VERSION = "RACING_API_ANALYSIS_V1"
BATCH_SIZE = 500


def load_env() -> None:
    for env_path in [
        Path("/mnt/c/Users/puror/velo-oracle-prime/.env"),
        Path(r"C:\Users\puror\velo-oracle-prime\.env"),
    ]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


class SupabaseLoader:
    def __init__(self, base_url: str, service_key: str) -> None:
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        })

    def upsert(self, table: str, rows: list[dict], on_conflict: str = "") -> tuple[int, list[str]]:
        """Upsert a batch. Returns (rows_affected, errors)."""
        if not rows:
            return 0, []
        errors = []
        total = 0
        params = {}
        if on_conflict:
            params["on_conflict"] = on_conflict
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i: i + BATCH_SIZE]
            resp = self.session.post(
                f"{self.base}/rest/v1/{table}",
                data=json.dumps(batch, ensure_ascii=True).encode("utf-8"),
                params=params,
                timeout=60,
            )
            if resp.status_code in (200, 201):
                try:
                    total += len(resp.json())
                except Exception:
                    total += len(batch)
            else:
                errors.append(f"batch {i//BATCH_SIZE}: HTTP {resp.status_code} — {resp.text[:200]}")
        return total, errors

    def count(self, table: str) -> int:
        resp = self.session.get(
            f"{self.base}/rest/v1/{table}",
            headers={"Prefer": "count=exact"},
            params={"select": "id", "limit": "1"},
            timeout=15,
        )
        content_range = resp.headers.get("content-range", "0/0")
        try:
            return int(content_range.split("/")[-1])
        except (ValueError, IndexError):
            return -1


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_trainer_courses(staging_rows: list[dict]) -> list[dict]:
    out = []
    for row in staging_rows:
        if not row.get("accessible") or not row.get("payload"):
            continue
        pay = row["payload"]
        for item in pay.get("courses", []):
            if not item.get("course_id"):
                continue
            out.append({
                "entity_id": row["entity_id"],
                "entity_name": row.get("entity_name"),
                "endpoint_family": "trainer_analysis_courses",
                "course_id": item.get("course_id"),
                "course": item.get("course"),
                "region": item.get("region"),
                "runners_or_rides": safe_int(item.get("runners")),
                "wins": safe_int(item.get("1st")),
                "seconds": safe_int(item.get("2nd")),
                "thirds": safe_int(item.get("3rd")),
                "fourths": safe_int(item.get("4th")),
                "ae_ratio": safe_float(item.get("a/e")),
                "win_pct": safe_float(item.get("win_%")),
                "pnl": safe_float(item.get("1_pl")),
                "raw": item,
                "extraction_version": EXTRACTION_VERSION,
                "fetched_at": row.get("requested_at_utc"),
            })
    return out


def build_trainer_distances(staging_rows: list[dict]) -> list[dict]:
    out = []
    for row in staging_rows:
        if not row.get("accessible") or not row.get("payload"):
            continue
        pay = row["payload"]
        for item in pay.get("distances", []):
            if not item.get("dist"):
                continue
            out.append({
                "entity_id": row["entity_id"],
                "entity_name": row.get("entity_name"),
                "endpoint_family": "trainer_analysis_distances",
                "dist": item.get("dist"),
                "dist_y": item.get("dist_y"),
                "dist_m": item.get("dist_m"),
                "dist_f": item.get("dist_f"),
                "runners_or_rides": safe_int(item.get("runners")),
                "wins": safe_int(item.get("1st")),
                "seconds": safe_int(item.get("2nd")),
                "thirds": safe_int(item.get("3rd")),
                "fourths": safe_int(item.get("4th")),
                "ae_ratio": safe_float(item.get("a/e")),
                "win_pct": safe_float(item.get("win_%")),
                "pnl": safe_float(item.get("1_pl")),
                "raw": item,
                "extraction_version": EXTRACTION_VERSION,
                "fetched_at": row.get("requested_at_utc"),
            })
    return out


def build_trainer_jockeys(staging_rows: list[dict]) -> list[dict]:
    out = []
    for row in staging_rows:
        if not row.get("accessible") or not row.get("payload"):
            continue
        pay = row["payload"]
        for item in pay.get("jockeys", []):
            if not item.get("jockey_id"):
                continue
            out.append({
                "entity_id": row["entity_id"],
                "entity_name": row.get("entity_name"),
                "endpoint_family": "trainer_analysis_jockeys",
                "jockey_id": item.get("jockey_id"),
                "jockey_name": item.get("jockey"),
                "runners_or_rides": safe_int(item.get("runners")),
                "wins": safe_int(item.get("1st")),
                "seconds": safe_int(item.get("2nd")),
                "thirds": safe_int(item.get("3rd")),
                "fourths": safe_int(item.get("4th")),
                "ae_ratio": safe_float(item.get("a/e")),
                "win_pct": safe_float(item.get("win_%")),
                "pnl": safe_float(item.get("1_pl")),
                "raw": item,
                "extraction_version": EXTRACTION_VERSION,
                "fetched_at": row.get("requested_at_utc"),
            })
    return out


def build_jockey_courses(staging_rows: list[dict]) -> list[dict]:
    out = []
    for row in staging_rows:
        if not row.get("accessible") or not row.get("payload"):
            continue
        pay = row["payload"]
        for item in pay.get("courses", []):
            if not item.get("course_id"):
                continue
            out.append({
                "entity_id": row["entity_id"],
                "entity_name": row.get("entity_name"),
                "endpoint_family": "jockey_analysis_courses",
                "course_id": item.get("course_id"),
                "course": item.get("course"),
                "region": item.get("region"),
                "runners_or_rides": safe_int(item.get("rides")),
                "wins": safe_int(item.get("1st")),
                "seconds": safe_int(item.get("2nd")),
                "thirds": safe_int(item.get("3rd")),
                "fourths": safe_int(item.get("4th")),
                "ae_ratio": safe_float(item.get("a/e")),
                "win_pct": safe_float(item.get("win_%")),
                "pnl": safe_float(item.get("1_pl")),
                "raw": item,
                "extraction_version": EXTRACTION_VERSION,
                "fetched_at": row.get("requested_at_utc"),
            })
    return out


def build_jockey_distances(staging_rows: list[dict]) -> list[dict]:
    out = []
    for row in staging_rows:
        if not row.get("accessible") or not row.get("payload"):
            continue
        pay = row["payload"]
        for item in pay.get("distances", []):
            if not item.get("dist"):
                continue
            out.append({
                "entity_id": row["entity_id"],
                "entity_name": row.get("entity_name"),
                "endpoint_family": "jockey_analysis_distances",
                "dist": item.get("dist"),
                "dist_y": item.get("dist_y"),
                "dist_m": item.get("dist_m"),
                "dist_f": item.get("dist_f"),
                "runners_or_rides": safe_int(item.get("rides")),
                "wins": safe_int(item.get("1st")),
                "seconds": safe_int(item.get("2nd")),
                "thirds": safe_int(item.get("3rd")),
                "fourths": safe_int(item.get("4th")),
                "ae_ratio": safe_float(item.get("a/e")),
                "win_pct": safe_float(item.get("win_%")),
                "pnl": safe_float(item.get("1_pl")),
                "raw": item,
                "extraction_version": EXTRACTION_VERSION,
                "fetched_at": row.get("requested_at_utc"),
            })
    return out


def build_jockey_trainers(staging_rows: list[dict]) -> list[dict]:
    out = []
    for row in staging_rows:
        if not row.get("accessible") or not row.get("payload"):
            continue
        pay = row["payload"]
        for item in pay.get("trainers", []):
            if not item.get("trainer_id"):
                continue
            out.append({
                "entity_id": row["entity_id"],
                "entity_name": row.get("entity_name"),
                "endpoint_family": "jockey_analysis_trainers",
                "trainer_id": item.get("trainer_id"),
                "trainer_name": item.get("trainer"),
                "runners_or_rides": safe_int(item.get("rides")),
                "wins": safe_int(item.get("1st")),
                "seconds": safe_int(item.get("2nd")),
                "thirds": safe_int(item.get("3rd")),
                "fourths": safe_int(item.get("4th")),
                "ae_ratio": safe_float(item.get("a/e")),
                "win_pct": safe_float(item.get("win_%")),
                "pnl": safe_float(item.get("1_pl")),
                "raw": item,
                "extraction_version": EXTRACTION_VERSION,
                "fetched_at": row.get("requested_at_utc"),
            })
    return out


JOBS = [
    ("racing_api_trainer_analysis_courses",   "trainer_analysis_courses_v1.jsonl",   build_trainer_courses),
    ("racing_api_trainer_analysis_distances", "trainer_analysis_distances_v1.jsonl", build_trainer_distances),
    ("racing_api_trainer_analysis_jockeys",   "trainer_analysis_jockeys_v1.jsonl",   build_trainer_jockeys),
    ("racing_api_jockey_analysis_courses",    "jockey_analysis_courses_v1.jsonl",    build_jockey_courses),
    ("racing_api_jockey_analysis_distances",  "jockey_analysis_distances_v1.jsonl",  build_jockey_distances),
    ("racing_api_jockey_analysis_trainers",   "jockey_analysis_trainers_v1.jsonl",   build_jockey_trainers),
]


def main() -> None:
    load_env()
    base_url = os.environ["SUPABASE_URL"]
    svc_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]

    loader = SupabaseLoader(base_url, svc_key)
    print(f"Supabase REST loader ready — {base_url}")
    print()

    summary = {}
    for table, fname, builder in JOBS:
        path = STAGING_DIR / fname
        if not path.exists():
            print(f"  SKIP {table} — {fname} not found")
            continue

        print(f"  [{table}]")
        t0 = time.monotonic()

        staging_rows = read_jsonl(path)
        built = builder(staging_rows)
        print(f"    staged={len(staging_rows)} expanded={len(built)} rows")

        before = loader.count(table)
        affected, errors = loader.upsert(table, built)
        after = loader.count(table)
        elapsed = time.monotonic() - t0

        summary[table] = {
            "attempted": len(built),
            "after_count": after,
            "inserted": after - before,
            "errors": len(errors),
            "elapsed_s": round(elapsed, 1),
        }
        status = "OK" if not errors else f"ERRORS: {errors[:2]}"
        print(f"    before={before} after={after} inserted={after-before} elapsed={elapsed:.1f}s {status}")
        print()

    print("=== LOAD SUMMARY ===")
    total_rows = 0
    for table, stats in summary.items():
        print(f"  {table}: {stats['after_count']} rows (+{stats['inserted']} new) errors={stats['errors']}")
        total_rows += stats["after_count"]
    print(f"  TOTAL ROWS IN DB: {total_rows}")
    print()
    print("Phase 2 complete.")


if __name__ == "__main__":
    main()
