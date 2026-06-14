import json
import argparse
from pathlib import Path
from feature_health_detector import run_drift_analysis
from incident_report_card import IncidentReportCard

class HarnessGuardAgent:
    def __init__(self, policy_path):
        self.policy_path = Path(policy_path)
        with open(policy_path, "r") as f:
            self.policy = json.load(f)
            
    def process_incident(self, incident_dir, reference_path, incident_id, title):
        incident_dir = Path(incident_dir)
        current_csv = incident_dir / "incident_data.csv"
        
        print(f"\n[AGENT] Starting audit for: {title}")
        
        # 1. Run Detection
        run_drift_analysis(
            reference_path, 
            current_csv, 
            incident_dir, 
            critical_cols=["assigned_product", "improvement_score"]
        )
        
        # 2. Load the resulting report
        report_json = incident_dir / "evidently_report.json"
        with open(report_json, "r") as f:
            report_data = json.load(f)
            
        # 3. Generate Report Card
        card_dir = Path("hackathon/amd_harnessguard/reports/cards")
        generator = IncidentReportCard(incident_id, title)
        card = generator.generate(report_data, card_dir)
        
        print(f"[AGENT] Audit complete. Severity: {card['severity']}")
        print(f"[AGENT] Decision: {'🔴 BLOCKED' if not card['safe_to_learn'] else '🟢 CLEAR'}")
        print(f"[AGENT] Action: {card['recommended_action']}")
        
        return card

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HarnessGuard Deterministic Agent")
    parser.add_argument("--incident", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    
    args = parser.parse_args()
    
    agent = HarnessGuardAgent("hackathon/amd_harnessguard/src/policy_registry.json")
    agent.process_incident(args.incident, args.reference, args.id, args.title)
