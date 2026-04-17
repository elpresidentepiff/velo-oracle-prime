"""
VÉLØ Oracle - Parquet Dataset Loader
High-performance dataset loading with Parquet
"""
import pandas as pd
from typing import Optional, List

try:
    import pyarrow.parquet as pq
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False


def load_racing_dataset_parquet(
    path: str = "storage/velo-datasets/racing_full_1_7m.parquet",
    nrows: Optional[int] = None,
    columns: Optional[List[str]] = None,
    filters: Optional[List] = None
) -> pd.DataFrame:
    """
    Load racing dataset from Parquet (4-5x faster than CSV)
    
    Args:
        path: Path to Parquet file
        nrows: Number of rows to load (None = all)
        columns: Specific columns to load (None = all)
        filters: PyArrow filters for predicate pushdown
        
    Returns:
        DataFrame
        
    Example:
        # Load first 10K rows
        df = load_racing_dataset_parquet(nrows=10000)
        
        # Load specific columns
        df = load_racing_dataset_parquet(columns=['speed', 'rating', 'pos'])
        
        # Load with filter
        df = load_racing_dataset_parquet(
            filters=[('year', '>=', 2020)]
        )
    """
    if not PYARROW_AVAILABLE:
        raise RuntimeError("pyarrow not installed. Run: pip install pyarrow")
    
    # Read Parquet
    table = pq.read_table(
        path,
        columns=columns,
        filters=filters
    )
    
    # Convert to pandas
    df = table.to_pandas()
    
    # Limit rows if requested
    if nrows is not None:
        df = df.head(nrows)
    
    return df


def get_parquet_metadata(path: str) -> dict:
    """Get Parquet file metadata"""
    if not PYARROW_AVAILABLE:
        raise RuntimeError("pyarrow not installed")
    
    parquet_file = pq.ParquetFile(path)
    
    return {
        "num_rows": parquet_file.metadata.num_rows,
        "num_columns": parquet_file.metadata.num_columns,
        "num_row_groups": parquet_file.metadata.num_row_groups,
        "format_version": parquet_file.metadata.format_version,
        "serialized_size": parquet_file.metadata.serialized_size,
        "schema": {col: str(parquet_file.schema.field(col).type) 
                   for col in parquet_file.schema.names}
    }


if __name__ == "__main__":
    # Test loader
    print("Testing Parquet loader...")
    
    try:
        # Load sample
        df = load_racing_dataset_parquet(nrows=1000)
        print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
        
        # Get metadata
        metadata = get_parquet_metadata("storage/velo-datasets/racing_full_1_7m.parquet")
        print(f"✅ Total rows in file: {metadata['num_rows']:,}")
        print(f"✅ Total columns: {metadata['num_columns']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Note: Run convert_to_parquet_v2.py first to create Parquet file")
