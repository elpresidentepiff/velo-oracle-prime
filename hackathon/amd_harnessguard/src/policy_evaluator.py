import json
import argparse
from pathlib import Path

class PolicyEvaluator:
    def __init__(self, policy_path):
        with open(policy_path, "r") as f:
            self.registry = json.load(f)
            
    def evaluate(self, report_path):
        with open(report_path, "r") as f:
            report = json.load(f)
            
        violations = []
        severity = "LOW"
        action = "ALLOWED"
        
        # 1. Handle Catastrophic Failure (Incident B style)
        if report.get("status") == "FAILED":
            if report.get("null_failed_cols"):
                violations.append("POLICY_PERSISTENCE_GAP")
                severity = "HIGH"
                action = "BLOCK_LEARNING"
                
        # 2. Handle Drift (Incident A style)
        # Note: Evidently JSON structure is complex, we look for drift results
        metrics = report.get("metrics", [])
        for m in metrics:
            if m.get("metric") == "DatasetDriftMetric":
                result = m.get("result", {})
                if result.get("dataset_drift"):
                    # High drift check
                    share = result.get("share_of_drifted_columns", 0)
                    if share > 0.5:
                        violations.append("POLICY_ZERO_VARIANCE_CRITICAL")
                        severity = "CRITICAL"
                        action = "BLOCK_LEARNING"

        # 3. Handle Leakage (Incident C style - future)
        if report.get("leakage_detected"):
            violations.append("POLICY_TEMPORAL_LEAKAGE")
            severity = "CRITICAL"
            action = "BLOCK_LEARNING"

        return {
            "severity": severity,
            "learning_eligibility": action,
            "violations": violations,
            "raw_report_ref": str(report_path)
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HarnessGuard Policy Evaluator")
    parser.add_argument("--report", required=True, help="Path to Evidently JSON report")
    parser.add_argument("--policy", required=True, help="Path to Policy Registry JSON")
    
    args = parser.parse_args()
    
    evaluator = PolicyEvaluator(args.policy)
    assessment = evaluator.evaluate(args.report)
    
    print(json.dumps(assessment, indent=2))
