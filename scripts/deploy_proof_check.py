"""
VÉLØ Deploy Proof Check
=======================
Run this after every deploy. If any check fails: NOT LIVE.

Usage:
    python scripts/deploy_proof_check.py
    python scripts/deploy_proof_check.py --url https://custom-domain.railway.app
"""
import sys
import json
import argparse
import urllib.request
import urllib.error

BASE_URL = "https://velo-oracle-production.up.railway.app"

SAMPLE_PAYLOAD = {
    "race_id": "deploy-proof",
    "course": "Exeter",
    "runners": [
        {
            "horse": "Proofhorse",
            "ofr": "110", "rpr": "108", "ts": "95",
            "odds": [{"bookmaker": "Bet365", "decimal": "5.0"}],
            "trainer": "T Smith", "jockey": "J Doe",
            "form": "112", "draw": "3", "lbs": "126", "age": "4"
        },
        {
            "horse": "Challenger",
            "ofr": "106", "rpr": "104", "ts": "90",
            "odds": [{"bookmaker": "Bet365", "decimal": "8.0"}],
            "trainer": "A Jones", "jockey": "B Hill",
            "form": "221", "draw": "1", "lbs": "122", "age": "5"
        }
    ]
}


def check(label, fn):
    try:
        result = fn()
        print(f"  PASS  {label}: {result}")
        return True
    except Exception as e:
        print(f"  FAIL  {label}: {e}")
        return False


def get(url, timeout=10):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def post(url, data, timeout=15):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=BASE_URL)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    print(f"\nDEPLOY PROOF CHECK — {base}\n")

    results = []

    results.append(check(
        "/health returns OK",
        lambda: (
            lambda d: "OK" if d.get("status") == "ok" else (_ for _ in ()).throw(
                AssertionError(f"status={d.get('status')}")
            )
        )(get(f"{base}/health"))
    ))

    def check_openapi():
        d = get(f"{base}/openapi.json")
        paths = list(d.get("paths", {}).keys())
        if "/api/v1/predict/race" not in paths:
            raise AssertionError(f"route missing. present: {[p for p in paths if 'predict' in p]}")
        return f"found in {len(paths)} routes"

    results.append(check("/openapi.json contains /api/v1/predict/race", check_openapi))

    def check_endpoint():
        d = post(f"{base}/api/v1/predict/race", SAMPLE_PAYLOAD)
        top = d.get("top_pick") or {}
        prob = top.get("velo_prime_prob")
        version = top.get("ensemble_version", "?")
        if prob is None:
            raise AssertionError(f"no velo_prime_prob in response: {list(d.keys())}")
        return f"top={top.get('horse')} velo_prime_prob={prob:.4f} version={version}"

    results.append(check("POST /api/v1/predict/race returns velo_prime_prob", check_endpoint))

    print()
    if all(results):
        print("STATUS: LIVE")
        sys.exit(0)
    else:
        print("STATUS: NOT LIVE")
        sys.exit(1)


if __name__ == "__main__":
    main()
