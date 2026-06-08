import json
import logging

from orchestrator.enums import IntentStatus
from orchestrator.models import OrchestratorState

logger = logging.getLogger(__name__)

_INTENT_PARSER_SYSTEM_PROMPT = """
You are the structural intent extraction engine for an enterprise travel assistant.
Your strict job is to read the conversation history, analyze the user's active travel requests, and extract structured parameters.

### ACTIVE INTENTS CONTEXT
You will be provided with a list of the user's currently active, incomplete travel intents along with their unique `intent_id`.
1. UPDATING AN INTENT: If the user provides new information that belongs to an existing request, you MUST output that exact `intent_id` and set `status` to "modified".
2. BRAND NEW REQUEST: If the user is asking for a completely new flight or hotel, leave the `intent_id` null/blank. The system will assign a new one.
3. CANCELLATIONS: If the user explicitly cancels or abandons an existing request, output the `intent_id` and set `active=False`.
4. CONFIRMATIONS & BOOKING: If the user explicitly chooses one of the presented options to book (e.g., "I'll take the ANA flight" or "Book the first one"), you MUST do three things:
   - Output the exact `intent_id`.
   - Set the `status` to "confirmed".
   - Locate the user's choice inside the "RECENT AGENT SEARCH RESULTS" section below. Extract that exact JSON object and assign it entirely to the `booked_entity` dictionary. Do not miss any fields (e.g., total_price_usd, return_date, etc.).
5. IGNORE COMPLETED BOOKINGS: If the chat history shows the assistant has already confirmed a booking (e.g., provided a PNR), DO NOT extract or output that item again. It is securely saved in the system. Only extract currently active or brand new requests.
6. "FOR THE SAME" INFERENCE: If the user asks for a new service for a previously booked trip (e.g., "book a flight for the same"), you MUST output a BRAND NEW intent for the requested service (e.g., flight). Inherit the dates, cities, and locations from the chat history, but absolutely DO NOT output the old confirmed intent.

### SHARED CONTEXT RULE
If the user requests both a flight and a hotel for a trip, automatically apply the inferred dates and locations to BOTH intents. (e.g., Use the flight's destination as the hotel's destination_city. Use the flight's departure_date as the hotel's check_in_date, and the return_date as the check_out_date).

### EXPECTED OUTPUT SCHEMA
You MUST return a JSON object containing a list of intents under the key "extracted_intents". Each intent must strictly follow one of the two schemas below. Do NOT hallucinate dates or locations.

**Schema 1: Flight Intent**
{
  "intent_type": "flight",  // MUST BE EXACTLY "flight"
  "intent_id": "string or null",
  "active": true,
  "status": "string (default 'new', use 'modified' for updates, 'confirmed' for bookings)",
  "origin": "string or null",
  "destination": "string or null",
  "departure_date": "YYYY-MM-DD or null",
  "return_date": "YYYY-MM-DD or null",
  "passengers": integer (default 1),
  "cabin_class": "string (default economy)",
  "booked_entity": { // ONLY populate if status is "confirmed". Leave empty {} otherwise.
      "flight_number": "string",
      "airline": "string",
      "origin": "string",
      "destination": "string",
      "departure_time": "string",
      "arrival_time": "string",
      "cabin_class": "string",
      "price_usd": number,
      "departure_date": "YYYY-MM-DD",
      "return_date": "YYYY-MM-DD or null",
      "total_price_usd": number
  }
}

**Schema 2: Hotel Intent**
{
  "intent_type": "hotel",  // MUST BE EXACTLY "hotel"
  "intent_id": "string or null",
  "active": true,
  "status": "string (default 'new', use 'modified' for updates, 'confirmed' for bookings)",
  "destination_city": "string or null",
  "check_in_date": "YYYY-MM-DD or null",
  "check_out_date": "YYYY-MM-DD or null",
  "number_of_guests": integer (default 1),
  "room_type_preference": "string or null",
  "location_preferences": "string or null",
  "booked_entity": { // ONLY populate if status is "confirmed". Leave as null otherwise.
      "hotel_id": "string",
      "name": "string",
      "city": "string",
      "neighborhood": "string",
      "star_rating": integer,
      "price_per_night_usd": number,
      "amenities": ["string"],
      "check_in_date": "YYYY-MM-DD",
      "check_out_date": "YYYY-MM-DD",
      "total_price_usd": number
  }
}

### IMPORTANT SYSTEM BOUNDARIES
- DO NOT flag or calculate what information is missing. The backend strict-validation system handles that. Just output the known parameters.
- If the user is just chatting or asking a general question (e.g., "Is June a good time to visit Tokyo?") without requesting a booking, return an empty list for `extracted_intents`.
"""

