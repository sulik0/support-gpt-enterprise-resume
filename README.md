# SupportGPT Enterprise

[![CI](https://github.com/sulik0/support-gpt-enterprise-resume/actions/workflows/ci.yml/badge.svg)](https://github.com/sulik0/support-gpt-enterprise-resume/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-workflow-orange)](https://github.com/langchain-ai/langgraph)

SupportGPT Enterprise 是面向售后客服场景的 Agent 平台。系统将初版 FAQ 问答升级为支持工单理解、业务 Tool 联动、Hybrid RAG、安全风控、回复校验、Human-in-the-loop 审批、OpenTelemetry 可观测和离线评测的 LangGraph Workflow。

## 核心能力

| 领域 | 当前能力 |
|---|---|
| Agent Workflow | Analyzer、Tooling、Retriever、Resolver、QA、Escalation；Tool/RAG 并行执行 |
| LLM | `mock/openai/azure`；`openai` 兼容 OpenAI、DeepSeek、Qwen 和 vLLM |
| RAG | ChromaDB、Hybrid Search、轻量 rerank、版本/类别过滤、citation |
| Tool Calling | CRM、OMS、Ticket Mock Adapter；ToolRegistry、Schema、RBAC、风险控制 |
| Safety | 多层 Prompt Injection 规则、Qwen3Guard Adapter、Risk Engine、PII/泄露过滤 |
| HITL | 高风险、低置信度、低 QA、投诉与退款场景审批 |
| Observability | OpenTelemetry 统一采集，Collector 导出 LangSmith Trace 和 Prometheus Metrics |
| Evaluation | Ragas、DeepEval、确定性 Agent/Security Evaluator、100 条 Baseline Workflow Replay |
| Feedback | AgentRun + FeedbackEvent + Trace 关联，脱敏 SFT/DPO 候选导出 |
| Frontend | 用户咨询页、客服审批后台、Agent 可观测页 |

## 快速启动

### 后端

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python scripts/seed_kb.py
uvicorn src.main:app --reload
```

- Health：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

默认使用 Mock LLM、SQLite 和本地 ChromaDB，Redis 未启动时可正常降级。

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 [http://127.0.0.1:3000](http://127.0.0.1:3000)。

### 真实 LLM

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=https://example.com/v1
LLM_API_KEY=<api-key>
LLM_MODEL_NAME=<model-name>
```

Analyzer 和 QA 可配置 `LLM_FAST_*`、`LLM_ANALYZER_MODEL_NAME` 和 `LLM_QA_MODEL_NAME` 使用小模型。默认回复语言与用户当前输入一致，除非用户明确要求切换。

## 测试与评测

```bash
python -m pip install -r requirements/test.txt
python -m compileall src tests
python -m pytest -q
```

Baseline 100 真实 Workflow Replay：

```bash
python scripts/run_baseline_eval.py --dry-run
python scripts/run_baseline_eval.py --confirm-live
```

Ragas + DeepEval：

```bash
python -m pip install -r requirements/eval.txt
python scripts/run_agent_eval.py --rag-engine ragas --agent-engine deepeval
```

评测报告保存在 `evaluation/reports/`，该目录不进 Git。正式 Baseline 同时生成不可变时间戳 JSON/Markdown 快照与可直接打开的 `latest` 普通文件副本，并固定记录 Dataset Hash、模型、Prompt/Workflow 版本、阈值、Token、延迟与 Trace 配置。每次还会基于已生成 JSON 纯离线生成 `error_analysis_<run_id>.md` 和 `error_analysis_latest.md`，只分析 FAIL Case，不重放 Workflow 或调用 LLM。

## 可观测

最小启动 OpenTelemetry Collector：

```bash
docker compose -f deployment/docker-compose.yml up -d otel-collector
```

应用只使用 OpenTelemetry SDK：

```text
Application
  -> OTLP Collector
      -> LangSmith Trace
      -> Prometheus Metrics
          -> Grafana
```

Collector 未启动时后端会 fail-open，不影响 Agent 主流程。

## 文档

本项目只维护以下统一文档：

1. [项目概览](docs/00_PROJECT_CONTEXT.md)
2. [技术架构](docs/01_ARCHITECTURE.md)
3. [业务流程](docs/02_BUSINESS_LOGIC.md)
4. [事实口径](docs/03_INTERVIEW_CANON.md)
5. [技术决策](docs/04_DECISIONS.md)
6. [工程指南](docs/05_ENGINEERING_GUIDE.md)
7. [Prompt 设计](docs/06_PROMPTS.md)
8. [AI 交接](docs/07_AI_HANDOFF.md)
9. [任务清单](docs/08_TODO.md)
10. [面试问答](docs/09_INTERVIEW_QA.md)

未来任何 AI 或开发者参与项目前，应先阅读 [docs/00_PROJECT_CONTEXT.md](docs/00_PROJECT_CONTEXT.md)。

## 实现边界

- CRM、OMS、Ticketing 和默认 LLM 是 Mock Adapter，架构保留替换边界，但不得表述为已接入真实企业系统。
- Docker Compose 和 Kubernetes 是可复现部署模板，不代表已生产上线。
- Qwen3Guard 默认关闭，Risk Engine 阈值尚未用真实客服数据校准。
- Feedback Pipeline 当前只导出脱敏训练候选，尚未执行 SFT/DPO 训练和自动发布。
