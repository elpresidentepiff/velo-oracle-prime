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


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _stable_horse_id(country: str, name: str) -> str:
    digest = hashlib.sha1(f"{country}|{_norm(name)}".encode()).hexdigest()[:16]
    return f"ff_{country}_{digest}"


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
) -> tuple[list[dict[str,Any]], dict[str,Any]]:
    client=FormFavClient()
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
    }

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
            try:
                form=client.race_form(
                    date=date_str,track=slug,race=int(race_no),country=country,
                    timezone=mrace.get("timezone") or timezone,
                )
            except Exception as exc:
                report["errors"].append(f"form {track} R{race_no}: {type(exc).__name__}: {exc}")
                continue

            prices={}
            if include_prices:
                try:
                    prices=client.prices(
                        date=date_str,track=slug,race=int(race_no),country=country,
                        timezone=mrace.get("timezone") or timezone,
                    )
                    report["price_calls_ok"]+=1
                except FormFavError as exc:
                    if "403" in str(exc):
                        report["price_calls_forbidden"]+=1
                    else:
                        report["errors"].append(f"prices {track} R{race_no}: {exc}")
                except Exception as exc:
                    report["errors"].append(f"prices {track} R{race_no}: {type(exc).__name__}: {exc}")

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

            if not raw_runners:
                continue

            start=form.get("startTime") or mrace.get("startTime")
            tz=form.get("timezone") or mrace.get("timezone") or timezone
            race_id=f"ff_{country}_{_norm(slug)}_{date_str.replace('-','')}_r{int(race_no)}"
            races.append({
                "race_id":race_id,
                "course":form.get("track") or track,
                "course_id":f"ff_{country}_{_norm(slug)}",
                "date":date_str,
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
