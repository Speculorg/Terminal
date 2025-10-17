from enum import Enum

class EventEnum(str, Enum):
    HEARTBEAT = "HEARTBEAT"
    PUBLISH_STATE = "PUBLISH_STATE"
    WATCH = "WATCH"
    RELOAD = "RELOAD"
    REQUEST = "REQUEST"
    RETRY = "RETRY"
    TIMEOUT = "TIMEOUT"
