import copy
import json
import logging
import uuid
from datetime import datetime, timedelta

from orchestrator.const import AGENT_REGISTRY, INTENT_META_DATA_FIELDS, REQUIRED_FIELDS_BY_INTENT, INTENTS_THRESHOLD
from orchestrator.enums import IntentType, IntentStatus
from orchestrator.models import AgentTask, HotelIntent, FlightIntent, OrchestratorState

logger = logging.getLogger(__name__)


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


def validate_unprocessed_intents(state: OrchestratorState) -> dict:
    logger.info("--- NODE: VALIDATE INTENTS ---")
    new_intents: list[HotelIntent | FlightIntent] = [copy.copy(intent) for intent in state.get("intents", []) if
                                                     intent.status in [IntentStatus.NEW, IntentStatus.MODIFIED]]
    for intent in new_intents:
        if intent.status in [IntentStatus.NEW, IntentStatus.MODIFIED]:
            intent.missing_info = []
            fields_to_look_for: list[str] = REQUIRED_FIELDS_BY_INTENT[intent.intent_type]
            logger.info(
                f"Unprocessed intent detected of type - {intent.intent_type}, validating fields {fields_to_look_for}")
            for field in fields_to_look_for:
                if getattr(intent, field, None) is None:
                    intent.missing_info.append(field)

            if intent.missing_info:
                intent.status = IntentStatus.INVALID
                logger.warning(f"Intent {intent.intent_type} is INVALID. Missing fields: {intent.missing_info}")
            else:
                intent.status = IntentStatus.VALID
                logger.info(f"Intent {intent.intent_type} is VALID. Ready for delegation.")

    return {"intents": new_intents}

def remove_old_invalid_intents(state: OrchestratorState) -> dict:
    logger.info("--- NODE: REMOVE OLD INVALID INTENTS ---")
    intents = state.get("intents", [])
    current_time = datetime.now()

    ttl_threshold = timedelta(minutes=INTENTS_THRESHOLD)

    updated_intents = []
    for intent in intents:
        if intent.active and intent.status not in [IntentStatus.VALID, IntentStatus.CONFIRMED]:
            time_alive = current_time - intent.created_on

            if time_alive > ttl_threshold:
                logger.warning(f"Pruning stale intent {intent.intent_id} (Alive for {time_alive}).")
                intent.active = False
                intent.missing_info.append("Timeout: Intent abandoned by user after 5 minutes.")
        updated_intents.append(intent)
    return {"intents": updated_intents}
