"""
Integration tests for real agent system
Tests agents, orchestrator, and data ingestion
"""
import pytest
import json
import os
from pathlib import Path

# Import agents
from app.engine.agents.form_analyzer import FormAnalyzer
from app.engine.agents.connections_analyzer import ConnectionsAnalyzer
from app.engine.agents.course_distance_analyzer import CourseDistanceAnalyzer
from app.engine.agents.ratings_analyzer import RatingsAnalyzer
from app.engine.agents.market_analyzer import MarketAnalyzer
from app.engine.orchestrator import Orchestrator


# Sample test data
@pytest.fixture
def sample_race_data():
    """Sample race data for testing"""
    return {
        "race_id": "TEST_20260110_1600",
        "course": "KEMPTON",
        "off_time": "16:00",
        "race_name": "Test Handicap",
        "distance": "2m",
        "going": "standard",
        "race_type": "FLAT",
        "class_band": "4",
        "runners": [
            {
                "cloth_no": 1,
                "horse_name": "TEST HORSE ONE",
                "trainer": "Test Trainer",
                "jockey": "Test Jockey",
                "form_figures": "1234",
                "or_rating": 75,
                "rpr": 78,
                "ts": 76,
                "age": 4,
                "weight": "9-7",
                "draw": 1,
                "odds": 5.0
            },
            {
                "cloth_no": 2,
                "horse_name": "TEST HORSE TWO",
                "trainer": "Another Trainer",
                "jockey": "Another Jockey",
                "form_figures": "5678",
                "or_rating": 70,
                "rpr": 72,
                "ts": 71,
                "age": 5,
                "weight": "9-5",
                "draw": 2,
                "odds": 8.0
            }
        ]
    }


@pytest.fixture
def race_context(sample_race_data):
    """Race context for agent testing"""
    return {
        'race_id': sample_race_data['race_id'],
        'course': sample_race_data['course'],
        'distance': sample_race_data['distance'],
        'going': sample_race_data['going'],
        'runners': sample_race_data['runners']
    }


class TestFormAnalyzer:
    """Test Form Analyzer agent"""
    
    def test_analyzer_initialization(self):
        """Test that Form Analyzer initializes correctly"""
        analyzer = FormAnalyzer()
        assert analyzer.name == "form_analyzer"
    
    def test_analyze_with_good_form(self, sample_race_data, race_context):
        """Test analysis with good recent form"""
        runner = sample_race_data['runners'][0]  # form "1234"
        
        analyzer = FormAnalyzer()
        result = analyzer.analyze(runner, race_context)
        
        assert result.score >= 50  # Should be above neutral
        assert 0 <= result.score <= 100
        assert 0 <= result.confidence <= 1
        assert 'form_figures' in result.evidence
    
    def test_analyze_with_poor_form(self, sample_race_data, race_context):
        """Test analysis with poor recent form"""
        runner = sample_race_data['runners'][1]  # form "5678"
        
        analyzer = FormAnalyzer()
        result = analyzer.analyze(runner, race_context)
        
        assert 0 <= result.score <= 100
        assert 0 <= result.confidence <= 1
    
    def test_analyze_with_no_form(self, race_context):
        """Test analysis with no form data"""
        runner = {'horse_name': 'NO FORM', 'form_figures': ''}
        
        analyzer = FormAnalyzer()
        result = analyzer.analyze(runner, race_context)
        
        assert result.score == 50.0  # Neutral
        assert result.confidence < 0.5  # Low confidence


class TestRatingsAnalyzer:
    """Test Ratings Analyzer agent"""
    
    def test_analyzer_initialization(self):
        """Test that Ratings Analyzer initializes correctly"""
        analyzer = RatingsAnalyzer()
        assert analyzer.name == "ratings_analyzer"
    
    def test_analyze_top_rated_horse(self, sample_race_data, race_context):
        """Test analysis for top-rated horse"""
        runner = sample_race_data['runners'][0]  # OR 75
        
        analyzer = RatingsAnalyzer()
        result = analyzer.analyze(runner, race_context)
        
        assert result.score >= 50  # Should be above neutral for top-rated
        assert 0 <= result.score <= 100
        assert result.confidence > 0.5
    
    def test_analyze_with_no_ratings(self, race_context):
        """Test analysis with no ratings data"""
        runner = {'horse_name': 'NO RATINGS'}
        
        analyzer = RatingsAnalyzer()
        result = analyzer.analyze(runner, race_context)
        
        assert result.score == 50.0  # Neutral
        assert result.confidence < 0.5


class TestMarketAnalyzer:
    """Test Market Analyzer agent"""
    
    def test_analyzer_initialization(self):
        """Test that Market Analyzer initializes correctly"""
        analyzer = MarketAnalyzer()
        assert analyzer.name == "market_analyzer"
    
    def test_analyze_with_good_odds(self, sample_race_data, race_context):
        """Test analysis with optimal odds range"""
        runner = sample_race_data['runners'][0]  # odds 5.0
        
        analyzer = MarketAnalyzer()
        result = analyzer.analyze(runner, race_context)
        
        assert 0 <= result.score <= 100
        assert result.confidence > 0.5
        assert 'odds' in result.evidence
    
    def test_analyze_with_no_odds(self, race_context):
        """Test analysis with no odds data"""
        runner = {'horse_name': 'NO ODDS', 'or_rating': 75}
        
        analyzer = MarketAnalyzer()
        result = analyzer.analyze(runner, race_context)
        
        assert result.score == 50.0  # Neutral
        assert result.confidence < 0.5


