import random
import string

from orchestrator.enums import IntentStatus, IntentType


def generate_short_id(intent_type: IntentType) -> str:
    """Generates a short, LLM-friendly ID (e.g., FLT-8X2A)"""
    prefix = str(intent_type.value).upper()[0:3]
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{chars}"

def merge_intents(existing_intents: list, new_intents: list):
    """
        Strictly merges based on the intent_id explicitly targeted by the LLM.
    """
    #No history, so assign IDs to all new intents
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
                continue

            # Merge fields safely (only updating what the LLM newly extracted)
            new_data = new_intent.model_dump(exclude_unset=True, exclude_none=True)
            for k, v in new_data.items():
                if k not in ["created_on", "status", "missing_info", "intent_type", "intent_id"]:
                    setattr(existing, k, v)

            # Flag for validation to re-check
            existing.status = IntentStatus.MODIFIED

        # Condition B: It's a completely new request (or the LLM hallucinated a bad ID)
        else:
            # Force a fresh, valid system ID
            new_intent.intent_id = generate_short_id(new_intent.intent_type)
            merged_state[new_intent.intent_id] = new_intent

    # Return the dictionary back as a list for LangGraph
    return list(merged_state.values())