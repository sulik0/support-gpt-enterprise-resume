# SupportGPT Enterprise 🚀

[![CI](https://github.com/sulik0/support-gpt-enterprise-resume/actions/workflows/ci.yml/badge.svg)](https://github.com/sulik0/support-gpt-enterprise-resume/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.ly/badge/FastAPI-0.110%2B-green)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.ly/badge/LangGraph-0.0.28-orange)](https://github.com/langchain-ai/langgraph)
[![Docker](https://img.shields.ly/badge/Docker-ready-blue)](https://www.docker.com/)

**SupportGPT Enterprise** is an enterprise-grade AI Copilot platform built for Fortune 500 customer support organizations. It integrates RAG-based context retrieval, multi-agent orchestration, advanced input/output safety guardrails, token/cost observability, and human-in-the-loop workflows into a unified, high-performance service.

The platform is designed to augment customer service agents rather than replace them, providing suggested responses, ticket summarization, CRM contexts, order lookups, and real-time hallucination evaluation metrics.

---

## 🌟 Feature Highlights & Matrix

For a quick summary of the capabilities supported by this repository, please review our [Feature Matrix](FEATURE_MATRIX.md).

| Feature Group | Capabilities | Tech Stack | Documentation |
|---|---|---|---|
| **Multi-Agent** | Intent classification, RAG retrieval, resolution drafting, QA verification, SLA routing | LangGraph, LangChain | [Agent Architecture](docs/AGENT_ARCHITECTURE.md) |
| **RAG Pipeline** | Versioning, chunking splitters, hybrid vector search, source citations | ChromaDB, PyPDF2, BeautifulSoup | [RAG Architecture](docs/RAG_ARCHITECTURE.md) |
| **Observability** | Workflow/LLM/Retriever/Tool traces, latency, tokens, USD estimates | LangSmith, OpenTelemetry, Prometheus | [Observability Phase 1](docs/OBSERVABILITY_PHASE1.md) |
| **AI Guardrails** | PII scrubbing, injection detection, jailbreak blocks, output leak filters | Regex, String heuristic checks | [Security Guide](docs/SECURITY_GUIDE.md) |
| **HITL Approval** | Staging drafts, agent modifications, approval history, review latency checks | FastAPI, SQLAlchemy, PostgreSQL | [System Design](SYSTEM_DESIGN.md) |
| **Evaluation** | Golden dataset, Faithfulness, Answer Relevancy, Context Precision/Recall | Ragas, DeepEval | [Agent Evaluation](docs/AGENT_EVALUATION_PHASE1.md) |

---

## 📂 Repository Structure

The layout reflects production-grade engineering principles:

```text
supportgpt-enterprise/
├── .github/workflows/         # CI/CD Pipeline
├── src/                       # FastAPI Backend
│   ├── auth/                  # JWT Authentication & RBAC
│   ├── models/                # SQLAlchemy & Pydantic Schemas
│   ├── agents/                # LangGraph Node Implementations
│   ├── guardrails/            # AI Safety Guards (PII, Injections)
│   ├── rag/                   # Ingestion, Chunking, ChromaDB, KB versions
│   ├── approval/              # Human-in-the-Loop workflows
│   ├── memory/                # Conversation & session state stores
│   ├── tools/                 # CRM, Ticketing, and Invoice tools
│   ├── observability/         # Tracing, Prometheus, Cost estimators
│   ├── evaluation/            # Unified metrics engines
│   └── llm/                   # Pluggable LLM Providers (Mock / OpenAI)
├── frontend/                  # Vite + React Dashboard UI
├── tests/                     # Test Suites (Unit, integration, E2E, load)
├── docs/                      # Phase 1-10 manuals and diagrams
├── deployment/                # Dockerfile, compose, and Kubernetes manifests
├── monitoring/                # Prometheus targets and Grafana templates
└── scripts/                   # DB seeding and evaluation execution scripts
```

---

## 🛠️ Quick Start Guide

### 1. Local Development (Backend)
1. Clone the repository and navigate to the directory:
   ```bash
   cd supportgpt-enterprise
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements/test.txt  # only needed for local tests
   ```
4. Configure env parameters:
   ```bash
   cp .env.example .env
   ```
5. Seed the Vector Database:
   ```bash
   python scripts/seed_kb.py
   ```
6. Run the FastAPI development server:
   ```bash
   uvicorn src.main:app --reload
   ```
   Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to view the interactive API docs.

### 2. Local Development (Frontend)
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) to view the interactive dashboard.

### 3. Running with Docker Compose
To boot up the entire stack including backend, databases, cache, and Prometheus:
```bash
docker-compose -f deployment/docker-compose.yml up --build
```

---

## 📊 Telemetry and Observability Dashboard
When the stack is running, you can access monitoring panels:
- **API Health**: [http://localhost:8000/health](http://localhost:8000/health)
- **Prometheus Scraper**: [http://localhost:8000/metrics](http://localhost:8000/metrics)
- **Prometheus Dashboard**: [http://localhost:9090](http://localhost:9090)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000)

Phase 1 的 LangSmith + OpenTelemetry + Prometheus/Grafana 配置、指标和验收流程参见 [Observability Phase 1](docs/OBSERVABILITY_PHASE1.md)。

---

## 🧪 Testing Suite
To verify compilation and test coverage:
```bash
python -m compileall src tests
pytest tests/test_agents.py tests/test_rag.py -q
```
Optional evaluation and load-test dependencies are split into `requirements/eval.txt` and `requirements/load.txt`. For details, see our [Testing Guide](docs/TESTING_GUIDE.md).

Run the independent phase-1 Agent/RAG evaluation after seeding the knowledge base:

```bash
pip install -r requirements/eval.txt
python scripts/run_agent_eval.py --engine ragas
```

---

## 📄 Detailed Specifications
For deep technical explorations, read our dedicated guides:
- [System Design & Database Schemas](SYSTEM_DESIGN.md)
- [Enterprise Architecture Blueprint](ARCHITECTURE.md)
- [API Documentation Specification](API_DOCUMENTATION.md)
- [Deployment & Orchestration Manual](DEPLOYMENT_GUIDE.md)
- [Contributing Standards](CONTRIBUTING.md)

---

## Resume Upgrade Notes

This fork includes resume-oriented upgrades and documentation:

- [Resume Upgrade Plan](docs/RESUME_UPGRADE_PLAN.md)
- [Resume Project Guide](docs/RESUME_PROJECT_GUIDE.md)
- [Resume Upgrade Change Log](docs/CHANGELOG_RESUME_UPGRADE.md)
- [Mock Boundaries and Resume Claims](docs/MOCK_BOUNDARIES.md)

The CRM, order-management, and ticketing integrations are local mock adapters intended for demo and interview use. The architecture is adapter-driven so these mocks can be replaced with real enterprise service clients.
