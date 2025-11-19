"""
VÉLØ Oracle - System Schemas
Data models for system diagnostics and monitoring
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ModelInfo(BaseModel):
    """Model information schema"""
    name: str = Field(..., description="Model name")
    version: str = Field(..., description="Model version")
    type: str = Field(..., description="Model type (e.g., gradient_boosting)")
    status: str = Field(..., description="Model status (loaded/not_loaded)")
    loaded: bool = Field(..., description="Whether model is loaded")
    performance: Optional[Dict[str, float]] = Field(None, description="Performance metrics")


class ModelsResponse(BaseModel):
    """Response schema for /v1/system/models"""
    status: str = Field(..., description="Response status")
    initialized: bool = Field(..., description="Whether model manager is initialized")
    models_loaded: int = Field(..., description="Number of models loaded")
    models: Dict[str, ModelInfo] = Field(..., description="Model details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class FeatureCategory(BaseModel):
    """Feature category schema"""
    name: str = Field(..., description="Category name")
    features: List[str] = Field(..., description="Features in this category")
    count: int = Field(..., description="Number of features")


class FeaturesResponse(BaseModel):
    """Response schema for /v1/system/features"""
    status: str = Field(..., description="Response status")
    feature_count: int = Field(..., description="Total number of features")
    features: List[str] = Field(..., description="List of all features")
    categories: Dict[str, List[str]] = Field(..., description="Features by category")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class BacktestSummary(BaseModel):
    """Backtest summary schema"""
    backtest_id: str = Field(..., description="Backtest identifier")
    version: str = Field(..., description="Backtest version")
    sample_size: int = Field(..., description="Number of samples")
    roi: float = Field(..., description="Return on investment")
    win_rate: float = Field(..., description="Win rate")
    auc: float = Field(..., description="AUC score")
    log_loss: float = Field(..., description="Log loss")
    max_drawdown: float = Field(..., description="Maximum drawdown")
    num_bets: int = Field(..., description="Number of bets")
    status: str = Field(..., description="Backtest status")
    created_at: str = Field(..., description="Creation timestamp")


class BacktestsResponse(BaseModel):
    """Response schema for /v1/system/backtests"""
    status: str = Field(..., description="Response status")
    count: int = Field(..., description="Number of backtests returned")
    backtests: List[BacktestSummary] = Field(..., description="List of backtest summaries")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ComponentStatus(BaseModel):
    """Component status schema"""
    status: str = Field(..., description="Component status")
    type: Optional[str] = Field(None, description="Component type")
    count: Optional[int] = Field(None, description="Count (for models/features)")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class DiagnosticsResponse(BaseModel):
    """Response schema for /v1/system/diagnostics"""
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    version: str = Field(..., description="System version")
    components: Dict[str, ComponentStatus] = Field(..., description="Component statuses")
    system: Dict[str, str] = Field(..., description="System information")
