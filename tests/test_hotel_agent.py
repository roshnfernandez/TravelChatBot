import unittest
from unittest.mock import patch

from agents.hotel_agent.agent import (
    HotelAgentState,
    validate_request,
    retrieve_hotels,
    format_response,
    route_after_validation
)


class TestHotelAgentLogic(unittest.TestCase):

    def setUp(self):
        """Generates a clean baseline state before each test."""
        self.base_state: HotelAgentState = {
            "request": {},
            "is_valid": False,
            "validation_error": None,
            "hotel_results": [],
            "response": None
        }

        self.valid_request_payload = {
            "task_id": "test-hotel-task-123",
            "task_type": "hotel_search",
            "session_id": "session-xyz-123",
            "parameters": {
                "destination_city": "Tokyo",
                "check_in_date": "2026-06-15",
                "check_out_date": "2026-06-18",
                "number_of_guests": 2
            }
        }

        self.mock_hotel_result = {
            "hotel_id": "H001",
            "name": "Park Hyatt Tokyo",
            "city": "Tokyo",
            "neighborhood": "Shinjuku",
            "star_rating": 5,
            "price_per_night_usd": 500.0,
            "amenities": ["Pool", "Spa"],
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-18",
            "total_price_usd": 1500.0
        }

    # --- 1. ROUTING TESTS ---

    def test_route_after_validation_success(self):
        """Tests that a valid state routes directly to the search node."""
        self.base_state["is_valid"] = True
        route = route_after_validation(self.base_state)
        self.assertEqual(route, "search")

    def test_route_after_validation_failure(self):
        """Tests that an invalid state bypasses search and goes to formatting."""
        self.base_state["is_valid"] = False
        route = route_after_validation(self.base_state)
        self.assertEqual(route, "format")

    # --- 2. VALIDATION NODE TESTS ---

    def test_validate_request_success(self):
        """Ensures a perfectly structured request passes Pydantic validation."""
        self.base_state["request"] = self.valid_request_payload
        result = validate_request(self.base_state)

        self.assertTrue(result["is_valid"])
        self.assertIsNone(result["validation_error"])

    def test_validate_request_missing_fields(self):
        """Ensures a malformed request (missing parameters) gets caught."""
        # Intentionally dropping the required 'parameters' and 'session_id' fields
        self.base_state["request"] = {"task_id": "only-id"}
        result = validate_request(self.base_state)

        self.assertFalse(result["is_valid"])
        self.assertIn("Schema validation failed", result["validation_error"])

    # --- 3. SEARCH NODE TESTS ---

    @patch('agents.hotel_agent.agent.search_hotels')
    def test_retrieve_hotels(self, mock_search):
        """Tests the search node correctly extracts parameters and calls the DB."""
        mock_search.return_value = [self.mock_hotel_result]

        self.base_state["request"] = self.valid_request_payload
        result = retrieve_hotels(self.base_state)

        self.assertEqual(len(result["hotel_results"]), 1)
        self.assertEqual(result["hotel_results"][0]["hotel_id"], "H001")

        # Verify DB was called with correct explicit kwargs mapped from parameters
        mock_search.assert_called_once_with(
            destination_city="Tokyo",
            check_in_date="2026-06-15",
            check_out_date="2026-06-18",
            number_of_guests=2,
            room_type_preference=None,
            location_preferences=None
        )

    # --- 4. FORMATTING NODE TESTS ---

    def test_format_response_path_a_validation_failed(self):
        """Path A: Ensures an invalid request returns a 'failed' status payload."""
        self.base_state["request"] = {"task_id": "err-123"}
        self.base_state["is_valid"] = False
        self.base_state["validation_error"] = "Missing city parameter"

        result = format_response(self.base_state)
        response_dict = result["response"]

        self.assertEqual(response_dict["status"], "failed")
        self.assertEqual(response_dict["error"], "Missing city parameter")

    def test_format_response_path_b_no_hotels_found(self):
        """Path B: Ensures an empty search result asks the user for clarification."""
        self.base_state["request"] = self.valid_request_payload
        self.base_state["is_valid"] = True
        self.base_state["hotel_results"] = []  # DB found nothing

        result = format_response(self.base_state)
        response_dict = result["response"]

        self.assertEqual(response_dict["status"], "needs_clarification")
        self.assertIn("No hotels found", response_dict["clarification_needed"])
        self.assertEqual(response_dict["results"], [])

    def test_format_response_path_c_success(self):
        """Path C: Ensures a successful search packages the strict data correctly."""
        self.base_state["request"] = self.valid_request_payload
        self.base_state["is_valid"] = True
        self.base_state["hotel_results"] = [self.mock_hotel_result]

        result = format_response(self.base_state)
        response_dict = result["response"]

        self.assertEqual(response_dict["status"], "success")
        self.assertEqual(len(response_dict["results"]), 1)
        self.assertEqual(response_dict["results"][0]["name"], "Park Hyatt Tokyo")
        self.assertEqual(response_dict["metadata"]["agent_id"], "hotel-agent")


if __name__ == '__main__':
    unittest.main()