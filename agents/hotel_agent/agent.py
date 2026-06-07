from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from .schemas import A2AHotelTaskRequest, A2ATaskResponse, A2ATaskResponseMetadata
from .mock_data import search_hotels


# 1. Define the State
class HotelAgentState(TypedDict):
    request: Dict[str, Any]
    is_valid: bool
    validation_error: Optional[str]
    hotel_results: list
    response: Optional[Dict[str, Any]]


# 2. Define the Nodes
def validate_request(state: HotelAgentState):
    """Validates the incoming A2A request against the Pydantic schema."""
    req_data = state.get("request", {})
    try:
        validated_req = A2AHotelTaskRequest(**req_data)
        return {
            "is_valid": True,
            "validation_error": None,
            "request": validated_req.model_dump()
        }
    except Exception as e:
        return {
            "is_valid": False,
            "validation_error": f"Schema validation failed: {str(e)}"
        }


def retrieve_hotels(state: HotelAgentState):
    """Executes the search using the mock data layer."""
    req_data = state["request"]
    params = req_data.get("parameters", {})

    hotels = search_hotels(
        destination_city=params.get("destination_city"),
        check_in_date=params.get("check_in_date"),
        check_out_date=params.get("check_out_date"),
        number_of_guests=params.get("number_of_guests", 1),
        room_type_preference=params.get("room_type_preference"),
        location_preferences=params.get("location_preferences")
    )
    return {"hotel_results": hotels}


def format_response(state: HotelAgentState):
    """Packages the results or errors into the strict A2A Response schema."""
    req_data = state.get("request", {})
    task_id = req_data.get("task_id", "unknown-task-id")
    metadata = A2ATaskResponseMetadata(agent_id="hotel-agent")

    if not state.get("is_valid"):
        response = A2ATaskResponse(
            task_id=task_id,
            status="failed",
            error=state.get("validation_error"),
            metadata=metadata
        )
    elif not state.get("hotel_results"):
        response = A2ATaskResponse(
            task_id=task_id,
            status="success",
            results=[],
            clarification_needed="No hotels found for the requested city and dates.",
            metadata=metadata
        )
    else:
        response = A2ATaskResponse(
            task_id=task_id,
            status="success",
            results=state.get("hotel_results", []),
            metadata=metadata
        )

    return {"response": response.model_dump()}


# 3. Define Conditional Routing
def route_after_validation(state: HotelAgentState):
    """Routes to search if valid, otherwise skips directly to formatting the error."""
    if state.get("is_valid"):
        return "search"
    return "format"


# 4. Build the Graph
workflow = StateGraph(HotelAgentState)

workflow.add_node("validate", validate_request)
workflow.add_node("search", retrieve_hotels)
workflow.add_node("format", format_response)

workflow.set_entry_point("validate")
workflow.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "search": "search",
        "format": "format"
    }
)
workflow.add_edge("search", "format")
workflow.add_edge("format", END)

# Compile the runnable graph
hotel_agent_graph = workflow.compile()