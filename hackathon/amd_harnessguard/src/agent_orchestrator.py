import json
import argparse
from pathlib import Path
from datetime import datetime
from feature_health_detector import run_drift_analysis
from policy_evaluator import PolicyEvaluator
from recovery_planner import RecoveryPlanner

def run_orchestrator(incident_dir, reference_path, policy_path):
    incident_dir = Path(incident_dir)
    current_csv = incident_dir / "incident_data.csv"
    
    print(f"\n--- HARNESSGUARD ORCHESTRATOR START ---")
    print(f"Incident: {incident_dir.name}")
    
    # 1. Detection Phase (Evidently)
    print("\n[PHASE 1: DETECTION]")
    run_drift_analysis(reference_path, current_csv, incident_dir)
    report_json = incident_dir / "evidently_report.json"
    
    # 2. Policy Phase
    print("\n[PHASE 2: POLICY EVALUATION]")
    evaluator = PolicyEvaluator(policy_path)
    assessment = evaluator.evaluate(report_json)
    
    # 3. Planning Phase (Agent Inference)
    print("\n[PHASE 3: RECOVERY PLANNING]")
    planner = RecoveryPlanner(use_mock=True)
    recovery_plan = planner.generate_plan(assessment)
    
    # 4. Report Card Generation
    print("\n[PHASE 4: REPORT CARD GENERATION]")
    report_card = {
        "incident_id": incident_dir.name,
        "detection_time": datetime.utcnow().isoformat() + "Z",
        "severity": assessment["severity"],
        "evidence_source": str(report_json),
        "policy_evaluation": {
            "learning_eligibility": assessment["learning_eligibility"],
            "violations": assessment["violations"]
        },
        "recovery_plan": recovery_plan,
        "amd_benchmark": {
            "inference_device": "MOCKED_CPU_BASELINE",
            "latency_ms": 142.5,
            "throughput_signals_per_sec": 7.01
        }
    }
    
    report_card_path = incident_dir / "harnessguard_report_card.json"
    with open(report_card_path, "w") as f:
        json.dump(report_card, f, indent=2)
        
    print(f"\nSUCCESS: Report Card generated at {report_card_path}")
    print(json.dumps(report_card, indent=2))
    print(f"\n--- HARNESSGUARD ORCHESTRATOR COMPLETE ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HarnessGuard Agent Orchestrator")
    parser.add_argument("--incident", required=True, help="Directory of the incident")
    parser.add_argument("--reference", required=True, help="Path to reference baseline CSV")
    parser.add_argument("--policy", required=True, help="Path to Policy Registry JSON")
    
    args = parser.parse_args()
    
    run_orchestrator(args.incident, args.reference, args.policy)
