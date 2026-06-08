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
    },
    {
        "hotel_id": "H004",
        "name": "The Savoy",
        "city": "London",
        "neighborhood": "Covent Garden",
        "star_rating": 5,
        "price_per_night_usd": 750,
        "amenities": ["Luxury", "River View", "Fine Dining", "Spa"]
    },
    {
        "hotel_id": "H005",
        "name": "CitizenM Times Square",
        "city": "New York",
        "neighborhood": "Manhattan",
        "star_rating": 4,
        "price_per_night_usd": 280,
        "amenities": ["Smart Rooms", "Rooftop Bar", "Free WiFi", "Gym"]
    },
    {
        "hotel_id": "H006",
        "name": "Armani Hotel Dubai",
        "city": "Dubai",
        "neighborhood": "Downtown Dubai",
        "star_rating": 5,
        "price_per_night_usd": 600,
        "amenities": ["Burj Khalifa Access", "Spa", "Pool", "Luxury"]
    },
    {
        "hotel_id": "H007",
        "name": "Hotel Monge",
        "city": "Paris",
        "neighborhood": "Latin Quarter",
        "star_rating": 4,
        "price_per_night_usd": 320,
        "amenities": ["Boutique", "Hammam", "Free WiFi", "Honesty Bar"]
    },
    {
        "hotel_id": "H008",
        "name": "Fairmont San Francisco",
        "city": "San Francisco",
        "neighborhood": "Nob Hill",
        "star_rating": 5,
        "price_per_night_usd": 450,
        "amenities": ["Panoramic Views", "Tiki Bar", "Fitness Center", "Historic"]
    },
    {
        "hotel_id": "H009",
        "name": "Four Seasons Hotel Sydney",
        "city": "Sydney",
        "neighborhood": "The Rocks",
        "star_rating": 5,
        "price_per_night_usd": 520,
        "amenities": ["Harbour View", "Outdoor Pool", "Spa", "Restaurant"]
    },
    {
        "hotel_id": "H010",
        "name": "Motel One Frankfurt-Römer",
        "city": "Frankfurt",
        "neighborhood": "Altstadt",
        "star_rating": 3,
        "price_per_night_usd": 110,
        "amenities": ["Central Location", "Design Lounge", "Free WiFi", "Pet Friendly"]
    },
    {
        "hotel_id": "H011",
        "name": "W Taipei",
        "city": "Taipei",
        "neighborhood": "Xinyi District",
        "star_rating": 5,
        "price_per_night_usd": 380,
        "amenities": ["Outdoor Pool", "Nightclub", "Spa", "Taipei 101 View"]
    },
    {
        "hotel_id": "H012",
        "name": "Taj Mahal Palace",
        "city": "Mumbai",
        "neighborhood": "Colaba",
        "star_rating": 5,
        "price_per_night_usd": 350,
        "amenities": ["Sea View", "Heritage Architecture", "Multiple Restaurants", "Pool"]
    },
    {
        "hotel_id": "H013",
        "name": "Hyatt Ziva Cancun",
        "city": "Cancun",
        "neighborhood": "Hotel Zone",
        "star_rating": 4,
        "price_per_night_usd": 480,
        "amenities": ["All-Inclusive", "Beachfront", "Multiple Pools", "Kids Club"]
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