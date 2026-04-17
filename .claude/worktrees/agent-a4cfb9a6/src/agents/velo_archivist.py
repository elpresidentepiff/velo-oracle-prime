"""
VÉLØ v9.0++ CHAREX - VÉLØ ARCHIVIST Agent

Logs results to Scout Ledger (JSON or DB).
Maintains historical record of predictions and outcomes.
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path


class VeloArchivist:
    """
    VÉLØ ARCHIVIST - Ledger and Results Logger
    
    Maintains the Scout Ledger with all predictions and outcomes.
    Enables post-race analysis and Genesis Protocol learning.
    """
    
    def __init__(self, ledger_path: Optional[str] = None):
        """
        Initialize VÉLØ ARCHIVIST agent.
        
        Args:
            ledger_path: Path to ledger storage directory
        """
        self.name = "VÉLØ_ARCHIVIST"
        self.version = "v9.0++"
        self.status = "STANDBY"
        
        # Ledger configuration
        if ledger_path is None:
            ledger_path = Path(__file__).parent.parent.parent / "data" / "ledger"
        
        self.ledger_path = Path(ledger_path)
        self.ledger_path.mkdir(parents=True, exist_ok=True)
        
        self.ledger_file = self.ledger_path / "scout_ledger.json"
        self.predictions_file = self.ledger_path / "predictions.json"
        self.results_file = self.ledger_path / "results.json"
        
        # Initialize ledger if it doesn't exist
        self._initialize_ledger()
    
    def _initialize_ledger(self) -> None:
        """Initialize ledger files if they don't exist."""
        if not self.ledger_file.exists():
            initial_data = {
                "version": "v9.0++",
                "created": datetime.now().isoformat(),
                "entries": []
            }
            with open(self.ledger_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
        
        if not self.predictions_file.exists():
            with open(self.predictions_file, 'w') as f:
                json.dump({"predictions": []}, f, indent=2)
        
        if not self.results_file.exists():
            with open(self.results_file, 'w') as f:
                json.dump({"results": []}, f, indent=2)
    
    def activate(self) -> None:
        """Activate VÉLØ ARCHIVIST agent."""
        self.status = "ACTIVE"
        print(f"\n📚 {self.name} ACTIVATED")
        print(f"Ledger Path: {self.ledger_path}")
        print(f"Scout Ledger: {self.ledger_file}")
        print(f"Status: {'✅ Initialized' if self.ledger_file.exists() else '⚠️  Not initialized'}\n")
    
    def log_prediction(self, race_id: str, race_details: Dict, verdict: Dict) -> str:
        """
        Log a prediction to the ledger.
        
        Args:
            race_id: Unique race identifier
            race_details: Race information
            verdict: VÉLØ verdict with predictions
            
        Returns:
            Entry ID
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ ARCHIVIST not active. Call activate() first.")
        
        entry_id = f"{race_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        entry = {
            "entry_id": entry_id,
            "race_id": race_id,
            "timestamp": datetime.now().isoformat(),
            "race_details": race_details,
            "verdict": verdict,
            "outcome": None,  # To be filled after race
            "status": "PENDING"
        }
        
        # Load existing ledger
        with open(self.ledger_file, 'r') as f:
            ledger = json.load(f)
        
        # Add entry
        ledger["entries"].append(entry)
        
        # Save ledger
        with open(self.ledger_file, 'w') as f:
            json.dump(ledger, f, indent=2)
        
        print(f"📝 ARCHIVIST: Logged prediction {entry_id}")
        
        return entry_id
    
    def log_result(self, entry_id: str, result: Dict) -> None:
        """
        Log race result and update prediction entry.
        
        Args:
            entry_id: Entry identifier from log_prediction
            result: Race result data with final positions and SP
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ ARCHIVIST not active. Call activate() first.")
        
        # Load ledger
        with open(self.ledger_file, 'r') as f:
            ledger = json.load(f)
        
        # Find and update entry
        for entry in ledger["entries"]:
            if entry["entry_id"] == entry_id:
                entry["outcome"] = result
                entry["status"] = "COMPLETED"
                entry["result_timestamp"] = datetime.now().isoformat()
                
                # Mark predictions as hit/miss
                entry["performance"] = self._evaluate_performance(entry["verdict"], result)
                
                break
        
        # Save updated ledger
        with open(self.ledger_file, 'w') as f:
            json.dump(ledger, f, indent=2)
        
        print(f"✅ ARCHIVIST: Logged result for {entry_id}")
    
    def _evaluate_performance(self, verdict: Dict, result: Dict) -> Dict:
        """
        Evaluate prediction performance against actual result.
        
        Args:
            verdict: Original VÉLØ verdict
            result: Actual race result
            
        Returns:
            Performance evaluation
        """
        velo_verdict = verdict.get("velo_verdict", {})
        top_pick = velo_verdict.get("top_strike_selection")
        
        final_positions = result.get("positions", {})
        winner = result.get("winner")
        
        # Check if top pick won
        top_pick_hit = (top_pick == winner)
        
        # Check if top pick placed
        top_pick_position = final_positions.get(top_pick, 999)
        top_pick_placed = (top_pick_position <= 3)
        
        return {
            "top_pick_won": top_pick_hit,
            "top_pick_placed": top_pick_placed,
            "top_pick_position": top_pick_position,
            "verdict_status": "✅ HIT" if top_pick_hit else ("⚠️ PLACE" if top_pick_placed else "❌ MISS")
        }
    
    def get_ledger_stats(self) -> Dict:
        """
        Get statistics from the Scout Ledger.
        
        Returns:
            Statistics dictionary
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ ARCHIVIST not active. Call activate() first.")
        
        with open(self.ledger_file, 'r') as f:
            ledger = json.load(f)
        
        entries = ledger.get("entries", [])
        
        total = len(entries)
        pending = sum(1 for e in entries if e["status"] == "PENDING")
        completed = sum(1 for e in entries if e["status"] == "COMPLETED")
        
        # Performance stats
        hits = sum(1 for e in entries if e.get("performance", {}).get("top_pick_won", False))
        places = sum(1 for e in entries if e.get("performance", {}).get("top_pick_placed", False))
        
        hit_rate = (hits / completed * 100) if completed > 0 else 0.0
        place_rate = (places / completed * 100) if completed > 0 else 0.0
        
        return {
            "total_predictions": total,
            "pending": pending,
            "completed": completed,
            "wins": hits,
            "places": places,
            "hit_rate": round(hit_rate, 2),
            "place_rate": round(place_rate, 2)
        }
    
    def get_recent_entries(self, limit: int = 10) -> List[Dict]:
        """
        Get most recent ledger entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent entries
        """
        if self.status != "ACTIVE":
            raise RuntimeError("VÉLØ ARCHIVIST not active. Call activate() first.")
        
        with open(self.ledger_file, 'r') as f:
            ledger = json.load(f)
        
        entries = ledger.get("entries", [])
        
        # Sort by timestamp (most recent first)
        sorted_entries = sorted(entries, key=lambda x: x["timestamp"], reverse=True)
        
        return sorted_entries[:limit]
    
    def export_ledger(self, output_path: Optional[str] = None) -> str:
        """
        Export ledger to a file.
        
        Args:
            output_path: Path for export file
            
        Returns:
            Path to exported file
        """
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = self.ledger_path / f"ledger_export_{timestamp}.json"
        
        with open(self.ledger_file, 'r') as f:
            ledger = json.load(f)
        
        with open(output_path, 'w') as f:
            json.dump(ledger, f, indent=2)
        
        print(f"📤 ARCHIVIST: Exported ledger to {output_path}")
        
        return str(output_path)
    
    def get_status(self) -> Dict:
        """Get current agent status."""
        stats = self.get_ledger_stats() if self.status == "ACTIVE" else {}
        
        return {
            "agent": self.name,
            "version": self.version,
            "status": self.status,
            "ledger_path": str(self.ledger_path),
            "statistics": stats
        }


def main():
    """Test VÉLØ ARCHIVIST agent."""
    print("📚 VÉLØ ARCHIVIST - Ledger Manager")
    print("="*60)
    
    archivist = VeloArchivist()
    archivist.activate()
    
    # Display status
    status = archivist.get_status()
    print(f"\n📊 ARCHIVIST Status:")
    print(json.dumps(status, indent=2))
    
    # Test logging
    test_race = {
        "track": "Yarmouth",
        "time": "14:30",
        "distance": "6f"
    }
    
    test_verdict = {
        "velo_verdict": {
            "top_strike_selection": "Test Runner A"
        }
    }
    
    entry_id = archivist.log_prediction("TEST_001", test_race, test_verdict)
    print(f"\n✅ Test prediction logged: {entry_id}")
    
    # Get stats
    stats = archivist.get_ledger_stats()
    print(f"\n📈 Ledger Stats:")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()

