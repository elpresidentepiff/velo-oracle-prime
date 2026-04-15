"""
ingest_rp_stats.py
-------------------
Phase A: Racing Post trainer and jockey stats ingestion.

Fetches RP trainer/jockey stats pages via Jina reader, parses strike rates,
and upserts into rp_trainer_stats + rp_jockey_stats. Also builds entity aliases
(RP ID → Racing API ID) in rp_entity_aliases.

Resolution pipeline:
  1. Load top trainers/jockeys from racing_trainers / racing_jockeys (by runs)
  2. Resolve RP ID via RP autocomplete API (name → rp_id + slug)
  3. Fetch stats page: r.jina.ai/https://racingpost.com/trainers/{id}/{slug}/flat/stats
  4. Parse markdown tables → structured stats dict
  5. Upsert rp_trainer_stats + rp_entity_aliases

Usage:
  python scripts/ingest_rp_stats.py --trainers      # top trainers only
  python scripts/ingest_rp_stats.py --jockeys       # top jockeys only
  python scripts/ingest_rp_stats.py                 # both (default)
  python scripts/ingest_rp_stats.py --top 30        # expand to top-30 entities
  python scripts/ingest_rp_stats.py --trainer-id trn_12345  # single trainer refresh

Rate: max 3 req/sec with jitter. Jina reader handles RP's client-side rendering.
"""

import argparse
import json
import logging
import os
import re
import time
import random
from datetime import datetime
from difflib import SequenceMatcher
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Credentials ────────────────────────────────────────────────────────────────

LEGACY_SCRIPT_STATUS = "QUARANTINED_WAVE_1"
LEGACY_SCRIPT_OWNER = "TBD"
LEGACY_EXECUTION_ENV = "VELO_LEGACY_ALLOW_INGEST_RP_STATS"
SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or ""
JINA_KEY = os.getenv("JINA_API_KEY", "")


def _require_legacy_override() -> None:
    if os.getenv(LEGACY_EXECUTION_ENV) == "1":
        return
    raise SystemExit(
        "Legacy script is quarantined and blocked by default. "
        f"Set {LEGACY_EXECUTION_ENV}=1 for an intentional run."
    )

RP_BASE = "https://www.racingpost.com"
JINA_BASE = "https://r.jina.ai"

# ── Rate limiting ───────────────────────────────────────────────────────────────

_last_request_ts: float = 0.0

