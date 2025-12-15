"""
VÉLØ v11 - Signal Engines (Phase 1)
Layer 2: Multiple specialized model families

Phase 1 engines:
- Naive Bayes (probabilistic, fast, interpretable)
- K-Means Clustering (race/horse grouping, chaos detection)
- PCA (dimensionality reduction, noise compression)
"""

import numpy as np
import pandas as pd
from sklearn.naive_bayes import GaussianNB
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Tuple
import pickle
import os


class NaiveBayesEngine:
    """
    Naive Bayes probability engine
    Fast, interpretable, robust in low-sample regimes
    Great for low-grade handicaps where noise is huge
    """
    
    def __init__(self):
        self.model = GaussianNB()
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def train(self, X: pd.DataFrame, y: np.ndarray):
        """Train on feature blocks"""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return P(win | ability, intent, market, conditions)"""
        if not self.is_trained:
            return np.zeros((len(X), 2))
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def save(self, path: str):
        """Save model"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({'model': self.model, 'scaler': self.scaler}, f)
    
    def load(self, path: str):
        """Load model"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.is_trained = True


class KMeansClusteringEngine:
    """
    K-Means clustering for automatic grouping
    
    Clusters races into regimes:
    - Slow/honest/feral
    - Strong favourite vs wide open
    
    Clusters horses into types:
    - Exposed grinder
    - Unexposed improver
    - Plot horse
    - Outside gaff
    
    Outputs:
    - Race chaos score
    - Structure class (feeds SQPE and staking)
    """
    
    def __init__(self, n_race_clusters: int = 4, n_horse_clusters: int = 5):
        self.race_clusterer = KMeans(n_clusters=n_race_clusters, random_state=42)
        self.horse_clusterer = KMeans(n_clusters=n_horse_clusters, random_state=42)
        self.race_scaler = StandardScaler()
        self.horse_scaler = StandardScaler()
        self.is_trained = False
    
    def train_race_clusters(self, race_features: pd.DataFrame):
        """
        Cluster races by structure
        Features: field_size, pace_pressure, odds_spread, class, going
        """
        X = self.race_scaler.fit_transform(race_features)
        self.race_clusterer.fit(X)
        self.is_trained = True
    
    def train_horse_clusters(self, horse_features: pd.DataFrame):
        """
        Cluster horses by type
        Features: ability, form_trend, days_since_run, class_best, variance
        """
        X = self.horse_scaler.fit_transform(horse_features)
        self.horse_clusterer.fit(X)
    
    def predict_race_cluster(self, race_features: pd.DataFrame) -> np.ndarray:
        """Return race structure cluster ID"""
        X = self.race_scaler.transform(race_features)
        return self.race_clusterer.predict(X)
    
    def predict_horse_cluster(self, horse_features: pd.DataFrame) -> np.ndarray:
        """Return horse type cluster ID"""
        X = self.horse_scaler.transform(horse_features)
        return self.horse_clusterer.predict(X)
    
    def get_chaos_score(self, race_features: pd.DataFrame) -> float:
        """
        Calculate race chaos score from cluster assignment
        Cluster 0 = structured, Cluster 3 = full chaos
        """
        cluster = self.predict_race_cluster(race_features)[0]
        # Map cluster to chaos score (0 = clean, 1 = chaos)
        chaos_map = {0: 0.2, 1: 0.4, 2: 0.6, 3: 0.9}
        return chaos_map.get(cluster, 0.5)
    
    def save(self, path: str):
        """Save clusterers"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'race_clusterer': self.race_clusterer,
                'horse_clusterer': self.horse_clusterer,
                'race_scaler': self.race_scaler,
                'horse_scaler': self.horse_scaler
            }, f)
    
    def load(self, path: str):
        """Load clusterers"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.race_clusterer = data['race_clusterer']
            self.horse_clusterer = data['horse_clusterer']
            self.race_scaler = data['race_scaler']
            self.horse_scaler = data['horse_scaler']
            self.is_trained = True


class PCAEngine:
    """
    PCA dimensionality reduction
    Compress correlated features into clean components
    Feed to gradient boosting and RF instead of raw variables
    
    Effect:
    - Less overfitting
    - Sharper signals
    - Faster training
    """
    
    def __init__(self, n_components: int = 10):
        self.pca = PCA(n_components=n_components)
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def fit(self, X: pd.DataFrame):
        """Fit PCA on training data"""
        X_scaled = self.scaler.fit_transform(X)
        self.pca.fit(X_scaled)
        self.is_trained = True
    
    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Transform features to PCA components"""
        if not self.is_trained:
            return X.values
        X_scaled = self.scaler.transform(X)
        return self.pca.transform(X_scaled)
    
    def get_explained_variance(self) -> np.ndarray:
        """Return explained variance ratio per component"""
        return self.pca.explained_variance_ratio_
    
    def save(self, path: str):
        """Save PCA"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({'pca': self.pca, 'scaler': self.scaler}, f)
    
    def load(self, path: str):
        """Load PCA"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.pca = data['pca']
            self.scaler = data['scaler']
            self.is_trained = True


