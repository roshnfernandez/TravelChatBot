import sys
import os
import uuid

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
from orchestrator.agent import orchestrator_graph

load_dotenv()

# --- PAGE CONFIG ---
st.set_page_config(page_title="Travel Assistant", layout="centered")
st.title("Friendly Travel Assistant")
st.caption("I can help you book flights and hotels. Where would you like to go?")

# --- INITIALIZE SESSION STATE ---
# This holds the exact OrchestratorState
if "graph_state" not in st.session_state:
    st.session_state.graph_state = {
        "messages": [],
        "intents": [],
        "agent_responses": {},
        "session_id": str(uuid.uuid4())
    }

# --- DISPLAY CHAT HISTORY ---
for msg in st.session_state.graph_state["messages"]:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(msg.content)

# --- HANDLE USER INPUT ---
if prompt := st.chat_input("E.g., I need a flight to Tokyo on June 15th..."):

    # 1. Display the user's message immediately
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Append the new message to state
    st.session_state.graph_state["messages"].append(HumanMessage(content=prompt))

    # 3. Show a loading spinner while the Orchestrator works
    with st.spinner("Let me check that for you..."):
        try:
            # Invoke the graph with the current state
            new_state = orchestrator_graph.invoke(st.session_state.graph_state)

            # Update Streamlit session state with the new graph state
            st.session_state.graph_state = new_state

            # The last message in the state will be the AI's response
            ai_response = new_state["messages"][-1].content

            # 4. Display the AI's response
            with st.chat_message("assistant"):
                st.markdown(ai_response)

        except Exception as e:
            st.error("Oops! Something went wrong behind the scenes.")
            st.exception(e)