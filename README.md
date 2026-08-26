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
| **AI Guardrails** | Layered direct/indirect Prompt Injection detection, Qwen3Guard semantic classification, PII scrubbing, output filters, independent Risk Engine | Deterministic rules, Qwen3Guard-Gen-0.6B, LangGraph safety routing | [Security Guide](docs/SECURITY_GUIDE.md) |
| **HITL Approval** | Staging drafts, agent modifications, approval history, review latency checks | FastAPI, SQLAlchemy, PostgreSQL | [System Design](SYSTEM_DESIGN.md) |
| **Evaluation** | RAG/Agent/Security unified report, Workflow Replay, confusion matrix and safe-disposition metrics | Ragas, DeepEval, deterministic security evaluator | [Agent Evaluation](docs/AGENT_EVALUATION_PHASE1.md) |

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
│   ├── risk/                  # Independent risk scoring and disposition policy
│   ├── rag/                   # Ingestion, Chunking, ChromaDB, KB versions
│   ├── approval/              # Human-in-the-Loop workflows
│   ├── memory/                # Conversation & session state stores
│   ├── tools/                 # CRM, Ticketing, and Invoice tools
│   ├── observability/         # OpenTelemetry tracing/metrics, Cost estimators
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
   python3.11 -m venv .venv
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
   该配置默认使用 Mock LLM、SQLite、无 Redis 降级模式和版本化的本地 ChromaDB 目录，无需外部服务即可启动。
5. Seed the Vector Database:
   ```bash
   python scripts/seed_kb.py
   ```
6. Run the FastAPI development server:
   ```bash
   uvicorn src.main:app --reload
   ```
   Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser to view the interactive API docs.

   如果本地曾被其他 ChromaDB 大版本写入，请使用新的 `VECTOR_DB_PERSIST_DIR` 并重新执行 `scripts/seed_kb.py`，不要直接复用不兼容的 SQLite schema。

### Optional Fast Model for Analyzer and QA

Resolver 默认继续使用 `LLM_MODEL_NAME`。Analyzer 与 QA 可以共用独立的 OpenAI-compatible 小模型服务，例如 Qwen Turbo：

```dotenv
LLM_FAST_MODEL_NAME=qwen-turbo
LLM_FAST_BASE_URL=<Qwen OpenAI-compatible endpoint>
LLM_FAST_API_KEY=<Qwen API key>
```

如需为两个节点选择不同模型，可再设置 `LLM_ANALYZER_MODEL_NAME` 和 `LLM_QA_MODEL_NAME`。未配置 Fast Model 时，两者自动回退主模型。

### Optional Qwen3Guard semantic safety service

Qwen3Guard 与业务 LLM 使用独立端点，默认关闭，因此不影响无 GPU 的本地启动。可按官方 OpenAI-compatible 方式启动：

```bash
vllm serve Qwen/Qwen3Guard-Gen-0.6B \
  --port 18001 \
  --max-model-len 32768
```

然后在 `.env` 中设置：

```bash
QWEN3_GUARD_ENABLED=true
QWEN3_GUARD_BASE_URL=http://127.0.0.1:18001/v1
QWEN3_GUARD_API_KEY=EMPTY
QWEN3_GUARD_MODEL_NAME=Qwen/Qwen3Guard-Gen-0.6B
```

正常 Workflow 最多增加 `user_input`、`tool_result` 和 `rag_document` 三次 Guard 调用。确定性规则强命中会在 Guard 模型前直接短路。

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
- **Collector Metrics Exporter**: [http://localhost:8889/metrics](http://localhost:8889/metrics)
- **Prometheus Dashboard**: [http://localhost:9090](http://localhost:9090)
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000)

Phase 1 的 OpenTelemetry 统一采集、Collector → LangSmith/Prometheus 导出和 Grafana 验收流程参见 [Observability Phase 1](docs/OBSERVABILITY_PHASE1.md)。

主管或管理员登录 React 工作台后，可打开“Agent 可观测性”页面，查看已持久化的 Agent Run、Workflow Path、Trace ID、延迟、Token、QA、Tool 和 citation 摘要。在 `frontend/.env` 中配置 LangSmith Project 链接：

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_LANGSMITH_PROJECT_URL=https://smith.langchain.com/<your-project-url>
```

前端只保存 Project URL，不得放置 LangSmith API Key。API Key 仍只存在 Collector 环境变量中。

前端分为用户咨询页和客服员工后台。用户页通过 `POST /support/requests` 创建工单并同步执行 Agent：普通请求只返回安全的最终回复，高风险或低质量请求只返回“已转人工”。客服后台通过受 RBAC 保护的 `GET /staff/review-queue` 仅加载待审批工单，打开详情时读取持久化结果，不会重复调用模型。

如果本地未启动 Collector，Backend 会在启动时跳过不可达的 OTLP exporter，避免 `localhost:4318` 重试日志刷屏。需要恢复 LangSmith Trace 时，先启动 Collector，再重启 Backend。前端 JWT 过期时会自动清理旧登录态并要求重新登录。

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
python scripts/run_agent_eval.py --rag-engine ragas --agent-engine deepeval
```

统一 JSON / Markdown 报告还会输出安全专项指标，包括 Prompt Injection 检测的
Precision、Recall、F1、误报率，以及自动化阻断、安全短路、上下文隔离、人工介入和
critical 风险处置正确率。Baseline 100 中的 14 条攻击与 86 条非攻击样本共同构成混淆矩阵。

真实 LLM 回归使用独立的成本保护入口；建议先 Dry Run 核对模型与调用预算：

```bash
python scripts/run_real_llm_regression.py --suite smoke --dry-run
python scripts/run_real_llm_regression.py --suite smoke --confirm-live
```

Mock Provider、缺少密钥、示例模型名和超出调用上限都会在第一次模型请求前失败。报告记录 Provider、Model、Endpoint Host、Token、估算成本和 Workflow 延迟，不记录 API Key。

第一版固定 100 条 Baseline 评测使用独立入口，默认逐条构造完整 Ticket State 并真实回放当前 LangGraph Workflow：

```bash
python scripts/run_baseline_eval.py --dry-run
python scripts/run_baseline_eval.py --confirm-live
```

Case Pass 只由 Intent Accuracy、Department Accuracy、Required Tool Hit Rate、Forbidden Tool Violation Rate、HITL Accuracy 和 Approval Accuracy 决定。报告同时输出端到端及各节点 Average / P50 / P95、Token、模型、Analyzer Rule Hit Rate、LLM 调用次数和 Trace ID；`reference_answer`、priority、expected nodes 与安全标签保留在 Dataset 和报告快照中，但暂不参与本版判定。

### Feedback Pipeline

`/chat` 和 `/suggest-response` 返回 `agent_run_id`。用户评分、人工审批修正和质量评测可据此关联 OpenTelemetry Trace、Prompt / Workflow / Model 版本与执行快照。

导出经过 PII 脱敏和质量门控的训练候选：

```bash
python scripts/export_training_candidates.py
```

详细设计见 [Feedback Pipeline 第一阶段](docs/FEEDBACK_PIPELINE_PHASE1.md)。

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
