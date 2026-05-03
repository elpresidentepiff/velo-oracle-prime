from typing import Dict, List

class CouncilVerification:
    @staticmethod
    def verify_output(agent_name: str, output: Dict) -> Dict:
        """
        Verifies a single agent's output.
        Answers:
        1. What evidence supports this?
        2. What evidence contradicts this?
        3. What is missing?
        4. Status labels applied correctly?
        """
        # In a real implementation, this might use another LLM call or heuristics
        v_report = {
            "agent": agent_name,
            "verification_status": "PENDING_MANUAL",
            "evidence_supported": True,
            "contradictions_found": False,
            "missing_evidence_noted": False,
            "allowed_to_affect_staking": False,
            "allowed_to_affect_weights": False
        }
        return v_report

    @staticmethod
    def final_verification_gate(final_report: Dict) -> bool:
        """
        Final safety gate before producing operator report.
        """
        # Hard rules
        if final_report.get("staking_impact", False):
            return False
        if final_report.get("weight_change_impact", False):
            return False
        return True
