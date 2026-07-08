# Resume-Oriented Upgrade Plan

## Goal

Upgrade this repository into a resume-ready enterprise customer support Agent project.

The target is not to claim a fully production-hardened SaaS system. The target is to make the implementation credible for interviews by clearly separating:

- Implemented engineering capabilities.
- Mocked business integrations that are acceptable for a resume project.
- Production gaps that can be explained honestly.

## Current Code Audit Summary

### Implemented and Resume-Safe

- FastAPI backend with chat, ticket, approval, auth, evaluation, and customer context APIs.
- SQLAlchemy models for users, tickets, session memory, knowledge documents, and approval records.
- LangGraph workflow with analyzer, retriever, resolver, QA, and escalation nodes.
- ChromaDB vector store with metadata filters and KB versioning.
- Human-in-the-loop approval workflow backed by database records.
- Guardrails for prompt injection, jailbreak patterns, PII masking, and output filtering.
- Prometheus metrics and basic OpenTelemetry setup.
- Docker Compose with backend, PostgreSQL, Redis, and Prometheus.
- Test suite and load-test skeleton.

### Mocked but Resume-Acceptable

- CRM lookup, order lookup, and ticket history tools use in-memory mock data.
- LLM provider defaults to a mock implementation for local development.
- RAG evaluation can be represented with deterministic metrics for demo mode.
- Customer/order/refund data can be synthetic, as long as it is described as a simulated business system.

### Not Production-Grade Yet

- Tool calls are not currently part of the LangGraph workflow; they are separate API helpers.
- Redis is configured but not used for live conversation memory or workflow state.
- Agent graph is linear and lacks conditional routing.
- Dependencies are loosely pinned and test reproducibility is weak on Python 3.13.
- Real external adapters for CRM, OMS, logistics, refund, and ticketing systems are missing.
- RAG lacks BM25 hybrid retrieval and reranking.

## Upgrade Scope

### Phase 1: Resume Boundary Documentation

Add this document and update the project narrative so interviewers can distinguish real implementation from mocked integrations.

Deliverables:

- `docs/RESUME_UPGRADE_PLAN.md`
- Later README updates with resume-safe claims.

### Phase 2: Agent Workflow Upgrade

Add explicit tool context into the LangGraph workflow.

Planned changes:

- Add a `tool_context` field to agent state.
- Add a `tooling` node between analyzer and retriever.
- Use detected department/intent to decide whether to query mock CRM, order, and ticket tools.
- Feed tool context into the resolver prompt.

Resume value:

- Can honestly claim "tool-augmented Agent workflow".
- Can explain tools are mocked adapters standing in for CRM/OMS/ticketing systems.

### Phase 3: Redis Memory Adapter

Add a small Redis-backed memory layer with database fallback.

Planned changes:

- Add `src/memory/redis_memory.py`.
- Store recent chat turns by `session_id`.
- Keep current SQL `SessionMemory` as durable fallback.
- Make Redis optional so local demo still runs without Redis.

Resume value:

- Can honestly claim "Redis short-term memory with SQL durable history".

### Phase 4: Resume README and Interview Notes

Add a practical resume/project guide.

Planned changes:

- Add `docs/RESUME_PROJECT_GUIDE.md`.
- Include project description, bullets, mock boundaries, metrics, and interview talking points.

Resume value:

- Directly usable for resume and interview preparation.

### Phase 5: Verification

Run practical checks after each change:

- `python -m compileall src tests`
- Targeted import checks
- Direct `run_agent_workflow` execution

Known limitation:

- Full pytest currently segfaults in this Python 3.13 environment after installing broad evaluation dependencies. This should be fixed by pinning Python 3.11/3.12 and dependency versions.

## GitHub Upload Plan

Current repository state:

- `origin` points to the upstream project: `git@github.com:adhanushus19/Support-GPT-Enterprise.git`
- GitHub CLI auth for account `sulik0` is currently invalid.

Required before pushing:

1. Create or provide a target repository under your GitHub account.
2. Re-authenticate GitHub CLI or configure a valid push remote.
3. Push the local commits.

Recommended remote name:

```bash
git remote add my-origin git@github.com:<your-account>/support-gpt-enterprise-resume.git
git push -u my-origin main
```

If HTTPS is preferred:

```bash
git remote add my-origin https://github.com/<your-account>/support-gpt-enterprise-resume.git
git push -u my-origin main
```
