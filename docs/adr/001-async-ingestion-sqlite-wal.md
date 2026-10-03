# ADR 001: Asynchronous Concurrency, SQLite WAL Caching & Two-Stage Food Matching

## Status
**Accepted & Implemented** (Commit `dca7390`)

## Context
NutriBuddy's nutrition calculation and food matching pipeline previously had critical scalability bottlenecks:
1. **Sequential HTTP Latency**: Calculating multi-ingredient recipes ran synchronous serial requests to USDA FoodData Central. A 5-ingredient recipe caused up to 10 sequential blocking HTTP calls (taking 5–7 seconds).
2. **Monolithic Cache Writes**: The cache relied on `.cache/food_cache.json`. Every write serialized and overwrote the entire file on disk, creating race conditions under concurrent requests and risking file corruption.
3. **High CPU/GPU Matching Overhead**: Matching queries against 50 USDA candidates executed 50 sequential PyTorch `SentenceTransformer` embeddings and pairwise cosine loops in Python, causing ~417 ms latency per match.

## Decisions

### 1. Asynchronous Ingestion & Concurrency
* Replaced `requests.Session` with `httpx.AsyncClient`, connection pooling (`max_connections=40`), and exponential backoff retry handling.
* Converted `calculate_recipe` in `NutritionService` to `calculate_recipe_async` using `asyncio.gather` bounded by an `asyncio.Semaphore` to saturate network bandwidth without exceeding USDA rate limits.
* Preserved synchronous fallback methods for backwards compatibility with legacy callers and sync agent tools.

### 2. Embedded SQLite Storage in WAL Mode
* Replaced `.cache/food_cache.json` with an embedded SQLite database (`backend/data/cache.db`).
* Enabled Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) and normal synchronization (`PRAGMA synchronous=NORMAL;`).
* Added TTL expiration support and automatic migration of existing legacy JSON records.

### 3. Two-Stage Food Matcher
* Introduced a two-stage hybrid retrieval strategy:
  * **Stage 1 (Lexical Pre-Filter)**: Evaluates all candidates using RapidFuzz `token_set_ratio` and `token_sort_ratio` in < 0.5 ms. Exact/near-exact matches bypass neural models entirely.
  * **Stage 2 (Batched Semantic Rerank)**: Takes the top $K=6$ candidates and performs batched tensor encoding and vectorized dot product in a single operation.

## Consequences & Empirical Results
* **Food Matching**: Latency dropped from 417 ms to 7.9 ms (52.9x faster).
* **Network Throughput**: 3.34x higher throughput on concurrent USDA lookups.
* **Cache Latency**: Writes reduced to 0.052 ms (atomic, thread-safe); reads reduced to 0.006 ms.
* **Compatibility**: 100% backwards-compatible; all 13 automated tests pass.
