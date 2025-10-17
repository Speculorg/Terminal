from enum import Enum

class RunModeEnum(str, Enum):
    FIRST = "FIRST"
    RECOVERY = "RECOVERY"
    NORMAL = "NORMAL"