def _rate_sleep(min_gap: float = 0.34):
    """Enforce max 3 req/sec with jitter."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    gap = min_gap + random.uniform(0.05, 0.25)
    if elapsed < gap:
        time.sleep(gap - elapsed)
    _last_request_ts = time.monotonic()


# ── HTTP helpers ────────────────────────────────────────────────────────────────

def _fetch_url(url: str, headers: dict | None = None, timeout: int = 30) -> str | None:
    """GET a URL and return response text, or None on error."""
    _rate_sleep()
    is_jina = url.startswith(JINA_BASE)
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/plain,text/html,*/*" if is_jina else "text/html,application/xhtml+xml,*/*",
    }
    if headers:
        req_headers.update(headers)
    if JINA_KEY and is_jina:
        req_headers["Authorization"] = f"Bearer {JINA_KEY}"

    req = Request(url, headers=req_headers)
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        if e.code == 429:
            log.warning("Rate limited on %s — sleeping 15s", url[:80])
            time.sleep(15)
        elif e.code in (403, 404):
            log.debug("HTTP %d on %s", e.code, url[:80])
        else:
            log.error("HTTP %d on %s", e.code, url[:80])
        return None
    except URLError as e:
        log.error("Network error on %s: %s", url[:80], e.reason)
        return None
    except Exception as e:
        log.error("Fetch error on %s: %s", url[:80], e)
        return None


def _fetch_json(url: str, headers: dict | None = None) -> dict | list | None:
    """GET a URL expecting JSON response. Sends Accept: application/json."""
    merged = {"Accept": "application/json"}
    if headers:
        merged.update(headers)
    text = _fetch_url(url, merged)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── Supabase helpers ────────────────────────────────────────────────────────────

_sb_read_headers = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Accept": "application/json",
}
_sb_write_headers = {
    **_sb_read_headers,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def _sb_get_all(table: str, select: str, filters: str = "") -> list[dict]:
    rows, limit, offset = [], 1000, 0
    while True:
        path = f"{SB_URL}/rest/v1/{table}?select={select}&limit={limit}&offset={offset}"
        if filters:
            path += f"&{filters}"
        req = Request(path, headers=_sb_read_headers)
        try:
            with urlopen(req, timeout=30) as r:
                batch = json.loads(r.read().decode())
        except Exception as e:
            log.error("Supabase GET failed on %s: %s", table, e)
            break
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def _sb_upsert(table: str, rows: list[dict], batch: int = 200) -> int:
    if not rows:
        return 0
    written = 0
    url = f"{SB_URL}/rest/v1/{table}"
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        payload = json.dumps(chunk).encode()
        req = Request(url, data=payload, headers=_sb_write_headers, method="POST")
        try:
            with urlopen(req, timeout=30) as r:
                if r.status in (200, 201):
                    written += len(chunk)
        except HTTPError as e:
            log.error("Supabase upsert %s: %d — %s", table, e.code, e.read().decode()[:200])
        except Exception as e:
            log.error("Supabase upsert %s: %s", table, e)
    return written


def _sb_log_run(run_type: str, target_id: str, target_name: str) -> int:
    """Insert ingestion run record and return its ID."""
    rows = [{
        "run_type": run_type,
        "target_id": target_id,
        "target_name": target_name,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
    }]
    url = f"{SB_URL}/rest/v1/rp_ingestion_runs"
    payload = json.dumps(rows).encode()
    headers = {**_sb_write_headers, "Prefer": "return=representation"}
    req = Request(url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30) as r:
            result = json.loads(r.read().decode())
            return result[0]["id"] if result else 0
    except Exception:
        return 0


def _sb_finish_run(run_id: int, status: str, fetched: int, written: int, error: str = ""):
    if not run_id:
        return
    patch = {
        "status": status,
        "finished_at": datetime.utcnow().isoformat(),
        "records_fetched": fetched,
        "records_written": written,
    }
    if error:
        patch["error_note"] = error[:500]
    url = f"{SB_URL}/rest/v1/rp_ingestion_runs?id=eq.{run_id}"
    payload = json.dumps(patch).encode()
    headers = {**_sb_write_headers, "Prefer": "return=minimal"}
    req = Request(url, data=payload, headers=headers, method="PATCH")
    try:
        with urlopen(req, timeout=15):
            pass
    except Exception:
        pass


# ── RP Entity Resolution ────────────────────────────────────────────────────────

def _name_to_slug(name: str) -> str:
    """Convert entity name to RP URL slug format."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def _fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def resolve_rp_trainer(name: str, racing_api_id: str) -> dict | None:
    """
    Find Racing Post trainer ID + slug for a given trainer name.
    Uses RP's autocomplete JSON API. Returns {'rp_id': str, 'slug': str, 'score': float}
    or None if no confident match found.
    """
    # First check aliases cache
    existing = _sb_get_all(
        "rp_entity_aliases",
        "rp_id,alias_value,rp_slug:alias_value",
        f"entity_type=eq.trainer&alias_type=eq.racing_api_id&alias_value=eq.{racing_api_id}"
    )
    # Re-query for the rp_id if racing_api_id is found
    if existing:
        rp_id = existing[0].get("rp_id")
        slug_rows = _sb_get_all(
            "rp_entity_aliases",
            "alias_value",
            f"entity_type=eq.trainer&rp_id=eq.{rp_id}&alias_type=eq.rp_slug"
        )
        slug = slug_rows[0]["alias_value"] if slug_rows else _name_to_slug(name)
        log.debug("  Alias cache hit: %s → rp_id=%s", name, rp_id)
        return {"rp_id": rp_id, "slug": slug, "score": 1.0, "cached": True}

    # RP autocomplete search
    search_url = (
        f"{RP_BASE}/api/search/autocomplete/?term={quote(name)}&searchType=trainer"
    )
    data = _fetch_json(search_url)

    if not data or not isinstance(data, list):
        # Fallback: try search page via Jina
        return _resolve_via_jina_search(name, racing_api_id, "trainer")

    best_match = None
    best_score = 0.0
    for item in data:
        item_name = item.get("name", "") or item.get("label", "")
        score = _fuzzy_score(name, item_name)
        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score >= 0.85:
        rp_id = str(best_match.get("id", "") or best_match.get("trainerUid", ""))
        slug = best_match.get("slug", "") or _name_to_slug(best_match.get("name", name))
        log.info("  Resolved trainer %s → rp_id=%s (score=%.2f)", name, rp_id, best_score)
        return {"rp_id": rp_id, "slug": slug, "score": best_score, "cached": False}

    log.warning("  Could not resolve trainer: %s (best=%.2f)", name, best_score)
    return None


