"""FormFav REST client for VÉLØ.

Server-side only. Authentication uses FORMFAV_API_KEY in the X-API-Key header.
No key values are ever logged or returned.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE = "https://api.formfav.com"


class FormFavError(RuntimeError):
    pass


class FormFavClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 30):
        self.api_key = (api_key or os.getenv("FORMFAV_API_KEY") or "").strip()
        self.base_url = (base_url or os.getenv("FORMFAV_API_BASE_URL") or DEFAULT_BASE).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise FormFavError("FORMFAV_API_KEY is not configured")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        req = urllib.request.Request(
            f"{self.base_url}{path}?{qs}",
            headers={
                "X-API-Key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "VELO-Oracle-Prime/railway",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            if exc.code in (401, 403):
                raise FormFavError(f"FormFav authorization failed HTTP {exc.code}: {detail}") from exc
            if exc.code == 429:
                raise FormFavError("FormFav rate limit exceeded (HTTP 429)") from exc
            raise FormFavError(f"FormFav HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise FormFavError(f"FormFav request failed: {type(exc).__name__}: {exc}") from exc
        if not isinstance(payload, dict):
            raise FormFavError(f"FormFav returned unexpected payload type for {path}")
        return payload

    def meetings(self, date: str, race_code: str = "gallops", timezone: str = "Europe/London") -> dict[str, Any]:
        return self._get("/v1/form/meetings", {"date": date, "race_code": race_code, "timezone": timezone})

    def race_form(
        self,
        *,
        date: str,
        track: str,
        race: int,
        country: str,
        race_code: str = "gallops",
        timezone: str = "Europe/London",
    ) -> dict[str, Any]:
        return self._get(
            "/v1/form",
            {
                "date": date,
                "track": track,
                "race": race,
                "race_code": race_code,
                "country": country,
                "timezone": timezone,
            },
        )

    def prices(
        self,
        *,
        date: str,
        track: str,
        race: int,
        country: str,
        race_code: str = "gallops",
        timezone: str = "Europe/London",
    ) -> dict[str, Any]:
        return self._get(
            "/v1/prices",
            {
                "date": date,
                "track": track,
                "race": race,
                "race_code": race_code,
                "country": country,
                "timezone": timezone,
            },
        )

    def results(
        self,
        *,
        date: str,
        track: str,
        race: int,
        country: str,
        race_code: str = "gallops",
        timezone: str = "Europe/London",
    ) -> dict[str, Any]:
        return self._get(
            "/v1/results",
            {
                "date": date,
                "track": track,
                "race": race,
                "race_code": race_code,
                "country": country,
                "timezone": timezone,
            },
        )


def best_live_prices(price_runner: dict[str, Any]) -> dict[str, Any]:
    """Summarise fresh fixed/tote quotes without mutating the primary Racing API odds."""
    fresh = [
        q for q in (price_runner.get("prices") or [])
        if isinstance(q, dict) and not q.get("stale")
    ]
    win = [float(q["win"]) for q in fresh if q.get("win") not in (None, "")]
    place = [float(q["place"]) for q in fresh if q.get("place") not in (None, "")]
    opens = [float(q["open"]) for q in fresh if q.get("open") not in (None, "")]
    highs = [float(q["high"]) for q in fresh if q.get("high") not in (None, "")]
    lows = [float(q["low"]) for q in fresh if q.get("low") not in (None, "")]
    return {
        "best_win": max(win) if win else None,
        "best_place": max(place) if place else None,
        "shortest_win": min(win) if win else None,
        "open_max": max(opens) if opens else None,
        "high_max": max(highs) if highs else None,
        "low_min": min(lows) if lows else None,
        "fresh_quote_count": len(fresh),
        "quotes": price_runner.get("prices") or [],
    }
