"""
VÉLØ Memory System - Persistent Memory for the Oracle
Inspired by meMCP (Memory-Enhanced Model Context Protocol)

Provides persistent, searchable memory capabilities for VÉLØ to:
- Remember every race analyzed
- Store patterns discovered
- Track predictions and outcomes
- Enable continuous learning
- Build cumulative intelligence
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import re
from collections import Counter
import math


class VeloMemory:
    """
    Persistent memory system for VÉLØ Oracle.
    
    Features:
    - Persistent storage across sessions
    - Semantic search with TF-IDF
    - Fact quality scoring
    - Atomic writes (no data loss)
    - Cross-session knowledge building
    """
    
    def __init__(self, memory_dir: str = None):
        """Initialize VÉLØ memory system."""
        if memory_dir is None:
            memory_dir = os.path.expanduser("~/.velo_memory")
        
        self.memory_dir = Path(memory_dir)
        self.races_dir = self.memory_dir / "races"
        self.patterns_dir = self.memory_dir / "patterns"
        self.predictions_dir = self.memory_dir / "predictions"
        self.outcomes_dir = self.memory_dir / "outcomes"
        self.index_dir = self.memory_dir / "indexes"
        self.config_dir = self.memory_dir / "config"
        
        # Create directory structure
        for directory in [self.races_dir, self.patterns_dir, self.predictions_dir, 
                         self.outcomes_dir, self.index_dir, self.config_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize indexes
        self.tf_idf_index = {}
        self.fact_index = {}
        
        # Load existing indexes
        self._load_indexes()
        
        print(f"✓ VÉLØ Memory initialized at {self.memory_dir}")
        print(f"  Races stored: {len(self._list_files(self.races_dir))}")
        print(f"  Patterns stored: {len(self._list_files(self.patterns_dir))}")
        print(f"  Predictions stored: {len(self._list_files(self.predictions_dir))}")
    
    def _list_files(self, directory: Path) -> List[str]:
        """List all JSON files in a directory."""
        if not directory.exists():
            return []
        return [f.stem for f in directory.glob("*.json")]
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _atomic_write(self, filepath: Path, data: Dict) -> bool:
        """
        Atomic write operation to prevent data corruption.
        Writes to temp file first, then renames.
        """
        try:
            temp_path = filepath.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            # Atomic rename
            temp_path.replace(filepath)
            return True
        except Exception as e:
            print(f"✗ Error writing {filepath}: {e}")
            return False
    
    def _load_indexes(self):
        """Load existing indexes from disk."""
        index_file = self.index_dir / "tf_idf_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    self.tf_idf_index = json.load(f)
            except Exception as e:
                print(f"⚠ Could not load index: {e}")
                self.tf_idf_index = {}
    
    def _save_indexes(self):
        """Save indexes to disk."""
        index_file = self.index_dir / "tf_idf_index.json"
        self._atomic_write(index_file, self.tf_idf_index)
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for TF-IDF."""
        # Convert to lowercase and split on non-alphanumeric
        tokens = re.findall(r'\b\w+\b', text.lower())
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'was', 'are', 'were'}
        return [t for t in tokens if t not in stop_words and len(t) > 2]
    
    def _calculate_tf(self, tokens: List[str]) -> Dict[str, float]:
        """Calculate term frequency."""
        if not tokens:
            return {}
        counter = Counter(tokens)
        total = len(tokens)
        return {term: count / total for term, count in counter.items()}
    
    def _calculate_idf(self, term: str, all_documents: List[List[str]]) -> float:
        """Calculate inverse document frequency."""
        if not all_documents:
            return 0.0
        doc_count = sum(1 for doc in all_documents if term in doc)
        if doc_count == 0:
            return 0.0
        return math.log(len(all_documents) / doc_count)
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two TF-IDF vectors."""
        if not vec1 or not vec2:
            return 0.0
        
        # Get common terms
        common_terms = set(vec1.keys()) & set(vec2.keys())
        if not common_terms:
            return 0.0
        
        # Calculate dot product
        dot_product = sum(vec1[term] * vec2[term] for term in common_terms)
        
        # Calculate magnitudes
        mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
    
    # ===== RACE MEMORY =====
    
    def store_race(self, race_data: Dict) -> str:
        """
        Store race data with semantic indexing.
        
        Args:
            race_data: Dictionary containing race information
        
        Returns:
            race_id: Unique identifier for the race
        """
        # Generate unique ID
        race_key = f"{race_data.get('track', 'unknown')}_{race_data.get('time', 'unknown')}_{race_data.get('date', datetime.now().date())}"
        race_id = self._generate_id(race_key)
        
        # Add metadata
        race_data['race_id'] = race_id
        race_data['stored_at'] = datetime.now().isoformat()
        
        # Store race
        race_file = self.races_dir / f"{race_id}.json"
        if self._atomic_write(race_file, race_data):
            # Index for semantic search
            self._index_race(race_id, race_data)
            print(f"✓ Race stored: {race_data.get('track')} {race_data.get('time')}")
            return race_id
        else:
            print(f"✗ Failed to store race")
            return None
    
    def _index_race(self, race_id: str, race_data: Dict):
        """Index race for semantic search."""
        # Create searchable text from race data
        searchable_text = " ".join([
            str(race_data.get('track', '')),
            str(race_data.get('race_type', '')),
            str(race_data.get('distance', '')),
            str(race_data.get('going', '')),
            " ".join([h.get('name', '') for h in race_data.get('horses', [])]),
            " ".join([h.get('trainer', '') for h in race_data.get('horses', [])]),
            " ".join([h.get('jockey', '') for h in race_data.get('horses', [])])
        ])
        
        # Tokenize
        tokens = self._tokenize(searchable_text)
        
        # Calculate TF
        tf = self._calculate_tf(tokens)
        
        # Store in index
        self.tf_idf_index[race_id] = {
            'tokens': tokens,
            'tf': tf,
            'text': searchable_text
        }
        
        self._save_indexes()
    
    def get_race(self, race_id: str) -> Optional[Dict]:
        """Retrieve race by ID."""
        race_file = self.races_dir / f"{race_id}.json"
        if race_file.exists():
            with open(race_file, 'r') as f:
                return json.load(f)
        return None
    
    def search_similar_races(self, query_race: Dict, top_k: int = 5) -> List[Tuple[str, float, Dict]]:
        """
        Find similar races using semantic search.
        
        Args:
            query_race: Race data to search for
            top_k: Number of similar races to return
        
        Returns:
            List of (race_id, similarity_score, race_data) tuples
        """
        # Create query text
        query_text = " ".join([
            str(query_race.get('track', '')),
            str(query_race.get('race_type', '')),
            str(query_race.get('distance', '')),
            str(query_race.get('going', ''))
        ])
        
        # Tokenize query
        query_tokens = self._tokenize(query_text)
        query_tf = self._calculate_tf(query_tokens)
        
        # Calculate similarities
        similarities = []
        for race_id, index_data in self.tf_idf_index.items():
            similarity = self._cosine_similarity(query_tf, index_data['tf'])
            if similarity > 0:
                similarities.append((race_id, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Get top K races
        results = []
        for race_id, score in similarities[:top_k]:
            race_data = self.get_race(race_id)
            if race_data:
                results.append((race_id, score, race_data))
        
        return results
    
    # ===== PATTERN MEMORY =====
    
    def store_pattern(self, pattern_type: str, pattern_data: Dict) -> str:
        """
        Store discovered pattern.
        
        Args:
            pattern_type: Type of pattern (trainer, jockey, course, etc.)
            pattern_data: Pattern details
        
        Returns:
            pattern_id: Unique identifier
        """
        pattern_key = f"{pattern_type}_{pattern_data.get('name', 'unknown')}"
        pattern_id = self._generate_id(pattern_key)
        
        pattern_data['pattern_id'] = pattern_id
        pattern_data['pattern_type'] = pattern_type
        pattern_data['discovered_at'] = datetime.now().isoformat()
        pattern_data['confidence'] = pattern_data.get('confidence', 0.0)
        
        pattern_file = self.patterns_dir / f"{pattern_id}.json"
        if self._atomic_write(pattern_file, pattern_data):
            print(f"✓ Pattern stored: {pattern_type} - {pattern_data.get('name')}")
            return pattern_id
        return None
    
    def get_patterns(self, pattern_type: str = None, min_confidence: float = 0.0) -> List[Dict]:
        """
        Retrieve patterns by type and confidence.
        
        Args:
            pattern_type: Filter by pattern type (optional)
            min_confidence: Minimum confidence threshold
        
        Returns:
            List of pattern dictionaries
        """
        patterns = []
        for pattern_file in self.patterns_dir.glob("*.json"):
            with open(pattern_file, 'r') as f:
                pattern = json.load(f)
                
                # Filter by type
                if pattern_type and pattern.get('pattern_type') != pattern_type:
                    continue
                
                # Filter by confidence
                if pattern.get('confidence', 0.0) < min_confidence:
                    continue
                
                patterns.append(pattern)
        
        # Sort by confidence
        patterns.sort(key=lambda x: x.get('confidence', 0.0), reverse=True)
        return patterns
    
    # ===== PREDICTION MEMORY =====
    
    def store_prediction(self, race_id: str, prediction_data: Dict) -> str:
        """
        Store prediction for a race.
        
        Args:
            race_id: ID of the race
            prediction_data: Prediction details
        
        Returns:
            prediction_id: Unique identifier
        """
        prediction_id = self._generate_id(f"{race_id}_{datetime.now().isoformat()}")
        
        prediction_data['prediction_id'] = prediction_id
        prediction_data['race_id'] = race_id
        prediction_data['predicted_at'] = datetime.now().isoformat()
        
        prediction_file = self.predictions_dir / f"{prediction_id}.json"
        if self._atomic_write(prediction_file, prediction_data):
            print(f"✓ Prediction stored for race {race_id}")
            return prediction_id
        return None
    
    def get_prediction(self, prediction_id: str) -> Optional[Dict]:
        """Retrieve prediction by ID."""
        prediction_file = self.predictions_dir / f"{prediction_id}.json"
        if prediction_file.exists():
            with open(prediction_file, 'r') as f:
                return json.load(f)
        return None
    
    # ===== OUTCOME MEMORY =====
    
    def store_outcome(self, prediction_id: str, outcome_data: Dict) -> str:
        """
        Store actual outcome and learning data.
        
        Args:
            prediction_id: ID of the prediction
            outcome_data: Actual results and analysis
        
        Returns:
            outcome_id: Unique identifier
        """
        outcome_id = self._generate_id(f"{prediction_id}_outcome")
        
        outcome_data['outcome_id'] = outcome_id
        outcome_data['prediction_id'] = prediction_id
        outcome_data['recorded_at'] = datetime.now().isoformat()
        
        # Calculate accuracy if possible
        prediction = self.get_prediction(prediction_id)
        if prediction and 'shortlist' in prediction and 'winner' in outcome_data:
            shortlisted_horses = [h['name'] for h in prediction['shortlist']]
            outcome_data['hit'] = outcome_data['winner'] in shortlisted_horses
            outcome_data['accuracy'] = 1.0 if outcome_data['hit'] else 0.0
        
        outcome_file = self.outcomes_dir / f"{outcome_id}.json"
        if self._atomic_write(outcome_file, outcome_data):
            print(f"✓ Outcome stored for prediction {prediction_id}")
            return outcome_id
        return None
    
    def get_performance_stats(self) -> Dict:
        """
        Calculate overall performance statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        outcomes = []
        for outcome_file in self.outcomes_dir.glob("*.json"):
            with open(outcome_file, 'r') as f:
                outcomes.append(json.load(f))
        
        if not outcomes:
            return {
                'total_predictions': 0,
                'hits': 0,
                'misses': 0,
                'accuracy': 0.0,
                'learning_rate': 0.0
            }
        
        hits = sum(1 for o in outcomes if o.get('hit', False))
        total = len(outcomes)
        
        return {
            'total_predictions': total,
            'hits': hits,
            'misses': total - hits,
            'accuracy': hits / total if total > 0 else 0.0,
            'learning_rate': self._calculate_learning_rate(outcomes)
        }
    
    def _calculate_learning_rate(self, outcomes: List[Dict]) -> float:
        """
        Calculate if accuracy is improving over time.
        
        Returns:
            Learning rate (positive = improving, negative = declining)
        """
        if len(outcomes) < 10:
            return 0.0
        
        # Sort by time
        sorted_outcomes = sorted(outcomes, key=lambda x: x.get('recorded_at', ''))
        
        # Split into first half and second half
        mid = len(sorted_outcomes) // 2
        first_half = sorted_outcomes[:mid]
        second_half = sorted_outcomes[mid:]
        
        # Calculate accuracy for each half
        first_accuracy = sum(1 for o in first_half if o.get('hit', False)) / len(first_half)
        second_accuracy = sum(1 for o in second_half if o.get('hit', False)) / len(second_half)
        
        # Learning rate is the difference
        return second_accuracy - first_accuracy
    
    # ===== MEMORY STATS =====
    
    def get_memory_stats(self) -> Dict:
        """Get statistics about stored memory."""
        return {
            'races_stored': len(self._list_files(self.races_dir)),
            'patterns_discovered': len(self._list_files(self.patterns_dir)),
            'predictions_made': len(self._list_files(self.predictions_dir)),
            'outcomes_recorded': len(self._list_files(self.outcomes_dir)),
            'memory_location': str(self.memory_dir),
            'performance': self.get_performance_stats()
        }
    
    def clear_memory(self, confirm: bool = False):
        """
        Clear all memory (use with caution).
        
        Args:
            confirm: Must be True to actually clear
        """
        if not confirm:
            print("⚠ Memory clear not confirmed. Set confirm=True to proceed.")
            return
        
        import shutil
        if self.memory_dir.exists():
            shutil.rmtree(self.memory_dir)
            print("✓ Memory cleared")
            self.__init__()  # Reinitialize