def resolve_rp_jockey(name: str, racing_api_id: str) -> dict | None:
    """Same as trainer resolution but for jockeys."""
    existing = _sb_get_all(
        "rp_entity_aliases",
        "rp_id",
        f"entity_type=eq.jockey&alias_type=eq.racing_api_id&alias_value=eq.{racing_api_id}"
    )
    if existing:
        rp_id = existing[0]["rp_id"]
        slug_rows = _sb_get_all(
            "rp_entity_aliases",
            "alias_value",
            f"entity_type=eq.jockey&rp_id=eq.{rp_id}&alias_type=eq.rp_slug"
        )
        slug = slug_rows[0]["alias_value"] if slug_rows else _name_to_slug(name)
        return {"rp_id": rp_id, "slug": slug, "score": 1.0, "cached": True}

    search_url = (
        f"{RP_BASE}/api/search/autocomplete/?term={quote(name)}&searchType=jockey"
    )
    data = _fetch_json(search_url)

    if not data or not isinstance(data, list):
        return _resolve_via_jina_search(name, racing_api_id, "jockey")

    best_match = None
    best_score = 0.0
    for item in data:
        item_name = item.get("name", "") or item.get("label", "")
        score = _fuzzy_score(name, item_name)
        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score >= 0.85:
        rp_id = str(best_match.get("id", "") or best_match.get("jockeyUid", ""))
        slug = best_match.get("slug", "") or _name_to_slug(best_match.get("name", name))
        log.info("  Resolved jockey %s → rp_id=%s (score=%.2f)", name, rp_id, best_score)
        return {"rp_id": rp_id, "slug": slug, "score": best_score, "cached": False}

    log.warning("  Could not resolve jockey: %s (best=%.2f)", name, best_score)
    return None


def _resolve_via_jina_search(name: str, racing_api_id: str, entity_type: str) -> dict | None:
    """
    Fallback: fetch RP search page via Jina reader and extract entity ID from text.
    Handles cases where the autocomplete JSON API is gated or returns unexpected format.
    """
    path_type = "trainers" if entity_type == "trainer" else "jockeys"
    search_url = f"{RP_BASE}/{path_type}/search/?search={quote(name)}"
    jina_url = f"{JINA_BASE}/{search_url}"

    text = _fetch_url(jina_url)
    if not text:
        log.warning("  Jina fallback: empty response for %s %s", entity_type, name)
        return None

    # Look for RP entity URLs in the text: /trainers/12345/name-slug
    pattern = rf"/{path_type}/(\d+)/([a-z0-9][a-z0-9-]{{2,}})"
    matches = re.findall(pattern, text)
    if not matches:
        log.warning("  Jina fallback: no %s IDs found in page for '%s' (page len=%d)", entity_type, name, len(text))
        return None

    # Deduplicate
    seen = set()
    unique_matches = []
    for m in matches:
        if m[0] not in seen:
            seen.add(m[0])
            unique_matches.append(m)

    # Score each match against the target name
    best_rp_id, best_slug, best_score = None, None, 0.0
    for rp_id, slug in unique_matches:
        candidate_name = slug.replace("-", " ")
        score = _fuzzy_score(name, candidate_name)
        if score > best_score:
            best_score = score
            best_rp_id = rp_id
            best_slug = slug

    log.debug("  Jina fallback candidates for %s: %s", name, [(m[0], m[1]) for m in unique_matches[:5]])

    if best_rp_id and best_score >= 0.70:
        log.info("  Jina fallback resolved %s %s → rp_id=%s (score=%.2f)",
                 entity_type, name, best_rp_id, best_score)
        return {"rp_id": best_rp_id, "slug": best_slug, "score": best_score, "cached": False}

    log.warning("  Jina fallback: best score %.2f below threshold for %s '%s'", best_score, entity_type, name)
    return None


