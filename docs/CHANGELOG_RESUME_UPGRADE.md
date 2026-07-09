# Resume Upgrade Change Log

This document records the resume-oriented upgrades made on top of the upstream project.

## Commit 1: `docs: add resume upgrade plan`

Commit: `9f31e13`

### Files Changed

- `docs/RESUME_UPGRADE_PLAN.md`

### What Changed

- Added a clear upgrade plan for turning the project into a resume-ready large-language-model application.
- Separated implemented capabilities from mock integrations and production gaps.
- Documented the expected GitHub upload flow and current remote/auth constraints.

### Resume Value

This prevents overclaiming. It gives a defensible interview narrative:

- The project has a real FastAPI/LangGraph/RAG/HITL backbone.
- CRM/order/ticketing integrations are mocked adapters for local demo use.
- Production hardening is explicitly scoped as future work.

## Commit 2: `feat: add tool context node to agent workflow`

Commit: `824da7b`

### Files Changed

- `src/agents/tooling.py`
- `src/agents/graph.py`
- `src/agents/resolver.py`

### What Changed

- Added `ToolingAgent`, a dedicated LangGraph node that enriches the Agent state with structured business context.
- The tooling node calls mock CRM, order-management, and ticket-history adapters.
- Added `tool_context` to the shared Agent state.
- Inserted the new node into the workflow:

```text
analyzer -> tooling -> retriever -> resolver -> qa -> escalation
```

- Updated the resolver so generated responses receive both:
  - RAG knowledge-base context.
  - Structured tool context from customer/order/ticket mock adapters.

### Resume Value

This enables an honest resume claim:

> Designed a tool-augmented customer support Agent workflow where the Agent enriches each ticket with CRM, order, and historical ticket context before generating a response.

### Mock Boundary

The tools are local mock adapters, not real enterprise APIs. This is acceptable for a resume/demo project if described as simulated CRM/OMS/ticketing integrations.

## Commit 3: `feat: add optional Redis conversation memory`

Commit: `57d948d`

### Files Changed

- `src/memory/__init__.py`
- `src/memory/redis_memory.py`
- `src/main.py`

### What Changed

- Added `RedisConversationMemory`, an optional Redis-backed short-term memory adapter.
- The adapter loads and saves recent chat turns by `session_id`.
- Redis is optional; if `REDIS_URL` is not configured, the system continues using SQL `SessionMemory`.
- Updated `/chat` flow to:
  - Prefer Redis recent messages when available.
  - Persist conversation history to SQL.
  - Save recent messages back to Redis.

### Resume Value

This enables an honest resume claim:

> Implemented Redis short-term conversation memory with SQL-backed durable session history.

### Mock Boundary

Redis usage is real but optional. In local demo mode the app still runs without Redis. Docker Compose provides Redis for integration-style runs.

## Verification Performed

### Passed

```bash
python -m compileall src
```

```bash
.venv/bin/python -c 'import src.main; from src.memory.redis_memory import redis_memory; print("memory import ok", redis_memory.max_turns)'
```

```bash
.venv/bin/python -c 'from src.agents.graph import run_agent_workflow; import asyncio; out=asyncio.run(run_agent_workflow({"ticket_id":1,"customer_id":"cust_101","subject":"refund","description":"I want refund for charge","kb_version":"v1"})); print(out["department"], bool(out.get("tool_context")), out.get("tool_context", {}).get("mocked"), out["approval_required"])'
```

Output:

```text
billing True True True
```

### Known Test Limitation

Full pytest currently crashes with exit code `139` in this local Python 3.13/macOS environment after installing broad evaluation dependencies. The failure happens during pytest startup and appears related to native dependency/plugin interactions, not a normal assertion failure.

Recommended stabilization:

- Pin Python to 3.11 or 3.12.
- Add a lock file.
- Split optional evaluation dependencies into an extra group.
- Disable third-party telemetry in tests.

## Commit 4: `feat: add security short-circuit routing`

### Files Changed

- `src/agents/graph.py`

### What Changed

- Added `route_after_analyzer`, a LangGraph conditional router.
- Tickets flagged by guardrails as security threats now route directly from `analyzer` to `escalation`.
- Security-blocked requests skip:
  - Tool context lookup.
  - RAG retrieval.
  - Response generation.
  - QA validation.

Updated workflow:

```text
analyzer
  ├── security threat -> escalation -> END
  └── normal request  -> tooling -> retriever -> resolver -> qa -> escalation -> END
```

### Resume Value

This enables an honest resume claim:

> Added conditional routing in the LangGraph workflow so prompt-injection and jailbreak attempts are blocked early and escalated without invoking downstream tools or retrieval.

### Mock Boundary

The guardrail detectors are rule-based. This is acceptable for a resume project, but a production system should combine rules with model-based classifiers, audit logging, and policy-driven severity levels.

## Commit 5: `feat: expose tool context in API responses`

### Files Changed

- `src/models/schemas.py`
- `src/main.py`

### What Changed

- Added `tool_context` to `ChatResponse`.
- Added `tool_context` to `SuggestResponseResponse`.
- `/chat` and `/suggest-response` now return the structured context gathered by the tool node.

Example tool context:

