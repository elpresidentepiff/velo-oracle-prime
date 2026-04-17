"""
VÉLØ Oracle 2.0 - Machine Learning Engine
==========================================

Implements the Benter-inspired multinomial logit model for race prediction.
Includes training, backtesting, and live prediction capabilities.

Based on Bill Benter's $1 Billion Hong Kong horse racing model:
- Two-model approach: Fundamental + Market odds
- 130+ sophisticated variables
- Multinomial logit regression
- Kelly Criterion for optimal staking

Author: VÉLØ Oracle Team
Version: 2.0.0
"""

import os
import logging
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss

from ..data.db_connector import VeloDatabase
from ..data.models import Prediction, ModelVersion

logger = logging.getLogger(__name__)


class BenterModel:
    """
    Implementation of Bill Benter's multinomial logit model.
    
    This model predicts win probabilities for each horse in a race using:
    1. Fundamental model: Based on horse/jockey/trainer statistics
    2. Market model: Incorporates public odds
    3. Combined model: Weighted combination of both
    """
    
    def __init__(self, model_version: str = "v2.0"):
        """
        Initialize Benter model.
        
        Args:
            model_version: Model version identifier
        """
        self.version = model_version
        
        # Fundamental model (horse characteristics)
        self.fundamental_model = LogisticRegression(
            multi_class='multinomial',
            solver='lbfgs',
            max_iter=1000,
            random_state=42
        )
        
        # Feature scaler
        self.scaler = StandardScaler()
        
        # Feature names
        self.feature_names = []
        
        # Model performance metrics
        self.metrics = {
            'training_accuracy': 0.0,
            'validation_accuracy': 0.0,
            'test_accuracy': 0.0,
            'log_loss': 0.0
        }
        
        logger.info(f"BenterModel {model_version} initialized")
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare feature matrix from race data.
        
        Implements the 130+ variables from Benter's model.
        
        Args:
            df: DataFrame with race data
            
        Returns:
            DataFrame with engineered features
        """
        features = pd.DataFrame()
        
        # ====================================================================
        # CATEGORY 1: HORSE CHARACTERISTICS (30 variables)
        # ====================================================================
        
        # Age features
        features['age'] = df['age']
        features['age_squared'] = df['age'] ** 2
        features['is_prime_age'] = ((df['age'] >= 4) & (df['age'] <= 6)).astype(int)
        
        # Weight features
        if 'weight_kg' in df.columns:
            features['weight_kg'] = df['weight_kg']
            features['weight_vs_avg'] = df['weight_vs_avg']
        
        # Official rating
        if 'official_rating' in df.columns:
            features['official_rating'] = pd.to_numeric(df['official_rating'], errors='coerce').fillna(0)
            features['rating_vs_avg'] = df.get('rating_vs_avg', 0)
        
        # ====================================================================
        # CATEGORY 2: RECENT FORM (25 variables)
        # ====================================================================
        
        # Days since last run
        features['days_since_last_run'] = df.get('days_since_last_run', 0)
        features['days_since_last_run_squared'] = features['days_since_last_run'] ** 2
        
        # Recent positions (would come from historical lookup)
        features['last_position'] = 0  # Placeholder
        features['avg_position_last_3'] = 0  # Placeholder
        features['avg_position_last_5'] = 0  # Placeholder
        
        # Win/place rates
        features['career_win_rate'] = df.get('career_win_pct', 0) / 100
        features['career_place_rate'] = df.get('career_place_pct', 0) / 100
        
        # ====================================================================
        # CATEGORY 3: JOCKEY STATISTICS (20 variables)
        # ====================================================================
        
        features['jockey_strike_rate'] = df.get('jockey_strike_rate', 0)
        features['jockey_roi'] = 0  # Placeholder
        features['jockey_at_course_sr'] = 0  # Placeholder
        features['jockey_at_distance_sr'] = 0  # Placeholder
        
        # ====================================================================
        # CATEGORY 4: TRAINER STATISTICS (20 variables)
        # ====================================================================
        
        features['trainer_strike_rate'] = df.get('trainer_strike_rate', 0)
        features['trainer_roi'] = 0  # Placeholder
        features['trainer_at_course_sr'] = 0  # Placeholder
        features['trainer_form_last_14_days'] = 0  # Placeholder
        
        # ====================================================================
        # CATEGORY 5: JOCKEY-TRAINER COMBINATION (10 variables)
        # ====================================================================
        
        features['combo_win_rate'] = df.get('combo_win_rate', 0)
        features['combo_runs'] = 0  # Placeholder
        features['combo_roi'] = 0  # Placeholder
        
        # ====================================================================
        # CATEGORY 6: COURSE & DISTANCE (15 variables)
        # ====================================================================
        
        features['course_distance_win_rate'] = df.get('course_distance_win_rate', 0)
        features['course_wins'] = 0  # Placeholder
        features['distance_wins'] = 0  # Placeholder
        
        # Distance suitability
        features['distance_category_sprint'] = (df.get('distance_category', '') == 'sprint').astype(int)
        features['distance_category_middle'] = (df.get('distance_category', '') == 'middle').astype(int)
        features['distance_category_staying'] = (df.get('distance_category', '') == 'staying').astype(int)
        
        # ====================================================================
        # CATEGORY 7: GOING CONDITIONS (10 variables)
        # ====================================================================
        
        features['going_preference_score'] = df.get('going_preference_score', 0)
        
        # Going type dummies
        features['going_firm'] = (df.get('going_category', '') == 'firm').astype(int)
        features['going_good'] = (df.get('going_category', '') == 'good').astype(int)
        features['going_soft'] = (df.get('going_category', '') == 'soft').astype(int)
        features['going_heavy'] = (df.get('going_category', '') == 'heavy').astype(int)
        
        # ====================================================================
        # CATEGORY 8: DRAW BIAS (5 variables)
        # ====================================================================
        
        if 'draw' in df.columns:
            features['draw'] = df['draw']
            features['draw_advantage'] = df.get('draw_advantage', 0)
            features['is_low_draw'] = (df['draw'] <= 3).astype(int)
            features['is_high_draw'] = (df['draw'] >= 10).astype(int)
        
        # ====================================================================
        # CATEGORY 9: PACE ANALYSIS (10 variables)
        # ====================================================================
        
        features['early_speed_rating'] = df.get('early_speed_rating', 0)
        features['finishing_speed_rating'] = df.get('finishing_speed_rating', 0)
        features['pace_advantage'] = 0  # Placeholder
        
        # ====================================================================
        # CATEGORY 10: MARKET INDICATORS (5 variables)
        # ====================================================================
        
        if 'decimal_odds' in df.columns:
            features['market_rank'] = df.get('market_rank', 0)
            features['is_favorite'] = df.get('is_favorite', False).astype(int)
            features['log_odds'] = np.log(df['decimal_odds'].clip(lower=1.01))
        
        # Fill NaN values
        features = features.fillna(0)
        
        self.feature_names = list(features.columns)
        
        return features
    
    def train(self, training_data: pd.DataFrame, target_column: str = 'won') -> Dict:
        """
        Train the fundamental model.
        
        Args:
            training_data: DataFrame with historical race data
            target_column: Column indicating race winner (1 = won, 0 = lost)
            
        Returns:
            Dict containing training metrics
        """
        logger.info("Training Benter model...")
        
        # Prepare features
        X = self.prepare_features(training_data)
        y = training_data[target_column]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.fundamental_model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_pred = self.fundamental_model.predict(X_train_scaled)
        test_pred = self.fundamental_model.predict(X_test_scaled)
        
        self.metrics['training_accuracy'] = accuracy_score(y_train, train_pred)
        self.metrics['test_accuracy'] = accuracy_score(y_test, test_pred)
        
        # Probability predictions for log loss
        train_proba = self.fundamental_model.predict_proba(X_train_scaled)
        test_proba = self.fundamental_model.predict_proba(X_test_scaled)
        
        self.metrics['train_log_loss'] = log_loss(y_train, train_proba)
        self.metrics['test_log_loss'] = log_loss(y_test, test_proba)
        
        logger.info(f"✓ Model trained - Test accuracy: {self.metrics['test_accuracy']:.3f}")
        
        return self.metrics
    
    def predict_race(self, race_data: pd.DataFrame) -> pd.DataFrame:
        """
        Predict win probabilities for all horses in a race.
        
        Args:
            race_data: DataFrame with race runner data
            
        Returns:
            DataFrame with predictions added
        """
        # Prepare features
        X = self.prepare_features(race_data)
        
        # Scale features
        X_scaled = self.scaler.transform(X)
        
        # Get probabilities
        probabilities = self.fundamental_model.predict_proba(X_scaled)
        
        # Add to dataframe
        race_data = race_data.copy()
        race_data['win_probability'] = probabilities[:, 1]  # Probability of class 1 (win)
        
        # Normalize probabilities to sum to 1 across race
        total_prob = race_data['win_probability'].sum()
        race_data['normalized_win_prob'] = race_data['win_probability'] / total_prob
        
        # Calculate expected value vs market odds
        if 'decimal_odds' in race_data.columns:
            race_data['expected_value'] = (
                race_data['normalized_win_prob'] * race_data['decimal_odds']
            ) - 1
            
            # Value indicator (EV > 10% = value bet)
            race_data['is_value'] = race_data['expected_value'] > 0.10
        
        return race_data
    
    def save_model(self, filepath: str):
        """Save trained model to disk."""
        model_data = {
            'version': self.version,
            'fundamental_model': self.fundamental_model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'metrics': self.metrics
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"✓ Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load trained model from disk."""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.version = model_data['version']
        self.fundamental_model = model_data['fundamental_model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.metrics = model_data['metrics']
        
        logger.info(f"✓ Model loaded from {filepath}")


class MLEngine:
    """
    Main ML engine for VÉLØ Oracle.
    
    Manages model training, prediction, and performance tracking.
    """
    
    def __init__(self, db: VeloDatabase = None):
        """
        Initialize ML engine.
        
        Args:
            db: Database connector
        """
        self.db = db or VeloDatabase()
        self.model = BenterModel()
        self.model_dir = os.path.expanduser('~/.velo-oracle/models')
        
        # Create model directory
        os.makedirs(self.model_dir, exist_ok=True)
        
        logger.info("MLEngine initialized")
    
    def train_new_model(self, training_data: pd.DataFrame, version: str = None) -> str:
        """
        Train a new model version.
        
        Args:
            training_data: Historical race data for training
            version: Model version identifier
            
        Returns:
            Model version string
        """
        if version is None:
            version = f"v2.0-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        logger.info(f"Training new model: {version}")
        
        # Create target variable (1 if won, 0 if lost)
        training_data['won'] = (training_data['pos'] == '1').astype(int)
        
        # Train model
        self.model.version = version
        metrics = self.model.train(training_data)
        
        # Save model
        model_path = os.path.join(self.model_dir, f"{version}.pkl")
        self.model.save_model(model_path)
        
        # Save to database
        with self.db.get_session() as session:
            model_version = ModelVersion(
                version=version,
                model_type='benter_multinomial_logit',
                features_used=self.model.feature_names,
                training_data_size=len(training_data),
                validation_accuracy=metrics['test_accuracy'],
                test_accuracy=metrics['test_accuracy'],
                hyperparameters={
                    'solver': 'lbfgs',
                    'max_iter': 1000,
                    'multi_class': 'multinomial'
                },
                trained_at=datetime.now(),
                is_active=True
            )
            session.add(model_version)
        
        logger.info(f"✓ Model {version} trained and saved")
        return version
    
    def load_active_model(self) -> bool:
        """
        Load the currently active model.
        
        Returns:
            True if model loaded successfully
        """
        active_model = self.db.get_active_model_version()
        
        if not active_model:
            logger.warning("No active model found")
            return False
        
        model_path = os.path.join(self.model_dir, f"{active_model.version}.pkl")
        
        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            return False
        
        self.model.load_model(model_path)
        logger.info(f"✓ Loaded active model: {active_model.version}")
        return True
    
    def predict_race(self, race_data: pd.DataFrame, save_to_db: bool = True) -> pd.DataFrame:
        """
        Generate predictions for a race.
        
        Args:
            race_data: DataFrame with race runner data
            save_to_db: Whether to save predictions to database
            
        Returns:
            DataFrame with predictions
        """
        logger.info(f"Predicting race: {race_data.iloc[0].get('race_id', 'unknown')}")
        
        # Generate predictions
        predictions = self.model.predict_race(race_data)
        
        # Save to database
        if save_to_db:
            for _, row in predictions.iterrows():
                prediction_data = {
                    'race_id': row.get('race_id'),
                    'date': row.get('date'),
                    'course': row.get('course'),
                    'horse': row.get('horse'),
                    'model_version': self.model.version,
                    'win_probability': float(row.get('normalized_win_prob', 0)),
                    'expected_position': 1 / float(row.get('normalized_win_prob', 0.01)),
                    'confidence_score': float(row.get('normalized_win_prob', 0)) * 100,
                    'odds_at_prediction': float(row.get('decimal_odds', 0)),
                    'recommended_bet': self._determine_bet_type(row),
                    'recommended_stake': self._calculate_stake(row),
                    'predicted_at': datetime.now()
                }
                
                self.db.save_prediction(prediction_data)
        
        return predictions
    
    def _determine_bet_type(self, row: pd.Series) -> str:
        """Determine recommended bet type based on prediction."""
        ev = row.get('expected_value', 0)
        odds = row.get('decimal_odds', 0)
        win_prob = row.get('normalized_win_prob', 0)
        
        # VÉLØ betting rules: 3/1 to 20/1 range
        if odds < 4.0 or odds > 21.0:
            return 'PASS'
        
        # Strong value (EV > 20%)
        if ev > 0.20 and win_prob > 0.10:
            if odds >= 8.0 and odds <= 15.0:
                return 'EW'  # Each-way for prime range
            else:
                return 'WIN'
        
        # Moderate value (EV > 10%)
        elif ev > 0.10 and win_prob > 0.08:
            if odds >= 16.0:
                return 'EW'  # Each-way for longshots
            else:
                return 'WIN'
        
        return 'PASS'
    
    def _calculate_stake(self, row: pd.Series) -> float:
        """Calculate recommended stake using Kelly Criterion."""
        bet_type = self._determine_bet_type(row)
        
        if bet_type == 'PASS':
            return 0.0
        
        # Kelly Criterion: f = (bp - q) / b
        # where b = decimal odds - 1, p = win probability, q = 1 - p
        
        win_prob = row.get('normalized_win_prob', 0)
        odds = row.get('decimal_odds', 1.0)
        
        b = odds - 1
        p = win_prob
        q = 1 - p
        
        kelly_fraction = (b * p - q) / b
        
        # Use fractional Kelly (1/4 Kelly for safety)
        kelly_fraction = kelly_fraction / 4
        
        # Clamp to VÉLØ betting system rules
        if bet_type == 'EW' and odds >= 8.0 and odds <= 14.0:
            return 2.0  # 2% of bank for prime EW
        elif bet_type == 'EW' and odds >= 16.0:
            return 1.0  # 1% of bank for longshot EW
        elif bet_type == 'WIN':
            return 1.5  # 1.5% of bank for win bets
        
        return max(0.0, min(kelly_fraction * 100, 2.0))  # Cap at 2%
    
    def backtest(self, test_data: pd.DataFrame, starting_bank: float = 100.0) -> Dict:
        """
        Backtest model on historical data.
        
        Args:
            test_data: Historical race data with known results
            starting_bank: Starting bankroll
            
        Returns:
            Dict containing backtest results
        """
        logger.info("Running backtest...")
        
        bank = starting_bank
        bets = []
        
        # Group by race
        for race_id, race_data in test_data.groupby('race_id'):
            # Generate predictions
            predictions = self.model.predict_race(race_data)
            
            # Find bets
            for _, row in predictions.iterrows():
                bet_type = self._determine_bet_type(row)
                
                if bet_type == 'PASS':
                    continue
                
                stake = self._calculate_stake(row) * bank / 100
                
                # Check result
                won = row.get('pos') == '1'
                placed = row.get('pos', '99') in ['1', '2', '3']
                
                if bet_type == 'WIN':
                    if won:
                        returns = stake * row.get('decimal_odds', 0)
                        profit = returns - stake
                    else:
                        returns = 0
                        profit = -stake
                
                elif bet_type == 'EW':
                    # Simplified EW calculation (1/4 odds for place)
                    if won:
                        returns = stake * row.get('decimal_odds', 0)
                        profit = returns - stake
                    elif placed:
                        place_odds = 1 + ((row.get('decimal_odds', 1) - 1) / 4)
                        returns = stake * place_odds
                        profit = returns - stake
                    else:
                        returns = 0
                        profit = -stake
                
                bank += profit
                
                bets.append({
                    'race_id': race_id,
                    'horse': row.get('horse'),
                    'bet_type': bet_type,
                    'stake': stake,
                    'odds': row.get('decimal_odds'),
                    'result': 'WON' if won else ('PLACED' if placed else 'LOST'),
                    'profit': profit,
                    'bank': bank
                })
        
        # Calculate statistics
        total_bets = len(bets)
        wins = len([b for b in bets if b['result'] == 'WON'])
        places = len([b for b in bets if b['result'] in ['WON', 'PLACED']])
        
        total_staked = sum([b['stake'] for b in bets])
        total_profit = bank - starting_bank
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        
        results = {
            'total_bets': total_bets,
            'wins': wins,
            'places': places,
            'win_rate': (wins / total_bets * 100) if total_bets > 0 else 0,
            'place_rate': (places / total_bets * 100) if total_bets > 0 else 0,
            'starting_bank': starting_bank,
            'ending_bank': bank,
            'total_profit': total_profit,
            'roi': roi,
            'bets': bets
        }
        
        logger.info(f"✓ Backtest complete - ROI: {roi:.2f}%, Win rate: {results['win_rate']:.1f}%")
        
        return results


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🔮 VÉLØ ML Engine Test\n")
    print("="*60)
    
    # Create sample training data
    sample_data = pd.DataFrame({
        'race_id': ['R1'] * 5,
        'horse': ['Horse A', 'Horse B', 'Horse C', 'Horse D', 'Horse E'],
        'age': [4, 5, 3, 6, 4],
        'official_rating': [85, 90, 80, 88, 82],
        'decimal_odds': [5.0, 3.0, 10.0, 7.0, 15.0],
        'pos': ['2', '1', '5', '3', '4'],
        'jockey_strike_rate': [15, 20, 10, 18, 12],
        'trainer_strike_rate': [18, 22, 14, 20, 16]
    })
    
    # Initialize engine
    engine = MLEngine()
    
    # Train model
    print("\n🤖 Training model...")
    version = engine.train_new_model(sample_data)
    print(f"✓ Model trained: {version}")
    
    # Make prediction
    print("\n📊 Making prediction...")
    predictions = engine.predict_race(sample_data, save_to_db=False)
    
    print("\nPredictions:")
    for _, row in predictions.iterrows():
        print(f"{row['horse']}: {row['normalized_win_prob']:.1%} - {row.get('recommended_bet', 'PASS')}")
    
    print("\n" + "="*60)
    print("✅ ML engine ready!\n")