def save_entity_aliases(entity_type: str, rp_id: str, racing_api_id: str,
                        slug: str, name: str, score: float):
    """Write all alias types for a resolved entity to rp_entity_aliases."""
    aliases = [
        {
            "entity_type": entity_type,
            "rp_id": rp_id,
            "alias_type": "racing_api_id",
            "alias_value": racing_api_id,
            "match_score": round(score, 3),
            "verified": score >= 0.99,
        },
        {
            "entity_type": entity_type,
            "rp_id": rp_id,
            "alias_type": "rp_slug",
            "alias_value": slug,
            "match_score": None,
            "verified": True,
        },
        {
            "entity_type": entity_type,
            "rp_id": rp_id,
            "alias_type": "name_canonical",
            "alias_value": name,
            "match_score": round(score, 3),
            "verified": score >= 0.99,
        },
    ]
    _sb_upsert("rp_entity_aliases", aliases)


# ── RP Stats Page Parsing ───────────────────────────────────────────────────────

def fetch_stats_page(entity_type: str, rp_id: str, slug: str) -> str | None:
    """
    Fetch trainer or jockey stats page via Jina reader.
    Returns raw markdown text.
    """
    path_type = "trainers" if entity_type == "trainer" else "jockeys"
    # RP stats URL patterns:
    # /trainers/{id}/{slug}/flat/stats
    # /jockeys/{id}/{slug}/stats
    if entity_type == "trainer":
        rp_url = f"{RP_BASE}/{path_type}/{rp_id}/{slug}/flat/stats"
    else:
        rp_url = f"{RP_BASE}/{path_type}/{rp_id}/{slug}/stats"

    jina_url = f"{JINA_BASE}/{rp_url}"
    log.debug("  Fetching: %s", jina_url[:100])

    text = _fetch_url(jina_url)
    if not text or len(text) < 200:
        # Try without discipline suffix
        if entity_type == "trainer":
            rp_url_alt = f"{RP_BASE}/{path_type}/{rp_id}/{slug}/stats"
            text = _fetch_url(f"{JINA_BASE}/{rp_url_alt}")

    return text


def _parse_percentage(s: str) -> float | None:
    """Extract float from strings like '14%', '14.3%', '14'."""
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s.replace(",", ""))
    if m:
        return float(m.group(1))
    return None


