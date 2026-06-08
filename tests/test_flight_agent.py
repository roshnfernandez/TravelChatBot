import unittest
from unittest.mock import patch

from agents.flight_agent.agent import (
    FlightAgentState,
    validate_request,
    retrieve_flights,
    format_response,
    route_after_validation
)


class TestFlightAgentLogic(unittest.TestCase):

    def setUp(self):
        """Generates a clean baseline state before each test."""
        self.base_state: FlightAgentState = {
            "request": {},
            "is_valid": False,
            "validation_error": None,
            "flight_results": [],
            "response": {}
        }

        self.valid_request_payload = {
            "task_id": "test-task-123",
            "task_type": "flight_search",
            "session_id": "session-xyz-123",  # <-- Added the required session_id
            "parameters": {
                "origin": "SIN",
                "destination": "TYO",
                "departure_date": "2026-06-15",
                "passengers": 1,
                "cabin_class": "economy"
            }
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
        """Ensures a perfectly structured request passes validation."""
        self.base_state["request"] = self.valid_request_payload
        result = validate_request(self.base_state)

        self.assertTrue(result["is_valid"])
        self.assertIsNone(result["validation_error"])

    def test_validate_request_missing_fields(self):
        """Ensures a malformed request gets caught by Pydantic."""
        self.base_state["request"] = {"task_id": "only-id"}  # Missing required parameters
        result = validate_request(self.base_state)

        self.assertFalse(result["is_valid"])
        self.assertIn("Schema validation failed", result["validation_error"])

    # --- 3. SEARCH NODE TESTS ---
    @patch('agents.flight_agent.agent.search_flights')
    def test_retrieve_flights(self, mock_search):
        """Tests the search node correctly extracts parameters and calls the DB."""
        # Set up what the fake database should return
        mock_search.return_value = [{"flight_number": "JL712", "price_usd": 450.0}]

        self.base_state["request"] = self.valid_request_payload
        result = retrieve_flights(self.base_state)

        # Verify the node packaged the DB results correctly
        self.assertEqual(len(result["flight_results"]), 1)
        self.assertEqual(result["flight_results"][0]["flight_number"], "JL712")

        # Verify it passed the right arguments to the mock DB
        mock_search.assert_called_once_with(
            origin="SIN",
            destination="TYO",
            departure_date="2026-06-15",
            return_date=None,
            passengers=1,
            cabin_class="economy"
        )

    # --- 4. FORMATTING NODE TESTS ---

    def test_format_response_path_a_validation_failed(self):
        """Path A: Ensures an invalid request returns a 'failed' status payload."""
        self.base_state["request"] = {"task_id": "err-123"}
        self.base_state["is_valid"] = False
        self.base_state["validation_error"] = "Missing parameters"

        result = format_response(self.base_state)
        response_dict = result["response"]

        self.assertEqual(response_dict["status"], "failed")
        self.assertEqual(response_dict["error"], "Missing parameters")

    def test_format_response_path_b_no_flights_found(self):
        """Path B: Ensures an empty search result asks the user for clarification."""
        self.base_state["request"] = self.valid_request_payload
        self.base_state["is_valid"] = True
        self.base_state["flight_results"] = []  # DB found nothing

        result = format_response(self.base_state)
        response_dict = result["response"]

        self.assertEqual(response_dict["status"], "needs_clarification")
        self.assertIn("No flights found", response_dict["clarification_needed"])
        self.assertEqual(response_dict["results"], [])


if __name__ == '__main__':
    unittest.main()