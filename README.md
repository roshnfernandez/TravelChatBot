# TravelChatBot: Multi-Agent Orchestrator

## Overview

TravelChatBot is a multi-agent travel orchestration framework built with LangGraph. It acts as a central state machine managing autonomous, specialized micro-agents (Flight Agent, Hotel Agent) to handle complex, non-linear user travel requests. The system is designed for high resilience, parallel execution, and strict memory efficiency.

## System Design Decisions & Challenges

Throughout the development of this orchestrator, several complex system design challenges were identified and resolved to ensure production readiness and infinite scalability.

### 1. Scalable Intent Routing (Registry + Strategy Pattern)

**The Challenge:** Hardcoding routing logic (e.g., massive `if/else` chains checking for `"flight"` or `"hotel"`) creates a brittle bottleneck. Every time a new agent is added, the core router has to be modified, risking regressions.

**The Decision:** Implemented a combined Registry and Strategy pattern. The `delegate_to_agents` router dynamically determines the execution path by looking up the validated `IntentType` against a central `AGENT_REGISTRY`.

**The Result:** The routing logic strictly adheres to the Open-Closed Principle (OCP). You can add 50 new agents (Rental Cars, Dining, Excursions) in the future without ever touching or breaking the core orchestrator's routing code.

### 2. Custom Reducers for Parallel Execution (Preventing Race Conditions)

**The Challenge:** When routing to multiple agents simultaneously (e.g., searching for a flight and a hotel concurrently), LangGraph prevents parallel nodes from overwriting the same state key, resulting in pipeline crashes.

**The Decision:** Engineered a custom `Annotated` dictionary reducer (`merge_agent_responses`) that establishes a structured, key-based merge protocol.

**The Result:** The system safely intercepts and combines concurrent payloads from parallel nodes into a single unified state block without data loss or collisions.

### 3. Three-Tier Garbage Collection (Preventing Context Bloat)

**The Challenge:** Holding raw JSON payloads and full conversation histories in ephemeral memory causes massive token bloat, degrades LLM reasoning, and leads to physical memory leaks over long sessions.

**The Decision:** Built an aggressive, concurrent memory management pipeline:

- **Time-To-Live (TTL) Sweeper:** Sweeps the state array to identify and soft-delete unconfirmed intents left in limbo for over configured minutes.

- **Hard-Delete Protocols:** Upgraded the `merge_intents` and `merge_agent_responses` reducers to physically pop len - configured n objects out of RAM using `None` overrides and deactivated flags.

- **Sliding Window Summarization:** Utilizes LangGraph's `RemoveMessage` commands to physically delete 'n' old interactions and raw JSON, rolling them up into a lightweight, incremental Pydantic `SessionSummary`.

**The Result:** API token costs remain flat, and the context window stays pristine regardless of how long the user session lasts.

## Repository Structure

The repository follows a modular, domain-driven design, cleanly separating the central orchestration logic from the individual micro-agents and user interface.

```text
TravelChatBot/
├── agents/                     # Isolated edge agents (Micro-agent layer)
│   ├── flight_agent/           # Autonomous flight search & booking agent
│   │   ├── agent.py            # Agent-specific LangGraph definition
│   │   ├── mock_data.py        # Database simulation layer
│   │   └── schemas.py          # Strict Pydantic A2A request/response contracts
│   └── hotel_agent/            # Autonomous hotel search & booking agent
│       ├── agent.py
│       ├── mock_data.py
│       └── schemas.py
├── interface/                  # Frontend & User Interaction layer
│   └── app.py                  # Streamlit UI (or similar frontend framework)
├── orchestrator/               # The Central Brain (State Machine)
│   ├── agent.py                # Core LangGraph orchestrator compiler & routing
│   ├── ai_nodes.py             # LLM-driven nodes (Intent parsing, Generation)
│   ├── const.py                # System constants and Agent Registry
│   ├── enums.py                # Strict typing for statuses (NEW, VALID, INVALID)
│   ├── func_nodes.py           # Deterministic processing & Garbage collection nodes
│   ├── models.py               # Pure Pydantic state schemas & intents
│   ├── prompts.py              # Centralized system instructions
│   └── util.py                 # Custom graph reducers & routing helper functions
├── tests/                      # Unit test suite
│   ├── test_flight_agent.py
│   ├── test_hotel_agent.py
│   └── test_orchestrator_agent.py
├── utils/                      # Global project utilities
│   └── util.py
└── .env                        # Environment variables (OpenAI Keys)
```

## Setup & Installation

This project utilizes **uv**.

### Prerequisites

- Python 3.10+
- An OpenAI API Key
- uv package manager

### Installation Guide

#### 1. Clone the repository and navigate to the project directory:

```bash
git clone https://github.com/roshnfernandez/TravelChatBot
cd TravelChatBot
```

#### 2. Install uv (if you haven't already):

```bash
# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 3. Sync the Project Environment:

Run the sync command. `uv` will automatically read your project files, create a `.venv` virtual environment, and lock your dependencies with exact precision.

```bash
uv sync
```

#### 4. Configure Environment Variables:

Create a `.env` file in the root directory and add your OpenAI API key:

```env
OPENAI_API_KEY=your_sk_key_here
```

#### 5. Launch the Application:

You can bypass manual environment activation entirely by using `uv run`, which automatically executes the command within the synchronized virtual environment:

```bash
uv run streamlit run interface/app.py
```