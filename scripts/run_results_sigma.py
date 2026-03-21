"""
VELO Results Reconciliation + Sigma Loop
==========================================
Results workflow: WAIT -> FETCH RESULTS -> RECONCILE -> SIGMA -> LEARN

Chain:
  velo_verdicts (today's predictions)
  + Racing API results (actual finishers)
  -> reconcile top_pick vs actual winner
  -> sigma: strike rate, frame rate, miss classes, prob calibration
  -> persist to Supabase (runner_results, learned_patterns)
  -> Telegram sigma report

Usage:
    python scripts/run_results_sigma.py [--date YYYY-MM-DD]
"""
import sys
import os
import json
import base64
import argparse
import urllib.request
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TODAY   = date.today().strftime("%Y-%m-%d")
TODAY_DISPLAY = date.today().strftime("%d %b %Y")

RACING_USER = os.getenv("RACING_API_USERNAME", "")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "")
RACING_BASE = "https://api.theracingapi.com/v1"
# User-Agent required — Cloudflare blocks without it
RACING_HEADERS = {
    "Authorization": "Basic " + base64.b64encode(
        f"{RACING_USER}:{RACING_PASS}".encode()
    ).decode(),
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def tg(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print(f"[TG SKIP]: {text[:60]}")
        return False
    try:
        body = json.dumps({"chat_id": CHAT_ID, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"[TG FAIL]: {e}")
        return False


def racing_get(path: str) -> dict:
    req = urllib.request.Request(f"{RACING_BASE}{path}", headers=RACING_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def sb_get(path: str) -> list:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1{path}",
        headers={**SB_HEADERS, "Prefer": ""},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def sb_post(path: str, data: dict | list) -> bool:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1{path}",
        data=body, headers=SB_HEADERS,
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [SB POST FAIL] {path}: {e}")
        return False


def sb_upsert(path: str, data: dict | list, on_conflict: str) -> bool:
    sep = "&" if "?" in path else "?"
    url = f"{SB_URL}/rest/v1{path}{sep}on_conflict={on_conflict}"
    body = json.dumps(data).encode()
    headers = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [SB UPSERT FAIL] {path}: {e}")
        return False


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    race_date = args.date or TODAY

    print(f"\nVELO RESULTS + SIGMA — {race_date}")
    print("=" * 60)

    # ── STEP 1: Load today's predictions from Supabase ────────────────────────
    print("\nSTEP 1: Load predictions from velo_verdicts")
    verdicts_raw = sb_get(
        f"/velo_verdicts?select=race_id,top_rank_horse_id,velo_prime_prob,decision_tier,confidence_level,generated_at"
        f"&generated_at=gte.{race_date}T00:00:00"
        f"&generated_at=lt.{race_date}T23:59:59"
        f"&order=generated_at"
    )
    print(f"  Predictions loaded: {len(verdicts_raw)}")
    if not verdicts_raw:
        print("  ABORT: no predictions found for this date")
        tg(f"VELO SIGMA ABORT — {race_date}\nNo predictions found in velo_verdicts.")
        sys.exit(1)

    # Build lookup: race_id -> {horse_id, velo_prime_prob}
    predictions = {v["race_id"]: v for v in verdicts_raw}

    # Load horse names from local backup
    backup = ROOT / "data" / f"velo_prime_verdicts_{race_date.replace('-','_')}.json"
    horse_names = {}
    if backup.exists():
        for r in json.loads(backup.read_text()):
            top = r.get("top", {})
            horse_names[r["race_id"]] = {
                "horse": top.get("horse", "?"),
                "course": r.get("course", "?"),
                "off_time": r.get("off_time", "?"),
            }

    # ── STEP 2: Fetch results from Racing API ─────────────────────────────────
    print("\nSTEP 2: Fetch results from Racing API")
    cached = ROOT / "data" / f"results_{race_date.replace('-','_')}.json"
    if cached.exists() and cached.stat().st_size > 100:
        d = json.loads(cached.read_text())
        results_list = d.get("results", [])
        print(f"  Using cached results: {len(results_list)} races")
    else:
        print(f"  Fetching from API...")
        d = racing_get(f"/results?start_date={race_date}&end_date={race_date}&limit=50")
        results_list = d.get("results", [])
        cached.write_text(json.dumps(d, indent=2))
        print(f"  Fetched and cached: {len(results_list)} races")

    # Build result lookup: race_id -> {winner_horse, winner_id, top3_ids}
    results_by_id = {}
    for race in results_list:
        rid = race.get("race_id") or race.get("id", "")
        runners = race.get("runners", [])
        sorted_runners = sorted(
            [r for r in runners if r.get("position", "").isdigit()],
            key=lambda r: int(r["position"])
        )
        winner = sorted_runners[0] if sorted_runners else {}
        top3   = sorted_runners[:3]
        results_by_id[rid] = {
            "course":      race.get("course", "?"),
            "off":         race.get("off", "?"),
            "race_name":   race.get("race_name", race.get("name", "?"))[:40],
            "winner_horse":winner.get("horse", "?"),
            "winner_id":   winner.get("horse_id", ""),
            "winner_sp":   winner.get("sp_dec", 0),
            "top3_ids":    [r.get("horse_id","") for r in top3],
            "top3_names":  [r.get("horse","?") for r in top3],
            "full_runners": runners,
        }

    print(f"  Results indexed: {len(results_by_id)} races")

    # ── STEP 3: Reconcile ─────────────────────────────────────────────────────
    print("\nSTEP 3: Reconcile predictions vs actuals")

    hits        = []   # top pick won
    frames      = []   # top pick placed top 3
    misses      = []   # top pick outside top 3
    no_result   = []   # race result not found
    all_matched = []

    for race_id, pred in predictions.items():
        result = results_by_id.get(race_id)
        info   = horse_names.get(race_id, {})
        predicted_horse_id = pred.get("top_rank_horse_id", "")
        vpp = pred.get("velo_prime_prob", 0)

        if not result:
            no_result.append(race_id)
            continue

        is_hit   = predicted_horse_id == result["winner_id"]
        is_frame = predicted_horse_id in result["top3_ids"]
        miss_class = "n/a"

        if is_hit:
            hits.append(race_id)
            outcome = "HIT"
        elif is_frame:
            frames.append(race_id)
            outcome = "FRAME"
        else:
            outcome = "MISS"
            # Classify miss
            winner_sp = float(result.get("winner_sp") or 0)
            if winner_sp > 0 and winner_sp <= 3.0:
                miss_class = "short_fav_won"
            elif winner_sp > 10.0:
                miss_class = "outsider_won"
            else:
                miss_class = "mid_priced_won"
            misses.append(race_id)

        all_matched.append({
            "race_id":       race_id,
            "course":        result["course"],
            "off":           result["off"],
            "predicted":     info.get("horse", "?"),
            "predicted_id":  predicted_horse_id,
            "actual_winner": result["winner_id"],
            "actual_name":   result["winner_name"] if "winner_name" in result else result["winner_horse"],
            "winner_sp":     result["winner_sp"],
            "velo_prime_prob": vpp,
            "outcome":       outcome,
            "miss_class":    miss_class,
            "top3":          result["top3_names"],
        })

        symbol = "HIT" if is_hit else ("FRAME" if is_frame else f"MISS({miss_class})")
        pred_name = info.get("horse", "?")
        print(f"  {symbol:<25} {result['course']:<22} {result['off']}  "
              f"pred={pred_name:<22} actual={result['winner_horse']}")

    total_matched = len(all_matched)
    total_hits    = len(hits)
    total_frames  = len(frames)
    total_misses  = len(misses)
    strike_rate   = total_hits / total_matched if total_matched else 0
    frame_rate    = (total_hits + total_frames) / total_matched if total_matched else 0
    no_result_ct  = len(no_result)

    print(f"\n  Matched: {total_matched}  No result: {no_result_ct}")
    print(f"  HITS:    {total_hits} ({strike_rate:.1%})")
    print(f"  FRAMES:  {total_frames}")
    print(f"  MISSES:  {total_misses}")
    print(f"  Strike rate: {strike_rate:.1%}")
    print(f"  Frame rate:  {frame_rate:.1%}")

    # Miss class breakdown
    miss_classes = {}
    for r in all_matched:
        if r["outcome"] == "MISS":
            mc = r["miss_class"]
            miss_classes[mc] = miss_classes.get(mc, 0) + 1

    # ── STEP 4: runner_results note ───────────────────────────────────────────
    # runner_results has FK constraints to races + horse_profiles tables.
    # It is populated by the ingestion spine from actual result feeds.
    # Sigma reconciliation data goes to sigma_audits instead — do not write here.
    print("\nSTEP 4: runner_results — skipped (FK-constrained table owned by ingestion spine)")
    persist_ok = 0

    # ── STEP 5: Sigma calculation ──────────────────────────────────────────────
    print("\nSTEP 5: Sigma analysis")

    # Calibration: average velo_prime_prob for hits vs misses
    hit_probs  = [r["velo_prime_prob"] for r in all_matched if r["outcome"] == "HIT"]
    miss_probs = [r["velo_prime_prob"] for r in all_matched if r["outcome"] == "MISS"]
    avg_hit_prob  = sum(hit_probs)  / len(hit_probs)  if hit_probs  else 0
    avg_miss_prob = sum(miss_probs) / len(miss_probs) if miss_probs else 0

    # High-confidence picks (velo_prime_prob >= 0.30)
    high_conf = [r for r in all_matched if r["velo_prime_prob"] >= 0.30]
    high_hits = [r for r in high_conf if r["outcome"] == "HIT"]
    high_strike = len(high_hits) / len(high_conf) if high_conf else 0

    print(f"  avg prob (hits):    {avg_hit_prob:.4f}")
    print(f"  avg prob (misses):  {avg_miss_prob:.4f}")
    print(f"  high-conf picks:    {len(high_conf)} (prob>=0.30)")
    print(f"  high-conf strikes:  {len(high_hits)} ({high_strike:.1%})")

    # Doctrine patch: should we update sigma?
    sigma_note = ""
    if strike_rate >= 0.25:
        sigma_note = "ABOVE BASELINE — model calibration healthy"
    elif strike_rate >= 0.15:
        sigma_note = "AT BASELINE — review miss classes for pattern"
    else:
        sigma_note = "BELOW BASELINE — check miss_class distribution"

    # ── STEP 6: Persist sigma audit to Supabase ───────────────────────────────
    # Schema: race_id, date (date), track, outcome, miss_reason, top_pick_position,
    #         actual_winner_id, actual_winner_sp, notes, event_type, decision_tier
    # One row per race — insert (no unique key on run_date)
    print("\nSTEP 6: Persist sigma audit")
    sigma_ok = 0
    for row in all_matched:
        miss_reason = row["miss_class"] if row["outcome"] == "MISS" else None
        top_pos = 1 if row["outcome"] == "HIT" else (3 if row["outcome"] == "FRAME" else 99)
        sigma_row = {
            "race_id":           row["race_id"],
            "date":              race_date,
            "track":             row["course"],
            "event_type":        "sigma_reconciliation",
            "outcome":           row["outcome"],
            "decision_tier":     predictions.get(row["race_id"], {}).get("decision_tier"),
            "miss_reason":       miss_reason,
            "top_pick_position": top_pos,
            "actual_winner_id":  row["actual_winner"],
            "actual_winner_sp":  float(row["winner_sp"]) if row["winner_sp"] else None,
            "notes":             f"pred={row['predicted']} prob={row['velo_prime_prob']:.4f} {sigma_note}",
        }
        if sb_post("/sigma_audits", sigma_row):
            sigma_ok += 1
    print(f"  PASS: {sigma_ok}/{total_matched} sigma_audits rows written" if sigma_ok else "  FAIL: sigma_audits writes failed")

    # ── STEP 7: Update learned_patterns for consistent hits ───────────────────
    # Schema: pattern_name (unique), description, confidence_level (numeric),
    #         first_observed, last_observed, is_active
    print("\nSTEP 7: Learned patterns")
    now_iso = datetime.utcnow().isoformat()
    patterns_saved = 0
    for r in all_matched:
        if r["outcome"] == "HIT" and r["velo_prime_prob"] >= 0.25:
            pattern = {
                "pattern_name":    f"prime_hit_{r['race_id']}",
                "description":     f"PRIME hit: {r['predicted']} @ prob={r['velo_prime_prob']:.4f} won {r['course']} {r['off']}",
                "confidence_level": round(r["velo_prime_prob"], 4),
                "first_observed":  now_iso,
                "last_observed":   now_iso,
                "is_active":       True,
                "occurrences":     1,
                "successful_predictions": 1,
                "success_rate":    1.0,
            }
            if sb_upsert("/learned_patterns", pattern, "pattern_name"):
                patterns_saved += 1

    print(f"  Learned patterns saved: {patterns_saved}")

    # ── STEP 7b: Betting ledger write ─────────────────────────────────────────
    # For each B/C tier verdict with a matched result, write a ledger row.
    # Idempotent: race_ids already in ledger for this date are skipped explicitly.
    print("\nSTEP 7b: Betting ledger")
    STAKE = {"B": 10.0, "C": 5.0}
    ledger_ok = 0
    skip_reasons: dict = {
        "no_tier_match":   0,  # tier is A/D/X/null — not a betting tier
        "already_written": 0,  # race_id already in betting_ledger for this date
        "non_runner":      0,  # predicted horse absent from result set entirely
        "no_sp":           0,  # horse ran but sp_dec missing or ≤ 1.0
        "write_error":     0,  # DB upsert failed
    }

    # Get current bankroll tail — used as base for sequential bankroll
    try:
        bankroll_rows = sb_get("/betting_ledger?select=bankroll_after&order=placed_at.desc&limit=1")
        current_bankroll = float(bankroll_rows[0]["bankroll_after"]) if bankroll_rows else 1000.0
    except Exception:
        current_bankroll = 1000.0

    # Duplicate guard — load race_ids already written for this date
    try:
        existing_rows = sb_get(f"/betting_ledger?select=race_id&date=eq.{race_date}")
        existing_ledger_ids = {r["race_id"] for r in existing_rows}
    except Exception:
        existing_ledger_ids = set()

    # Build a lookup for decision_tier + confidence_level + generated_at from verdicts
    verdict_meta = {v["race_id"]: v for v in verdicts_raw}

    for row in all_matched:
        rid   = row["race_id"]
        vmeta = verdict_meta.get(rid, {})
        tier  = (vmeta.get("decision_tier") or "").upper()

        if tier not in STAKE:
            skip_reasons["no_tier_match"] += 1
            continue

        if rid in existing_ledger_ids:
            skip_reasons["already_written"] += 1
            print(f"    skip [already_written]: {row['predicted']} ({rid})")
            continue

        stake = STAKE[tier]
        # Find predicted horse's SP from full_runners list
        full_runners = results_by_id.get(rid, {}).get("full_runners", [])
        pred_sp = None
        horse_in_results = False
        for runner in full_runners:
            if runner.get("horse_id") == row["predicted_id"]:
                horse_in_results = True
                try:
                    pred_sp = float(runner.get("sp_dec") or 0) or None
                except (ValueError, TypeError):
                    pass
                break

        if not pred_sp or pred_sp <= 1.0:
            if not horse_in_results:
                skip_reasons["non_runner"] += 1
                print(f"    skip [non_runner]: {row['predicted']} ({rid}) — not in result set")
            else:
                skip_reasons["no_sp"] += 1
                print(f"    skip [no_sp]: {row['predicted']} ({rid}) — sp_dec absent or ≤ 1.0")
            continue

        is_win     = row["outcome"] == "HIT"
        pl         = round(stake * (pred_sp - 1), 2) if is_win else round(-stake, 2)
        returns    = round(stake * pred_sp, 2) if is_win else 0.0
        bankroll_before = round(current_bankroll, 2)
        bankroll_after  = round(current_bankroll + pl, 2)
        current_bankroll = bankroll_after

        placed_at = vmeta.get("generated_at") or datetime.utcnow().isoformat() + "Z"

        # confidence_level stores the verdict label as a numeric proxy:
        #   high → 1.0 | normal → 0.5 | low → 0.25
        # velo_prime_prob (raw win probability) is captured in reasoning.
        conf_label   = (vmeta.get("confidence_level") or "low").lower()
        conf_numeric = {"high": 1.0, "normal": 0.5, "low": 0.25}.get(conf_label, 0.25)

        ledger_row = {
            "race_id":          rid,
            "date":             race_date,
            "course":           row["course"],
            "race_time":        f"{race_date}T{row['off']}:00" if row.get("off") else placed_at,
            "horse":            row["predicted"],
            "bet_type":         tier,
            "stake":            stake,
            "odds":             pred_sp,
            "result":           "WIN" if is_win else "LOSS",
            "returns":          returns,
            "profit_loss":      pl,
            "bankroll_before":  bankroll_before,
            "bankroll_after":   bankroll_after,
            "confidence_level": conf_numeric,
            "reasoning":        f"velo_prime_v1 | tier={tier} | conf={conf_label} | prob={row['velo_prime_prob']:.4f} | outcome={row['outcome']} | sp={pred_sp}",
            "placed_at":        placed_at,
            "settled_at":       datetime.utcnow().isoformat() + "Z",
        }
        if sb_upsert("/betting_ledger", ledger_row, "race_id"):
            ledger_ok += 1
        else:
            skip_reasons["write_error"] += 1
            print(f"    skip [write_error]: {row['predicted']} ({rid})")

    print(f"  Ledger rows written: {ledger_ok}")
    for reason, count in skip_reasons.items():
        if count:
            print(f"    skip [{reason}]: {count}")

    # ── STEP 8: Telegram sigma report ─────────────────────────────────────────
    print("\nSTEP 8: Telegram sigma report")

    # A. Hits
    hit_lines = []
    for r in all_matched:
        if r["outcome"] == "HIT":
            hit_lines.append(f"  HIT  {r['course']:<18} {r['off']}  {r['predicted']} (prob={r['velo_prime_prob']:.4f})")

    # B. Notable misses (high prob but missed)
    notable_misses = sorted(
        [r for r in all_matched if r["outcome"] == "MISS" and r["velo_prime_prob"] >= 0.25],
        key=lambda r: -r["velo_prime_prob"]
    )

    # C. Frame picks (2nd/3rd)
    frame_lines = [r for r in all_matched if r["outcome"] == "FRAME"]

    # Main sigma report
    sigma_msg = (
        f"VELO SIGMA REPORT — {TODAY_DISPLAY}\n"
        f"{'=' * 35}\n"
        f"Races evaluated:  {total_matched}\n"
        f"Hits (1st):       {total_hits}  ({strike_rate:.1%})\n"
        f"Frames (top 3):   {total_hits + total_frames}  ({frame_rate:.1%})\n"
        f"Misses:           {total_misses}\n"
        f"\n"
        f"High-conf (>=0.30): {len(high_conf)} picks, {len(high_hits)} hits ({high_strike:.1%})\n"
        f"Avg prob (hits):    {avg_hit_prob:.4f}\n"
        f"Avg prob (misses):  {avg_miss_prob:.4f}\n"
        f"\n"
        f"SIGMA: {sigma_note}\n"
        f"Engine: velo_prime_v1 (SQPE v17 + specialists)"
    )
    tg(sigma_msg)
    print(f"  Sent: main sigma report")

    # Hits breakdown
    if hit_lines:
        tg("VELO HITS — " + TODAY_DISPLAY + "\n" + "\n".join(hit_lines))
        print(f"  Sent: {len(hit_lines)} hits")

    # Miss class breakdown
    miss_breakdown = "\n".join([f"  {k}: {v}" for k, v in sorted(miss_classes.items(), key=lambda x: -x[1])])
    tg(
        f"VELO MISS ANALYSIS — {TODAY_DISPLAY}\n"
        f"Miss classes:\n{miss_breakdown}\n"
        f"\nNotable fades (prob>=0.25 but missed):\n" +
        "\n".join([
            f"  {r['course']} {r['off']}  {r['predicted']} (prob={r['velo_prime_prob']:.4f}) — won: {r['actual_name']}"
            for r in notable_misses[:5]
        ] or ["  none"])
    )
    print(f"  Sent: miss analysis ({len(notable_misses)} notable fades)")

    # Frame picks
    if frame_lines:
        frame_msg = "VELO FRAMES (placed 2nd/3rd) — " + TODAY_DISPLAY + "\n"
        frame_msg += "\n".join([
            f"  {r['course']} {r['off']}  {r['predicted']} placed — won: {r['actual_name']}"
            for r in frame_lines[:10]
        ])
        tg(frame_msg)
        print(f"  Sent: {len(frame_lines)} frames")

    # Final report
    tg(
        f"VELO RESULTS COMPLETE — {TODAY_DISPLAY}\n"
        f"Races: {total_matched}\n"
        f"Strike rate: {strike_rate:.1%}\n"
        f"Frame rate:  {frame_rate:.1%}\n"
        f"Ledger bets: {ledger_ok}  bankroll: £{current_bankroll:.2f}\n"
        f"Supabase: sigma_audits={sigma_ok}  learned_patterns={patterns_saved}\n"
        f"Status: COMPLETE"
    )
    print(f"  Sent: final report")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"SIGMA COMPLETE — {race_date}")
    print(f"  Strike rate:  {strike_rate:.1%} ({total_hits}/{total_matched})")
    print(f"  Frame rate:   {frame_rate:.1%} ({total_hits+total_frames}/{total_matched})")
    print(f"  Miss classes: {miss_classes}")
    print(f"  Sigma note:   {sigma_note}")
    print(f"  Supabase:     sigma_audits={sigma_ok} learned_patterns={patterns_saved}")


if __name__ == "__main__":
    main()
