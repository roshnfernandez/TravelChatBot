from agents.flight_agent.agent import flight_agent_graph
from agents.hotel_agent.agent import hotel_agent_graph
from orchestrator.enums import IntentType

REQUIRED_FIELDS_BY_INTENT: dict[IntentType, list[str]] = {
    IntentType.FLIGHT : ["origin","destination","departure_date"],
    IntentType.HOTEL: ["destination_city","check_in_date","check_out_date"]
}

AGENT_REGISTRY = {
    IntentType.FLIGHT: {
        "graph": flight_agent_graph,
        "name": "call_flight_agent",
        "task_type": "flight_search"
    },
    IntentType.HOTEL: {
        "graph": hotel_agent_graph,
        "name": "call_hotel_agent",
        "task_type": "hotel_search"
    }
}

INTENT_META_DATA_FIELDS: set = {"intent_type", "active", "status", "missing_info", "created_on"}

INTENTS_TO_LOAD: int = 3