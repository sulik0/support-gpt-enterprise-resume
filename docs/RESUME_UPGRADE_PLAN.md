# 简历项目改造计划

## 目标

将该仓库改造成适合写进简历的企业级智能客服 Agent 项目。

目标不是宣称它已经是完整生产级 SaaS，而是让项目在面试中具备可信度，并清晰区分：

- 已经实现的工程能力。
- 简历项目中可接受的 mock 业务集成。
- 仍需生产化补齐的部分。

## 当前代码审计摘要

### 已实现且适合写进简历

- FastAPI 后端，包含聊天、工单、审批、鉴权、评估和客户上下文 API。
- SQLAlchemy 模型，覆盖用户、工单、会话记忆、知识文档和审批记录。
- LangGraph 工作流，包含 analyzer、tooling、retriever、resolver、QA 和 escalation 节点。
- ChromaDB 向量库，支持 metadata filter、知识库版本和混合检索。
- 基于数据库记录的 Human-in-the-Loop 审批流程。
- Prompt injection、jailbreak、PII 脱敏和输出过滤 guardrails。
- Prometheus 指标和基础 OpenTelemetry 配置。
- Docker Compose 本地栈，包含 backend、PostgreSQL、Redis 和 Prometheus。
- 定向测试和压测脚本骨架。

### Mock 但简历项目可接受

- CRM 查询、订单查询和历史工单查询使用内存 mock 数据。
- LLM provider 默认使用 mock 实现，方便本地 demo。
- RAG 评估在无 API key 时使用本地确定性指标。
- 客户、订单、退款等业务数据为合成数据，面试中需要明确说明。

### 仍非完整生产级

- 外部 CRM、OMS、物流、退款和工单系统尚未接入真实服务。
- 关键词检索是进程内轻量 BM25 风格实现，不是生产搜索集群。
- 依赖已经分层，但还没有生成 lock file。
- 当前 CI 是 Python 3.11 smoke workflow，还不是完整多版本矩阵。
- 评估集不是来自真实业务标注数据。

## 改造阶段

### 阶段 1：简历边界文档

目标：明确哪些能力可写、哪些属于 mock，避免面试中过度包装。

交付物：

- `docs/RESUME_UPGRADE_PLAN.md`
- `docs/MOCK_BOUNDARIES.md`
- README 中的简历项目说明入口。

简历价值：

- 面试时可以主动说明项目边界，体现工程判断。

### 阶段 2：Agent 工作流升级

目标：将工具上下文显式接入 LangGraph 工作流。

已完成改造：

- 在 Agent state 中增加 `tool_context`。
- 增加 `tooling` 节点。
- 在 analyzer 和 retriever 之间调用 CRM、订单和历史工单工具。
- 将工具上下文注入 resolver prompt。

简历价值：

- 可以真实描述为“工具增强型 Agent 工作流”。
- 可以说明工具是 mock adapter，生产中可替换成 CRM / OMS / ticketing API。

### 阶段 3：Redis 记忆层

目标：增加 Redis 短期会话记忆，并保留 SQL 持久化兜底。

已完成改造：

- 增加 `src/memory/redis_memory.py`。
- 按 `session_id` 保存最近对话 turn。
- SQL `SessionMemory` 继续作为持久化历史。
- Redis 不可用时系统自动降级。

简历价值：

- 可以真实描述为“Redis 短期记忆 + SQL 持久化会话历史”。

### 阶段 4：条件路由和安全短路

目标：让安全风险请求直接进入升级节点，避免调用后续工具和 RAG。

已完成改造：

- 增加 analyzer 后的条件路由。
- prompt injection / jailbreak 命中时跳过 tooling、retriever、resolver 和 QA。
- 安全风险请求直接标记为需要人工审批。

简历价值：

- 可以描述为“基于 guardrails 的 Agent 条件路由和安全短路”。

### 阶段 5：混合检索和轻量 Rerank

目标：提升 RAG 对客服政策中精确词的召回能力。

已完成改造：

- `query_kb` 从纯向量检索升级为混合检索。
- 增加 BM25 风格关键词 scorer。
- 增加向量分、关键词分和精确词重合的轻量 rerank。

简历价值：

- 可以描述为“向量检索 + BM25 风格关键词检索 + 轻量 rerank 的混合 RAG 检索层”。

### 阶段 6：依赖分层和 CI

目标：提升项目可复现性。

已完成改造：

- 固定推荐 Python 版本为 3.11。
- 拆分 runtime、test、eval、load 依赖。
- 增加 GitHub Actions smoke workflow。
- Dockerfile 和 CI 统一到 Python 3.11。

简历价值：

- 可以描述为“通过依赖分层和 CI 提升项目可复现性和工程质量”。

### 阶段 7：中文文档统一

目标：将 `docs/` 下项目文档统一为中文，便于简历准备和面试复盘。

交付物：

- 所有 `docs/*.md` 改为中文说明。
- 后续文档统一使用中文，代码、命令和技术名词可保留英文。

## 验证方式

每次改造后优先运行：

```bash
python -m compileall src tests
```

必要时补充：

```bash
.venv/bin/python -c 'import src.main; print("main import ok")'
```

```bash
.venv/bin/python -c 'from src.agents.graph import run_agent_workflow; import asyncio; out=asyncio.run(run_agent_workflow({"ticket_id":1,"customer_id":"cust_101","subject":"refund","description":"I want refund for charge","kb_version":"v1"})); print(out["department"], bool(out.get("tool_context")), out["approval_required"])'
```

## GitHub 状态

- 上游仓库 remote：`origin`
- 个人仓库 remote：`my-origin`
- 个人 GitHub 仓库：`https://github.com/sulik0/support-gpt-enterprise-resume`
- 改造提交已持续推送到 `my-origin/main`。
