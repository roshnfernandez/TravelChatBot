from agents.flight_agent.agent import flight_agent_graph
from agents.hotel_agent.agent import hotel_agent_graph
from orchestrator.agent import orchestrator_graph
from utils.util import get_mermaid_graph


def main():
    print(get_mermaid_graph(orchestrator_graph))
    print(get_mermaid_graph(flight_agent_graph))
    print(get_mermaid_graph(hotel_agent_graph))

if __name__ == "__main__":
    main()
