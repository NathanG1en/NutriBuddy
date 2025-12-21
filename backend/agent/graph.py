# backend/agent/graph.py
"""
LangGraph agent for nutrition queries.

The graph flow:
    User Message → Agent (LLM) → Tool Calls? → Tools → Agent → Response
                       ↓ (no tools)
                   Response
"""

from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from backend.agent.tools import get_all_tools
from backend.config import settings


# ============================================
# State Definition
# ============================================

class AgentState(TypedDict):
    """State that flows through the graph."""
    messages: Annotated[list, add_messages]


# ============================================
# System Prompt
# ============================================

## TODO: add something for unit conversion, update the prompt
SYSTEM_PROMPT = """You are NutriAgent, a helpful nutrition assistant.

You can help users:
1. Search for foods in the USDA database
2. Get detailed nutrition information for single foods
3. Calculate combined nutrition for recipes with multiple ingredients
4. Generate nutrition labels (text or image)

## For single foods:
1. Use search_foods to find the FDC ID
2. Use get_nutrition to get details
3. Use format_nutrition_label or generate_label_image to create a label

## For recipes with multiple ingredients:
1. Use calculate_recipe_nutrition with a JSON array like:
   [{"name": "eggs", "grams": 100}, {"name": "flour", "grams": 200}]
2. This returns combined totals and per-ingredient breakdown
3. Then use generate_label_image with the result to create a recipe label

Note: All nutrition is based on grams. Ask users for approximate grams if needed.

Be friendly, concise, and helpful!"""



# ============================================
# Graph Nodes
# ============================================

def create_agent():
    """Create and return the compiled agent graph."""

    # Get tools and bind to LLM
    tools = get_all_tools()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key
    ).bind_tools(tools)

    # --- Node: Agent ---
    def agent_node(state: AgentState) -> dict:
        """Process messages and decide on actions."""
        messages = state["messages"]

        # Add system prompt if this is the start
        if len(messages) == 1:  # Only user message
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        response = llm.invoke(messages)
        return {"messages": [response]}

    # --- Node: Tools ---
    tool_node = ToolNode(tools)

    # --- Routing Logic ---
    def should_continue(state: AgentState) -> str:
        """Decide whether to call tools or end."""
        last_message = state["messages"][-1]

        # If LLM wants to call tools, route to tools
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # Otherwise, we're done
        return END

    # ============================================
    # Build the Graph
    # ============================================

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Add edges
    graph.add_conditional_edges("agent", should_continue, ["tools", END])
    graph.add_edge("tools", "agent")  # After tools, go back to agent

    # Compile with memory
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# ============================================
# Convenience wrapper
# ============================================

class NutritionAgent:
    """Wrapper class for easier API integration."""

    def __init__(self):
        self.graph = create_agent()
        self.tools = get_all_tools()

    def run(self, message: str, thread_id: str = "default") -> dict:
        """
        Run the agent with a user message.

        Returns:
            dict with 'message' and optionally 'image_path'
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}

        result = self.graph.invoke(
            {"messages": [HumanMessage(content=message)]},
            config
        )

        # Extract the final AI response
        last_message = result["messages"][-1]
        response_text = last_message.content if hasattr(last_message, "content") else str(last_message)

        return {
            "message": response_text,
            "image_path": None  # TODO: Extract from tool results if label was generated
        }

    def get_history(self, thread_id: str) -> list:
        """Get conversation history for a thread."""
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = self.graph.get_state(config)
            return state.values.get("messages", [])
        except Exception:
            return []