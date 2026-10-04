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
# Multi-Node System Prompts
# ============================================

PLANNER_PROMPT = """You are NutriChef, the primary culinary strategist and recipe intelligence assistant for NutriBuddy.

Your role:
1. Deconstruct user queries into clear culinary plans and intent.
2. Locate foods and nutrition details using `search_foods` and `get_nutrition`.
3. When formulating recipes, resolve volumetric ingredients and counts using `calculate_recipe_nutrition` and `parse_recipe_text`.
4. Consult uploaded cookbooks or culinary guidelines via `search_recipe_knowledge` to discover authentic techniques and ingredient pairings.
5. Generate official FDA-style nutrition labels using `generate_label_image`.
6. Inspect uploaded meal photos using `analyze_food_image`.

Guidelines:
- For recipes: Provide clear culinary preparation steps with realistic portion measurements (e.g., cups, tbsp, grams, pieces).
- Always call `calculate_recipe_nutrition` when analyzing multiple ingredients or crafting a recipe.
- Keep your tone culinary-forward, encouraging, and precise."""

AUDITOR_PROMPT = """You are NutriAuditor, the senior registered dietitian and food safety specialist for NutriBuddy.

The recipe, meal analysis, and USDA nutritional totals have been computed above.
Provide your authoritative Dietetic & Safety Audit to complete the user's consultation:

1. **Macronutrient & Energy Evaluation**:
   - Assess caloric density and macro distribution (protein sufficiency, carbohydrate-to-fiber ratio, saturated vs unsaturated fats).
2. **🛡️ Allergen & Health Screening**:
   - Explicitly identify any of the 9 major allergens present: Milk/Dairy, Eggs, Fish, Crustacean Shellfish, Tree Nuts, Peanuts, Wheat/Gluten, Soy, Sesame.
   - Flag any elevated sodium (>1,000mg/serving), excessive added sugars (>25g), or high saturated fats.
3. **Clinical & Culinary Optimization**:
   - Provide 1-2 actionable tips (e.g. pairing Vitamin C for non-heme iron absorption, swapping oils, boosting fiber).

Keep your response authoritative, structured with clear markdown headings, and directly helpful."""


# ============================================
# Graph Nodes & Routing
# ============================================

def create_agent():
    """Create and return the compiled multi-node agent graph."""

    tools = get_all_tools()

    # LLM for culinary planning and tool orchestration
    planner_llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.1,
    ).bind_tools(tools)

    # LLM for registered dietitian audit
    auditor_llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.2,
    )

    # --- Node 1: Planner (NutriChef) ---
    def planner_node(state: AgentState) -> dict:
        messages = state["messages"]
        if len(messages) == 1:
            messages = [SystemMessage(content=PLANNER_PROMPT)] + messages

        response = planner_llm.invoke(messages)
        return {"messages": [response]}

    # --- Node 2: Tools (Execution) ---
    tool_node = ToolNode(tools)

    # --- Node 3: Auditor (NutriAuditor) ---
    def auditor_node(state: AgentState) -> dict:
        messages = state["messages"]
        audit_context = messages + [SystemMessage(content=AUDITOR_PROMPT)]
        response = auditor_llm.invoke(audit_context)
        # Tag response as auditor output
        response.name = "NutriAuditor"
        return {"messages": [response]}

    # --- Routing Logic ---
    def should_continue_planner(state: AgentState) -> str:
        """Route to tools if tool calls exist; if recipe calculated, route to auditor; else END."""
        messages = state["messages"]
        last_message = messages[-1]

        # 1. If LLM wants to call tools, execute them
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # 2. Check if a recipe/meal calculation tool was run and needs dietitian auditing
        audit_trigger_tools = {"calculate_recipe_nutrition", "analyze_food_image"}
        has_recipe_tool = any(
            getattr(m, "name", None) in audit_trigger_tools or
            any(tc.get("name") in audit_trigger_tools for tc in getattr(m, "tool_calls", []))
            for m in messages
        )

        auditor_already_run = any(
            getattr(m, "name", None) == "NutriAuditor"
            for m in messages
        )

        if has_recipe_tool and not auditor_already_run:
            return "auditor"

        return END

    # ============================================
    # Build Multi-Node Graph
    # ============================================

    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("planner", planner_node)
    graph.add_node("tools", tool_node)
    graph.add_node("auditor", auditor_node)

    # Entry point
    graph.set_entry_point("planner")

    # Edges
    graph.add_conditional_edges("planner", should_continue_planner, ["tools", "auditor", END])
    graph.add_edge("tools", "planner")
    graph.add_edge("auditor", END)

    # Compile with checkpoint memory
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

        # 1. Extract text from assistant messages (synthesizing planner and auditor outputs)
        assistant_texts = []
        for msg in messages:
            is_ai = hasattr(msg, "tool_calls") or msg.__class__.__name__ == "AIMessage"
            if is_ai and not getattr(msg, "tool_calls", None):
                raw = getattr(msg, "content", "")
                if isinstance(raw, list):
                    text_parts = [
                        p.get("text", str(p)) if isinstance(p, dict) else str(p)
                        for p in raw
                    ]
                    content_str = "\n".join(text_parts).strip()
                else:
                    content_str = str(raw).strip()
                if content_str and content_str not in assistant_texts:
                    assistant_texts.append(content_str)

        if assistant_texts:
            response_text = "\n\n".join(assistant_texts)
        else:
            last_message = messages[-1]
            response_text = str(getattr(last_message, "content", str(last_message)))

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
