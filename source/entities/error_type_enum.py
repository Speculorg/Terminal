from enum import Enum

class ErrorTypeEnum(str, Enum):
    RECOVERABLE = "RECOVERABLE"
    FATAL = "FATAL"
