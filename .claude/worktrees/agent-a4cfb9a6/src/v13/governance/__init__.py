"""
VÉLØ V13 Governance Layer

Phase 3A: Proposal Persistence + Review Gate

This module implements the human-in-loop control layer that routes critic findings
to explicit approval before any system change.

Core principles:
- Separation of powers (critics propose, humans decide, system executes)
- Explicit ledger (every decision recorded)
- Atomic promotion (DRAFT → PENDING → ACCEPTED/REJECTED)
- Reversibility (accepted patches can be rolled back)
- No backdoors (zero auto-apply code paths)

Author: VÉLØ Team
Date: 2026-01-19
Status: Phase 3A Implementation
"""

from .fingerprint import fingerprint_proposal, fingerprint_from_dict
from .persistence import ProposalPersistence
from .transitions import ProposalTransitions
from .ledger import GovernanceLedger
from .doctrine_manager import DoctrineManager
from .api import GovernanceAPI

__all__ = [
    "fingerprint_proposal",
    "fingerprint_from_dict",
    "ProposalPersistence",
    "ProposalTransitions",
    "GovernanceLedger",
    "DoctrineManager",
    "GovernanceAPI",
]
