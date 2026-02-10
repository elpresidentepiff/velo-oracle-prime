"""
V11 PHASE 4: POST-RACE LEARNING LOOP
------------------------------------
Closes the loop by feeding results back into VETP memory and updating model weights.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from ..vetp.services.vetp_layer1 import VETPLayer1
from ..vetp.schemas.vetp import VETPEventIn
from datetime import date

class LearningLoop:
    def __init__(self, db_session: Session):
        self.vetp = VETPLayer1(db_session)

    def process_result(
        self, 
        race_id: str, 
        prediction_data: Dict, 
        result_data: Dict
    ):
        """
        Ingest race result, compare with prediction, and log to VETP.
        """
        # 1. Determine if we read the race right
        winner = result_data.get('winner')
        predicted_winner = prediction_data.get('primary_selection')
        
        read_right = "Yes" if winner == predicted_winner else "No"
        
        # 2. Calculate PnL
        pnl = 0.0
        if read_right == "Yes":
            pnl = prediction_data.get('stake', 0) * (result_data.get('winner_odds', 0) - 1)
        else:
            pnl = -prediction_data.get('stake', 0)
            
        # 3. Extract Learnings
        learning = "Model aligned with reality." if read_right == "Yes" else "Model missed winner."
        
        # 4. Log to VETP
        event = VETPEventIn(
            event_id=race_id,
            date=date.today(),
            course=result_data.get('course', 'Unknown'),
            code=result_data.get('code', 'Flat'),
            winner=winner,
            pnl_units=pnl,
            read_race_right=read_right,
            key_learning=learning,
            emotion_tag="smug" if pnl > 0 else "lesson"
        )
        
        self.vetp.log_event(event)
        
        return {
            "status": "logged",
            "pnl": pnl,
            "learning": learning
        }
