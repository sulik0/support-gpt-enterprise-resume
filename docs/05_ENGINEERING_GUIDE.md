# 工程开发指南

> 本文档是 SupportGPT 的唯一工程操作手册，整合原 API、依赖、测试、部署、可观测、安全与 Feedback Pipeline 文档中仍然有效的内容。项目事实以 `00_PROJECT_CONTEXT.md` 和 `03_INTERVIEW_CANON.md` 为准。

## 环境要求

- 推荐 Python 3.11，CI 与 Docker 也使用 Python 3.11。
- Node.js 用于 Vite + React 前端。
- 默认使用 SQLite、Mock LLM、本地 ChromaDB，Redis 可选，因此无外部服务也能运行。
- PostgreSQL、Redis、OpenTelemetry Collector、Prometheus 和 Grafana 由 Docker Compose 提供。

依赖按用途分层：

| 文件 | 用途 |
|---|---|
| `requirements.txt` / `requirements/base.txt` | 后端核心运行时 |
| `requirements/test.txt` | pytest 与 CI |
| `requirements/eval.txt` | Ragas、DeepEval 离线评测 |
| `requirements/load.txt` | Locust 压测 |

## 本地启动

### 后端

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python scripts/seed_kb.py
uvicorn src.main:app --reload
```

验证地址：

- Health Check：`http://127.0.0.1:8000/health`
- Swagger：`http://127.0.0.1:8000/docs`

如果本地 ChromaDB 曾被其他大版本写入，应修改 `VECTOR_DB_PERSIST_DIR` 并重新执行 `scripts/seed_kb.py`，不得复用不兼容的 SQLite schema。

### 前端

```bash
cd frontend
npm install
npm run dev
```

默认地址为 `http://127.0.0.1:3000`。前端包含：

- 用户咨询页：提交问题并获得自动回复或转人工结果。
- 客服后台：只处理异常、待审批和需要人工修改的工单。
- Agent 可观测页：仅 `manager/admin` 可访问 Agent Run 摘要并跳转 LangSmith Project。

## LLM Provider 配置

默认 Provider 为 `mock`。`openai` 是通用 OpenAI-compatible 实现，可接 OpenAI、DeepSeek、Qwen 和 vLLM：

```dotenv
LLM_PROVIDER=openai
LLM_BASE_URL=https://example.com/v1
LLM_API_KEY=<api-key>
LLM_MODEL_NAME=<model-name>
```

Analyzer 和 QA 可使用独立小模型：

```dotenv
LLM_FAST_BASE_URL=<openai-compatible-endpoint>
LLM_FAST_API_KEY=<api-key>
LLM_FAST_MODEL_NAME=qwen-turbo
LLM_ANALYZER_MODEL_NAME=qwen-turbo
LLM_QA_MODEL_NAME=qwen-turbo
```

未配置 Fast Model 时自动回退主模型。Resolver 始终使用 `LLM_MODEL_NAME`。

## 安全配置

输入、Tool Result 和 RAG Document 均经过多层 Prompt Injection 检测；结果与 Qwen3Guard 语义分类共同进入 Risk Engine。Qwen3Guard 默认关闭：

```dotenv
QWEN3_GUARD_ENABLED=true
QWEN3_GUARD_BASE_URL=http://127.0.0.1:18001/v1
QWEN3_GUARD_API_KEY=EMPTY
QWEN3_GUARD_MODEL_NAME=Qwen/Qwen3Guard-Gen-0.6B
```

风险阈值由 `RISK_MEDIUM_THRESHOLD`、`RISK_HIGH_THRESHOLD`、`RISK_CRITICAL_THRESHOLD`、`RISK_LOW_CONFIDENCE_THRESHOLD` 和 `RISK_QA_SCORE_THRESHOLD` 配置。安全检测不得因外部 Guard 服务不可用而使主 API 失败；降级场景会隔离不可信上下文并转人工。

## 主要 API

| 路径 | 用途 | 权限 |
|---|---|---|
| `POST /auth/register` | 注册用户 | 公开 |
| `POST /auth/token` | 获取 JWT | 公开 |
| `GET /auth/users/me` | 查询当前用户 | 登录 |
| `GET /health` | 健康检查 | 公开 |
| `POST /support/requests` | 用户提交客服问题 | 公开演示入口 |
| `POST /chat` | 执行对话 Workflow | 按当前路由约束 |
| `POST /tickets` | 创建工单并持久化 AgentRun | 登录 |
| `GET /tickets` | 查询工单 | 登录 |
| `GET /staff/review-queue` | 待审批工单 | 客服员工 |
| `GET /approvals/pending` | 待审批记录 | 客服员工 |
| `POST /approvals/{approval_id}` | 通过、修改或拒绝草稿 | 客服员工 |
| `POST /feedback/user` | 提交一次性用户评价 | `agent_run_id + feedback_token` |
| `GET /feedback/runs/{agent_run_id}` | 查看 Run 与反馈关联 | `manager/admin` |
| `GET /observability/runs` | 分页查询 Agent Run 摘要 | `manager/admin` |
| `POST /evaluate-response` | 运行单次评估 | 关联 Run 时需 `manager/admin` |

