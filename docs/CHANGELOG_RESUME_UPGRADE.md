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
