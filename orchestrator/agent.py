import json
import logging
import uuid
from typing import Any

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from orchestrator.const import REQUIRED_FIELDS_BY_INTENT, AGENT_REGISTRY, INTENT_META_DATA_FIELDS
from orchestrator.enums import IntentStatus, IntentType
from orchestrator.models import OrchestratorState, HotelIntent, FlightIntent, AgentTask, IntentExtraction
from orchestrator.prompts import INTENT_PARSER_SYSTEM_PROMPT, RESPONSE_GENERATOR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def parse_intent(state: OrchestratorState) -> dict:
    """Uses an LLM to analyze the conversation and extract structured intent/parameters."""
    logger.info("--- NODE: PARSE INTENT ---")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(IntentExtraction, method="function_calling")
    system_prompt: str = INTENT_PARSER_SYSTEM_PROMPT
    invalid_active_intents = [intent for intent in  state.get("intents", []) if intent.active and intent.status == IntentStatus.INVALID]
    valid_active_intents = [intent for intent in state.get("intents", []) if intent.active and intent.status == IntentStatus.VALID]
    if invalid_active_intents:
        logger.debug(f"Injecting {len(invalid_active_intents)} invalid/incomplete intents into context.")
        system_prompt += "### PREVIOUS UNFILLED INTENTS ###\n"
        for ints in invalid_active_intents:
            system_prompt += f"```json\n{ints.model_dump_json(exclude_none=True)}\n```\n"
    if valid_active_intents:
        logger.debug(f"Injecting {len(valid_active_intents)} valid intents into context.")
        system_prompt += "### PREVIOUS VALID INTENTS ###\n"
        for ints in valid_active_intents:
            system_prompt += f"```json\n{ints.model_dump_json(exclude_none=True)}\n```\n"

    all_tasks = list(state.get("agent_responses", {}).values())
    # Sort to get the most recent tasks first, and grab the top 2
    recent_tasks = sorted(all_tasks, key=lambda x: x.created_on, reverse=True)[:2]

    if recent_tasks:
        logger.debug(f"Injecting {len(recent_tasks)} recent agent payloads into context.")
        system_prompt += "### RECENT AGENT SEARCH RESULTS (AVAILABLE FOR BOOKING) ###\n"
        system_prompt += "Use these exact JSON blocks to populate the `booked_entity` if the user confirms a booking.\n"
        for task in recent_tasks:
            system_prompt += f"--- Agent: {task.agent_name} ---\n"
            system_prompt += f"```json\n{task.agent_response}\n```\n\n"

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    logger.debug("Invoking LLM for structured intent extraction...")
    intent_wrapper: IntentExtraction = structured_llm.invoke(messages)
    intents: list[HotelIntent | FlightIntent] = intent_wrapper.extracted_intents

    return {"intents": intents}

#TODO: Add better router
def validate_unprocessed_intents(state: OrchestratorState) -> dict:
    logger.info("--- NODE: VALIDATE INTENTS ---")
    for intent in state["intents"]:
        if intent.status in [IntentStatus.NEW, IntentStatus.MODIFIED]:
            intent.missing_info = []
            fields_to_look_for: list[str] = REQUIRED_FIELDS_BY_INTENT[intent.intent_type]
            logger.info(f"Unprocessed intent detected of type - {intent.intent_type}, validating fields {fields_to_look_for}")
            for field in fields_to_look_for:
                if getattr(intent, field, None) is None:
                    intent.missing_info.append(field)

            if intent.missing_info:
                intent.status = IntentStatus.INVALID
                logger.warning(f"Intent {intent.intent_type} is INVALID. Missing fields: {intent.missing_info}")
            else:
                intent.status = IntentStatus.VALID
                logger.info(f"Intent {intent.intent_type} is VALID. Ready for delegation.")

    return {}


def call_flight_agent(state: OrchestratorState):
    """Explicit node for Flight Agent delegation."""
    logger.info("--- NODE: CALL FLIGHT AGENT ---")
    return _invoke_agent(state, IntentType.FLIGHT)


