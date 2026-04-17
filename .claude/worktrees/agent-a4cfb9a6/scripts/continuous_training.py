"""
VÉLØ Oracle - Continuous Training Pipeline
Trains models non-stop for 4 hours, learning from new data continuously
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class ContinuousTrainer:
    """Continuous learning system for VÉLØ Oracle"""
    
    def __init__(self, duration_hours=4):
        self.duration_hours = duration_hours
        self.end_time = datetime.now() + timedelta(hours=duration_hours)
        self.iteration = 0
        self.best_auc = 0.0
        self.training_log = []
        
        # Model storage
        self.models_dir = Path(__file__).parent.parent / "models" / "continuous"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
    def fetch_training_data(self, limit=5000):
        """Fetch latest racing data from Supabase"""
        logger.info(f"Fetching {limit} training samples from Supabase...")
        
        try:
            # Get racing data with results
            response = supabase.table("racing_data")\
                .select("*")\
                .not_.is_("finishing_position", "null")\
                .order("race_date", desc=True)\
                .limit(limit)\
                .execute()
            
            if not response.data:
                logger.warning("No data returned from Supabase")
                return None
                
            df = pd.DataFrame(response.data)
            logger.info(f"✓ Fetched {len(df)} records")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return None
    
    def engineer_features(self, df):
        """Create features for training"""
        logger.info("Engineering features...")
        
        # Target: Win (1) or Lose (0)
        df['target'] = (df['finishing_position'] == 1).astype(int)
        
        # Features
        features = []
        
        # 1. Odds-based features
        if 'odds' in df.columns:
            df['odds_prob'] = 1 / df['odds']
            df['odds_log'] = np.log(df['odds'] + 1)
            features.extend(['odds_prob', 'odds_log'])
        
        # 2. Rating features
        if 'rating' in df.columns:
            df['rating_norm'] = df['rating'] / 100
            features.append('rating_norm')
        
        # 3. Speed features
        if 'speed_figure' in df.columns:
            df['speed_norm'] = df['speed_figure'] / 100
            features.append('speed_norm')
        
        # 4. Weight features
        if 'weight_carried' in df.columns:
            df['weight_norm'] = df['weight_carried'] / 140
            features.append('weight_norm')
        
        # 5. Draw features (for flat races)
        if 'draw' in df.columns:
            df['draw_norm'] = df['draw'] / 20
            features.append('draw_norm')
        
        # 6. Age features
        if 'age' in df.columns:
            df['age_norm'] = df['age'] / 10
            features.append('age_norm')
        
        # Fill NaN values
        df[features] = df[features].fillna(df[features].median())
        
        logger.info(f"✓ Created {len(features)} features")
        return df, features
    
    def train_model(self, X, y, model_name="VELO"):
        """Train a gradient boosting model"""
        logger.info(f"Training {model_name} model...")
        
        model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            min_samples_split=20,
            min_samples_leaf=10,
            subsample=0.8,
            random_state=42
        )
        
        model.fit(X, y)
        
        # Evaluate
        y_pred_proba = model.predict_proba(X)[:, 1]
        auc = roc_auc_score(y, y_pred_proba)
        logloss = log_loss(y, y_pred_proba)
        brier = brier_score_loss(y, y_pred_proba)
        
        logger.info(f"✓ AUC: {auc:.4f} | LogLoss: {logloss:.4f} | Brier: {brier:.4f}")
        
        return model, {
            "auc": auc,
            "log_loss": logloss,
            "brier_score": brier
        }
    
    def save_model(self, model, metrics, model_name):
        """Save model and metrics"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save model
        model_path = self.models_dir / f"{model_name}_{timestamp}.pkl"
        joblib.dump(model, model_path)
        
        # Save metrics
        metrics_path = self.models_dir / f"{model_name}_{timestamp}_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"✓ Saved model to {model_path}")
        
        return model_path
    
    def run(self):
        """Run continuous training loop"""
        logger.info("="*60)
        logger.info(f"🚀 VÉLØ CONTINUOUS TRAINING STARTED")
        logger.info(f"Duration: {self.duration_hours} hours")
        logger.info(f"End Time: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)
        
        while datetime.now() < self.end_time:
            self.iteration += 1
            iteration_start = time.time()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {self.iteration}")
            logger.info(f"Time Remaining: {(self.end_time - datetime.now()).total_seconds() / 60:.1f} minutes")
            logger.info(f"{'='*60}")
            
            try:
                # 1. Fetch data
                df = self.fetch_training_data(limit=5000)
                if df is None or len(df) < 100:
                    logger.warning("Insufficient data, waiting 60 seconds...")
                    time.sleep(60)
                    continue
                
                # 2. Engineer features
                df, features = self.engineer_features(df)
                
                # 3. Prepare training data
                X = df[features].values
                y = df['target'].values
                
                # 4. Train model
                model, metrics = self.train_model(X, y, model_name=f"VELO_iter{self.iteration}")
                
                # 5. Save if best
                if metrics['auc'] > self.best_auc:
                    self.best_auc = metrics['auc']
                    self.save_model(model, metrics, f"VELO_BEST")
                    logger.info(f"🏆 NEW BEST MODEL! AUC: {self.best_auc:.4f}")
                
                # 6. Log iteration
                self.training_log.append({
                    "iteration": self.iteration,
                    "timestamp": datetime.now().isoformat(),
                    "samples": len(df),
                    "features": len(features),
                    "metrics": metrics,
                    "duration_seconds": time.time() - iteration_start
                })
                
                # 7. Save log
                log_path = self.models_dir / "training_log.json"
                with open(log_path, 'w') as f:
                    json.dump(self.training_log, f, indent=2)
                
                # 8. Wait before next iteration (10 minutes)
                wait_time = 600  # 10 minutes
                logger.info(f"Waiting {wait_time}s before next iteration...")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error in iteration {self.iteration}: {e}")
                time.sleep(60)
                continue
        
        logger.info("\n" + "="*60)
        logger.info("✅ CONTINUOUS TRAINING COMPLETE")
        logger.info(f"Total Iterations: {self.iteration}")
        logger.info(f"Best AUC: {self.best_auc:.4f}")
        logger.info("="*60)


if __name__ == "__main__":
    trainer = ContinuousTrainer(duration_hours=4)
    trainer.run()