if __name__ == "__main__":
    # Test the memory system
    print("=== VÉLØ Memory System Test ===\n")
    
    memory = VeloMemory()
    
    # Test race storage
    test_race = {
        'track': 'Punchestown',
        'time': '15:05',
        'date': '2025-10-15',
        'race_type': 'Handicap',
        'distance': '2m',
        'going': 'Good',
        'horses': [
            {'name': 'Test Horse 1', 'trainer': 'Trainer A', 'jockey': 'Jockey X'},
            {'name': 'Test Horse 2', 'trainer': 'Trainer B', 'jockey': 'Jockey Y'}
        ]
    }
    
    race_id = memory.store_race(test_race)
    print(f"\nRace ID: {race_id}")
    
    # Test pattern storage
    pattern_id = memory.store_pattern('trainer', {
        'name': 'Trainer A',
        'track': 'Punchestown',
        'win_rate': 0.25,
        'confidence': 0.75,
        'sample_size': 20
    })
    
    # Test prediction storage
    prediction_id = memory.store_prediction(race_id, {
        'shortlist': [
            {'name': 'Test Horse 1', 'odds': 5.0, 'confidence': 0.8}
        ],
        'confidence_index': 85
    })
    
    # Test outcome storage
    outcome_id = memory.store_outcome(prediction_id, {
        'winner': 'Test Horse 1',
        'placed': ['Test Horse 1', 'Test Horse 2']
    })
    
    # Get stats
    print("\n=== Memory Stats ===")
    stats = memory.get_memory_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("\n✓ VÉLØ Memory System operational")

