# NutriBuddy Performance & Architecture Benchmark Report

This document reports the empirical performance benchmarks comparing NutriBuddy's legacy backend implementation against the **Track 2 (High-Performance Async Ingestion & Vector Caching Pipeline)** implementation on branch `feature/async-ingestion-caching`.

---

## Executive Summary

| Subsystem | Legacy Architecture | Track 2 Architecture | Speedup / Impact |
| :--- | :--- | :--- | :--- |
| **Food Matching & Reranking** | 417 ms (Sequential PyTorch loop) | **7.9 ms** (Two-stage hybrid) | **52.9x faster (98% reduction)** |
| **USDA Network Ingestion** | 2.37s (Sequential HTTP requests) | **0.71s** (`asyncio.gather` + pooling) | **3.3x higher throughput** |
| **Cache Write Latency** | Monolithic JSON rewrite on every set | **0.052 ms** (SQLite WAL atomic write) | **Sub-millisecond & thread-safe** |
| **Cache Read Latency** | Full-dict memory parse | **0.006 ms** (6 µs indexed lookups) | **Sub-millisecond retrieval** |
| **Cached Recipe Calculation** | Sequential cache reads | **1.47 ms** for 5 ingredients | **Real-time instant UX** |

---

## 1. Food Matching & Reranking Optimization

### The Problem in Legacy Code
The previous `FoodMatcher` implementation suffered from severe computational overhead:
1. When USDA returned 50 candidate food items, the system executed **50 individual, sequential PyTorch tensor embeddings** (`SentenceTransformer.encode(..., convert_to_tensor=True)`).
2. Pairwise cosine similarities (`util.pytorch_cos_sim`) were calculated in a serial Python `for` loop.
3. Every user query blocked the thread for nearly half a second (400–600ms) on CPU/MPS before selecting a match.

### The Track 2 Architecture
* **Stage 1 (Sub-millisecond Lexical Pre-Filter)**: Candidates are rapidly scored using combined RapidFuzz `token_set_ratio` (60%) and `token_sort_ratio` (40%). This eliminates non-viable candidates in **< 0.5 ms**.
* **Exact-Match Fast Path**: If a candidate description matches the query or achieves $\ge 98\%$ lexical similarity, the neural network is completely bypassed.
* **Stage 2 (Batched Vectorized Rerank)**: Only the top $K$ ($K=6$) candidates are passed to the neural model, encoded in a **single batched vector tensor operation**, and scored via vectorized dot products.

### Empirical Benchmark Results (50 Candidates)
```text
Old Unbatched Matcher (avg over 5 runs):  416.98 ms
New Two-Stage Matcher (avg over 20 runs):    7.88 ms
---------------------------------------------------
Net Latency Reduction: 409.10 ms (52.9x faster)
```

---

## 2. Asynchronous Ingestion & Concurrency

### The Problem in Legacy Code
In `calculate_recipe()`, each ingredient was resolved sequentially over HTTP:
$$\text{Total Time} = \sum_{i=1}^{N} \Big(\text{Search Latency}_i + \text{Detail Latency}_i\Big)$$
For a recipe with 5 ingredients, this meant 10 serial blocking HTTP requests. If each request took ~500ms, the user waited 5 to 7 seconds.

### The Track 2 Architecture
* Replaced `requests.Session` with `httpx.AsyncClient` utilizing keep-alive connection pooling (`Limits(max_connections=40, max_keepalive_connections=20)`).
* `calculate_recipe_async` leverages `asyncio.gather(*[_resolve_ingredient(...)])` to resolve all ingredients in parallel across non-blocking coroutines.
* Bounded by `asyncio.Semaphore` to protect against rate-limit bursts while ensuring maximum saturation of allowable network bandwidth.

### Empirical Network Benchmark Results (4 USDA Searches)
```text
Sequential 4 USDA searches: 2.37s  (0.59s / query)
Concurrent 4 USDA searches: 0.71s  (Speedup: 3.34x)
```

---

## 3. Storage Layer & Atomic WAL Caching

### The Problem in Legacy Code
The previous `FileCache` stored data in a single monolithic JSON file (`.cache/food_cache.json`):
* Every single `set()` operation serialized the entire dictionary and overwrote the file on disk.
* Under concurrent asynchronous requests or multiple users, file writes could interleave, leading to lost writes or corrupted JSON.
* No expiration or TTL support existed.

### The Track 2 Architecture
* Replaced with embedded **SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`)** and `PRAGMA synchronous=NORMAL;`.
* Reads never block writes; writes never block reads.
* Thread-safe with connection pooling, index-backed primary keys, and automatic lazy TTL expiration.
* Legacy migration on startup: 86 previously cached items were seamlessly imported without data loss.

### Empirical Cache Benchmark Results (100 Operations)
```text
SQLite WAL Writes (100 sets): 5.23 ms  (0.052 ms / write operation)
SQLite WAL Reads  (100 gets): 0.58 ms  (0.006 ms / read operation)
```

---

## 4. Test Suite Verification
All 13 unit and integration tests verify correctness across all layers:
```bash
uv run pytest
```
```text
tests/test_cache.py .....                                                [ 38%]
tests/test_food_matcher.py ....                                          [ 69%]
tests/test_nutrition_service.py .                                        [ 76%]
tests/test_usda_client.py ...                                            [100%]

============================== 13 passed in 4.97s ==============================
```