```json
{
  "customer_profile": {
    "customer_id": "cust_101",
    "tier": "VIP",
    "open_tickets_count": 2
  },
  "recent_orders": [],
  "past_tickets": [],
  "mocked": true
}
```

### Resume Value

This makes the tool-augmented Agent behavior visible from the API layer. It is useful for demos, debugging, and interview explanation because the response can prove which business context was injected before answer generation.

### Mock Boundary

The returned `tool_context.mocked` field intentionally marks local tool adapters as mock data. Keep this visible in demos to avoid overclaiming real enterprise integrations.

## Commit 6: `docs: document mock boundaries for resume claims`

### Files Changed

- `docs/MOCK_BOUNDARIES.md`
- `README.md`

### What Changed

- Added a dedicated document explaining which parts are implemented and which are mocked.
- Added safe resume wording and risky wording to avoid.
- Added a mock-to-production upgrade checklist.
- Linked the document from README.

### Resume Value

This helps defend the project in interviews. It shows engineering judgment by making the boundary between demo adapters and production integrations explicit.

## Commit 7: `feat: add hybrid retrieval reranking`

### Files Changed

- `src/rag/vector_store.py`
- `tests/test_rag.py`
- `docs/RAG_ARCHITECTURE.md`
- `docs/RESUME_PROJECT_GUIDE.md`
- `docs/MOCK_BOUNDARIES.md`

### What Changed

- Upgraded `VectorStoreManager.query_kb` from pure vector search to hybrid retrieval.
- Added ChromaDB vector candidate over-fetching.
- Added in-process BM25-style lexical scoring over version/category-filtered chunks.
- Added a lightweight reranker that merges vector similarity, normalized lexical score, and exact-term overlap.
- Added a focused test proving keyword-heavy support queries can outrank unrelated chunks.
- Updated RAG and resume documentation with the implementation boundary.

### Resume Value

This enables an honest resume claim:

> Built a hybrid RAG retrieval layer that combines vector similarity with BM25-style lexical scoring and reranking, improving support-policy retrieval for exact terms such as warranty phrases, refund windows, product names, and order-related keywords.

### Mock Boundary

The lexical scorer is implemented in-process for demo and interview use. It is not a production distributed search backend. A production version should use OpenSearch, Elasticsearch, PostgreSQL full-text search, or a dedicated reranker service.

### Verification Performed

Passed:

```bash
python -m compileall src tests
```

```bash
.venv/bin/python -c 'from src.rag.vector_store import vector_store; print("vector store import ok", vector_store.collection_name)'
```

```bash
.venv/bin/python -c 'from src.agents.graph import run_agent_workflow; import asyncio; out=asyncio.run(run_agent_workflow({"ticket_id":7,"customer_id":"cust_101","subject":"warranty headphones","description":"My damaged headphones need warranty support and serial number validation","kb_version":"v1"})); print({"department": out.get("department"), "citations": len(out.get("context_citations", [])), "tool_context": bool(out.get("tool_context")), "approval_required": out.get("approval_required")})'
```

Output:

```text
{'department': 'general', 'citations': 2, 'tool_context': True, 'approval_required': False}
```

Known local limitation:

- `.venv/bin/python -m pytest tests/test_rag.py -q` still exits with code `139` in this Python 3.13/macOS environment, matching the existing native dependency crash documented earlier.

## Commit 8: `chore: stabilize python dependency profiles`

### Files Changed

- `.python-version`
- `.github/workflows/ci.yml`
- `requirements.txt`
- `requirements/base.txt`
- `requirements/test.txt`
- `requirements/eval.txt`
- `requirements/load.txt`
- `docs/DEPENDENCY_PROFILES.md`
- `deployment/Dockerfile`
- `pyproject.toml`
- `README.md`
- `docs/TESTING_GUIDE.md`

### What Changed

- Standardized the project on Python 3.11 for local development, Docker, and CI.
- Split dependencies into runtime, test, evaluation, and load-test profiles.
- Kept the root `requirements.txt` as a runtime install entry point.
- Moved optional RAGAS/DeepEval and Locust dependencies out of the default install path.
- Added a GitHub Actions workflow that compiles the code and runs focused backend/RAG tests.
- Updated README and testing docs with the reproducible install path.
- Added a dedicated dependency profile guide.

### Resume Value

This enables an honest resume claim:

> Improved project reproducibility by separating runtime, test, evaluation, and load-test dependency profiles, then added a Python 3.11 CI workflow for compile checks and focused Agent/RAG tests.

### Production Boundary

This is dependency hygiene, not a fully locked production build. A stricter production setup should add a generated lock file, vulnerability scanning, image scanning, and a full CI matrix.

### Verification Performed

Passed:

```bash
python -m compileall src tests
```

```bash
.venv/bin/python -c 'import yaml; yaml.safe_load(open(".github/workflows/ci.yml")); print("ci yaml ok")'
```

```bash
.venv/bin/python -c 'import src.main; print("main import ok")'
```

Checked:

- `requirements/test.txt` resolves `-r base.txt` from the `requirements/` directory.
- Dockerfile copies both `requirements.txt` and the `requirements/` directory before install.

Known local limitation:

- A `pip install --dry-run -r requirements/test.txt` check was cancelled because the current local virtualenv is Python 3.13 and began preparing native package metadata. The committed CI workflow uses Python 3.11.
