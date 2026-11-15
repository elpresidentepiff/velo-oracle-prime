#!/usr/bin/env python3
"""Keep the state a race day builds on in Supabase, not on one machine's disk.

Two things the pipeline reads every morning used to live only on the operator's laptop:

* the horse passport bank  ``data/new_build/passports/horse_passports_v1.jsonl``
* the per-run form history ``data/race_shape/form_history_*.json`` (the source of the bank and
  of the Champion Intent features)

A Railway container starts from the git checkout, whose copies of both date from 2026-08-04. Each
morning it captured a few hundred horses, rebuilt the bank, and lost all of it when the container
exited. On 2026-11-12 the cloud run scored New Build with 59 of 224 runners holding a passport;
on 2026-11-14 Champion Intent found history for 59 of 564 runners.

This module makes Supabase the store:

``--hydrate``  before the run: download every stored form-history file that is not on disk, and
               merge the ``new_build_horse_passports`` table into the local bank (the newer
               passport of a horse wins; nothing is dropped).
``--persist``  after a capture: upload the new form-history file(s) and upsert the passports
               that changed since the hydrate.

Form history is stored as files in Supabase Storage (bucket ``rp_imports``). The laptop archive
uploaded on 2026-09-19 (``velo-archive/v1/data/race_shape/``) is read as the seed; new captures
go to ``velo-state/race_shape/``. Nothing in the archive is modified.

Every operation is fail-soft for the caller: the run continues on the git copy if Supabase is
unreachable, and says so.

Usage:
    PYTHONPATH=. python scripts/ops/cloud_state.py --hydrate
    PYTHONPATH=. python scripts/ops/cloud_state.py --persist
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BUCKET = "rp_imports"
SEED_PREFIX = "velo-archive/v1/data/race_shape"  # laptop archive, read-only
STATE_PREFIX = "velo-state/race_shape"  # written by every capture from now on
RACE_SHAPE_DIR = ROOT / "data" / "race_shape"
PASSPORT_PATH = ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"
PASSPORT_TABLE = "new_build_horse_passports"
# What Supabase held at the last hydrate, so a persist uploads only what changed.
HYDRATED_HASHES = PASSPORT_PATH.with_name(".supabase_passport_hashes.json")
# Form-history files that came from Supabase, so a persist uploads only new captures.
HYDRATED_FILES = RACE_SHAPE_DIR / ".supabase_files.json"


# ── Supabase access ───────────────────────────────────────────────────────────


def _env() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and a Supabase service key are required")
    return url, key


def _request(method: str, path: str, *, body: bytes | None = None, headers: dict | None = None, timeout: int = 120):
    url, key = _env()
    req = urllib.request.Request(
        f"{url}{path}",
        data=body,
        method=method,
        headers={"apikey": key, "Authorization": f"Bearer {key}", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def list_objects(prefix: str) -> list[str]:
    """Names (not paths) of the files directly under ``prefix`` in the bucket."""
    names: list[str] = []
    offset = 0
    while True:
        raw = _request(
            "POST",
            f"/storage/v1/object/list/{BUCKET}",
            body=json.dumps({"prefix": prefix, "limit": 1000, "offset": offset}).encode(),
            headers={"Content-Type": "application/json"},
        )
        page = json.loads(raw)
        names.extend(row["name"] for row in page if row.get("id"))  # folders have no id
        if len(page) < 1000:
            return names
        offset += 1000


def download_object(path: str) -> bytes:
    return _request("GET", f"/storage/v1/object/{BUCKET}/{urllib.parse.quote(path)}", timeout=300)


def upload_object(path: str, data: bytes) -> None:
    _request(
        "POST",
        f"/storage/v1/object/{BUCKET}/{urllib.parse.quote(path)}",
        body=data,
        headers={"Content-Type": "application/json", "x-upsert": "true"},
        timeout=300,
    )


def fetch_passport_rows() -> list[dict]:
    rows: list[dict] = []
    page = 1000
    offset = 0
    while True:
        raw = _request(
            "GET",
            f"/rest/v1/{PASSPORT_TABLE}?select=passport&order=horse_rp_uid.asc&limit={page}&offset={offset}",
        )
        chunk = json.loads(raw)
        rows.extend(row["passport"] for row in chunk if isinstance(row.get("passport"), dict))
        if len(chunk) < page:
            return rows
        offset += page


# ── form history ──────────────────────────────────────────────────────────────


def _is_form_history(name: str) -> bool:
    return name.startswith("form_history_") and name.endswith(".json") and "latest" not in name


def hydrate_form_history(target: Path = RACE_SHAPE_DIR) -> dict[str, Any]:
    """Download every stored form-history file that is not already on disk."""
    target.mkdir(parents=True, exist_ok=True)
    downloaded: list[str] = []
    known: set[str] = set()
    # State is listed last so a file re-captured in the cloud replaces the archived seed.
    for prefix in (SEED_PREFIX, STATE_PREFIX):
        for name in list_objects(prefix):
            if not _is_form_history(name):
                continue
            known.add(name)
            destination = target / name
            if destination.exists() and prefix == SEED_PREFIX:
                continue
            destination.write_bytes(download_object(f"{prefix}/{name}"))
            downloaded.append(name)
    (target / HYDRATED_FILES.name).write_text(json.dumps(sorted(known)), encoding="utf-8")
    on_disk = sum(1 for p in target.glob("form_history_*.json") if _is_form_history(p.name))
    return {"stored": len(known), "downloaded": len(set(downloaded)), "on_disk": on_disk}


def persist_form_history(source: Path = RACE_SHAPE_DIR) -> dict[str, Any]:
    """Upload form-history files that Supabase does not hold yet. Git-tracked ones are skipped."""
    marker = source / HYDRATED_FILES.name
    if not marker.exists():
        # Without the hydrate we cannot tell a new capture from the 78 files in git.
        return {"uploaded": 0, "skipped": "NOT_HYDRATED"}
    known = set(json.loads(marker.read_text(encoding="utf-8")))
    tracked = _git_tracked(source)
    uploaded: list[str] = []
    for path in sorted(source.glob("form_history_*.json")):
        if not _is_form_history(path.name) or path.name in known or path.name in tracked:
            continue
        upload_object(f"{STATE_PREFIX}/{path.name}", path.read_bytes())
        uploaded.append(path.name)
        known.add(path.name)
    marker.write_text(json.dumps(sorted(known)), encoding="utf-8")
    return {"uploaded": len(uploaded), "files": uploaded}


def _git_tracked(directory: Path) -> set[str]:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "ls-files", str(directory)], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return set()  # no git in the image: every file not known to Supabase is uploaded
    return {Path(line).name for line in out.splitlines()}


# ── passports ─────────────────────────────────────────────────────────────────


def passport_key(row: dict) -> str:
    uid = row.get("horse_rp_uid")
    if uid not in (None, ""):
        return str(uid)
    return f"name:{str(row.get('horse_name') or '').strip().lower()}"


def passport_freshness(row: dict) -> tuple[str, int]:
    """Orders two passports of one horse: later last run first, then more career runs."""
    return (str(row.get("last_run_date") or "")[:10], int(row.get("career_runs") or 0))


def passport_hash(row: dict) -> str:
    return hashlib.sha1(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()


def merge_passports(local: list[dict], remote: list[dict]) -> list[dict]:
    """Union by horse. The fresher passport wins; on a tie the local one is kept."""
    merged: dict[str, dict] = {passport_key(row): row for row in local}
    for row in remote:
        key = passport_key(row)
        if key not in merged or passport_freshness(row) > passport_freshness(merged[key]):
            merged[key] = row
    return list(merged.values())


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def hydrate_passports(path: Path = PASSPORT_PATH) -> dict[str, Any]:
    local = _read_jsonl(path)
    remote = fetch_passport_rows()
    merged = merge_passports(local, remote)
    _write_jsonl(path, merged)
    path.with_name(HYDRATED_HASHES.name).write_text(
        json.dumps({passport_key(row): passport_hash(row) for row in remote}), encoding="utf-8"
    )
    return {"local_before": len(local), "supabase": len(remote), "bank_after": len(merged)}


def changed_passports(rows: list[dict], hydrated_hashes: dict[str, str]) -> list[dict]:
    return [row for row in rows if hydrated_hashes.get(passport_key(row)) != passport_hash(row)]


def persist_passports(path: Path = PASSPORT_PATH) -> dict[str, Any]:
    """Upsert the passports that differ from what Supabase held at the hydrate."""
    from scripts.ops import persist_daily_artifacts as daily

    marker = path.with_name(HYDRATED_HASHES.name)
    if not marker.exists():
        # Never push a bank that was not first merged with Supabase: a stale git copy would
        # overwrite newer rows.
        return {"upserted": 0, "skipped": "NOT_HYDRATED"}
    hydrated = json.loads(marker.read_text(encoding="utf-8"))
    changed = {passport_key(row) for row in changed_passports(_read_jsonl(path), hydrated)}
    rows = [row for row in daily.build_passports() if str(row["horse_rp_uid"]) in changed]
    written = daily._upsert(PASSPORT_TABLE, rows, "horse_rp_uid", batch=500) if rows else 0
    hydrated.update({str(row["horse_rp_uid"]): passport_hash(row["passport"]) for row in rows})
    marker.write_text(json.dumps(hydrated), encoding="utf-8")
    return {"upserted": written, "changed": len(changed)}


# ── entrypoint ────────────────────────────────────────────────────────────────


def _attempt(label: str, action) -> dict[str, Any]:
    try:
        result = {"status": "OK", **action()}
    except Exception as exc:  # noqa: BLE001 - durable state must never stop a race day
        result = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"[:300]}
    print(f"[CLOUD-STATE] {label}: {json.dumps(result)}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--hydrate", action="store_true", help="Supabase -> local disk, before the run")
    mode.add_argument("--persist", action="store_true", help="local disk -> Supabase, after a capture")
    args = parser.parse_args()
    if args.hydrate:
        results = [
            _attempt("hydrate form history", hydrate_form_history),
            _attempt("hydrate passport bank", hydrate_passports),
        ]
    else:
        results = [
            _attempt("persist form history", persist_form_history),
            _attempt("persist passport bank", persist_passports),
        ]
    return 0 if all(r["status"] == "OK" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