def _parse_fraction(s: str) -> tuple[int, int] | None:
    """Extract (wins, runs) from strings like '14/97', '14-97'."""
    m = re.search(r"(\d+)[/\-](\d+)", s.replace(",", ""))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def parse_trainer_stats(text: str, trainer_name: str) -> dict:
    """
    Parse Jina-rendered RP trainer stats page markdown into structured stats dict.

    RP stats page structure (as markdown):
    - "Last 14 days" section: runs/wins table
    - "Last 30 days" section
    - "Last 6 months" section
    - "By days since last run" table
    - "By going" table
    - "By race type" table

    Returns a dict of stat fields or an empty dict on parse failure.
    """
    stats: dict = {}
    if not text:
        return stats

    lines = text.splitlines()
    text_lower = text.lower()

    # ── Rolling windows ──────────────────────────────────────────────────────
    # RP stat tables render in markdown roughly as:
    # | Period | Runners | Wins | Win% | Places | Place% |
    # We scan for known section headers and extract the first data row.

    window_patterns = [
        ("14d",  ["last 14 day", "14 day"]),
        ("30d",  ["last 30 day", "30 day"]),
        ("180d", ["last 6 month", "6 month", "180 day"]),
    ]

    for key, keywords in window_patterns:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(kw in ll for kw in keywords):
                # Look at next 5 lines for a data row with numbers
                for j in range(i + 1, min(i + 6, len(lines))):
                    data_line = lines[j]
                    fracs = re.findall(r"(\d+)[/\-](\d+)", data_line)
                    pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", data_line)
                    nums = re.findall(r"\b(\d+)\b", data_line)
                    if len(nums) >= 2:
                        try:
                            runs = int(nums[0])
                            wins = int(nums[1])
                            if runs > 0:
                                stats[f"runs_{key}"] = runs
                                stats[f"wins_{key}"] = wins
                                stats[f"win_rate_{key}"] = round(
                                    (pcts and float(pcts[0])) or (wins / runs * 100), 1
                                )
                                break
                        except (ValueError, IndexError):
                            pass
                break

    # ── Days-since-last-run buckets ──────────────────────────────────────────
    # Rows like: | 8-21 days | 45 | 7 | 15.6% |
    rest_patterns = [
        ("win_rate_8_21d",   ["8-21", "8 to 21", "8–21"]),
        ("win_rate_22_45d",  ["22-45", "22 to 45", "22–45"]),
        ("win_rate_46_90d",  ["46-90", "46 to 90", "46–90"]),
        ("win_rate_90d_plus",["90+", "90 days+", "over 90"]),
    ]
    for stat_key, keywords in rest_patterns:
        for line in lines:
            ll = line.lower()
            if any(kw in ll for kw in keywords):
                pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", line)
                if pcts:
                    stats[stat_key] = float(pcts[0])
                    break
                nums = re.findall(r"\b(\d+)\b", line)
                if len(nums) >= 2:
                    try:
                        r, w = int(nums[0]), int(nums[1])
                        if r > 0:
                            stats[stat_key] = round(w / r * 100, 1)
                        break
                    except (ValueError, IndexError):
                        pass

    # ── Going stats ──────────────────────────────────────────────────────────
    going_patterns = [
        ("win_rate_good_plus",  ["good to firm", "good/firm", "firm"]),
        ("win_rate_soft_plus",  ["soft", "heavy", "good to soft", "yielding"]),
        ("win_rate_aw",         ["standard", "all weather", "tapeta", "polytrack", "fibresand"]),
    ]
    for stat_key, keywords in going_patterns:
        best_pct = None
        for line in lines:
            ll = line.lower()
            if any(kw in ll for kw in keywords):
                pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", line)
                if pcts:
                    val = float(pcts[0])
                    if best_pct is None or val > best_pct:
                        best_pct = val
        if best_pct is not None:
            stats[stat_key] = best_pct

    # ── Top courses ──────────────────────────────────────────────────────────
    # Look for a courses table and extract top 5 course names
    course_section = False
    course_names = []
    for i, line in enumerate(lines):
        ll = line.lower()
        if "course" in ll and ("win" in ll or "%" in ll):
            course_section = True
        if course_section:
            # Course names in RP tables tend to be title-case non-numeric cells
            m = re.search(r"\|\s*([A-Z][a-zA-Z\s]+)\s*\|", line)
            if m:
                cn = m.group(1).strip()
                if cn and len(cn) > 2 and cn not in ("Course", "Runners", "Wins"):
                    course_names.append(cn)
            if len(course_names) >= 5:
                break

    if course_names:
        stats["top_courses"] = course_names[:5]

    # ── Stable heat flag ─────────────────────────────────────────────────────
    r14 = stats.get("win_rate_14d")
    r30 = stats.get("win_rate_30d")
    if r14 is not None and r30 is not None and r30 > 0:
        heat_score = round((r14 / r30) - 1.0, 3)
        stats["stable_heat_score"] = heat_score
        stats["stable_heat_flag"] = heat_score >= 0.20  # 20% above baseline = warming

    log.debug("  Parsed %d stats fields for %s", len(stats), trainer_name)
    return stats


def parse_jockey_stats(text: str, jockey_name: str) -> dict:
    """Parse Jina-rendered RP jockey stats page markdown."""
    stats: dict = {}
    if not text:
        return stats

    lines = text.splitlines()

    # Rolling windows — same structure as trainer
    window_patterns = [
        ("14d",  ["last 14 day", "14 day"]),
        ("30d",  ["last 30 day", "30 day"]),
        ("180d", ["last 6 month", "6 month"]),
    ]
    for key, keywords in window_patterns:
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(kw in ll for kw in keywords):
                for j in range(i + 1, min(i + 6, len(lines))):
                    data_line = lines[j]
                    pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", data_line)
                    nums = re.findall(r"\b(\d+)\b", data_line)
                    if len(nums) >= 2:
                        try:
                            runs = int(nums[0])
                            wins = int(nums[1])
                            if runs > 0:
                                stats[f"runs_{key}"] = runs
                                stats[f"wins_{key}"] = wins
                                stats[f"win_rate_{key}"] = round(
                                    (pcts and float(pcts[0])) or (wins / runs * 100), 1
                                )
                                break
                        except (ValueError, IndexError):
                            pass
                break

    # Going stats
    going_patterns = [
        ("win_rate_good_plus",  ["good to firm", "good/firm", "firm"]),
        ("win_rate_soft_plus",  ["soft", "heavy", "yielding"]),
        ("win_rate_aw",         ["standard", "all weather", "tapeta", "polytrack"]),
    ]
    for stat_key, keywords in going_patterns:
        best_pct = None
        for line in lines:
            if any(kw in line.lower() for kw in keywords):
                pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", line)
                if pcts:
                    val = float(pcts[0])
                    if best_pct is None or val > best_pct:
                        best_pct = val
        if best_pct is not None:
            stats[stat_key] = best_pct

    # Distance bands
    dist_patterns = [
        ("win_rate_sprint",  ["5f", "6f", "sprint"]),
        ("win_rate_middle",  ["7f", "8f", "9f", "10f", "mile", "middle"]),
        ("win_rate_stayer",  ["12f", "13f", "14f", "stayer", "2m"]),
    ]
    for stat_key, keywords in dist_patterns:
        best_pct = None
        for line in lines:
            if any(kw in line.lower() for kw in keywords):
                pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", line)
                if pcts:
                    val = float(pcts[0])
                    if best_pct is None or val > best_pct:
                        best_pct = val
        if best_pct is not None:
            stats[stat_key] = best_pct

    # Top courses
    course_names = []
    course_section = False
    for line in lines:
        ll = line.lower()
        if "course" in ll and ("win" in ll or "%" in ll):
            course_section = True
        if course_section:
            m = re.search(r"\|\s*([A-Z][a-zA-Z\s]+)\s*\|", line)
            if m:
                cn = m.group(1).strip()
                if cn and len(cn) > 2 and cn not in ("Course", "Runners", "Wins"):
                    course_names.append(cn)
            if len(course_names) >= 5:
                break
    if course_names:
        stats["top_courses"] = course_names[:5]

    log.debug("  Parsed %d stats fields for %s", len(stats), jockey_name)
    return stats


