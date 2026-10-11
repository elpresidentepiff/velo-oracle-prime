#!/usr/bin/env python3
"""Run VÉLØ's existing model stack over FormFav international racecards.

This is SHADOW ONLY. It never writes velo_verdicts, pipeline_runs, selections,
or execution state. The purpose is to study cross-jurisdiction behaviour and
build evidence before any international model promotion.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from app.services.velo_prime_service import score_race_velo_prime
from src.velo.formfav_card_adapter import fetch_formfav_racecards
from workers.racing_api_normalizer import normalize_race


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",required=True)
    ap.add_argument("--countries",default="us")
    ap.add_argument("--tracks",default="")
    ap.add_argument("--timezone",default="Europe/London")
    ap.add_argument("--no-prices",action="store_true")
    ap.add_argument("--persist-artifact",action="store_true")
    args=ap.parse_args()

    countries={c.strip().lower() for c in args.countries.split(",") if c.strip()}
    tracks={t.strip() for t in args.tracks.split(",") if t.strip()}

    raw_races,fetch_report=fetch_formfav_racecards(
        date_str=args.date,
        countries=countries,
        timezone=args.timezone,
        include_prices=not args.no_prices,
        tracks=tracks or None,
    )

    races_out=[]
    for raw in raw_races:
        race=normalize_race(raw)
        preds=score_race_velo_prime(race)
        if not preds:
            continue
        # Keep this report compact but preserve the signals we need to study.
        top3=[]
        for p in preds[:3]:
            top3.append({
                "horse":p.get("horse") or p.get("horse_name"),
                "horse_id":p.get("horse_id"),
                "velo_prime_prob":p.get("velo_prime_prob"),
                "place_prob":p.get("place_prob"),
                "longshot_prob":p.get("longshot_prob"),
                "improvement_score":p.get("improvement_score"),
                "market_deception_score":p.get("market_deception_score"),
                "confidence_level":p.get("confidence_level"),
                "sp_dec":p.get("sp_dec"),
            })

        priced=[p for p in preds if float(p.get("sp_dec") or 0) >= 6.0]
        longshot=max(priced,key=lambda p:float(p.get("longshot_prob") or 0),default=None)
        races_out.append({
            "race_id":race.get("race_id"),
            "course":race.get("course"),
            "off_time":race.get("off_time"),
            "race_name":race.get("race_name"),
            "country":raw.get("country"),
            "field_size":len(race.get("runners") or []),
            "top3":top3,
            "longshot":({
                "horse":longshot.get("horse") or longshot.get("horse_name"),
                "horse_id":longshot.get("horse_id"),
                "sp_dec":longshot.get("sp_dec"),
                "longshot_prob":longshot.get("longshot_prob"),
                "place_prob":longshot.get("place_prob"),
                "velo_prime_prob":longshot.get("velo_prime_prob"),
            } if longshot else None),
        })

    payload={
        "date":args.date,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "status":"EXPERIMENTAL_CROSS_JURISDICTION_SHADOW_ONLY",
        "countries":sorted(countries),
        "tracks":sorted(tracks),
        "source":"FormFav",
        "scoring_engine":"existing_velo_prime_stack",
        "execution_allowed":False,
        "promotion_allowed":False,
        "canonical_production_write":False,
        "warning":"Existing Velo models were developed primarily on UK/IRE evidence. International outputs are research until independently validated.",
        "fetch_report":fetch_report,
        "race_count":len(races_out),
        "races":races_out,
    }

    out=ROOT/"data"/"reports"/f"formfav_global_shadow_{args.date.replace('-','_')}.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({
        "status":payload["status"],
        "date":args.date,
        "countries":sorted(countries),
        "races":len(races_out),
        "output":str(out.relative_to(ROOT)),
        "fetch_errors":len(fetch_report.get("errors") or []),
    },indent=2))

    if args.persist_artifact:
        cmd=[
            sys.executable,"scripts/ops/persist_daily_artifacts.py",
            "--kind","reports","--date",args.date,"--execute"
        ]
        import subprocess
        rc=subprocess.run(cmd,cwd=ROOT,check=False).returncode
        if rc != 0:
            print(f"WARNING: artifact persistence exited {rc}",file=sys.stderr)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
