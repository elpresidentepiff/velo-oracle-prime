
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def audit_safety():
    print("VÉLØ Sentient Feed Safety Audit")
    print("===============================")
    
    findings = []
    
    # 1. VELO_G_FEED_ENABLED check
    g_feed = os.getenv("VELO_G_FEED_ENABLED", "OFF").upper()
    print(f"G_FEED_ENABLED (env): {g_feed}")
    if g_feed == "ON":
        findings.append("⚠️ VELO_G_FEED_ENABLED is ON. Live feedback is active.")
    else:
        print("✅ G_FEED_ENABLED is correctly OFF or explicitly disabled.")

    # 2. SentientLoopbackEngine gating
    try:
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
        print("✅ SentientLoopbackEngine class found.")
    except ImportError:
        findings.append("❌ SentientLoopbackEngine not found in expected path.")

    # 3. Step 7 gating in run_results_sigma.py
    sigma_path = ROOT / "scripts" / "run_results_sigma.py"
    if sigma_path.exists():
        with open(sigma_path) as f:
            content = f.read()
            if "VELO_G_FEED_ENABLED" in content:
                print("✅ run_results_sigma.py has G_FEED_ENABLED gate.")
            else:
                findings.append("❌ run_results_sigma.py missing VELO_G_FEED_ENABLED gate in Step 7.")
    else:
        findings.append("❌ run_results_sigma.py not found.")

    # 4. Idempotency / Event Ledger
    # Check for 'learned_patterns' system marker logic in the script
    if sigma_path.exists():
        with open(sigma_path) as f:
            content = f.read()
            if "playbook_g_fed_" in content:
                print("✅ Idempotency key logic detected.")
            else:
                findings.append("❌ Idempotency marker logic ('playbook_g_fed_') not found in sigma script.")

    # Classification
    print("\nClassification:")
    if findings:
        for f in findings: print(f)
        print("\nSTATUS: SENTIENT_FEED_BLOCKED")
    else:
        print("\nSTATUS: SENTIENT_FEED_READY_FOR_SANDBOX")
        print("  - Gated OFF by default")
        print("  - Idempotency logic present")
        print("  - Infrastructure verified")

if __name__ == "__main__":
    audit_safety()
