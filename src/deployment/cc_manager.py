# src/deployment/cc_manager.py
"""
V13 Champion/Challenger Manager - Registry-based model loading.
Simpler than the old framework - focuses on loading models from registry.
"""
import logging
from typing import Optional, Dict

from src.registry.model_registry import default_model_registry, ModelRecord
from src.intelligence.orchestrator import VeloOrchestrator

logger = logging.getLogger(__name__)

# Cache for loaded orchestrators
ORCHESTRATOR_CACHE: Dict[str, VeloOrchestrator] = {}

class ChampionChallengerManager:
    """
    Manages loading Champion and Challenger orchestrators from the model registry.
    """
    def __init__(self, registry=default_model_registry):
        self.registry = registry

    def get_champion_orchestrator(self) -> Optional[VeloOrchestrator]:
        """Loads and returns the champion (production) orchestrator."""
        cache_key = "champion"
        if cache_key in ORCHESTRATOR_CACHE:
            return ORCHESTRATOR_CACHE[cache_key]

        logger.info("Loading CHAMPION models from registry...")
        sqpe_record = self.registry.get_champion("sqpe")
        tie_record = self.registry.get_champion("tie")

        if not sqpe_record or not tie_record:
            logger.error("CRITICAL: Champion models (SQPE or TIE) not found in 'production' stage.")
            return None
        
        orchestrator = VeloOrchestrator(sqpe_record, tie_record)
        ORCHESTRATOR_CACHE[cache_key] = orchestrator
        logger.info(f"Loaded CHAMPION: SQPE v{sqpe_record.version}, TIE v{tie_record.version}")
        return orchestrator

    def get_challenger_orchestrator(self) -> Optional[VeloOrchestrator]:
        """Loads and returns the challenger (staging) orchestrator."""
        cache_key = "challenger"
        if cache_key in ORCHESTRATOR_CACHE:
            return ORCHESTRATOR_CACHE[cache_key]

        logger.info("Loading CHALLENGER models from registry...")
        sqpe_record = self.registry.get_challenger("sqpe")
        tie_record = self.registry.get_challenger("tie")

        if not sqpe_record or not tie_record:
            logger.info("No complete challenger set found in 'staging' stage.")
            return None

        orchestrator = VeloOrchestrator(sqpe_record, tie_record)
        ORCHESTRATOR_CACHE[cache_key] = orchestrator
        logger.info(f"Loaded CHALLENGER: SQPE v{sqpe_record.version}, TIE v{tie_record.version}")
        return orchestrator

# Default instance
default_cc_manager = ChampionChallengerManager()

