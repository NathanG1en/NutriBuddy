# NutriBuddy Backend Engineering Roadmap

This document outlines four foundational AI & Data Engineering initiatives designed to elevate NutriBuddy's backend performance, intelligence, and architectural resilience.

---

## 🚀 Track 1: Natural Language Ingredient & Portion Normalization Engine
* **Status**: ✅ **Completed** (Implemented in `feature/natural-ingredient-parsing`, see [ADR 002](../adr/002-natural-language-ingredient-parser.md))
* **Engineering Disciplines**: Information Extraction, Structured NLP / LLM Function Calling, Domain-Specific Unit Conversion.

### Objective
Allow users to enter natural language recipes and arbitrary units (*"2 1/2 cups rolled oats, 2 tbsp chia seeds, 1 medium banana"*) instead of requiring manual gram inputs.

### Delivered Architecture Components
1. **Two-Tier Structured Ingestion Pipeline** (`IngredientParser`):
   - Fast deterministic regex/rule engine (< 1ms) parsing mixed fractions (`2 1/2`), unicode fractions (`½`), ranges, units, and preparation modifiers.
   - Structured fallback via Google Gemini 2.0 Flash (`with_structured_output`) for complex freeform text.
2. **USDA Portions & Unit Conversion Matrix** (`UnitConverter`):
   - Ingests and maps USDA `foodPortions` metadata to resolve food-specific gram weights (e.g. `1 cup oats = 81g`, `1 cup milk = 245g`).
   - Built-in culinary density table (g/ml) for volumetric items (flours, sugars, nut butters, oils).
   - Discrete count heuristics for produce and items (eggs, bananas, garlic cloves).
3. **API & Agent Integration**:
   - Upgraded `NutritionService.calculate_recipe_async` to accept natural language strings, structured objects, or legacy gram dicts.
   - Added `/api/recipe/parse` endpoint to FastAPI.
   - Updated LangGraph `calculate_recipe_nutrition` and added `parse_recipe_text` tool.

---

## ⚡ Track 2: High-Performance Async Ingestion & Vector Caching Pipeline
* **Status**: ✅ **Completed** (Implemented in `feature/async-ingestion-caching`, see [ADR 001](../adr/001-async-ingestion-sqlite-wal.md), [Benchmark Report](../benchmarks/track-2-async-caching.md))
* **Engineering Disciplines**: Modern Data Engineering, Async Concurrency, Persistent Embedded Storage, Vector Search & Reranking.

### Objective
Overhaul the USDA FoodData Central ingestion pipeline and food-matching mechanism to eliminate sequential I/O latency, remove heavy cold-start PyTorch dependencies, and introduce durable, thread-safe embedded caching.

### Delivered Architecture Components
1. **Async Batch Ingestion** (`USDAClient`):
   - Refactored to `httpx.AsyncClient` with connection pooling (`max_connections=40`).
   - Non-blocking concurrent ingredient resolution via `asyncio.gather` with exponential backoff retries.
2. **Embedded Storage Layer** (`SQLiteCache`):
   - Deprecated monolithic `.cache/food_cache.json`.
   - Thread-safe embedded SQLite in WAL mode (`PRAGMA journal_mode=WAL;`) with sub-millisecond atomic writes and TTL expiration.
3. **Two-Stage Food Matching & Reranking** (`FoodMatcher`):
   - Stage 1: Sub-millisecond RapidFuzz lexical pre-filter with exact-match fast path.
   - Stage 2: Batched `SentenceTransformer` vector reranking (52.9x faster matching).

---

## 🧠 Track 3: Modern LangGraph Agent: Typed State, Tool Artifacts & RAG Grounding
* **Status**: ✅ **Completed** (Implemented in `feature/agent-state-artifacts-rag`, see [ADR 003](../adr/003-agent-typed-state-artifacts-rag.md))
* **Engineering Disciplines**: Advanced Agentic AI, StateGraph Architecture, Retrieval-Augmented Generation (RAG).

### Objective
Transition the nutrition conversational agent from loose string-matching and prompt-hacking into a deterministic, artifact-driven LangGraph workflow grounded in uploaded cookbook/dietary data.

### Delivered Architecture Components
1. **Typed Graph State & Tool Artifacts**:
   - Upgraded tools (`calculate_recipe_nutrition`, `generate_label_image`) using `response_format="content_and_artifact"` to attach structured data directly to `ToolMessage.artifact`.
   - Built `NutritionAgent._extract_result` to deterministically extract `image_path`, `exportable`, and structured `artifacts`, eliminating fragile regex matching.
2. **RAG Tool Integration**:
   - Implemented `search_recipe_knowledge` tool querying `RAGService` (ChromaDB + Gemini embeddings) with source document and page attribution.
   - Grounded LLM responses in uploaded cookbooks and dietary guidelines.
3. **Streaming Agent Events (Server-Sent Events)**:
   - Implemented `NutritionAgent.astream_events(version="v2")` yielding real-time SSE event streams (`token`, `tool_start`, `tool_end`, `done`).
   - Added `POST /api/chat/stream` endpoint for real-time frontend token streaming and tool execution updates.
   - Converted standard `/api/chat` endpoint to non-blocking async `agent.arun()`.

---

## 👁️ Track 4: Multimodal Vision Ingestion Pipeline
* **Status**: 📋 **Planned**
* **Engineering Disciplines**: Multimodal AI Engineering, Document OCR / Vision Extraction, Entity Resolution.

### Objective
Enable users to capture photos of meals, restaurant menus, handwritten recipes, or packaged food nutrition labels, and automatically convert them into structured nutrition data.

### Key Architecture Components
1. **Multimodal Ingestion**:
   - Image upload endpoint supporting photos of plates, ingredient lists, or physical Nutrition Facts panels.
   - Multimodal prompt extraction using Gemini 2.0 Flash Vision to identify food items, estimated portion sizes, and label values.
2. **Entity Resolution & Cross-Validation**:
   - Resolve extracted visual foods against USDA FoodData Central to validate estimated macros and ingredients.
3. **Digital Label Reconstruction**:
   - Automatically hydrate `LabelBuilder` and `LabelService` from scanned physical labels to generate clean, editable digital FDA labels.
