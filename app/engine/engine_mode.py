from enum import StrEnum


class EngineMode(StrEnum):
    PROD = "prod"
    SQPE_DIRECT = "sqpe_direct"
    SUPPRESSION_ONLY = "suppression_only"
    HYBRID = "hybrid"
