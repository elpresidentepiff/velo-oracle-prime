"""
VÉLØ Oracle - Dataset Loader
Centralized dataset loading with support for CSV and Parquet formats
"""
import pandas as pd
import os
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# Dataset paths
DATASET_PATHS = {
    "racing_full_1_7m": "storage/velo-datasets/racing_full_1_7m.csv",
    "racing_full_parquet": "storage/velo-datasets/racing_full_1_7m.parquet",
    "backtest_50k": "data/backtest_50k_clean.csv",
    "train_sample": "data/train_sample_clean.csv",
    "train_5k": "data/train_5k_clean.csv"
}


def load_racing_dataset(
    dataset_name: str = "racing_full_1_7m",
    nrows: Optional[int] = None,
    sample_frac: Optional[float] = None,
    date_range: Optional[Tuple[str, str]] = None,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Load racing dataset with flexible options
    
    Args:
        dataset_name: Name of dataset to load (see DATASET_PATHS)
        nrows: Number of rows to load (None = all)
        sample_frac: Fraction of data to sample (0.0-1.0)
        date_range: Optional tuple of (start_date, end_date) for filtering
        random_state: Random seed for sampling
        
    Returns:
        DataFrame with racing data
        
    Examples:
        >>> # Load full dataset
        >>> df = load_racing_dataset()
        
        >>> # Load first 100K rows
        >>> df = load_racing_dataset(nrows=100_000)
        
        >>> # Load 10% sample
        >>> df = load_racing_dataset(sample_frac=0.1)
        
        >>> # Load specific date range
        >>> df = load_racing_dataset(date_range=("2020-01-01", "2023-12-31"))
    """
    
    # Get dataset path
    if dataset_name not in DATASET_PATHS:
        raise ValueError(f"Unknown dataset: {dataset_name}. Available: {list(DATASET_PATHS.keys())}")
    
    path = DATASET_PATHS[dataset_name]
    
    # Check if file exists
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")
    
    logger.info(f"Loading dataset: {dataset_name} from {path}")
    
    # Load based on file type
    if path.endswith('.parquet'):
        df = pd.read_parquet(path)
        if nrows:
            df = df.head(nrows)
    elif path.endswith('.csv'):
        df = pd.read_csv(path, nrows=nrows, low_memory=False)
    else:
        raise ValueError(f"Unsupported file format: {path}")
    
    logger.info(f"✅ Loaded dataset with shape: {df.shape}")
    
    # Apply sampling if requested
    if sample_frac and 0 < sample_frac < 1.0:
        original_size = len(df)
        df = df.sample(frac=sample_frac, random_state=random_state)
        logger.info(f"Sampled {len(df)} rows ({sample_frac*100:.1f}%) from {original_size}")
    
    # Apply date filtering if requested
    if date_range and 'date' in df.columns:
        start_date, end_date = date_range
        original_size = len(df)
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        logger.info(f"Filtered to date range {start_date} to {end_date}: {len(df)} rows (from {original_size})")
    
    return df


def get_dataset_info(dataset_name: str = "racing_full_1_7m") -> dict:
    """
    Get metadata about a dataset without loading it
    
    Args:
        dataset_name: Name of dataset
        
    Returns:
        Dictionary with dataset metadata
    """
    if dataset_name not in DATASET_PATHS:
        raise ValueError(f"Unknown dataset: {dataset_name}")
    
    path = DATASET_PATHS[dataset_name]
    
    if not os.path.exists(path):
        return {
            "name": dataset_name,
            "path": path,
            "exists": False,
            "error": "File not found"
        }
    
    file_size = os.path.getsize(path)
    
    # Quick row count for CSV
    if path.endswith('.csv'):
        with open(path, 'r') as f:
            row_count = sum(1 for _ in f) - 1  # Subtract header
    else:
        # For parquet, need to load to get row count
        df = pd.read_parquet(path)
        row_count = len(df)
    
    return {
        "name": dataset_name,
        "path": path,
        "exists": True,
        "size_mb": file_size / (1024 ** 2),
        "row_count": row_count,
        "format": "parquet" if path.endswith('.parquet') else "csv"
    }


def list_available_datasets() -> dict:
    """
    List all available datasets with their status
    
    Returns:
        Dictionary mapping dataset names to their info
    """
    datasets = {}
    for name in DATASET_PATHS.keys():
        try:
            datasets[name] = get_dataset_info(name)
        except Exception as e:
            datasets[name] = {
                "name": name,
                "exists": False,
                "error": str(e)
            }
    
    return datasets


def convert_csv_to_parquet(
    csv_path: str,
    parquet_path: str,
    compression: str = 'snappy'
) -> None:
    """
    Convert CSV to Parquet format for faster loading
    
    Args:
        csv_path: Path to CSV file
        parquet_path: Path to save Parquet file
        compression: Compression algorithm (snappy, gzip, brotli)
    """
    logger.info(f"Converting {csv_path} to {parquet_path}...")
    
    df = pd.read_csv(csv_path, low_memory=False)
    df.to_parquet(parquet_path, compression=compression, index=False)
    
    csv_size = os.path.getsize(csv_path) / (1024 ** 2)
    parquet_size = os.path.getsize(parquet_path) / (1024 ** 2)
    
    logger.info(f"✅ Converted: {csv_size:.2f}MB (CSV) → {parquet_size:.2f}MB (Parquet)")
    logger.info(f"Compression ratio: {csv_size/parquet_size:.2f}x")


if __name__ == "__main__":
    # Test loading
    print("=" * 60)
    print("VÉLØ Oracle - Dataset Loader Test")
    print("=" * 60)
    
    print("\nAvailable datasets:")
    datasets = list_available_datasets()
    for name, info in datasets.items():
        if info.get('exists'):
            print(f"  ✅ {name}: {info['size_mb']:.2f}MB, {info['row_count']:,} rows")
        else:
            print(f"  ❌ {name}: {info.get('error', 'Not found')}")
    
    print("\nLoading sample (first 1000 rows)...")
    try:
        df = load_racing_dataset(nrows=1000)
        print(f"✅ Loaded: {df.shape}")
        print(f"\nColumns ({len(df.columns)}):")
        print(df.columns.tolist())
        print(f"\nFirst row:")
        print(df.head(1).T)
    except Exception as e:
        print(f"❌ Error: {e}")
