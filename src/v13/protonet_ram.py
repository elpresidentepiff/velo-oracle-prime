"""
VÉLØ Oracle v13 - Prototypical Networks for Rival Analysis Module (RAM)

Implements ProtoNet for few-shot classification of rival betting patterns.

Based on research: "Prototypical Networks for Few-shot Learning"
Application: Detect and classify rival AI betting strategies from limited examples.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RivalPattern:
    """Represents a detected rival betting pattern."""
    rival_id: str
    pattern_type: str  # 'value_hunter', 'momentum_chaser', 'contrarian', etc.
    confidence: float
    features: np.ndarray
    timestamp: str


class ProtoNetEncoder(nn.Module):
    """
    Encoder network for ProtoNet.
    
    Maps betting patterns to an embedding space where similar patterns
    are close together.
    """
    
    def __init__(self, input_dim: int, hidden_dims: List[int], output_dim: int):
        """
        Initialize encoder.
        
        Args:
            input_dim: Dimension of input features
            hidden_dims: List of hidden layer dimensions
            output_dim: Dimension of output embedding
        """
        super().__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.BatchNorm1d(hidden_dim)
            ])
            prev_dim = hidden_dim
        
        # Final projection to embedding space
        layers.append(nn.Linear(prev_dim, output_dim))
        
        self.encoder = nn.Sequential(*layers)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Encode input to embedding space.
        
        Args:
            x: Input tensor of shape (batch_size, input_dim)
            
        Returns:
            Embeddings of shape (batch_size, output_dim)
        """
        return self.encoder(x)


