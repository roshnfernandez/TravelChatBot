import logging

from langgraph.graph import StateGraph, END
from orchestrator.ai_nodes import generate_response, parse_intent, summarize_context, summarize_task_response
from orchestrator.func_nodes import call_flight_agent, call_hotel_agent, validate_unprocessed_intents, \
    remove_old_invalid_intents
from orchestrator.models import OrchestratorState
from orchestrator.util import delegate_to_agents, route_to_summarizers

logger = logging.getLogger(__name__)

workflow = StateGraph(state_schema=OrchestratorState)  # type:ignore

workflow.add_node("parse", parse_intent)  # type:ignore
workflow.add_node("validate", validate_unprocessed_intents)  # type:ignore
workflow.add_node("call_flight_agent", call_flight_agent)  # type:ignore
workflow.add_node("call_hotel_agent", call_hotel_agent)  # type:ignore
workflow.add_node("generate_response", generate_response) # type:ignore
workflow.add_node("summarize_session", summarize_context) # type:ignore
workflow.add_node("summarize_tasks", summarize_task_response) # type:ignore
workflow.add_node("remove_old_intents", remove_old_invalid_intents) # type:ignore
workflow.add_node("aggregator", lambda x: x) # type:ignore

workflow.set_entry_point("parse")
workflow.add_edge("parse", "validate")

workflow.add_conditional_edges(
    "validate",
    delegate_to_agents,
    {
        "call_flight_agent": "call_flight_agent",
        "generate_response": "generate_response",
        "call_hotel_agent": "call_hotel_agent"
    }
)

workflow.add_edge("call_flight_agent", "generate_response")
workflow.add_edge("call_hotel_agent", "generate_response")

workflow.add_conditional_edges(
    "generate_response",
    route_to_summarizers,
    {
        "summarize_session": "summarize_session",
        "summarize_tasks": "summarize_tasks",
        "remove_old_intents": "remove_old_intents"
    }
)

workflow.add_edge("summarize_session", "aggregator")
workflow.add_edge("summarize_tasks", "aggregator")
workflow.add_edge("remove_old_intents", "aggregator")

workflow.add_edge("aggregator", END)

orchestrator_graph = workflow.compile()
