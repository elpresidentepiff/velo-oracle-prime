#!/usr/bin/env python3
"""Shared helpers for RP archive Supabase tools."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"
FORBIDDEN_TABLES = {
    "velo_verdicts",
    "predictions",
    "runner_prediction_snapshots",
    "learned_patterns",
    "velo_learning_events",
}
ARCHIVE_TABLES = {
    "rp_ingestion_runs",
    "rp_meetings",
    "rp_racecards",
    "rp_runner_profiles",
    "rp_runner_signals",
    "rp_entity_aliases",
    "raw_payload_archive",
}
POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
RPR_POLICY = "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def supabase_config() -> tuple[str, str]:
    load_dotenv()
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and service key env vars are required.")
    return url, key


def headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def fetch_openapi() -> dict[str, Any]:
    url, key = supabase_config()
    resp = requests.get(
        f"{url}/rest/v1/",
        headers={**headers(key), "Accept": "application/openapi+json"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def table_columns(spec: dict[str, Any], table: str) -> list[str]:
    return list((spec.get("definitions", {}).get(table, {}).get("properties") or {}).keys())


def table_exists(spec: dict[str, Any], table: str) -> bool:
    return bool(table_columns(spec, table))


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def norm_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def filter_columns(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k in columns}


class SupabaseRest:
    def __init__(self) -> None:
        self.url, self.key = supabase_config()
        self.base = f"{self.url}/rest/v1"

    def _check_table(self, table: str) -> None:
        if table in FORBIDDEN_TABLES:
            raise RuntimeError(f"Forbidden table touch blocked: {table}")
        if table not in ARCHIVE_TABLES:
            raise RuntimeError(f"Non-archive table touch blocked: {table}")

    def select(self, table: str, filters: dict[str, Any], select: str = "*", limit: int | None = None) -> list[dict[str, Any]]:
        self._check_table(table)
        params = {"select": select}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        if limit is not None:
            params["limit"] = str(limit)
        resp = requests.get(f"{self.base}/{table}?{urlencode(params)}", headers=headers(self.key), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def insert(self, table: str, row: dict[str, Any]) -> list[dict[str, Any]]:
        self._check_table(table)
        resp = requests.post(
            f"{self.base}/{table}",
            headers={**headers(self.key), "Prefer": "return=representation"},
            data=json.dumps(row, ensure_ascii=False),
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"Supabase insert failed table={table} status={resp.status_code} body={resp.text[:1000]}")
        return resp.json()

    def patch(self, table: str, filters: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]]:
        self._check_table(table)
        params = {key: f"eq.{value}" for key, value in filters.items()}
        resp = requests.patch(
            f"{self.base}/{table}?{urlencode(params)}",
            headers={**headers(self.key), "Prefer": "return=representation"},
            data=json.dumps(row, ensure_ascii=False),
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"Supabase patch failed table={table} status={resp.status_code} body={resp.text[:1000]}")
        return resp.json()

    def upsert_by_filter(self, table: str, row: dict[str, Any], filters: dict[str, Any]) -> str:
        existing = self.select(table, filters, select="*", limit=1)
        if existing:
            self.patch(table, filters, row)
            return "updated"
        self.insert(table, row)
        return "inserted"
