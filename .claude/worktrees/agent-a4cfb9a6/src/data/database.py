"""
VÉLØ Database Connector
Provides access to historical racing data
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class VeloDatabase:
    """Database connector for VÉLØ Oracle"""
    
    def __init__(self):
        self.config = {
            'dbname': 'velo_racing',
            'user': 'postgres'
        }
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        if not self.conn or self.conn.closed:
            self.conn = psycopg2.connect(**self.config)
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()
    
    def query(self, sql: str, params: tuple = None) -> List[Dict]:
        """Execute query and return results as list of dicts"""
        conn = self.connect()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql, params or ())
        results = cursor.fetchall()
        cursor.close()
        return [dict(row) for row in results]
    
    def get_horse_history(self, horse_name: str, limit: int = 10) -> List[Dict]:
        """Get recent race history for a horse"""
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
        """Get jockey statistics for recent period"""
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
        """Get trainer statistics for recent period"""
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
    
    def get_course_stats(self, course_name: str) -> Dict:
        """Get course statistics"""
        sql = """
            SELECT 
                COUNT(DISTINCT race_id) as total_races,
                COUNT(*) as total_runners,
                MIN(date) as first_race,
                MAX(date) as last_race
            FROM racing_data
            WHERE course = %s
        """
        results = self.query(sql, (course_name,))
        return results[0] if results else {}
    
    def get_jockey_at_course(self, jockey_name: str, course_name: str, days: int = 730) -> Dict:
        """Get jockey performance at specific course"""
        sql = """
            SELECT 
                COUNT(*) as rides,
                SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
                ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct
            FROM racing_data
            WHERE jockey = %s
              AND course = %s
              AND date >= CURRENT_DATE - INTERVAL '%s days'
              AND pos ~ '^[0-9]+$'
        """
        results = self.query(sql, (jockey_name, course_name, days))
        return results[0] if results else {}
    
    def get_trainer_at_course(self, trainer_name: str, course_name: str, days: int = 730) -> Dict:
        """Get trainer performance at specific course"""
        sql = """
            SELECT 
                COUNT(*) as runners,
                SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
                ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct
            FROM racing_data
            WHERE trainer = %s
              AND course = %s
              AND date >= CURRENT_DATE - INTERVAL '%s days'
              AND pos ~ '^[0-9]+$'
        """
        results = self.query(sql, (trainer_name, course_name, days))
        return results[0] if results else {}
    
    def get_horse_at_distance(self, horse_name: str, distance: str) -> Dict:
        """Get horse performance at specific distance"""
        sql = """
            SELECT 
                COUNT(*) as runs,
                SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) as places,
                ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct
            FROM racing_data
            WHERE horse = %s
              AND dist = %s
              AND pos ~ '^[0-9]+$'
        """
        results = self.query(sql, (horse_name, distance))
        return results[0] if results else {}
    
    def get_horse_on_going(self, horse_name: str, going: str) -> Dict:
        """Get horse performance on specific going"""
        sql = """
            SELECT 
                COUNT(*) as runs,
                SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pos IN ('1','2','3') THEN 1 ELSE 0 END) as places,
                ROUND(100.0 * SUM(CASE WHEN pos = '1' THEN 1 ELSE 0 END) / COUNT(*), 2) as win_pct
            FROM racing_data
            WHERE horse = %s
              AND going ILIKE %s
              AND pos ~ '^[0-9]+$'
        """
        results = self.query(sql, (horse_name, f'%{going}%'))
        return results[0] if results else {}
    
    def get_similar_races(self, course: str, distance: str, race_type: str, limit: int = 20) -> List[Dict]:
        """Find similar historical races"""
        sql = """
            SELECT DISTINCT ON (race_id)
                race_id, date, race_name, going, ran,
                (SELECT horse FROM racing_data r2 WHERE r2.race_id = r1.race_id AND r2.pos = '1' LIMIT 1) as winner,
                (SELECT sp FROM racing_data r2 WHERE r2.race_id = r1.race_id AND r2.pos = '1' LIMIT 1) as winner_sp
            FROM racing_data r1
            WHERE course = %s
              AND dist = %s
              AND type = %s
              AND date >= CURRENT_DATE - INTERVAL '2 years'
            ORDER BY race_id, date DESC
            LIMIT %s
        """
        return self.query(sql, (course, distance, race_type, limit))
    
    def get_database_stats(self) -> Dict:
        """Get overall database statistics"""
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


# Test the database connection
if __name__ == "__main__":
    db = VeloDatabase()
    
    print("🔮 VÉLØ Database Connector Test\n")
    print("="*60)
    
    # Get database stats
    stats = db.get_database_stats()
    print("\nDATABASE STATISTICS:")
    print(f"Total rows: {stats['total_rows']:,}")
    print(f"Total races: {stats['total_races']:,}")
    print(f"Unique horses: {stats['unique_horses']:,}")
    print(f"Unique jockeys: {stats['unique_jockeys']:,}")
    print(f"Unique trainers: {stats['unique_trainers']:,}")
    print(f"Unique courses: {stats['unique_courses']:,}")
    print(f"Date range: {stats['earliest_date']} to {stats['latest_date']}")
    
    # Test horse query
    print("\n" + "="*60)
    print("\nTEST: Horse History (Captain Ryan Matt)")
    history = db.get_horse_history("Captain Ryan Matt", limit=5)
    for i, race in enumerate(history, 1):
        print(f"\n{i}. {race['date']} - {race['course']}")
        print(f"   Position: {race['pos']} | SP: {race['sp']} | Going: {race['going']}")
    
    # Test jockey stats
    print("\n" + "="*60)
    print("\nTEST: Jockey Stats (Darragh O'Keeffe)")
    jockey_stats = db.get_jockey_stats("Darragh O'Keeffe", days=365)
    if jockey_stats:
        print(f"Total rides: {jockey_stats.get('total_rides', 0)}")
        print(f"Wins: {jockey_stats.get('wins', 0)}")
        print(f"Win %: {jockey_stats.get('win_pct', 0)}%")
    
    db.close()
    print("\n" + "="*60)
    print("✅ Database connector working!\n")

