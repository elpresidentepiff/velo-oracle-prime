#!/usr/bin/env python3
"""
Update dataset paths in all scripts to use new dataset loader
"""
import os
import re

# Files to update
FILES_TO_UPDATE = [
    "app/services/backtest/backtest_50k_v2.py",
    "scripts/backtest/run_50k_v2.py",
    "scripts/train_automation/auto_train_all.py",
    "scripts/train_automation/auto_compare.py"
]

# Path replacements
REPLACEMENTS = [
    (r'data/train_1_7m\.parquet', 'storage/velo-datasets/racing_full_1_7m.csv'),
    (r'data/test\.parquet', 'storage/velo-datasets/racing_full_1_7m.csv'),
]

def update_file(filepath):
    """Update dataset paths in a file"""
    if not os.path.exists(filepath):
        print(f"⚠️  Skipping {filepath} (not found)")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"✅ Updated {filepath}")
        return True
    else:
        print(f"ℹ️  No changes needed in {filepath}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Updating dataset paths...")
    print("=" * 60)
    
    updated_count = 0
    for filepath in FILES_TO_UPDATE:
        if update_file(filepath):
            updated_count += 1
    
    print("=" * 60)
    print(f"✅ Updated {updated_count} files")
    print("=" * 60)