# ── Main entity processors ──────────────────────────────────────────────────────

def process_trainer(trainer: dict, dry_run: bool = False) -> bool:
    """Resolve, fetch, parse and upsert one trainer. Returns True on success."""
    racing_api_id = trainer["id"]
    name = trainer["name"]
    log.info("Processing trainer: %s (%s)", name, racing_api_id)

    run_id = _sb_log_run("trainer_stats", racing_api_id, name)

    # Resolve RP entity
    resolved = resolve_rp_trainer(name, racing_api_id)
    if not resolved:
        _sb_finish_run(run_id, "fail", 0, 0, "could not resolve RP entity")
        return False

    rp_id = resolved["rp_id"]
    slug = resolved["slug"]
    score = resolved["score"]

    if not rp_id:
        _sb_finish_run(run_id, "fail", 0, 0, "empty RP ID after resolution")
        return False

    # Save aliases (even if we skip stats fetch)
    if not resolved.get("cached") and not dry_run:
        save_entity_aliases("trainer", rp_id, racing_api_id, slug, name, score)

    # Fetch stats page
    text = fetch_stats_page("trainer", rp_id, slug)
    if not text:
        _sb_finish_run(run_id, "fail", 1, 0, "stats page fetch failed")
        return False

    # Parse stats
    stats = parse_trainer_stats(text, name)
    if not stats:
        log.warning("  No stats parsed for %s — page may be gated", name)
        _sb_finish_run(run_id, "partial", 1, 0, "page returned but 0 stats parsed")
        return False

    # Build upsert row
    row = {
        "rp_trainer_id": rp_id,
        "racing_api_id": racing_api_id,
        "trainer_name": name,
        "rp_slug": slug,
        "updated_at": datetime.utcnow().isoformat(),
        **{k: v for k, v in stats.items()},
    }

    if dry_run:
        log.info("  [DRY RUN] Would upsert: %s", {k: v for k, v in row.items() if k not in ("rp_trainer_id",)})
        _sb_finish_run(run_id, "pass", 1, 0)
        return True

    written = _sb_upsert("rp_trainer_stats", [row])
    _sb_finish_run(run_id, "pass" if written else "fail", 1, written)
    log.info("  Upserted trainer stats: %s (%d fields)", name, len(stats))
    return written > 0


