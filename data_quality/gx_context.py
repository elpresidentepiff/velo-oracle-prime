"""Great Expectations context for VÉLØ data validation"""

import great_expectations as gx
from pathlib import Path
import pandas as pd


def get_gx_context():
    """Get or create GX context"""
    context_root = Path(__file__).parent / "great_expectations"
    context_root.mkdir(parents=True, exist_ok=True)
    
    return gx.get_context(project_root_dir=str(context_root))


def create_races_suite(context, df: pd.DataFrame):
    """
    Define expectations for races table
    Uses validator pattern with actual data to create suite
    """
    suite_name = "races_validation_suite"
    
    # Create or get pandas datasource
    try:
        datasource = context.data_sources.add_pandas(name="races_pandas")
    except Exception:
        # Datasource already exists, get it
        datasource = context.data_sources.get("races_pandas")
    
    # Add or get dataframe asset
    try:
        data_asset = datasource.add_dataframe_asset(name="races_asset")
    except Exception:
        # Asset already exists, get it
        data_asset = datasource.get_asset("races_asset")
    
    # Create or get batch definition
    try:
        batch_definition = data_asset.add_batch_definition_whole_dataframe("races_batch")
    except Exception:
        # Batch definition already exists, get it
        batch_definition = data_asset.get_batch_definition("races_batch")
    
    # Get batch with the dataframe
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
    
    # Build validator with the batch
    validator = context.get_validator(batch=batch)
    
    # Add expectations
    validator.expect_column_values_to_not_be_null(column="course")
    validator.expect_column_values_to_not_be_null(column="distance")
    validator.expect_column_values_to_be_between(column="distance", min_value=1000, max_value=5000)
    validator.expect_column_values_to_be_unique(column="id")
    validator.expect_column_values_to_be_between(column="quality_score", min_value=0.0, max_value=1.0)
    validator.expect_table_row_count_to_be_between(min_value=1, max_value=100)
    
    # Save the expectation suite (if it doesn't already exist)
    try:
        suite = validator.get_expectation_suite()
        suite.name = suite_name
        context.suites.add(suite)
    except Exception:
        # Suite already exists, that's okay
        pass
    
    return validator


def create_runners_suite(context, df: pd.DataFrame):
    """
    Define expectations for runners table
    Uses validator pattern with actual data to create suite
    """
    suite_name = "runners_validation_suite"
    
    # Create or get pandas datasource
    try:
        datasource = context.data_sources.add_pandas(name="runners_pandas")
    except Exception:
        # Datasource already exists, get it
        datasource = context.data_sources.get("runners_pandas")
    
    # Add or get dataframe asset
    try:
        data_asset = datasource.add_dataframe_asset(name="runners_asset")
    except Exception:
        # Asset already exists, get it
        data_asset = datasource.get_asset("runners_asset")
    
    # Create or get batch definition
    try:
        batch_definition = data_asset.add_batch_definition_whole_dataframe("runners_batch")
    except Exception:
        # Batch definition already exists, get it
        batch_definition = data_asset.get_batch_definition("runners_batch")
    
    # Get batch with the dataframe
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})
    
    # Build validator with the batch
    validator = context.get_validator(batch=batch)
    
    # Add expectations
    validator.expect_column_values_to_not_be_null(column="horse_name")
    validator.expect_column_values_to_be_between(column="odds", min_value=1.01, max_value=1000.0)
    validator.expect_column_values_to_be_between(column="confidence", min_value=0.0, max_value=1.0)
    validator.expect_compound_columns_to_be_unique(column_list=["race_id", "horse_name"])
    
    # Save the expectation suite (if it doesn't already exist)
    try:
        suite = validator.get_expectation_suite()
        suite.name = suite_name
        context.suites.add(suite)
    except Exception:
        # Suite already exists, that's okay
        pass
    
    return validator
