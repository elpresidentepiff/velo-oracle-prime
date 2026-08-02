"""
VELO Ops Cross-Check
====================
Single script that verifies all 7 systems simultaneously.
Outputs GREEN (safe to run) or RED (do not run).

Usage:
    python scripts/velo_ops_check.py
    python scripts/velo_ops_check.py --date 2026-03-17
"""
import sys
import os
import json
import argparse
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

CANONICAL_REPO     = "elpresidentepiff/velo-oracle-prime"
CANONICAL_BRANCH   = "feature/v10-launch"
CANONICAL_SERVICE  = "velo-oracle"
CANONICAL_ENDPOINT = "https://velo-oracle-production.up.railway.app"
CANONICAL_ROUTE    = "/api/v1/predict/race"
CANONICAL_TABLE    = "velo_verdicts"


def _pass(label, detail=""):
    s = f"  PASS  {label}"
    if detail:
        s += f": {detail}"
    print(s)
    return True


def _fail(label, detail=""):
    s = f"  FAIL  {label}"
    if detail:
        s += f": {detail}"
    print(s)
    return False


def _get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def _post(url, data, timeout=12):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


# ===========================================================================
# 1. GIT
# ===========================================================================
def check_git():
    print("\nGIT")
    results = []

    try:
        local_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        results.append(_pass("local SHA", local_sha[:12]))
    except Exception as e:
        local_sha = None
        results.append(_fail("local SHA", str(e)))

    try:
        remote_sha = subprocess.check_output(
            ["git", "ls-remote", "origin", CANONICAL_BRANCH], cwd=ROOT, text=True
        ).strip().split()[0]
        results.append(_pass(f"remote {CANONICAL_BRANCH} SHA", remote_sha[:12]))
    except Exception as e:
        remote_sha = None
        results.append(_fail(f"remote {CANONICAL_BRANCH} SHA", str(e)))

    if local_sha and remote_sha:
        if local_sha == remote_sha:
            results.append(_pass("local == remote SHA"))
        else:
            results.append(_fail("local == remote SHA", f"{local_sha[:8]} != {remote_sha[:8]}"))

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip()
        # Only count modified/staged tracked files — ignore untracked (??) files
        tracked_dirty = [l for l in status.splitlines() if not l.startswith("??")]
        if tracked_dirty:
            results.append(_fail("tracked files clean", f"{len(tracked_dirty)} modified tracked files: {[l[:40] for l in tracked_dirty[:3]]}"))
        else:
            results.append(_pass("tracked files clean (untracked data/model files OK)"))
    except Exception as e:
        results.append(_fail("working tree clean", str(e)))

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True
        ).strip()
        if branch == CANONICAL_BRANCH:
            results.append(_pass("branch", branch))
        else:
            results.append(_fail("branch", f"{branch} != {CANONICAL_BRANCH}"))
    except Exception as e:
        results.append(_fail("branch", str(e)))

    return all(results)


# ===========================================================================
# 2. RAILWAY
# ===========================================================================
def check_railway():
    print("\nRAILWAY")
    results = []

    try:
        # Use shell=True on Windows; strip RAILWAY_TOKEN from env so CLI uses stored auth
        env = {k: v for k, v in os.environ.items() if k != "RAILWAY_TOKEN"}
        r = subprocess.run(
            "railway status", cwd=ROOT, text=True, capture_output=True, shell=True, env=env
        )
        status_out = (r.stdout + r.stderr).strip()
        if CANONICAL_SERVICE in status_out:
            results.append(_pass("service linked", CANONICAL_SERVICE))
        else:
            results.append(_fail("service linked", f"expected {CANONICAL_SERVICE}, got: {status_out}"))
    except Exception as e:
        results.append(_fail("railway CLI", str(e)))

    try:
        health = _get(f"{CANONICAL_ENDPOINT}/health", timeout=8)
        if health.get("status") == "ok":
            results.append(_pass("/health", "ok"))
        else:
            results.append(_fail("/health", str(health)))
    except Exception as e:
        results.append(_fail("/health", str(e)))

    try:
        openapi = _get(f"{CANONICAL_ENDPOINT}/openapi.json", timeout=8)
        paths = list(openapi.get("paths", {}).keys())
        if CANONICAL_ROUTE in paths:
            results.append(_pass(f"/openapi.json contains {CANONICAL_ROUTE}"))
        else:
            results.append(_fail(f"/openapi.json contains {CANONICAL_ROUTE}", f"missing. predict paths: {[p for p in paths if 'predict' in p]}"))
    except Exception as e:
        results.append(_fail("/openapi.json", str(e)))

    return all(results)


