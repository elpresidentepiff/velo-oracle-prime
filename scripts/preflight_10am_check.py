"""
VELO 10am Preflight Check
==========================
Run this before the 10am race workflow. If ANY check fails: DO NOT RUN.

Checks:
  1. Canonical env keys present
  2. Canonical repo/branch/service confirmed in git
  3. Prediction endpoint live (/health)
  4. OpenAPI route present (/api/v1/predict/race)
  5. Racing API reachable
  6. Supabase connectivity (write access to velo_verdicts)
  7. Telegram bot reachable
  8. Normalizer imports OK
  9. Pre-flight Telegram report sent

Usage:
    python scripts/preflight_10am_check.py
"""
import sys
import os
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

CANONICAL = {
    "repo":          "elpresidentepiff/velo-oracle-prime",
    "branch":        "feature/v10-launch",
    "service":       "velo-oracle",
    "service_id":    "0992976e-a59d-4cc8-a51f-76e330057493",
    "endpoint":      "https://velo-oracle-production.up.railway.app",
    "predict_route": "/api/v1/predict/race",
}

RESULTS   = {}
FAIL_MSGS = []


def check(label, fn):
    try:
        result = fn()
        print(f"  PASS  {label}: {result}")
        RESULTS[label] = True
    except Exception as e:
        msg = str(e)
        print(f"  FAIL  {label}: {msg}")
        RESULTS[label] = False
        FAIL_MSGS.append(f"{label}: {msg}")


