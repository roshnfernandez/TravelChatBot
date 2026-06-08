import logging
import random
import string

from orchestrator.const import AGENT_REGISTRY, CHATS_TO_HOLD_IN_MEMORY, TASKS_TO_HOLD_IN_MEMORY
from orchestrator.enums import IntentStatus, IntentType

logger = logging.getLogger(__name__)


def generate_short_id(intent_type: IntentType) -> str:
    """Generates a short, LLM-friendly ID (e.g., FLT-8X2A)"""
    prefix = str(intent_type.value).upper()[0:3]
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{chars}"


def merge_intents(existing_intents: list, new_intents: list):
    """
        Strictly merges based on the intent_id explicitly targeted by the LLM.
    """
    # No history, so assign IDs to all new intents
    if not existing_intents:
        for intent in new_intents:
            if not getattr(intent, 'intent_id', None):
                intent.intent_id = generate_short_id(intent.intent_type)
        return new_intents

    if not new_intents:
        return existing_intents

    # 1. Load existing state into a fast dictionary keyed by ID
    merged_state = {intent.intent_id: intent for intent in existing_intents}

    # 2. Process updates from the LLM
    for new_intent in new_intents:
        # Condition A: The LLM explicitly targeted an existing ID
        if new_intent.intent_id and new_intent.intent_id in merged_state:
            existing = merged_state[new_intent.intent_id]

            # Handle user changing topics (canceling an intent)
            if not new_intent.active:
                existing.active = False
                merged_state.pop(existing.intent_id, None)
                continue

            # Merge fields safely (only updating what the LLM newly extracted)
            new_data = new_intent.model_dump(exclude_unset=True, exclude_none=True)
            for k, v in new_data.items():
                if k not in ["created_on", "missing_info", "intent_type", "intent_id"]:
                    setattr(existing, k, v)

        # Condition B: It's a completely new request (or the LLM hallucinated a bad ID)
        elif new_intent.active:
            # Force a fresh, valid system ID
            new_intent.intent_id = generate_short_id(new_intent.intent_type)
            merged_state[new_intent.intent_id] = new_intent

    # Return the dictionary back as a list for LangGraph
    return list(merged_state.values())


def merge_agent_responses(existing: dict, new: dict) -> dict:
    """Merges incoming agent responses into the existing state dictionary."""
    if not existing:
        # If no existing state, just filter out any Nones from the new payload
        return {k: v for k, v in new.items() if v is not None}

    if not new:
        return existing

    merged = existing.copy()
    for key, value in new.items():
        # --- THE DELETION PROTOCOL ---
        if value is None:
            merged.pop(key, None)  # Physically remove the old task
        else:
            merged[key] = value

    return merged

def delegate_to_agents(state) -> list[str]:
    """
    Returns a list of nodes to execute in parallel.
    Routes to Flight, Hotel, Both, or Neither
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

def route_to_summarizers(state) -> list[str]:
    """
    Returns a list of nodes to execute in parallel.
    Routes to Session Summarizer, Task Summarizer, Both, or Neither
    """
    routes = ["remove_old_intents"]
    if len(state.get("messages", [])) > CHATS_TO_HOLD_IN_MEMORY:
        routes.append("summarize_session")

    if len(state.get("agent_responses", {})) > TASKS_TO_HOLD_IN_MEMORY:
        routes.append("summarize_tasks")

    return routes

