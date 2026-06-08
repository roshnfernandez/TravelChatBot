from langgraph.graph.state import CompiledStateGraph


def get_mermaid_graph(state_graph: CompiledStateGraph) -> str:
    return state_graph.get_graph().draw_mermaid()