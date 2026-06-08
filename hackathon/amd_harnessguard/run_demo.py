import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from harnessguard_agent import HarnessGuardAgent

def run_all_demo_cases():
    ROOT = Path(__file__).parent
    POLICY = ROOT / "src" / "policy_registry.json"
    
    agent = HarnessGuardAgent(POLICY)
    
    cases = [
        {
            "id": "may24_rpdc_degraded",
            "title": "Incident A: RPDC Feature Flatline",
            "dir": ROOT / "demo_cases" / "may24_rpdc_degraded",
            "ref": ROOT / "demo_cases" / "reference_baseline.csv"
        },
        {
            "id": "supabase_decision_tier_null",
            "title": "Incident B: Supabase Persistence Gap",
            "dir": ROOT / "demo_cases" / "supabase_decision_tier_null",
            "ref": ROOT / "demo_cases" / "persistence_reference.csv"
        },
        {
            "id": "international_rpr_timestamp_risk",
            "title": "Incident C: International RPR Leakage Risk",
            "dir": ROOT / "demo_cases" / "international_rpr_timestamp_risk",
            "ref": ROOT / "demo_cases" / "reference_baseline.csv" # Using same ref for demo
        }
    ]
    
    print("====================================================")
    print("   HARNESSGUARD BY VÉLØ - HACKATHON DEMO RUNNER     ")
    print("====================================================\n")
    
    results = []
    for case in cases:
        try:
            res = agent.process_incident(case["dir"], case["ref"], case["id"], case["title"])
            results.append(res)
        except Exception as e:
            print(f"Error processing {case['id']}: {e}")

    print("\n" + "="*50)
    print("            DEMO SUMMARY REPORT")
    print("="*50)
    print(f"{'INCIDENT':<35} | {'SEVERITY':<10} | {'STATUS':<10}")
    print("-" * 60)
    for r in results:
        status = "BLOCKED" if not r['safe_to_learn'] else "CLEAR"
        print(f"{r['title']:<35} | {r['severity']:<10} | {status:<10}")
    print("="*60)
    print(f"\nReport cards generated in: {ROOT}/reports/cards/")

if __name__ == "__main__":
    run_all_demo_cases()
