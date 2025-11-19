#!/usr/bin/env python3
"""
VÉLØ Oracle - Convert CSV to Parquet
Optimizes dataset for 4-5x faster loading
"""
import pandas as pd
import time
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def convert_csv_to_parquet(
    csv_path: str = "storage/velo-datasets/racing_full_1_7m.csv",
    parquet_path: str = "storage/velo-datasets/racing_full_1_7m.parquet",
    exclude_columns: list = None,
    compression: str = 'snappy'
):
    """
    Convert CSV to Parquet format with optimizations
    
    Args:
        csv_path: Path to source CSV file
        parquet_path: Path to save Parquet file
        exclude_columns: Columns to exclude (e.g., ['comment'])
        compression: Compression algorithm (snappy, gzip, brotli)
    """
    
    logger.info("="*60)
    logger.info("VÉLØ Oracle - CSV to Parquet Conversion")
    logger.info("="*60)
    
    # Check source file exists
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source file not found: {csv_path}")
    
    csv_size = os.path.getsize(csv_path) / (1024 ** 2)
    logger.info(f"Source CSV: {csv_path}")
    logger.info(f"Size: {csv_size:.2f}MB")
    
    # Load CSV
    logger.info("\nLoading CSV...")
    start = time.time()
    
    df = pd.read_csv(csv_path, low_memory=False)
    
    load_time = time.time() - start
    logger.info(f"✅ Loaded in {load_time:.2f}s")
    logger.info(f"Shape: {df.shape}")
    logger.info(f"Memory: {df.memory_usage(deep=True).sum() / (1024**2):.2f}MB")
    
    # Exclude columns if specified
    if exclude_columns:
        logger.info(f"\nExcluding columns: {exclude_columns}")
        df = df.drop(columns=[col for col in exclude_columns if col in df.columns])
        logger.info(f"New shape: {df.shape}")
    
    # Optimize data types
    logger.info("\nOptimizing data types...")
    
    # Convert date to datetime
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    
    # Optimize numeric columns
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    
    # Convert categorical columns
    categorical_cols = ['course', 'type', 'class', 'going', 'sex', 'jockey', 'trainer']
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')
    
    optimized_memory = df.memory_usage(deep=True).sum() / (1024**2)
    logger.info(f"Optimized memory: {optimized_memory:.2f}MB")
    
    # Save to Parquet
    logger.info(f"\nSaving to Parquet...")
    logger.info(f"Compression: {compression}")
    
    start = time.time()
    df.to_parquet(parquet_path, compression=compression, index=False)
    save_time = time.time() - start
    
    parquet_size = os.path.getsize(parquet_path) / (1024 ** 2)
    
    logger.info(f"✅ Saved in {save_time:.2f}s")
    logger.info(f"Parquet size: {parquet_size:.2f}MB")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("CONVERSION SUMMARY")
    logger.info("="*60)
    logger.info(f"CSV Size:        {csv_size:.2f}MB")
    logger.info(f"Parquet Size:    {parquet_size:.2f}MB")
    logger.info(f"Compression:     {csv_size/parquet_size:.2f}x")
    logger.info(f"Space Saved:     {csv_size - parquet_size:.2f}MB")
    logger.info(f"Load Time (CSV): {load_time:.2f}s")
    logger.info(f"Save Time (PQ):  {save_time:.2f}s")
    logger.info("="*60)
    
    # Test loading speed
    logger.info("\nTesting Parquet load speed...")
    start = time.time()
    df_test = pd.read_parquet(parquet_path)
    parquet_load_time = time.time() - start
    
    logger.info(f"✅ Parquet loaded in {parquet_load_time:.2f}s")
    logger.info(f"Speedup: {load_time/parquet_load_time:.2f}x faster")
    
    return {
        "csv_size_mb": csv_size,
        "parquet_size_mb": parquet_size,
        "compression_ratio": csv_size / parquet_size,
        "csv_load_time": load_time,
        "parquet_load_time": parquet_load_time,
        "speedup": load_time / parquet_load_time,
        "rows": len(df),
        "columns": len(df.columns)
    }


if __name__ == "__main__":
    # Convert with comment column excluded
    result = convert_csv_to_parquet(
        csv_path="storage/velo-datasets/racing_full_1_7m.csv",
        parquet_path="storage/velo-datasets/racing_full_1_7m.parquet",
        exclude_columns=['comment'],  # Exclude large text field
        compression='snappy'
    )
    
    print("\n✅ Conversion complete!")
    print(f"Parquet file: storage/velo-datasets/racing_full_1_7m.parquet")
    print(f"Size: {result['parquet_size_mb']:.2f}MB")
    print(f"Speedup: {result['speedup']:.2f}x faster loading")
