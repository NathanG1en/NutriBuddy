# NutriBuddy System Architecture Overview

This document provides a comprehensive overview of NutriBuddy's full-stack architecture, service layers, and data pipelines.

---

## 🏛️ High-Level System Architecture

```
                       +---------------------------------------+
                       |       React / Vite Frontend           |
                       | (AI Chat, Recipe Lab, Label Builder)  |
                       +---------------------------------------+
                                           │
                           HTTPS (JWT / Bearer Token)
                                           ▼
                       +---------------------------------------+
                       |            FastAPI Backend            |
                       | (CORS, Auth, Static Files, REST APIs) |
                       +---------------------------------------+
                                     │           │
                 ┌───────────────────┘           └──────────────────┐
                 ▼                                                  ▼
     +──────────────────────+                           +──────────────────────+
     | LangGraph ReAct Agent|                           |   Domain Services    |
     | (ChatGoogleGenAI)    |                           | (Nutrition, Labels)  |
     +──────────────────────+                           +──────────────────────+
                 │                                                  │
                 ▼                                                  ▼
     +──────────────────────+                           +──────────────────────+
     |    Agent Tools       |───[Dependency Injection]──▶   USDAAsyncClient    |
     | (Search, Calc, Label)|                           |   SQLiteCache (WAL)  |
     +──────────────────────+                           |   FoodMatcher (Hybrid|
                                                        +──────────────────────+
```

---

## ⚙️ Backend Core Services

### 1. `NutritionService` ([backend/services/nutrition.py](file:///Users/nathanglen/NutriBuddy/backend/services/nutrition.py))
* **Role**: Primary business logic orchestrator for food searches and recipe nutrition calculations.
* **Key Methods**:
  * `search_async(query: str) -> Optional[dict]`: Queries USDA via `USDAClient`, caches results in `SQLiteCache`, and uses `FoodMatcher` to rank candidates.
  * `get_nutrition_async(fdc_id: int) -> Optional[dict]`: Fetches full nutrient profile and portion sizes, mapping to standard FDA nutrient IDs.
  * `calculate_recipe_async(ingredients: list[dict]) -> dict`: Concurrently resolves all ingredients via `asyncio.gather`, computes scaled macronutrients and aggregates recipe totals.

### 2. `USDAClient` ([backend/services/usda_client.py](file:///Users/nathanglen/NutriBuddy/backend/services/usda_client.py))
* **Role**: Resilient, non-blocking HTTP client for the USDA FoodData Central API.
* **Key Features**:
  * `httpx.AsyncClient` with connection pooling (`max_connections=40`, `max_keepalive_connections=20`).
  * Exponential backoff and jitter for HTTP 429 (rate limits) and 5xx errors.
  * `asyncio.Semaphore(8)` rate-limiting protection.
  * Batch fetching (`get_foods_batch_async`).

### 3. `SQLiteCache` ([backend/services/cache.py](file:///Users/nathanglen/NutriBuddy/backend/services/cache.py))
* **Role**: Embedded persistent key-value cache.
* **Key Features**:
  * Pure standard-library SQLite storage with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`).
  * Thread-safe with connection pooling and TTL expiration support.
  * Backward-compatible `FileCache` alias.

### 4. `FoodMatcher` ([backend/services/food_matcher.py](file:///Users/nathanglen/NutriBuddy/backend/services/food_matcher.py))
* **Role**: Two-stage candidate matching engine.
* **Key Features**:
  * Stage 1: RapidFuzz lexical pre-filter (< 0.5 ms) with exact-match fast path.
  * Stage 2: Batched `SentenceTransformer` vector reranking on top 6 candidates.

### 5. `LabelService` ([backend/services/labels.py](file:///Users/nathanglen/NutriBuddy/backend/services/labels.py))
* **Role**: FDA-compliant nutrition label generator.
* **Key Features**:
  * Layout engine rendering pixel-accurate FDA Nutrition Facts images via Pillow (`PIL`).
  * Configurable daily value percentages, serving sizes, and container servings.

---

## 🤖 Conversational Agent (`LangGraph`)

* **State**: `AgentState` managing message history with `MemorySaver` checkpointer.
* **Model**: Google Gemini (`gemini-2.0-flash-exp`).
* **Graph Flow**:
  ```
  User Input ──► Agent (LLM) ──► Tool Calling? ──► Tools (USDA / Labels) ──► Agent ──► Response
                                     │ (No tools)
                                     ▼
                                  Response
  ```

---

## 🔐 Authentication & Security

* Firebase Authentication handles Google Sign-In on the frontend.
* [backend/api/security.py](file:///Users/nathanglen/NutriBuddy/backend/api/security.py) validates Firebase JWT ID tokens on protected endpoints using `firebase_admin.auth.verify_id_token()`.
