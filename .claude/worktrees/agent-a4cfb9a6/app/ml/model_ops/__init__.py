"""
VÉLØ Oracle - Model Ops
Model operations and lifecycle management
"""
from .loader import (
    load_sqpe,
    load_tie,
    load_longshot,
    load_overlay,
    load_model_by_name,
    load_all_models,
    get_loaded_models
)

from .validator import (
    validate_model_schema,
    validate_feature_map,
    validate_version,
    validate_model_complete,
    validate_prediction_output
)

from .registry_manager import (
    register_model_run,
    list_model_runs,
    get_model_performance,
    register_model_version,
    promote_model_version,
    get_production_version
)

__all__ = [
    # Loader
    "load_sqpe",
    "load_tie",
    "load_longshot",
    "load_overlay",
    "load_model_by_name",
    "load_all_models",
    "get_loaded_models",
    
    # Validator
    "validate_model_schema",
    "validate_feature_map",
    "validate_version",
    "validate_model_complete",
    "validate_prediction_output",
    
    # Registry
    "register_model_run",
    "list_model_runs",
    "get_model_performance",
    "register_model_version",
    "promote_model_version",
    "get_production_version"
]
