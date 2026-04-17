"""
VÉLØ Oracle - Parquet Conversion + Performance Benchmarking
Convert CSV to Parquet for 4-5x speed improvement
"""
import time
import json
from pathlib import Path

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False
    print("WARNING: pyarrow not available. Install with: pip install pyarrow")


def convert_to_parquet(
    csv_path: str,
    parquet_path: str = None,
    compression: str = 'snappy',
    chunk_size: int = 100000
):
    """
    Convert CSV to Parquet with chunked processing
    
    Args:
        csv_path: Input CSV file
        parquet_path: Output Parquet file (None = auto)
        compression: Compression algorithm (snappy, gzip, brotli)
        chunk_size: Rows per chunk
        
    Returns:
        Conversion statistics
    """
    if not PYARROW_AVAILABLE:
        raise RuntimeError("pyarrow not installed. Run: pip install pyarrow")
    
    if parquet_path is None:
        parquet_path = csv_path.replace('.csv', '.parquet')
    
    print("="*60)
    print("Parquet Conversion")
    print("="*60)
    print(f"Input: {csv_path}")
    print(f"Output: {parquet_path}")
    print(f"Compression: {compression}")
    print(f"Chunk size: {chunk_size:,}")
    
    # Start timing
    start_time = time.time()
    
    # Read CSV in chunks and write to Parquet
    print("\nConverting...")
    
    writer = None
    total_rows = 0
    chunk_count = 0
    
    for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
        chunk_count += 1
        total_rows += len(chunk)
        
        # Convert to PyArrow Table
        table = pa.Table.from_pandas(chunk)
        
        # Write to Parquet
        if writer is None:
            writer = pq.ParquetWriter(
                parquet_path,
                table.schema,
                compression=compression
            )
        
        writer.write_table(table)
        
        if chunk_count % 10 == 0:
            print(f"  Processed {total_rows:,} rows ({chunk_count} chunks)...")
    
    # Close writer
    if writer:
        writer.close()
    
    # End timing
    end_time = time.time()
    duration = end_time - start_time
    
    # Get file sizes
    csv_size = Path(csv_path).stat().st_size
    parquet_size = Path(parquet_path).stat().st_size
    
    compression_ratio = csv_size / parquet_size if parquet_size > 0 else 0
    
    # Results
    print("\n" + "="*60)
    print("Conversion Complete")
    print("="*60)
    print(f"Total rows: {total_rows:,}")
    print(f"Total chunks: {chunk_count}")
    print(f"Duration: {duration:.2f}s")
    print(f"CSV size: {csv_size / 1024**2:.2f} MB")
    print(f"Parquet size: {parquet_size / 1024**2:.2f} MB")
    print(f"Compression ratio: {compression_ratio:.2f}x")
    print(f"Throughput: {total_rows / duration:,.0f} rows/sec")
    
    return {
        "csv_path": csv_path,
        "parquet_path": parquet_path,
        "total_rows": total_rows,
        "duration_seconds": duration,
        "csv_size_mb": csv_size / 1024**2,
        "parquet_size_mb": parquet_size / 1024**2,
        "compression_ratio": compression_ratio,
        "throughput_rows_per_sec": total_rows / duration
    }


def benchmark_performance(
    csv_path: str,
    parquet_path: str,
    n_rows: int = 100000
):
    """
    Benchmark CSV vs Parquet read performance
    
    Args:
        csv_path: CSV file
        parquet_path: Parquet file
        n_rows: Number of rows to read
        
    Returns:
        Benchmark results
    """
    if not PYARROW_AVAILABLE:
        raise RuntimeError("pyarrow not installed")
    
    print("\n" + "="*60)
    print("Performance Benchmark")
    print("="*60)
    print(f"Reading {n_rows:,} rows from each format...")
    
    # Benchmark CSV
    print("\nCSV:")
    start = time.time()
    df_csv = pd.read_csv(csv_path, nrows=n_rows)
    csv_time = time.time() - start
    print(f"  Time: {csv_time:.3f}s")
    print(f"  Throughput: {n_rows / csv_time:,.0f} rows/sec")
    
    # Benchmark Parquet
    print("\nParquet:")
    start = time.time()
    df_parquet = pq.read_table(parquet_path).to_pandas().head(n_rows)
    parquet_time = time.time() - start
    print(f"  Time: {parquet_time:.3f}s")
    print(f"  Throughput: {n_rows / parquet_time:,.0f} rows/sec")
    
    # Speedup
    speedup = csv_time / parquet_time if parquet_time > 0 else 0
    
    print("\n" + "="*60)
    print(f"Parquet is {speedup:.2f}x faster than CSV")
    print("="*60)
    
    return {
        "n_rows": n_rows,
        "csv_time_seconds": csv_time,
        "parquet_time_seconds": parquet_time,
        "speedup": speedup,
        "csv_throughput": n_rows / csv_time,
        "parquet_throughput": n_rows / parquet_time
    }


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert CSV to Parquet and benchmark")
    parser.add_argument("--csv", default="storage/velo-datasets/racing_full_1_7m.csv")
    parser.add_argument("--parquet", default=None)
    parser.add_argument("--compression", default="snappy", choices=['snappy', 'gzip', 'brotli'])
    parser.add_argument("--chunk-size", type=int, default=100000)
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmark")
    parser.add_argument("--benchmark-rows", type=int, default=100000)
    
    args = parser.parse_args()
    
    # Convert
    conversion_results = convert_to_parquet(
        csv_path=args.csv,
        parquet_path=args.parquet,
        compression=args.compression,
        chunk_size=args.chunk_size
    )
    
    # Benchmark
    if args.benchmark:
        benchmark_results = benchmark_performance(
            csv_path=args.csv,
            parquet_path=conversion_results['parquet_path'],
            n_rows=args.benchmark_rows
        )
    else:
        benchmark_results = None
    
    # Save results
    results = {
        "conversion": conversion_results,
        "benchmark": benchmark_results
    }
    
    results_path = "storage/parquet_conversion_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {results_path}")
    
    return results


if __name__ == "__main__":
    main()
