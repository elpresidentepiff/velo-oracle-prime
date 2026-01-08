"""Tests for Great Expectations validation"""

import pytest
import pandas as pd
from data_quality.gx_context import get_gx_context, create_races_suite, create_runners_suite


class TestGXValidation:
    def test_valid_races_pass_validation(self):
        """Valid races should pass all GX expectations"""
        context = get_gx_context()
        create_races_suite()
        
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
        
        batch = context.sources.add_pandas("test_races")
        batch_request = batch.add_batch(valid_races)
        
        checkpoint = context.add_checkpoint(
            name="test_races_checkpoint",
            validations=[
                {
                    "batch_request": batch_request.dict(),
                    "expectation_suite_name": "races_validation_suite"
                }
            ]
        )
        
        results = checkpoint.run()
        assert results.success is True
    
    def test_invalid_races_fail_validation(self):
        """Races with missing critical fields should fail"""
        context = get_gx_context()
        create_races_suite()
        
        invalid_races = pd.DataFrame([
            {
                "id": "race-1",
                "course": None,  # Missing course
                "distance": 2000,
                "quality_score": 0.5,
                "batch_id": "batch-1"
            }
        ])
        
        batch = context.sources.add_pandas("test_invalid_races")
        batch_request = batch.add_batch(invalid_races)
        
        checkpoint = context.add_checkpoint(
            name="test_invalid_races_checkpoint",
            validations=[
                {
                    "batch_request": batch_request.dict(),
                    "expectation_suite_name": "races_validation_suite"
                }
            ]
        )
        
        results = checkpoint.run()
        assert results.success is False
    
    def test_duplicate_runners_fail_validation(self):
        """Duplicate horse names in same race should fail"""
        context = get_gx_context()
        create_runners_suite()
        
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
        
        batch = context.sources.add_pandas("test_duplicate_runners")
        batch_request = batch.add_batch(duplicate_runners)
        
        checkpoint = context.add_checkpoint(
            name="test_duplicate_runners_checkpoint",
            validations=[
                {
                    "batch_request": batch_request.dict(),
                    "expectation_suite_name": "runners_validation_suite"
                }
            ]
        )
        
        results = checkpoint.run()
        assert results.success is False
    
    def test_distance_out_of_range_fails(self):
        """Distance outside reasonable range should fail"""
        context = get_gx_context()
        create_races_suite()
        
        invalid_distance = pd.DataFrame([
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 500,  # Too short
                "quality_score": 0.9,
                "batch_id": "batch-1"
            }
        ])
        
        batch = context.sources.add_pandas("test_distance_range")
        batch_request = batch.add_batch(invalid_distance)
        
        checkpoint = context.add_checkpoint(
            name="test_distance_range_checkpoint",
            validations=[
                {
                    "batch_request": batch_request.dict(),
                    "expectation_suite_name": "races_validation_suite"
                }
            ]
        )
        
        results = checkpoint.run()
        assert results.success is False
    
    def test_odds_out_of_range_fails(self):
        """Odds outside reasonable range should fail"""
        context = get_gx_context()
        create_runners_suite()
        
        invalid_odds = pd.DataFrame([
            {
                "race_id": "race-1",
                "horse_name": "Test Horse",
                "odds": 0.5,  # Below minimum 1.01
                "confidence": 1.0
            }
        ])
        
        batch = context.sources.add_pandas("test_odds_range")
        batch_request = batch.add_batch(invalid_odds)
        
        checkpoint = context.add_checkpoint(
            name="test_odds_range_checkpoint",
            validations=[
                {
                    "batch_request": batch_request.dict(),
                    "expectation_suite_name": "runners_validation_suite"
                }
            ]
        )
        
        results = checkpoint.run()
        assert results.success is False