class ProtoNet:
    """
    Prototypical Networks for few-shot rival pattern classification.
    
    Key idea:
    - Each rival type has a "prototype" (average embedding of examples)
    - Classify new patterns by finding nearest prototype
    - Can learn from very few examples (few-shot learning)
    """
    
    def __init__(
        self,
        input_dim: int = 20,
        hidden_dims: List[int] = [64, 64],
        embedding_dim: int = 32,
        learning_rate: float = 0.001
    ):
        """
        Initialize ProtoNet.
        
        Args:
            input_dim: Dimension of betting pattern features
            hidden_dims: Hidden layer dimensions for encoder
            embedding_dim: Dimension of embedding space
            learning_rate: Learning rate for training
        """
        self.input_dim = input_dim
        self.embedding_dim = embedding_dim
        
        # Create encoder network
        self.encoder = ProtoNetEncoder(input_dim, hidden_dims, embedding_dim)
        
        # Optimizer
        self.optimizer = torch.optim.Adam(self.encoder.parameters(), lr=learning_rate)
        
        # Prototypes (class centroids in embedding space)
        self.prototypes: Dict[str, torch.Tensor] = {}
        
        # Rival type definitions
        self.rival_types = [
            'value_hunter',      # Bets on undervalued horses
            'momentum_chaser',   # Follows recent form
            'contrarian',        # Bets against public
            'favorite_backer',   # Always bets favorites
            'longshot_hunter'    # Targets high-odds horses
        ]
        
        logger.info(f"ProtoNet initialized: {input_dim}D -> {embedding_dim}D")
    
    def extract_features(self, betting_data: Dict[str, any]) -> np.ndarray:
        """
        Extract features from betting data.
        
        Features capture betting behavior:
        - Average odds of bets
        - Variance in odds
        - Bet timing patterns
        - Stake distribution
        - Win rate
        - etc.
        
        Args:
            betting_data: Dict containing betting history
            
        Returns:
            Feature vector of shape (input_dim,)
        """
        features = []
        
        # Odds-based features
        odds = betting_data.get('odds', [])
        if len(odds) > 0:
            features.extend([
                np.mean(odds),           # Average odds
                np.std(odds),            # Odds variance
                np.min(odds),            # Minimum odds
                np.max(odds),            # Maximum odds
                np.median(odds)          # Median odds
            ])
        else:
            features.extend([0.0] * 5)
        
        # Stake-based features
        stakes = betting_data.get('stakes', [])
        if len(stakes) > 0:
            features.extend([
                np.mean(stakes),         # Average stake
                np.std(stakes),          # Stake variance
                np.max(stakes) / (np.mean(stakes) + 1e-6)  # Max/avg ratio
            ])
        else:
            features.extend([0.0] * 3)
        
        # Timing features
        bet_times = betting_data.get('bet_times_before_race', [])
        if len(bet_times) > 0:
            features.extend([
                np.mean(bet_times),      # Average time before race
                np.std(bet_times)        # Timing variance
            ])
        else:
            features.extend([0.0] * 2)
        
        # Performance features
        features.extend([
            betting_data.get('win_rate', 0.0),
            betting_data.get('roi', 0.0),
            betting_data.get('total_bets', 0.0) / 100.0  # Normalized
        ])
        
        # Market position features
        features.extend([
            betting_data.get('avg_market_position', 0.5),  # Position in market (0-1)
            betting_data.get('contrarian_score', 0.0),     # How often bets against public
            betting_data.get('favorite_frequency', 0.0)    # How often bets favorites
        ])
        
        # Behavioral features
        features.extend([
            betting_data.get('bet_frequency', 0.0),        # Bets per race
            betting_data.get('multi_bet_frequency', 0.0),  # Multiple bets per race
            betting_data.get('consistency_score', 0.0)     # Strategy consistency
        ])
        
        # Pad or truncate to input_dim
        features = np.array(features[:self.input_dim])
        if len(features) < self.input_dim:
            features = np.pad(features, (0, self.input_dim - len(features)))
        
        return features
    
    def train_episode(
        self,
        support_set: Dict[str, List[np.ndarray]],
        query_set: Dict[str, List[np.ndarray]]
    ) -> float:
        """
        Train on a single episode (few-shot learning style).
        
        Args:
            support_set: Dict mapping rival_type -> list of examples
            query_set: Dict mapping rival_type -> list of query examples
            
        Returns:
            Loss value
        """
        self.encoder.train()
        self.optimizer.zero_grad()
        
        # Compute prototypes from support set
        prototypes = {}
        for rival_type, examples in support_set.items():
            if len(examples) == 0:
                continue
            
            # Convert to tensor
            examples_tensor = torch.FloatTensor(np.array(examples))
            
            # Encode examples
            embeddings = self.encoder(examples_tensor)
            
            # Compute prototype (mean of embeddings)
            prototype = embeddings.mean(dim=0)
            prototypes[rival_type] = prototype
        
        # Classify query set
        total_loss = 0.0
        num_queries = 0
        
        for rival_type, queries in query_set.items():
            if len(queries) == 0 or rival_type not in prototypes:
                continue
            
            queries_tensor = torch.FloatTensor(np.array(queries))
            query_embeddings = self.encoder(queries_tensor)
            
            # Calculate distances to all prototypes
            for query_emb in query_embeddings:
                distances = {}
                for proto_type, proto in prototypes.items():
                    dist = F.pairwise_distance(
                        query_emb.unsqueeze(0),
                        proto.unsqueeze(0)
                    )
                    distances[proto_type] = dist
                
                # Convert to logits (negative distances)
                logits = torch.stack([
                    -distances[rt] for rt in self.rival_types if rt in distances
                ])
                
                # Get true label index
                true_idx = [i for i, rt in enumerate(self.rival_types) if rt == rival_type and rt in distances][0]
                true_label = torch.tensor([true_idx])
                
                # Cross-entropy loss
                loss = F.cross_entropy(logits.unsqueeze(0), true_label)
                total_loss += loss
                num_queries += 1
        
        if num_queries > 0:
            avg_loss = total_loss / num_queries
            avg_loss.backward()
            self.optimizer.step()
            
            return avg_loss.item()
        
        return 0.0
    
    def update_prototypes(self, labeled_examples: Dict[str, List[np.ndarray]]):
        """
        Update prototypes from labeled examples.
        
        Args:
            labeled_examples: Dict mapping rival_type -> list of feature vectors
        """
        self.encoder.eval()
        
        with torch.no_grad():
            for rival_type, examples in labeled_examples.items():
                if len(examples) == 0:
                    continue
                
                examples_tensor = torch.FloatTensor(np.array(examples))
                embeddings = self.encoder(examples_tensor)
                prototype = embeddings.mean(dim=0)
                
                self.prototypes[rival_type] = prototype
        
        logger.info(f"Updated prototypes for {len(self.prototypes)} rival types")
    
    def classify(self, features: np.ndarray, top_k: int = 3) -> List[Tuple[str, float]]:
        """
        Classify a betting pattern.
        
        Args:
            features: Feature vector of shape (input_dim,)
            top_k: Return top-k most likely rival types
            
        Returns:
            List of (rival_type, confidence) tuples
        """
        if len(self.prototypes) == 0:
            logger.warning("No prototypes available. Call update_prototypes() first.")
            return []
        
        self.encoder.eval()
        
        with torch.no_grad():
            # Encode query
            features_tensor = torch.FloatTensor(features).unsqueeze(0)
            query_emb = self.encoder(features_tensor).squeeze(0)
            
            # Calculate distances to all prototypes
            distances = {}
            for rival_type, prototype in self.prototypes.items():
                dist = F.pairwise_distance(
                    query_emb.unsqueeze(0),
                    prototype.unsqueeze(0)
                ).item()
                distances[rival_type] = dist
            
            # Convert distances to confidences (softmax of negative distances)
            neg_distances = {k: -v for k, v in distances.items()}
            max_neg_dist = max(neg_distances.values())
            exp_neg_dists = {k: np.exp(v - max_neg_dist) for k, v in neg_distances.items()}
            sum_exp = sum(exp_neg_dists.values())
            confidences = {k: v / sum_exp for k, v in exp_neg_dists.items()}
            
            # Sort by confidence
            sorted_results = sorted(
                confidences.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            return sorted_results[:top_k]
    
    def save(self, path: str):
        """Save model to disk."""
        torch.save({
            'encoder_state': self.encoder.state_dict(),
            'prototypes': self.prototypes,
            'config': {
                'input_dim': self.input_dim,
                'embedding_dim': self.embedding_dim
            }
        }, path)
        logger.info(f"Model saved to {path}")
    
    def load(self, path: str):
        """Load model from disk."""
        checkpoint = torch.load(path)
        self.encoder.load_state_dict(checkpoint['encoder_state'])
        self.prototypes = checkpoint['prototypes']
        logger.info(f"Model loaded from {path}")


class RivalAnalysisModule:
    """
    High-level Rival Analysis Module (RAM) for VÉLØ v13.
    
    Uses ProtoNet to detect and classify rival betting strategies.
    """
    
    def __init__(self):
        """Initialize RAM."""
        self.protonet = ProtoNet()
        self.detected_rivals: Dict[str, RivalPattern] = {}
        
        logger.info("Rival Analysis Module (RAM) initialized")
    
    def analyze_market(self, market_data: Dict[str, any]) -> List[RivalPattern]:
        """
        Analyze market data to detect rival patterns.
        
        Args:
            market_data: Dict containing market activity
            
        Returns:
            List of detected rival patterns
        """
        detected = []
        
        # Extract betting patterns from market data
        betting_patterns = market_data.get('betting_patterns', [])
        
        for pattern_data in betting_patterns:
            # Extract features
            features = self.protonet.extract_features(pattern_data)
            
            # Classify pattern
            classifications = self.protonet.classify(features, top_k=1)
            
            if classifications:
                rival_type, confidence = classifications[0]
                
                if confidence > 0.7:  # High confidence threshold
                    rival_pattern = RivalPattern(
                        rival_id=pattern_data.get('rival_id', 'unknown'),
                        pattern_type=rival_type,
                        confidence=confidence,
                        features=features,
                        timestamp=pattern_data.get('timestamp', '')
                    )
                    detected.append(rival_pattern)
        
        return detected
    
    def get_counter_strategy(self, rival_pattern: RivalPattern) -> Dict[str, any]:
        """
        Generate counter-strategy for a detected rival pattern.
        
        Args:
            rival_pattern: Detected rival pattern
            
        Returns:
            Dict with counter-strategy recommendations
        """
        strategies = {
            'value_hunter': {
                'action': 'avoid_overlapping_bets',
                'reasoning': 'Value hunters drive down odds on undervalued horses',
                'recommendation': 'Bet earlier or find different value opportunities'
            },
            'momentum_chaser': {
                'action': 'fade_late_money',
                'reasoning': 'Momentum chasers create false signals',
                'recommendation': 'Bet against late-shortening horses with weak fundamentals'
            },
            'contrarian': {
                'action': 'follow_selectively',
                'reasoning': 'Contrarians can be right when public is wrong',
                'recommendation': 'Validate contrarian positions with own analysis'
            },
            'favorite_backer': {
                'action': 'exploit_overlay',
                'reasoning': 'Favorite backers create value in non-favorites',
                'recommendation': 'Look for value in second and third favorites'
            },
            'longshot_hunter': {
                'action': 'avoid_longshots',
                'reasoning': 'Longshot hunters inflate odds on unlikely winners',
                'recommendation': 'Focus on realistic contenders'
            }
        }
        
        return strategies.get(rival_pattern.pattern_type, {
            'action': 'monitor',
            'reasoning': 'Unknown pattern type',
            'recommendation': 'Collect more data'
        })

