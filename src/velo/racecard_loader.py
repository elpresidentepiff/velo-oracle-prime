"""
VÉLØ Racecard Loader — source-contract fix (Issue #83).

Provides load_racecards() with a strict priority order and clear fallback doctrine:

  Source order (auto):
    1. data/racecards_{date_tag}_standard.json     → 'cache'
    2. data/racecard_merged/racecard_*_{date}.json → 'rp_merged'
    3. Racing API /racecards/standard               → 'api'

  CLI / env overrides:
    --source cache|rp|api|auto
    VELO_RACECARD_SOURCE=cache|rp|api|auto
    VELO_DISABLE_RACING_API=1

  API 401/403: hard-fail — in auto mode the API is only reached when both
  cache and RP merged are absent, so there is no local source to fall back to.

Hard constraints:
  No scoring changes. No routing changes. No execution changes.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

# Known Irish venue codes — everything else is treated as GB
_IRE_VENUE_CODES = frozenset({
    "GOW", "LEO", "NAV", "CUR", "TIP", "GAL", "KIL", "BAL", "BEL",
    "CLO", "DUN", "FAI", "LIM", "NAA", "PAR", "ROS", "SLI", "THU",
    "WEX", "NAS", "DRO", "MUS", "SAL", "CAR", "FFA", "GRA", "KIG",
    "PTK",
})


def _parse_betting_forecast(forecast_str: str | None) -> dict[str, float]:
    """
    Parse a RP betting forecast string into {horse_name_lower: decimal_odds}.

    Handles: "4/6 One Knight, 5/2 The Flaggy Shore, 100/1 Kenobi"
             "EVS Bluegrass, 2/1 Crystal Queen" (EVS = 2.0)
    Strips favourite markers (F, JF, CF) from odds tokens.
    Segments that cannot be parsed are skipped; returns {} for None/empty input.
    """
    if not forecast_str:
        return {}
    result: dict[str, float] = {}
    for part in forecast_str.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split(None, 1)
        if len(tokens) != 2:
            continue
        odds_tok, horse_name = tokens
        # Strip favourite markers (trailing F, JF, CF)
        odds_tok = odds_tok.rstrip("FJCfjc")
        try:
            if odds_tok.upper() in ("EVS", "EVENS"):
                dec = 2.0
            elif "/" in odds_tok:
                num, den = odds_tok.split("/")
                dec = round(int(num) / int(den) + 1, 3)
            else:
                dec = round(float(odds_tok) + 1, 3)
            result[horse_name.strip().lower()] = dec
        except (ValueError, ZeroDivisionError):
            continue
    return result


def _fuzzy_odds_lookup(name: str, forecast_odds: dict[str, float]) -> float:
    """
    Look up a horse's forecast odds by fuzzy name match (strips non-alpha chars).

    Returns 0.0 when no match found (caller uses 0.0 as 'odds unavailable').
    """
    import re as _re
    if not forecast_odds:
        return 0.0
    name_key = _re.sub(r"[^a-z]", "", name.lower())
    for fname, dec in forecast_odds.items():
        fname_key = _re.sub(r"[^a-z]", "", fname)
        if fname_key == name_key or (len(fname_key) > 4 and (fname_key in name_key or name_key in fname_key)):
            return dec
    return 0.0


def load_rp_merged_as_racecards(date_str: str, data_root: Path) -> list[dict[str, Any]]:
    """
    Synthesise Racing API-compatible race dicts from RP merged JSON files.

    Reads all {data_root}/racecard_merged/racecard_*_{date_str}.json files and
    builds race dicts with enough structure for normalize_race() to process.

    Hydration improvements (Issue #85 — RP_MERGED differentiation collapse):
      - betting_forecast parsed and injected as per-horse "odds" → normalizer
        converts to best_odds_decimal, driving sp_dec/sp_rank differentiation
      - ts_latest, ts_master wired as "ts" and "ts_master" for TS-based scoring
      - postdata_score, or_compression_score, plot_conviction wired as "pdf_intel"
        so _build_live_features() reads them on the first pass
      - going and race_class extracted from race_info when present

    Fields absent from RP data remain None. Sets region="IRE" for Irish venues.
    Returns an empty list if no RP merged files exist for the date.
    """
    import re as _re

    merged_dir = data_root / "racecard_merged"
    rp_files = list(merged_dir.glob(f"racecard_*_{date_str}.json"))
    if not rp_files:
        return []

    races: list[dict[str, Any]] = []
    for rp_path in sorted(rp_files):
        try:
            rp = json.loads(rp_path.read_text())
        except Exception:
            continue

        venue_name: str = rp.get("venue", rp_path.stem.split("_")[1])
        venue_code: str = rp_path.stem.split("_")[1].upper()
        region = "IRE" if venue_code in _IRE_VENUE_CODES else "GB"

        for race_time, race_data in rp.get("races", {}).items():
            horses = race_data.get("horses", [])
            if not horses:
                continue

            # ── Betting forecast → per-horse odds ────────────────────────────
            forecast_raw = race_data.get("betting_forecast", "")
            forecast_odds = _parse_betting_forecast(forecast_raw)

            # ── Race-level metadata ───────────────────────────────────────────
            race_info = race_data.get("race_info", "")
            going_str: str | None = None
            race_class: str | None = None
            m_going = _re.search(r"\b(Good|Firm|Soft|Heavy|Yielding|Standard)[^\)]*", race_info, _re.I)
            if m_going:
                going_str = m_going.group(0).strip()
            m_class = _re.search(r"Class\s*(\d)", race_info, _re.I)
            if m_class:
                race_class = m_class.group(1)

            runners = []
            for h in horses:
                name = h.get("horse_name") or h.get("horse", "")
                if not name:
                    continue

                # Odds from betting forecast
                odds_dec = _fuzzy_odds_lookup(name, forecast_odds)

                # TS: prefer ts_latest, fall back to ts_adjusted / ts_master
                ts_val = (
                    h.get("ts_latest")
                    or h.get("ts_adjusted")
                    or h.get("ts_master")
                )

                # Build pdf_intel dict for immediate use in _build_live_features()
                pdf_intel: dict[str, Any] = {
                    "postdata_score": h.get("postdata_score", 0.0) or 0.0,
                    "or_compression_score": h.get("or_compression_score", 0.0) or 0.0,
                    "plot_conviction": h.get("plot_conviction", 0.0) or 0.0,
                    "ts_master": float(h.get("ts_master") or h.get("ts_adjusted") or 0),
                    "or_delta_to_best_win": 0.0,
                    "trainer_form_signal": h.get("trainer_form_signal", 0.0) or 0.0,
                    "ts_trend_signal": h.get("ts_trend_signal", 0.0) or 0.0,
                    "or_trend_signal": h.get("or_trend_signal", 0.0) or 0.0,
                    "handicap_plot_score": h.get("handicap_plot_score") or 0.0,
                    # Pass through the raw RP horse dict for downstream enrichment
                    "_rp_raw": h,
                }

                runners.append({
                    "horse": name,
                    "horse_id": f"rp_{venue_code}_{name.lower().replace(' ', '_')}",
                    "age": h.get("age") or None,
                    "sex": None,
                    "lbs": None,
                    "draw": None,
                    "trainer": None,
                    "jockey": None,
                    "ofr": h.get("current_or") or None,
                    # RP-derived RPR is archive/context only. Do not expose it as
                    # live runner["rpr"], because downstream scoring consumes that key.
                    "rpr": None,
                    "rp_rpr_archive_only": h.get("rpr_master") or None,
                    "rp_rpr_velo_allowed": False,
                    "ts": ts_val,
                    "ts_master": h.get("ts_master"),
                    "form": None,
                    "last_run": None,
                    # Odds: set so normalizer converts to best_odds_decimal
                    "odds": odds_dec if odds_dec > 0 else None,
                    # RP passthrough fields
                    "_rp_horse_name": name,
                    "_rp_ts_base": h.get("ts_base"),
                    "_rp_plot_conviction": h.get("plot_conviction"),
                    "_rp_or_compression_score": h.get("or_compression_score"),
                    "_rp_postdata_score": h.get("postdata_score"),
                    # Pre-built pdf_intel so _build_live_features() reads it immediately
                    # (before the post-normalization pdf_intel_cache loop runs)
                    "pdf_intel": pdf_intel,
                })

            time_parts = race_time.replace(":", "_")
            races.append({
                "race_id": f"rp_{venue_code}_{date_str.replace('-', '')}_{time_parts}",
                "course": venue_name,
                "course_id": venue_code.lower(),
                "date": date_str,
                "off_time": race_time,
                "race_name": race_info[:80],
                "distance_f": None,
                "going": going_str,
                "race_class": race_class,
                "region": region,
                "runners": runners,
                # Keep raw forecast for diagnostics
                "_rp_betting_forecast": forecast_raw,
            })

    return races


def fetch_api_racecards(
    date_str: str,
    date_tag: str,
    data_root: Path,
    racing_base: str,
    racing_user: str,
    racing_pass: str,
) -> tuple[list[dict[str, Any]], str]:
    """
    Fetch racecards from Racing API. Caches response locally. Returns (races, 'api').

    Raises RuntimeError on 401/403 or missing credentials.
    """
    cache_path = data_root / f"racecards_{date_tag}_standard.json"

    if not racing_user or not racing_pass:
        raise RuntimeError(
            "Racing API credentials not set and no local racecard source found.\n"
            f"  Expected cache:    {cache_path}\n"
            f"  Expected RP merged: {data_root}/racecard_merged/racecard_*_{date_str}.json\n"
            "  Set VELO_DISABLE_RACING_API=1 to suppress this error when running RP-only."
        )

    from datetime import date as _date
    _today = str(_date.today())
    if date_str == _today:
        qs = urlencode({"day": "today"})
    elif date_str > _today:
        qs = ""
    else:
        qs = urlencode({"date": date_str})
    url = f"{racing_base}/racecards/standard" + (f"?{qs}" if qs else "")

    import ssl as _ssl
    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    _creds = base64.b64encode(f"{racing_user}:{racing_pass}".encode()).decode()
    _req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {_creds}",
            "Accept": "application/json",
            "User-Agent": "VeloPrime/1.0",
        },
    )
    try:
        with urllib.request.urlopen(_req, context=_ctx, timeout=30) as resp:
            raw = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(
                f"Racing API returned {exc.code} — subscription/credentials issue.\n"
                "  VELO_DISABLE_RACING_API=1 suppresses API calls and uses cache/RP source."
            ) from exc
        raise

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(raw, indent=2))
    except Exception:
        pass

    races = raw if isinstance(raw, list) else raw.get("racecards", [])
    return races, "api"


def _sanitize_api_rpr(races: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sanitize bare live RPR from Racing API / cache runner payloads.

    Racing API racecards carry a live 'rpr' field on each runner.
    VÉLØ scoring policy: rpr_policy = RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO.
    Live RPR must never enter the scoring formula.

    This function:
      - Moves runner['rpr'] → runner['rp_rpr_archive_only'] (preserves the value for audit)
      - Sets runner['rpr'] = None (scoring treats it as missing)
      - Sets runner['rp_rpr_velo_allowed'] = False (explicit scoring block)

    Skipped when VELO_ALLOW_API_RPR=1 (archive / test mode only).
    RP-merged races never pass through this function — they are already sanitized.
    """
    if os.getenv("VELO_ALLOW_API_RPR", "").strip() in ("1", "true", "yes"):
        return races

    for race in races:
        race.setdefault("rpr_policy", "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO")
        for runner in race.get("runners") or []:
            live_rpr = runner.get("rpr")
            if live_rpr is not None:
                runner.setdefault("rp_rpr_archive_only", live_rpr)
                runner["rpr"] = None
            runner["rp_rpr_velo_allowed"] = False
    return races


def load_racecards(
    date_tag: str,
    date_str: str,
    data_root: Path,
    racing_base: str,
    racing_user: str,
    racing_pass: str,
    source: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Return (races_list, source_label) for the given date.

    Source priority (auto):
      1. data/racecards_{date_tag}_standard.json  → 'cache'
      2. data/racecard_merged/racecard_*_{date_str}.json  → 'rp_merged'
      3. Racing API  → 'api'

    RPR sanitization: cache and api sources are always sanitized via
    _sanitize_api_rpr() before return. rp_merged is already clean.
    Override: VELO_ALLOW_API_RPR=1 disables sanitization (archive/test only).

    Env overrides:
      VELO_RACECARD_SOURCE=cache|rp|api|auto
      VELO_DISABLE_RACING_API=1
      VELO_ALLOW_API_RPR=1

    source labels returned: 'cache' | 'rp_merged' | 'api'
    """
    _source = (source or os.getenv("VELO_RACECARD_SOURCE", "auto")).lower()
    _disable_api = os.getenv("VELO_DISABLE_RACING_API", "").strip() in ("1", "true", "yes")
    cache_path = data_root / f"racecards_{date_tag}_standard.json"

    if _source == "cache":
        if not cache_path.exists():
            raise RuntimeError(f"--source cache specified but {cache_path} not found")
        raw = json.loads(cache_path.read_text())
        races = raw if isinstance(raw, list) else raw.get("racecards", [])
        return _sanitize_api_rpr(races), "cache"

    if _source == "rp":
        races = load_rp_merged_as_racecards(date_str, data_root)
        if not races:
            raise RuntimeError(
                f"--source rp specified but no RP merged files found for {date_str}\n"
                f"  Expected: {data_root}/racecard_merged/racecard_*_{date_str}.json"
            )
        return races, "rp_merged"  # already sanitized — no _sanitize_api_rpr needed

    if _source == "api":
        if _disable_api:
            raise RuntimeError("--source api requested but VELO_DISABLE_RACING_API=1")
        races, src = fetch_api_racecards(date_str, date_tag, data_root, racing_base, racing_user, racing_pass)
        return _sanitize_api_rpr(races), src

    # ── Auto: cache → rp_merged → api ─────────────────────────────────────────
    if cache_path.exists():
        raw = json.loads(cache_path.read_text())
        races = raw if isinstance(raw, list) else raw.get("racecards", [])
        return _sanitize_api_rpr(races), "cache"

    rp_races = load_rp_merged_as_racecards(date_str, data_root)
    if rp_races:
        return rp_races, "rp_merged"  # already sanitized

    if _disable_api:
        raise RuntimeError(
            f"VELO_DISABLE_RACING_API=1: no cache and no RP merged files for {date_str}.\n"
            f"  Cache expected:    {cache_path}\n"
            f"  RP merged expected: {data_root}/racecard_merged/racecard_*_{date_str}.json"
        )

    try:
        races, src = fetch_api_racecards(date_str, date_tag, data_root, racing_base, racing_user, racing_pass)
        return _sanitize_api_rpr(races), src
    except RuntimeError as exc:
        raise RuntimeError(
            f"No racecard source available for {date_str}.\n"
            f"  Tried: cache ({cache_path.name}) → RP merged → Racing API\n"
            f"  API error: {exc}\n"
            "  Fix: supply a cache file, run RP PDF ingestion, or check Racing API credentials."
        ) from exc
