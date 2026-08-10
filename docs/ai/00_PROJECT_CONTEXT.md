# SupportGPT Enterprise 项目上下文

> 本文档是本项目唯一的项目概览，也是 Codex、GPT、Claude Code、Cursor 等 AI 参与开发前的必读入口。
> 当本文档与代码不一致时，以当前代码和测试为准，并在同一次改动中更新本文档。

## 项目背景

SupportGPT Enterprise 是一个面向企业售后客服场景的 AI Agent 项目。项目基于开源客服问答系统改造，目标是将传统 FAQ / RAG 问答升级为具有工单理解、业务上下文补全、风险拦截、回复校验、人工审批和工单状态闭环的 Agent 平台。

核心业务场景包括退款、保修、物流异常、订单取消、账户问题和技术支持。目标用户是客服坐席、客服组长和运营管理人员。

本项目的定位是“可本地运行的生产风格简历项目”，而不是已经接入真实客户数据并上线生产的客服系统。CRM、OMS、历史工单和退款初筛均使用本地 Mock Adapter；它们用于验证 Tool Calling 协议、权限和审计设计，不代表已接入真实企业系统。

## 项目目标

### 业务目标

- 将客户的自然语言问题转换为可路由、可审批、可追踪的工单处理流程。
- 在生成回复前同时引入知识库依据和结构化业务上下文。
- 对安全违规、紧急工单、负面高优先级工单和低质量回复引入 Human-in-the-Loop。
- 通过 citation、QA 结果、工具审计和 Trace 为客服坐席提供可核查依据。

### 工程目标

- 使用 LangGraph 将 Agent 流程拆分为职责清晰、可独立观测的节点。
- 通过 ToolRegistry 统一工具协议，实现 Schema 校验、RBAC、超时和调用审计。
- 使用 Hybrid RAG 兼顾语义检索与政策编号、产品名、时间窗口等精确词匹配。
- 保持默认 Mock LLM、可选 Redis 和 SQLite 本地配置，使项目在无企业凭据、无外部 LLM 和无 Redis 时仍可复现。
- 通过 Prometheus、OpenTelemetry、分层依赖和 Python 3.11 CI 提供基础可观测性与可维护性。

## 核心能力

1. **工单分析**：识别 `sentiment`、`priority`、`department` 和 `intent`。
2. **安全短路**：在调用工具和 LLM 生成回复前检测 Prompt Injection 与 Jailbreak，命中后直接进入 Escalation。
3. **PII 脱敏**：正常请求进入 LLM 前对主题和描述中的敏感信息进行匿名化。
4. **业务工具上下文**：通过 ToolRegistry 查询客户画像、近期订单和历史工单，并把结构化结果注入 Resolver。
5. **工具治理**：工具具有 `input_schema`、`output_schema`、`min_role`、`timeout_seconds` 和 `mocked` 元数据；每次调用返回状态、耗时、权限结果和错误。
6. **Hybrid RAG**：融合 ChromaDB 向量召回、进程内 BM25 风格词法打分和轻量 rerank，返回带版本的 citation。
7. **回复生成与 QA**：使用知识库 citation 和 Tool Context 生成草稿，再评估 QA 分数、幻觉风险和输出泄露。
8. **Human-in-the-Loop**：对需要人工处理的草稿创建审批记录，支持通过、修改和拒绝。
9. **工单状态机**：统一约束 `open`、`in_progress`、`pending_approval`、`resolved` 和 `closed` 的合法流转。
10. **分层记忆**：SQL `SessionMemory` 保存持久化对话历史，Redis 作为可选短期快速存储，不可用时回退到 SQL。
11. **可观测性**：使用 OpenTelemetry 统一采集 Trace 与 Metrics；Collector 将 Trace 转发 LangSmith，并通过 Prometheus exporter 提供指标，由 Grafana 展示。
12. **离线评测适配**：提供 RAGAS、DeepEval 和本地确定性指标的统一评测入口。

## 技术栈

