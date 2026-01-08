"""Great Expectations context for VÉLØ data validation"""

import great_expectations as gx
from great_expectations.core import ExpectationConfiguration
from pathlib import Path


def get_gx_context():
    """Get or create GX context"""
    context_root = Path(__file__).parent / "great_expectations"
    context_root.mkdir(parents=True, exist_ok=True)
    
    return gx.get_context(context_root_dir=str(context_root))


def create_races_suite():
    """Define expectations for races table"""
    context = get_gx_context()
    
    suite_name = "races_validation_suite"
    suite = context.add_expectation_suite(suite_name, overwrite_existing=True)
    
    # Critical fields must not be null
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_not_be_null",
            kwargs={"column": "course"}
        )
    )
    
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_not_be_null",
            kwargs={"column": "distance"}
        )
    )
    
    # Distance must be in reasonable range (1000m - 5000m)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "distance", "min_value": 1000, "max_value": 5000}
        )
    )
    
    # Race ID must be unique
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_unique",
            kwargs={"column": "id"}
        )
    )
    
    # Quality score must be 0-1
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "quality_score", "min_value": 0.0, "max_value": 1.0}
        )
    )
    
    # Runner count should be reasonable (at least 1, max 30)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_table_row_count_to_be_between",
            kwargs={"min_value": 1, "max_value": 100}
        )
    )
    
    context.save_expectation_suite(suite)
    return suite


def create_runners_suite():
    """Define expectations for runners table"""
    context = get_gx_context()
    
    suite_name = "runners_validation_suite"
    suite = context.add_expectation_suite(suite_name, overwrite_existing=True)
    
    # Horse name must not be null
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_not_be_null",
            kwargs={"column": "horse_name"}
        )
    )
    
    # Odds must be present and reasonable (1.01 - 1000)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "odds", "min_value": 1.01, "max_value": 1000.0}
        )
    )
    
    # Confidence must be 0-1
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_column_values_to_be_between",
            kwargs={"column": "confidence", "min_value": 0.0, "max_value": 1.0}
        )
    )
    
    # Race ID + Horse name must be unique (no duplicate runners in same race)
    suite.add_expectation(
        ExpectationConfiguration(
            expectation_type="expect_compound_columns_to_be_unique",
            kwargs={"column_list": ["race_id", "horse_name"]}
        )
    )
    
    context.save_expectation_suite(suite)
    return suite