class TestConnectionsAnalyzer:
    """Test Connections Analyzer agent (without database)"""
    
    def test_analyzer_initialization(self):
        """Test that Connections Analyzer initializes correctly"""
        analyzer = ConnectionsAnalyzer(None)  # No DB client
        assert analyzer.name == "connections_analyzer"
    
    def test_analyze_without_database(self, sample_race_data, race_context):
        """Test analysis without database connection"""
        runner = sample_race_data['runners'][0]
        
        analyzer = ConnectionsAnalyzer(None)
        result = analyzer.analyze(runner, race_context)
        
        # Should return neutral score with low confidence when no DB
        assert result.score == 50.0
        assert result.confidence < 0.5


class TestCourseDistanceAnalyzer:
    """Test Course/Distance Analyzer agent (without database)"""
    
    def test_analyzer_initialization(self):
        """Test that Course/Distance Analyzer initializes correctly"""
        analyzer = CourseDistanceAnalyzer(None)  # No DB client
        assert analyzer.name == "course_distance_analyzer"
    
    def test_analyze_without_database(self, sample_race_data, race_context):
        """Test analysis without database connection"""
        runner = sample_race_data['runners'][0]
        
        analyzer = CourseDistanceAnalyzer(None)
        result = analyzer.analyze(runner, race_context)
        
        # Should return neutral score with low confidence when no DB
        assert result.score == 50.0
        assert result.confidence < 0.5


class TestOrchestrator:
    """Test Orchestrator integration"""
    
    def test_orchestrator_initialization(self):
        """Test that Orchestrator initializes correctly"""
        orchestrator = Orchestrator(supabase_url=None, supabase_key=None)
        
        assert len(orchestrator.agents) == 5
        assert 'form' in orchestrator.agents
        assert 'connections' in orchestrator.agents
        assert 'course_distance' in orchestrator.agents
        assert 'ratings' in orchestrator.agents
        assert 'market' in orchestrator.agents
    
    def test_analyze_race(self, sample_race_data):
        """Test full race analysis"""
        orchestrator = Orchestrator(supabase_url=None, supabase_key=None)
        
        verdicts = orchestrator.analyze_race(sample_race_data)
        
        # Should return verdicts for all runners
        assert len(verdicts) == len(sample_race_data['runners'])
        
        for verdict in verdicts:
            # Check verdict structure
            assert hasattr(verdict, 'horse_name')
            assert hasattr(verdict, 'final_score')
            assert hasattr(verdict, 'action')
            assert hasattr(verdict, 'stake_pct')
            assert hasattr(verdict, 'reason')
            
            # Check score range
            assert 0 <= verdict.final_score <= 100
            
            # Check action is valid
            assert verdict.action in ['BACK', 'LAY', 'PASS']
            
            # Check stake is reasonable
            assert 0 <= verdict.stake_pct <= 5.0
            
            # Check all agent scores present
            assert len(verdict.agent_scores) == 5
            assert 'form' in verdict.agent_scores
            assert 'connections' in verdict.agent_scores
            assert 'course_distance' in verdict.agent_scores
            assert 'ratings' in verdict.agent_scores
            assert 'market' in verdict.agent_scores
    
    def test_betting_rules_pass(self, sample_race_data):
        """Test that PASS action is applied correctly"""
        orchestrator = Orchestrator(supabase_url=None, supabase_key=None)
        
        verdicts = orchestrator.analyze_race(sample_race_data)
        
        # Without database, most should be PASS
        pass_count = len([v for v in verdicts if v.action == 'PASS'])
        assert pass_count > 0
    
    def test_weighted_scoring(self, sample_race_data):
        """Test that weighted scoring is applied"""
        orchestrator = Orchestrator(supabase_url=None, supabase_key=None)
        
        verdicts = orchestrator.analyze_race(sample_race_data)
        
        for verdict in verdicts:
            # Calculate expected weighted score
            expected_score = (
                verdict.agent_scores['form'] * 0.20 +
                verdict.agent_scores['connections'] * 0.25 +
                verdict.agent_scores['course_distance'] * 0.20 +
                verdict.agent_scores['ratings'] * 0.20 +
                verdict.agent_scores['market'] * 0.15
            )
            
            # Should match final score (within rounding)
            assert abs(verdict.final_score - expected_score) < 0.1


class TestSystemIntegration:
    """Test complete system integration"""
    
    def test_end_to_end_analysis(self, sample_race_data):
        """Test complete end-to-end race analysis"""
        # Initialize orchestrator
        orchestrator = Orchestrator(supabase_url=None, supabase_key=None)
        
        # Run analysis
        verdicts = orchestrator.analyze_race(sample_race_data)
        
        # Verify results
        assert len(verdicts) > 0
        
        # Should have complete data for each verdict
        for verdict in verdicts:
            assert verdict.horse_name in [r['horse_name'] for r in sample_race_data['runners']]
            assert isinstance(verdict.final_score, (int, float))
            assert verdict.action in ['BACK', 'LAY', 'PASS']
            assert isinstance(verdict.reason, str)
            assert len(verdict.reason) > 0
    
    def test_graceful_degradation_without_db(self, sample_race_data):
        """Test that system works without database (degraded mode)"""
        orchestrator = Orchestrator(supabase_url=None, supabase_key=None)
        
        # Should not raise error even without DB
        verdicts = orchestrator.analyze_race(sample_race_data)
        
        # Should still produce verdicts
        assert len(verdicts) > 0
        
        # Connections and course/distance should have neutral scores
        for verdict in verdicts:
            assert verdict.agent_scores['connections'] == 50.0
            assert verdict.agent_scores['course_distance'] == 50.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
