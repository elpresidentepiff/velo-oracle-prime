"""
Monitoring API Router
Provides endpoints for model monitoring via Evidently AI
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import sys
sys.path.insert(0, '/home/ubuntu/velo-oracle')

import pandas as pd
from pathlib import Path
from src.monitoring.evidently_monitor import VeloModelMonitor

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Initialize Evidently monitor
try:
    monitor = VeloModelMonitor()
    print("✓ Evidently Monitor initialized")
except Exception as e:
    print(f"⚠ Failed to initialize Evidently: {e}")
    monitor = None


class DriftCheckRequest(BaseModel):
    """Request model for drift check."""
    production_data_path: Optional[str] = None
    drift_threshold: float = 0.3


class DriftCheckResponse(BaseModel):
    """Response model for drift check."""
    drift_detected: bool
    drift_share: float
    drifted_columns: int
    total_columns: int
    threshold: float
    timestamp: str
    recommendation: str


@router.post("/check_drift", response_model=DriftCheckResponse)
async def check_drift(request: DriftCheckRequest):
    """
    Check for data drift.
    
    Compares recent production data against reference (training) data.
    """
    if monitor is None:
        raise HTTPException(status_code=503, detail="Monitor not available")
    
    try:
        # Load reference data
        reference_path = Path("/home/ubuntu/velo-oracle/reports/evidently/reference/reference_data.parquet")
        
        if not reference_path.exists():
            raise HTTPException(status_code=404, detail="Reference data not found")
        
        reference_data = pd.read_parquet(reference_path)
        
        # Load production data (use reference as placeholder if not provided)
        if request.production_data_path:
            current_data = pd.read_parquet(request.production_data_path)
        else:
            # Use last 500 records from reference as "current" for testing
            current_data = reference_data.tail(500)
        
        # Check for drift
        drift_status = monitor.check_for_drift(
            reference_data=reference_data,
            current_data=current_data,
            drift_threshold=request.drift_threshold
        )
        
        # Add recommendation
        if drift_status['drift_detected']:
            recommendation = "RETRAIN MODEL - Significant drift detected"
        else:
            recommendation = "Continue monitoring - No significant drift"
        
        return DriftCheckResponse(
            drift_detected=drift_status['drift_detected'],
            drift_share=drift_status['drift_share'],
            drifted_columns=drift_status['drifted_columns'],
            total_columns=drift_status['total_columns'],
            threshold=drift_status['threshold'],
            timestamp=drift_status['timestamp'],
            recommendation=recommendation
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Drift check failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Check if monitoring is operational."""
    if monitor is None:
        return {
            "status": "degraded",
            "message": "Monitor not initialized"
        }
    
    return {
        "status": "healthy",
        "message": "Monitor operational"
    }


@router.get("/reports")
async def list_reports():
    """List available monitoring reports."""
    if monitor is None:
        raise HTTPException(status_code=503, detail="Monitor not available")
    
    try:
        reports_dir = monitor.reports_dir
        
        # List HTML reports
        html_reports = list(reports_dir.glob("*.html"))
        json_reports = list(reports_dir.glob("*.json"))
        
        return {
            "reports_directory": str(reports_dir),
            "html_reports": [r.name for r in html_reports],
            "json_reports": [r.name for r in json_reports],
            "total_reports": len(html_reports) + len(json_reports)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")


@router.get("/stats")
async def get_monitoring_stats():
    """Get monitoring statistics."""
    if monitor is None:
        raise HTTPException(status_code=503, detail="Monitor not available")
    
    try:
        # Load reference data
        reference_path = Path("/home/ubuntu/velo-oracle/reports/evidently/reference/reference_data.parquet")
        
        if not reference_path.exists():
            return {
                "reference_data_loaded": False,
                "message": "Reference data not found"
            }
        
        reference_data = pd.read_parquet(reference_path)
        
        return {
            "reference_data_loaded": True,
            "reference_records": len(reference_data),
            "reference_features": len(reference_data.columns),
            "reports_directory": str(monitor.reports_dir)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