| 层级 | 技术 | 当前用途 |
|---|---|---|
| API | Python、FastAPI、Pydantic | 异步 API、请求/响应 Schema与健康检查 |
| Agent 编排 | LangGraph | 编排 Analyzer、Tooling、Retriever、Resolver、QA 和 Escalation |
| LLM | Mock LLM、OpenAI、Azure OpenAI | 默认 Mock 保证离线可复现；通过 `BaseLLMProvider` 适配外部模型 |
| 数据库 | SQLAlchemy Async、SQLite、PostgreSQL | 本地默认 SQLite；Docker Compose 使用 PostgreSQL |
| 短期记忆 | Redis | 可选的会话历史快速存储，失败时不影响 SQL 持久化 |
| RAG | ChromaDB、Embedding、Hybrid RAG | 知识库分块、版本/类别过滤、向量与词法混合召回、rerank |
| 安全 | JWT、RBAC、Prompt Guardrails | API 鉴权、工具权限、PII 脱敏、Prompt Injection / Jailbreak 检测和输出过滤 |
| 评测 | RAGAS、DeepEval、本地启发式指标 | Faithfulness、Context Precision / Recall、Answer Relevance 和 Hallucination Rate |
| 可观测 | LangSmith、OpenTelemetry、Prometheus、Grafana | OTel 统一采集 Trace 与 Metrics；Collector 转发 Trace 并导出 Prometheus 指标 |
| 交付 | Docker、Docker Compose、Kubernetes manifests | 本地组件编排和部署模板 |
| 质量保障 | pytest、GitHub Actions | Python 3.11 编译检查与定向后端测试 |

## 系统整体架构

```text
客服端 / API Client
        |
        v
FastAPI
  |-- JWT / RBAC
  |-- Chat / Ticket / Approval / Evaluation API
  |-- OpenTelemetry Trace + Metrics
  |
  +--> LangGraph Agent Workflow
  |      |-- Analyzer + Guardrails
  |      |-- Tooling --> ToolRegistry --> Mock CRM / OMS / Ticketing
  |      |-- Retriever --> ChromaDB Hybrid RAG
  |      |-- Resolver --> BaseLLMProvider --> Mock / OpenAI / Azure OpenAI
  |      |-- QA --> LLM QA + Response Filter
  |      `-- Escalation --> Human-in-the-Loop
  |
  +--> SQLAlchemy Async --> SQLite / PostgreSQL
  |      |-- User
  |      |-- Ticket
  |      |-- SessionMemory
  |      |-- KnowledgeDoc
  |      `-- ResponseApproval
  |
  `--> Redis（可选短期记忆）

Observability
  |-- OpenTelemetry Collector
  |     |-- Trace --> LangSmith
  |     `-- Metrics --> Prometheus exporter
  `-- Prometheus --> Grafana
```

本地默认使用 SQLite、Mock LLM 和本地持久化 ChromaDB，Redis 不是强依赖。Docker Compose 编排 backend、PostgreSQL、Redis、OpenTelemetry Collector、Prometheus 和 Grafana。应用通过 OTLP/HTTP 将 Trace 与 Metrics 发送到 Collector；后端不直接暴露 Prometheus `/metrics`。

## Agent 工作流

### AgentState

LangGraph 使用 `AgentState` 作为节点间共享状态。关键字段分为：

- 请求标识：`ticket_id`、`customer_id`、`subject`、`description`、`kb_version`。
- 分析结果：`sentiment`、`priority`、`intent`、`department`。
- 权限与工具：`operator_role`、`tool_context`、`tool_calls`。
- RAG 与回复：`context_citations`、`suggested_response`。
- 质量与风险：`qa_score`、`hallucination_detected`、`errors`。
- 闭环决策：`escalation_recommended`、`escalation_reason`、`approval_required`。
- 成本与延迟：`tokens_input`、`tokens_output`、`cost_usd`、`latency_seconds`。

当前项目使用 `AgentState`，没有另外定义 `TaskState`、Checkpoint 或持久化 LangGraph State。不要在未实现前将这些能力写成现状。

### 路由

```text
analyzer
  |-- 命中 Prompt Injection / Jailbreak
  |      `--> escalation --> END
  |
  `-- 正常请求
         `--> tooling --> retriever --> resolver --> qa --> escalation --> END
```

### 节点职责

