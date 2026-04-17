#!/usr/bin/env python3
"""
VELO Leakage Firewall
Hard-blocks future data from contaminating training and inference

Critical: Prevents using any data timestamped after decision time.
This is non-negotiable for production betting systems.

Blocked data types:
- Finishing positions (pos, pos_num, result)
- Starting prices after off (sp, bfsp)
- In-running data (in_running_low, in_running_high)
- Any timestamp > decision_timestamp

Author: VELO Team
Version: 1.0
Date: December 17, 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class LeakageFirewall:
    """
    Prevents future data leakage in training and inference.
    
    Acceptance criteria: All features must be timestamped <= decision_timestamp
    """
    
    # Blocked fields that contain future information
    BLOCKED_FIELDS = [
        'pos',           # Finishing position
        'pos_num',       # Numeric finishing position
        'sp',            # Starting price (after off)
        'bfsp',          # Betfair starting price
        'in_running_low', # In-running low
        'in_running_high', # In-running high
        'result',        # Race result
        'finish_time',   # Finish time
        'winner',        # Winner flag
        'placed',        # Placed flag (if post-race)
    ]
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize leakage firewall.
        
        Args:
            schema_path: Optional path to feature schema JSON
        """
        self.blocked_fields = set(self.BLOCKED_FIELDS)
        
        # Load additional blocked fields from schema
        if schema_path:
            self._load_schema_blocked_fields(schema_path)
    
    def _load_schema_blocked_fields(self, schema_path: str):
        """Load blocked fields from schema."""
        try:
            with open(schema_path, 'r') as f:
                schema = json.load(f)
                
            blocked = schema.get('leakage_firewall', {}).get('blocked_fields', [])
            self.blocked_fields.update(blocked)
            logger.info(f"Loaded {len(blocked)} blocked fields from schema")
        except Exception as e:
            logger.warning(f"Could not load schema blocked fields: {e}")
    
    def check_columns(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        """
        Check DataFrame for blocked columns.
        
        Args:
            df: DataFrame to check
            
        Returns:
            Dictionary with 'blocked' and 'allowed' column lists
        """
        df_cols = set(df.columns)
        blocked = df_cols.intersection(self.blocked_fields)
        allowed = df_cols - self.blocked_fields
        
        return {
            'blocked': sorted(list(blocked)),
            'allowed': sorted(list(allowed))
        }
    
    def validate_columns(self, df: pd.DataFrame, strict: bool = True) -> bool:
        """
        Validate that DataFrame contains no blocked columns.
        
        Args:
            df: DataFrame to validate
            strict: If True, raise exception on violation. If False, log warning.
            
        Returns:
            True if valid, False if blocked columns found
        """
        check = self.check_columns(df)
        
        if check['blocked']:
            msg = f"LEAKAGE DETECTED: Blocked columns found: {check['blocked']}"
            
            if strict:
                logger.error(msg)
                raise ValueError(msg)
            else:
                logger.warning(msg)
                return False
        
        logger.info("✓ Leakage firewall: No blocked columns detected")
        return True
    
    def validate_timestamps(
        self, 
        df: pd.DataFrame, 
        decision_timestamp: datetime,
        timestamp_col: str = 'timestamp',
        strict: bool = True
    ) -> bool:
        """
        Validate that all data timestamps are <= decision_timestamp.
        
        Args:
            df: DataFrame to validate
            decision_timestamp: Decision time (no data after this)
            timestamp_col: Name of timestamp column
            strict: If True, raise exception on violation
            
        Returns:
            True if valid, False if future data found
        """
        if timestamp_col not in df.columns:
            logger.warning(f"Timestamp column '{timestamp_col}' not found. Skipping timestamp validation.")
            return True
        
        # Convert to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
        
        # Find future data
        future_mask = df[timestamp_col] > decision_timestamp
        future_count = future_mask.sum()
        
        if future_count > 0:
            msg = f"LEAKAGE DETECTED: {future_count} rows have timestamps > decision_timestamp"
            
            if strict:
                logger.error(msg)
                logger.error(f"Decision timestamp: {decision_timestamp}")
                logger.error(f"Latest data timestamp: {df[timestamp_col].max()}")
                raise ValueError(msg)
            else:
                logger.warning(msg)
                return False
        
        logger.info(f"✓ Leakage firewall: All timestamps <= {decision_timestamp}")
        return True
    
    def clean_dataframe(
        self, 
        df: pd.DataFrame,
        decision_timestamp: Optional[datetime] = None,
        timestamp_col: str = 'timestamp'
    ) -> pd.DataFrame:
        """
        Remove blocked columns and future data from DataFrame.
        
        Args:
            df: DataFrame to clean
            decision_timestamp: Optional decision timestamp for filtering
            timestamp_col: Name of timestamp column
            
        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()
        
        # Remove blocked columns
        check = self.check_columns(df_clean)
        if check['blocked']:
            logger.info(f"Removing {len(check['blocked'])} blocked columns: {check['blocked']}")
            df_clean = df_clean.drop(columns=check['blocked'])
        
        # Filter future data
        if decision_timestamp and timestamp_col in df_clean.columns:
            if not pd.api.types.is_datetime64_any_dtype(df_clean[timestamp_col]):
                df_clean[timestamp_col] = pd.to_datetime(df_clean[timestamp_col], errors='coerce')
            
            before_count = len(df_clean)
            df_clean = df_clean[df_clean[timestamp_col] <= decision_timestamp]
            after_count = len(df_clean)
            
            if before_count > after_count:
                logger.info(f"Filtered {before_count - after_count} rows with future timestamps")
        
        logger.info(f"✓ DataFrame cleaned: {len(df_clean)} rows, {len(df_clean.columns)} columns")
        return df_clean
    
    def audit_log(
        self, 
        df: pd.DataFrame,
        decision_timestamp: Optional[datetime] = None,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        Generate audit log for leakage firewall checks.
        
        Args:
            df: DataFrame to audit
            decision_timestamp: Optional decision timestamp
            output_path: Optional path to save audit log JSON
            
        Returns:
            Audit log dictionary
        """
        audit = {
            'timestamp': datetime.now().isoformat(),
            'decision_timestamp': decision_timestamp.isoformat() if decision_timestamp else None,
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'column_check': self.check_columns(df),
            'blocked_fields_config': sorted(list(self.blocked_fields))
        }
        
        # Timestamp validation if applicable
        if decision_timestamp and 'timestamp' in df.columns:
            df_ts = pd.to_datetime(df['timestamp'], errors='coerce')
            future_count = (df_ts > decision_timestamp).sum()
            audit['timestamp_validation'] = {
                'future_rows': int(future_count),
                'valid': future_count == 0
            }
        
        # Save if path provided
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(audit, f, indent=2)
            logger.info(f"✓ Audit log saved: {output_path}")
        
        return audit


def validate_training_data(
    df: pd.DataFrame,
    strict: bool = True
) -> bool:
    """
    Validate training data for leakage.
    
    Args:
        df: Training DataFrame
        strict: If True, raise exception on violation
        
    Returns:
        True if valid
    """
    firewall = LeakageFirewall()
    return firewall.validate_columns(df, strict=strict)


def validate_inference_data(
    df: pd.DataFrame,
    decision_timestamp: datetime,
    strict: bool = True
) -> bool:
    """
    Validate inference data for leakage.
    
    Args:
        df: Inference DataFrame
        decision_timestamp: Decision time
        strict: If True, raise exception on violation
        
    Returns:
        True if valid
    """
    firewall = LeakageFirewall()
    
    # Check columns
    if not firewall.validate_columns(df, strict=strict):
        return False
    
    # Check timestamps
    if not firewall.validate_timestamps(df, decision_timestamp, strict=strict):
        return False
    
    return True


if __name__ == "__main__":
    # Example usage
    firewall = LeakageFirewall()
    
    # Test data with leakage
    df_bad = pd.DataFrame({
        'rpr': [95, 92, 88],
        'or': [90, 87, 85],
        'pos': [1, 2, 3],  # BLOCKED
        'sp': [3.5, 5.0, 8.0]  # BLOCKED
    })
    
    print("Testing leakage detection...")
    try:
        firewall.validate_columns(df_bad, strict=True)
    except ValueError as e:
        print(f"✓ Correctly caught leakage: {e}")
    
    # Clean data
    df_clean = firewall.clean_dataframe(df_bad)
    print(f"✓ Cleaned DataFrame: {df_clean.columns.tolist()}")
