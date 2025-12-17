#!/usr/bin/env python3
"""
VELO Engine Run Object
Single source of truth for reproducible race verdicts

Every verdict must be reproducible from stored inputs.
This module provides the EngineRun object that captures:
- engine_run_id (unique identifier)
- decision_timestamp (when the decision was made)
- race_ctx + market_ctx (all inputs)
- engine outputs (scores, verdicts, metadata)

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class RaceContext:
    """Race context: all race-level inputs."""
    race_id: str
    course: str
    datetime: datetime
    distance: int
    going: str
    class_level: int
    surface: str
    field_size: int
    race_type: str = "flat"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['datetime'] = self.datetime.isoformat()
        return d


@dataclass
class MarketContext:
    """Market context: all market-level inputs."""
    race_id: str
    snapshot_timestamp: datetime
    runners: List[Dict[str, Any]] = field(default_factory=list)
    market_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['snapshot_timestamp'] = self.snapshot_timestamp.isoformat()
        return d


@dataclass
class RunnerScore:
    """Individual runner scores from engine pipeline."""
    runner_id: str
    horse_name: str
    ability_score: float
    intent_score: float
    market_role: str  # ANCHOR / RELEASE / NOISE
    sle_hits: List[str] = field(default_factory=list)
    redteam_risk: float = 0.0
    final_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class EngineVerdict:
    """Final verdict from decision policy."""
    top_strike_selection: Optional[str] = None
    top4_structure: List[str] = field(default_factory=list)
    value_ew: List[str] = field(default_factory=list)
    fade_zone: List[str] = field(default_factory=list)
    win_suppressed: bool = False
    suppression_reason: Optional[str] = None
    confidence: float = 0.0
    notes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class EngineRun:
    """
    Complete engine run: inputs + outputs + metadata.
    
    Acceptance criteria: Every verdict is reproducible from stored inputs.
    """
    engine_run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_timestamp: datetime = field(default_factory=datetime.now)
    race_ctx: Optional[RaceContext] = None
    market_ctx: Optional[MarketContext] = None
    runner_scores: List[RunnerScore] = field(default_factory=list)
    verdict: Optional[EngineVerdict] = None
    mode: str = "RACE"  # RACE / BACKTEST / SIMULATION
    chaos_level: float = 0.0
    pipeline_version: str = "v1.0"
    execution_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            'engine_run_id': self.engine_run_id,
            'decision_timestamp': self.decision_timestamp.isoformat(),
            'race_ctx': self.race_ctx.to_dict() if self.race_ctx else None,
            'market_ctx': self.market_ctx.to_dict() if self.market_ctx else None,
            'runner_scores': [rs.to_dict() for rs in self.runner_scores],
            'verdict': self.verdict.to_dict() if self.verdict else None,
            'mode': self.mode,
            'chaos_level': self.chaos_level,
            'pipeline_version': self.pipeline_version,
            'execution_time_ms': self.execution_time_ms,
            'metadata': self.metadata
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, output_path: str):
        """Save to JSON file."""
        with open(output_path, 'w') as f:
            f.write(self.to_json())
        logger.info(f"✓ Engine run saved: {output_path}")
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EngineRun':
        """Load from dictionary."""
        # Parse race context
        race_ctx = None
        if data.get('race_ctx'):
            rc = data['race_ctx']
            rc['datetime'] = datetime.fromisoformat(rc['datetime'])
            race_ctx = RaceContext(**rc)
        
        # Parse market context
        market_ctx = None
        if data.get('market_ctx'):
            mc = data['market_ctx']
            mc['snapshot_timestamp'] = datetime.fromisoformat(mc['snapshot_timestamp'])
            market_ctx = MarketContext(**mc)
        
        # Parse runner scores
        runner_scores = [RunnerScore(**rs) for rs in data.get('runner_scores', [])]
        
        # Parse verdict
        verdict = None
        if data.get('verdict'):
            verdict = EngineVerdict(**data['verdict'])
        
        # Parse decision timestamp
        decision_timestamp = datetime.fromisoformat(data['decision_timestamp'])
        
        return cls(
            engine_run_id=data['engine_run_id'],
            decision_timestamp=decision_timestamp,
            race_ctx=race_ctx,
            market_ctx=market_ctx,
            runner_scores=runner_scores,
            verdict=verdict,
            mode=data.get('mode', 'RACE'),
            chaos_level=data.get('chaos_level', 0.0),
            pipeline_version=data.get('pipeline_version', 'v1.0'),
            execution_time_ms=data.get('execution_time_ms'),
            metadata=data.get('metadata', {})
        )
    
    @classmethod
    def load(cls, input_path: str) -> 'EngineRun':
        """Load from JSON file."""
        with open(input_path, 'r') as f:
            data = json.load(f)
        logger.info(f"✓ Engine run loaded: {input_path}")
        return cls.from_dict(data)
    
    def add_runner_score(self, score: RunnerScore):
        """Add runner score to engine run."""
        self.runner_scores.append(score)
    
    def set_verdict(self, verdict: EngineVerdict):
        """Set final verdict."""
        self.verdict = verdict
    
    def get_runner_score(self, runner_id: str) -> Optional[RunnerScore]:
        """Get score for specific runner."""
        for score in self.runner_scores:
            if score.runner_id == runner_id:
                return score
        return None
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Engine Run: {self.engine_run_id}",
            f"Race: {self.race_ctx.race_id if self.race_ctx else 'Unknown'}",
            f"Decision Time: {self.decision_timestamp}",
            f"Mode: {self.mode}",
            f"Chaos Level: {self.chaos_level:.2f}",
            f"Runners Scored: {len(self.runner_scores)}",
        ]
        
        if self.verdict:
            lines.append(f"Top Strike: {self.verdict.top_strike_selection or 'None'}")
            lines.append(f"Top-4: {', '.join(self.verdict.top4_structure)}")
            lines.append(f"Win Suppressed: {self.verdict.win_suppressed}")
        
        return "\n".join(lines)


class EngineRunRepository:
    """
    Repository for storing and retrieving engine runs.
    
    Provides persistence layer for reproducibility.
    """
    
    def __init__(self, storage_dir: str = "/data/engine_runs"):
        from pathlib import Path
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, engine_run: EngineRun) -> str:
        """
        Save engine run to storage.
        
        Args:
            engine_run: EngineRun object
            
        Returns:
            Path to saved file
        """
        filename = f"{engine_run.engine_run_id}.json"
        filepath = self.storage_dir / filename
        engine_run.save(str(filepath))
        return str(filepath)
    
    def load(self, engine_run_id: str) -> Optional[EngineRun]:
        """
        Load engine run from storage.
        
        Args:
            engine_run_id: Engine run ID
            
        Returns:
            EngineRun object or None if not found
        """
        filepath = self.storage_dir / f"{engine_run_id}.json"
        
        if not filepath.exists():
            logger.warning(f"Engine run not found: {engine_run_id}")
            return None
        
        return EngineRun.load(str(filepath))
    
    def list_runs(self, limit: int = 100) -> List[str]:
        """
        List recent engine run IDs.
        
        Args:
            limit: Maximum number of runs to return
            
        Returns:
            List of engine run IDs
        """
        files = sorted(self.storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [f.stem for f in files[:limit]]


if __name__ == "__main__":
    # Example usage
    
    # Create race context
    race_ctx = RaceContext(
        race_id="test_race_001",
        course="Newmarket",
        datetime=datetime.now(),
        distance=1200,
        going="Good",
        class_level=3,
        surface="Turf",
        field_size=10
    )
    
    # Create market context
    market_ctx = MarketContext(
        race_id="test_race_001",
        snapshot_timestamp=datetime.now(),
        runners=[
            {'runner_id': 'r1', 'odds': 3.5},
            {'runner_id': 'r2', 'odds': 5.0}
        ]
    )
    
    # Create engine run
    engine_run = EngineRun(
        race_ctx=race_ctx,
        market_ctx=market_ctx,
        mode="RACE",
        chaos_level=0.35
    )
    
    # Add runner scores
    engine_run.add_runner_score(RunnerScore(
        runner_id='r1',
        horse_name='Horse A',
        ability_score=0.85,
        intent_score=0.75,
        market_role='RELEASE',
        final_score=0.80
    ))
    
    # Set verdict
    engine_run.set_verdict(EngineVerdict(
        top_strike_selection='r1',
        top4_structure=['r1', 'r2', 'r3', 'r4'],
        win_suppressed=False,
        confidence=0.78
    ))
    
    # Save
    repo = EngineRunRepository()
    filepath = repo.save(engine_run)
    print(f"✓ Saved: {filepath}")
    
    # Load
    loaded = repo.load(engine_run.engine_run_id)
    print(f"✓ Loaded: {loaded.summary()}")