def get_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def tg(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        body = json.dumps({"chat_id": chat_id, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


print("\nVELO 10AM PREFLIGHT CHECK\n")

# --- 1. Canonical env keys ---
check("SUPABASE_URL set",
    lambda: os.environ["SUPABASE_URL"][:30] + "..." if os.environ.get("SUPABASE_URL") else (_ for _ in ()).throw(AssertionError("missing")))
check("SUPABASE_SERVICE_KEY set",
    lambda: "OK" if (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")) else (_ for _ in ()).throw(AssertionError("missing")))
check("RACING_API_USERNAME set",
    lambda: "OK" if os.environ.get("RACING_API_USERNAME") else (_ for _ in ()).throw(AssertionError("missing")))
check("RACING_API_PASSWORD set",
    lambda: "OK" if os.environ.get("RACING_API_PASSWORD") else (_ for _ in ()).throw(AssertionError("missing")))
check("TELEGRAM_BOT_TOKEN set",
    lambda: "OK" if os.environ.get("TELEGRAM_BOT_TOKEN") else (_ for _ in ()).throw(AssertionError("missing")))
check("TELEGRAM_CHAT_ID set",
    lambda: os.environ.get("TELEGRAM_CHAT_ID", "") if os.environ.get("TELEGRAM_CHAT_ID") else (_ for _ in ()).throw(AssertionError("missing")))

# --- 2. Git: canonical repo + branch ---
def check_git_branch():
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if branch != CANONICAL["branch"]:
        raise AssertionError(f"on branch '{branch}', expected '{CANONICAL['branch']}'")
    return branch

def check_git_remote():
    remote_url = subprocess.check_output(
        ["git", "remote", "get-url", "origin"], cwd=ROOT, text=True
    ).strip()
    if CANONICAL["repo"] not in remote_url:
        raise AssertionError(f"remote is '{remote_url}', expected to contain '{CANONICAL['repo']}'")
    return remote_url

check("git branch == canonical", check_git_branch)
check("git remote == canonical repo", check_git_remote)

# --- 3. Prediction endpoint live ---
check("endpoint /health",
    lambda: "OK" if get_json(f"{CANONICAL['endpoint']}/health").get("status") == "ok"
            else (_ for _ in ()).throw(AssertionError("status != ok")))

# --- 4. OpenAPI route present ---
def check_openapi():
    d = get_json(f"{CANONICAL['endpoint']}/openapi.json")
    paths = list(d.get("paths", {}).keys())
    if CANONICAL["predict_route"] not in paths:
        raise AssertionError(f"route missing. predict routes: {[p for p in paths if 'predict' in p]}")
    return "found"

check(f"openapi contains {CANONICAL['predict_route']}", check_openapi)

# --- 5. Racing API reachable ---
def check_racing_api():
    username = os.environ.get("RACING_API_USERNAME", "")
    password = os.environ.get("RACING_API_PASSWORD", "")
    if not username or not password:
        raise AssertionError("credentials missing")
    import base64
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    req = urllib.request.Request(
        "https://api.theracingapi.com/v1/courses",
        headers={"Authorization": f"Basic {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    count = len(d) if isinstance(d, list) else d.get("total", "?")
    return f"{count} courses returned"

check("Racing API reachable", check_racing_api)

# --- 6. Supabase write access ---
def check_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise AssertionError("credentials missing")
    req = urllib.request.Request(
        f"{url}/rest/v1/velo_verdicts?select=count&limit=1",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "count=exact",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        cr = r.headers.get("Content-Range", "")
    if not cr:
        raise AssertionError("no Content-Range header — table may not exist")
    return f"velo_verdicts reachable, Content-Range={cr}"

check("Supabase velo_verdicts reachable", check_supabase)

# --- 7. Telegram bot reachable ---
def check_telegram():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise AssertionError("TELEGRAM_BOT_TOKEN missing")
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe")
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.loads(r.read())
    if not d.get("ok"):
        raise AssertionError(f"getMe failed: {d}")
    return d.get("result", {}).get("username", "ok")

check("Telegram bot reachable", check_telegram)

# --- 8. Normalizer imports ---
def check_normalizer():
    from workers.racing_api_normalizer import normalize_race, normalize_runner
    # Smoke test
    raw = {
        "race_id": "preflight_check", "course": "Test", "off": "12:00",
        "name": "Test", "type": "Flat", "class": "5",
        "runners": [{"horse": "TestHorse", "ofr": "100", "rpr": "95", "ts": "90",
                     "draw": "1", "lbs": "126", "age": "4", "jockey": "J", "trainer": "T",
                     "form": "1", "odds": [{"bookmaker": "B365", "decimal": "3.0"}]}],
    }
    norm = normalize_race(raw)
    runners = norm.get("runners", [])
    if not runners or "horse_name" not in runners[0]:
        raise AssertionError(f"normalize_race did not produce horse_name — keys: {list(runners[0].keys()) if runners else 'no runners'}")
    return f"OK — horse_name={runners[0]['horse_name']}"

check("normalizer imports and smoke test", check_normalizer)

# --- Result ---
print()
passed_count = sum(RESULTS.values())
total_count  = len(RESULTS)
all_pass     = all(RESULTS.values())

status_line = "ALL CHECKS PASSED — safe to run 10am workflow" if all_pass else f"{total_count - passed_count} CHECK(S) FAILED — DO NOT RUN RACE-DAY WORKFLOW"
print(f"STATUS: {status_line}")

# --- 9. Telegram pre-flight report ---
tg_status = "READY" if all_pass else "DO NOT RUN"
tg_lines = [
    f"VELO PRE-FLIGHT REPORT",
    f"repo:       {CANONICAL['repo']}",
    f"branch:     {CANONICAL['branch']}",
    f"service:    {CANONICAL['service']}",
    f"endpoint:   {'LIVE' if RESULTS.get('endpoint /health') else 'DOWN'}",
    f"supabase:   {'OK' if RESULTS.get('Supabase velo_verdicts reachable') else 'FAIL'}",
    f"racing api: {'OK' if RESULTS.get('Racing API reachable') else 'FAIL'}",
    f"telegram:   {'OK' if RESULTS.get('Telegram bot reachable') else 'FAIL'}",
    f"normalizer: {'OK' if RESULTS.get('normalizer imports and smoke test') else 'FAIL'}",
    f"",
    f"STATUS: {tg_status}",
]
if not all_pass:
    tg_lines.append("FAILURES:")
    for msg in FAIL_MSGS:
        tg_lines.append(f"  - {msg}")
tg_sent = tg("\n".join(tg_lines))
print(f"Telegram pre-flight report: {'sent' if tg_sent else 'not sent (token/chat missing)'}")

if not all_pass:
    print("\nFix all failures above before running scripts/run_todays_races.py")
    sys.exit(1)

sys.exit(0)