1. **Analyzer**
   - 先检测 Prompt Injection 和 Jailbreak。
   - 命中安全风险时写入 `errors`，设置紧急优先级和拒绝回复，不执行后续 Tooling、RAG、Resolver 和 QA。
   - 正常请求先对 PII 脱敏，再调用 LLM 分析情绪、优先级、部门和意图。
2. **Tooling**
   - 始终查询客户画像和历史工单。
   - 只在 billing、shipping 或相关意图下查询订单历史。
   - 所有调用必须经过 ToolRegistry，Agent 不能直接调用 Mock Adapter。
3. **Retriever**
   - 用工单主题和描述构造 Query，默认返回 Top 3 citation。
   - 强制带 `kb_version`，并优先按 `department` 过滤类别。
   - 类别过滤无结果时，保留版本过滤并放宽类别再检索一次。
4. **Resolver**
   - 将 citation 格式化为 Knowledge Base Context。
   - 将 `tool_context` 序列化为 Structured Tool Context。
   - 将两类上下文合并后交给 LLM Provider 生成草稿。
5. **QA**
   - 根据原始问题、citation 和回复评估 `qa_score` 与幻觉风险。
   - 通过 Response Filter 删除内部指令或工作流泄露；命中时将 QA 分数降为 `0.5` 并标记幻觉。
6. **Escalation**
   - 按优先级计算 SLA：urgent `2h`、high `12h`、medium `24h`、low `48h`。
   - 以下任一条件命中时建议升级：安全违规、urgent、negative + high、`qa_score < 0.8`、检测到幻觉。
   - 工作流结束后，只要建议升级或 `qa_score < 0.8`，就设置 `approval_required = true`。

### 工单状态闭环

```text
open --start_work--> in_progress
open / in_progress --request_approval--> pending_approval
pending_approval --approve_response / modify_response--> resolved
pending_approval --reject_response--> in_progress
resolved --close--> closed
resolved / closed --reopen--> in_progress
```

状态流转必须通过 `TicketStateMachine.transition()`。非法流转返回 `409 Conflict`，不允许在业务代码中直接修改 `Ticket.status`。

## 关键模块

| 模块 | 路径 | 职责 |
|---|---|---|
| API 入口 | `src/main.py` | FastAPI 应用、鉴权、聊天、工单、审批、评测、Metrics 与 HTTP Trace |
| Agent Graph | `src/agents/graph.py` | `AgentState`、节点编排、安全条件路由、token/成本/延迟汇总 |
| Agent 节点 | `src/agents/` | Analyzer、Tooling、Retriever、Resolver、QA、Escalation |
| Tool Registry | `src/tools/registry.py` | 工具注册、Schema、RBAC、超时、内存审计和 Trace |
| Mock Adapter | `src/tools/crm.py`、`order_mgmt.py`、`ticketing.py` | 模拟 CRM、OMS 和历史工单系统 |
| LLM Provider | `src/llm/provider.py` | 定义分析、生成、QA 和通用 Chat 接口；选择 Mock / OpenAI / Azure |
| Guardrails | `src/guardrails/` | PII 脱敏、Prompt Injection、Jailbreak 和 Response Filter |
| RAG | `src/rag/` | 文档解析、分块、Embedding、版本管理、Hybrid Retrieval 和 citation |
| 记忆 | `src/memory/redis_memory.py` | Redis 可选会话历史存储与降级 |
| 审批 | `src/approval/workflows.py` | 创建待审批记录，处理通过、修改、拒绝和审批延迟 |
| 工单状态机 | `src/tickets/state_machine.py` | 工单合法状态与动作约束 |
| 数据模型 | `src/models/` | User、Ticket、SessionMemory、KnowledgeDoc、ResponseApproval 和 API Schema |
| 评测 | `src/evaluation/` | RAGAS / DeepEval Adapter、本地指标与统一评测入口 |
| 可观测 | `src/observability/` | Prometheus Metrics、token/成本估算和 OpenTelemetry Trace |
| 部署 | `deployment/`、`monitoring/` | Docker、Docker Compose、Kubernetes、Prometheus 和 Grafana 模板 |

## 数据流

### `/chat` 主链路

