"""
Race Metadata Resolver
======================

Resolves course, off_time, race_name, and horse names for a race_id/horse_id 
using a priority chain:

  1. Supabase public.races (primary)
  2. local data/racecards_YYYY_MM_DD_standard.json
  3. local data/racecard_merged/racecard_*_YYYY-MM-DD.json
  4. local data/results_YYYY_MM_DD.json
  5. verdict full_analysis fallback

Returns a RaceMetadata dataclass per race_id.
Read-only. No scoring, model, router, or staking changes.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"

# --- UTILITIES ---

def chunked(values: list[str], size: int = 100) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]

def load_env_candidates() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def resolve_supabase_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")

def resolve_supabase_headers() -> dict[str, str]:
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def get_json(url: str, *, headers: dict[str, str], timeout: int = 20) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            payload = json.loads(body.decode("utf-8")) if body else {}
            return response.status, payload
    except Exception as exc:
        return 0, {"error": str(exc)}

def rest_fetch(table: str, select: str, filters: dict[str, str] | None = None) -> list[dict[str, Any]]:
    load_env_candidates()
    base_url = resolve_supabase_url()
    headers = resolve_supabase_headers()
    rows: list[dict[str, Any]] = []
    offset = 0
    limit = 1000
    filters = filters or {}
    while True:
        params = {"select": select, "limit": str(limit), "offset": str(offset), **filters}
        query = urllib.parse.urlencode(params, safe="(),.*:-")
        status, payload = get_json(f"{base_url}/rest/v1/{table}?{query}", headers=headers)
        if status < 200 or status >= 400: break
        rows.extend(payload)
        if len(payload) < limit: break
        offset += limit
    return rows

def normalize_text(value: Any) -> str | None:
    if value is None: return None
    return str(value).strip() or None

def normalize_rid(rid: Any) -> str:
    if not rid: return ""
    s = str(rid).strip().lower()
    if s.startswith("rac_"):
        return s[4:]
    return s

def normalize_name(name: Any) -> str:
    if not name: return ""
    return str(name).strip().upper().split("(")[0].strip()

# --- CLASSES ---

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
    runners: List[Dict[str, Any]] = field(default_factory=list)

    def _evaluate(self) -> None:
        missing = []
        if not self.course:
            missing.append("course")
        if not self.off_time:
            missing.append("off_time")
        self.missing_fields = missing
        self.metadata_complete = len(missing) == 0

    def get_horse_name(self, horse_id: str = "", raw_name: str = "") -> str:
        """Resolve horse name from runner list if missing."""
        if raw_name and raw_name != "?":
            return raw_name
            
        h_clean = normalize_name(raw_name)
        h_id_clean = str(horse_id).strip().lower()
        
        for r in self.runners:
            r_id = str(r.get("horse_id", "")).strip().lower()
            r_name = normalize_name(r.get("horse") or r.get("horse_name"))
            
            if h_id_clean and r_id == h_id_clean:
                return r.get("horse") or r.get("horse_name") or ""
            if h_clean and r_name == h_clean:
                return r.get("horse") or r.get("horse_name") or ""
                
        # If still nothing and we have exactly one runner in the list (common for single-verdict lookups)
        if len(self.runners) == 1 and not raw_name:
            return self.runners[0].get("horse") or self.runners[0].get("horse_name") or ""
            
        return raw_name or "?"


class RaceMetadataResolver:
    """
    Priority-based metadata resolver with local file support.
    """

    @staticmethod
    def _fmt_time(raw: str) -> str:
        if not raw:
            return ""
        match = re.search(r"(\d{1,2}:\d{2})", str(raw))
        if match:
            return match.group(1)
        # Handle 4.30 format
        match = re.search(r"(\d{1,2}\.\d{2})", str(raw))
        return match.group(1).replace(".", ":") if match else str(raw)

    def __init__(self, date: str = "", sb_client=None):
        self.date = date
        self.date_token = date.replace("-", "_") if date else ""
        self.sb = sb_client
        self._race_idx = {}   # norm_rid -> {metadata}
        self._runner_idx = {} # norm_rid -> [{runner}]
        self._prime_local_index()

    def _prime_local_index(self) -> None:
        """Builds a comprehensive lookup for the requested date."""
        if not self.date:
            return

        # 1. Standard Racecards
        std_files = [
            DATA / f"racecards_{self.date_token}_standard.json",
            DATA / f"racecards_{self.date}_standard.json"
        ]
        for fpath in std_files:
            if fpath.exists():
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            r_list = data
                        else:
                            # Standard card usually has 'racecards' key
                            r_list = data.get("racecards", data.get("races", []))
                        
                        for r in r_list:
                            rid = normalize_rid(r.get("race_id"))
                            if not rid: continue
                            
                            self._race_idx[rid] = {
                                "course": r.get("course") or r.get("venue"),
                                "off_time": self._fmt_time(r.get("off_time") or r.get("off") or r.get("time")),
                                "race_name": r.get("race_name") or r.get("name"),
                                "source": fpath.name
                            }
                            self._runner_idx[rid] = r.get("runners", [])
                except Exception as e:
                    print(f"Warning: Failed to index {fpath}: {e}")

        # 2. Merged Racecards
        merged_files = list(DATA.glob(f"racecard_merged/*_{self.date}.json"))
        merged_files += list(DATA.glob(f"racecard_merged/*_{self.date_token}.json"))
        for fpath in merged_files:
            try:
                with open(fpath) as f:
                    data = json.load(f)
                    venue = data.get("venue")
                    for time, race in data.get("races", {}).items():
                        rid = normalize_rid(race.get("race_id"))
                        if rid:
                            # Update indices if not already present from standard
                            if rid not in self._race_idx:
                                self._race_idx[rid] = {
                                    "course": venue or race.get("course"),
                                    "off_time": self._fmt_time(time),
                                    "race_name": race.get("race_name"),
                                    "source": fpath.name
                                }
                            if rid not in self._runner_idx:
                                self._runner_idx[rid] = race.get("horses", [])
            except Exception:
                pass

        # 3. Local Verdicts (Source of Truth for what was scored)
        vp_files = [
            DATA / f"velo_prime_verdicts_{self.date_token}.json",
            DATA / f"velo_prime_verdicts_{self.date}.json"
        ]
        for fpath in vp_files:
            if fpath.exists():
                try:
                    with open(fpath) as f:
                        v_data = json.load(f)
                        v_list = v_data.get("verdicts", v_data) if isinstance(v_data, dict) else v_data
                        for v in v_list:
                            rid = normalize_rid(v.get("race_id"))
                            if rid and rid not in self._race_idx:
                                self._race_idx[rid] = {
                                    "course": v.get("course"),
                                    "off_time": self._fmt_time(v.get("off_time")),
                                    "race_name": v.get("race_name"),
                                    "source": fpath.name
                                }
                            # We might extract the 'top' horse from full_analysis as a runner
                            fa = v.get("full_analysis")
                            if rid and rid not in self._runner_idx and fa:
                                top = {}
                                if isinstance(fa, dict): top = (fa.get("predictions") or [{}])[0]
                                elif isinstance(fa, list) and fa: top = fa[0]
                                if top: self._runner_idx[rid] = [top]
                except Exception:
                    pass

    def resolve(self, race_id: str, verdict_full_analysis: Any | None = None) -> RaceMetadata:
        rid_norm = normalize_rid(race_id)
        meta = RaceMetadata(race_id=race_id, date=self.date)

        # Priority 1: Supabase
        if self.sb and rid_norm:
            self._from_supabase(meta)

        # Priority 2: Local Index
        if rid_norm in self._race_idx:
            hit = self._race_idx[rid_norm]
            meta.course = meta.course or hit["course"]
            meta.off_time = meta.off_time or hit["off_time"]
            meta.race_name = meta.race_name or hit["race_name"]
            meta.source_used = meta.source_used or hit["source"]

        # Priority 3: Verdict Fallback (last resort)
        if not meta.metadata_complete and verdict_full_analysis:
            self._from_verdict_fallback(meta, verdict_full_analysis)

        # Attach runners for horse name resolution
        if rid_norm in self._runner_idx:
            meta.runners = self._runner_idx[rid_norm]

        meta._evaluate()
        return meta

    def _from_supabase(self, meta: RaceMetadata) -> None:
        try:
            # Try both with and without rac_ prefix
            rids = [meta.race_id]
            if meta.race_id.startswith("rac_"): rids.append(meta.race_id[4:])
            else: rids.append(f"rac_{meta.race_id}")
            
            r = self.sb.table("races").select("course,time,race_name").in_("race_id", rids).execute()
            if r.data:
                row = r.data[0]
                meta.course = row.get("course") or meta.course
                meta.off_time = self._fmt_time(row.get("time")) or meta.off_time
                meta.race_name = row.get("race_name") or meta.race_name
                meta.source_used = "supabase_races"
        except Exception:
            pass

    def _from_verdict_fallback(self, meta: RaceMetadata, full_analysis: Any) -> None:
        top = {}
        if isinstance(full_analysis, dict):
            top = (full_analysis.get("predictions") or [{}])[0]
        elif isinstance(full_analysis, list) and full_analysis:
            top = full_analysis[0]
            
        if not isinstance(top, dict): return
        
        meta.course = meta.course or top.get("course") or top.get("venue")
        meta.off_time = meta.off_time or self._fmt_time(top.get("off_time") or top.get("time"))
        meta.race_name = meta.race_name or top.get("race_name")
        if not meta.source_used: meta.source_used = "verdict_fallback"

    def resolve_batch(self, race_ids: list[str], verdict_map: dict[str, list] | None = None) -> dict[str, RaceMetadata]:
        results = {}
        for rid in race_ids:
            fa = verdict_map.get(rid) if verdict_map else None
            results[rid] = self.resolve(rid, fa)
        return results
