"""
VÉLØ 10am Preflight Check
==========================
Run this before the 10am race workflow. If any check fails: DO NOT RUN.

Usage:
    python scripts/preflight_10am_check.py
"""
import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

CANONICAL = {
    "repo": "elpresidentepiff/velo-oracle-prime",
    "branch": "feature/v10-launch",
    "service": "velo-oracle",
    "service_id": "0992976e-a59d-4cc8-a51f-76e330057493",
    "endpoint": "https://velo-oracle-production.up.railway.app",
    "predict_route": "/api/v1/predict/race",
}

RESULTS = []


def check(label, fn):
    try:
        result = fn()
        print(f"  PASS  {label}: {result}")
        RESULTS.append(True)
    except Exception as e:
        print(f"  FAIL  {label}: {e}")
        RESULTS.append(False)


def get_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def post_json(url, data, timeout=15):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


print(f"\nVÉLØ 10AM PREFLIGHT CHECK\n")

# 1. Canonical env keys present
check(
    "SUPABASE_URL set",
    lambda: os.environ.get("SUPABASE_URL", "")[:20] + "..." if os.environ.get("SUPABASE_URL") else (_ for _ in ()).throw(AssertionError("missing"))
)
check(
    "RACING_API_USERNAME set",
    lambda: "OK" if os.environ.get("RACING_API_USERNAME") else (_ for _ in ()).throw(AssertionError("missing"))
)
check(
    "RACING_API_PASSWORD set",
    lambda: "OK" if os.environ.get("RACING_API_PASSWORD") else (_ for _ in ()).throw(AssertionError("missing"))
)

# 2. Prediction endpoint live
check(
    f"endpoint /health",
    lambda: (
        lambda d: "OK" if d.get("status") == "ok" else (_ for _ in ()).throw(AssertionError(str(d)))
    )(get_json(f"{CANONICAL['endpoint']}/health"))
)

# 3. Canonical route in OpenAPI
def check_openapi():
    d = get_json(f"{CANONICAL['endpoint']}/openapi.json")
    paths = list(d.get("paths", {}).keys())
    if CANONICAL["predict_route"] not in paths:
        raise AssertionError(f"route missing. predict routes: {[p for p in paths if 'predict' in p]}")
    return "found"

check(f"openapi contains {CANONICAL['predict_route']}", check_openapi)

# 4. Racing API reachable
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

# Result
print()
if all(RESULTS):
    print("STATUS: ALL CHECKS PASSED — safe to run 10am workflow")
    sys.exit(0)
else:
    failed = RESULTS.count(False)
    print(f"STATUS: {failed} CHECK(S) FAILED — DO NOT RUN RACE-DAY WORKFLOW")
    print("\nFix all failures above before running scripts/run_todays_races.py")
    sys.exit(1)