1. Client 提交 `session_id`、`customer_id`、`message` 和 `kb_version`。
2. API 为当次消息新建 `Ticket(status="open")` 并写入 SQL。
3. API 查询或创建 `SessionMemory`，优先从 Redis 读取历史；Redis 无数据或不可用时使用 SQL 历史。
4. API 以当前工单信息构造 `AgentState`并调用 `run_agent_workflow()`。
5. Analyzer 进行安全检测、PII 脱敏和工单分类。
6. Tooling 通过 ToolRegistry 补充客户、订单和历史工单上下文。
7. Retriever 按知识库版本和部门检索 citation。
8. Resolver 合并 Knowledge Base Context 和 Structured Tool Context 生成回复草稿。
9. QA 校验草稿，Escalation 计算 SLA 并决定是否升级。
10. API 回写工单的情绪、优先级、部门和 SLA。
11. 如果 `approval_required = true`，创建 `ResponseApproval(status="pending")`，并通过状态机将工单转为 `pending_approval`。
12. API 将当前用户消息和 AI 回复写入 SQL 与可选 Redis，然后返回回复、`tool_context`、`tool_calls`、`citations`、升级原因、审批 ID 和成本元数据。

**当前限制**：`/chat` 已读取并持久化多轮会话历史，但当前 `AgentState` 没有 `conversation_history` 字段，历史尚未注入 Analyzer 或 Resolver Prompt。因此只能表述为“实现会话历史存储与 Redis 降级”，不能表述为“已完成基于多轮历史的回复生成”。

### 人工审批链路

1. 客服通过 `GET /approvals/pending` 查询待审批草稿。
2. 客服通过 `POST /approvals/{approval_id}` 提交 `approved`、`modified` 或 `rejected`。
3. 系统记录审批人、最终回复和从草稿创建到人工处理的延迟。
4. 状态机将通过/修改的工单转为 `resolved`，将拒绝的工单转回 `in_progress`。
5. 只有 `resolved` 工单可以通过关闭动作转为 `closed`。

### 知识库链路

1. 文档解析支持 PDF、DOCX、HTML、TXT、Markdown 和结构化 FAQ JSON。
2. `RecursiveTextSplitter` 默认使用 `600` 字符 chunk 和 `120` 字符 overlap。
3. `KBVersioningService` 将原文和元数据写入 SQL，并将分块与 Embedding 写入 ChromaDB。
4. 检索时强制 `version`，可选 `category`，扩展候选集后融合向量分数和 BM25 风格词法分数。
5. 最终返回 `source`、`text`、`score` 和 `version` 组成的 citation。

## Prompt 策略

### 总体原则

- Prompt 当前集中在 `src/llm/provider.py` 的 Provider 实现中，没有独立 Prompt Registry 或 Prompt 版本管理。
- `BaseLLMProvider` 定义 `analyze_ticket`、`generate_resolution`、`evaluate_qa` 和 `run_chat` 四类统一接口。
- 默认 `LLM_PROVIDER=mock`，保证无 API Key 的本地开发、测试和演示可复现。
- OpenAI 和 Azure OpenAI 使用 `temperature=0.0`；Analyzer 和 QA 要求 JSON Mode，Resolver 返回自然语言。
- 输入在到达 Prompt 前先经过安全检测与 PII 脱敏，输出在返回客户前经过 QA 和 Response Filter。

### Analyzer Prompt

- 角色是客服工单分析器。
- 输入是脱敏后的主题与描述。
- 输出必须包含情绪、优先级、部门、意图、情绪标签和置信分数。
- 允许的部门为 billing、technical、shipping 和 general；优先级为 low、medium、high 和 urgent。

### Resolver Prompt

- System Prompt 要求只使用提供的上下文回答。
- 上下文同时包含 Knowledge Base citation 和 Structured Tool Context。
- 当上下文不足时，应说明需要升级，而不是自行编造政策或业务结果。
- 对外回复应保持专业、直接、可执行，并在适当位置保留来源依据。

### QA Prompt

- 输入包含 Query、citation 文本和 Resolver 回复。
- 输出必须包含 `qa_score`、`hallucination_detected`、`reasons`、`faithfulness`、`context_precision` 和 `citation_verified`。
- QA 结果不直接修改业务事实，而是为 Escalation 和 Approval 提供决策信号。

