from datetime import datetime
from typing import List, Optional

from agents.hotel_agent.schemas import HotelDetails

MOCK_HOTEL_DB = [
    {
        "hotel_id": "H001",
        "name": "Shinjuku Granbell Hotel",
        "city": "Tokyo",
        "neighborhood": "Shinjuku",
        "star_rating": 4,
        "price_per_night_usd": 150,
        "amenities": ["Free WiFi", "Bar", "City View"]
    },
    {
        "hotel_id": "H002",
        "name": "Park Hyatt Tokyo",
        "city": "Tokyo",
        "neighborhood": "Shinjuku",
        "star_rating": 5,
        "price_per_night_usd": 550,
        "amenities": ["Pool", "Spa", "Fitness Center", "Luxury"]
    },
    {
        "hotel_id": "H003",
        "name": "Shibuya Excel Hotel Tokyu",
        "city": "Tokyo",
        "neighborhood": "Shibuya",
        "star_rating": 4,
        "price_per_night_usd": 180,
        "amenities": ["Free WiFi", "Restaurant", "Close to station"]
    }
]


def search_hotels(
        destination_city: str,
        check_in_date: str,
        check_out_date: str,
        number_of_guests: int = 1,
        room_type_preference: Optional[str] = None,
        location_preferences: Optional[str] = None
) -> List[HotelDetails]:
    """
        Simulates querying a hotel database and calculates stay totals.
        """
    results = []

    try:
        in_date = datetime.strptime(check_in_date, "%Y-%m-%d")
        out_date = datetime.strptime(check_out_date, "%Y-%m-%d")
        nights = (out_date - in_date).days
        nights = max(1, nights)  # Fallback to 1 night if dates are same-day
    except ValueError:
        nights = 1  # Safe fallback if the LLM passes weird date strings

    for hotel in MOCK_HOTEL_DB:
        if hotel["city"].lower() == destination_city.lower():

            # Create the data payload
            booked_hotel = hotel.copy()
            booked_hotel["check_in_date"] = check_in_date
            booked_hotel["check_out_date"] = check_out_date
            booked_hotel["total_price_usd"] = str(float(hotel["price_per_night_usd"] * nights * number_of_guests))

            validated_result = HotelDetails(**booked_hotel)

            # Prioritize location preferences
            if location_preferences and location_preferences.lower() in hotel["neighborhood"].lower():
                results.insert(0, validated_result)
            else:
                results.append(validated_result)

    return results