Swagger 是最新 Schema 的最终参考；修改 API 时必须同步 Pydantic Model、测试和本文档。

## 数据库与缓存

- PostgreSQL/开发 SQLite 持久化 User、Ticket、Approval、AgentRun、AgentRunLink 和 FeedbackEvent。
- Redis 保存短期会话和最近消息；不可用时回退数据库。
- ChromaDB 保存 Embedding 与文档 metadata，支持 `kb_version` 和 category filter。
- 当前新表依赖 SQLAlchemy `create_all`；生产上线前必须增加 Alembic migration。

## OpenTelemetry 与 LangSmith

应用仅用 OpenTelemetry SDK 采集 Trace 和 Metrics，通过 OTLP 发送 Collector。Collector 将 Agent 主链 Trace 发往 LangSmith，将 Metrics 以 Prometheus 格式暴露在 `:8889`。项目不使用 LangSmith `traceable` 双轨采集。

最小 Collector 启动：

```bash
docker compose -f deployment/docker-compose.yml up -d otel-collector
```

重启：

```bash
docker compose -f deployment/docker-compose.yml restart otel-collector
```

关键配置：

```dotenv
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4318/v1/traces
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://localhost:4318/v1/metrics
OTEL_COLLECTOR_LANGSMITH_API_KEY=<api-key>
OTEL_COLLECTOR_LANGSMITH_PROJECT=supportgpt-enterprise
```

本地 Collector 不可达时 Backend 在 preflight 阶段跳过 exporter，避免重试刷屏。Collector 启动后需重启 Backend 恢复上报。遥测始终 fail-open，不影响业务主链。

## 测试

安装并运行完整测试：

```bash
python -m pip install -r requirements/test.txt
python -m compileall src tests
python -m pytest -q
```

定向烟测：

```bash
python -m pytest tests/test_agents.py tests/test_rag.py -q
```

测试使用内存 SQLite，不污染本地开发数据。覆盖率 90%+ 是生产化目标，不得表述为当前已强制达成。

Locust 压测：

```bash
python -m pip install -r requirements/load.txt
locust -f tests/load_test.py
```

## 评测命令

管道烟测：

```bash
python scripts/run_agent_eval.py --rag-engine local --agent-engine local
```

Ragas + DeepEval 正式评测：

```bash
python -m pip install -r requirements/eval.txt
python scripts/seed_kb.py
python scripts/run_agent_eval.py --rag-engine ragas --agent-engine deepeval
```

真实 LLM 回归：

```bash
python scripts/run_real_llm_regression.py --suite smoke --dry-run
python scripts/run_real_llm_regression.py --suite smoke --confirm-live
```

Baseline 100 Workflow Replay：

```bash
python scripts/run_baseline_eval.py --dry-run
python scripts/run_baseline_eval.py --confirm-live
```

正式 Baseline 每次产生一组不可变时间戳 JSON/Markdown 快照，`baseline_v1_latest.json/md` 是指向最新快照的相对软链接。报告目录不进 Git；实验配置、Dataset SHA256、模型、Prompt/Workflow 版本、Token 与 Trace ID 必须写入报告。

## Feedback Pipeline

`/chat`、`/suggest-response` 和工单 Workflow 将结果持久化为 AgentRun；用户评价、人工修正和 Evaluation 以 FeedbackEvent 关联同一 `agent_run_id` 与 `trace_id`。

导出脱敏后的训练候选：

```bash
python scripts/export_training_candidates.py
```

导入统一评测结果：

```bash
python scripts/import_evaluation_feedback.py \
  --report evaluation/reports/evaluation_latest.json
```

当前只生成 SFT/DPO 候选，不执行训练、自动发布或未经人工治理的数据回流。

## Docker 与部署

启动全部本地组件：

```bash
docker compose -f deployment/docker-compose.yml up --build
```

主要端口：Backend `8000`、PostgreSQL `5432`、Redis `6379`、OTLP gRPC `4317`、OTLP HTTP `4318`、Collector Metrics `8889`、Prometheus `9090`、Grafana `3000`。Kubernetes 模板位于 `deployment/k8s/`，它仅是部署样例，不代表已在生产环境运行。

## 开发约定

- Python 遵循 PEP 8，新函数可增加一两行精简中文注释。
- Pydantic Schema 应提供合理默认值和字段描述。
- 数据库使用 `AsyncSession`，明确事务边界。
- 新 Tool 必须注册到 ToolRegistry，配置 Schema、permission、risk level 和审计字段。
- 改动 Agent 节点时同步 State、Trace、Metrics、确定性测试和 Baseline 评测。
- 不得提交 `.env`、API Key、业务评测报告或训练候选数据。
