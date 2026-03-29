"""
VÉLØ Oracle - Data Package
Centralized data loading and management
"""

from .dataset_loader import (
    DATASET_PATHS,
    convert_csv_to_parquet,
    get_dataset_info,
    list_available_datasets,
    load_racing_dataset,
)

__all__ = [
    "load_racing_dataset",
    "get_dataset_loader",
    "list_available_datasets",
    "convert_csv_to_parquet",
    "DATASET_PATHS",
]
