# GPT-5.6 Handoff Document

> 目标读者：下一次接手本仓库的 GPT-5.6 / Codex 会话。  
> 仓库路径：`/Users/fayefufu/Downloads/居丽叶简历项目6：差旅出行助手/support-gpt-enterprise-review`  
> GitHub 仓库：`https://github.com/sulik0/support-gpt-enterprise-resume`

## 1. Project Overview

这是一个基于开源项目 `adhanushus19/Support-GPT-Enterprise` 改造而来的智能客服 Agent 项目，目标是包装成“企业售后客服 Agent / 工单自动化 / Agentic RAG”方向的简历项目。

核心场景：

- 售后客服工单理解。
- 客户画像、订单状态、历史工单上下文补全。
- 退款、保修、物流异常、订单取消等复杂问题处理。
- RAG 知识库问答。
- AI 回复生成、质量校验、风险拦截和人工审批。
- 工单状态闭环。
- 可观测性、依赖分层和本地 Docker 编排。

当前定位：

- 代码层面是一个可本地运行的生产风格项目。
- CRM / 订单 / 工单 / 退款等业务系统使用本地 mock adapter。
- 不要在代码或文档中声称已经真实接入企业 CRM / OMS / 工单系统，除非用户后续明确提供真实接入凭据或实现。
- 用户希望这个项目用于简历和面试表达。回复时可以强化“生产风格、业务闭环、可观测、可替换真实服务”的叙事，但不要编造无法由代码支撑的生产事实。

## 2. Current Architecture

### Backend

- `FastAPI` 提供后端 API。
- `SQLAlchemy async` 负责数据库模型和查询。
- 默认数据库为 SQLite：`sqlite+aiosqlite:///./supportgpt.db`。
- Docker Compose 配置中使用 PostgreSQL、Redis、Prometheus。

### Agent Workflow

核心工作流在 `src/agents/graph.py`：

```text
analyzer
  ├── security threat -> escalation -> END
  └── normal request  -> tooling -> retriever -> resolver -> qa -> escalation -> END
```

节点职责：

- `analyzer`：PII 脱敏、prompt injection / jailbreak 检测、情绪/优先级/部门/意图分类。
- `tooling`：通过 `ToolRegistry` 调 CRM、订单、历史工单工具，补充结构化上下文。
- `retriever`：调用 ChromaDB Hybrid RAG 检索知识库 citation。
- `resolver`：结合 RAG + 工具上下文生成客服回复。
- `qa`：QA 评分、幻觉检测、输出泄露过滤。
- `escalation`：SLA 和人工升级判断。

### Tool Calling

工具注册中心在 `src/tools/registry.py`：

- 工具定义包含 `name`、`description`、`input_schema`、`output_schema`、`min_role`、`timeout_seconds`、`mocked`、`handler`。
- 读类工具允许 `agent` 调用。
- `orders.check_refund_eligibility` 是 manager 级 mock 工具，用于展示高风险工具权限控制。
- 每次调用返回 `tool_calls` 审计记录，包含工具名、角色、工单 ID、是否允许、状态、耗时、mock 标记和错误。

### RAG

RAG 主要在 `src/rag/vector_store.py`：

- ChromaDB 作为向量库。
- 支持知识库版本 `version`。
- 支持类别过滤 `category_filter`。
- 已从纯向量检索升级为 hybrid retrieval：
  - ChromaDB 向量召回。
  - 进程内 BM25 风格关键词打分。
  - 轻量 rerank。
  - citation 返回。

### Memory

记忆层在 `src/memory/redis_memory.py`：

- Redis 是可选短期会话记忆。
- SQL `SessionMemory` 是持久化历史。
- Redis 不可用时自动降级到 SQL。

### Ticket Lifecycle

工单状态机在 `src/tickets/state_machine.py`：

```text
open -> pending_approval -> resolved -> closed
pending_approval -> in_progress  # 人工拒绝 AI 草稿
resolved -> in_progress          # 重新打开
closed -> in_progress            # 重新打开
```