### Prompt 修改约束

- 不得在 Prompt 中宣称 Mock Adapter 可以执行真实退款、取消订单或修改 CRM 数据。
- 不得删除“上下文不足时升级”的核心约束。
- 新增 Prompt 字段时必须同步更新 Provider 接口、Mock Provider、外部 Provider 和相关测试。
- Prompt 版本管理与 A/B 灰度尚未实现，不得将其写成已有能力。

## 评测体系

项目包含“在线 QA”和“离线评测 Adapter”两层质量保障，两者不可混为同一概念。

### 在线 QA

- QA Agent 对每次 Agent 草稿返回 `qa_score` 和 `hallucination_detected`。
- `qa_score < 0.8` 或检测到幻觉时触发 Escalation 与人工审批。
- Response Filter 命中指令泄露时强制将分数降为 `0.5` 并标记风险。
- Mock LLM 在无 citation 时返回低 QA 分数和幻觉标记，用于可复现测试。

### 离线评测

- 统一入口是 `run_deeval_evaluation()` 和 `POST /evaluate-response`。
- RAGAS Adapter 输出 Faithfulness、Context Precision、Context Recall 和 Answer Relevance。
- DeepEval Adapter 输出 Hallucination Score 和 Answer Relevance。
- 没有可用 API Key 或外部评测失败时，使用本地文本重合、关键词召回和上下文覆盖率等启发式指标。
- 综合质量分数是 Faithfulness、Context Precision、Context Recall 和 Answer Relevance 的平均值。
- 当前通过条件为综合质量分数 `>= 0.75` 且 Hallucination Rate `< 0.35`。
- 每次评测尝试在 `evaluation/reports/` 写入 JSON 报告。

### 评测边界

- 当前尚无 30–50 条客服 Golden Set，也没有 citation hit rate 回归报告。
- RAGAS 当前的 `ground_truths` 是简化占位映射，不是经人工标注的标准答案。
- 本地启发式指标适合验证评测链路和做基础回归，不能代表生产环境真实准确率。
- 在完成 Golden Set 之前，不得将本项目表述为已建立“生产级 RAG 评测体系”。

## 当前完成情况

### 已完成

- FastAPI 后端 API、JWT 鉴权和基础 RBAC。
- LangGraph 六节点 Agent 工作流和安全条件路由。
- Prompt Injection、Jailbreak、PII 脱敏和 Response Filter。
- ToolRegistry、三类读工具、manager 级退款初筛、Schema、权限、超时和内存审计。
- ChromaDB、知识库版本/类别过滤、Hybrid Retrieval、轻量 rerank 和 citation。
- Mock / OpenAI / Azure OpenAI LLM Provider 适配。
- SQLAlchemy 持久化模型、Redis 可选会话存储与 SQL 降级。
- Human-in-the-Loop 审批与工单状态机。
- OpenTelemetry 统一 Trace / Metrics 采集、OTLP Collector、LangSmith Trace 后端和 Prometheus / Grafana 指标展示。
- Docker Compose、Kubernetes manifests、分层 requirements 和 Python 3.11 GitHub Actions smoke CI。
- RAGAS / DeepEval Adapter、本地评测降级和 JSON 报告输出。
- 覆盖 Agent、API、Auth、Guardrails、RAG、Evaluation、Observability、Tool Registry 和工单状态机的 pytest 测试模块。

### 部分完成

- **多轮记忆**：已存储与降级，但尚未将历史注入 Agent Prompt。
- **工具审计**：调用记录已生成并可通过 API 返回，但 Registry 审计日志仍保存在进程内，尚未持久化。
- **Trace**：核心 Span 与 OTLP Collector 已接入，当前 Collector 将 Trace 转发 LangSmith；尚未接入 Jaeger / Tempo。
- **评测**：指标 Adapter 和报告管道已存在，但缺少 Golden Set、人工标注与稳定回归基线。
- **部署**：本地 Docker Compose 和 Kubernetes 模板已存在，但不代表已在真实生产环境部署。
- **前端**：仓库保留原始 React Dashboard，尚未形成面向当前 Agent 审批闭环的完整客服工作台。

