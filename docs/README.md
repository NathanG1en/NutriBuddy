# NutriBuddy Documentation Hub

Welcome to the internal engineering documentation for **NutriBuddy**. This directory is structured to provide full transparency into system architecture, architectural decisions, performance benchmarks, and development roadmaps for both human engineers and AI agents.

---

## 🗂️ Documentation Structure

```
docs/
├── README.md                           # This document (Documentation Hub & Index)
│
├── architecture/                       # System design, data flow, agent state
│   └── system-overview.md              # Full-stack architectural breakdown
│
├── roadmap/                            # Forward-looking technical initiatives
│   └── backend-roadmap.md              # 4 core AI & Data Engineering tracks
│
├── benchmarks/                         # Empirical measurements & profiling reports
│   └── track-2-async-caching.md        # Benchmark report: Async I/O, SQLite WAL & Reranking
│
└── adr/                                # Architecture Decision Records (ADRs)
    └── 001-async-ingestion-sqlite-wal.md  # ADR: Moving from serial JSON to async SQLite WAL
```

---

## 🧭 Navigation Index

### 1. Architecture & Design
* **[System Overview](file:///Users/nathanglen/NutriBuddy/docs/architecture/system-overview.md)**: Full component breakdown covering FastAPI, LangGraph ReAct agent, ChromaDB RAG, and Firebase Auth.
* **[Architecture Decision Records (ADRs)](file:///Users/nathanglen/NutriBuddy/docs/adr)**: Context, trade-offs, and consequences of key technical pivots.
  * [ADR 001: Async Ingestion & Embedded SQLite Storage](file:///Users/nathanglen/NutriBuddy/docs/adr/001-async-ingestion-sqlite-wal.md)

### 2. Roadmaps & Planning
* **[Backend Engineering Roadmap](file:///Users/nathanglen/NutriBuddy/docs/roadmap/backend-roadmap.md)**: Detailed breakdown of the four engineering tracks:
  * **Track 1**: Natural Language Ingredient & Portion Normalization Engine *(Next)*
  * **Track 2**: High-Performance Async Ingestion & Vector Caching Pipeline *(Completed)*
  * **Track 3**: Modern LangGraph Agent: Typed State, Tool Artifacts & RAG Grounding
  * **Track 4**: Multimodal Vision Ingestion Pipeline

### 3. Empirical Benchmarks
* **[Track 2 Benchmark Report](file:///Users/nathanglen/NutriBuddy/docs/benchmarks/track-2-async-caching.md)**:
  * 52.9x faster food matching (417 ms → 7.9 ms)
  * 3.3x higher network throughput (`asyncio.gather` + connection pooling)
  * Sub-millisecond SQLite WAL atomic writes (0.052 ms) and reads (0.006 ms)

---

## 🤖 For AI Coding Agents

When working on tasks in this repository, follow these conventions:
1. **Adding Documentation**: Place architectural docs in `docs/architecture/`, benchmarks in `docs/benchmarks/`, and architectural decisions in `docs/adr/`.
2. **Context Grounding**: Check `docs/architecture/system-overview.md` for service wiring and dependency injection before creating new routes or agent tools.
3. **Benchmarks**: Whenever optimizing a pipeline, capture reproducible benchmark scripts in tests or documentation reports inside `docs/benchmarks/`.
