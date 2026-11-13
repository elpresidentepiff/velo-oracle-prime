"""Convert FormFav race form + live prices into VÉLØ-compatible raw racecards.

Used for international shadow scoring. This adapter does NOT claim FormFav's
classProfile rating is a BHA official rating and therefore leaves OR/RPR/TS
unset when the source does not provide those canonical fields.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.velo.formfav_client import FormFavClient, FormFavError, best_live_prices
from src.velo.race_identity import (
    VERIFIED,
    canonical_race_key,
    local_race_date,
    parse_utc,
    verify_race_identity,
)

PROVIDER_OPINION_FIELDS = frozenset({
    "modelRank", "winProb", "placeProb", "fairOdds", "edge", "confidence",
    "modelVersion", "prediction", "predictions",
})


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _stable_horse_id(country: str, name: str) -> str:
    digest = hashlib.sha1(f"{country}|{_norm(name)}".encode()).hexdigest()[:16]
    return f"ff_{country}_{digest}"


def _provider_race_key(date_str: str, country: str, slug: str, race_no: int) -> str:
    """``date_str`` is the race's LOCAL racing date (src/velo/race_identity.py)."""
    return canonical_race_key(country, date_str, slug, race_no)


def _kg_to_lbs(v: Any) -> int | None:
    try:
        f=float(v)
        return round(f*2.2046226218) if f>0 else None
    except (TypeError,ValueError):
        return None


def _local_off(start_time: str | None, tz_name: str | None) -> str:
    if not start_time:
        return ""
    try:
        dt=datetime.fromisoformat(start_time.replace("Z","+00:00"))
        return dt.astimezone(ZoneInfo(tz_name or "UTC")).strftime("%H:%M")
    except Exception:
        return str(start_time)


