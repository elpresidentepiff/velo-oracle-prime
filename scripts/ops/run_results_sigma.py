
def _norm_course(value: str) -> str:
    """Canonical normalized course name."""
    import re as _re
    v = str(value or "").strip().lower()
    v = v.replace("(aw)", "").replace("aw", "").strip()
    return _re.sub(r"[^a-z]", "", v)
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

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
import uuid
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.core.runtime_env import load_optional_env_file, utc_now_iso  # noqa: E402

load_optional_env_file(ROOT / ".env")

from src.constants import (  # noqa: E402
    validate_outcome,
    validate_tier,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TODAY = date.today().strftime("%Y-%m-%d")
TODAY_DISPLAY = date.today().strftime("%d %b %Y")

RACING_USER = os.getenv("RACING_API_USERNAME", "")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "")
RACING_BASE = "https://api.theracingapi.com/v1"
# User-Agent required — Cloudflare blocks without it
RACING_HEADERS = {
    "Authorization": "Basic " + base64.b64encode(f"{RACING_USER}:{RACING_PASS}".encode()).decode(),
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


def _candidate_bst_times(off_time: str) -> list[str]:
    """Generate ±3-minute candidate BST time strings (HH.MM) for course-time fallback matching."""
    try:
        h, m = map(int, off_time.replace(":", ".").split("."))
        total = h * 60 + m
        cands = []
        for delta in range(-3, 4):
            t = total + delta
            cands.append(f"{t // 60:02d}.{t % 60:02d}")
        return cands
    except Exception:
        return [off_time]

SIGMA_SERVICE = "velo-results-sigma"
SIGMA_RUN_TYPE = "results_reconciliation_light"


def _pipeline_request(method: str, path: str, data: dict | None = None) -> tuple[int, bytes]:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1{path}",
        data=body,
        method=method,
        headers={**SB_HEADERS, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b""
    except Exception as exc:  # pragma: no cover
        return 0, str(exc).encode()


def _open_sigma_run(source_date: str) -> str | None:
    existing_run_id = (os.getenv("PIPELINE_RUN_ID") or "").strip()
    if existing_run_id:
        return existing_run_id
    if not SB_URL or not SB_KEY:
        return None
    run_id = str(uuid.uuid4())
    status, _body = _pipeline_request(
        "POST",
        "/pipeline_runs",
        {
            "id": run_id,
            "service_name": SIGMA_SERVICE,
            "run_type": SIGMA_RUN_TYPE,
            "source_date": source_date,
            "run_state": "running",
            "status": "TRIGGERED",
            "trigger_source": os.getenv("TRIGGER_SOURCE", "manual") or "manual",
            "started_at": utc_now_iso(),
            "environment": os.getenv("RAILWAY_ENVIRONMENT", "production"),
        },
    )
    return run_id if status in (200, 201) else None


def _close_sigma_run(run_id: str | None, *, status: str, error: str | None = None) -> None:
    if not run_id or not SB_URL or not SB_KEY:
        return
    patch = {
        "run_state": "completed",
        "status": status,
        "finished_at": utc_now_iso(),
    }
    if error:
        patch["error_message"] = error[:500]
    _pipeline_request("PATCH", f"/pipeline_runs?id=eq.{run_id}", patch)


# ── helpers ──────────────────────────────────────────────────────────────────


def tg(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print(f"[TG SKIP]: {text[:60]}")
        return False
    try:
        body = json.dumps({"chat_id": CHAT_ID, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=body, headers={"Content-Type": "application/json"}
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
        data=body,
        headers=SB_HEADERS,
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [SB POST FAIL] {path}: {e}")
        return False


def _off_to_timestamp(race_date: str, off: str) -> str:
    """Convert VELO off time '2.30' (H.MM) to ISO timestamp '2026-05-25T14:30:00'."""
    try:
        h, m = off.split(".")
        h = int(h)
        m = int(m)
        # VELO times are BST afternoon: 1-9 maps to 13:00-21:00, else morning
        if 1 <= h <= 9:
            h += 12
        return f"{race_date}T{h:02d}:{m:02d}:00"
    except Exception:
        return race_date + "T00:00:00"


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
    parser.add_argument("--source", default="api")
    parser.add_argument("--date", default=None)
    parser.add_argument("--min-coverage", type=float, default=None,
                        help="Override completeness gate threshold (0-1). Use when Irish/blocked venues are known to be inaccessible.")
    args = parser.parse_args()
    race_date = args.date or TODAY
    run_id = _open_sigma_run(race_date)
    os.environ["_ACTIVE_SIGMA_RUN_ID"] = run_id or ""

    print(f"\nVELO RESULTS + SIGMA — {race_date}")
    print("=" * 60)

    # ── PREFLIGHT GATE ────────────────────────────────────────────────────────
    print("\nPREFLIGHT")
    from src.preflight import preflight_or_die

    preflight_or_die(tg_fn=tg)  # exits with sys.exit(1) on FAIL
    # ─────────────────────────────────────────────────────────────────────────

    # ── STEP 1: Load today's predictions from Supabase ────────────────────────
    print("\nSTEP 1: Load predictions from velo_verdicts")
    verdicts_raw = sb_get(
        f"/velo_verdicts?select=race_id,top_rank_horse_id,velo_prime_prob,decision_tier,confidence_level,generated_at,full_analysis"
        f"&generated_at=gte.{race_date}T00:00:00"
        f"&generated_at=lt.{race_date}T23:59:59"
        f"&order=generated_at"
    )
    if not verdicts_raw:
        # Scoring runs past midnight UTC land on race_date+1 — widen by 12h and
        # filter by race_id prefix so we don't pull in the wrong day's verdicts.
        from datetime import timedelta
        race_date_obj = datetime.strptime(race_date, "%Y-%m-%d").date()
        next_day = (race_date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        date_tag = race_date.replace("-", "")  # e.g. "20260529"
        extended = sb_get(
            f"/velo_verdicts?select=race_id,top_rank_horse_id,velo_prime_prob,decision_tier,confidence_level,generated_at,full_analysis"
            f"&generated_at=gte.{next_day}T00:00:00"
            f"&generated_at=lt.{next_day}T12:00:00"
            f"&order=generated_at"
        )
        verdicts_raw = [v for v in (extended or []) if date_tag in v.get("race_id", "")]
        if verdicts_raw:
            print(f"  [INFO] Found {len(verdicts_raw)} verdicts via overnight window (generated_at={next_day})")
    print(f"  Predictions loaded: {len(verdicts_raw)}")
    if not verdicts_raw:
        print("  ABORT: no predictions found for this date")
        tg(f"VELO SIGMA ABORT — {race_date}\nNo predictions found in velo_verdicts.")
        sys.exit(1)

    # Filter: only keep verdicts whose race_id contains today's date (YYYYMMDD).
    # Verdicts for prior days can appear if generated_at falls on today (overnight runs).
    _date_tag = race_date.replace("-", "")  # e.g. "20260530"
    _pre_filter = len(verdicts_raw)
    verdicts_raw = [v for v in verdicts_raw if _date_tag in str(v.get("race_id", ""))]
    if len(verdicts_raw) < _pre_filter:
        print(f"  [INFO] Filtered {_pre_filter - len(verdicts_raw)} verdicts with wrong date in race_id")

    # Build lookup: race_id -> verdict row (keep latest generated_at if duplicates exist)
    predictions: dict = {}
    degraded_count = 0
    for v in verdicts_raw:
        # ── Learning Block Detection ──────────────────────────────────────────
        # Check if the run was feature-degraded (>80% of core features missing)
        try:
            full = v.get("full_analysis") or {}
            preds_list = full.get("predictions") or []
            if preds_list:
                excluded = preds_list[0].get("excluded_from_ensemble") or []
                if "improvement_score" in excluded or "market_deception_score" in excluded:
                    degraded_count += 1
        except Exception:
            pass

        rid = v["race_id"]
        if rid not in predictions:
            predictions[rid] = v
        else:
            # Keep the row with the latest generated_at
            existing_ts = predictions[rid].get("generated_at") or ""
            new_ts = v.get("generated_at") or ""
            if new_ts > existing_ts:
                if (predictions[rid].get("top_rank_horse_id") or "") != (v.get("top_rank_horse_id") or ""):
                    print(f"  [WARN] multiple conflicting verdicts for {rid}, using latest generated_at")
                predictions[rid] = v
    
    is_degraded_day = (degraded_count / len(verdicts_raw)) > 0.80 if verdicts_raw else False
    if is_degraded_day:
        print(f"  ⚠ LEARNING BLOCK: {degraded_count}/{len(verdicts_raw)} verdicts are FEATURE_DEGRADED.")
        print("  ⚠ Sigma will reconcile results but will NOT update learned_patterns.")
    else:
        print(f"  Feature integrity: OK ({len(verdicts_raw) - degraded_count}/{len(verdicts_raw)} full features)")

    # ── Gap 2: resolve pick horse names from velo_verdicts.selections ─────────
    # Primary source: Supabase velo_verdicts.selections JSON array.
    # Fallback: local backup JSON (flagged with [fallback] tag).
    horse_names: dict = {}

    # Build local backup index first (used as fallback below)
    backup = ROOT / "data" / f"velo_prime_verdicts_{race_date.replace('-', '_')}.json"
    local_backup: dict = {}
    if backup.exists():
        try:
            for r in json.loads(backup.read_text()):
                top = r.get("top", {})
                local_backup[r["race_id"]] = {
                    "horse": top.get("horse", "?"),
                    "course": r.get("course", "?"),
                    "off_time": r.get("off_time", "?"),
                }
        except Exception as e:
            print(f"  [WARN] local backup JSON unreadable: {e}")

    for rid, v in predictions.items():
        top_horse_id = v.get("top_rank_horse_id") or ""
        selections_raw = v.get("full_analysis")

        # Parse selections — may arrive as string or list depending on Supabase client
        selections = []
        if isinstance(selections_raw, list):
            selections = selections_raw
        elif isinstance(selections_raw, str):
            try:
                selections = json.loads(selections_raw)
            except Exception:
                selections = []

        pick_name = None
        if top_horse_id and selections:
            for sel in selections:
                if not isinstance(sel, dict):
                    continue
                # selections entries may use horse_id or id
                sel_hid = sel.get("horse_id") or sel.get("id") or ""
                if sel_hid == top_horse_id:
                    pick_name = sel.get("horse") or sel.get("name") or sel.get("horse_name")
                    break
            # If top_rank_horse_id not matched in selections, try rank position 0
            if pick_name is None and selections:
                first = selections[0]
                if isinstance(first, dict):
                    pick_name = first.get("horse") or first.get("name") or first.get("horse_name")

        if pick_name:
            horse_names[rid] = {
                "horse": pick_name,
                "course": "?",  # not in velo_verdicts; filled from results lookup below
                "off_time": "?",
                "from_db": True,
            }
        else:
            # Fallback to local JSON backup
            fb = local_backup.get(rid)
            if fb:
                print(f"  [WARN] pick name from local fallback for race {rid}")
                horse_names[rid] = {
                    "horse": fb["horse"],
                    "course": fb.get("course", "?"),
                    "off_time": fb.get("off_time", "?"),
                    "from_db": False,
                }
            else:
                horse_names[rid] = {"horse": "?", "course": "?", "off_time": "?", "from_db": False}
    # ── STEP 2: Load results ─────────────────────────────────
    print("\nSTEP 2: Load results")
    source = "api"
    for i, arg in enumerate(sys.argv):
        if arg == "--source" and i+1 < len(sys.argv): source = sys.argv[i+1]
    
    if source == "cache":
        results_path = ROOT / "data" / "results" / f"rp_results_{race_date.replace('-', '_')}.json"
        print(f"  Loading from cache: {results_path}")
        if not results_path.exists():
             print(f"  FAILED: local results not found at {results_path}")
             sys.exit(1)
        import json as _json
        _raw = _json.loads(results_path.read_text())
        # Handle SL scraper format: {"results": [...]} wrapper
        results_list = _raw if isinstance(_raw, list) else _raw.get("results", [])
        # Normalise SL-format results: derive winner/top3/off_time if missing
        for _r in results_list:
            if "winner_id" not in _r and "runners" in _r:
                _DNF = {"NR","WD","PU","F","BD","UR","SU","RO","REF","DSQ",""}
                def _pos(x):
                    p = str(x.get("position","")).strip()
                    return int(p) if p.isdigit() else 999
                _sorted = sorted(_r["runners"], key=_pos)
                _top3 = [x for x in _sorted if str(x.get("position","")).strip() in ("1","2","3")]
                _w = _top3[0] if _top3 else {}
                _r["winner_id"]    = _w.get("horse_id","")
                _r["winner_name"]  = _w.get("horse","")
                _r["winner_horse"] = _w.get("horse","")
                _r["winner_sp"]    = _w.get("sp_dec", 0)
                _r["top3_ids"]     = [x.get("horse_id","") for x in _top3]
                _r["top3_names"]   = [x.get("horse","") for x in _top3]
                _r["full_runners"] = _r["runners"]
            # Ensure 24h off_time for course-time fallback (SL uses H.MM 12h)
            if "off_time" not in _r:
                _off = str(_r.get("off",""))
                try:
                    _h, _m = map(int, _off.split("."))
                    if _h < 11:
                        _h += 12
                    _r["off_time"] = f"{_h:02d}.{_m:02d}"
                except Exception:
                    _r["off_time"] = _off
        print(f"  Results loaded: {len(results_list)}")
    else:
        print("  Fetching from API...")
        results_list = []
        skip = 0
        page_size = 50
        while True:
            d = racing_get(f"/results?start_date={race_date}&end_date={race_date}&limit={page_size}&skip={skip}")
            page = d if isinstance(d, list) else d.get("results", [])
            results_list.extend(page)
            if len(page) < page_size: break
            skip += page_size
    # ── STEP 3: Reconcile ─────────────────────────────────────────────────────
    print("\nSTEP 3: Reconcile predictions vs actuals")
    results_by_id = {str(r.get("race_id")): r for r in results_list if r.get("race_id")}
    # Also index by normalised 24h-underscore race_id so SL 12h-period IDs match VELO prediction IDs.
    # e.g. rp_CAR_20260530_1.30 → rp_CAR_20260530_13_30
    import re as _re_id
    for _r in results_list:
        _rid = str(_r.get("race_id",""))
        _m = _re_id.match(r"(rp_[A-Z]+_\d{8})_(\d+)\.(\d{2})$", _rid)
        if _m:
            _h, _mn = int(_m.group(2)), int(_m.group(3))
            if _h < 11: _h += 12
            _norm_rid = f"{_m.group(1)}_{_h:02d}_{_mn:02d}"
            if _norm_rid not in results_by_id:
                results_by_id[_norm_rid] = _r

    # Secondary index keyed by (norm_course, off_time) for course-time fallback.
    results_by_course_time: dict = {}
    for r in results_list:
        c = _norm_course(r.get("course", "") or r.get("course_name", ""))
        ot = r.get("off_time", "")
        if c and ot:
            results_by_course_time[(c, ot)] = r

    hits = []  # top pick won
    frames = []  # top pick placed top 3
    misses = []  # top pick outside top 3
    no_result = []  # race result not found
    non_runners = []  # predicted horse did not participate (F/PU/BD/UR/WD/NR)
    all_matched = []

    # Positions that mean "did not finish / was not a runner" — exclude from stats
    DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", ""}

    for race_id, pred in predictions.items():
        predicted_horse_id = str(pred.get("top_rank_horse_id", "") or "")
        vpp = pred.get("velo_prime_prob", 0)
        info = horse_names.get(race_id, {})
        
        # ── Step 3.1: Race Reconciliation (ID-First) ──────────────────────────
        result = results_by_id.get(race_id)
        provenance = "UNRESOLVED"
        via_course_time = False

        if result:
            provenance = "MATCH_EXACT_ID"
        else:
            # Fallback: match by course + off_time
            fb = local_backup.get(race_id, {})
            fb_course = _norm_course(fb.get("course", ""))
            fb_off = fb.get("off_time", "")
            if fb_course and fb_off:
                for bst_cand in _candidate_bst_times(fb_off):
                    result = results_by_course_time.get((fb_course, bst_cand))
                    if result:
                        provenance = "MATCH_COURSE_TIME"
                        via_course_time = True
                        break
        
        if not result:
            no_result.append(race_id)
            continue

        # ── Step 3.2: Integrity Gate ──────────────────────────────────────────
        if not predicted_horse_id and not info.get("horse"):
            print(f"  [SKIP] {race_id}: no horse_id and no name — unresolvable")
            no_result.append(race_id)
            continue

        # ── Step 3.3: Horse Reconciliation (ID-First) ─────────────────────────
        horse_result = None
        
        # 1. Match by exact horse_id
        if predicted_horse_id:
            for runner in result.get("full_runners", result.get("runners", [])):
                if str(runner.get("horse_id")) == predicted_horse_id:
                    horse_result = runner
                    provenance += "_HID"
                    break
        
        # 2. Fallback to name match
        if not horse_result and info.get("horse"):
            pred_name_norm = _norm_course(info["horse"]) # reuse course norm for basic string cleaning
            for runner in result.get("full_runners", result.get("runners", [])):
                if _norm_course(runner.get("horse", "")) == pred_name_norm:
                    horse_result = runner
                    provenance += "_NAME"
                    break
        
        if not horse_result:
            print(f"  [WARN] {race_id}: race matched ({provenance}) but horse {predicted_horse_id}/{info.get('horse')} not found")
            no_result.append(race_id)
            continue

        # ── Step 3.4: Non-runner check ────────────────────────────────────────
        pos = str(horse_result.get("position", "")).strip().upper()
        if pos in DNF_POSITIONS:
            non_runners.append(race_id)
            print(f"  [NR] {race_id}: {info.get('horse','?')} — pos={pos or 'NR'} — excluded")
            continue

        # ── Step 3.5: Outcomes ────────────────────────────────────────────────
        # Use horse_result to determine WIN/PLACE status
        is_hit = pos == "1"
        is_frame = pos in ("1", "2", "3")
        
        miss_class = "n/a"
        if is_hit:
            hits.append(race_id)
            outcome = "WIN"
        elif is_frame:
            frames.append(race_id)
            outcome = "PLACED"
        else:
            outcome = "MISS"
            winner_sp = float(result.get("winner_sp") or 0)
            if winner_sp > 0 and winner_sp <= 3.0: miss_class = "short_fav_won"
            elif winner_sp > 10.0: miss_class = "outsider_won"
            else: miss_class = "mid_priced_won"
            misses.append(race_id)

        all_matched.append(
            {
                "race_id": race_id,
                "course": result["course"],
                "off": result["off"],
                "predicted": info.get("horse", "?"),
                "predicted_id": predicted_horse_id,
                "reconciliation_provenance": provenance,
                "actual_winner": result.get("winner_id", "?"),
                "winner_sp": result.get("winner_sp", 0),
                "velo_prime_prob": vpp,
                "outcome": outcome,
                "miss_class": miss_class,
                "top3": result.get("top3_names", []),
            }
        )

        symbol = "WIN" if is_hit else ("PLACED" if is_frame else f"MISS({miss_class})")
        print(f"  {symbol:<25} {result['course']:<22} {result['off']}  pred={info.get('horse','?'):<30} [{provenance}]")


    total_matched = len(all_matched)
    total_hits = len(hits)
    total_frames = len(frames)
    total_misses = len(misses)
    total_nr = len(non_runners)
    strike_rate = total_hits / total_matched if total_matched else 0
    frame_rate = (total_hits + total_frames) / total_matched if total_matched else 0
    no_result_ct = len(no_result)

    print(f"\n  Matched: {total_matched}  No result: {no_result_ct}  Non-runners excluded: {total_nr}")
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

    # ── COMPLETENESS GATE ─────────────────────────────────────────────────────
    # Sigma must have >= 95% result coverage before any learning or final reporting.
    # Below threshold: write DIAGNOSTIC artifact only. NO sigma_audits. NO learning.
    # NO Telegram final. NO Council/Mission Control finalization.
    COMPLETENESS_THRESHOLD = args.min_coverage if args.min_coverage is not None else 0.95
    expected_races = len(predictions)
    coverage_ratio = total_matched / expected_races if expected_races else 0
    is_incomplete = coverage_ratio < COMPLETENESS_THRESHOLD

    if is_incomplete:
        _needed = int(expected_races * COMPLETENESS_THRESHOLD) + 1
        _coverage_pct = f"{coverage_ratio:.1%}"
        print(f"\n{'=' * 60}")
        print("COMPLETENESS GATE — BLOCKED")
        print(f"  Expected races:  {expected_races}")
        print(f"  Matched:         {total_matched} ({_coverage_pct})")
        print(f"  Threshold:       {COMPLETENESS_THRESHOLD:.0%} (need ≥{_needed})")
        print(f"  Status:          SIGMA_RESULTS_INCOMPLETE_BLOCKED")
        print(f"  Learning:        BLOCKED")
        print(f"  Final reports:   BLOCKED")
        print(f"  Action:          Obtain full result source for all {expected_races} races, then rerun.")

        _gate_msg = (
            f"SIGMA_RESULTS_INCOMPLETE_BLOCKED — {TODAY_DISPLAY}\n"
            f"Expected: {expected_races} races scored\n"
            f"Matched:  {total_matched} ({_coverage_pct}) — need ≥{_needed} ({COMPLETENESS_THRESHOLD:.0%})\n"
            f"Unmatched: {no_result_ct} races have no result\n"
            f"\nClassification: PARTIAL_RESULTS_DIAGNOSTIC_ONLY\n"
            f"Learning: BLOCKED\n"
            f"Final reports: BLOCKED\n"
            f"\nAction: Full result source required covering all {expected_races} races.\n"
            f"Rerun Sigma when complete coverage is available."
        )
        tg(_gate_msg)

        _sigma_dir = ROOT / "data" / "sigma_results"
        _sigma_dir.mkdir(parents=True, exist_ok=True)
        _diag = {
            "date": race_date,
            "generated_at": utc_now_iso(),
            "sigma_status": "PARTIAL_RESULTS_DIAGNOSTIC_ONLY",
            "completeness_gate": "BLOCKED",
            "expected_predictions": expected_races,
            "result_races_available": len(results_by_id),
            "matched": total_matched,
            "coverage_ratio": round(coverage_ratio, 4),
            "threshold": COMPLETENESS_THRESHOLD,
            "no_result_count": no_result_ct,
            "learning_blocked": True,
            "telegram_final_blocked": True,
            "sigma_audits_written": 0,
            "learned_patterns": 0,
            "miss_classes": miss_classes,
            "diagnostic_rows": [
                {
                    "race_id": r["race_id"],
                    "course": r["course"],
                    "off": r["off"],
                    "predicted": r["predicted"],
                    "outcome": r["outcome"],
                    "velo_prime_prob": r["velo_prime_prob"],
                    "miss_class": r.get("miss_class"),
                }
                for r in all_matched
            ],
        }
        _dated_path = _sigma_dir / f"sigma_results_{race_date.replace('-', '_')}.json"
        _dated_path.write_text(json.dumps(_diag, indent=2))
        print(f"\nDiagnostic artifact: {_dated_path}")
        print(f"{'=' * 60}")
        _close_sigma_run(run_id, status="FAIL", error="SIGMA_RESULTS_INCOMPLETE_BLOCKED")
        sys.exit(2)

    # ── STEP 4: runner_results note ───────────────────────────────────────────
    # runner_results has FK constraints to races + horse_profiles tables.
    # It is populated by the ingestion spine from actual result feeds.
    # Sigma reconciliation data goes to sigma_audits instead — do not write here.
    print("\nSTEP 4: runner_results — skipped (FK-constrained table owned by ingestion spine)")

    # ── STEP 5: Sigma calculation ──────────────────────────────────────────────
    print("\nSTEP 5: Sigma analysis")

    # Calibration: average velo_prime_prob for hits vs misses
    hit_probs = [r["velo_prime_prob"] for r in all_matched if r["outcome"] == "WIN"]
    miss_probs = [r["velo_prime_prob"] for r in all_matched if r["outcome"] == "MISS"]
    avg_hit_prob = sum(hit_probs) / len(hit_probs) if hit_probs else 0
    avg_miss_prob = sum(miss_probs) / len(miss_probs) if miss_probs else 0

    # High-confidence picks (velo_prime_prob >= 0.30)
    high_conf = [r for r in all_matched if r["velo_prime_prob"] >= 0.30]
    high_hits = [r for r in high_conf if r["outcome"] == "WIN"]
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
        _tier_raw = predictions.get(row["race_id"], {}).get("decision_tier")
        if _tier_raw == "X":
            print(f"  [BLOCK] {row['race_id']}: tier X blocked from sigma audit")
            continue

        miss_reason = row["miss_class"] if row["outcome"] == "MISS" else None

        # Gap 1: fetch actual finishing position from runner_results.
        # Primary source: runner_results.position (written by close_sigma_loops.py).
        # runner_race_facts.finishing_position is never populated — do not read it.
        # If position is NULL or query fails: write None — never manufacture 1/3/99.
        top_pos = None
        _pos_note = ""
        try:
            rr_rows = sb_get(
                f"/runner_results"
                f"?select=position"
                f"&race_id=eq.{row['race_id']}"
                f"&horse_id=eq.{row['predicted_id']}"
                f"&limit=1"
            )
            if rr_rows and rr_rows[0].get("position") is not None:
                top_pos = int(rr_rows[0]["position"])
            else:
                _pos_note = "finishing_position_null"
                print(
                    f"  [SKIP-POS] {row['race_id']}/{row['predicted_id']}: position not in runner_results — writing NULL"
                )
        except Exception as _fp_err:
            _pos_note = f"finishing_position_error: {_fp_err}"
            print(
                f"  [SKIP-POS] {row['race_id']}/{row['predicted_id']}: runner_results fetch failed — writing NULL: {_fp_err}"
            )

        # Full-field RPD: read rpd_tag per runner from velo_verdicts.selections
        # Primary source: selections already stored by run_prime_today.py.
        # Runners absent from selections get rpd_tag=UNKNOWN.
        _pred_sel_raw = predictions.get(row["race_id"], {}).get("full_analysis")
        if isinstance(_pred_sel_raw, list):
            _pred_sel = _pred_sel_raw
        elif isinstance(_pred_sel_raw, str):
            try:
                _pred_sel = json.loads(_pred_sel_raw)
            except Exception:
                _pred_sel = []
        else:
            _pred_sel = []

        _sel_by_hid: dict = {}
        for _s in _pred_sel:
            if isinstance(_s, dict):
                _hid = _s.get("horse_id") or _s.get("id") or ""
                if _hid:
                    _sel_by_hid[_hid] = {
                        "rpd_tag": _s.get("rpd_tag"),
                        "rpd_confidence": _s.get("rpd_confidence"),
                        "rpd_evidence": _s.get("rpd_evidence_codes") or _s.get("rpd_evidence"),
                    }

        _full_runners = results_by_id.get(row["race_id"], {}).get("full_runners", [])
        _sorted_runners = sorted(
            [_r for _r in _full_runners if str(_r.get("position", "")).isdigit()], key=lambda _r: int(_r["position"])
        )
        full_field_rpd = []
        for _r in _sorted_runners:
            _rhid = _r.get("horse_id", "")
            _rpd = _sel_by_hid.get(_rhid, {})
            full_field_rpd.append(
                {
                    "pos": int(_r["position"]),
                    "horse": _r.get("horse", "?"),
                    "horse_id": _rhid,
                    "rpd_tag": _rpd.get("rpd_tag") or "UNKNOWN",
                    "rpd_confidence": _rpd.get("rpd_confidence"),
                    "rpd_evidence": _rpd.get("rpd_evidence"),
                }
            )

        _notes_summary = (
            f"pred={row['predicted']}"
            f" | prob={row['velo_prime_prob']:.4f} {sigma_note}"
            f" | winner_name={row['top3'][0] if row['top3'] else '?'}"
            f" | place2={row['top3'][1] if len(row['top3']) > 1 else 'unknown'}"
            f" | place3={row['top3'][2] if len(row['top3']) > 2 else 'unknown'}"
            + (f" | pos_note={_pos_note}" if _pos_note else "")
        )

        # Hard validate before write — non-canonical outcome raises ValueError (aborts row)
        try:
            validate_outcome(row["outcome"])
            _tier_raw = predictions.get(row["race_id"], {}).get("decision_tier")
            if _tier_raw:
                validate_tier(_tier_raw)
        except ValueError as _ve:
            print(f"  [CANON REJECT] {row['race_id']}: {_ve}")
            continue

        sigma_row = {
            "race_id": row["race_id"],
            "date": race_date,
            "track": row["course"],
            "off_time": row.get("off") or None,  # race start time
            "event_type": "sigma_reconciliation",
            "outcome": row["outcome"],
            "decision_tier": predictions.get(row["race_id"], {}).get("decision_tier"),
            "miss_reason": miss_reason,
            "top_pick_position": top_pos,
            "actual_winner_id": row["actual_winner"],
            "actual_winner_name": row.get("actual_name") or None,  # winner name
            "actual_winner_sp": float(row["winner_sp"]) if row["winner_sp"] else None,
            "notes": json.dumps(
                {
                    "summary": _notes_summary,
                    "full_field_rpd": full_field_rpd,
                }
            ),
        }
        if sb_upsert("/sigma_audits", sigma_row, "race_id"):
            sigma_ok += 1
    print(
        f"  PASS: {sigma_ok}/{total_matched} sigma_audits rows written"
        if sigma_ok
        else "  FAIL: sigma_audits writes failed"
    )

    # ── STEP 7: Update learned_patterns for consistent hits ───────────────────
    # Schema: pattern_name (unique), description, confidence_level (numeric),
    #         first_observed, last_observed, is_active
    print("\nSTEP 7: Learned patterns")
    now_iso = utc_now_iso()
    patterns_saved = 0
    if is_degraded_day:
        print("  SKIPPED: Learning blocked due to FEATURE_DEGRADED status.")
    else:
        for r in all_matched:
            if r["outcome"] == "WIN" and r["velo_prime_prob"] >= 0.25:
                pattern = {
                    "pattern_name": f"prime_hit_{r['race_id']}",
                    "description": f"PRIME hit: {r['predicted']} @ prob={r['velo_prime_prob']:.4f} won {r['course']} {r['off']}",
                    "confidence_level": round(r["velo_prime_prob"], 4),
                    "first_observed": now_iso,
                    "last_observed": now_iso,
                    "is_active": True,
                    "occurrences": 1,
                    "successful_predictions": 1,
                    "success_rate": 1.0,
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
        "no_tier_match": 0,  # tier is A/D/X/null — not a betting tier
        "already_written": 0,  # race_id already in betting_ledger for this date
        "non_runner": 0,  # predicted horse absent from result set entirely
        "no_sp": 0,  # horse ran but sp_dec missing or ≤ 1.0
        "write_error": 0,  # DB upsert failed
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
        rid = row["race_id"]
        vmeta = verdict_meta.get(rid, {})
        tier = (vmeta.get("decision_tier") or "").upper()

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

        is_win = row["outcome"] == "WIN"
        pl = round(stake * (pred_sp - 1), 2) if is_win else round(-stake, 2)
        returns = round(stake * pred_sp, 2) if is_win else 0.0
        bankroll_before = round(current_bankroll, 2)
        bankroll_after = round(current_bankroll + pl, 2)
        current_bankroll = bankroll_after

        placed_at = vmeta.get("generated_at") or utc_now_iso()

        # confidence_level stores the verdict label as a numeric proxy:
        #   high → 1.0 | normal → 0.5 | low → 0.25
        # velo_prime_prob (raw win probability) is captured in reasoning.
        conf_label = (vmeta.get("confidence_level") or "low").lower()
        conf_numeric = {"high": 1.0, "normal": 0.5, "low": 0.25}.get(conf_label, 0.25)

        ledger_row = {
            "race_id": rid,
            "date": race_date,
            "course": row["course"],
            "race_time": _off_to_timestamp(race_date, row["off"]) if row.get("off") else placed_at,
            "horse": row["predicted"],
            "bet_type": tier,
            "stake": stake,
            "odds": pred_sp,
            "result": "WIN" if is_win else "LOSS",
            "returns": returns,
            "profit_loss": pl,
            "bankroll_before": bankroll_before,
            "bankroll_after": bankroll_after,
            "confidence_level": conf_numeric,
            "reasoning": f"velo_prime_v1 | tier={tier} | conf={conf_label} | prob={row['velo_prime_prob']:.4f} | outcome={row['outcome']} | sp={pred_sp}",
            "placed_at": placed_at,
            "settled_at": utc_now_iso(),
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
        if r["outcome"] == "WIN":
            hit_lines.append(f"  WIN  {r['course']:<18} {r['off']}  {r['predicted']} (prob={r['velo_prime_prob']:.4f})")

    # B. Notable misses (high prob but missed)
    notable_misses = sorted(
        [r for r in all_matched if r["outcome"] == "MISS" and r["velo_prime_prob"] >= 0.25],
        key=lambda r: -r["velo_prime_prob"],
    )

    # C. Frame picks (2nd/3rd)
    frame_lines = [r for r in all_matched if r["outcome"] == "PLACED"]

    # Main sigma report
    sigma_msg = (
        f"VELO SIGMA REPORT — {TODAY_DISPLAY}\n"
        f"{'=' * 35}\n"
        f"Races evaluated:  {total_matched}\n"
        f"Hits (1st):       {total_hits}  ({strike_rate:.1%})\n"
        f"Frames (top 3):   {total_hits + total_frames}  ({frame_rate:.1%})\n"
        f"Misses:           {total_misses}\n"
        + (f"Non-runners:      {total_nr} (excluded)\n" if total_nr else "")
        + f"\n"
        f"High-conf (>=0.30): {len(high_conf)} picks, {len(high_hits)} hits ({high_strike:.1%})\n"
        f"Avg prob (hits):    {avg_hit_prob:.4f}\n"
        f"Avg prob (misses):  {avg_miss_prob:.4f}\n"
        f"\n"
        f"SIGMA: {sigma_note}\n"
        f"Engine: velo_prime_v1 (SQPE v17 + specialists)"
    )
    tg(sigma_msg)
    print("  Sent: main sigma report")

    # Hits breakdown
    if hit_lines:
        tg("VELO WINS — " + TODAY_DISPLAY + "\n" + "\n".join(hit_lines))
        print(f"  Sent: {len(hit_lines)} hits")

    # Miss class breakdown
    miss_breakdown = "\n".join([f"  {k}: {v}" for k, v in sorted(miss_classes.items(), key=lambda x: -x[1])])
    tg(
        f"VELO MISS ANALYSIS — {TODAY_DISPLAY}\n"
        f"Miss classes:\n{miss_breakdown}\n"
        f"\nNotable fades (prob>=0.25 but missed):\n"
        + "\n".join(
            [
                f"  {r['course']} {r['off']}  {r['predicted']} (prob={r['velo_prime_prob']:.4f}) — won: {r['actual_name']}"
                for r in notable_misses[:5]
            ]
            or ["  none"]
        )
    )
    print(f"  Sent: miss analysis ({len(notable_misses)} notable fades)")

    # Frame picks
    if frame_lines:
        frame_msg = "VELO PLACED (2nd/3rd) — " + TODAY_DISPLAY + "\n"
        frame_msg += "\n".join(
            [f"  {r['course']} {r['off']}  {r['predicted']} placed — won: {r['actual_name']}" for r in frame_lines[:10]]
        )
        tg(frame_msg)
        print(f"  Sent: {len(frame_lines)} frames")

    # Final report — status reflects sigma write truth
    sigma_status = "PASS" if sigma_ok > 0 else "FAIL"
    tg(
        f"VELO RESULTS COMPLETE — {TODAY_DISPLAY}\n"
        f"Races: {total_matched}\n"
        f"Strike rate: {strike_rate:.1%}\n"
        f"Frame rate:  {frame_rate:.1%}\n"
        f"Ledger bets: {ledger_ok}  bankroll: £{current_bankroll:.2f}\n"
        f"Supabase: sigma_audits={sigma_ok}/{total_matched}  learned_patterns={patterns_saved}\n"
        f"Status: {sigma_status}"
    )
    print(f"  Sent: final report ({sigma_status})")

    # Hard fail if all sigma writes failed — this run produced no truth
    if sigma_ok == 0 and total_matched > 0:
        tg(
            f"VELO ALERT — SIGMA FAIL — {TODAY_DISPLAY}\n"
            f"All {total_matched} sigma_audits writes failed.\n"
            f"Post-race truth not persisted. Investigate immediately."
        )
        print("\nFAIL — sigma_ok=0: no reconciliation truth persisted")
        sys.exit(1)

    # ── STEP 9: Write local sigma artifact for Council / Mission Control ─────
    # This is a mirror artifact ONLY. sigma_audits truth is already in Supabase.
    # Purpose: let Council (SigmaCoverageAgent) read local JSON without DB query.
    print("\nSTEP 9: Write local sigma artifact")
    _sigma_dir = ROOT / "data" / "sigma_results"
    _sigma_dir.mkdir(parents=True, exist_ok=True)
    _sigma_artifact = {
        "date": race_date,
        "generated_at": utc_now_iso(),
        "expected_predictions": len(predictions),
        "result_races": len(results_by_id),
        "evaluated_count": total_matched,
        "wins": total_hits,
        "frames": total_frames,
        "misses": total_misses,
        "true_non_runners": total_nr,
        "identity_failures": 0,
        "no_result_count": no_result_ct,
        "total_reviewed": total_matched,
        "sr": round(strike_rate, 4),
        "frame_rate": round(frame_rate, 4),
        "miss_class_breakdown": miss_classes,
        "high_conf_n": len(high_conf),
        "high_conf_sr": round(high_strike, 4),
        "avg_hit_prob": round(avg_hit_prob, 4),
        "avg_miss_prob": round(avg_miss_prob, 4),
        "source": "sigma_reconciliation",
        "sigma_status": "PASS" if sigma_ok > 0 else "FAIL",
        "sigma_note": sigma_note,
        "learning_candidate_rows": sigma_ok,
        "unresolved_rows": no_result_ct,
        "raw_sigma_audits_preserved": True,
    }
    _dated_path = _sigma_dir / f"sigma_results_{race_date.replace('-', '_')}.json"
    _dated_path.write_text(json.dumps(_sigma_artifact, indent=2))
    print(f"  Written: {_dated_path}")

    _md_lines = [
        f"# VELO Sigma Results — {race_date}",
        f"\n**Status:** {_sigma_artifact['sigma_status']} — {sigma_note}",
        f"\n| Metric | Value |",
        f"|---|---|",
        f"| Evaluated | {total_matched} |",
        f"| Wins | {total_hits} ({strike_rate:.1%}) |",
        f"| Frames | {total_frames} |",
        f"| Misses | {total_misses} |",
        f"| Non-runners excluded | {total_nr} |",
        f"| No-result | {no_result_ct} |",
        f"| High-conf (VP≥0.30) | {len(high_conf)} picks, {high_strike:.1%} SR |",
        f"| sigma_audits written | {sigma_ok}/{total_matched} |",
        f"\n**raw_sigma_audits_preserved:** true",
    ]
    (_sigma_dir / f"sigma_results_{race_date.replace('-', '_')}.md").write_text("\n".join(_md_lines))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"SIGMA COMPLETE — {race_date}")
    print(f"  Strike rate:  {strike_rate:.1%} ({total_hits}/{total_matched})")
    print(f"  Frame rate:   {frame_rate:.1%} ({total_hits + total_frames}/{total_matched})")
    print(f"  Miss classes: {miss_classes}")
    print(f"  Sigma note:   {sigma_note}")
    print(f"  Supabase:     sigma_audits={sigma_ok} learned_patterns={patterns_saved}")
    _close_sigma_run(run_id, status="PASS")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        _close_sigma_run((os.getenv("_ACTIVE_SIGMA_RUN_ID") or "").strip() or None, status="FAIL", error="script exited before successful completion")
        raise
    except Exception as exc:
        _close_sigma_run((os.getenv("_ACTIVE_SIGMA_RUN_ID") or "").strip() or None, status="FAIL", error=str(exc))
        raise
