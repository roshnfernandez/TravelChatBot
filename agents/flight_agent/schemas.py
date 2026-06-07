from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class FlightParameters(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int
    cabin_class: str

class A2ATaskRequestMetadata(BaseModel):
    requested_by: str = "orchestrator"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class A2AFlightTaskRequest(BaseModel):
    task_id: str
    task_type: str = "flight_search"
    session_id: str
    parameters: FlightParameters
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