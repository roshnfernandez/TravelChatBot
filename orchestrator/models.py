from datetime import datetime
from typing_extensions import TypedDict
from typing import Optional, Annotated, Literal

from langgraph.graph import add_messages
from pydantic import BaseModel, Field, field_validator

from orchestrator.enums import IntentStatus, IntentType
from orchestrator.util import merge_intents


class Intent(BaseModel):
    intent_id: Optional[str] = Field(None, description="intent id")
    active: bool = Field(True, description="Whether the intent is active.")
    status: IntentStatus = Field(IntentStatus.NEW, description="The intent status")
    missing_info: list[str] = Field(default_factory=list, description="List of missing information.")
    created_on: datetime = Field(default_factory=datetime.now, description="The date the intent was created.")

class FlightIntent(Intent):
    intent_type: IntentType.FLIGHT = IntentType.FLIGHT
    origin: Optional[str] = Field(None, description="The origin of the flight.")
    destination: Optional[str] = Field(None, description="The destination of the flight.")
    departure_date: Optional[str] = Field(None, description="The departure date.")
    return_date: Optional[str] = Field(None, description="The return date.")
    passengers: int = Field(1, description="The number of passengers.")
    cabin_class: Optional[str] = Field("economy", description="The cabin class.")

    @field_validator('intent_type')
    @classmethod
    def enforce_flight(cls, v):
        if v != IntentType.FLIGHT:
            raise ValueError("intent_type must be FLIGHT")
        return v

class HotelIntent(Intent):
    intent_type: IntentType.HOTEL = IntentType.HOTEL
    destination_city: Optional[str] = Field(None, description="The destination city.")
    check_in_date: Optional[str] = Field(None, description="The check-in date.")
    check_out_date: Optional[str] = Field(None, description="The check-out date.")
    number_of_guests: int = Field(1, description="The number of guests.")
    room_type_preference: Optional[str] = Field(None, description="The room type.")
    location_preferences: Optional[str] = Field(None, description="The location preference.")

    @field_validator('intent_type')
    @classmethod
    def enforce_flight(cls, v):
        if v != IntentType.FLIGHT:
            raise ValueError("intent_type must be FLIGHT")
        return v

class AgentTask(BaseModel):
    task_id: str = Field(..., description="The task id.")
    agent_name: str = Field(..., description="The agent name.")
    agent_request: str = Field(..., description="The agent request.")
    agent_response: str = Field(..., description="The agent response.")
    created_on: datetime = Field(default_factory=datetime.now, description="The datetime the task was created.")
    processed: bool = Field(False, description="Whether the task was processed.")

class IntentExtraction(BaseModel):
    extracted_intents: list[FlightIntent | HotelIntent]

class OrchestratorState(TypedDict):
    messages: Annotated[list, add_messages]
    session_id: str
    intents: Annotated[list[HotelIntent | FlightIntent], merge_intents]
    agent_responses: dict[str, AgentTask]