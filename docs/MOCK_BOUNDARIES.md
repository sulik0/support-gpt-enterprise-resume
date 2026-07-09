# Mock Boundaries and Resume Claims

This project is designed as a resume-ready enterprise customer support Agent application. Some integrations are implemented as local mock adapters so the system can run without private enterprise services.

## Safe Resume Claims

These claims are backed by code in this repository:

- FastAPI backend for chat, ticket, auth, approval, evaluation, and customer context APIs.
- LangGraph Agent workflow with analyzer, tooling, retriever, resolver, QA, and escalation nodes.
- Conditional routing for security-blocked requests.
- Tool context enrichment through CRM, order-management, and ticket-history adapters.
- RAG vector store with ChromaDB, embeddings, metadata filters, KB versioning, lightweight hybrid retrieval, and reranking.
- SQLAlchemy data models for users, tickets, session memory, knowledge documents, and approvals.
- Optional Redis short-term conversation memory with SQL fallback.
- Human-in-the-loop approval workflow for high-risk or low-confidence responses.
- Guardrail checks for prompt injection, jailbreak patterns, PII masking, and response filtering.
- Prometheus metrics hooks for request, Agent, QA, escalation, token, and cost tracking.
- Docker Compose stack with backend, PostgreSQL, Redis, and Prometheus.

## Mocked Integrations

These integrations are intentionally mocked:

| Area | Current Implementation | Why It Is Mocked | Production Replacement |
| --- | --- | --- | --- |
| CRM | In-memory customer profiles in `src/tools/crm.py` | No access to private CRM | Salesforce/Zendesk/HubSpot API client |
| Order Management | In-memory order history in `src/tools/order_mgmt.py` | No real OMS account | E-commerce/OMS REST or GraphQL adapter |
| Ticket History | In-memory historical tickets in `src/tools/ticketing.py` | No real helpdesk backend | Jira/ServiceNow/Zendesk ticket API |
| LLM | `mock` provider by default | Local deterministic demo | OpenAI/Azure/OpenRouter/Qwen/DeepSeek provider |
| Evaluation | Deterministic and optional RAGAS/DeepEval code paths | No stable production eval dataset | Curated golden set plus LLM-as-judge pipeline |
| Lexical Retrieval | In-process BM25-style scorer over Chroma-filtered chunks | Not a distributed search index | Elasticsearch/OpenSearch/PostgreSQL full-text search |

## Recommended Interview Wording

Use:

> I implemented the Agent workflow, RAG pipeline, memory layer, approval flow, and observability hooks. CRM/order/ticketing integrations are mock adapters so the project can run locally, but they are isolated behind tool classes and can be replaced by real enterprise API clients.

Avoid:

> This is connected to real enterprise CRM/order systems.

Use:

> The default local demo uses a mock LLM provider for reproducibility. The provider interface also includes OpenAI and Azure adapters.

Avoid:

> The system was load-tested in a real production support center.

## Mock-to-Production Upgrade Checklist

- Replace mock tools with real API clients.
- Add tool schemas, permissions, timeouts, retries, and circuit breakers.
- Add audit logging for all tool calls.
- Add per-tenant knowledge-base isolation.
- Replace in-process lexical scoring with a production search backend.
- Add cross-encoder or LLM-based reranking before answer generation.
- Pin Python and dependencies in a lock file.
- Move optional evaluation dependencies to a separate install extra.
- Add CI on Python 3.11/3.12.
- Add real-world golden evaluation datasets.

## Resume Bullet Boundaries

### Strong Bullet

> Designed a tool-augmented LangGraph workflow that enriches customer support tickets with CRM, order, and historical ticket context before RAG-based response generation.

Why it is safe:

- The workflow really has a tooling node.
- The tools really return structured data.
- The mock boundary is explicit.

### Strong Bullet

> Implemented Redis short-term conversation memory with SQL-backed durable session history.

Why it is safe:

- Redis adapter exists.
- SQL `SessionMemory` exists.
- Redis is optional and gracefully degrades.

### Needs Careful Wording

> Integrated CRM and order systems.

Better:

> Built mock CRM/order adapters behind a tool interface to simulate enterprise integrations and demonstrate the Agent tool-calling path.

### Needs Careful Wording

> Built production-grade RAG evaluation.

Better:

> Added a RAG evaluation module and documented target metrics such as faithfulness, context recall, and hallucination rate.
