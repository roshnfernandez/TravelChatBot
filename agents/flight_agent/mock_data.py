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
    },
    {
        "flight_number": "BA112",
        "airline": "British Airways",
        "origin": "NEW YORK",
        "destination": "LONDON",
        "departure_time": "18:30",
        "arrival_time": "06:30 (+1)",
        "price_usd": 650,
        "cabin_class": "economy"
    },
    {
        "flight_number": "VS004",
        "airline": "Virgin Atlantic",
        "origin": "NEW YORK",
        "destination": "LONDON",
        "departure_time": "22:00",
        "arrival_time": "10:05 (+1)",
        "price_usd": 1250,
        "cabin_class": "premium economy"
    },
    {
        "flight_number": "EK001",
        "airline": "Emirates",
        "origin": "DUBAI",
        "destination": "LONDON",
        "departure_time": "07:45",
        "arrival_time": "12:25",
        "price_usd": 850,
        "cabin_class": "economy"
    },
    {
        "flight_number": "AF022",
        "airline": "Air France",
        "origin": "PARIS",
        "destination": "NEW YORK",
        "departure_time": "08:30",
        "arrival_time": "10:40",
        "price_usd": 580,
        "cabin_class": "economy"
    },
    {
        "flight_number": "UA837",
        "airline": "United Airlines",
        "origin": "SAN FRANCISCO",
        "destination": "TOKYO",
        "departure_time": "11:30",
        "arrival_time": "15:00 (+1)",
        "price_usd": 920,
        "cabin_class": "economy"
    },
    {
        "flight_number": "QF011",
        "airline": "Qantas",
        "origin": "SYDNEY",
        "destination": "LOS ANGELES",
        "departure_time": "10:15",
        "arrival_time": "06:00",
        "price_usd": 1050,
        "cabin_class": "economy"
    },
    {
        "flight_number": "LH778",
        "airline": "Lufthansa",
        "origin": "FRANKFURT",
        "destination": "SINGAPORE",
        "departure_time": "21:40",
        "arrival_time": "16:15 (+1)",
        "price_usd": 2800,
        "cabin_class": "business"
    },
    {
        "flight_number": "CX480",
        "airline": "Cathay Pacific",
        "origin": "HONG KONG",
        "destination": "TAIPEI",
        "departure_time": "17:45",
        "arrival_time": "19:40",
        "price_usd": 220,
        "cabin_class": "economy"
    },
    {
        "flight_number": "AI129",
        "airline": "Air India",
        "origin": "MUMBAI",
        "destination": "LONDON",
        "departure_time": "06:30",
        "arrival_time": "11:30",
        "price_usd": 490,
        "cabin_class": "economy"
    },
    {
        "flight_number": "AC950",
        "airline": "Air Canada",
        "origin": "TORONTO",
        "destination": "CANCUN",
        "departure_time": "09:00",
        "arrival_time": "13:10",
        "price_usd": 310,
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