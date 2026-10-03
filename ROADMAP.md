# NutriBuddy Backend Engineering Roadmap

This document outlines four foundational AI & Data Engineering initiatives designed to elevate NutriBuddy's backend performance, intelligence, and architectural resilience.

---

## ⚡ Track 1: High-Performance Async Ingestion & Vector Caching Pipeline (Current Focus)
> **Engineering Disciplines**: Modern Data Engineering, Async Concurrency, Persistent Embedded Storage, Vector Search & Reranking.

### Objective
Overhaul the USDA FoodData Central ingestion pipeline and food-matching mechanism to eliminate sequential I/O latency, remove heavy cold-start PyTorch dependencies, and introduce durable, thread-safe embedded caching.

### Key Architecture Components
1. **Async Batch Ingestion**:
   - Refactor `USDAClient` and `NutritionService` to use an asynchronous HTTP client (`httpx.AsyncClient`) with connection pooling.
   - Implement concurrent ingredient fetching via `asyncio.gather` with rate limiting, timeouts, and exponential backoff retry policies.
2. **Embedded Storage Layer (SQLite / DuckDB with WAL mode)**:
   - Deprecate the single monolithic `.cache/food_cache.json` file.
   - Establish an embedded relational storage engine (`sqlite3` / `DuckDB`) storing:
     - `food_searches` (raw queries, search results, TTL timestamps)
     - `food_nutrients` (FDC ID, full nutrient records, portion data)
     - `ingredient_embeddings` (cached vectors for semantic search)
3. **Optimized Two-Stage Food Matching & Reranking**:
   - Replace in-process heavy `SentenceTransformer` (PyTorch) on every candidate evaluation.
   - Stage 1: Fast lexical/token filtering using SQLite FTS5 / RapidFuzz.
   - Stage 2: Fast lightweight semantic similarity (via Google Gemini `text-embedding-004` or ONNX/FastEmbed) with cosine similarity cache.

---

## 🚀 Track 2: Natural Language Ingredient & Portion Normalization Engine
> **Engineering Disciplines**: Information Extraction, Structured NLP / LLM Function Calling, Domain-Specific Unit Conversion.

### Objective
Allow users to enter natural language recipes and arbitrary units (*"2 1/2 cups rolled oats, 2 tbsp chia seeds, 1 medium banana"*) instead of requiring manual gram inputs.

### Key Architecture Components
1. **Structured Ingestion Pipeline**:
   - Leverage Gemini structured outputs / Pydantic schemas to parse unstructured recipe text or voice transcripts into:
     ```python
     class ParsedIngredient(BaseModel):
         quantity: float
         unit: str  # e.g., 'cup', 'tbsp', 'medium', 'clove'
         food_name: str
         preparation: Optional[str]  # e.g., 'chopped', 'roasted'
     ```
2. **USDA Portions Ingestion Engine**:
   - Ingest and index USDA's `foodPortions` API data (which provides `measureUnit`, `gramWeight`, `amount`, and `modifier`).
   - Match parsed culinary units to the official USDA gram conversion factors for that specific food item.
3. **Data Quality & Heuristic Fallback Layer**:
   - Standard density conversion table for volumetric culinary units (cups, tbsp, tsp, fl oz -> grams by food category: dry powder, liquid, produce).
   - Ambiguity detection and confidence scoring with user clarification fallbacks.

---

## 🧠 Track 3: Modern LangGraph Agent: Typed State, Tool Artifacts & RAG Grounding
> **Engineering Disciplines**: Advanced Agentic AI, StateGraph Architecture, Retrieval-Augmented Generation (RAG).

### Objective
Transition the nutrition conversational agent from loose string-matching and prompt-hacking into a deterministic, artifact-driven LangGraph workflow grounded in uploaded cookbook/dietary data.

### Key Architecture Components
1. **Typed Graph State & Tool Artifacts**:
   - Upgrade `AgentState` to store structured objects: `conversation_messages`, `active_recipe_data`, `generated_label_artifacts`, and `nutrition_summaries`.
   - Eliminate fragile regex matching (`re.search(r"/labels/...png")`) by passing generated label artifacts directly through the graph state to API callers.
2. **RAG Tool Integration**:
   - Expose the existing `RAGService` (ChromaDB + Gemini embeddings) to the LangGraph agent as tools (`search_recipe_knowledge`, `consult_dietary_guidelines`).
   - Provide source document citations and grounding in agent responses.
3. **Streaming Agent Events (Server-Sent Events)**:
   - Provide real-time token streaming and step-by-step tool execution updates (e.g., *"Searching USDA database..."*, *"Calculating macronutrients..."*) to the client via SSE.

---

## 👁️ Track 4: Multimodal Vision Ingestion Pipeline
> **Engineering Disciplines**: Multimodal AI Engineering, Document OCR / Vision Extraction, Entity Resolution.

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
