
import os
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dotenv import load_dotenv
from supabase import create_client

# --- Configuration ---
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Weights from src/intelligence/velo_prime_ensemble.py
WEIGHTS = {
    "sqpe_v17":              0.45,
    "market_deception_score":0.10,
    "place_prob":            0.08,
    "longshot_score":        0.07,
    "improvement_score":     0.12,
    "release_window_score":  0.10,
    "comment_intel_score":   0.08,
}

@dataclass
class Runner:
    horse: str
    horse_id: str
    sqpe: float
    mds: Optional[float] = 0.0
    place: Optional[float] = 0.0
    longshot: Optional[float] = 0.0
    improve: Optional[float] = 0.0
    release: Optional[float] = 0.0
    comment: Optional[float] = 0.0
    sp_dec: Optional[float] = 0.0
    won: bool = False
    placed: bool = False
    p: float = 0.0

def calculate_prob(runner: Runner, policy: str) -> float:
    scores = {"sqpe_v17": runner.sqpe}
    if policy == "POLICY_CURRENT":
        scores["market_deception_score"] = runner.mds or 0
        scores["place_prob"] = runner.place or 0
        if (runner.sp_dec or 0) >= 10.0: scores["longshot_score"] = runner.longshot or 0
    elif policy == "POLICY_SQPE_ONLY":
        pass
    elif policy == "POLICY_CORE_SAFE":
        scores["market_deception_score"] = runner.mds or 0
        scores["place_prob"] = runner.place or 0
        if (runner.sp_dec or 0) >= 10.0: scores["longshot_score"] = runner.longshot or 0
    elif policy == "POLICY_NO_RELEASE_COMMENT":
        scores["market_deception_score"] = runner.mds or 0
        scores["place_prob"] = runner.place or 0
        scores["improvement_score"] = runner.improve or 0
        if (runner.sp_dec or 0) >= 10.0: scores["longshot_score"] = runner.longshot or 0
    elif policy == "POLICY_NO_IMPROVE_RELEASE_COMMENT":
        scores["market_deception_score"] = runner.mds or 0
        scores["place_prob"] = runner.place or 0
        if (runner.sp_dec or 0) >= 10.0: scores["longshot_score"] = runner.longshot or 0
    elif policy == "POLICY_HALF_SIDECARS":
        total_weight = WEIGHTS["sqpe_v17"]
        prob = WEIGHTS["sqpe_v17"] * runner.sqpe
        sidecars = {"market_deception_score": runner.mds, "place_prob": runner.place}
        for k, v in sidecars.items():
            if v is not None:
                w = WEIGHTS[k] * 0.5
                total_weight += w
                prob += w * v
        return prob / total_weight
    elif policy == "POLICY_CAP_SIDECARS":
        base_prob = runner.sqpe
        scores["market_deception_score"] = runner.mds or 0
        scores["place_prob"] = runner.place or 0
        total_weight = sum(WEIGHTS[k] for k in scores)
        full_prob = sum(WEIGHTS[k] * v for k, v in scores.items()) / total_weight
        uplift = full_prob - base_prob
        return base_prob + max(-0.03, min(0.03, uplift))
    elif policy == "POLICY_VALUE_GATED":
        if (runner.sp_dec or 0) < 4.0: return runner.sqpe
        scores["market_deception_score"] = runner.mds or 0
        scores["place_prob"] = runner.place or 0
            
    total_weight = sum(WEIGHTS.get(k, 0) for k in scores)
    if total_weight == 0: return runner.sqpe
    return sum(WEIGHTS.get(k, 0) * v for k, v in scores.items()) / total_weight

