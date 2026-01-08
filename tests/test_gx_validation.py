"""Tests for Great Expectations validation"""

import pytest
import pandas as pd
from data_quality.gx_context import get_gx_context, create_races_suite, create_runners_suite


class TestGXValidation:
    def test_valid_races_pass_validation(self):
        """Valid races should pass all GX expectations"""
        context = get_gx_context()
        
        valid_races = pd.DataFrame([
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "quality_score": 0.95,
                "batch_id": "batch-1"
            },
            {
                "id": "race-2",
                "course": "Ascot",
                "distance": 1600,
                "quality_score": 0.88,
                "batch_id": "batch-1"
            }
        ])
        
        validator = create_races_suite(context, valid_races)
        results = validator.validate()
        
        assert results.success is True
    
    def test_invalid_races_fail_validation(self):
        """Races with missing critical fields should fail"""
        context = get_gx_context()
        
        invalid_races = pd.DataFrame([
            {
                "id": "race-1",
                "course": None,  # Missing course
                "distance": 2000,
                "quality_score": 0.5,
                "batch_id": "batch-1"
            }
        ])
        
        validator = create_races_suite(context, invalid_races)
        results = validator.validate()
        
        assert results.success is False
    
    def test_duplicate_runners_fail_validation(self):
        """Duplicate horse names in same race should fail"""
        context = get_gx_context()
        
        duplicate_runners = pd.DataFrame([
            {
                "race_id": "race-1",
                "horse_name": "Same Horse",
                "odds": 5.0,
                "confidence": 1.0
            },
            {
                "race_id": "race-1",
                "horse_name": "Same Horse",  # Duplicate
                "odds": 3.0,
                "confidence": 1.0
            }
        ])
        
        validator = create_runners_suite(context, duplicate_runners)
        results = validator.validate()
        
        assert results.success is False
    
    def test_distance_out_of_range_fails(self):
        """Distance outside reasonable range should fail"""
        context = get_gx_context()
        
        invalid_distance = pd.DataFrame([
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 500,  # Too short
                "quality_score": 0.9,
                "batch_id": "batch-1"
            }
        ])
        
        validator = create_races_suite(context, invalid_distance)
        results = validator.validate()
        
        assert results.success is False
    
    def test_odds_out_of_range_fails(self):
        """Odds outside reasonable range should fail"""
        context = get_gx_context()
        
        invalid_odds = pd.DataFrame([
            {
                "race_id": "race-1",
                "horse_name": "Test Horse",
                "odds": 0.5,  # Below minimum 1.01
                "confidence": 1.0
            }
        ])
        
        validator = create_runners_suite(context, invalid_odds)
        results = validator.validate()
        
        assert results.success is False
    
    def test_quality_score_out_of_range_fails(self):
        """Quality score outside 0-1 range should fail"""
        context = get_gx_context()
        
        invalid_quality = pd.DataFrame([
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "quality_score": 1.5,  # Above maximum 1.0
                "batch_id": "batch-1"
            }
        ])
        
        validator = create_races_suite(context, invalid_quality)
        results = validator.validate()
        
        assert results.success is False
    
    def test_missing_horse_name_fails(self):
        """Missing horse name should fail"""
        context = get_gx_context()
        
        missing_name = pd.DataFrame([
            {
                "race_id": "race-1",
                "horse_name": None,  # Missing name
                "odds": 5.0,
                "confidence": 1.0
            }
        ])
        
        validator = create_runners_suite(context, missing_name)
        results = validator.validate()
        
        assert results.success is False
