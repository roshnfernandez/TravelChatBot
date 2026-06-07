from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class HotelParameters(BaseModel):
    destination_city: str
    check_in_date: str
    check_out_date: str
    number_of_guests: int
    room_type_preference: Optional[str] = None
    location_preferences: Optional[str] = None

class A2ATaskRequestMetadata(BaseModel):
    requested_by: str = "orchestrator"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class A2AHotelTaskRequest(BaseModel):
    task_id: str
    task_type: str = "hotel_search"
    session_id: str
    parameters: HotelParameters
    metadata: A2ATaskRequestMetadata = Field(default_factory=A2ATaskRequestMetadata)

class A2ATaskResponseMetadata(BaseModel):
    agent_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class A2ATaskResponse(BaseModel):
    task_id: str
    status: str # "success | partial | failed | needs_clarification"
    results: List[Dict[str, Any]] = Field(default_factory=list)
    clarification_needed: Optional[str] = None
    error: Optional[str] = None
    metadata: A2ATaskResponseMetadata