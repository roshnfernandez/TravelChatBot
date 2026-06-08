from typing import List, Dict, Any, Optional

from agents.flight_agent.schemas import FlightDetails

MOCK_FLIGHT_DB = [
    {
        "flight_number": "JL712",
        "airline": "Japan Airlines",
        "origin": "SINGAPORE",
        "destination": "TOKYO",
        "departure_time": "08:15",
        "arrival_time": "16:10",
        "price_usd": 450,
        "cabin_class": "economy"
    },
    {
        "flight_number": "SQ638",
        "airline": "Singapore Airlines",
        "origin": "SINGAPORE",
        "destination": "TOKYO",
        "departure_time": "23:55",
        "arrival_time": "08:00 (+1)",
        "price_usd": 520,
        "cabin_class": "economy"
    },
    {
        "flight_number": "NH802",
        "airline": "ANA",
        "origin": "SINGAPORE",
        "destination": "TOKYO",
        "departure_time": "06:30",
        "arrival_time": "14:20",
        "price_usd": 480,
        "cabin_class": "economy"
    }
]


def search_flights(
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy"
) -> List[FlightDetails]:
    """
    Simulates querying a flight database.
    Filters primarily by origin, destination, and cabin class.
    """
    results = []
    for flight in MOCK_FLIGHT_DB:
        if (flight["origin"].upper() == origin.upper() and
                flight["destination"].upper() == destination.upper() and
                flight["cabin_class"].lower() == cabin_class.lower()):
            booked_flight = flight.copy()
            booked_flight["departure_date"] = departure_date
            booked_flight["total_price_usd"] = flight["price_usd"] * passengers
            validated_result = FlightDetails(**booked_flight)
            results.append(validated_result)

    return results