# src/logging/prediction_logger.py

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from filelock import FileLock
import uuid

# --- Log Record Schema ---
@dataclass
class PredictionLogRecord:
    """
    Schema for a single prediction event for one runner.
    This structure is designed to be written as a single line in a JSONL file.
    """
    timestamp: str
    request_id: str
    race_id: str
    horse_id: str
    model_name: str
    model_version: str
    is_champion: bool
    sqpe_prob: float
    tie_intent: float
    final_prob: float
    # Fields to be filled in later by the outcome joiner
    result_position: Optional[int] = None
    won: Optional[bool] = None

    def to_json(self) -> str:
        """Serializes the record to a JSON string."""
        return json.dumps(asdict(self))

# --- Logger Implementation ---
class PredictionLogger:
    """
    Handles writing prediction log records to a destination.
    V1 uses a thread-safe JSONL file appender.
    """
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.lock_path = self.log_path.with_suffix('.lock')
        
        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, records: list):
        """
        Appends a list of prediction records to the JSONL file.

        Args:
            records: A list of PredictionLogRecord objects.
        """
        if not records:
            return

        # Use a file lock to ensure thread-safe appends from concurrent requests
        with FileLock(self.lock_path):
            with open(self.log_path, 'a') as f:
                for record in records:
                    f.write(record.to_json() + '\n')

# --- Default Instance ---
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "predictions.jsonl"

default_prediction_logger = PredictionLogger(log_path=DEFAULT_LOG_PATH)

# --- Helper Function for Service ---
def generate_request_id() -> str:
    """Generates a unique ID for a prediction request."""
    return str(uuid.uuid4())

