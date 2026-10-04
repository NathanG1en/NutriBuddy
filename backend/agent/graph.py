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
from langchain_google_genai import ChatGoogleGenerativeAI
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

SYSTEM_PROMPT = """You are NutriAgent, an expert nutrition and culinary intelligence assistant.

You can help users:
1. Search for foods in the USDA FoodData database
2. Retrieve comprehensive nutrition facts for individual foods
3. Calculate combined nutrition for recipes with multiple ingredients and natural units
4. Parse raw recipe text into structured culinary components
5. Generate official FDA-style nutrition labels (text or image)

## For single foods:
1. Use `search_foods` to locate the food and its FDC ID.
2. Use `get_nutrition` to retrieve full FDA macro and micronutrient details.
3. Use `format_nutrition_label` or `generate_label_image` to render a label.

## For multi-ingredient recipes:
1. Users can specify natural cooking measurements (e.g., "2 cups rolled oats, 1 cup milk, 2 tbsp peanut butter, 1 medium banana").
2. Use `calculate_recipe_nutrition` with:
   - A list of natural phrases: ["2 cups rolled oats", "1 cup milk", "2 tbsp peanut butter"]
   - Or structured objects: [{"name": "rolled oats", "quantity": 2, "unit": "cup"}]
   - Or a multi-line recipe text string.
3. The engine automatically resolves culinary volumetric units, counts, and USDA portions into exact gram weights and aggregates all 15 FDA nutrients.
4. You can also use `parse_recipe_text` to structure raw recipe inputs.
5. Use `generate_label_image` with the calculated nutrition result to render a downloadable FDA label.
## For uploaded meal images & photos:
1. When a user provides or mentions an uploaded meal image file, use `analyze_food_image` to inspect the dish.
2. The vision pipeline will detect ingredients, estimate portions, and cross-reference them with USDA FoodData Central.

## For cookbooks and uploaded documents:
1. Use `search_recipe_knowledge` to retrieve culinary techniques, recipe instructions, and dietary knowledge from the RAG store.
2. Always attribute your answers to the source documents and page numbers returned.

Be friendly, concise, accurate, and helpful!"""


# ============================================
# Graph Nodes
# ============================================


def create_agent():
    """Create and return the compiled agent graph."""

    # Get tools and bind to LLM
    tools = get_all_tools()
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0,
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
    """Wrapper class for easier API integration, streaming, and typed artifact resolution."""

    def __init__(self):
        self.graph = create_agent()
        self.tools = get_all_tools()

    def _extract_result(self, result: dict) -> dict:
        """Extract AI response text, typed tool artifacts, and generated image paths."""
        messages = result.get("messages", [])
        if not messages:
            return {"message": "", "image_path": None, "artifacts": []}

        # 1. Extract text from last AI message
        last_message = messages[-1]
        raw_content = getattr(last_message, "content", str(last_message))
        if isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)
                else:
                    text_parts.append(str(part))
            response_text = "\n".join(text_parts)
        else:
            response_text = str(raw_content)

        # 2. Extract typed tool artifacts from ToolMessages
        artifacts = []
        image_path = None
        exportable = None

        for msg in messages:
            artifact = getattr(msg, "artifact", None)
            if artifact and isinstance(artifact, dict):
                artifacts.append(artifact)
                if artifact.get("type") == "label_image":
                    image_path = artifact.get("image_path")
                elif artifact.get("type") in ("recipe_nutrition", "meal_vision"):
                    exportable = artifact

        # Safety fallback: regex search on text if image_path wasn't caught by artifact
        if not image_path:
            import re
            match = re.search(r"/labels/([A-Za-z0-9_]+\.png)", response_text)
            if match:
                image_path = f"/labels/{match.group(1)}"

        return {
            "message": response_text,
            "image_path": image_path,
            "artifacts": artifacts,
            "exportable": exportable,
        }

    def run(self, message: str, thread_id: str = "default") -> dict:
        """
        Run the agent synchronously with a user message.
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}
        result = self.graph.invoke(
            {"messages": [HumanMessage(content=message)]}, config
        )
        return self._extract_result(result)

    async def arun(self, message: str, thread_id: str = "default") -> dict:
        """
        Run the agent asynchronously with non-blocking event loop execution.
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}
        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=message)]}, config
        )
        return self._extract_result(result)

    async def astream_events(self, message: str, thread_id: str = "default"):
        """
        Stream agent events (tokens, tool execution steps, and artifacts) for Server-Sent Events.
        """
        from langchain_core.messages import HumanMessage

        config = {"configurable": {"thread_id": thread_id}}
        input_data = {"messages": [HumanMessage(content=message)]}

        accumulated_text = []
        artifacts = []
        image_path = None

        async for event in self.graph.astream_events(input_data, config, version="v2"):
            kind = event.get("event")

            # Token stream from Chat Model
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    text = chunk.content if isinstance(chunk.content, str) else ""
                    if text:
                        accumulated_text.append(text)
                        yield {"event": "token", "data": {"token": text}}

            # Tool execution start
            elif kind == "on_tool_start":
                name = event.get("name")
                inputs = event.get("data", {}).get("input")
                yield {
                    "event": "tool_start",
                    "data": {"tool": name, "input": str(inputs)[:300]},
                }

            # Tool execution end (with artifact)
            elif kind == "on_tool_end":
                name = event.get("name")
                output = event.get("data", {}).get("output")
                artifact = getattr(output, "artifact", None)
                if artifact and isinstance(artifact, dict):
                    artifacts.append(artifact)
                    if artifact.get("type") == "label_image":
                        image_path = artifact.get("image_path")

                yield {
                    "event": "tool_end",
                    "data": {"tool": name, "artifact": artifact},
                }

        final_text = "".join(accumulated_text)
        if not image_path:
            import re
            match = re.search(r"/labels/([A-Za-z0-9_]+\.png)", final_text)
            if match:
                image_path = f"/labels/{match.group(1)}"

        yield {
            "event": "done",
            "data": {
                "message": final_text,
                "image_path": image_path,
                "artifacts": artifacts,
                "thread_id": thread_id,
            },
        }

    def get_history(self, thread_id: str) -> list:
        """Get conversation history for a thread."""
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = self.graph.get_state(config)
            return state.values.get("messages", [])
        except Exception:
            return []