非法流转返回 `409 Conflict`。

### Observability

- Prometheus 指标在 `src/observability/metrics.py`。
- OpenTelemetry 初始化和 helper 在 `src/observability/tracing.py`。
- 已增加 spans：
  - `api.{method} {path}`
  - `agent.workflow`
  - `agent.analyzer`
  - `agent.tooling`
  - `agent.retriever`
  - `agent.resolver`
  - `agent.qa`
  - `agent.escalation`
  - `tool.*`
  - `rag.query`
  - `rag.query_fallback`
  - `approval.create_pending`
  - `approval.process`

## 3. Directory Structure

重要目录：

```text
.
├── src/
│   ├── agents/              # LangGraph 节点：analyzer/tooling/retriever/resolver/qa/escalation
│   ├── approval/            # Human-in-the-loop 审批流程
│   ├── auth/                # JWT、RBAC
│   ├── evaluation/          # RAGAS/DeepEval/本地评估适配
│   ├── guardrails/          # PII、prompt injection、jailbreak、response filter
│   ├── llm/                 # mock/openai/azure LLM provider
│   ├── memory/              # Redis conversation memory
│   ├── models/              # SQLAlchemy models + Pydantic schemas
│   ├── observability/       # Prometheus、token/cost、OpenTelemetry trace
│   ├── rag/                 # chunking/embedding/vector_store/kb_versioning
│   ├── tickets/             # 工单状态机
│   └── tools/               # mock CRM/order/ticketing + ToolRegistry
├── tests/                   # pytest 测试文件
├── docs/                    # 中文项目文档、简历文档、变更日志
├── requirements/            # base/test/eval/load 分层依赖
├── deployment/              # Dockerfile、docker-compose、k8s
├── monitoring/              # Prometheus 和 Grafana 配置
├── scripts/                 # seed_kb、run_eval
└── frontend/                # 原始 React dashboard，当前不是重点
```

重要文档：

- `docs/RESUME_PROJECT_GUIDE.md`
- `docs/RESUME_UPGRADE_PLAN.md`
- `docs/RESUME_VALUE_ENHANCEMENT_ROADMAP.md`
- `docs/MOCK_BOUNDARIES.md`
- `docs/CHANGELOG_RESUME_UPGRADE.md`
- `docs/AGENT_ARCHITECTURE.md`
- `docs/RAG_ARCHITECTURE.md`
- `docs/PHASE_9_MONITORING.md`

## 4. What Has Been Implemented

已完成并推送的关键提交：

- `57d948d feat: add optional Redis conversation memory`
- `923b073 feat: add security short-circuit routing`
- `51c6523 feat: expose tool context in API responses`
- `20565c5 docs: document mock boundaries for resume claims`
- `de876b9 feat: add hybrid retrieval reranking`
- `c977f56 chore: stabilize python dependency profiles`
- `8940872 docs: translate project docs to chinese`
- `077dd6d docs: add resume enhancement roadmap`
- `bf16204 feat: add tool registry permissions and audit`
- `37b91c5 feat: add ticket lifecycle state machine`
- `3e18b2b feat: add opentelemetry trace spans`

功能层面已实现：

- FastAPI API。
- LangGraph 多 Agent 工作流。
- 条件路由和安全短路。
- ToolRegistry 工具调用协议、schema、权限、超时、审计。
- CRM / order / ticketing mock adapter。
- manager 级退款初筛 mock 工具。
- Hybrid RAG：向量召回 + BM25 风格关键词打分 + rerank。
- citation 返回。
- Redis 短期记忆 + SQL 持久化会话历史。
- Human-in-the-loop 审批。
- 工单状态机。
- Prometheus metrics。
- OpenTelemetry trace spans。
- Python 3.11 依赖分层和 GitHub Actions smoke CI。
- 中文文档体系。

## 5. Pending TODOs

建议后续按优先级推进：

