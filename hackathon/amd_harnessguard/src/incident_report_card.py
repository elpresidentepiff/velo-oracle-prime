import json
import argparse
from pathlib import Path
from datetime import datetime

class IncidentReportCard:
    def __init__(self, incident_id, title):
        self.incident_id = incident_id
        self.title = title
        
    def generate(self, report_data, output_dir):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        status = report_data.get("status")
        severity = report_data.get("severity", "LOW")
        
        affected_features = []
        mathematical_proof = ""
        
        if status == "QUALITY_FAILURE":
            failures = report_data.get("failures", [])
            affected_features = [f['column'] for f in failures]
            mathematical_proof = "\n".join([f"- {f['issue']}: {f['message']}" for f in failures])
            safe_to_score = report_data.get("safe_to_score", False)
            safe_to_learn = report_data.get("safe_to_learn", False)
        else:
            # Handle Evidently report
            metrics = report_data.get("metrics", [])
            for m in metrics:
                if m.get("metric") == "DatasetDriftMetric":
                    res = m.get("result", {})
                    if res.get("dataset_drift"):
                        mathematical_proof += f"- Drift detected in {res.get('number_of_drifted_columns')} columns.\n"
                        mathematical_proof += f"- Drift share: {res.get('share_of_drifted_columns'):.2f}\n"
                if m.get("metric") == "ColumnDriftMetric":
                    res = m.get("result", {})
                    if res.get("drift_detected"):
                        col = res.get("column_name")
                        affected_features.append(col)
                        mathematical_proof += f"- Column '{col}' drifted (score: {res.get('drift_score'):.4f})\n"
            
            safe_to_score = True if severity != "CRITICAL" else False
            safe_to_learn = False if severity in ["HIGH", "CRITICAL"] else True

        recommended_action = "BLOCK_LEARNING / OPERATOR_REVIEW" if not safe_to_learn else "CONTINUE_MONITORING"
        
        card = {
            "incident_id": self.incident_id,
            "title": self.title,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "severity": severity,
            "affected_features": affected_features,
            "mathematical_proof": mathematical_proof,
            "safe_to_score": safe_to_score,
            "safe_to_learn": safe_to_learn,
            "recommended_action": recommended_action,
            "operator_recovery_commands": self._get_recovery_commands(affected_features),
            "evidence_paths": {
                "json": str(output_dir / f"{self.incident_id}_card.json")
            }
        }
        
        # Save JSON
        json_path = output_dir / f"{self.incident_id}_card.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(card, f, indent=2)
            
        # Save Markdown
        md_path = output_dir / f"{self.incident_id}_card.md"
        self._save_markdown(card, md_path)
        
        return card

    def _get_recovery_commands(self, features):
        commands = []
        for f in features:
            if "improvement_score" in f:
                commands.append(f"python scripts/ops/reindex_feature_source.py --feature {f}")
            elif "assigned_product" in f:
                commands.append("python scripts/ops/verify_rp_supabase_archive_load.py")
            elif "leakage_status" in f:
                commands.append("python scripts/ops/verify_ts_coverage.py --audit-rpr")
        return commands if commands else ["NONE"]

    def _save_markdown(self, card, path):
        status_text = "BLOCKED" if not card['safe_to_learn'] else "CLEAR"
        md = f"""# Incident Report Card: {card['title']}
- **ID:** `{card['incident_id']}`
- **Severity:** `{card['severity']}`
- **Status:** {status_text}

## Executive Summary
{card['recommended_action']}

## Mathematical Proof
{card['mathematical_proof']}

## Affected Features
{', '.join(card['affected_features']) if card['affected_features'] else 'None'}

## Operator Recovery
```bash
{chr(10).join(card['operator_recovery_commands'])}
```
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HarnessGuard Incident Report Card Generator")
    parser.add_argument("--report", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True)
    
    args = parser.parse_args()
    
    with open(args.report, "r") as f:
        data = json.load(f)
        
    generator = IncidentReportCard(args.id, args.title)
    generator.generate(data, args.output)
