"""
Race Metadata Resolver
======================

Resolves course, off_time, race_name for a race_id using a priority chain:

  1. Supabase public.races (primary — 3,641+ rows, best coverage)
  2. Supabase race_results (has race_id, fallback)
  3. local data/racecards_YYYY_MM_DD_standard.json
  4. local data/racecard_merged/racecard_*_YYYY-MM-DD.json
  5. local data/results_YYYY_MM_DD.json
  6. verdict full_analysis[0] fallback

Returns a RaceMetadata dataclass per race_id.
Read-only. No scoring, model, router, or staking changes.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"


@dataclass
class RaceMetadata:
    race_id: str
    date: str = ""
    course: str = ""
    off_time: str = ""
    race_name: str = ""
    source_used: str = ""
    metadata_complete: bool = False
    missing_fields: list[str] = field(default_factory=list)

    def _evaluate(self) -> None:
        missing = []
        if not self.course:
            missing.append("course")
        if not self.off_time:
            missing.append("off_time")
        self.missing_fields = missing
        self.metadata_complete = len(missing) == 0

    @staticmethod
    def _fmt_time(raw: str) -> str:
        """Convert HH:MM:SS or HH:MM to H:MM (no leading zero)."""
        if not raw:
            return ""
        parts = raw.strip().split(":")
        if len(parts) >= 2:
            try:
                h = int(parts[0])
                m = parts[1].zfill(2)
                return f"{h}:{m}"
            except ValueError:
                pass
        return raw.strip()


class RaceMetadataResolver:
    """
    Resolve race metadata by race_id.

    Usage:
        resolver = RaceMetadataResolver(date="2026-05-01")
        meta = resolver.resolve("rac_11912368")
    """

    def __init__(self, date: str = "", sb_client=None):
        self._date = date  # YYYY-MM-DD
        self._sb = sb_client
        self._cache: dict[str, RaceMetadata] = {}
        self._local_index: dict[str, dict] | None = None

    # ── public ────────────────────────────────────────────────────────────────

    def resolve(self, race_id: str, verdict_full_analysis: list | None = None) -> RaceMetadata:
        if race_id in self._cache:
            return self._cache[race_id]

        meta = RaceMetadata(race_id=race_id, date=self._date)

        for attempt in (
            self._from_supabase_races,
            self._from_supabase_race_results,
            self._from_local_standard,
            self._from_local_merged,
            self._from_local_results,
        ):
            attempt(meta)
            meta._evaluate()
            if meta.metadata_complete:
                break

        if not meta.metadata_complete and verdict_full_analysis:
            self._from_verdict_fallback(meta, verdict_full_analysis)
            meta._evaluate()

        if not meta.source_used:
            meta.source_used = "unresolved"

        self._cache[race_id] = meta
        return meta

    def resolve_batch(
        self,
        race_ids: list[str],
        verdict_map: dict[str, list] | None = None,
    ) -> dict[str, RaceMetadata]:
        self._prime_supabase_batch(race_ids)
        self._prime_local_index()
        verdict_map = verdict_map or {}
        return {
            rid: self.resolve(rid, verdict_map.get(rid))
            for rid in race_ids
        }

    # ── source 1: Supabase races ───────────────────────────────────────────────

    def _prime_supabase_batch(self, race_ids: list[str]) -> None:
        if not self._sb or not race_ids:
            return
        try:
            rows = (
                self._sb.table("races")
                .select("race_id,course,date,time,race_name")
                .in_("race_id", race_ids)
                .execute()
                .data
            )
            for row in rows:
                rid = row.get("race_id", "")
                if not rid:
                    continue
                meta = RaceMetadata(
                    race_id=rid,
                    date=row.get("date", self._date),
                    course=row.get("course", ""),
                    off_time=RaceMetadata._fmt_time(row.get("time", "")),
                    race_name=row.get("race_name", ""),
                    source_used="supabase_races",
                )
                meta._evaluate()
                self._cache[rid] = meta
        except Exception:
            pass

    def _from_supabase_races(self, meta: RaceMetadata) -> None:
        if meta.race_id in self._cache and self._cache[meta.race_id].source_used == "supabase_races":
            found = self._cache[meta.race_id]
            meta.course = found.course
            meta.off_time = found.off_time
            meta.race_name = found.race_name
            meta.date = found.date or meta.date
            meta.source_used = "supabase_races"
            return
        if not self._sb:
            return
        try:
            rows = (
                self._sb.table("races")
                .select("race_id,course,date,time,race_name")
                .eq("race_id", meta.race_id)
                .limit(1)
                .execute()
                .data
            )
            if rows:
                row = rows[0]
                meta.course = row.get("course", "")
                meta.off_time = RaceMetadata._fmt_time(row.get("time", ""))
                meta.race_name = row.get("race_name", "")
                meta.date = row.get("date", meta.date)
                meta.source_used = "supabase_races"
        except Exception:
            pass

    # ── source 2: Supabase race_results ───────────────────────────────────────

    def _from_supabase_race_results(self, meta: RaceMetadata) -> None:
        if not self._sb:
            return
        try:
            rows = (
                self._sb.table("race_results")
                .select("race_id")
                .eq("race_id", meta.race_id)
                .limit(1)
                .execute()
                .data
            )
            if rows:
                meta.source_used = "supabase_race_results"
        except Exception:
            pass

    # ── local index ────────────────────────────────────────────────────────────

    def _prime_local_index(self) -> None:
        if self._local_index is not None:
            return
        self._local_index = {}
        date_tag = self._date.replace("-", "_") if self._date else ""

        def _ingest(races: list, source: str) -> None:
            for race in races:
                rid = race.get("race_id")
                if not rid or rid in self._local_index:
                    continue
                course = race.get("course") or race.get("venue") or ""
                off_time = RaceMetadata._fmt_time(
                    race.get("off_time") or race.get("race_time") or race.get("time") or ""
                )
                self._local_index[rid] = {
                    "course": course,
                    "off_time": off_time,
                    "race_name": race.get("race_name") or race.get("name") or "",
                    "date": race.get("date") or self._date,
                    "source": source,
                }

        # standard racecard files
        patterns = []
        if date_tag:
            patterns.append(DATA / f"racecards_{date_tag}_standard.json")
        patterns.extend(sorted(DATA.glob("racecards_*_standard.json")))
        for p in patterns:
            if not p.exists():
                continue
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                races = raw if isinstance(raw, list) else raw.get("racecards", raw.get("races", []))
                _ingest(races, f"local_standard:{p.name}")
            except Exception:
                pass

        # merged racecard files
        date_suffix = self._date if self._date else ""
        merged_candidates = sorted(DATA.glob(f"racecard_merged/racecard_*_{date_suffix}.json")) if date_suffix else []
        merged_candidates += sorted(DATA.glob("racecard_merged/racecard_*.json"))
        for p in merged_candidates:
            if not p.exists():
                continue
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                races = raw if isinstance(raw, list) else raw.get("races", raw.get("racecards", [raw]))
                _ingest(races, f"local_merged:{p.name}")
            except Exception:
                pass

        # results files
        results_candidates = []
        if date_tag:
            results_candidates.append(DATA / f"results_{date_tag}.json")
        results_candidates.extend(sorted(DATA.glob("results_*.json")))
        for p in results_candidates:
            if not p.exists():
                continue
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                races = raw.get("results", []) if isinstance(raw, dict) else raw
                for race in races:
                    rid = race.get("race_id")
                    if not rid or rid in self._local_index:
                        continue
                    course = race.get("course") or race.get("venue") or ""
                    off_time = RaceMetadata._fmt_time(
                        race.get("off_time") or race.get("race_time") or ""
                    )
                    self._local_index[rid] = {
                        "course": course,
                        "off_time": off_time,
                        "race_name": race.get("race_name") or "",
                        "date": race.get("date") or self._date,
                        "source": f"local_results:{p.name}",
                    }
            except Exception:
                pass

    # ── source 3–5: local files ────────────────────────────────────────────────

    def _from_local_standard(self, meta: RaceMetadata) -> None:
        self._prime_local_index()
        entry = (self._local_index or {}).get(meta.race_id)
        if entry and "local_standard" in entry.get("source", ""):
            meta.course = entry["course"]
            meta.off_time = entry["off_time"]
            meta.race_name = entry.get("race_name", "")
            meta.date = entry.get("date", meta.date)
            meta.source_used = entry["source"]

    def _from_local_merged(self, meta: RaceMetadata) -> None:
        self._prime_local_index()
        entry = (self._local_index or {}).get(meta.race_id)
        if entry and "local_merged" in entry.get("source", ""):
            meta.course = entry["course"]
            meta.off_time = entry["off_time"]
            meta.race_name = entry.get("race_name", "")
            meta.date = entry.get("date", meta.date)
            meta.source_used = entry["source"]

    def _from_local_results(self, meta: RaceMetadata) -> None:
        self._prime_local_index()
        entry = (self._local_index or {}).get(meta.race_id)
        if entry and "local_results" in entry.get("source", ""):
            meta.course = entry["course"]
            meta.off_time = entry["off_time"]
            meta.race_name = entry.get("race_name", "")
            meta.date = entry.get("date", meta.date)
            meta.source_used = entry["source"]

    # ── source 6: verdict full_analysis fallback ──────────────────────────────

    def _from_verdict_fallback(self, meta: RaceMetadata, full_analysis: list) -> None:
        top = full_analysis[0] if full_analysis else {}
        course = top.get("course", "")
        off_time = RaceMetadata._fmt_time(top.get("off_time") or top.get("race_time") or "")
        if course or off_time:
            meta.course = course or meta.course
            meta.off_time = off_time or meta.off_time
            meta.race_name = top.get("race_name", meta.race_name)
            meta.source_used = "verdict_fallback"
