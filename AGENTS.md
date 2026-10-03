# NutriBuddy Repository Agent Instructions (`AGENTS.md`)

This file defines behavioral constraints, architectural standards, and mandatory documentation protocols for all AI coding agents working on **NutriBuddy**.

---

## 📋 Mandatory "Definition of Done" Documentation Protocol

Before declaring any feature, roadmap track, or architectural refactoring complete, you **MUST** document your work in the [`docs/`](docs/README.md) directory following these rules:

### 1. Architectural Updates
If any service, database schema, agent state, tool interface, or API route was modified or introduced:
* Update [`docs/architecture/system-overview.md`](docs/architecture/system-overview.md) to reflect the new state, data flow, and components.

### 2. Architecture Decision Records (ADRs)
Whenever an architectural choice, optimization, or pattern is adopted (e.g. choice of storage engine, parsing strategy, agent graph structure):
* Create a numbered ADR in [`docs/adr/`](docs/adr/) using the format `NNN-<topic>.md` (e.g. `002-natural-language-ingredient-parser.md`).
* Include:
  * **Status**: Accepted / Implemented
  * **Context**: The problem in legacy code or missing capability
  * **Decisions**: Technical approach and components built
  * **Consequences**: Measurable impacts, trade-offs, and backwards-compatibility notes

### 3. Roadmap Tracking
* Update [`docs/roadmap/backend-roadmap.md`](docs/roadmap/backend-roadmap.md) to update the status of the completed track or milestone, linking to relevant PRs or ADRs.

### 4. Benchmarking & Empirical Verification
* If the task involved performance, throughput, or latency optimization, write an empirical benchmark report in [`docs/benchmarks/`](docs/benchmarks/) detailing before-and-after metrics.

### 5. Documentation Hub Index
* Ensure any newly created markdown document is properly indexed in [`docs/README.md`](docs/README.md).

---

## 🧪 Testing & Verification Standards
* **Test Suite**: Always run and verify all tests pass with zero errors:
  ```bash
  uv run pytest
  ```
* **New Features**: Every new service or parser must have corresponding automated unit/integration tests in the `tests/` directory.

---

## 💻 Tech Stack Guidelines
* **Python Runtime**: Python 3.11+ managed with `uv`.
* **Async Concurrency**: Use `httpx.AsyncClient` with connection pooling and `asyncio.gather` for non-blocking I/O.
* **Storage Layer**: Embedded SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`). Avoid monolithic file rewrites.
* **Typing & Validation**: Strictly typed schemas using `Pydantic v2` (`SettingsConfigDict`, `BaseModel`).
