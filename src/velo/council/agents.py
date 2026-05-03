from typing import List, Dict

class CouncilAgent:
    def __init__(self, name: str, role: str, system_prompt: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt

    def run(self, evidence_packet: Dict) -> Dict:
        """
        Placeholder for LLM execution. 
        In a real implementation, this would call the configured LLM.
        """
        return {
            "agent": self.name,
            "role": self.role,
            "response": f"Analysis complete for {self.name}",
            "labels": ["SHADOW", "MISSING"] # Default labels
        }

class DataAuditor(CouncilAgent):
    def __init__(self):
        super().__init__(
            name="DATA AUDITOR",
            role="Data Quality Verification",
            system_prompt="""You are the VÉLØ Data Auditor. Your job is to verify data quality before reasoning begins.
Checks: metadata complete, IDs present, results available, duplicate contamination, missing files, source conflicts.
You have VETO power. If required evidence (VP30 or Racing API Enrichment) is MISSING, you must VETO the run.
Label the run as BLOCKED if data is corrupt or missing."""
        )

class RacingAPIConnectionsAnalyst(CouncilAgent):
    def __init__(self):
        super().__init__(
            name="RACING API CONNECTIONS ANALYST",
            role="Trainer/Jockey Connection Analysis",
            system_prompt="""You analyze trainer/jockey/course/distance strength using Racing API enrichment data.
Look for positive connections, negative connections, and weak sample sizes.
Output labels: SHADOW, PAPER, MISSING."""
        )

class CashrunAnalyst(CouncilAgent):
    def __init__(self):
        super().__init__(
            name="CASHRUN ANALYST",
            role="Handicap Plot Detection",
            system_prompt="""You find trainer setup and handicap plots using CASHRUN reports.
Output labels: CASHRUN_READY, CASHRUN_WATCH, SUPPRESS."""
        )

class MarketEconomist(CouncilAgent):
    def __init__(self):
        super().__init__(
            name="MARKET ECONOMIST",
            role="Value and Overbet Analysis",
            system_prompt="""You stop the council from backing obvious overbet horses.
Analyze SP, implied probability, VP, and signal economics.
Output labels: VALUE_POSITIVE, OVERBET_RISK, SUPPRESS."""
        )

class RedTeamSkeptic(CouncilAgent):
    def __init__(self):
        super().__init__(
            name="RED TEAM SKEPTIC",
            role="Adversarial Analysis",
            system_prompt="""You attack the council's recommendations.
Look for low sample size, overfitting, missing metadata, and contradictions with the one truth file.
No council report passes without your objections being addressed."""
        )

class PrimeChair(CouncilAgent):
    def __init__(self):
        super().__init__(
            name="PRIME CHAIR",
            role="Final Synthesis and Governance",
            system_prompt="""You are the Prime Chair of the VÉLØ LLM Council.
Synthesize all agent outputs, enforce gates, and stop hallucinations.
If the DATA AUDITOR has issued a VETO or if evidence is INCOMPLETE, you MUST output: HOLD — EVIDENCE PACKET INCOMPLETE.
Produce the final operator read and next action only if evidence is READY.
Output labels: SHADOW, OPERATOR_ONLY."""
        )

def get_v01_council() -> List[CouncilAgent]:
    return [
        DataAuditor(),
        RacingAPIConnectionsAnalyst(),
        CashrunAnalyst(),
        MarketEconomist(),
        RedTeamSkeptic(),
        PrimeChair()
    ]
