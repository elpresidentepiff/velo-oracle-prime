"""
VÉLØ Oracle - Model Ops Registry Manager
Model run tracking and performance registry
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_model_run(metadata: Dict[str, Any]) -> bool:
    """
    Register a model training/evaluation run
    
    Args:
        metadata: Run metadata including:
            - model_name
            - version
            - metrics
            - config
            - dataset_info
            
    Returns:
        Success status
    """
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        # Prepare run data
        run_data = {
            "model_name": metadata.get("model_name"),
            "version": metadata.get("version"),
            "run_type": metadata.get("run_type", "training"),
            "dataset_size": metadata.get("dataset_size", 0),
            "config": metadata.get("config", {}),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Insert into model_runs table
        result = db.client.table("model_runs").insert(run_data).execute()
        
        run_id = result.data[0]["id"] if result.data else None
        
        if not run_id:
            logger.error("❌ Failed to get run ID")
            return False
        
        # Register metrics
        metrics = metadata.get("metrics", {})
        if metrics:
            _register_metrics(db, run_id, metadata["model_name"], metrics)
        
        logger.info(f"✅ Model run registered: {metadata['model_name']} {metadata['version']}")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to register model run: {e}")
        return False


def _register_metrics(db, run_id: int, model_name: str, metrics: Dict[str, float]) -> None:
    """Register metrics for a model run"""
    
    try:
        metrics_data = {
            "run_id": run_id,
            "model_name": model_name,
            "accuracy": metrics.get("accuracy"),
            "auc": metrics.get("auc"),
            "log_loss": metrics.get("log_loss"),
            "roi": metrics.get("roi"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "f1_score": metrics.get("f1_score"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        db.client.table("model_metrics").insert(metrics_data).execute()
        logger.info(f"✅ Metrics registered for run {run_id}")
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to register metrics: {e}")


def list_model_runs(limit: int = 20, model_name: str = None) -> List[Dict[str, Any]]:
    """
    List recent model runs
    
    Args:
        limit: Maximum number of runs to return
        model_name: Optional filter by model name
        
    Returns:
        List of model run records
    """
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        query = db.client.table("model_runs").select("*")
        
        if model_name:
            query = query.eq("model_name", model_name)
        
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        logger.info(f"✅ Retrieved {len(result.data)} model runs")
        return result.data
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to list model runs: {e}")
        return []


def get_model_performance(model_name: str, version: str = None) -> Optional[Dict[str, Any]]:
    """
    Get performance metrics for a model
    
    Args:
        model_name: Model name
        version: Optional specific version
        
    Returns:
        Performance metrics dictionary or None
    """
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        # Get latest run for this model
        query = db.client.table("model_runs").select("*").eq("model_name", model_name)
        
        if version:
            query = query.eq("version", version)
        
        result = query.order("created_at", desc=True).limit(1).execute()
        
        if not result.data:
            logger.warning(f"⚠️ No runs found for model: {model_name}")
            return None
        
        run = result.data[0]
        run_id = run["id"]
        
        # Get metrics for this run
        metrics_result = db.client.table("model_metrics") \
            .select("*") \
            .eq("run_id", run_id) \
            .execute()
        
        if not metrics_result.data:
            logger.warning(f"⚠️ No metrics found for run: {run_id}")
            return None
        
        metrics = metrics_result.data[0]
        
        performance = {
            "model_name": model_name,
            "version": run["version"],
            "run_date": run["created_at"],
            "metrics": {
                "accuracy": metrics.get("accuracy"),
                "auc": metrics.get("auc"),
                "log_loss": metrics.get("log_loss"),
                "roi": metrics.get("roi"),
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1_score": metrics.get("f1_score")
            }
        }
        
        logger.info(f"✅ Retrieved performance for {model_name}")
        return performance
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to get model performance: {e}")
        return None


def register_model_version(
    model_name: str,
    version: str,
    status: str = "development",
    notes: str = None
) -> bool:
    """
    Register a new model version
    
    Args:
        model_name: Model name
        version: Version string
        status: Version status (development/staging/production)
        notes: Optional notes
        
    Returns:
        Success status
    """
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        version_data = {
            "model_name": model_name,
            "version": version,
            "status": status,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat()
        }
        
        db.client.table("model_versions").insert(version_data).execute()
        
        logger.info(f"✅ Model version registered: {model_name} {version}")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to register model version: {e}")
        return False


def promote_model_version(model_name: str, version: str, to_status: str = "production") -> bool:
    """
    Promote model version to new status
    
    Args:
        model_name: Model name
        version: Version to promote
        to_status: Target status (staging/production)
        
    Returns:
        Success status
    """
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        # Update version status
        db.client.table("model_versions") \
            .update({"status": to_status}) \
            .eq("model_name", model_name) \
            .eq("version", version) \
            .execute()
        
        logger.info(f"✅ Model promoted: {model_name} {version} -> {to_status}")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to promote model: {e}")
        return False


def get_production_version(model_name: str) -> Optional[str]:
    """
    Get current production version for a model
    
    Args:
        model_name: Model name
        
    Returns:
        Production version string or None
    """
    try:
        from src.data.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        result = db.client.table("model_versions") \
            .select("version") \
            .eq("model_name", model_name) \
            .eq("status", "production") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        if result.data:
            version = result.data[0]["version"]
            logger.info(f"✅ Production version: {model_name} {version}")
            return version
        else:
            logger.warning(f"⚠️ No production version for: {model_name}")
            return None
            
    except Exception as e:
        logger.warning(f"⚠️ Failed to get production version: {e}")
        return None
