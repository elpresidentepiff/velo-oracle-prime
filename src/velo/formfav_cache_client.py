"""FormFav client that reads what the live worker already stored in Supabase.

The live worker (scripts/ops/formfav_live_worker.py) persists meetings, race
form and predictions to ``formfav_races`` / ``formfav_runner_form`` /
``formfav_predictions``. The UK shadow enrichment job used to call the FormFav
API again for the same data; with one shared, rate-limited key it hit HTTP 429
on /meetings and failed closed with zero enrichment (2026-10-13 and 10-14).

This shim has the same read interface as ``FormFavClient`` for the calls the
enrichment uses. Cache first, live API only on a miss or stale row. Prices and
track bias are not cached and go to the live client when one is available.
Read-only: it never writes to Supabase.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from src.velo.formfav_client import FormFavClient, FormFavError


def race_key(date_str: str, country: str, slug: str, race_no: int) -> str:
    """Same key the live worker writes (keep in sync with formfav_live_worker._race_key)."""
    safe_slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in slug).strip("_")
    return f"formfav:{country}:{date_str}:{safe_slug}:r{race_no}"


def _supabase_get(path: str) -> list[dict[str, Any]]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not url or not key:
        raise FormFavError("cache unavailable: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise FormFavError(f"cache read failed: {type(exc).__name__}: {exc}") from exc


def _parse(ts: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


class CachedFormFavClient:
    def __init__(
        self,
        live: FormFavClient | None = None,
        *,
        max_age_hours: float = 12.0,
        fetch: Callable[[str], list[dict[str, Any]]] = _supabase_get,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.live = live
        self.max_age = timedelta(hours=max_age_hours)
        self._fetch = fetch
        self._now = now
        self.stats = {"cache_hits": 0, "live_fallbacks": 0, "misses": 0}

    # -- helpers ---------------------------------------------------------
    def _fresh(self, ts: Any) -> bool:
        dt = _parse(ts)
        return bool(dt and self._now() - dt <= self.max_age)

    def _fallback(self, name: str, reason: str, **kwargs: Any) -> dict[str, Any]:
        if self.live is None:
            self.stats["misses"] += 1
            raise FormFavError(f"FormFav cache miss ({reason}) and no live client for {name}")
        self.stats["live_fallbacks"] += 1
        return getattr(self.live, name)(**kwargs)

    # -- cached reads ----------------------------------------------------
    def meetings(self, date: str, race_code: str = "gallops", timezone: str = "Europe/London") -> dict[str, Any]:
        qs = urllib.parse.urlencode({
            "race_date": f"eq.{date}",
            "select": "country,track,meeting_slug,metadata,updated_at",
            "limit": "5000",
        })
        rows = self._fetch(f"formfav_races?{qs}")
        fresh = [r for r in rows if self._fresh(r.get("updated_at"))]
        if not fresh:
            if self.live is None:
                self.stats["misses"] += 1
                raise FormFavError("FormFav cache miss (no fresh meetings) and no live client")
            self.stats["live_fallbacks"] += 1
            return self.live.meetings(date, race_code=race_code, timezone=timezone)
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for r in fresh:
            meta = r.get("metadata")
            # metadata is the meeting-race dict itself; older rows nested it.
            mrace = meta.get("meeting_race") if isinstance(meta, dict) and "meeting_race" in meta else meta
            if not isinstance(mrace, dict) or mrace.get("raceNumber") is None:
                continue
            key = (str(r.get("country") or ""), str(r.get("meeting_slug") or r.get("track") or ""))
            m = grouped.setdefault(key, {
                "country": key[0], "track": r.get("track"), "slug": key[1], "races": [],
            })
            m["races"].append(mrace)
        self.stats["cache_hits"] += 1
        return {"meetings": list(grouped.values()), "_source": "formfav_cache"}

    def race_form(
        self, *, date: str, track: str, race: int, country: str,
        race_code: str = "gallops", timezone: str = "Europe/London",
    ) -> dict[str, Any]:
        key = race_key(date, country, track, race)
        enc = urllib.parse.quote(key, safe="")
        races = self._fetch(f"formfav_races?provider_race_key=eq.{enc}&select=metadata,form_meta,updated_at")
        runners = self._fetch(
            f"formfav_runner_form?provider_race_key=eq.{enc}&select=form_payload,updated_at&order=runner_number.asc"
        )
        if races and runners and all(self._fresh(r.get("updated_at")) for r in runners):
            # Race-level fields: meeting-race dict as the base, /form extras on top.
            # (The enrichment already prefers form values and falls back to these.)
            base = races[0].get("metadata") or {}
            meta = {**base, **(races[0].get("form_meta") or {})}
            self.stats["cache_hits"] += 1
            return {**meta, "runners": [r["form_payload"] for r in runners], "_source": "formfav_cache"}
        return self._fallback("race_form", "no fresh row", date=date, track=track, race=race,
                              country=country, race_code=race_code, timezone=timezone)

    def predictions(
        self, *, date: str, track: str, race: int, country: str,
        race_code: str = "gallops", timezone: str = "Europe/London",
    ) -> dict[str, Any]:
        enc = urllib.parse.quote(race_key(date, country, track, race), safe="")
        rows = self._fetch(f"formfav_predictions?provider_race_key=eq.{enc}&select=predictions_payload,updated_at")
        if rows and self._fresh(rows[0].get("updated_at")):
            self.stats["cache_hits"] += 1
            return rows[0]["predictions_payload"]
        return self._fallback("predictions", "no fresh row", date=date, track=track, race=race,
                              country=country, race_code=race_code, timezone=timezone)

    # -- not cached: live only ------------------------------------------
    def prices(self, **kwargs: Any) -> dict[str, Any]:
        return self._fallback("prices", "prices are not cached", **kwargs)

    def track_bias(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if self.live is None:
            raise FormFavError("track bias is not cached and no live client is configured")
        self.stats["live_fallbacks"] += 1
        return self.live.track_bias(*args, **kwargs)

    def results(self, **kwargs: Any) -> dict[str, Any]:
        return self._fallback("results", "results are not cached", **kwargs)


def build_enrichment_client() -> CachedFormFavClient | FormFavClient | None:
    """Cache-first client for the shadow job; None means 'let enrichment build its own'."""
    if os.getenv("FORMFAV_ENRICH_FROM_CACHE", "1").strip() == "0":
        return None
    if not (os.getenv("SUPABASE_URL") and (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY"))):
        return None
    live = None
    if (os.getenv("FORMFAV_API_KEY") or "").strip():
        live = FormFavClient()
    return CachedFormFavClient(live)
