from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from .schemas import A2AFlightTaskRequest, A2ATaskResponse, A2ATaskResponseMetadata
from .mock_data import search_flights


# 1. Define the State
class FlightAgentState(TypedDict):
    request: Dict[str, Any]
    is_valid: bool
    validation_error: Optional[str]
    flight_results: list
    response: Optional[Dict[str, Any]]


# 2. Define the Nodes
def validate_request(state: FlightAgentState):
    """Validates the incoming A2A request against the Pydantic schema."""
    req_data = state.get("request", {})
    try:
        validated_req = A2AFlightTaskRequest(**req_data)
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


def retrieve_flights(state: FlightAgentState):
    """Executes the search using the mock data layer."""
    req_data = state["request"]
    params = req_data.get("parameters", {})

    flights = search_flights(
        origin=params.get("origin"),
        destination=params.get("destination"),
        departure_date=params.get("departure_date"),
        return_date=params.get("return_date"),
        passengers=params.get("passengers", 1),
        cabin_class=params.get("cabin_class", "economy")
    )
    return {"flight_results": flights}


def format_response(state: FlightAgentState):
    """Packages the results or errors into the strict A2A Response schema."""
    req_data = state.get("request", {})
    task_id = req_data.get("task_id", "unknown-task-id")
    metadata = A2ATaskResponseMetadata(agent_id="flight-agent")

    if not state.get("is_valid"):
        response = A2ATaskResponse(
            task_id=task_id,
            status="failed",
            error=state.get("validation_error"),
            metadata=metadata
        )
    elif not state.get("flight_results"):
        response = A2ATaskResponse(
            task_id=task_id,
            status="success",
            results=[],
            clarification_needed="No flights found for the requested route and dates.",
            metadata=metadata
        )
    else:
        response = A2ATaskResponse(
            task_id=task_id,
            status="success",
            results=state.get("flight_results", []),
            metadata=metadata
        )

    return {"response": response.model_dump()}


# 3. Define Conditional Routing
def route_after_validation(state: FlightAgentState):
    """Routes to search if valid, otherwise skips directly to formatting the error."""
    if state.get("is_valid"):
        return "search"
    return "format"


# 4. Build the Graph
workflow = StateGraph(FlightAgentState)

workflow.add_node("validate", validate_request)
workflow.add_node("search", retrieve_flights)
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
flight_agent_graph = workflow.compile()