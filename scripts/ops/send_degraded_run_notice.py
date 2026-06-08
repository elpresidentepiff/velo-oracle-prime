"""
One-shot Telegram notice for a feature-degraded run.
Reads TOKEN and CHAT_ID from .env. Sends a single correction message.
NOT a scoring script. No Supabase. No model loading. No predictions.
"""
import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        print("[SEND_SKIP] TOKEN or CHAT_ID not set")
        return False
    body = json.dumps({"chat_id": CHAT_ID, "text": text[:4096]}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("[SEND_OK]")
                return True
            print(f"[SEND_FAIL] HTTP {resp.status}")
            return False
    except urllib.error.HTTPError as e:
        print(f"[SEND_FAIL] HTTP {e.code} {e.reason}")
        return False
    except Exception as e:
        print(f"[SEND_FAIL] {e}")
        return False


MESSAGE = """\
VÉLØ OPERATOR NOTICE — 24 May 2026

Today's official card remains valid, but it is classified FEATURE DEGRADED.

One live-weighted layer — RPDC/improvement_score — was unavailable because the prior results-to-horse-runs chain had not been refreshed. The engine scored all 29 races with SQPE + MDS active, but the improvement component was excluded, inflating VP confidence by approximately 22%.

A-Strike CUR 1.45 Sun Goddess: structurally supported. The gap signal (0.19) derives from SQPE and MDS — both operational. This selection stands.

B-tier selections: treat with reduced conviction today. VP scores in the 0.20–0.28 range may be one tier above their full-formula position.

No new picks. No rescoring. Official predictions are not changed.

Learning from this card is blocked until RPDC reconciliation closes.

— El Presidente
"""

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    print("--- MESSAGE TO SEND ---")
    print(MESSAGE)
    print("---")
    if dry_run:
        print("[DRY RUN — not sent]")
        sys.exit(0)
    ok = send(MESSAGE)
    sys.exit(0 if ok else 1)