def run_simulation():
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    sigma = []
    pg = 0
    while True:
        r = sb.table("sigma_audits").select("race_id,date,outcome,actual_winner_sp").neq("outcome", "X_BLOCKED").range(pg*1000, (pg+1)*1000-1).execute()
        sigma.extend(r.data)
        if len(r.data) < 1000: break
        pg += 1
    vv = []
    pg = 0
    while True:
        r = sb.table("velo_verdicts").select("race_id,full_analysis").range(pg*1000, (pg+1)*1000-1).execute()
        vv.extend(r.data)
        if len(r.data) < 1000: break
        pg += 1
    vv_map = {v["race_id"]: v for v in vv}
    policies = ["POLICY_CURRENT", "POLICY_SQPE_ONLY", "POLICY_CORE_SAFE", "POLICY_NO_RELEASE_COMMENT", "POLICY_NO_IMPROVE_RELEASE_COMMENT", "POLICY_HALF_SIDECARS", "POLICY_CAP_SIDECARS", "POLICY_VALUE_GATED"]
    stats = {p: {"n": 0, "wins": 0, "frames": 0, "pnl": 0.0, "equity": 0.0, "peak": 0.0, "drawdown": 0.0, "streak": 0, "max_streak": 0, "vp30_n": 0, "vp30_wins": 0, "vp30_pnl": 0.0, "vp30_frames": 0} for p in policies}

    total_matched = 0
    for sv in sigma:
        v = vv_map.get(sv["race_id"])
        if not v: continue
        fa = v.get("full_analysis") or []
        if isinstance(fa, dict): fa = list(fa.values())
        if not fa: continue
        
        # Original Top Pick
        otp = fa[0]
        otp_name = otp.get("horse")
        if not otp_name: continue
        
        winner_name = otp_name if sv["outcome"] == "WIN" else None
        winner_sp = float(sv["actual_winner_sp"]) if sv.get("actual_winner_sp") else 0.0
        
        # Extract all runners
        sim_runners = []
        for rd in fa:
            if not isinstance(rd, dict): continue
            h_name = rd.get("horse")
            if not h_name: continue
            sr = Runner(horse=h_name, horse_id=rd.get("horse_id", ""), sqpe=rd.get("sqpe_v17_prob", 0.0), mds=rd.get("market_deception_score", 0.0), place=rd.get("place_prob", 0.0), longshot=rd.get("longshot_prob", 0.0), improve=rd.get("improvement_score", 0.0), release=rd.get("release_day_prob", 0.0), comment=rd.get("comment_intel_score", 0.0))
            if h_name == winner_name:
                sr.won = True
                sr.placed = True
                sr.sp_dec = winner_sp
            elif h_name == otp_name and sv["outcome"] == "PLACED":
                sr.placed = True
            sim_runners.append(sr)

        if not sim_runners: continue
        total_matched += 1
        for p in policies:
            for sr in sim_runners: sr.p = calculate_prob(sr, p)
            sim_runners.sort(key=lambda x: x.p, reverse=True)
            top = sim_runners[0]
            s = stats[p]
            s["n"] += 1
            if top.won:
                s["wins"] += 1
                s["pnl"] += (top.sp_dec - 1.0)
                s["equity"] += (top.sp_dec - 1.0)
                s["streak"] = 0
            else:
                s["pnl"] -= 1.0
                s["equity"] -= 1.0
                s["streak"] += 1
            if top.placed: s["frames"] += 1
            s["max_streak"] = max(s["max_streak"], s["streak"])
            s["peak"] = max(s["peak"], s["equity"])
            s["drawdown"] = max(s["drawdown"], s["peak"] - s["equity"])
            if top.p >= 0.30:
                s["vp30_n"] += 1
                if top.won:
                    s["vp30_wins"] += 1
                    s["vp30_pnl"] += (top.sp_dec - 1.0)
                else: s["vp30_pnl"] -= 1.0
                if top.placed: s["vp30_frames"] += 1

    print(f"Total Matched: {total_matched}")
    print("| Policy | n | SR | Frame | P&L | ROI | Max DD | Streak | VP30 n | VP30 ROI |")
    for p in policies:
        s = stats[p]
        n = s["n"]
        roi = (s["pnl"] / n * 100) if n else 0
        sr = (s["wins"] / n * 100) if n else 0
        fr = (s["frames"] / n * 100) if n else 0
        v_roi = (s["vp30_pnl"] / s["vp30_n"] * 100) if s["vp30_n"] else 0
        print(f"| {p} | {n} | {sr:.1f}% | {fr:.1f}% | {s['pnl']:.1f} | {roi:.1f}% | {s['drawdown']:.1f} | {s['max_streak']} | {s['vp30_n']} | {v_roi:.1f}% |")

if __name__ == "__main__":
    run_simulation()