def call_hotel_agent(state: OrchestratorState):
    """Explicit node for Hotel Agent delegation."""
    logger.info("--- NODE: CALL HOTEL AGENT ---")
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

        logger.debug(f"A2A Request Payload for {agent_config['name']}: {json.dumps(req_payload)}")

        # Invoke the sub-graph
        result = agent_config["graph"].invoke({"request": req_payload})
        response_data = result.get("response", {})

        logger.debug(f"A2A Response Data from {agent_config['name']}: {json.dumps(response_data)}")

        status = response_data.get("status")
        if status in ["failed", "needs_clarification"]:
            intent.status = IntentStatus.INVALID
            error_msg = response_data.get("clarification_needed") or response_data.get("error") or "Unknown error."

            logger.warning(f"{agent_config['name']} returned {status}: {error_msg}")

            if error_msg not in intent.missing_info:
                intent.missing_info.append(f"Agent Error: {error_msg}")
        else:
            logger.info(f"{agent_config['name']} executed successfully.")

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
            if intent.intent_type in AGENT_REGISTRY:
                routes.append(AGENT_REGISTRY[intent.intent_type]["name"])

    routes = list(set(routes))

    if not routes:
        logger.info("ROUTER: No valid agents to call. Routing to generate_response.")
        return ["generate_response"]

    logger.info(f"ROUTER: Delegating to agents -> {routes}")
    return routes


def generate_response(state: OrchestratorState) -> dict[str, Any]:
    """Generates the final conversational response based on valid agent executions, missing info, and confirmed bookings."""
    logger.info("--- NODE: GENERATE RESPONSE ---")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    system_prompt = RESPONSE_GENERATOR_SYSTEM_PROMPT

    # 1. Grab Missing Info
    missing_details_context = []
    for intent in state.get("intents", []):
        if intent.active and intent.status == IntentStatus.INVALID:
            missing_details_context.append(
                f"- For {intent.intent_type}: Need {', '.join(intent.missing_info)}"
            )

    # 2. Grab Agent Results
    agent_results = [json.loads(task.agent_response) for task in state.get("agent_responses", {}).values() if not task.processed]

    # 3. Grab Newly Confirmed Bookings
    confirmed_bookings = [
        intent for intent in state.get("intents", [])
        if intent.status == IntentStatus.CONFIRMED and not getattr(intent, "acknowledged", False)
    ]

    logger.debug(f"Formatting {len(agent_results)} agent results, {len(missing_details_context)} clarification points, and {len(confirmed_bookings)} confirmations.")

    if confirmed_bookings:
        system_prompt += "### RECENTLY CONFIRMED BOOKINGS ###\n"
        system_prompt += "The user has officially booked the following items. Enthusiastically confirm the booking, provide their booking reference (PNR), and summarize the details from the booked_entity.\n"
        for booking in confirmed_bookings:
            entity_str = json.dumps(booking.booked_entity) if booking.booked_entity else "{}"
            system_prompt += f"- {booking.intent_type.value.upper()} ({booking.intent_id}) | Ref: {getattr(booking, 'booking_reference', 'PENDING')} | Details: {entity_str}\n"

    if agent_results:
        system_prompt += "### AGENT RESULTS (Format these nicely for the user) ###\n"
        system_prompt += f"{json.dumps(agent_results)}\n\n"

    if missing_details_context:
        system_prompt += "### MISSING INFORMATION (Politely ask the user for these specific details) ###\n"
        system_prompt += "\n".join(missing_details_context) + "\n\n"

    if not agent_results and not missing_details_context and not confirmed_bookings:
        system_prompt += "No active searches or bookings right now. Just chat nicely with the user!"

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    logger.debug("Invoking final response LLM...")
    response = llm.invoke(messages)

    logger.info("Response generated successfully.")

    # Mark agent responses as processed
    agent_responses = state.get("agent_responses", {})
    for resp_key in agent_responses:
        agent_responses[resp_key].processed = True

    intents = state.get("intents", [])
    for booking in confirmed_bookings:
        booking.acknowledged = True

    return {
        "messages": [response],
        "agent_responses": agent_responses,
        "intents": intents
    }


workflow = StateGraph(state_schema=OrchestratorState)  # type:ignore

workflow.add_node("parse", parse_intent)  # type:ignore
workflow.add_node("validate", validate_unprocessed_intents)  # type:ignore
workflow.add_node("call_flight_agent", call_flight_agent)  # type:ignore
workflow.add_node("call_hotel_agent", call_hotel_agent)  # type:ignore
workflow.add_node("generate_response", generate_response)  # type:ignore

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