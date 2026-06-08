"""
International Sigma Reconciliation Audit
Evaluates VELO predictions for international jurisdictions (HK, US, etc.)
against actual finishers.
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import date, datetime
from pathlib import Path

# Ground to project root
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
SIGMA_DIR = ROOT / "data" / "sigma_results"
SIGMA_DIR.mkdir(parents=True, exist_ok=True)

# Racing API settings (standard)
RACING_USER = os.getenv("RACING_API_USERNAME", "")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "")
RACING_BASE = "https://api.theracingapi.com/v1"
RACING_HEADERS = {
    "Authorization": "Basic " + base64.b64encode(f"{RACING_USER}:{RACING_PASS}".encode()).decode(),
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

def _fetch_results(race_date: str):
    """Fetch all results for a date from Racing API."""
    url = f"{RACING_BASE}/results?date={race_date}"
    req = urllib.request.Request(url, headers=RACING_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
            return data.get("results", [])
    except Exception as e:
        print(f"Error fetching results: {e}")
        return []

def _norm(s):
    return "".join(filter(str.isalpha, str(s or "").lower()))

def run_intl_sigma(target_date: str, jurisdiction: str):
    date_und = target_date.replace("-", "_")
    verdicts_path = DATA_DIR / f"velo_prime_verdicts_{date_und}_international.json"
    
    if not verdicts_path.exists():
        print(f"Error: Verdicts file not found: {verdicts_path}")
        return

    print(f"Loading international verdicts: {verdicts_path.name}...")
    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    
    print(f"Fetching results for {target_date}...")
    results_list = _fetch_results(target_date)
    if not results_list:
        print("No results found for this date.")
        return

    # Index results by race_id
    results_by_id = {str(r.get("race_id")): r for r in results_list}
    
    hits = 0
    frames = 0
    evaluated = 0
    audit_trail = []

    for v in verdicts:
        race_id = str(v.get("race_id"))
        top = v.get("top") or {}
        horse = top.get("horse")
        
        res = results_by_id.get(race_id)
        if not res:
            continue
            
        evaluated += 1
        winner = ""
        top3 = []
        for rnr in res.get("runners", []):
            pos = str(rnr.get("position"))
            if pos == "1":
                winner = rnr.get("horse")
            if pos in ("1", "2", "3"):
                top3.append(rnr.get("horse"))
        
        is_win = _norm(horse) == _norm(winner)
        is_frame = any(_norm(horse) == _norm(h) for h in top3)
        
        if is_win: hits += 1
        if is_frame and not is_win: frames += 1
        
        audit_trail.append({
            "race_id": race_id,
            "course": v.get("course"),
            "off": v.get("off_time"),
            "predicted": horse,
            "actual_winner": winner,
            "outcome": "WIN" if is_win else ("FRAME" if is_frame else "MISS"),
            "vp": top.get("velo_prime_prob"),
            "tier": v.get("tier")
        })

    sr = hits / evaluated if evaluated else 0
    fr = (hits + frames) / evaluated if evaluated else 0
    
    report = {
        "date": target_date,
        "jurisdiction": jurisdiction,
        "evaluated": evaluated,
        "wins": hits,
        "frames": frames,
        "sr": round(sr, 4),
        "frame_rate": round(fr, 4),
        "audit": audit_trail
    }
    
    out_path = SIGMA_DIR / f"international_sigma_{date_und}_{jurisdiction}.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\n[International Sigma Result]")
    print(f"  SR: {sr:.1%}, Frame: {fr:.1%} (n={evaluated})")
    print(f"  Saved to: {out_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--jurisdiction", required=True, choices=["hk", "us"], help="hk or us")
    args = parser.parse_args()
    run_intl_sigma(args.date, args.jurisdiction)

if __name__ == "__main__":
    main()
