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
    invalid_active_intents = [intent for intent in  state["intents"] if intent.active and intent.status == IntentStatus.INVALID]
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
    for intent in state["intents"]:
        if intent.status in [IntentStatus.NEW, IntentStatus.MODIFIED]:
            intent.missing_info = []
            fields_to_look_for: list[str] = REQUIRED_FIELDS_BY_INTENT[intent.intent_type]
            logger.info(f"Unprocessed intent detected of type - {intent.intent_type}, validating fields {fields_to_look_for}")
            for field in fields_to_look_for:
                if getattr(intent, field, None) is None:
                    intent.missing_info.append(field)
            intent.status = IntentStatus.INVALID if intent.missing_info else IntentStatus.VALID
    return {"intents": state["intents"]}

def delegate_to_agents(state: OrchestratorState):
    """Translates the extracted parameters into A2A requests and calls sub-agents."""

    #Fetch active intents that are valid and delegate them to agents
    valid_intents: dict[IntentType, HotelIntent|FlightIntent] = {intent.intent_type:intent for intent in state["intents"] if intent.status == IntentStatus.VALID and intent.active}
    new_agent_responses = {}
    for intent_type, intent in valid_intents.items():

        if intent_type not in AGENT_REGISTRY or intent_type not in valid_intents:
            continue

        agent_config = AGENT_REGISTRY[intent_type]
        task_id = str(uuid.uuid4())

        # Build strict A2A Request
        req_payload = {
            "task_id": task_id,
            "session_id": state["session_id"],
            "task_type": agent_config["task_type"],
            "parameters": intent.model_dump(exclude=INTENT_META_DATA_FIELDS)
        }

        # Invoke the graph dynamically from the registry
        result = agent_config["graph"].invoke({"request": req_payload})

        # Create AgentTask record
        new_agent_responses[task_id] = AgentTask(
            task_id=task_id,
            agent_name=agent_config["name"],
            agent_request=json.dumps(req_payload),
            agent_response=json.dumps(result.get("response", {}))
        )

    return {"agent_responses": new_agent_responses}


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


def route_after_parsing(state: OrchestratorState):
    """Determines whether to trigger sub-agents or reply directly to the user."""
    intent = [intent for intent in state["intents"] if intent.status == IntentStatus.VALID and intent.active]
    if intent:
        return "delegate"
    return "generate_response"


workflow = StateGraph(state_schema=OrchestratorState) #type:ignore

workflow.add_node("parse", parse_intent) #type:ignore
workflow.add_node("validate", validate_unprocessed_intents) #type:ignore
workflow.add_node("delegate", delegate_to_agents) #type:ignore
workflow.add_node("generate_response", generate_response) #type:ignore

workflow.set_entry_point("parse")

workflow.add_edge("parse", "validate")

workflow.add_conditional_edges(
    "validate",
    route_after_parsing,
    {
        "delegate": "delegate",
        "generate_response": "generate_response"
    }
)

workflow.add_edge("delegate", "generate_response")
workflow.add_edge("generate_response", END)

orchestrator_graph = workflow.compile()

print(orchestrator_graph.get_graph().draw_mermaid())