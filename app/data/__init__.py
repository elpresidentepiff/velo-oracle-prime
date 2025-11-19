"""
VÉLØ Oracle - Data Package
Centralized data loading and management
"""

from .dataset_loader import (
    load_racing_dataset,
    get_dataset_info,
    list_available_datasets,
    convert_csv_to_parquet,
    DATASET_PATHS
)

__all__ = [
    'load_racing_dataset',
    'get_dataset_loader',
    'list_available_datasets',
    'convert_csv_to_parquet',
    'DATASET_PATHS'
]