def fetch_formfav_racecards(
    *,
    date_str: str,
    countries: set[str],
    timezone: str = "Europe/London",
    include_prices: bool = True,
    tracks: set[str] | None = None,
    client: Any | None = None,
    utc_date: str | None = None,
) -> tuple[list[dict[str,Any]], dict[str,Any]]:
    """Load one meetings date's cards. Every race is identified by its LOCAL racing date and
    must pass ``verify_race_identity`` (meeting clock == racecard clock == key date) or it is
    reported under ``identity_blocked`` and never returned (#189).

    ``utc_date`` keeps only races whose scheduled off falls on that UTC calendar date, so a
    caller can scan neighbouring racing dates without picking up the same race twice.
    """
    client=client or FormFavClient()
    countries={c.lower() for c in countries}
    track_filter={_norm(t) for t in (tracks or set())}
    meetings_payload=client.meetings(date_str,timezone=timezone)
    races:list[dict[str,Any]]=[]
    report={
        "date":date_str,
        "countries":sorted(countries),
        "meetings_seen":len(meetings_payload.get("meetings") or []),
        "meetings_in_scope":0,
        "races_loaded":0,
        "runners_loaded":0,
        "price_calls_ok":0,
        "price_calls_forbidden":0,
        "errors":[],
        "error_detail":[],
        "identity_blocked":[],
    }

    def _fail(kind: str, track: str, race_no: Any, country: str, message: str) -> None:
        # `errors` stays a flat list of strings for existing readers; `error_detail`
        # carries the country so a per-country run ledger can be written.
        report["errors"].append(f"{kind} {track} R{race_no}: {message}")
        report["error_detail"].append({
            "kind": kind, "country": country, "track": track, "race": race_no, "message": message,
        })

    for meeting in meetings_payload.get("meetings") or []:
        if not isinstance(meeting,dict) or meeting.get("abandoned"):
            continue
        country=str(meeting.get("country") or "").lower()
        if country not in countries:
            continue
        track=str(meeting.get("track") or "")
        if track_filter and _norm(track) not in track_filter and _norm(meeting.get("slug")) not in track_filter:
            continue
        report["meetings_in_scope"]+=1
        slug=str(meeting.get("slug") or track)
        for mrace in meeting.get("races") or []:
            if not isinstance(mrace,dict) or mrace.get("abandoned"):
                continue
            race_no=mrace.get("raceNumber")
            if race_no is None:
                continue
            meeting_off=parse_utc(mrace.get("startTime"))
            if utc_date and (meeting_off is None or meeting_off.date().isoformat()!=utc_date):
                continue
            race_tz=mrace.get("timezone") or meeting.get("timezone")
            racing_date=local_race_date(meeting_off, race_tz)
            if racing_date is None:
                _fail("identity", track, race_no, country, "RACECARD_MISMATCH: MISSING_START_TIME/TIMEZONE")
                report["identity_blocked"].append({
                    "country":country,"track":track,"race":race_no,"reasons":["MISSING_START_TIME_OR_TIMEZONE"],
                })
                continue
            try:
                form=client.race_form(
                    date=racing_date,track=slug,race=int(race_no),country=country,
                    timezone=race_tz,
                )
            except Exception as exc:
                _fail("form", track, race_no, country, f"{type(exc).__name__}: {exc}")
                continue
            race_key=_provider_race_key(racing_date,country,slug,int(race_no))
            identity=verify_race_identity(
                {
                    "provider_race_key":race_key,"race_date":racing_date,"race_number":int(race_no),
                    "start_time":mrace.get("startTime"),"timezone":race_tz,"metadata":mrace,
                    "form_meta":{k:v for k,v in form.items() if k not in ("runners","_provenance","_source")},
                },
                form.get("runners"),
                require_fresh_racecard=False,
            )
            if identity["status"]!=VERIFIED:
                _fail("identity", track, race_no, country, "RACECARD_MISMATCH: "+",".join(identity["reasons"]))
                report["identity_blocked"].append({
                    "provider_race_key":race_key,"country":country,"track":track,"race":race_no,
                    "reasons":identity["reasons"],"meeting_off":mrace.get("startTime"),"card_off":form.get("startTime"),
                })
                continue

            prices={}
            if include_prices:
                try:
                    prices=client.prices(
                        date=racing_date,track=slug,race=int(race_no),country=country,
                        timezone=race_tz,
                    )
                    report["price_calls_ok"]+=1
                except FormFavError as exc:
                    if "403" in str(exc):
                        report["price_calls_forbidden"]+=1
                    else:
                        _fail("prices", track, race_no, country, str(exc))
                except Exception as exc:
                    _fail("prices", track, race_no, country, f"{type(exc).__name__}: {exc}")

            price_map={_norm(r.get("name")):r for r in (prices.get("runners") or []) if isinstance(r,dict)}
            raw_runners=[]
            for rr in form.get("runners") or []:
                if not isinstance(rr,dict) or rr.get("scratched"):
                    continue
                name=str(rr.get("name") or "")
                if not name:
                    continue
                market=best_live_prices(price_map.get(_norm(name),{})) if _norm(name) in price_map else {}
                raw_runners.append({
                    "horse":name,
                    "horse_id":_stable_horse_id(country,name),
                    "age":rr.get("age"),
                    "sex":rr.get("sex"),
                    "lbs":_kg_to_lbs(rr.get("weight")),
                    "draw":rr.get("barrier"),
                    "trainer":rr.get("trainer"),
                    "jockey":rr.get("jockey"),
                    "form":rr.get("form") or rr.get("last20Starts"),
                    "odds":market.get("best_win"),
                    "ofr":None,
                    "rpr":None,
                    "ts":None,
                    "_formfav_synthetic_horse_id":True,
                    "_formfav":{
                        "number":rr.get("number"),
                        "last20Starts":rr.get("last20Starts"),
                        "stats":rr.get("stats") or {},
                        "decorators":rr.get("decorators") or [],
                        "speedMap":rr.get("speedMap"),
                        "classProfile":rr.get("classProfile"),
                        "raceClassFit":rr.get("raceClassFit"),
                        "sire":rr.get("sire"),
                        "dam":rr.get("dam"),
                        "market":market,
                    },
                })

            # This adapter is a provider-data boundary. Velo may consume the
            # card, factual form/statistics and captured market observations,
            # but never FormFav's rank/probability/opinion payload.
            for runner in raw_runners:
                leaked = PROVIDER_OPINION_FIELDS.intersection((runner.get("_formfav") or {}).keys())
                if leaked:
                    raise RuntimeError(f"FormFav prediction opinion leaked into Velo input: {sorted(leaked)}")

            if not raw_runners:
                continue

            start=form.get("startTime") or mrace.get("startTime")
            tz=form.get("timezone") or mrace.get("timezone") or timezone
            race_id=f"ff_{country}_{_norm(slug)}_{racing_date.replace('-','')}_r{int(race_no)}"
            races.append({
                "race_id":race_id,
                "course":form.get("track") or track,
                "course_id":f"ff_{country}_{_norm(slug)}",
                "date":racing_date,
                "off_time":_local_off(start,tz),
                "race_name":form.get("raceName") or mrace.get("raceName") or f"Race {race_no}",
                "distance":form.get("distance") or mrace.get("distance"),
                "going":form.get("condition") or mrace.get("condition"),
                "race_class":form.get("raceClass") or mrace.get("raceClass"),
                "surface":None,
                "type":"flat",
                "region":country.upper(),
                "country":country,
                "field_size":len(raw_runners),
                "runners":raw_runners,
                "_formfav":{
                    "source":"formfav",
                    "data_only":True,
                    "provider_predictions_consumed":False,
                    "provider_race_key":race_key,
                    "race_date":racing_date,
                    "race_identity":{
                        "status":identity["status"],
                        "warnings":identity["warnings"],
                        "local_race_date":identity["local_race_date"],
                        "start_time_utc":identity["start_time_utc"],
                        "timezone":identity["timezone"],
                        "runner_numbers":[r["number"] for r in identity["active_runners"]],
                        "non_runners":identity["non_runners"],
                    },
                    "country":country,
                    "slug":slug,
                    "raceNumber":race_no,
                    "startTime":start,
                    "timezone":tz,
                    "weather":form.get("weather") or mrace.get("weather"),
                    "prizeMoney":form.get("prizeMoney") or mrace.get("prizeMoney"),
                    "experimental_global_shadow":True,
                },
            })
            report["races_loaded"]+=1
            report["runners_loaded"]+=len(raw_runners)
    return races,report
