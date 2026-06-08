from enum import Enum


class IntentStatus(Enum):
    NEW = "new"
    MODIFIED = "modified"
    INVALID = "invalid"
    VALID = "send_to_agent"
    PROCESSED_BY_AGENT = "processed_by_agent"
    CONFIRMED = "confirmed"


class IntentType(Enum):
    FLIGHT = "flight"
    HOTEL = "hotel"
