import unittest
from datetime import datetime, timedelta
from langchain_core.messages import HumanMessage

from orchestrator.models import FlightIntent, AgentTask, OrchestratorState
from orchestrator.enums import IntentStatus, IntentType

from orchestrator.util import delegate_to_agents, route_to_summarizers
from orchestrator.func_nodes import remove_old_invalid_intents


class TestOrchestratorStateAndLogic(unittest.TestCase):

    def setUp(self):
        """Helper to generate a clean, valid OrchestratorState before every test."""
        self.base_state: OrchestratorState = {
            "messages": [],
            "session_id": "session-xyz-123",
            "summary": None,
            "task_responses_summary": None,
            "intents": [],
            "agent_responses": {}
        }

    # --- 1. ROUTING & DELEGATION TESTS ---

    def test_delegate_to_agents_with_valid_intent(self):
        """Proves that a validated flight intent triggers the flight agent node."""
        valid_flight = FlightIntent(
            intent_id="FLI-OK99",
            intent_type=IntentType.FLIGHT,
            active=True,
            status=IntentStatus.VALID,
            origin="SIN",
            destination="TYO",
            departure_date="2026-06-15"
        )

        self.base_state["intents"] = [valid_flight]

        routes = delegate_to_agents(self.base_state)

        # Use unittest's built-in assertions
        self.assertIn("call_flight_agent", routes)
        self.assertNotIn("generate_response", routes)

    def test_delegate_to_agents_fallback_to_user_on_invalid(self):
        """Proves that an invalid intent bypasses agents and routes to the responder."""
        invalid_flight = FlightIntent(
            intent_id="FLI-FAIL",
            intent_type=IntentType.FLIGHT,
            active=True,
            status=IntentStatus.INVALID,
            missing_info=["departure_date"]
        )

        self.base_state["intents"] = [invalid_flight]

        routes = delegate_to_agents(self.base_state)
        self.assertEqual(routes, ["generate_response"])

    # --- 2. CONCURRENT CLEANUP ROUTING TESTS ---

    def test_route_to_summarizers_triggers_appropriate_cleanup(self):
        """Verifies conditional parallel fanning out for garbage collection nodes."""
        # 1. Force state to exceed message limits
        self.base_state["messages"] = [HumanMessage(content="Hello")] * 15

        # 2. Force state to exceed task history limits
        self.base_state["agent_responses"] = {
            f"task_{i}": AgentTask(
                task_id=f"t-{i}",
                agent_name="flight",
                agent_request='{"intent_id": "FLI-123", "destination": "TYO"}',
                agent_response="{}",
                created_on=datetime.now(),
                processed=False
            ) for i in range(5)
        }

        routes = route_to_summarizers(self.base_state)

        self.assertIn("remove_old_intents", routes)
        self.assertIn("summarize_session", routes)
        self.assertIn("summarize_tasks", routes)

    # --- 3. STATE MUTATION & CLEANUP TESTS ---

    def test_remove_old_invalid_intents_toggles_active_flag(self):
        """Ensures the time-to-live sweeper targets only stale, unconfirmed intents."""
        stale_timestamp = datetime.now() - timedelta(minutes=10)

        stale_intent = FlightIntent(
            intent_id="FLI-OLD",
            intent_type=IntentType.FLIGHT,
            active=True,
            status=IntentStatus.INVALID,
            created_on=stale_timestamp
        )

        confirmed_intent = FlightIntent(
            intent_id="FLI-CONF",
            intent_type=IntentType.FLIGHT,
            active=True,
            status=IntentStatus.CONFIRMED,
            created_on=stale_timestamp
        )

        self.base_state["intents"] = [stale_intent, confirmed_intent]

        # Execute node logic
        result = remove_old_invalid_intents(self.base_state)
        processed_intents = result["intents"]

        # Find processed results by ID
        stale_res = next(i for i in processed_intents if i.intent_id == "FLI-OLD")
        confirmed_res = next(i for i in processed_intents if i.intent_id == "FLI-CONF")

        # Assertions
        self.assertFalse(stale_res.active)  # Soft deleted/Pruned
        self.assertIn("Timeout", stale_res.missing_info[0])
        self.assertTrue(confirmed_res.active)  # Left completely untouched!


if __name__ == '__main__':
    unittest.main()