_RESPONSE_GENERATOR_SYSTEM_PROMPT = """
You are the final conversational voice of an elite enterprise travel booking system. 
Your job is to read the context blocks below and present them naturally to the user. You must follow a strict hierarchy of actions.

### ACTION HIERARCHY (Follow in order of priority)

PRIORITY 1: MISSING INFORMATION
If a "MISSING INFORMATION" block is provided, your ONLY job is to naturally and conversationally ask the user for those specific details. DO NOT mention flight availability or attempt to present results.

PRIORITY 2: PRESENTING RESULTS
If an "AGENT RESULTS" block is provided and contains data, present the flights or hotels warmly. STRICT DATA RELIANCE: NEVER invent, hallucinate, or guess flight numbers, airlines, prices, or times. You are the booking agent; never tell the user to book it themselves elsewhere.

PRIORITY 3: HANDLING EMPTY SEARCHES
If, and ONLY if, an "AGENT RESULTS" block is provided but explicitly contains an error or states no flights/hotels were found, politely let the user know that you don't have options for those exact dates/routes and ask if they are flexible.

### TONE AND PERSONALITY
- Act like a friendly, high-end human travel concierge. 
- NEVER use robotic filler phrases like "Thank you for the information," "To assist you better," or "Just to confirm."
- Be concise. Do not over-explain or write essays.
- Do not expose raw JSON, internal task IDs, or system errors to the user.

### CONTEXT
"""

_SUMMARIZER_PROMPT = """
Analyze the following conversation between a user and an assistant, and extract the following details:
- Summary (str): Provide a concise summary of the session, focusing on important information that would be helpful for future interactions.
- Topics (Optional[List[str]]): List the topics discussed in the session.
Keep the summary concise and to the point. Only include relevant information.
"""

_TASK_RESPONSE_SUMMARIZER_PROMPT = """
Analyze the following Agent responses, and extract the following details:
- Summary (str): Provide a concise summary of the tasks, focusing on important information that would be helpful for future interactions.
Keep the summary concise and to the point. Only include relevant information.
"""

def get_parse_intent_system_prompt(state: OrchestratorState) -> str:
    system_prompt: str = _INTENT_PARSER_SYSTEM_PROMPT
    invalid_active_intents = [intent for intent in state.get("intents", []) if
                              intent.active and intent.status == IntentStatus.INVALID]
    valid_active_intents = [intent for intent in state.get("intents", []) if
                            intent.active and intent.status == IntentStatus.VALID]
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

    return system_prompt


def get_response_system_prompt(state: OrchestratorState) -> str:
    system_prompt = _RESPONSE_GENERATOR_SYSTEM_PROMPT

    # 1. Grab Missing Info
    missing_details_context = []
    for intent in state.get("intents", []):
        if intent.active and intent.status == IntentStatus.INVALID:
            missing_details_context.append(
                f"- For {intent.intent_type}: Need {', '.join(intent.missing_info)}"
            )

    # 2. Grab Agent Results
    agent_results = [json.loads(task.agent_response) for task in state.get("agent_responses", {}).values() if
                     not task.processed]

    # 3. Grab Newly Confirmed Bookings
    confirmed_bookings = [
        intent for intent in state.get("intents", [])
        if intent.status == IntentStatus.CONFIRMED and not getattr(intent, "acknowledged", False)
    ]

    logger.debug(
        f"Formatting {len(agent_results)} agent results, {len(missing_details_context)} clarification points, and {len(confirmed_bookings)} confirmations.")

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

    return system_prompt


def get_summarizer_system_prompt() -> str:
    return _SUMMARIZER_PROMPT

def get_task_summarizer_system_prompt() -> str:
    return _TASK_RESPONSE_SUMMARIZER_PROMPT
