# VÉLØ Oracle - Storage Directory

## Overview

This directory contains large datasets that are too big for Git version control.

---

## 📁 Directory Structure

```
storage/
├── velo-datasets/          # Racing datasets
│   ├── racing_full_1_7m.csv       # Full UK racing dataset (633MB, 1.7M rows)
│   └── racing_full_1_7m.parquet   # Parquet version (faster loading)
└── README.md               # This file
```

---

## 📊 Datasets

### racing_full_1_7m.csv

**Description:** Complete UK horse racing dataset  
**Size:** 633MB  
**Rows:** 1,702,741  
**Columns:** 37  
**Date Range:** 2015-01-01 to 2024-12-31  
**Format:** CSV  

**Columns:**
- `date` - Race date
- `course` - Racecourse name
- `race_id` - Unique race identifier
- `off` - Race start time
- `race_name` - Race name
- `type` - Race type (Flat, Hurdle, Chase)
- `class` - Race class
- `dist` - Distance
- `going` - Going description
- `ran` - Number of runners
- `num` - Runner number
- `pos` - Finishing position
- `draw` - Draw position
- `horse` - Horse name
- `age` - Horse age
- `sex` - Horse sex
- `wgt` - Weight carried
- `time` - Finishing time
- `sp` - Starting price (odds)
- `jockey` - Jockey name
- `trainer` - Trainer name
- `or` - Official rating
- `rpr` - Racing Post Rating
- `ts` - Timeform rating
- And more...

**Source:** Google Drive  
**Upload Date:** 2025-11-19  
**Uploader:** Steven Restrepo (purorestrepo1981@gmail.com)  

---

## 🚀 Usage

### Load Dataset

```python
from app.data.dataset_loader import load_racing_dataset

# Load full dataset
df = load_racing_dataset()

# Load first 100K rows
df = load_racing_dataset(nrows=100_000)

# Load 10% sample
df = load_racing_dataset(sample_frac=0.1)

# Load specific date range
df = load_racing_dataset(date_range=("2020-01-01", "2023-12-31"))
```

### List Available Datasets

```python
from app.data.dataset_loader import list_available_datasets

datasets = list_available_datasets()
for name, info in datasets.items():
    print(f"{name}: {info['size_mb']:.2f}MB, {info['row_count']:,} rows")
```

### Get Dataset Info

```python
from app.data.dataset_loader import get_dataset_info

info = get_dataset_info("racing_full_1_7m")
print(f"Size: {info['size_mb']:.2f}MB")
print(f"Rows: {info['row_count']:,}")
```

---

## 🔧 Conversion to Parquet

For faster loading, convert CSV to Parquet:

```python
from app.data.dataset_loader import convert_csv_to_parquet

convert_csv_to_parquet(
    csv_path="storage/velo-datasets/racing_full_1_7m.csv",
    parquet_path="storage/velo-datasets/racing_full_1_7m.parquet",
    compression='snappy'
)
```

**Benefits:**
- 3-5x faster loading
- 2-3x smaller file size
- Column-based storage (efficient queries)
- Preserves data types

---

## 📝 Git Ignore

This directory is **excluded from Git** to avoid:
- Repository bloat
- Slow clone/pull operations
- GitHub file size limits (100MB)

**`.gitignore` entry:**
```
storage/velo-datasets/*.csv
storage/velo-datasets/*.parquet
```

---

## 🌐 Alternative Storage Options

### Option 1: Supabase Storage (Recommended)
```python
# Upload to Supabase bucket
from src.data.supabase_client import get_supabase_client

client = get_supabase_client()
with open('storage/velo-datasets/racing_full_1_7m.csv', 'rb') as f:
    client.storage.from_('velo-datasets').upload('racing_full_1_7m.csv', f)
```

### Option 2: Cloudflare R2
```bash
# Upload to R2 bucket via MCP
manus-mcp-cli tool call r2_upload --server cloudflare \
  --input '{"file_path": "storage/velo-datasets/racing_full_1_7m.csv", "bucket": "velo-datasets"}'
```

### Option 3: Railway Volume
```bash
# Mount volume to /mnt/data
railway volume create velo-datasets 10GB
railway volume mount /mnt/data
cp storage/velo-datasets/*.csv /mnt/data/
```

---

## 📈 Dataset Statistics

| Metric | Value |
|--------|-------|
| Total Races | ~170,000 |
| Total Runners | 1,702,741 |
| Date Range | 2015-2024 (10 years) |
| Racecourses | ~60 UK courses |
| Race Types | Flat, Hurdle, Chase |
| File Size (CSV) | 633MB |
| File Size (Parquet) | ~200MB (estimated) |
| Compression Ratio | ~3x |

---

## 🔐 Access Control

**Who can access:**
- Developers with repository access
- Production servers with storage mount
- CI/CD pipelines (if configured)

**Who cannot access:**
- Public (file not in Git)
- Unauthorized users

---

## 🆘 Troubleshooting

### File Not Found
```python
FileNotFoundError: Dataset not found: storage/velo-datasets/racing_full_1_7m.csv
```

**Solution:**
1. Check file exists: `ls -lh storage/velo-datasets/`
2. Download from Google Drive (see below)
3. Or use alternative dataset: `load_racing_dataset("backtest_50k")`

### Download from Google Drive

```bash
# Using curl
curl -L "https://drive.usercontent.google.com/download?id=1vIe76v2-4jGwBxwDZCijEYPctDcb4ZRa&export=download&confirm=t" \
  -o storage/velo-datasets/racing_full_1_7m.csv

# Verify download
ls -lh storage/velo-datasets/racing_full_1_7m.csv
wc -l storage/velo-datasets/racing_full_1_7m.csv  # Should be 1,702,742
```

### Memory Issues

If loading full dataset causes memory issues:

```python
# Load in chunks
chunks = []
for chunk in pd.read_csv('storage/velo-datasets/racing_full_1_7m.csv', chunksize=100_000):
    # Process chunk
    chunks.append(chunk)

df = pd.concat(chunks)
```

Or use sampling:

```python
# Load 10% sample
df = load_racing_dataset(sample_frac=0.1)
```

---

## 📞 Support

For issues with:
- **Dataset access:** Check this README
- **Data quality:** Report to data team
- **Loading errors:** Check `app/data/dataset_loader.py`
- **Storage setup:** See deployment docs

---

**Last Updated:** 2025-11-19  
**Maintainer:** VÉLØ Oracle Team  
**Version:** 1.0