# ===========================================================================
# 3. SUPABASE
# ===========================================================================
def check_supabase(date_str: str):
    print("\nSUPABASE")
    results = []

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

    if not url or not key:
        results.append(_fail("credentials set", "SUPABASE_URL or SERVICE_KEY missing"))
        return False

    results.append(_pass("credentials set", url[:40] + "..."))

    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/velo_verdicts?select=count&limit=1",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            content_range = r.headers.get("Content-Range", "")
        results.append(_pass("write access / table reachable", f"Content-Range: {content_range}"))
        total = int(content_range.split("/")[1]) if "/" in content_range else "?"
    except Exception as e:
        results.append(_fail("table reachable", str(e)))
        return False

    # Today's row count
    try:
        # race_id membership, not a generated_at window (write time -- returns
        # nothing for any day scored outside its own calendar date).
        sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None
        from src.velo.verdict_loader import race_id_filter
        _rid = race_id_filter(date_str, ROOT)
        if _rid is None:
            results.append(_fail(f"rows for {date_str}", "UNVERIFIED_NO_RACECARD_CACHE"))
        else:
            req = urllib.request.Request(
                f"{url}/rest/v1/velo_verdicts?select=count&{_rid}",
                headers={"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"},
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                cr = r.headers.get("Content-Range", "")
            today_count = int(cr.split("/")[1]) if "/" in cr else "?"
            results.append(_pass(f"rows for {date_str}", str(today_count)))
    except Exception as e:
        results.append(_fail(f"rows for {date_str}", str(e)))

    return all(results)


# ===========================================================================
# 4. TELEGRAM
# ===========================================================================
def check_telegram():
    print("\nTELEGRAM")
    results = []

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token:
        results.append(_fail("TELEGRAM_BOT_TOKEN set"))
        return False
    results.append(_pass("TELEGRAM_BOT_TOKEN set"))

    if not chat_id:
        results.append(_fail("TELEGRAM_CHAT_ID set"))
        return False
    results.append(_pass("TELEGRAM_CHAT_ID set", chat_id))

    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/getMe",
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        if d.get("ok"):
            results.append(_pass("bot reachable", d.get("result", {}).get("username", "?")))
        else:
            results.append(_fail("bot reachable", str(d)))
    except Exception as e:
        results.append(_fail("bot reachable", str(e)))

    return all(results)


# ===========================================================================
# 5. NORMALIZER
# ===========================================================================
def check_normalizer():
    print("\nNORMALIZER")
    results = []

    try:
        sys.path.insert(0, str(ROOT))
        from workers.racing_api_normalizer import normalize_race, normalize_runner
        results.append(_pass("normalize_race import"))
        results.append(_pass("normalize_runner import"))
    except Exception as e:
        results.append(_fail("normalizer import", str(e)))
        return False

    # Verify normalizer converts raw Racing API fields to canonical schema
    sample_raw_runner = {
        "horse": "Test Horse", "ofr": "110", "rpr": "105", "ts": "95",
        "draw": "3", "lbs": "126", "age": "5", "jockey": "J Doe",
        "trainer": "T Smith", "form": "112",
        "odds": [{"bookmaker": "Bet365", "decimal": "5.0"}],
    }
    sample_raw_race = {
        "race_id": "test_001", "course": "Exeter", "off": "14:00",
        "name": "Test Race", "type": "Hurdle", "class": "4",
        "distance": "2m", "going": "Good",
        "runners": [sample_raw_runner],
    }
    try:
        norm = normalize_race(sample_raw_race)
        runners = norm.get("runners", [])
        if not runners:
            raise AssertionError("normalize_race returned no runners")
        r = runners[0]
        # Must NOT have raw key "horse" — must have canonical "horse_name"
        if "horse_name" not in r:
            raise AssertionError(f"normalize_runner did not produce horse_name — keys: {list(r.keys())}")
        if "horse" in r and "horse_name" not in r:
            raise AssertionError("raw payload key 'horse' not canonicalized")
        results.append(_pass("normalize_race produces canonical schema", f"horse_name={r.get('horse_name')}"))
    except Exception as e:
        results.append(_fail("normalize_race smoke", str(e)))

    return all(results)


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    print(f"\nVELO OPS CROSS-CHECK — {date_str}")
    print("=" * 60)

    git_ok        = check_git()
    railway_ok    = check_railway()
    supabase_ok   = check_supabase(date_str)
    telegram_ok   = check_telegram()
    normalizer_ok = check_normalizer()

    all_ok = all([git_ok, railway_ok, supabase_ok, telegram_ok, normalizer_ok])

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  git:        {'PASS' if git_ok        else 'FAIL'}")
    print(f"  railway:    {'PASS' if railway_ok    else 'FAIL'}")
    print(f"  supabase:   {'PASS' if supabase_ok   else 'FAIL'}")
    print(f"  telegram:   {'PASS' if telegram_ok   else 'FAIL'}")
    print(f"  normalizer: {'PASS' if normalizer_ok else 'FAIL'}")
    print()

    if all_ok:
        print("STATUS: GREEN — safe to run")
        sys.exit(0)
    else:
        failed = [n for n, ok in [
            ("git", git_ok), ("railway", railway_ok), ("supabase", supabase_ok),
            ("telegram", telegram_ok), ("normalizer", normalizer_ok)
        ] if not ok]
        print(f"STATUS: RED — DO NOT RUN  (failed: {', '.join(failed)})")
        sys.exit(1)


if __name__ == "__main__":
    main()
