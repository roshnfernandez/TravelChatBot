from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from agents.flight_agent.schemas import A2AFlightTaskRequest, A2ATaskResponse, A2ATaskResponseMetadata
from .mock_data import search_flights

class FlightAgentState(TypedDict):
    request: Dict[str, Any]       # The raw incoming A2A JSON
    is_valid: bool                # Flag for routing
    validation_error: Optional[str]
    flight_results: list          # The raw output from the mock DB
    response: Dict[str, Any]      # The final strict A2A Response JSON

def validate_request(state: FlightAgentState) -> dict:
    """Validates the incoming A2A request against the Pydantic schema."""
    req_data = state.get("request", {})
    try:
        # Pydantic will raise an error if required fields are missing
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

def retrieve_flights(state: FlightAgentState) -> dict:
    """Executes the search using the mock data layer."""
    req_data = state["request"]
    params = req_data.get("parameters", {})

    # Call the mock DB function
    flights = search_flights(
        origin=params.get("origin"),
        destination=params.get("destination"),
        departure_date=params.get("departure_date"),
        return_date=params.get("return_date"),
        passengers=params.get("passengers", 1),
        cabin_class=params.get("cabin_class", "economy")
    )
    return {"flight_results": flights}

def format_response(state: FlightAgentState) -> dict:
    """Packages the results or errors into the strict A2A Response schema."""
    req_data = state.get("request", {})
    task_id = req_data.get("task_id", "unknown-task-id")
    metadata = A2ATaskResponseMetadata(agent_id="flight-agent")

    # Path A: Validation Failed
    if not state.get("is_valid"):
        response = A2ATaskResponse(
            task_id=task_id,
            status="failed",
            error=state.get("validation_error"),
            metadata=metadata
        )
    # Path B: Search Valid, but No Flights Found
    elif not state.get("flight_results"):
        response = A2ATaskResponse(
            task_id=task_id,
            status="needs_clarification", # Still a successful execution, just no data
            results=[],
            clarification_needed="No flights found for the requested route and dates. Please try different dates or airports.",
            metadata=metadata
        )
    # Path C: Success
    else:
        response = A2ATaskResponse(
            task_id=task_id,
            status="success",
            results=state.get("flight_results", []),
            metadata=metadata
        )

    # Dump to JSON-ready dict for the Orchestrator
    return {"response": response.model_dump()}

def route_after_validation(state: FlightAgentState) -> str:
    """Routes to search if valid, otherwise skips directly to formatting the error."""
    if state.get("is_valid"):
        return "search"
    return "format"

# --- 4. Build the Graph ---
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

flight_agent_graph = workflow.compile()