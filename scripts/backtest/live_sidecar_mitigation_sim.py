#!/usr/bin/env python3
"""
live_sidecar_mitigation_sim.py

Local-only simulation comparing 5 scoring profiles against closed results.
Uses full_analysis per-runner scores from velo_verdicts to re-rank each race
under each profile, then measures SR/ROI against actual_winner_id.

No live scoring changes. No model changes. No router changes. No staking.

Profiles:
  A — Current live weights (baseline)
  B — SQPE only
  C — SQPE + MDS + place_prob + longshot gated SP>=10
  D — Remove red flags: SQPE + MDS + place + IMP; release=0, comment=0
  E — Strict value: SQPE + MDS only, longshot gated SP>=10

Usage:
    python scripts/live_sidecar_mitigation_sim.py
"""

import os, sys, json, time, math, requests
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
OUTPUT_MD   = Path("data/live_sidecar_mitigation_sim_latest.md")
OUTPUT_JSON = Path("data/live_sidecar_mitigation_sim_latest.json")

# Live weights as currently deployed in velo_prime_ensemble.py
LIVE_WEIGHTS = {
    "velo_prime_prob":        0.40,
    "improvement_score":      0.15,
    "market_deception_score": 0.20,
    "release_day_prob":       0.10,
    "place_prob":             0.10,
    "longshot_prob":          0.05,
}

PROFILES = {
    "A_CURRENT_LIVE": {
        "desc": "Current live weights (baseline)",
        "weights": LIVE_WEIGHTS,
        "longshot_gate_sp": None,
        "comment_weight": 0.0,
    },
    "B_CORE_ONLY": {
        "desc": "SQPE only",
        "weights": {
            "velo_prime_prob":        1.0,
            "improvement_score":      0.0,
            "market_deception_score": 0.0,
            "release_day_prob":       0.0,
            "place_prob":             0.0,
            "longshot_prob":          0.0,
        },
        "longshot_gate_sp": None,
        "comment_weight": 0.0,
    },
    "C_CORE_PLUS_MDS_PLACE": {
        "desc": "SQPE + MDS + place_prob + longshot gated SP>=10",
        "weights": {
            "velo_prime_prob":        0.55,
            "improvement_score":      0.0,
            "market_deception_score": 0.25,
            "release_day_prob":       0.0,
            "place_prob":             0.15,
            "longshot_prob":          0.05,
        },
        "longshot_gate_sp": 10.0,
        "comment_weight": 0.0,
    },
    "D_REMOVE_RED_FLAGS": {
        "desc": "Remove release+comment; keep IMP",
        "weights": {
            "velo_prime_prob":        0.45,
            "improvement_score":      0.15,
            "market_deception_score": 0.25,
            "release_day_prob":       0.0,
            "place_prob":             0.15,
            "longshot_prob":          0.0,
        },
        "longshot_gate_sp": None,
        "comment_weight": 0.0,
    },
    "E_STRICT_VALUE": {
        "desc": "SQPE + MDS only; longshot gated SP>=10",
        "weights": {
            "velo_prime_prob":        0.65,
            "improvement_score":      0.0,
            "market_deception_score": 0.35,
            "release_day_prob":       0.0,
            "place_prob":             0.0,
            "longshot_prob":          0.0,
        },
        "longshot_gate_sp": 10.0,
        "comment_weight": 0.0,
    },
}


