import logging
from typing import Any

from langchain_core.messages import SystemMessage, RemoveMessage
from langchain_openai import ChatOpenAI

from orchestrator.const import CHATS_TO_HOLD_IN_MEMORY, TASKS_TO_HOLD_IN_MEMORY
from orchestrator.enums import IntentStatus
from orchestrator.models import IntentExtraction, HotelIntent, FlightIntent, OrchestratorState, SessionSummary
from orchestrator.prompts import get_parse_intent_system_prompt, get_response_system_prompt, \
    get_summarizer_system_prompt, get_task_summarizer_system_prompt

logger = logging.getLogger(__name__)


def parse_intent(state: OrchestratorState) -> dict:
    """Uses an LLM to analyze the conversation and extract structured intent/parameters."""
    logger.info("--- NODE: PARSE INTENT ---")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(IntentExtraction, method="function_calling")
    system_prompt: str = get_parse_intent_system_prompt(state)
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    logger.debug("Invoking LLM for structured intent extraction...")
    intent_wrapper: IntentExtraction = structured_llm.invoke(messages)
    intents: list[HotelIntent | FlightIntent] = intent_wrapper.extracted_intents

    return {"intents": intents}

def generate_response(state: OrchestratorState) -> dict[str, Any]:
    """Generates the final conversational response based on valid agent executions, missing info, and confirmed bookings."""
    logger.info("--- NODE: GENERATE RESPONSE ---")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    system_prompt = get_response_system_prompt(state)

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    logger.debug("Invoking final response LLM...")
    response = llm.invoke(messages)

    logger.info("Response generated successfully.")

    # Mark agent responses as processed
    agent_responses = state.get("agent_responses", {})
    for resp_key in agent_responses:
        agent_responses[resp_key].processed = True

    intents = state.get("intents", [])

    confirmed_bookings = [
        intent for intent in state.get("intents", [])
        if intent.status == IntentStatus.CONFIRMED and not getattr(intent, "acknowledged", False)
    ]

    for booking in confirmed_bookings:
        booking.acknowledged = True

    return {
        "messages": [response],
        "agent_responses": agent_responses,
        "intents": intents
    }

def summarize_context(state: OrchestratorState) -> dict:
    logger.info("--- NODE: SUMMARIZE CONTEXT ---")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(SessionSummary, method="function_calling")
    system_prompt: str = get_summarizer_system_prompt()
    old_messages = state["messages"][:-CHATS_TO_HOLD_IN_MEMORY]
    if state.get("summary", None):
        old_summary_json = state["summary"].model_dump_json(exclude_none=True)
        system_prompt += f"\n\n### PREVIOUS CONVERSATION SUMMARY ###\n" \
                         f"You must build upon and update this existing context:\n{old_summary_json}"
    messages = [SystemMessage(content=system_prompt)] + old_messages
    summary: SessionSummary = structured_llm.invoke(messages)
    delete_commands = [RemoveMessage(id=m.id) for m in old_messages if m.id is not None]
    return {
        "messages": delete_commands,
        "summary": summary
    }

def summarize_task_response(state: OrchestratorState) -> dict:
    logger.info("--- NODE: SUMMARIZE AGENT TASK ---")

    agent_responses = state.get("agent_responses", {})

    sorted_tasks = sorted(agent_responses.items(), key=lambda item: item[1].created_on)

    tasks_to_summarize = dict(sorted_tasks[:-TASKS_TO_HOLD_IN_MEMORY])

    if not tasks_to_summarize:
        return {}

    task_data_str = "\n".join([
        f"Task {t_id} ({t.agent_name}): {t.agent_response}"
        for t_id, t in tasks_to_summarize.items()
    ])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    system_prompt: str = get_task_summarizer_system_prompt()
    prompt_with_data = f"{system_prompt}\n\n### PROCESSED TASKS TO SUMMARIZE ###\n{task_data_str}"
    messages = [SystemMessage(content=prompt_with_data)]
    summary: str = llm.invoke(messages).content
    logger.debug(f"Task Summary Generated: {summary}")
    delete_commands = {t_id: None for t_id in tasks_to_summarize.keys()}
    return {
        "task_responses_summary": summary,
        "agent_responses": delete_commands
    }