### 已知环境限制

- 项目推荐 Python 3.11。
- 当前本机 `.venv` 使用 Python 3.13，pytest 可因 native dependency / plugin 冲突以 `exit code 139` 崩溃。
- `python -m compileall src tests` 以及直接调用核心 workflow 通常可正常运行。
- 本地 Full pytest 的 `139` 不能直接解读为业务断言失败；应优先使用 Python 3.11 新环境或 GitHub Actions 验证。

## 下一步规划

按当前优先级推进，未在代码中完成前不得将以下项目表述为已有能力。

### P0：RAG Golden Set 与离线回归报告

- 构造 30–50 条 Synthetic Customer Support 样本，覆盖退款、保修、物流、订单取消、账户和技术支持。
- 每条样本包含 Query、Expected Answer Points、Expected Sources、Risk Level 和 Category。
- 输出 citation hit rate、Context Recall、Answer Relevance、Faithfulness Proxy 和 Hallucination Risk。
- 生成稳定的 JSON + Markdown 报告，用于知识库和 Prompt 变更的回归比较。

### P1：多租户知识库隔离

- 为 KnowledgeDoc 和 ChromaDB metadata 增加 `tenant_id`。
- RAG Query 强制使用 `tenant_id + kb_version` Filter。
- 从鉴权上下文解析 Tenant，并增加跨租户越权检索测试。

### P1：检索后端抽象

- 定义 `SearchBackend` 接口。
- 保留当前 `ChromaHybridBackend`。
- 设计 `OpenSearchHybridBackend`，支持 Vector Search、BM25、Metadata Filter、rerank 和 citation。

### P1：审计与可观测增强

- 新增 `ticket_status_events` 持久化状态流转历史。
- 持久化 Tool Calling 审计记录。
- 根据部署需要为 Collector 增加 Jaeger、Tempo 或其他 APM exporter，并完善采样与告警策略。

### P2：客服工作台

- 展示工单列表、AI 草稿、Tool Context、Tool Calls、citation、QA 分数和风险原因。
- 提供审批、修改、拒绝、关闭和重开操作。

### P2：Prompt 版本管理与灰度

- 对 Analyzer、Resolver 和 QA Prompt 进行版本化。
- 记录 Prompt 版本、QA 分数、审批率、延迟和 token 成本。
- 在有 Golden Set 和回归基线后再引入 A/B 或灰度发布。

## 项目不变约束

后续 AI 和开发者必须遵守以下约束：

1. 不得将 Mock CRM、OMS、Ticketing、Refund 或默认 Mock LLM 写成真实企业接入。
2. 所有业务工具必须经过 ToolRegistry，不得在 Agent 中直接调用 Adapter。
3. 工单状态只能通过 TicketStateMachine 流转，不得直接赋值 `ticket.status`。
4. 不得移除 Analyzer 后的安全短路路由。
5. Redis 必须保持可选，本地 Demo 不得因 Redis 未启动而失败。
6. 默认 LLM Provider 必须保持 Mock，以便无 API Key 运行和测试。
7. API 中面向 Demo 和审计的 `tool_context`、`tool_calls`、`citations`、`approval_required`、`approval_id` 和 `cost_metadata` 不得无理由删除。
8. `docs/` 下文档默认使用中文，代码标识符、API 路径和通用技术名词可保留英文。
9. 新能力必须同步更新本文档、相关架构文档、测试和变更日志。
10. 不得根据路线图、接口占位或文档设想宣称能力已实现；是否完成必须以当前代码和测试为准。

## AI 参与开发时的使用方式

1. 首先阅读本文档，确认当前能力、Mock 边界、已知限制和下一步优先级。
2. 在修改前阅读相关实现与测试，不能只依赖旧文档推断现状。
3. 将改动限制在当前任务范围，不重构无关模块，不删除未理解的用户文件。
4. 实现后使用 Python 3.11 环境执行与风险相匹配的编译、定向测试或 CI 验证。
5. 完成新能力时更新本文档中的“当前完成情况”和“下一步规划”，避免上下文失真。
