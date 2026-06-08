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

class FlightDetails(BaseModel):
    flight_number: str = Field(..., description="The alphanumeric flight identifier, e.g., 'NH802'.")
    airline: str = Field(..., description="The name of the airline.")
    origin: str = Field(..., description="3-letter IATA code for the departure airport.")
    destination: str = Field(..., description="3-letter IATA code for the arrival airport.")
    departure_time: str = Field(..., description="Local departure time (HH:MM).")
    arrival_time: str = Field(..., description="Local arrival time (HH:MM), optionally with day offset.")
    cabin_class: str = Field(..., description="The class of service (e.g., economy, business).")

    # Base price from DB
    price_usd: float = Field(..., description="Base price per passenger in USD.")

    # Dynamic fields injected by the search function
    departure_date: str = Field(..., description="The specific departure date (YYYY-MM-DD).")
    return_date: Optional[str] = Field(None, description="The return date, if applicable.")
    total_price_usd: float = Field(..., description="Total price for all passengers combined.")

class A2ATaskResponse(BaseModel):
    task_id: str
    status: str # "success | partial | failed | needs_clarification"
    results: List[FlightDetails] = Field(default_factory=list)
    clarification_needed: Optional[str] = None
    error: Optional[str] = None
    metadata: A2ATaskResponseMetadata