1. **RAG 评估集与离线评测报告**
   - 构造 30-50 条 synthetic customer support golden set。
   - 输出 citation hit rate、faithfulness、answer relevance、hallucination rate。
   - 生成 Markdown + JSON 报告。

2. **多租户知识库隔离**
   - 文档和 metadata 加 `tenant_id`。
   - RAG 查询强制 `tenant_id + kb_version` filter。
   - 测试不同租户不能互相检索文档。

3. **生产级检索后端抽象**
   - 抽象 `SearchBackend`。
   - 保留 `ChromaHybridBackend`。
   - 设计或 mock `OpenSearchHybridBackend`。

4. **状态流转审计表**
   - 当前状态机复用 `Ticket.status`。
   - 后续可加 `ticket_status_events`，记录操作者、动作、来源状态、目标状态、原因、时间。

5. **客服工作台前端**
   - 展示工单列表、AI 草稿、tool context、tool calls、RAG citation、QA 分数、审批按钮。

6. **Prompt 版本管理和灰度**
   - analyzer/resolver/QA prompt 版本化。
   - 记录版本指标、审批率、QA 分数和延迟。

## 6. Important Design Decisions

- **文档语言**：`docs/` 下文档统一使用中文。代码标识符、命令、API 路径和通用技术名词可保留英文。
- **Mock 边界**：CRM、订单、历史工单、退款初筛、默认 LLM 都是本地 mock。不要把它们写成真实企业系统接入。
- **工具调用治理**：所有工具必须走 `ToolRegistry`，不要在 Agent 中直接调用 `crm_tool` / `order_mgmt_tool` / `ticketing_tool`。
- **状态流转治理**：不要直接写 `ticket.status = ...`。应通过 `ticket_state_machine.transition(ticket, TicketAction.X)`。
- **Redis 可选**：Redis 不应成为本地 demo 的硬依赖。
- **LLM 默认 mock**：默认 `LLM_PROVIDER=mock`，保证本地可复现。
- **Python 版本**：项目推荐 Python 3.11。当前本机 `.venv` 是 Python 3.13，pytest 有 native dependency crash 风险。
- **Trace 生产边界**：当前 OpenTelemetry 使用 Console Exporter，生产应接 OTLP exporter / Jaeger / Tempo。
- **简历叙事**：强调生产风格架构、业务闭环、可观测性、可替换真实业务系统。不要伪造真实上线或真实客户数据。

## 7. APIs and Interfaces

主要 FastAPI endpoints：

```text
POST /auth/register
POST /auth/token
GET  /auth/users/me
GET  /health
POST /chat
POST /summarize-ticket
POST /suggest-response
POST /analyze-sentiment
POST /recommend-escalation
POST /customer-context
POST /evaluate-response
GET  /approvals/pending
POST /approvals/{approval_id}
POST /tickets
POST /tickets/{ticket_id}/close
GET  /tickets
GET  /metrics
```

关键接口：

- `run_agent_workflow(initial_state: Dict[str, Any]) -> Dict[str, Any]`
- `tool_registry.call_tool(name, payload, role="agent", ticket_id=None)`
- `vector_store.query_kb(query, version="v1", top_k=3, category_filter=None)`
- `redis_memory.load_messages(session_id)`
- `redis_memory.save_messages(session_id, messages)`
- `human_it_loop_service.create_pending_approval(db, ticket_id, drafted_response)`
- `human_it_loop_service.process_agent_approval(db, approval_id, agent_id, req)`
- `ticket_state_machine.transition(ticket, action)`

重要 response 字段：

- `tool_context`：结构化客户/订单/历史工单上下文。
- `tool_calls`：工具调用审计，包含工具名、角色、是否允许、状态、耗时、mock 标记。
- `citations`：RAG citation。
- `approval_required` / `approval_id`：人工审批信息。
- `cost_metadata`：token、cost、latency。

## 8. Coding Conventions

