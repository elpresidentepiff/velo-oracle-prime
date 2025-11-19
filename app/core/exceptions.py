"""
Custom exceptions for VÉLØ Oracle API
"""
from fastapi import HTTPException, status


class APIException(HTTPException):
    """Base API exception"""
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(status_code=status_code, detail=detail)


class ValidationError(APIException):
    """Raised when request validation fails"""
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Validation error: {detail}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class ModelNotFoundError(APIException):
    """Raised when requested model is not found"""
    def __init__(self, model_name: str):
        super().__init__(
            detail=f"Model '{model_name}' not found in registry",
            status_code=status.HTTP_404_NOT_FOUND
        )


class ServiceUnavailable(APIException):
    """Raised when a required service is unavailable"""
    def __init__(self, service: str):
        super().__init__(
            detail=f"Service '{service}' is currently unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class InternalModelFailure(APIException):
    """Raised when model inference fails"""
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Model inference failed: {detail}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class FeatureEngineeringError(APIException):
    """Raised when feature engineering fails"""
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Feature engineering error: {detail}",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

