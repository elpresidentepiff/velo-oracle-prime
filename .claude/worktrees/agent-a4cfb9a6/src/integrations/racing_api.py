"""
VÉLØ Oracle 2.0 - The Racing API Integration
=============================================

This module provides access to historical racing data from The Racing API,
which contains 500,000+ historical races with comprehensive statistics.

The Racing API gives us:
1. Historical race results (20+ years of data)
2. Horse performance history
3. Jockey and trainer statistics
4. Course and distance records
5. Sectional times and pace data
6. Breeding and pedigree information

This is the foundation for pattern recognition and ML training.

Author: VÉLØ Oracle Team
Version: 2.0.0
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from pathlib import Path

logger = logging.getLogger(__name__)


class RacingAPIClient:
    """
    Client for The Racing API - historical racing data provider.
    
    This client provides access to comprehensive historical racing data
    for pattern analysis, ML training, and statistical modeling.
    """
    
    # The Racing API endpoint (placeholder - actual endpoint from subscription)
    API_ENDPOINT = "https://api.theracingapi.com/v1"
    
    def __init__(self, api_key: str = None, cache_dir: str = None):
        """
        Initialize Racing API client.
        
        Args:
            api_key: The Racing API key (or from RACING_API_KEY env var)
            cache_dir: Directory for caching API responses
        """
        self.api_key = api_key or os.getenv('RACING_API_KEY')
        self.cache_dir = cache_dir or os.path.expanduser('~/.velo-oracle/racing_api_cache')
        
        # Create cache directory
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms between requests
        
        logger.info(f"RacingAPIClient initialized with cache at {self.cache_dir}")
    
    def _rate_limit(self):
        """Enforce rate limiting between API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        # Create safe filename from cache key
        safe_key = cache_key.replace('/', '_').replace(':', '_')
        return Path(self.cache_dir) / f"{safe_key}.json"
    
    def _get_from_cache(self, cache_key: str, max_age_hours: int = 24) -> Optional[Dict]:
        """
        Retrieve data from cache if available and not expired.
        
        Args:
            cache_key: Unique identifier for cached data
            max_age_hours: Maximum age of cache in hours
            
        Returns:
            Cached data or None if not available/expired
        """
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        # Check cache age
        cache_age = time.time() - cache_path.stat().st_mtime
        if cache_age > (max_age_hours * 3600):
            logger.debug(f"Cache expired for {cache_key}")
            return None
        
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
                logger.debug(f"Cache hit for {cache_key}")
                return data
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: Dict):
        """Save data to cache."""
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Cached data for {cache_key}")
        except Exception as e:
            logger.error(f"Error writing cache: {e}")
    
    def _call_api(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Make an API call to The Racing API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            API response dict or None on error
        """
        if not self.api_key:
            logger.error("Missing Racing API key. Set RACING_API_KEY environment variable")
            return None
        
        # Check cache first
        cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        # Rate limit
        self._rate_limit()
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.API_ENDPOINT}/{endpoint}"
            
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                # Cache successful response
                self._save_to_cache(cache_key, data)
                return data
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded, waiting...")
                time.sleep(5)
                return self._call_api(endpoint, params)  # Retry
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"API call exception: {e}")
            return None
    
    def get_race_results(self, date: str, country: str = 'GB') -> List[Dict]:
        """
        Get race results for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            country: Country code (GB, IE, etc.)
            
        Returns:
            List of race result dictionaries
        """
        params = {
            'date': date,
            'country': country
        }
        
        result = self._call_api('races/results', params)
        return result.get('races', []) if result else []
    
    def get_horse_history(self, horse_name: str, limit: int = 20) -> List[Dict]:
        """
        Get performance history for a specific horse.
        
        Args:
            horse_name: Name of the horse
            limit: Maximum number of results
            
        Returns:
            List of race performances
        """
        params = {
            'horse': horse_name,
            'limit': limit
        }
        
        result = self._call_api('horses/history', params)
        return result.get('performances', []) if result else []
    
    def get_jockey_stats(self, jockey_name: str, days: int = 365) -> Dict:
        """
        Get statistics for a specific jockey.
        
        Args:
            jockey_name: Name of the jockey
            days: Number of days to analyze
            
        Returns:
            Dict containing jockey statistics
        """
        params = {
            'jockey': jockey_name,
            'days': days
        }
        
        result = self._call_api('jockeys/stats', params)
        return result if result else {}
    
    def get_trainer_stats(self, trainer_name: str, days: int = 365) -> Dict:
        """
        Get statistics for a specific trainer.
        
        Args:
            trainer_name: Name of the trainer
            days: Number of days to analyze
            
        Returns:
            Dict containing trainer statistics
        """
        params = {
            'trainer': trainer_name,
            'days': days
        }
        
        result = self._call_api('trainers/stats', params)
        return result if result else {}
    
    def get_course_stats(self, course_name: str, distance: int = None) -> Dict:
        """
        Get statistics for a specific course.
        
        Args:
            course_name: Name of the course
            distance: Optional distance filter in meters
            
        Returns:
            Dict containing course statistics including draw bias, pace bias, etc.
        """
        params = {
            'course': course_name
        }
        
        if distance:
            params['distance'] = distance
        
        result = self._call_api('courses/stats', params)
        return result if result else {}
    
    def search_historical_patterns(self, filters: Dict) -> List[Dict]:
        """
        Search for historical race patterns matching specific criteria.
        
        This is powerful for finding similar races to current conditions.
        
        Args:
            filters: Dict containing search criteria:
                - course: Course name
                - distance: Distance in meters
                - going: Ground conditions
                - class: Race class
                - age_range: Age restrictions
                - date_from: Start date
                - date_to: End date
                
        Returns:
            List of matching historical races
        """
        result = self._call_api('races/search', filters)
        return result.get('races', []) if result else []
    
    def get_sectional_data(self, race_id: str) -> Optional[Dict]:
        """
        Get sectional timing data for a specific race.
        
        Sectional data is crucial for pace analysis and understanding
        how races were run.
        
        Args:
            race_id: Unique race identifier
            
        Returns:
            Dict containing sectional times for each runner
        """
        result = self._call_api(f'races/{race_id}/sectionals')
        return result if result else None
    
    def get_breeding_info(self, horse_name: str) -> Dict:
        """
        Get breeding and pedigree information for a horse.
        
        Args:
            horse_name: Name of the horse
            
        Returns:
            Dict containing sire, dam, and pedigree information
        """
        params = {'horse': horse_name}
        result = self._call_api('horses/breeding', params)
        return result if result else {}


class RacingDataAnalyzer:
    """
    Analyzes historical racing data to identify patterns and trends.
    
    This is the "memory" of VÉLØ - learning from 500,000+ historical races
    to understand what patterns lead to success.
    """
    
    def __init__(self, client: RacingAPIClient):
        self.client = client
        logger.info("RacingDataAnalyzer initialized")
    
    def analyze_horse_form(self, horse_name: str) -> Dict:
        """
        Comprehensive form analysis for a horse.
        
        Returns:
            Dict containing:
            - recent_form: Last 5 runs analysis
            - course_record: Performance at specific courses
            - distance_record: Performance at specific distances
            - going_preference: Preferred ground conditions
            - class_performance: Performance by race class
            - trend: Improving/declining/stable
        """
        history = self.client.get_horse_history(horse_name, limit=20)
        
        if not history:
            return {
                'error': 'No historical data available',
                'recent_form': [],
                'trend': 'unknown'
            }
        
        # Recent form (last 5 runs)
        recent_form = history[:5]
        recent_positions = [r.get('position', 99) for r in recent_form]
        
        # Calculate trend
        if len(recent_positions) >= 3:
            # Simple trend: are positions improving?
            early_avg = sum(recent_positions[:2]) / 2
            late_avg = sum(recent_positions[-2:]) / 2
            
            if late_avg < early_avg - 1:
                trend = 'improving'
            elif late_avg > early_avg + 1:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        # Course record
        course_record = {}
        for race in history:
            course = race.get('course', 'Unknown')
            if course not in course_record:
                course_record[course] = {'runs': 0, 'wins': 0, 'places': 0}
            
            course_record[course]['runs'] += 1
            if race.get('position') == 1:
                course_record[course]['wins'] += 1
            if race.get('position', 99) <= 3:
                course_record[course]['places'] += 1
        
        # Distance record
        distance_record = {}
        for race in history:
            distance = race.get('distance', 0)
            distance_band = self._get_distance_band(distance)
            
            if distance_band not in distance_record:
                distance_record[distance_band] = {'runs': 0, 'wins': 0, 'places': 0}
            
            distance_record[distance_band]['runs'] += 1
            if race.get('position') == 1:
                distance_record[distance_band]['wins'] += 1
            if race.get('position', 99) <= 3:
                distance_record[distance_band]['places'] += 1
        
        # Going preference
        going_record = {}
        for race in history:
            going = race.get('going', 'Unknown')
            if going not in going_record:
                going_record[going] = {'runs': 0, 'wins': 0, 'places': 0}
            
            going_record[going]['runs'] += 1
            if race.get('position') == 1:
                going_record[going]['wins'] += 1
            if race.get('position', 99) <= 3:
                going_record[going]['places'] += 1
        
        return {
            'recent_form': recent_form,
            'trend': trend,
            'course_record': course_record,
            'distance_record': distance_record,
            'going_preference': going_record,
            'total_runs': len(history),
            'form_summary': self._summarize_form(recent_positions, trend)
        }
    
    def _get_distance_band(self, distance: int) -> str:
        """Categorize distance into bands."""
        if distance < 1000:
            return '5f-6f (sprint)'
        elif distance < 1400:
            return '7f-1m (short)'
        elif distance < 2000:
            return '1m-1m4f (middle)'
        elif distance < 2800:
            return '1m4f-1m6f (long)'
        else:
            return '2m+ (staying)'
    
    def _summarize_form(self, positions: List[int], trend: str) -> str:
        """Generate human-readable form summary in VÉLØ's voice."""
        if not positions:
            return "No recent form - ghost in the field"
        
        wins = sum(1 for p in positions if p == 1)
        places = sum(1 for p in positions if p <= 3)
        
        if wins >= 2:
            summary = f"Strong form - {wins} wins from {len(positions)} runs"
        elif places >= 3:
            summary = f"Consistent - {places} places from {len(positions)} runs"
        elif max(positions) > 10:
            summary = f"Struggling - best position {min(positions)} from {len(positions)} runs"
        else:
            summary = f"Mixed form - {places} places from {len(positions)} runs"
        
        if trend == 'improving':
            summary += " 📈 Trending upward - momentum building"
        elif trend == 'declining':
            summary += " 📉 Trending downward - losing edge"
        
        return summary
    
    def analyze_jockey_trainer_combo(self, jockey: str, trainer: str) -> Dict:
        """
        Analyze the effectiveness of a jockey-trainer combination.
        
        This is crucial - some combos have exceptional strike rates.
        
        Returns:
            Dict containing combo statistics and effectiveness rating
        """
        jockey_stats = self.client.get_jockey_stats(jockey, days=365)
        trainer_stats = self.client.get_trainer_stats(trainer, days=365)
        
        # In a real implementation, we'd query for specific combo stats
        # For now, we'll analyze individual stats
        
        jockey_strike_rate = jockey_stats.get('strike_rate', 0)
        trainer_strike_rate = trainer_stats.get('strike_rate', 0)
        
        # Combined effectiveness score
        combo_score = (jockey_strike_rate + trainer_strike_rate) / 2
        
        if combo_score > 20:
            rating = 'elite'
            message = "🔥 Elite combination - trust the partnership"
        elif combo_score > 15:
            rating = 'strong'
            message = "✓ Strong combination - proven success"
        elif combo_score > 10:
            rating = 'average'
            message = "→ Average combination - no edge here"
        else:
            rating = 'weak'
            message = "⚠️ Weak combination - proceed with caution"
        
        return {
            'jockey_strike_rate': jockey_strike_rate,
            'trainer_strike_rate': trainer_strike_rate,
            'combo_score': combo_score,
            'rating': rating,
            'message': message,
            'jockey_stats': jockey_stats,
            'trainer_stats': trainer_stats
        }
    
    def find_similar_races(self, race_conditions: Dict, limit: int = 50) -> List[Dict]:
        """
        Find historical races with similar conditions.
        
        This is pattern matching - finding what happened before in similar situations.
        
        Args:
            race_conditions: Dict containing:
                - course: Course name
                - distance: Distance in meters
                - going: Ground conditions
                - class: Race class
                
        Returns:
            List of similar historical races with outcomes
        """
        filters = {
            'course': race_conditions.get('course'),
            'distance': race_conditions.get('distance'),
            'going': race_conditions.get('going'),
            'class': race_conditions.get('class'),
            'date_from': (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d'),  # Last 2 years
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        similar_races = self.client.search_historical_patterns(filters)
        
        return similar_races[:limit]
    
    def analyze_course_bias(self, course: str, distance: int) -> Dict:
        """
        Analyze course biases (draw, pace, running style).
        
        Course bias is CRITICAL - some courses heavily favor certain draws or styles.
        
        Returns:
            Dict containing:
            - draw_bias: Which stalls perform best
            - pace_bias: Front-runners vs closers
            - going_impact: How ground affects bias
        """
        course_stats = self.client.get_course_stats(course, distance)
        
        if not course_stats:
            return {
                'draw_bias': 'unknown',
                'pace_bias': 'unknown',
                'message': 'Insufficient course data'
            }
        
        draw_bias = course_stats.get('draw_bias', {})
        pace_stats = course_stats.get('pace_stats', {})
        
        # Interpret draw bias
        if draw_bias.get('low_advantage', 0) > 15:
            draw_message = "⚠️ STRONG LOW DRAW BIAS - Inside stalls critical"
        elif draw_bias.get('high_advantage', 0) > 15:
            draw_message = "⚠️ STRONG HIGH DRAW BIAS - Outside stalls favored"
        else:
            draw_message = "✓ Neutral draw - stall position less critical"
        
        # Interpret pace bias
        front_runner_sr = pace_stats.get('front_runner_strike_rate', 0)
        closer_sr = pace_stats.get('closer_strike_rate', 0)
        
        if front_runner_sr > closer_sr + 10:
            pace_message = "🏃 Front-runner track - early speed crucial"
        elif closer_sr > front_runner_sr + 10:
            pace_message = "🎯 Closer's track - save energy for finish"
        else:
            pace_message = "→ Balanced pace - style less critical"
        
        return {
            'draw_bias': draw_bias,
            'pace_bias': pace_stats,
            'draw_message': draw_message,
            'pace_message': pace_message,
            'course_stats': course_stats
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize client
    client = RacingAPIClient()
    
    # Get recent results
    today = datetime.now().strftime('%Y-%m-%d')
    results = client.get_race_results(today)
    print(f"✓ Found {len(results)} races today")
    
    # Analyze a horse
    analyzer = RacingDataAnalyzer(client)
    form_analysis = analyzer.analyze_horse_form("Example Horse")
    print(f"\n📊 Form Analysis:")
    print(f"Trend: {form_analysis['trend']}")
    print(f"Summary: {form_analysis.get('form_summary', 'N/A')}")
    
    # Analyze course bias
    bias_analysis = analyzer.analyze_course_bias("Kempton", 1600)
    print(f"\n🏇 Course Bias:")
    print(f"Draw: {bias_analysis.get('draw_message', 'N/A')}")
    print(f"Pace: {bias_analysis.get('pace_message', 'N/A')}")

