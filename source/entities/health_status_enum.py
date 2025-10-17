from enum import Enum

class HealthStatusEnum(str, Enum):
    PASSING = "PASSING"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    MAINTENANCE = "MAINTENANCE"
