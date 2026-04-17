"""
Structured logging configuration using loguru
"""
import sys
import json
from loguru import logger
from app.core.config import settings


def serialize_log(record):
    """Serialize log record to JSON format"""
    subset = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }
    
    # Add extra fields if present
    if record["extra"]:
        subset["extra"] = record["extra"]
    
    return json.dumps(subset)


def setup_logging():
    """Configure loguru for production logging"""
    
    # Remove default handler
    logger.remove()
    
    if settings.LOG_JSON:
        # JSON logging for production
        logger.add(
            sys.stdout,
            format=serialize_log,
            level=settings.LOG_LEVEL,
            serialize=False,
        )
    else:
        # Human-readable logging for development
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=settings.LOG_LEVEL,
        )
    
    return logger


# Initialize logger
log = setup_logging()

