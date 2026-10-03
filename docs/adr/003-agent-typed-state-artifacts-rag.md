# ADR 003: LangGraph Agent Typed State, Tool Artifacts, RAG Grounding & SSE Streaming

* **Status**: Implemented / Accepted
* **Date**: October 2026
* **Deciders**: AI & Data Engineering Pair
* **Related Track**: Track 3: Modern LangGraph Agent ([Backend Roadmap](../roadmap/backend-roadmap.md#brain-track-3-modern-langgraph-agent-typed-state-tool-artifacts--rag-grounding))

---

## Context

In the initial implementation of NutriBuddy's conversational assistant:
1. **Brittle String-Matching for Tool Outputs**: When generating FDA-style nutrition labels, the agent printed a message containing `/labels/<filename>.png` in its raw chat response. The FastAPI backend relied on regex (`re.search(r"/labels/([A-Za-z0-9_]+\.png)", text)`) to detect and surface images to the frontend. If the model rephrased its response or omitted the raw path, the image preview failed to render.
2. **Disconnected Knowledge Base (RAG)**: An isolated ChromaDB vector store (`RAGService`) existed for cookbook PDFs, but was not accessible to the LangGraph ReAct agent. The agent had no ability to search uploaded dietary guides or retrieve culinary knowledge.
3. **Synchronous Execution & Lack of Streaming**: The chat endpoint (`/api/chat`) ran synchronously blocking worker threads, providing no streaming tokens or step-by-step tool execution feedback (e.g., notifying the user when USDA search or label generation begins).

---

## Decisions

### 1. LangGraph Tool Artifacts (`content_and_artifact`)
We migrated LangGraph tools (`calculate_recipe_nutrition`, `generate_label_image`) to LangChain's `response_format="content_and_artifact"`.
* The tool function returns a 2-tuple: `(content_for_llm: str, artifact: dict)`.
* LangGraph automatically attaches the artifact to `ToolMessage.artifact`.
* The `NutritionAgent._extract_result` method deterministically inspects messages in graph state, extracting structured payloads:
  * `type: "label_image"` ➔ Populates `image_path` and `artifacts` directly.
  * `type: "recipe_nutrition"` ➔ Populates `exportable` recipe data and `artifacts`.
* A regex fallback is maintained for backwards compatibility if no artifact is attached.

### 2. RAG Knowledge Base Agent Tool (`search_recipe_knowledge`)
We created the `search_recipe_knowledge` tool within [backend/agent/tools.py](file:///Users/nathanglen/NutriBuddy/backend/agent/tools.py) which:
* Queries `RAGService` (ChromaDB + Gemini embeddings) for relevant context passages.
* Includes chunk text, source document filename, and page number for authoritative attribution.
* Formats search results cleanly into JSON for LLM synthesis and citation in user responses.

### 3. Asynchronous Non-Blocking Execution & Server-Sent Events (SSE)
* Added `NutritionAgent.arun(message, thread_id)` using `graph.ainvoke()` for non-blocking event-loop execution in FastAPI routes.
* Added `NutritionAgent.astream_events(message, thread_id)` using LangGraph's `astream_events(version="v2")`.
* Created `POST /api/chat/stream` in [backend/api/routes/chat.py](file:///Users/nathanglen/NutriBuddy/backend/api/routes/chat.py) utilizing FastAPI `StreamingResponse` to deliver SSE event types:
  * `event: token`: Chunked textual tokens as they are emitted from the model.
  * `event: tool_start`: Real-time notification of tool execution (`search_recipe_knowledge`, `calculate_recipe_nutrition`, etc.).
  * `event: tool_end`: Completion notification with structured artifacts.
  * `event: done`: Final message, generated image path, thread ID, and artifact collection.

---

## Consequences & Impact

### Positive
* **Deterministic UI Hydration**: The UI receives exact file paths and structured macro totals directly from tool artifacts without regex parsing risks.
* **Grounding in Culinary Knowledge**: The conversational agent can answer questions using uploaded documents (cookbooks, dietary manuals) with accurate source and page citations.
* **Modern Real-Time UX**: The frontend can stream AI responses in real-time with visual indicators when tools are running.
* **Scalable Concurrency**: Async execution frees up FastAPI worker threads during LLM and external I/O waits.

### Backwards Compatibility
* Existing synchronous callers and legacy regex outputs remain fully supported via fallback resolution in `_extract_result`.
