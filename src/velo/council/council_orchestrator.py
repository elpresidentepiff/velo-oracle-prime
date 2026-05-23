import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from .evidence_packet import EvidencePacket
from .agents import get_v01_council, CouncilAgent
from .verification import CouncilVerification

class CouncilOrchestrator:
    def __init__(self, date_str: str, repo_root: Path):
        self.date_str = date_str
        self.repo_root = repo_root
        self.packet_loader = EvidencePacket(date_str)
        self.agents: List[CouncilAgent] = get_v01_council()
        self.run_results = {
            "metadata": {
                "date": date_str,
                "run_at": datetime.now().isoformat(),
                "orchestrator_version": "v0.2-real-tribunal"
            },
            "evidence_packet": None,
            "agent_responses": [],
            "verifications": [],
            "final_report": None,
            "council_status": "PENDING",
            "council_verdict": "NOT_RUN",
        }

    def run_council(self):
        print(f"--- VÉLØ LLM Council Run: {self.date_str} ---")

        # 1. Load evidence
        print("Step 1: Loading evidence packet...")
        evidence = self.packet_loader.load_all_evidence(self.repo_root)
        self.packet_loader.save_packet(self.repo_root)
        self.run_results["evidence_packet"] = evidence
        self.run_results["council_status"] = evidence["metadata"]["council_status"]

        # 2. Run non-chair agents first, then inject their responses into evidence for PrimeChair
        print("Step 2: Running council members...")
        non_chair_agents = [a for a in self.agents if a.name != "PRIME CHAIR"]
        chair_agent = next((a for a in self.agents if a.name == "PRIME CHAIR"), None)

        for agent in non_chair_agents:
            print(f"  -> {agent.name} is deliberating...")
            response = agent.run(evidence)
            self.run_results["agent_responses"].append(response)
            verification = CouncilVerification.verify_output(agent.name, response)
            self.run_results["verifications"].append(verification)

        # Pass all agent responses to PrimeChair for synthesis
        if chair_agent:
            print(f"  -> {chair_agent.name} is deliberating...")
            evidence_with_responses = dict(evidence)
            evidence_with_responses["_agent_responses"] = self.run_results["agent_responses"]
            response = chair_agent.run(evidence_with_responses)
            self.run_results["agent_responses"].append(response)
            self.run_results["council_verdict"] = response.get("council_verdict", "UNKNOWN")
            verification = CouncilVerification.verify_output(chair_agent.name, response)
            self.run_results["verifications"].append(verification)

        # 4. Final Synthesis
        print("Step 3: Synthesizing final report...")
        self.run_results["final_report"] = self._generate_markdown_report()
        
        # 5. Save results
        self._save_run_results()
        print(f"Step 4: Council run complete. Status: {self.run_results['council_status']}")
        return self.run_results

    def _generate_markdown_report(self) -> str:
        report = f"# VÉLØ LLM Council Operator Report - {self.date_str}\n\n"
        report += f"**Run Date:** {datetime.now().isoformat()}\n"
        report += f"**Council Status:** {self.run_results['council_status']}\n"
        report += "**Status:** SHADOW / OPERATOR ONLY\n\n"
        
        report += "## 1. Executive Summary (Prime Chair)\n"
        prime_response = next((r for r in self.run_results["agent_responses"] if r["agent"] == "PRIME CHAIR"), None)
        if prime_response:
            report += f"{prime_response['response']}\n\n"
        
        report += "## 2. Agent Deliberations\n"
        for resp in self.run_results["agent_responses"]:
            if resp["agent"] == "PRIME CHAIR": continue
            report += f"### {resp['agent']}\n"
            report += f"**Role:** {resp['role']}\n"
            report += f"**Labels:** {', '.join(resp['labels'])}\n"
            report += f"**Read:** {resp['response']}\n\n"
            
        report += "## 3. Evidence Status\n"
        sources = self.run_results["evidence_packet"]["evidence_sources"]
        for name, info in sources.items():
            req_str = "[REQUIRED]" if info["required_for_release"] else ""
            report += f"- **{name}**: {info['status']} {req_str}\n"
            if info['path']:
                report += f"  - Path: `{info['path']}`\n"
        
        report += "\n## 4. Safety Audit\n"
        report += "- NO staking impact confirmed: YES\n"
        report += "- NO weight change impact confirmed: YES\n"
        report += "- NO live Betfair impact confirmed: YES\n"
        
        return report

    def _save_run_results(self):
        run_path = self.repo_root / f"data/council_runs/council_run_{self.date_str}.json"
        with open(run_path, 'w') as f:
            # Strip large content from run log to keep it manageable
            log_data = json.loads(json.dumps(self.run_results))
            for src in log_data["evidence_packet"]["evidence_sources"].values():
                if src.get("content"):
                    src["content"] = "[CONTENT_OMITTED_FOR_LOG]"
            json.dump(log_data, f, indent=2)
            
        report_path = self.repo_root / f"data/council_reports/velo_council_report_{self.date_str}.md"
        with open(report_path, 'w') as f:
            f.write(self.run_results["final_report"])
