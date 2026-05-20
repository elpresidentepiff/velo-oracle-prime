"""
sync_verdicts_from_supabase.py

Pull persisted Railway/Supabase verdicts for a race date into local data/.
Joins velo_verdicts with runners + races to build the flat verdict JSON
expected by cashrun_detector, acca_detector, racing_api_enrichment_operator_card.

Usage: python scripts/sync_verdicts_from_supabase.py --date YYYY-MM-DD
Output: data/velo_prime_verdicts_YYYY_MM_DD.json

This script is READ-ONLY. It does not score races, does not run run_prime_today.py,
and does not write to Supabase.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
load_dotenv(dotenv_path=ROOT / ".env")

SB_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Accept": "application/json"}

PAGE = 1000


def _fetch_all(table: str, query_str: str) -> list:
    rows = []
    offset = 0
    while True:
        url = f"{SB_URL}/rest/v1/{table}?{query_str}&limit={PAGE}&offset={offset}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    return rows


def _fetch_verdict_rows(target: str) -> tuple[list, str]:
    """Try four date resolution strategies. Returns (rows, method_used)."""
    d = date.fromisoformat(target)
    next_d = d + timedelta(days=1)

    # Strategy 1: UK race-day window (03:00Z–03:00Z)
    uk_start = f"{target}T03:00:00Z"
    uk_end = f"{next_d.isoformat()}T03:00:00Z"
    cols = ("id,race_id,generated_at,engine_version,git_commit_sha,environment,"
            "velo_prime_prob,improvement_score,market_deception_score,place_prob,"
            "longshot_prob,release_day_prob,decision_tier,confidence_level,"
            "confidence_level_raw,confidence_level_effective,"
            "rpdc_release_score,rpdc_cash_window_flag,rpdc_tag_count,rpdc_primary_tag,rpdc_tags,"
            "race_archetype,archetype_confidence,archetype_bet_style,archetype_suppression,"
            "assigned_product,router_reasons,execution_allowed,"
            "top_rank_horse_id,selections,full_analysis,active_components,excluded_from_ensemble,"
            "g_shadow_multiplier,g_shadow_flags")
    q = f"select={cols}&generated_at=gte.{uk_start}&generated_at=lt.{uk_end}&order=velo_prime_prob.desc"
    rows = _fetch_all("velo_verdicts", q)
    if rows:
        return rows, f"uk_window ({uk_start} – {uk_end})"

    # Strategy 2: UTC day window
    utc_start = f"{target}T00:00:00Z"
    utc_end = f"{next_d.isoformat()}T00:00:00Z"
    q = f"select={cols}&generated_at=gte.{utc_start}&generated_at=lt.{utc_end}&order=velo_prime_prob.desc"
    rows = _fetch_all("velo_verdicts", q)
    if rows:
        return rows, f"utc_day ({utc_start} – {utc_end})"

    # Strategy 3: race_id join via races.date
    race_rows = _fetch_all("races", f"select=id&date=eq.{target}")
    if race_rows:
        race_ids = [r["id"] for r in race_rows]
        # PostgREST in() filter — batch to avoid URL length limits
        all_verdicts: list = []
        for i in range(0, len(race_ids), 50):
            chunk = ",".join(race_ids[i:i+50])
            q = f"select={cols}&race_id=in.({chunk})&order=velo_prime_prob.desc"
            all_verdicts.extend(_fetch_all("velo_verdicts", q))
        if all_verdicts:
            return all_verdicts, f"race_id_join (races.date={target}, {len(race_ids)} races)"

    # Strategy 4: nothing found
    return [], "none"


def _latest_generated_at() -> str:
    rows = _fetch_all("velo_verdicts", "select=generated_at&order=generated_at.desc&limit=1")
    return rows[0]["generated_at"] if rows else "unknown"


def _enrich_with_race_and_runner(rows: list, target: str) -> list:
    """Join verdict rows with races + runners to add horse_name, course, race_time."""
    race_ids = list({r["race_id"] for r in rows if r.get("race_id")})

    # Fetch races
    races: dict[str, dict] = {}
    for i in range(0, len(race_ids), 50):
        chunk = ",".join(race_ids[i:i+50])
        race_rows = _fetch_all("races", f"select=id,course,date,off_time,time,distance,going,class&race_id=in.({chunk})")
        # races table uses 'id' not 'race_id'
        race_rows2 = _fetch_all("races", f"select=id,course,date,off_time,time,distance,going,class&id=in.({chunk})")
        for rr in race_rows2:
            races[rr["id"]] = rr

    # Fetch runners
    runners_by_race: dict[str, list] = {}
    for i in range(0, len(race_ids), 50):
        chunk = ",".join(race_ids[i:i+50])
        runner_rows = _fetch_all("runners", f"select=race_id,horse_id,horse_name,trainer,jockey,draw,weight&race_id=in.({chunk})")
        for rr in runner_rows:
            runners_by_race.setdefault(rr["race_id"], []).append(rr)

    enriched = []
    for v in rows:
        race_id = v.get("race_id")
        race = races.get(race_id, {})

        # Identify top-ranked horse
        top_horse_id = v.get("top_rank_horse_id")
        horse_name = None
        trainer = None
        jockey = None
        draw = None

        race_runners = runners_by_race.get(race_id, [])
        if top_horse_id:
            for rr in race_runners:
                if rr.get("horse_id") == top_horse_id:
                    horse_name = rr.get("horse_name")
                    trainer = rr.get("trainer")
                    jockey = rr.get("jockey")
                    draw = rr.get("draw")
                    break

        # Fallback: try selections field
        if not horse_name:
            sels = v.get("selections") or []
            if isinstance(sels, str):
                try:
                    sels = json.loads(sels)
                except Exception:
                    sels = []
            if sels and isinstance(sels, list):
                top = sels[0] if isinstance(sels[0], dict) else {}
                horse_name = top.get("horse_name") or top.get("name")
                trainer = top.get("trainer")
                jockey = top.get("jockey")

        race_time = race.get("off_time") or race.get("time") or ""

        enriched.append({
            "race_id": race_id,
            "horse_name": horse_name or "",
            "course": race.get("course", ""),
            "race_time": str(race_time),
            "race_date": target,
            "distance": race.get("distance", ""),
            "going": race.get("going", ""),
            "race_class": race.get("class", ""),
            "trainer": trainer or "",
            "jockey": jockey or "",
            "draw": draw,
            "velo_prime_prob": v.get("velo_prime_prob"),
            "improvement_score": v.get("improvement_score"),
            "market_deception_score": v.get("market_deception_score"),
            "place_prob": v.get("place_prob"),
            "longshot_prob": v.get("longshot_prob"),
            "release_day_prob": v.get("release_day_prob"),
            "decision_tier": v.get("decision_tier"),
            "confidence_level": v.get("confidence_level"),
            "confidence_level_raw": v.get("confidence_level_raw"),
            "confidence_level_effective": v.get("confidence_level_effective"),
            "rpdc_release_score": v.get("rpdc_release_score"),
            "rpdc_cash_window_flag": v.get("rpdc_cash_window_flag"),
            "rpdc_tag_count": v.get("rpdc_tag_count"),
            "rpdc_primary_tag": v.get("rpdc_primary_tag"),
            "rpdc_tags": v.get("rpdc_tags"),
            "race_archetype": v.get("race_archetype"),
            "archetype_confidence": v.get("archetype_confidence"),
            "archetype_bet_style": v.get("archetype_bet_style"),
            "archetype_suppression": v.get("archetype_suppression"),
            "assigned_product": v.get("assigned_product"),
            "router_reasons": v.get("router_reasons"),
            "execution_allowed": v.get("execution_allowed"),
            "generated_at": v.get("generated_at"),
            "engine_version": v.get("engine_version"),
            "git_commit_sha": v.get("git_commit_sha"),
            "environment": v.get("environment"),
            "active_components": v.get("active_components"),
            "excluded_from_ensemble": v.get("excluded_from_ensemble"),
            "g_shadow_multiplier": v.get("g_shadow_multiplier"),
            "g_shadow_flags": v.get("g_shadow_flags"),
            "all_runners": race_runners,
            "verdict_source": "supabase_sync",
        })

    return enriched


def main() -> None:
    ap = argparse.ArgumentParser(description="Sync Railway verdicts from Supabase to local data/")
    ap.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    args = ap.parse_args()
    target = args.date

    print(f"\nSyncing verdicts for {target} from Supabase...")

    rows, method = _fetch_verdict_rows(target)

    if not rows:
        latest = _latest_generated_at()
        print(f"\nDIAGNOSIS_REQUIRED")
        print(f"Zero verdict rows found for {target} across all query strategies.")
        print(f"Latest generated_at in DB: {latest}")
        print("Possible causes:")
        print("  1. Railway deployed but scoring cron has not yet fired (cron: 06:00 UTC)")
        print("  2. Scoring failed — check Railway deployment logs")
        print("  3. Verdicts stored with unexpected timestamp offset")
        print(f"\nRun: python scripts/audit_railway_supabase_run_status.py --date {target}")
        return

    print(f"Query method: {method}")
    print(f"Rows fetched: {len(rows)}")
    print(f"Unique race_ids: {len({r['race_id'] for r in rows})}")

    ts_vals = [r["generated_at"] for r in rows if r.get("generated_at")]
    if ts_vals:
        print(f"generated_at range: {min(ts_vals)} → {max(ts_vals)}")

    ver_counts = Counter(r.get("engine_version") for r in rows)
    print(f"engine_version: {dict(ver_counts)}")

    sha_counts = Counter((r.get("git_commit_sha") or "")[:7] for r in rows)
    print(f"git_commit_sha: {dict(sha_counts)}")

    print("\nEnriching with race + runner data...")
    enriched = _enrich_with_race_and_runner(rows, target)

    out_path = DATA / f"velo_prime_verdicts_{target.replace('-', '_')}.json"
    out_path.write_text(json.dumps(enriched, indent=2, default=str), encoding="utf-8")

    vp30 = [v for v in enriched if (v.get("velo_prime_prob") or 0) >= 0.30]
    print(f"\nWritten: {out_path}")
    print(f"Total records: {len(enriched)}")
    print(f"VP>=0.30: {len(vp30)}")

    if vp30:
        print("\nTop VP30 selections:")
        for v in sorted(vp30, key=lambda x: x.get("velo_prime_prob") or 0, reverse=True)[:10]:
            print(f"  {v.get('race_time','?'):6} {v.get('course','?'):20} "
                  f"{v.get('horse_name','?'):25} VP={v.get('velo_prime_prob',0):.3f} "
                  f"tier={v.get('decision_tier','?')}")

    print(f"\nStatus: LOCAL_HYDRATED — {out_path.name} ready for operator stack")
    print("Next: python scripts/racing_api_enrichment_operator_card.py --date", target)
    print("      python scripts/acca_detector.py --date", target)


if __name__ == "__main__":
    main()
