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

class HotelDetails(BaseModel):
    hotel_id: str = Field(..., description="The unique hotel identifier (e.g., 'H001').")
    name: str = Field(..., description="The name of the hotel.")
    city: str = Field(..., description="The city where the hotel is located.")
    neighborhood: str = Field(..., description="The specific neighborhood.")
    star_rating: int = Field(..., description="Hotel star rating (1-5).")
    price_per_night_usd: float = Field(..., description="Base price per night in USD.")
    amenities: List[str] = Field(default_factory=list, description="List of amenities provided.")

    # Dynamic fields injected by the search function
    check_in_date: str = Field(..., description="Check-in date (YYYY-MM-DD).")
    check_out_date: str = Field(..., description="Check-out date (YYYY-MM-DD).")
    total_price_usd: float = Field(..., description="Total calculated price for the entire stay.")

class A2ATaskResponse(BaseModel):
    task_id: str
    status: str # "success | partial | failed | needs_clarification"
    results: List[HotelDetails] = Field(default_factory=list)
    clarification_needed: Optional[str] = None
    error: Optional[str] = None
    metadata: A2ATaskResponseMetadata