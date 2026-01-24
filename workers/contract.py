#!/usr/bin/env python3
"""
Worker Contract for VÉLØ MCP.
All integral workers must adhere to this contract.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class WorkerContract(ABC):
    """Base contract for all VÉLØ workers."""
    
    @abstractmethod
    def analyze(self, race_id: int) -> Dict[str, Any]:
        """
        Analyze race and return results.
        
        Args:
            race_id: Integer race ID from database.
        
        Returns:
            Dictionary with at least:
            - race_id (int)
            - venue (str)
            - race_time (str)
            - worker_version (str)
            - results (list)
            - summary (dict)
        """
        pass
    
    @property
    @abstractmethod
    def worker_name(self) -> str:
        """Return worker name."""
        pass
    
    @property
    @abstractmethod
    def worker_version(self) -> str:
        """Return worker version."""
        pass

