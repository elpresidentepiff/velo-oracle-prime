"""Service layer — lazy imports to avoid circular / missing-module crashes at startup."""

__all__ = [
    "model_registry",
    "model_loader",
    "predictor",
    "validator",
]


def __getattr__(name):
    if name == "model_registry":
        from app.services.model_registry import model_registry
        return model_registry
    if name == "model_loader":
        from app.services.model_loader import model_loader
        return model_loader
    if name == "predictor":
        from app.services.predictor import predictor
        return predictor
    if name == "validator":
        from app.services.validation import validator
        return validator
    raise AttributeError(f"module 'app.services' has no attribute {name!r}")

