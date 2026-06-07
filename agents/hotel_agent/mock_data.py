from typing import List, Dict, Any, Optional

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
) -> List[Dict[str, Any]]:
    results = []
    for hotel in MOCK_HOTEL_DB:
        if hotel["city"].lower() == destination_city.lower():

            # If a location preference is provided, prioritize it
            if location_preferences and location_preferences.lower() in hotel["neighborhood"].lower():
                results.insert(0, hotel)
            else:
                results.append(hotel)

    # Calculate total price based on mock stay duration (simplified)
    for res in results:
        res["check_in"] = check_in_date
        res["check_out"] = check_out_date

    return results