import json
import logging
import uuid
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from orchestrator.const import REQUIRED_FIELDS_BY_INTENT, AGENT_REGISTRY, INTENT_META_DATA_FIELDS
from orchestrator.enums import IntentStatus, IntentType
from orchestrator.models import OrchestratorState, HotelIntent, FlightIntent, AgentTask
from orchestrator.prompts import INTENT_PARSER_SYSTEM_PROMPT, RESPONSE_GENERATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def parse_intent(state: OrchestratorState) -> dict:
    """Uses an LLM to analyze the conversation and extract structured intent/parameters."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(list[HotelIntent | FlightIntent])
    system_prompt: str = INTENT_PARSER_SYSTEM_PROMPT
    invalid_active_intents = [intent for intent in  state.get("intents", []) if intent.active and intent.status == IntentStatus.INVALID]
    if invalid_active_intents:
        system_prompt += "### PREVIOUS UNFILLED INTENTS ###\n"
        for ints in invalid_active_intents:
            system_prompt+=(
                "```json```"
                f"\n{ints.model_dump_json(exclude_none=True)}\n"
                "```json```"
            )
    # Pass the system prompt and the conversation history
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    intents: list[HotelIntent | FlightIntent] = structured_llm.invoke(messages)

    return {"intents": intents}

def validate_unprocessed_intents(state: OrchestratorState) -> dict:
    for intent in state.get("intents", []):
        if intent.status in [IntentStatus.NEW, IntentStatus.MODIFIED]:
            intent.missing_info = []
            fields_to_look_for: list[str] = REQUIRED_FIELDS_BY_INTENT[intent.intent_type]
            logger.info(f"Unprocessed intent detected of type - {intent.intent_type}, validating fields {fields_to_look_for}")
            for field in fields_to_look_for:
                if getattr(intent, field, None) is None:
                    intent.missing_info.append(field)
            intent.status = IntentStatus.INVALID if intent.missing_info else IntentStatus.VALID
    return {"intents": state.get("intents", [])}


def call_flight_agent(state: OrchestratorState):
    """Explicit node for Flight Agent delegation."""
    return _invoke_agent(state, IntentType.FLIGHT)


def call_hotel_agent(state: OrchestratorState):
    """Explicit node for Hotel Agent delegation."""
    return _invoke_agent(state, IntentType.HOTEL)


def _invoke_agent(state: OrchestratorState, target_intent_type: IntentType):
    """Helper function to handle the A2A protocol and status updates."""
    valid_intents = [i for i in state.get("intents", []) if
                     i.status == IntentStatus.VALID and i.active and i.intent_type == target_intent_type]

    new_agent_responses = {}

    for intent in valid_intents:
        agent_config = AGENT_REGISTRY[target_intent_type]
        task_id = str(uuid.uuid4())

        # Build A2A Request
        req_payload = {
            "task_id": task_id,
            "session_id": state.get("session_id", str(uuid.uuid4())),
            "task_type": agent_config["task_type"],
            "parameters": intent.model_dump(exclude=INTENT_META_DATA_FIELDS)
        }

        # Invoke the sub-graph
        result = agent_config["graph"].invoke({"request": req_payload})
        response_data = result.get("response", {})
        status = response_data.get("status")
        if status in ["failed", "needs_clarification"]:
            intent.status = IntentStatus.INVALID
            # Save the error so the LLM knows what to ask the user
            error_msg = response_data.get("clarification_needed") or response_data.get("error") or "Unknown error."
            if error_msg not in intent.missing_info:
                intent.missing_info.append(f"Agent Error: {error_msg}")

        # Record the task
        new_agent_responses[task_id] = AgentTask(
            task_id=task_id,
            agent_name=agent_config["name"],
            agent_request=json.dumps(req_payload),
            agent_response=json.dumps(response_data),
            processed=False
        )

    return {"agent_responses": new_agent_responses, "intents": state.get("intents", [])}

def delegate_to_agents(state: OrchestratorState) -> list[str]:
    """
    Returns a list of nodes to execute in parallel.
    Routes to Flight, Hotel, Both, or Neither!
    """
    routes = []
    for intent in state.get("intents", []):
        if intent.status == IntentStatus.VALID and intent.active:
            if intent.intent_type == IntentType.FLIGHT:
                routes.append("call_flight_agent")
            elif intent.intent_type == IntentType.HOTEL:
                routes.append("call_hotel_agent")

    # Deduplicate in case there are multiple of the same type
    routes = list(set(routes))

    # If no valid active intents, go straight to chatting (Neither)
    if not routes:
        return ["generate_response"]

    return routes

def generate_response(state: OrchestratorState) -> dict[str, Any]:
    """Generates the final conversational response based on valid agent executions and missing info."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    #Extract what needs clarification (Active but INVALID)
    missing_details_context = []
    for intent in state.get("intents", []):
        if intent.active and intent.status == IntentStatus.INVALID:
            missing_details_context.append(
                f"- For {intent.intent_type}: Need {', '.join(intent.missing_info)}"
            )

    agent_results = [json.loads(task.agent_response) for task in state.get("agent_responses", {}).values() if not task.processed]

    system_prompt = RESPONSE_GENERATOR_SYSTEM_PROMPT

    if agent_results:
        system_prompt += "### AGENT RESULTS (Format these nicely for the user) ###\n"
        system_prompt += f"{json.dumps(agent_results)}\n\n"

    if missing_details_context:
        system_prompt += "### MISSING INFORMATION (Politely ask the user for these specific details) ###\n"
        system_prompt += "\n".join(missing_details_context) + "\n\n"

    if not agent_results and not missing_details_context:
        system_prompt += "No active bookings right now. Just chat nicely with the user!"

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)

    #Mark agent responses as processed
    agent_responses = state.get("agent_responses", {})
    for resp_key in agent_responses:
        agent_responses[resp_key].processed = True

    return {
        "messages": [response],
        "agent_responses": agent_responses
    }


workflow = StateGraph(state_schema=OrchestratorState) #type:ignore

workflow.add_node("parse", parse_intent) #type:ignore
workflow.add_node("validate", validate_unprocessed_intents) #type:ignore
workflow.add_node("call_flight_agent", call_flight_agent) #type:ignore
workflow.add_node("call_hotel_agent", call_hotel_agent) #type:ignore
workflow.add_node("generate_response", generate_response) #type:ignore

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
workflow.add_edge("generate_response", END)

orchestrator_graph = workflow.compile()