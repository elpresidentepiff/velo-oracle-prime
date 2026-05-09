"""
course_identity_resolver.py

Resolves horse race course names to Racing API course_ids.

Source of truth: racing_horse_runs table in Supabase, which stores both
`course` (name string) and `course_id` ("crs_XXXXX" format) alongside
`race_id` and `horse_id`.

This avoids dependency on the /courses API endpoint (not on standard plan).
The mapping is derived from 90,869 historical run rows covering all active
GB/IRE venues and international courses.

Usage:
    resolver = CourseIdentityResolver(supabase_url, service_key)
    resolver.load()  # or CourseIdentityResolver.from_env()
    course_id = resolver.get_course_id("Ascot")  # → "crs_4732"
    result = resolver.resolve("Ascot (AW)")       # → {course_id, course, ...}
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

_CACHE_PATH = Path("data/racing_api_courses_cache.json")
_HEADERS_TEMPLATE = {"apikey": "{key}", "Authorization": "Bearer {key}"}


def _supabase_headers(key: str) -> dict:
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _normalize_name(name: str) -> str:
    """Canonical form for fuzzy matching: lowercase, strip AW/parens, collapse spaces."""
    if not name:
        return ""
    s = name.lower()
    # strip parenthetical suffixes: (aw), (usa), (ire) etc.
    s = re.sub(r"\s*\(.*?\)", "", s)
    # strip trailing AW/FT/etc standalone suffixes
    s = re.sub(r"\s+\b(aw|all.weather|flat|tp|chelmsford city)\b", "", s)
    return s.strip()


class CourseIdentityResolver:
    """Maps course name strings to Racing API course_ids.

    Loaded from racing_horse_runs Supabase table; cached locally.
    """

    def __init__(self, supabase_url: str, service_key: str) -> None:
        self._url = supabase_url.rstrip("/")
        self._key = service_key
        # name_canonical → {course_id, course, region, region_code}
        self._by_name: dict[str, dict] = {}
        # race_id → course_id (fast path for dataset builder)
        self._by_race: dict[str, str] = {}
        self._loaded = False

    @classmethod
    def from_env(cls) -> "CourseIdentityResolver":
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=".env")
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SERVICE_KEY", "")
        return cls(url, key)

    def load(self, use_cache: bool = True) -> None:
        """Populate lookup tables from Supabase racing_horse_runs."""
        if self._loaded:
            return
        if use_cache and _CACHE_PATH.exists():
            self._load_from_cache()
            return
        self._fetch_from_supabase()
        self._save_cache()
        self._loaded = True

    def _fetch_from_supabase(self) -> None:
        rows, offset = [], 0
        h = _supabase_headers(self._key)
        while True:
            req = urllib.request.Request(
                f"{self._url}/rest/v1/racing_horse_runs"
                f"?select=race_id,course,course_id,region,region_code"
                f"&offset={offset}&limit=1000",
                headers={**h, "Range": f"{offset}-{offset+999}"},
            )
            with urllib.request.urlopen(req) as r:
                batch = json.loads(r.read())
            rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000

        for row in rows:
            cid = row.get("course_id")
            cname = row.get("course")
            race_id = row.get("race_id")
            if not cid:
                continue
            if race_id:
                self._by_race[race_id] = cid
            if cname and cid not in {v.get("course_id") for v in self._by_name.values()}:
                canon = _normalize_name(cname)
                if canon not in self._by_name:
                    self._by_name[canon] = {
                        "course_id": cid,
                        "course": cname,
                        "region": row.get("region", ""),
                        "region_code": row.get("region_code", ""),
                    }

    def _load_from_cache(self) -> None:
        with _CACHE_PATH.open() as f:
            data = json.load(f)
        self._by_name = data.get("by_name", {})
        self._by_race = data.get("by_race", {})
        self._loaded = True

    def _save_cache(self) -> None:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CACHE_PATH.open("w") as f:
            json.dump({"by_name": self._by_name, "by_race": self._by_race}, f)

    def get_course_id_by_race(self, race_id: str) -> str | None:
        """Direct race_id → course_id lookup (highest confidence)."""
        return self._by_race.get(race_id)

    def get_course_id(self, course_name: str) -> str | None:
        """Resolve course name string to course_id."""
        result = self.resolve(course_name)
        return result.get("course_id") if result else None

    def resolve(self, course_name: str) -> dict | None:
        """Return full resolve result or None if unresolvable.

        Returns dict with: course_id, course, region, region_code, confidence.
        """
        if not course_name:
            return None
        canon = _normalize_name(course_name)
        # Exact canonical match
        if canon in self._by_name:
            return {**self._by_name[canon], "confidence": "exact"}
        # Partial match — course name contains or is contained by a known name
        for known_canon, info in self._by_name.items():
            if canon in known_canon or known_canon in canon:
                return {**info, "confidence": "partial"}
        return None

    @property
    def course_count(self) -> int:
        return len(self._by_name)

    @property
    def race_count(self) -> int:
        return len(self._by_race)
