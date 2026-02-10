from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class PredictionRecord(BaseModel):
    race_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # The Oracle's Pre-Race State
    predicted_winner: str
    confidence_score: float
    playbook_e_signal: str # Attack Signal
    playbook_f_tactic: str # Execution Tactic
    
    # The "Why" (Explainability)
    key_factors: List[str] = [] # e.g. ["Well Handicapped", "Lone Speed"]

class RaceResult(BaseModel):
    race_id: str
    actual_winner: str
    winning_distance: str
    winning_time: str
    
    # The "What Happened"
    race_comment: str # e.g. "Led, clear 2f out, comfortable"

class LearningEvent(BaseModel):
    race_id: str
    prediction: PredictionRecord
    result: RaceResult
    
    # The "Lesson" (Playbook G Output)
    outcome: str # "SUCCESS" or "FAILURE"
    error_margin: float # Difference between predicted and actual performance
    adjustment_needed: bool
    
    # Weight Updates (The "Learning")
    # e.g. If we bet on a "Lone Speed" horse and it lost because of "Soft Ground",
    # we might decrease the weight of "Pace" on "Soft Ground".
    suggested_weight_changes: Dict[str, float] = {} 