def process_jockey(jockey: dict, dry_run: bool = False) -> bool:
    """Resolve, fetch, parse and upsert one jockey. Returns True on success."""
    racing_api_id = jockey["id"]
    name = jockey["name"]
    claim = jockey.get("claim_lbs") or 0
    log.info("Processing jockey: %s (%s)", name, racing_api_id)

    run_id = _sb_log_run("jockey_stats", racing_api_id, name)

    resolved = resolve_rp_jockey(name, racing_api_id)
    if not resolved:
        _sb_finish_run(run_id, "fail", 0, 0, "could not resolve RP entity")
        return False

    rp_id = resolved["rp_id"]
    slug = resolved["slug"]
    score = resolved["score"]

    if not rp_id:
        _sb_finish_run(run_id, "fail", 0, 0, "empty RP ID after resolution")
        return False

    if not resolved.get("cached") and not dry_run:
        save_entity_aliases("jockey", rp_id, racing_api_id, slug, name, score)

    text = fetch_stats_page("jockey", rp_id, slug)
    if not text:
        _sb_finish_run(run_id, "fail", 1, 0, "stats page fetch failed")
        return False

    stats = parse_jockey_stats(text, name)
    if not stats:
        log.warning("  No stats parsed for %s", name)
        _sb_finish_run(run_id, "partial", 1, 0, "page returned but 0 stats parsed")
        return False

    row = {
        "rp_jockey_id": rp_id,
        "racing_api_id": racing_api_id,
        "jockey_name": name,
        "rp_slug": slug,
        "claim_lbs": claim,
        "updated_at": datetime.utcnow().isoformat(),
        **{k: v for k, v in stats.items()},
    }

    if dry_run:
        log.info("  [DRY RUN] Would upsert: %s", {k: v for k, v in row.items() if k not in ("rp_jockey_id",)})
        _sb_finish_run(run_id, "pass", 1, 0)
        return True

    written = _sb_upsert("rp_jockey_stats", [row])
    _sb_finish_run(run_id, "pass" if written else "fail", 1, written)
    log.info("  Upserted jockey stats: %s (%d fields)", name, len(stats))
    return written > 0


# ── Entry point ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest Racing Post trainer/jockey stats (Phase A)")
    parser.add_argument("--trainers",    action="store_true", help="Process trainers")
    parser.add_argument("--jockeys",     action="store_true", help="Process jockeys")
    parser.add_argument("--top",         type=int, default=20, help="Top N entities by runs (default: 20)")
    parser.add_argument("--min-runs",    type=int, default=50, help="Min runs in 180d to qualify (default: 50)")
    parser.add_argument("--trainer-id",  type=str, default="", help="Process single trainer by Racing API ID")
    parser.add_argument("--jockey-id",   type=str, default="", help="Process single jockey by Racing API ID")
    parser.add_argument("--dry-run",     action="store_true", help="Parse but do not write to Supabase")
    args = parser.parse_args()

    # Default: both if neither flag set
    do_trainers = args.trainers or (not args.trainers and not args.jockeys)
    do_jockeys  = args.jockeys  or (not args.trainers and not args.jockeys)

    results: dict[str, list[str]] = {"ok": [], "fail": [], "skip": []}

    # ── Trainers ──────────────────────────────────────────────────────────────
    if do_trainers:
        if args.trainer_id:
            rows = _sb_get_all(
                "racing_trainers",
                "id,name",
                f"id=eq.{args.trainer_id}"
            )
        else:
            rows = _sb_get_all(
                "racing_trainers",
                "id,name,runs",
                f"runs=gte.{args.min_runs}&order=runs.desc&limit={args.top}"
            )

        log.info("Trainers to process: %d", len(rows))
        for row in rows:
            ok = process_trainer(row, dry_run=args.dry_run)
            (results["ok"] if ok else results["fail"]).append(row["name"])

    # ── Jockeys ───────────────────────────────────────────────────────────────
    if do_jockeys:
        if args.jockey_id:
            rows = _sb_get_all(
                "racing_jockeys",
                "id,name",
                f"id=eq.{args.jockey_id}"
            )
        else:
            rows = _sb_get_all(
                "racing_jockeys",
                "id,name,runs",
                f"runs=gte.{args.min_runs}&order=runs.desc&limit={args.top}"
            )

        log.info("Jockeys to process: %d", len(rows))
        for row in rows:
            ok = process_jockey(row, dry_run=args.dry_run)
            (results["ok"] if ok else results["fail"]).append(row["name"])

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(results["ok"]) + len(results["fail"])
    print(f"\n{'='*55}")
    print("  RP STATS INGESTION SUMMARY")
    print(f"{'='*55}")
    print(f"  Processed : {total}")
    print(f"  OK        : {len(results['ok'])}")
    print(f"  Failed    : {len(results['fail'])}")
    if results["fail"]:
        print(f"  Failed entities: {', '.join(results['fail'][:10])}")
    print(f"{'='*55}")


if __name__ == "__main__":
    _require_legacy_override()
    main()
