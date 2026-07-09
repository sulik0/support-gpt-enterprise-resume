# Mock 边界与简历表述

本项目定位为可写进简历的企业智能客服 Agent 应用。部分企业系统集成使用本地 mock 适配器实现，这样项目可以在没有真实企业私有服务的情况下运行。

## 可以安全写进简历的内容

以下能力都有代码支撑：

- 基于 FastAPI 的聊天、工单、鉴权、审批、评估和客户上下文 API。
- 基于 LangGraph 的 Agent 工作流，包含 analyzer、tooling、retriever、resolver、QA 和 escalation 节点。
- 对安全风险请求的条件路由和提前阻断。
- 通过 CRM、订单、历史工单适配器注入结构化工具上下文。
- 基于 ChromaDB、Embedding、metadata filter、知识库版本、轻量混合检索和 rerank 的 RAG 检索。
- SQLAlchemy 数据模型，覆盖用户、工单、会话记忆、知识文档和审批记录。
- 可选 Redis 短期会话记忆，SQL 作为持久化兜底。
- 高风险或低置信度回复的 Human-in-the-Loop 审批流程。
- Prompt injection、jailbreak、PII 脱敏和输出过滤等 guardrails。
- Prometheus 指标，覆盖请求、Agent、QA、升级、token 和成本估算。
- Docker Compose 本地栈，包含 backend、PostgreSQL、Redis 和 Prometheus。

## Mock 集成清单

| 模块 | 当前实现 | Mock 原因 | 生产替换方案 |
|---|---|---|---|
| CRM | `src/tools/crm.py` 中的内存客户画像 | 没有真实 CRM 权限 | Salesforce / Zendesk / HubSpot API client |
| 订单管理 | `src/tools/order_mgmt.py` 中的内存订单历史 | 没有真实 OMS 账号 | 电商/OMS REST 或 GraphQL adapter |
| 历史工单 | `src/tools/ticketing.py` 中的内存历史工单 | 没有真实 helpdesk backend | Jira / ServiceNow / Zendesk ticket API |
| LLM | 默认 `mock` provider | 本地 demo 可复现 | OpenAI / Azure / OpenRouter / Qwen / DeepSeek provider |
| 评估 | 本地确定性指标，可选 RAGAS / DeepEval | 没有稳定生产评估集 | Golden set + LLM-as-Judge pipeline |
| 关键词检索 | 进程内 BM25 风格 scorer | 不是分布式搜索索引 | Elasticsearch / OpenSearch / PostgreSQL full-text search |

## 推荐面试表述

可以说：

> 我实现了 Agent 工作流、RAG 链路、记忆层、人工审批和可观测性。CRM、订单和工单系统使用 mock adapter，本地可以直接运行；这些 adapter 被隔离在工具类后面，生产环境可以替换成真实企业 API client。

避免说：

> 这个系统已经接入真实企业 CRM 和订单系统。

可以说：

> 本地 demo 默认使用 mock LLM provider 保证可复现，provider 接口也预留了 OpenAI 和 Azure 适配。

避免说：

> 系统已经在真实生产客服中心压测并上线。

## 从 Mock 升级到生产的清单

- 将 mock tools 替换为真实 API client。
- 为工具调用增加 schema、权限、超时、重试和 circuit breaker。
- 为所有工具调用增加审计日志。
- 增加租户级知识库隔离。
- 将进程内关键词打分替换为生产搜索后端。
- 在生成前增加 cross-encoder 或 LLM reranker。
- 使用 lock file 固定 Python 和依赖版本。
- 将可选评估依赖拆分为 install extra。
- 在现有 Python 3.11 smoke workflow 后补充更完整的 CI matrix。
- 建立真实业务 golden evaluation dataset。

## 简历 Bullet 边界

### 强推荐写法

> 基于 LangGraph 设计工具增强型客服 Agent 工作流，在 RAG 回复生成前注入 CRM、订单和历史工单上下文。

安全原因：

- 工作流中确实有 tooling node。
- 工具确实返回结构化数据。
- mock 边界已经明确。

### 强推荐写法

> 实现 Redis 短期会话记忆与 SQL 持久化会话历史，支持 Redis 不可用时自动降级。

安全原因：

- Redis adapter 已实现。
- SQL `SessionMemory` 已存在。
- Redis 是可选能力，可以优雅降级。

### 需要谨慎的写法

不建议：

> 集成 CRM 和订单系统。

更准确：

> 在工具接口后实现 mock CRM 和订单 adapter，模拟企业系统集成并展示 Agent tool-calling 路径。

### 需要谨慎的写法

不建议：

> 实现生产级 RAG 评估。

更准确：

> 增加 RAG 评估模块，并设计 faithfulness、context recall、hallucination rate 等目标指标。
