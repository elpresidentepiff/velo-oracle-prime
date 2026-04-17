"""
VÉLØ Oracle 2.0 - Enhanced Database Connector
==============================================

Provides both raw SQL (psycopg2) and ORM (SQLAlchemy) access to the database.
Supports all Oracle 2.0 tables including predictions, ML models, and betting ledger.

Author: VÉLØ Oracle Team
Version: 2.0.0
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from .models import (
    Base, RacingData, SectionalData, Racecard,
    BetfairMarket, BetfairOdds, ManipulationAlert,
    Prediction, ModelVersion, RaceAnalysis, LearnedPattern,
    BettingLedger
)

logger = logging.getLogger(__name__)


class VeloDatabase:
    """
    Enhanced database connector for VÉLØ Oracle 2.0.
    
    Provides both raw SQL and ORM access to all database tables.
    """
    
    def __init__(self, connection_string: str = None):
        """
        Initialize database connector.
        
        Args:
            connection_string: PostgreSQL connection string
                              (or from VELO_DB_CONNECTION env var)
        """
        # Get connection string
        if connection_string:
            self.connection_string = connection_string
        elif os.getenv('VELO_DB_CONNECTION'):
            self.connection_string = os.getenv('VELO_DB_CONNECTION')
        else:
            # Default local connection
            self.connection_string = "postgresql://postgres@localhost/velo_racing"
        
        # Parse for psycopg2
        self.psycopg2_config = self._parse_connection_string(self.connection_string)
        
        # SQLAlchemy engine and session
        self.engine = create_engine(
            self.connection_string,
            poolclass=NullPool,  # No connection pooling for simplicity
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Raw connection (psycopg2)
        self.conn = None
        
        logger.info(f"VeloDatabase initialized: {self.connection_string}")
    
    def _parse_connection_string(self, conn_str: str) -> Dict:
        """Parse PostgreSQL connection string for psycopg2."""
        # Simple parser for postgresql://user:pass@host:port/dbname
        if conn_str.startswith('postgresql://'):
            conn_str = conn_str.replace('postgresql://', '')
        
        config = {}
        
        # Extract user:pass@host:port/dbname
        if '@' in conn_str:
            auth, rest = conn_str.split('@', 1)
            if ':' in auth:
                config['user'], config['password'] = auth.split(':', 1)
            else:
                config['user'] = auth
            
            if '/' in rest:
                host_port, dbname = rest.split('/', 1)
                if ':' in host_port:
                    config['host'], port = host_port.split(':', 1)
                    config['port'] = int(port)
                else:
                    config['host'] = host_port
                config['dbname'] = dbname
            else:
                config['host'] = rest
        else:
            # Just dbname
            if '/' in conn_str:
                config['dbname'] = conn_str.split('/')[-1]
            else:
                config['dbname'] = conn_str
        
        # Set defaults
        if 'user' not in config:
            config['user'] = 'postgres'
        if 'dbname' not in config:
            config['dbname'] = 'velo_racing'
        
        return config
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    def connect(self):
        """Establish raw psycopg2 connection."""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**self.psycopg2_config)
        return self.conn
    
    def close(self):
        """Close raw psycopg2 connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Get SQLAlchemy session context manager.
        
        Usage:
            with db.get_session() as session:
                predictions = session.query(Prediction).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            session.close()
    
    def init_database(self):
        """Initialize database - create all tables."""
        logger.info("Creating database tables...")
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created successfully")
    
    # ========================================================================
    # RAW SQL QUERIES (for backward compatibility)
    # ========================================================================
    
    def query(self, sql: str, params: tuple = None) -> List[Dict]:
        """Execute raw SQL query and return results as list of dicts."""
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql, params or ())
        results = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in results]
    
    def execute(self, sql: str, params: tuple = None):
        """Execute raw SQL command (INSERT, UPDATE, DELETE)."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        cursor.close()
    
    # ========================================================================
    # HISTORICAL RACING DATA QUERIES
    # ========================================================================
    
    def get_horse_history(self, horse_name: str, limit: int = 10) -> List[Dict]:
        """Get recent race history for a horse."""
        sql = """
            SELECT date, course, race_name, type, dist, going, pos, 
                   ovr_btn, sp, jockey, trainer, official_rating, rpr, comment
            FROM racing_data
            WHERE horse = %s
            ORDER BY date DESC
            LIMIT %s
        """
        return self.query(sql, (horse_name, limit))
    
    def get_jockey_stats(self, jockey_name: str, days: int = 365) -> Dict:
        """Get jockey statistics for recent period."""
        sql = """
            SELECT 
                COUNT(*) as total_rides,
                SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) as places,
                ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct,
                ROUND(100.0 * SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) / COUNT(*), 2) as place_pct
            FROM racing_data
            WHERE jockey = %s
              AND date >= CURRENT_DATE - INTERVAL '%s days'
              AND pos ~ '^[0-9]+$'
        """
        results = self.query(sql, (jockey_name, days))
        return results[0] if results else {}
    
    def get_trainer_stats(self, trainer_name: str, days: int = 365) -> Dict:
        """Get trainer statistics for recent period."""
        sql = """
            SELECT 
                COUNT(*) as total_runners,
                SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) as places,
                ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct,
                ROUND(100.0 * SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) / COUNT(*), 2) as place_pct
            FROM racing_data
            WHERE trainer = %s
              AND date >= CURRENT_DATE - INTERVAL '%s days'
              AND pos ~ '^[0-9]+$'
        """
        results = self.query(sql, (trainer_name, days))
        return results[0] if results else {}
    
    # ========================================================================
    # ORACLE 2.0 - PREDICTIONS & ML
    # ========================================================================
    
    def save_prediction(self, prediction_data: Dict) -> int:
        """
        Save a prediction to the database.
        
        Args:
            prediction_data: Dict containing prediction fields
            
        Returns:
            Prediction ID
        """
        with self.get_session() as session:
            prediction = Prediction(**prediction_data)
            session.add(prediction)
            session.flush()
            return prediction.id
    
    def update_prediction_result(self, prediction_id: int, result_data: Dict):
        """
        Update prediction with actual race result.
        
        Args:
            prediction_id: Prediction ID
            result_data: Dict containing actual_position, actual_sp, result, profit_loss
        """
        with self.get_session() as session:
            prediction = session.query(Prediction).get(prediction_id)
            if prediction:
                for key, value in result_data.items():
                    setattr(prediction, key, value)
                prediction.updated_at = datetime.now()
    
    def get_predictions_for_race(self, race_id: str) -> List[Prediction]:
        """Get all predictions for a specific race."""
        with self.get_session() as session:
            return session.query(Prediction).filter_by(race_id=race_id).all()
    
    def get_active_model_version(self) -> Optional[ModelVersion]:
        """Get the currently active model version."""
        with self.get_session() as session:
            return session.query(ModelVersion).filter_by(is_active=True).first()
    
    # ========================================================================
    # ORACLE 2.0 - BETFAIR MARKET DATA
    # ========================================================================
    
    def save_betfair_market(self, market_data: Dict) -> int:
        """Save Betfair market information."""
        with self.get_session() as session:
            market = BetfairMarket(**market_data)
            session.add(market)
            session.flush()
            return market.id
    
    def save_betfair_odds_snapshot(self, odds_data: Dict):
        """Save Betfair odds snapshot."""
        with self.get_session() as session:
            odds = BetfairOdds(**odds_data)
            session.add(odds)
    
    def save_manipulation_alert(self, alert_data: Dict):
        """Save market manipulation alert."""
        with self.get_session() as session:
            alert = ManipulationAlert(**alert_data)
            session.add(alert)
    
    def get_market_odds_history(self, market_id: str) -> List[BetfairOdds]:
        """Get odds history for a market."""
        with self.get_session() as session:
            return session.query(BetfairOdds)\
                .filter_by(market_id=market_id)\
                .order_by(BetfairOdds.snapshot_time)\
                .all()
    
    # ========================================================================
    # ORACLE 2.0 - GENESIS PROTOCOL (LEARNING)
    # ========================================================================
    
    def save_race_analysis(self, analysis_data: Dict) -> int:
        """Save post-race analysis."""
        with self.get_session() as session:
            analysis = RaceAnalysis(**analysis_data)
            session.add(analysis)
            session.flush()
            return analysis.id
    
    def get_learned_patterns(self, pattern_type: str = None, active_only: bool = True) -> List[LearnedPattern]:
        """Get learned patterns."""
        with self.get_session() as session:
            query = session.query(LearnedPattern)
            
            if pattern_type:
                query = query.filter_by(pattern_type=pattern_type)
            
            if active_only:
                query = query.filter_by(is_active=True)
            
            return query.all()
    
    def update_pattern_performance(self, pattern_name: str, success: bool, roi: float):
        """Update pattern performance metrics."""
        with self.get_session() as session:
            pattern = session.query(LearnedPattern).filter_by(pattern_name=pattern_name).first()
            
            if pattern:
                pattern.occurrences += 1
                if success:
                    pattern.successful_predictions += 1
                
                pattern.success_rate = (pattern.successful_predictions / pattern.occurrences) * 100
                pattern.avg_roi = ((pattern.avg_roi * (pattern.occurrences - 1)) + roi) / pattern.occurrences
                pattern.last_observed = datetime.now()
                pattern.updated_at = datetime.now()
    
    # ========================================================================
    # ORACLE 2.0 - BETTING LEDGER
    # ========================================================================
    
    def save_bet(self, bet_data: Dict) -> int:
        """Save a bet to the ledger."""
        with self.get_session() as session:
            bet = BettingLedger(**bet_data)
            session.add(bet)
            session.flush()
            return bet.id
    
    def update_bet_result(self, bet_id: int, result_data: Dict):
        """Update bet with settlement result."""
        with self.get_session() as session:
            bet = session.query(BettingLedger).get(bet_id)
            if bet:
                for key, value in result_data.items():
                    setattr(bet, key, value)
                bet.settled_at = datetime.now()
    
    def get_betting_performance(self, days: int = 30) -> Dict:
        """Get betting performance summary."""
        sql = """
            SELECT 
                COUNT(*) as total_bets,
                SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result IN ('WON', 'PLACED') THEN 1 ELSE 0 END) as places,
                ROUND(100.0 * SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate,
                SUM(stake) as total_staked,
                SUM(returns) as total_returns,
                SUM(profit_loss) as net_profit,
                ROUND(100.0 * SUM(profit_loss) / NULLIF(SUM(stake), 0), 2) as roi
            FROM betting_ledger
            WHERE result IS NOT NULL
              AND date >= CURRENT_DATE - INTERVAL '%s days'
        """
        results = self.query(sql, (days,))
        return results[0] if results else {}
    
    def get_current_bankroll(self) -> float:
        """Get current bankroll from latest bet."""
        sql = """
            SELECT bankroll_after
            FROM betting_ledger
            ORDER BY placed_at DESC
            LIMIT 1
        """
        results = self.query(sql)
        return float(results[0]['bankroll_after']) if results else 0.0
    
    # ========================================================================
    # STATISTICS & ANALYTICS
    # ========================================================================
    
    def get_database_stats(self) -> Dict:
        """Get overall database statistics."""
        sql = """
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT race_id) as total_races,
                COUNT(DISTINCT horse) as unique_horses,
                COUNT(DISTINCT jockey) as unique_jockeys,
                COUNT(DISTINCT trainer) as unique_trainers,
                COUNT(DISTINCT course) as unique_courses,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM racing_data
        """
        results = self.query(sql)
        return results[0] if results else {}


# Singleton instance
_db_instance = None

def get_database() -> VeloDatabase:
    """Get singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = VeloDatabase()
    return _db_instance


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    db = VeloDatabase()
    
    print("🔮 VÉLØ Oracle 2.0 Database Connector\n")
    print("="*60)
    
    # Initialize database (create tables)
    db.init_database()
    print("✓ Database initialized")
    
    # Get stats
    stats = db.get_database_stats()
    print(f"\n📊 Database Statistics:")
    print(f"Total races: {stats.get('total_races', 0):,}")
    print(f"Unique horses: {stats.get('unique_horses', 0):,}")
    print(f"Date range: {stats.get('earliest_date', 'N/A')} to {stats.get('latest_date', 'N/A')}")
    
    # Test ORM
    with db.get_session() as session:
        prediction_count = session.query(Prediction).count()
        model_count = session.query(ModelVersion).count()
        print(f"\n🤖 ML Data:")
        print(f"Predictions: {prediction_count}")
        print(f"Model versions: {model_count}")
    
    print("\n" + "="*60)
    print("✅ Database connector ready!\n")