class V11SignalEngines:
    """
    Orchestrator for Phase 1 signal engines
    Combines Naive Bayes, K-Means, and PCA outputs
    """
    
    def __init__(self):
        self.bayes = NaiveBayesEngine()
        self.clusters = KMeansClusteringEngine()
        self.pca = PCAEngine(n_components=10)
    
    def train(self, X: pd.DataFrame, y: np.ndarray):
        """Train all Phase 1 engines"""
        print("Training Naive Bayes...")
        self.bayes.train(X, y)
        
        print("Training K-Means clusters...")
        # Race features for clustering
        race_features = X[['field_size', 'pace_pressure', 'chaos_score']]
        self.clusters.train_race_clusters(race_features)
        
        # Horse features for clustering
        horse_features = X[['rpr_best', 'form_trend', 'days_since_run', 'rpr_variance']]
        self.clusters.train_horse_clusters(horse_features)
        
        print("Training PCA...")
        self.pca.fit(X)
        
        print("✅ Phase 1 engines trained")
    
    def predict(self, X: pd.DataFrame) -> Dict:
        """
        Get predictions from all Phase 1 engines
        
        Returns:
            Dict with:
            - bayes_proba: Naive Bayes win probability
            - race_cluster: Race structure cluster ID
            - horse_cluster: Horse type cluster ID
            - chaos_score: Race chaos score
            - pca_components: PCA-transformed features
        """
        race_features = X[['field_size', 'pace_pressure', 'chaos_score']]
        horse_features = X[['rpr_best', 'form_trend', 'days_since_run', 'rpr_variance']]
        
        return {
            'bayes_proba': self.bayes.predict_proba(X)[:, 1],
            'race_cluster': self.clusters.predict_race_cluster(race_features),
            'horse_cluster': self.clusters.predict_horse_cluster(horse_features),
            'chaos_score': self.clusters.get_chaos_score(race_features),
            'pca_components': self.pca.transform(X)
        }
    
    def save_all(self, base_dir: str):
        """Save all engines"""
        self.bayes.save(f"{base_dir}/bayes_engine.pkl")
        self.clusters.save(f"{base_dir}/kmeans_engine.pkl")
        self.pca.save(f"{base_dir}/pca_engine.pkl")
        print(f"✅ All Phase 1 engines saved to {base_dir}")
    
    def load_all(self, base_dir: str):
        """Load all engines"""
        self.bayes.load(f"{base_dir}/bayes_engine.pkl")
        self.clusters.load(f"{base_dir}/kmeans_engine.pkl")
        self.pca.load(f"{base_dir}/pca_engine.pkl")
        print(f"✅ All Phase 1 engines loaded from {base_dir}")