- 使用 Python async 风格，API 层依赖 `AsyncSession`。
- 手工编辑文件必须用 `apply_patch`。
- 搜索优先用 `rg`，文件列表优先用 `rg --files`。
- 中文文档放在 `docs/`。
- 新增能力必须同步更新：
  - `docs/CHANGELOG_RESUME_UPGRADE.md`
  - 相关架构文档
  - 简历相关文档
- 每次改动后提交并推送到 `my-origin main`，保持用户要求的“每次改动后提交 GitHub”。
- 不要大规模重构无关模块。
- 不要删除用户已有文件或未理解的生成文件。
- 不要直接修改 `.venv`、`chromadb_store`、`evaluation/reports`，除非用户明确要求。

## 9. Known Bugs

- 当前本机 `.venv` 是 Python 3.13，运行 pytest 经常 `exit code 139`，这是已知 native dependency/plugin crash。
- `python -m compileall src tests` 正常通过。
- 直接用 `.venv/bin/python -c ...` 调核心 workflow 正常通过。
- 建议使用 Python 3.11 新建环境并安装 `requirements/test.txt` 跑 CI smoke tests。
- Full pytest 在当前本地环境不可靠，不要误判为业务代码断言失败。
- Docker / CI 使用 Python 3.11，是更推荐的验证路径。

## 10. Things That Must NOT Be Changed

- 不要把 mock CRM / OMS / ticketing 写成真实企业 API 接入。
- 不要删除 mock boundary 文档。
- 不要把 Redis 改成强依赖，本地 demo 必须能无 Redis 运行。
- 不要绕过 `ToolRegistry` 直接在 Agent 中调用业务工具。
- 不要绕过 `TicketStateMachine` 直接修改 `Ticket.status`。
- 不要移除安全短路路由。
- 不要移除 `tool_context`、`tool_calls`、`citations` 等 demo/面试可见字段。
- 不要把文档改回大段英文。当前约定是中文文档。
- 不要执行 `git reset --hard`、`git checkout --` 等破坏性命令。
- 不要强行修复或删除与当前任务无关的上游历史文件。

## 11. Current Branch / Modified Files

当前状态：

- Branch：`main`
- Tracking：`my-origin/main`
- Remote：
  - `my-origin -> git@github.com:sulik0/support-gpt-enterprise-resume.git`
  - `origin -> git@github.com:adhanushus19/Support-GPT-Enterprise.git`
- 最新提交：`3e18b2b feat: add opentelemetry trace spans`
- 当前工作区在创建本文件前是干净的。

本 handoff 文档创建后会出现：

```text
?? docs/HANDOFF_GPT56.md
```

建议创建并推送提交：

```bash
git add docs/HANDOFF_GPT56.md
git commit -m "docs: add gpt56 handoff"
git push my-origin main
```

## 12. Next Recommended Task

推荐下一步做：**RAG 评估集与离线评测报告**。

原因：

- 它是当前简历路线图中最直接的可量化加分项。
- 不需要真实企业 API。
- 可以用 synthetic support QA dataset 完成。
- 能让项目从“实现了 RAG”升级为“有质量评估和回归报告的 RAG 系统”。

建议实现范围：

1. 新增 `evaluation/golden/support_qa_golden.json`。
2. 包含 30-50 条合成售后问题，覆盖：
   - 退款规则
   - 保修流程
   - 物流异常
   - 订单取消
   - 账户问题
   - 技术支持
3. 每条包含：
   - `query`
   - `expected_answer_points`
   - `expected_sources`
   - `risk_level`
   - `category`
4. 新增 `scripts/run_golden_eval.py`。
5. 生成：
   - `evaluation/reports/golden_eval_latest.json`
   - `evaluation/reports/golden_eval_latest.md`
6. 指标：
   - citation hit rate
   - context recall
   - answer relevance
   - faithfulness proxy
   - hallucination risk flag
7. 更新中文文档和变更日志。
8. 提交并推送。

建议简历表述：

> 构建客服 RAG 离线评测集，覆盖退款、保修、物流异常和账户问题，设计 citation hit rate、context recall、answer relevance 等指标，支持知识库问答质量回归评估。