def hdrs():
    return {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def fetch_all(table, select, extra=""):
    rows, offset = [], 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}{('&'+extra) if extra else ''}&offset={offset}&limit=1000"
        r = requests.get(url, headers=hdrs(), timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch: break
        rows.extend(batch)
        if len(batch) < 1000: break
        offset += 1000
        time.sleep(0.05)
    return rows


def score_runner(runner: dict, weights: dict, longshot_gate_sp: float | None,
                 winner_sp: float | None) -> float:
    vp  = float(runner.get("velo_prime_prob")        or 0)
    imp = float(runner.get("improvement_score")       or 0)
    mds = float(runner.get("market_deception_score")  or 0)
    rel = float(runner.get("release_day_prob")        or 0)
    plc = float(runner.get("place_prob")              or 0)
    lng = float(runner.get("longshot_prob")           or 0)

    if longshot_gate_sp and winner_sp and winner_sp < longshot_gate_sp:
        lng = 0.0

    return (
        weights["velo_prime_prob"]        * vp  +
        weights["improvement_score"]      * imp +
        weights["market_deception_score"] * mds +
        weights["release_day_prob"]       * rel +
        weights["place_prob"]             * plc +
        weights["longshot_prob"]          * lng
    )


def profile_metrics(races: list[dict], profile: dict) -> dict:
    weights   = profile["weights"]
    gate_sp   = profile["longshot_gate_sp"]
    wins = placed = n = 0
    total_pl = roi_n = 0
    running = peak = max_dd = 0.0
    losing_run = max_losing = 0
    sp_sum = sp_n = 0
    vp30_wins = vp30_n = 0

    for race in races:
        runners = race["runners"]
        winner_sp = race["winner_sp"]

        # Re-rank under this profile
        scored = sorted(
            runners,
            key=lambda r: score_runner(r, weights, gate_sp, winner_sp),
            reverse=True
        )
        if not scored:
            continue

        top = scored[0]
        won = (top["horse_id"] == race["winner_id"])
        # placed: top is in top 3 (approximation — we don't have per-runner position)
        # use: if top won OR if live top-pick was placed and it's the same horse
        is_placed = won or race.get("live_top_placed", False) and top["horse_id"] == race.get("live_top_id")

        n += 1
        if won: wins += 1
        if is_placed and not won: placed += 1

        if winner_sp:
            pl = (winner_sp - 1.0) if won else -1.0
            total_pl += pl
            roi_n += 1
            sp_sum += winner_sp
            sp_n += 1

            running += pl
            if running > peak:
                peak = running
                losing_run = 0
            else:
                dd = peak - running
                max_dd = max(max_dd, dd)
                if pl < 0:
                    losing_run += 1
                    max_losing = max(max_losing, losing_run)
                else:
                    losing_run = 0

        vp = float(top.get("velo_prime_prob") or 0)
        if vp >= 0.30:
            vp30_n += 1
            if won: vp30_wins += 1

    if n == 0:
        return {"n": 0}

    return {
        "n": n,
        "sr":    round(wins / n, 4),
        "frame": round((wins + placed) / n, 4),
        "roi":   round(total_pl / roi_n, 4) if roi_n else 0,
        "avg_sp": round(sp_sum / sp_n, 2) if sp_n else 0,
        "vp30_n": vp30_n,
        "vp30_sr": round(vp30_wins / vp30_n, 4) if vp30_n else 0,
        "max_drawdown": round(max_dd, 2),
        "max_losing_run": max_losing,
    }


def main():
    if not SUPABASE_URL or not KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    print("=" * 68)
    print("LIVE SIDECAR MITIGATION SIMULATION")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 68)

    # ── Fetch verdicts with full_analysis ─────────────────────────────────────
    print("\n[1/4] Fetching verdicts (with full_analysis)...")
    verdicts = fetch_all("velo_verdicts", "id,race_id,full_analysis,top_rank_horse_id")
    verdict_by_id = {v["id"]: v for v in verdicts}
    verdict_by_race = {v["race_id"]: v for v in verdicts}
    print(f"  Verdicts: {len(verdicts):,}")

    # ── Fetch reviews (actual results) ────────────────────────────────────────
    print("[2/4] Fetching closed reviews...")
    reviews = fetch_all(
        "velo_post_race_reviews",
        "verdict_id,race_id,top_pick_won,top_pick_placed,actual_winner_id,actual_winner_sp"
    )
    print(f"  Reviews: {len(reviews):,}")

    # ── Build race objects ────────────────────────────────────────────────────
    print("[3/4] Building race objects...")
    races = []
    skipped = 0
    for rev in reviews:
        if not rev.get("actual_winner_id") or not rev.get("actual_winner_sp"):
            skipped += 1
            continue

        v = verdict_by_id.get(rev.get("verdict_id"))
        if not v:
            skipped += 1
            continue

        fa = v.get("full_analysis")
        if isinstance(fa, str):
            try: fa = json.loads(fa)
            except: fa = []
        if not fa:
            skipped += 1
            continue
        fa = [r for r in fa if isinstance(r, dict)]
        if not fa:
            skipped += 1
            continue

        races.append({
            "race_id":         rev["race_id"],
            "winner_id":       rev["actual_winner_id"],
            "winner_sp":       float(rev["actual_winner_sp"]),
            "live_top_placed": bool(rev.get("top_pick_placed")),
            "live_top_id":     v.get("top_rank_horse_id"),
            "runners":         fa,
        })

    print(f"  Valid races: {len(races):,}  (skipped: {skipped})")

    if len(races) < 10:
        print("  WARNING: very small sample — results directional only")

    # ── Score profiles ────────────────────────────────────────────────────────
    print("[4/4] Scoring profiles...")
    results = {}
    for key, profile in PROFILES.items():
        m = profile_metrics(races, profile)
        results[key] = {**profile, "metrics": m}
        print(f"  {key}: n={m.get('n',0)}  SR={m.get('sr',0):.3f}  ROI={m.get('roi',0):+.3f}")

    # ── Analysis ──────────────────────────────────────────────────────────────
    live_roi = results["A_CURRENT_LIVE"]["metrics"].get("roi", 0)
    live_sr  = results["A_CURRENT_LIVE"]["metrics"].get("sr", 0)

    def get(k, metric): return results[k]["metrics"].get(metric, -99)

    best_roi_key   = max(results, key=lambda k: get(k, "roi"))
    best_sr_key    = max(results, key=lambda k: get(k, "sr"))
    best_frame_key = max(results, key=lambda k: get(k, "frame"))

    # Shadow candidate = best ROI profile that beats live
    shadow_candidate = best_roi_key if get(best_roi_key, "roi") > live_roi else "A_CURRENT_LIVE"

    # Red flag verdicts
    d_roi = get("D_REMOVE_RED_FLAGS", "roi")
    e_roi = get("E_STRICT_VALUE", "roi")
    release_disable_test = d_roi > live_roi
    comment_disable_test = d_roi > live_roi

    c_roi = get("C_CORE_PLUS_MDS_PLACE", "roi")
    if d_roi > c_roi and d_roi > live_roi:
        imp_verdict = "RETAIN"
    elif c_roi > d_roi and c_roi > live_roi:
        imp_verdict = "REDUCE_OR_SHADOW_TEST"
    else:
        imp_verdict = "SHADOW_TEST"

    # ── Report ────────────────────────────────────────────────────────────────
    lines = []
    def out(s=""): lines.append(s); print(s)

    out()
    out("=" * 68)
    out("LIVE SIDECAR MITIGATION SIMULATION")
    out(f"Generated: {datetime.utcnow().isoformat()}Z")
    out(f"Sample: {len(races):,} races with full runner scores and closed results")
    out("=" * 68)
    out()
    out("## Profile Comparison")
    out()
    hdr = f"{'Profile':<28} {'n':>5} {'SR':>7} {'Frame':>7} {'ROI':>8} {'AvgSP':>7} {'VP30n':>6} {'VP30SR':>7} {'MaxDD':>7} {'LoseRun':>8}"
    out(hdr)
    out("-" * len(hdr))

    for key, res in results.items():
        m = res["metrics"]
        if not m.get("n"): continue
        delta_roi = m.get("roi",0) - live_roi
        flag = " ← LIVE" if key == "A_CURRENT_LIVE" else f"  ROI{delta_roi:+.3f}vs live"
        out(
            f"{key:<28} {m['n']:>5} {m['sr']:>7.3f} {m['frame']:>7.3f} "
            f"{m['roi']:>+8.3f} {m['avg_sp']:>7.2f} {m.get('vp30_n',0):>6} "
            f"{m.get('vp30_sr',0):>7.3f} {m.get('max_drawdown',0):>7.2f} "
            f"{m.get('max_losing_run',0):>8}{flag}"
        )

    out()
    out("## Verdicts")
    out()
    out(f"  Best profile by ROI:         {best_roi_key}  ({get(best_roi_key,'roi'):+.3f})")
    out(f"  Best profile by SR:          {best_sr_key}  ({get(best_sr_key,'sr'):.3f})")
    out(f"  Best profile by frame rate:  {best_frame_key}  ({get(best_frame_key,'frame'):.3f})")
    out()
    out(f"  Shadow comparison candidate:        {shadow_candidate}")
    out(f"  release_day_prob → disable-test:    {'YES — Profile D beats live ROI' if release_disable_test else 'NO — inconclusive at this sample size'}")
    out(f"  comment_intel_score → disable-test: {'YES — Profile D beats live ROI' if comment_disable_test else 'NO — inconclusive at this sample size'}")
    out(f"  improvement_score verdict:          {imp_verdict}")
    out()
    out("## Notes")
    out(f"  Frame rate uses live engine's top_pick_placed for same-horse selections.")
    out(f"  ROI = flat-stake £1 per race, winner SP taken as return.")
    out(f"  VP30 SR = strike rate among races where profile top-pick has VP≥0.30.")
    out()
    out("## Live Code Change: NONE")
    out("  No scoring weights changed. No model touched. No router changed.")
    out("  No staking. No Telegram. No live execution. Simulation only.")

    OUTPUT_MD.parent.mkdir(exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines))
    OUTPUT_JSON.write_text(json.dumps({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sample_n": len(races),
        "profiles": {k: {"desc": v["desc"], "metrics": v["metrics"]} for k, v in results.items()},
        "best_roi": best_roi_key,
        "best_sr": best_sr_key,
        "best_frame": best_frame_key,
        "shadow_candidate": shadow_candidate,
        "release_day_prob_disable_test": release_disable_test,
        "comment_disable_test": comment_disable_test,
        "improvement_score_verdict": imp_verdict,
    }, indent=2))

    print(f"\nOutputs: {OUTPUT_MD}  {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
