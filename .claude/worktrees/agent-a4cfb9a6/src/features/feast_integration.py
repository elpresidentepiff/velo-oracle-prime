"""
VÉLØ Oracle - Feast Feature Store Integration
Provides production-grade feature management and serving
"""
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
from pathlib import Path
from feast import FeatureStore


class VeloFeatureStore:
    """
    Integration layer between VÉLØ Oracle and Feast Feature Store.
    
    Provides:
    - Feature materialization (offline → online)
    - Online feature serving (low-latency)
    - Historical feature retrieval (training)
    - Feature consistency (training-serving parity)
    """
    
    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize Feast feature store.
        
        Args:
            repo_path: Path to Feast repository (default: feast_repo/)
        """
        if repo_path is None:
            repo_path = Path(__file__).parent.parent.parent / "feast_repo"
        
        self.repo_path = Path(repo_path)
        self.store = FeatureStore(repo_path=str(self.repo_path))
        
        print(f"✓ Feast Feature Store initialized")
        print(f"  Repository: {self.repo_path}")
        print(f"  Online store: {self.store.config.online_store.type}")
        print(f"  Offline store: {self.store.config.offline_store.type}")
    
    def get_online_features(
        self,
        horse_id: str,
        trainer_id: str,
        jockey_id: str,
        race_id: str
    ) -> Dict:
        """
        Get features for online inference (low-latency).
        
        Args:
            horse_id: Horse identifier
            trainer_id: Trainer identifier
            jockey_id: Jockey identifier
            race_id: Race identifier
        
        Returns:
            Dictionary of features
        """
        # Define entity rows
        entity_rows = [{
            "horse_id": horse_id,
            "trainer_id": trainer_id,
            "jockey_id": jockey_id,
            "race_id": race_id
        }]
        
        # Define features to retrieve
        features = [
            "trainer_velocity_features:trainer_sr_14d",
            "trainer_velocity_features:trainer_sr_30d",
            "trainer_velocity_features:trainer_sr_90d",
            "jockey_velocity_features:jockey_sr_14d",
            "jockey_velocity_features:jockey_sr_30d",
            "jockey_velocity_features:jockey_sr_90d",
            "trainer_jockey_combo_features:tj_combo_uplift",
            "horse_form_features:form_ewma",
            "horse_form_features:form_slope",
            "horse_form_features:form_var",
            "horse_form_features:layoff_days",
            "horse_form_features:layoff_penalty",
            "horse_form_features:freshness_flag",
            "horse_form_features:class_drop",
            "horse_form_features:classdrop_flag",
            "race_context_features:course_going_iv",
            "race_context_features:draw_iv",
            "race_context_features:bias_persist_flag"
        ]
        
        # Retrieve features
        feature_vector = self.store.get_online_features(
            features=features,
            entity_rows=entity_rows
        ).to_dict()
        
        return feature_vector
    
    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        features: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get historical features for training.
        
        Args:
            entity_df: DataFrame with entity keys and timestamps
            features: List of features to retrieve (default: all)
        
        Returns:
            DataFrame with features joined to entities
        """
        if features is None:
            features = [
                "trainer_velocity_features",
                "jockey_velocity_features",
                "trainer_jockey_combo_features",
                "horse_form_features",
                "race_context_features"
            ]
        
        # Get historical features
        training_df = self.store.get_historical_features(
            entity_df=entity_df,
            features=features
        ).to_df()
        
        return training_df
    
    def materialize_features(
        self,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Materialize features from offline to online store.
        
        This enables low-latency online serving.
        
        Args:
            start_date: Start of materialization window
            end_date: End of materialization window
        """
        print(f"Materializing features from {start_date} to {end_date}...")
        
        self.store.materialize(
            start_date=start_date,
            end_date=end_date
        )
        
        print("✓ Features materialized to online store")
    
    def materialize_incremental(self, end_date: datetime):
        """
        Incrementally materialize features up to end_date.
        
        Only materializes features since last materialization.
        
        Args:
            end_date: End of materialization window
        """
        print(f"Incrementally materializing features to {end_date}...")
        
        self.store.materialize_incremental(end_date=end_date)
        
        print("✓ Incremental materialization complete")
    
    def get_feature_vector_for_prediction(
        self,
        horse_id: str,
        trainer_id: str,
        jockey_id: str,
        race_id: str,
        odds: float
    ) -> Dict:
        """
        Get complete feature vector for a prediction.
        
        Combines online features with request-time features (like odds).
        
        Args:
            horse_id: Horse identifier
            trainer_id: Trainer identifier
            jockey_id: Jockey identifier
            race_id: Race identifier
            odds: Current odds
        
        Returns:
            Complete feature vector
        """
        # Get online features
        features = self.get_online_features(
            horse_id=horse_id,
            trainer_id=trainer_id,
            jockey_id=jockey_id,
            race_id=race_id
        )
        
        # Add request-time features
        features['odds'] = odds
        
        return features
    
    def apply_feature_definitions(self):
        """Apply feature definitions to the registry."""
        print("Applying feature definitions...")
        self.store.apply(objects=None, commit=True)
        print("✓ Feature definitions applied")
    
    def get_feature_service_features(self, service_name: str) -> List[str]:
        """
        Get features for a named feature service.
        
        Feature services group features for specific use cases.
        
        Args:
            service_name: Name of the feature service
        
        Returns:
            List of feature names
        """
        service = self.store.get_feature_service(service_name)
        return [f.name for f in service.features]


def create_sample_feature_data():
    """
    Create sample feature data for testing.
    
    In production, this would be replaced by actual data pipeline.
    """
    import numpy as np
    
    # Sample trainer features
    trainer_df = pd.DataFrame({
        "trainer_id": ["T001", "T002", "T003"],
        "event_timestamp": [datetime.now()] * 3,
        "trainer_sr_14d": [0.25, 0.30, 0.20],
        "trainer_sr_30d": [0.22, 0.28, 0.18],
        "trainer_sr_90d": [0.20, 0.25, 0.15],
        "trainer_roi_14d": [0.15, 0.20, 0.10],
        "trainer_roi_30d": [0.12, 0.18, 0.08],
        "trainer_roi_90d": [0.10, 0.15, 0.05],
        "trainer_total_runs": [100, 150, 80],
        "trainer_win_rate": [0.25, 0.30, 0.20]
    })
    
    # Sample jockey features
    jockey_df = pd.DataFrame({
        "jockey_id": ["J001", "J002", "J003"],
        "event_timestamp": [datetime.now()] * 3,
        "jockey_sr_14d": [0.28, 0.32, 0.22],
        "jockey_sr_30d": [0.25, 0.30, 0.20],
        "jockey_sr_90d": [0.22, 0.28, 0.18],
        "jockey_roi_14d": [0.18, 0.22, 0.12],
        "jockey_roi_30d": [0.15, 0.20, 0.10],
        "jockey_roi_90d": [0.12, 0.18, 0.08],
        "jockey_total_runs": [120, 180, 90],
        "jockey_win_rate": [0.28, 0.32, 0.22]
    })
    
    # Sample horse features
    horse_df = pd.DataFrame({
        "horse_id": ["H001", "H002", "H003"],
        "event_timestamp": [datetime.now()] * 3,
        "form_ewma": [0.6, 0.7, 0.5],
        "form_slope": [0.1, 0.2, -0.1],
        "form_var": [0.05, 0.03, 0.08],
        "layoff_days": [14, 7, 21],
        "layoff_penalty": [0.05, 0.02, 0.10],
        "freshness_flag": [1, 1, 0],
        "class_drop": [0, 1, 0],
        "classdrop_flag": [0, 1, 0],
        "total_runs": [20, 25, 15],
        "win_rate": [0.25, 0.30, 0.20]
    })
    
    # Sample race features
    race_df = pd.DataFrame({
        "race_id": ["R001", "R002", "R003"],
        "event_timestamp": [datetime.now()] * 3,
        "course_going_iv": [0.15, 0.20, 0.10],
        "draw_iv": [0.08, 0.12, 0.05],
        "bias_persist_flag": [1, 0, 1],
        "field_size": [12, 10, 14],
        "race_class": [3, 4, 2],
        "distance_furlongs": [6.0, 7.0, 5.0],
        "going_code": [1, 2, 1]
    })
    
    return trainer_df, jockey_df, horse_df, race_df


if __name__ == "__main__":
    # Test the feature store
    print("=== VÉLØ Oracle - Feast Feature Store Test ===\n")
    
    # Initialize feature store
    fs = VeloFeatureStore()
    
    # Create sample data
    print("\nCreating sample feature data...")
    trainer_df, jockey_df, horse_df, race_df = create_sample_feature_data()
    
    # Save to parquet (for offline store)
    data_dir = Path("/home/ubuntu/velo-oracle/feast_repo/data/feast")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    trainer_df.to_parquet(data_dir / "trainer_features.parquet")
    jockey_df.to_parquet(data_dir / "jockey_features.parquet")
    horse_df.to_parquet(data_dir / "horse_features.parquet")
    race_df.to_parquet(data_dir / "race_features.parquet")
    
    print("✓ Sample data saved")
    
    # Apply feature definitions
    fs.apply_feature_definitions()
    
    # Materialize features
    from datetime import timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    fs.materialize_features(start_date=start_date, end_date=end_date)
    
    # Test online feature retrieval
    print("\nTesting online feature retrieval...")
    features = fs.get_online_features(
        horse_id="H001",
        trainer_id="T001",
        jockey_id="J001",
        race_id="R001"
    )
    
    print(f"Retrieved {len(features)} features")
    print(f"Sample features: {list(features.keys())[:5]}")
    
    print("\n✓ Feast Feature Store operational!")
