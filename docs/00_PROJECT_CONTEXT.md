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
- 通过独立 Risk Engine 统一评估安全、业务、分类置信度和回复质量，对高风险或临界风险引入 Human-in-the-Loop。
- 通过 citation、QA 结果、工具审计和 Trace 为客服坐席提供可核查依据。

### 工程目标

- 使用 LangGraph 将 Agent 流程拆分为职责清晰、可独立观测的节点。
- 使用 LangGraph Checkpoint 持久化 Graph State，让高风险回复可在人工审批前暂停，并在进程重启后从原 Thread 恢复。
- 通过 ToolRegistry 统一工具协议，实现 Schema 校验、RBAC、超时和调用审计。
- 使用 Hybrid RAG 兼顾语义检索与政策编号、产品名、时间窗口等精确词匹配。
- 保持默认 Mock LLM、可选 Redis 和 SQLite 本地配置，使项目在无企业凭据、无外部 LLM 和无 Redis 时仍可复现。
- 通过 Prometheus、OpenTelemetry、分层依赖、Python 3.11 CI 和 Agent Evaluation Quality Gate 提供可观测性、可维护性与发布质量保障。

## 核心能力

1. **工单分析**：识别 `sentiment`、`priority`、`department` 和 `intent`。
2. **多层安全短路**：先执行 Unicode 规范化、中英文特征、组合启发式、角色提权与 Base64 载荷扫描，规则未命中时再使用 Qwen3Guard-Gen-0.6B 扫描客户输入、Tool 返回和 RAG 文档。
3. **PII 脱敏**：正常请求进入 LLM 前对主题和描述中的敏感信息进行匿名化。
4. **业务工具上下文**：通过 ToolRegistry 查询客户画像、近期订单和历史工单，并把结构化结果注入 Resolver。
5. **工具治理**：工具具有 `input_schema`、`output_schema`、`min_role`、`timeout_seconds` 和 `mocked` 元数据；每次调用返回状态、耗时、权限结果和错误。
6. **Hybrid RAG**：融合 ChromaDB 向量召回、进程内 BM25 风格词法打分和轻量 rerank，返回带版本的 citation。
7. **回复生成与 QA**：使用知识库 citation 和 Tool Context 生成草稿，再评估 QA 分数、幻觉风险和输出泄露。
8. **Risk Engine 与 Human-in-the-Loop**：统一输出 `risk_level`、`risk_score`、`risk_reasons`、是否人工处理及是否阻断自动化，并为高风险草稿创建审批记录。
9. **工单状态机**：统一约束 `open`、`in_progress`、`pending_approval`、`resolved` 和 `closed` 的合法流转。
10. **分层记忆**：SQL `SessionMemory` 保存持久化对话历史，Redis 作为可选短期快速存储，不可用时回退到 SQL。
11. **可观测性**：使用 OpenTelemetry 统一采集 Trace 与 Metrics；Collector 将 Trace 转发 LangSmith，并通过 Prometheus exporter 提供指标，由 Grafana 展示。
12. **离线评测适配**：提供 RAGAS、DeepEval 和本地确定性指标的统一评测入口。
13. **Durable Execution**：使用 SQLite / PostgreSQL Checkpointer、稳定 `thread_id`、`AgentExecution` 业务元数据和数据库恢复租约，支持 `interrupt` / `Command(resume=...)`、重启恢复和幂等重试。

## 技术栈

| 层级 | 技术 | 当前用途 |
|---|---|---|
| API | Python、FastAPI、Pydantic | 异步 API、请求/响应 Schema与健康检查 |
| Agent 编排 | LangGraph、LangGraph Checkpoint | 编排 Analyzer、Tooling、Retriever、Resolver、QA、Escalation 和 Approval Gate，持久化暂停/恢复状态 |
| LLM | Mock LLM、OpenAI、Azure OpenAI | 默认 Mock 保证离线可复现；通过 `BaseLLMProvider` 适配外部模型 |
| 数据库 | SQLAlchemy Async、SQLite、PostgreSQL | 本地默认 SQLite；Docker Compose 使用 PostgreSQL |
| 短期记忆 | Redis | 可选的会话历史快速存储，失败时不影响 SQL 持久化 |
| RAG | ChromaDB、Embedding、Hybrid RAG | 知识库分块、版本/类别过滤、向量与词法混合召回、rerank |
| 安全 | JWT、RBAC、Prompt Guardrails、Qwen3Guard-Gen-0.6B、Risk Engine | API 鉴权、工具权限、PII 脱敏、规则 + 语义的直接/间接 Prompt Injection 检测、Jailbreak、输出过滤和统一风险分级 |
| 评测 | RAGAS、DeepEval、确定性 Security Evaluator、本地启发式指标 | RAG 质量、Agent 行为、安全检测混淆矩阵与阻断处置质量 |
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
  |      `-- Risk Engine --> Escalation --> Approval Gate
  |                                      |-- 普通请求 --> END
  |                                      `-- 高风险 --> Checkpoint / interrupt --> Human-in-the-Loop --> resume
  |
  +--> SQLAlchemy Async --> SQLite / PostgreSQL
  |      |-- User
  |      |-- Ticket
  |      |-- SessionMemory
  |      |-- KnowledgeDoc
  |      |-- ResponseApproval
  |      `-- AgentExecution + LangGraph Checkpoint
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

- 请求标识：`ticket_id`、`customer_id`、`subject`、`description`、`kb_version`、`checkpoint_thread_id`。
- 分析结果：`sentiment`、`priority`、`intent`、`department`、`analyzer_confidence`。`intent` 必须来自统一 `IntentType`：`billing_dispute`、`outage_report`、`order_cancellation`、`order_status`、`account_support`、`warranty_claim`、`feedback`、`information_request`；最后一项是唯一兜底值。
- 权限与工具：`operator_role`、`tool_context`、`tool_calls`。
- RAG 与回复：`context_citations`、`suggested_response`。
- 安全与风险：`security_threat_detected`、`security_risk_score`、`security_findings`、`semantic_guard_label`、`semantic_guard_categories`、`semantic_guard_checks`、`semantic_guard_degraded`、`risk_level`、`risk_score`、`risk_reasons`、`risk_requires_human`、`risk_block_automation`。
- 质量结果：`qa_score`、`hallucination_detected`、`citation_verified`、`errors`。
- 性能策略：`analyzer_strategy`、`qa_strategy`，用于区分规则短路与 LLM 评估。
- 闭环决策：`escalation_recommended`、`escalation_reason`、`approval_required`。
- 持久执行：`checkpoint_namespace`、`durable_execution_enabled`、`execution_status`、`approval_status`、`human_decision`。
- 成本与延迟：`tokens_input`、`tokens_output`、`cost_usd`、`latency_seconds`。

当前项目没有另外定义 `TaskState`，仍由单一 `AgentState` 承载固定 Workflow 的上下文；但 Graph State 已通过 LangGraph Checkpointer 持久化。本地默认使用独立 SQLite Saver，PostgreSQL 环境默认使用 AsyncPostgresSaver。

### 路由

```text
analyzer
  |-- 命中 Prompt Injection / Jailbreak
  |      `--> escalation --> approval_gate
  |
  `-- 正常请求
         `--> context_enrichment
                |-- tooling（并行）
                `-- retriever（并行）
                      |-- 任一上下文命中注入 --> escalation --> approval_gate
                      `-- 合并安全结果与上下文 --> resolver --> qa --> escalation --> approval_gate

approval_gate
  |-- 无需审批 --> END
  `-- 需审批 --> interrupt + Checkpoint --> 人工决策 --> Command(resume) --> END
```

### 节点职责

1. **Analyzer**
   - 先执行多层 Prompt Injection 和 Jailbreak 检测。
   - 命中安全风险时写入 `errors`，设置紧急优先级和拒绝回复，不执行后续 Tooling、RAG、Resolver 和 QA。
   - 正常请求先对 PII 脱敏；固定单意图且高置信度时使用规则输出必要字段，模糊或多意图时才调用 LLM。
2. **Tooling**
   - 始终查询客户画像和历史工单。
   - 只在 billing、shipping 或相关意图下查询订单历史。
   - 所有调用必须经过 ToolRegistry，Agent 不能直接调用 Mock Adapter。
   - 工具返回在写入 Tool Context 前扫描间接 Prompt Injection；命中后保留调用审计，但清空工具上下文并短路。
3. **Retriever**
   - 用工单主题和描述构造 Query，默认返回 Top 3 citation。
   - 强制带 `kb_version`，并优先按 `department` 过滤类别。
   - 类别过滤无结果时，保留版本过滤并放宽类别再检索一次。
   - citation 在交给 Resolver 前扫描间接 Prompt Injection；命中后清空 citation 并短路。
   - 与 Tooling 并行执行，由 Context Enrichment 统一合并结果；风险信号只升不降。
4. **Resolver**
   - 只选取最高相关的 Top-2 citation 与必要 Tool 字段，并限制上下文字符数。
   - 将精简上下文交给 LLM Provider，只生成最终客服回复并限制输出 token。
5. **QA**
   - 空回复、输出泄露或完全缺少依据等确定性失败优先使用规则判断，不调用 LLM。
   - 其余请求使用可单独配置的轻量模型，仅返回 `score`、`hallucination_detected`、`citation_verified`。
   - 通过 Response Filter 删除内部指令或工作流泄露；命中时将 QA 分数降为 `0.5` 并标记幻觉。
6. **Escalation**
   - 按优先级计算 SLA：urgent `2h`、high `12h`、medium `24h`、low `48h`。
   - 调用独立 Risk Engine 综合安全威胁、优先级、情绪、业务意图、Analyzer 置信度、QA、幻觉和 Workflow 错误。
   - 默认风险等级阈值为 `medium >= 0.4`、`high >= 0.7`、`critical >= 0.9`；`high` / `critical` 要求人工处理。
   - 建议升级、`qa_score < 0.8` 或 `risk_requires_human = true` 任一命中，就设置 `approval_required = true`。
7. **Approval Gate**
   - 无需审批时直接结束；需审批时调用 LangGraph `interrupt()` 暂停并保存 Checkpoint。
   - 人工通过、修改或拒绝后，API 使用原 `thread_id` 和 `Command(resume=...)` 续跑，不重跑 Analyzer、Tool、RAG、Resolver 和 QA。

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
| Checkpoint | `src/agents/checkpointing.py` | 根据环境管理 Memory / SQLite / PostgreSQL Saver 及其连接生命周期 |
| Durable Execution | `src/agents/durable_execution.py` | 管理 Thread 业务关联、执行状态、恢复租约、重启扫描和幂等续跑 |
| Agent 节点 | `src/agents/` | Analyzer、Tooling、Retriever、Resolver、QA、Escalation |
| Tool Registry | `src/tools/registry.py` | 工具注册、Schema、RBAC、风险策略、执行和 Trace |
| Tool Governance | `src/tools/governance.py` | 高风险写 Action 的加密提议、职责分离审批、状态机和持久化审计 |
| Mock Adapter | `src/tools/crm.py`、`order_mgmt.py`、`ticketing.py` | 模拟 CRM、OMS 和历史工单系统 |
| LLM Provider | `src/llm/provider.py` | 定义分析、生成、QA 和通用 Chat 接口；选择 Mock / OpenAI / Azure，并支持 Analyzer/QA 独立 Fast Model 路由 |
| Guardrails | `src/guardrails/` | PII 脱敏、Prompt Injection、Jailbreak 和 Response Filter |
| Risk Engine | `src/risk/engine.py` | 统一综合安全、业务、置信度、QA 和异常信号，输出风险等级与处置建议 |
| RAG | `src/rag/` | 文档解析、分块、Embedding、版本管理、Hybrid Retrieval 和 citation |
| 记忆 | `src/memory/redis_memory.py` | Redis 可选会话历史存储与降级 |
| 审批 | `src/approval/workflows.py` | 创建待审批记录，处理通过、修改、拒绝和审批延迟 |
| 工单状态机 | `src/tickets/state_machine.py` | 工单合法状态与动作约束 |
| 数据模型 | `src/models/` | User、Ticket、SessionMemory、KnowledgeDoc、ResponseApproval、AgentRun、AgentExecution、Feedback 与 Tool Action/Audit |
| 评测 | `src/evaluation/` | RAGAS / DeepEval Adapter、本地指标与统一评测入口 |
| 可观测 | `src/observability/` | Prometheus Metrics、token/成本估算和 OpenTelemetry Trace |
| 部署 | `deployment/`、`monitoring/` | Docker、Docker Compose、Kubernetes、Prometheus 和 Grafana 模板 |

## 数据流

### 用户咨询与客服后台主链路

1. 终端用户通过用户咨询页提交问题，前端调用 `POST /support/requests`。
2. API 创建唯一业务工单并执行 LangGraph Workflow，随后持久化 `AgentRun`，包含回复、citation、Tool Call、QA、版本、Token、延迟和 Trace ID。
3. 普通且通过质量门的请求只向用户返回安全的最终回复，不暴露 Tool、QA、风险或 Trace 内部字段。
4. 高风险、低置信度、低 QA、幻觉或异常请求创建 `ResponseApproval`，用户页只显示“已转交人工客服”。
5. 客服员工后台通过受 RBAC 保护的 `GET /staff/review-queue` 仅加载 `pending_approval` 工单，不展示普通自动处理工单。
6. 员工打开详情时调用 `GET /tickets/{ticket_id}/agent-result`，只读取最新持久化结果，不重新执行 Workflow；审批完成后工单自动移出人工队列。

### `/chat` 主链路

1. Client 提交 `session_id`、`customer_id`、`message` 和 `kb_version`。
2. API 为当次消息新建 `Ticket(status="open")` 并写入 SQL。
3. API 查询或创建 `SessionMemory`，优先从 Redis 读取历史；Redis 无数据或不可用时使用 SQL 历史。
4. API 以当前工单信息构造 `AgentState`并调用 `run_agent_workflow()`。
5. Analyzer 进行输入多层安全检测、PII 脱敏、工单分类和初始风险评估。
6. Context Enrichment 并行执行 Tooling 与 Retriever：前者补充客户、订单和历史工单上下文，后者按知识库版本和部门检索 citation；两条分支分别扫描间接注入。
7. 系统以风险只升不降的方式合并两条分支；任一分支命中安全威胁就清空受污染上下文并直接进入 Escalation。
8. Resolver 合并 Knowledge Base Context 和 Structured Tool Context 生成回复草稿。
9. QA 校验草稿，Risk Engine 更新输出风险，Escalation 计算 SLA 并决定是否升级。
10. API 回写工单的情绪、优先级、部门和 SLA。
11. Approval Gate 对普通请求直接结束；如果 `approval_required = true`，则在持久化 Checkpoint 后 `interrupt`。
12. API 创建 `ResponseApproval(status="pending")` 和 `AgentExecution(status="interrupted")`，并通过状态机将工单转为 `pending_approval`。
13. API 将当前用户消息和 AI 草稿写入 SQL 与可选 Redis，然后返回回复、`tool_context`、`tool_calls`、`citations`、升级原因、审批 ID 和成本元数据。

**当前限制**：`/chat` 已读取并持久化多轮会话历史，但当前 `AgentState` 没有 `conversation_history` 字段，历史尚未注入 Analyzer 或 Resolver Prompt。因此只能表述为“实现会话历史存储与 Redis 降级”，不能表述为“已完成基于多轮历史的回复生成”。

### 人工审批链路

1. 客服通过 `GET /approvals/pending` 查询待审批草稿。
2. 客服通过 `POST /approvals/{approval_id}` 提交 `approved`、`modified` 或 `rejected`。
3. 系统记录审批人、最终回复和从草稿创建到人工处理的延迟，再原子抢占数据库恢复租约。
4. 续跑使用原 Checkpoint Thread，只重新进入 Approval Gate；成功后更新 AgentRun 的 Workflow Path 和 AgentExecution。AgentRun 保留原始 AI 草稿，人工最终回复保存在 ResponseApproval / Feedback，供 DPO 数据正确区分 rejected 与 chosen。
5. 状态机将通过/修改的工单转为 `resolved`，将拒绝的工单转回 `in_progress`。恢复失败时状态保留为 `resume_pending`，可在重启扫描或主管 API 中重试。
6. 只有 `resolved` 工单可以通过关闭动作转为 `closed`。

### 知识库链路

1. 文档解析支持 PDF、DOCX、HTML、TXT、Markdown 和结构化 FAQ JSON。
2. `RecursiveTextSplitter` 默认使用 `600` 字符 chunk 和 `120` 字符 overlap。
3. `KBVersioningService` 将原文和元数据写入 SQL，并将分块与 Embedding 写入 ChromaDB。
4. 检索时强制 `version`，可选 `category`，扩展候选集后融合向量分数和 BM25 风格词法分数。
5. 最终返回 `source`、`text`、`score` 和 `version` 组成的 citation。

## Prompt 策略

### 总体原则

- Prompt 当前集中在 `src/llm/provider.py` 的 Provider 实现中。Agent Run 会保存配置型 `prompt_version`，但没有独立 Prompt Registry、Prompt 内容快照或发布管理。
- `BaseLLMProvider` 定义 `analyze_ticket`、`generate_resolution`、`evaluate_qa` 和 `run_chat` 四类统一接口。
- 默认 `LLM_PROVIDER=mock`，保证无 API Key 的本地开发、测试和演示可复现。
- OpenAI 和 Azure OpenAI 使用 `temperature=0.0`；Analyzer 和 QA 要求 JSON Mode，Resolver 返回自然语言。
- OpenAI-compatible Provider 支持通过 `LLM_FAST_*` 将 Analyzer 与 QA 路由到独立小模型服务（例如 Qwen Turbo），Resolver 继续使用 `LLM_MODEL_NAME`；未配置 Fast Model 时安全回退主模型。
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
- 配置型 `prompt_version` 已用于运行归因；Prompt Registry、内容快照、发布管理与 A/B 灰度尚未实现，不得将其写成已有能力。

## 评测体系

项目包含“在线 QA”和“离线评测 Adapter”两层质量保障，两者不可混为同一概念。

### 在线 QA

- QA Agent 对每次 Agent 草稿返回 `qa_score` 和 `hallucination_detected`。
- `qa_score < 0.8` 或检测到幻觉时触发 Escalation 与人工审批。
- Response Filter 命中指令泄露时强制将分数降为 `0.5` 并标记风险。
- Mock LLM 在无 citation 时返回低 QA 分数和幻觉标记，用于可复现测试。

### 离线评测

- 在线单条评测入口是 `run_deeval_evaluation()` 和 `POST /evaluate-response`。
- 离线统一入口是 Dataset + Workflow Replay Pipeline，RAG 采用 RAGAS，Agent 行为采用 DeepEval。
- 第一版真实 Baseline 入口是 `scripts/run_baseline_eval.py`：固定读取 100 条 Baseline，逐 Case 构造完整 Ticket State 并回放当前 LangGraph Workflow。Case Pass 仅使用 intent、department、Required/Forbidden Tool、HITL 和 Approval 六类确定性比较；暂不读取 reference answer、priority、expected nodes 和安全标签参与判定。
- Baseline V1 在同一次 OTel Trace 中采集端到端与 Analyzer / Tool / RAG / Resolver / QA 节点耗时、Token、模型、Analyzer 策略和 LLM 调用明细，报告汇总 Average、P50、P95、平均 Token 与 Rule Hit Rate，并关联实际 Agent Trace ID。
- 每次 Baseline V1 正式运行同时保存带本地时间戳的不可变 JSON / Markdown 快照，`baseline_v1_latest.*` 以普通文件副本保留最新内容，兼容 Typora 等不打开符号链接的桌面工具；报告固定记录 Dataset SHA256、Evaluator 范围、Workflow/Prompt 版本、模型、生成限制、Risk 阈值与 Observability 配置。旧单条评测隔离到 `single_response/` 并最多保留 20 份，所有运行报告默认不提交 Git。
- Baseline JSON 写入后会纯离线、确定性生成 `error_analysis_<run_id>.md` 与 `error_analysis_latest.md`，只分析 FAIL Case 的 Failure Breakdown、Intent Confusion Matrix、HITL/Approval mismatch、Tool 问题和逐 Case Expected/Actual/Trace，不重放 Workflow、不调用 LLM、不修改 Dataset 或 Agent。
- PR Gate 使用 Mock Provider 在隔离 SQLite/Chroma 目录中回放同一固定 100 条 Workflow，对 Dataset Hash、六项行为指标和新增失败 Case 执行免费、确定性门禁。Release Gate 必须显式确认付费调用，对真实 LLM 报告额外检查 P95、Token、LLM Calls 和 Analyzer Rule Hit Rate。
- GitHub Actions `CI` 执行全量后端测试、前端构建、PR Gate 和镜像构建；仅当 `Release Quality Gate` 通过时，`CD` 才会将完全相同 Git SHA 的镜像发布到 GHCR。当前交付目标是镜像仓库，不代表已自动部署生产集群。
- 正式离线报告同时输出 Faithfulness、Answer Relevancy、Context Precision、Context Recall、Agent 行为指标、Security Precision / Recall / F1 / 误报率、安全处置正确率、citation hit rate、Workflow Path 和 Trace ID。
- 没有可用 API Key 时可显式选择 `local` 确定性指标进行 CI 烟测；正式 RAGAS / DeepEval 模式缺少依赖或密钥会直接失败，不会自动伪装为正式结果。
- 报告写入 `evaluation/reports/evaluation_latest.json` 和 `evaluation_latest.md`。

### 评测边界

- 当前有 13 条 Synthetic Golden Dataset，另有 100 条 Workflow Replay Baseline；Golden Dataset 本身仍需继续扩充和人工复核。
- Synthetic 参考答案不是经真实客服专家审核的生产标准答案。
- 本地启发式指标适合验证评测链路和做基础回归，不能代表生产环境真实准确率。
- 在完成人工标注、稳定基线和真实环境校准前，不得将本项目表述为已有生产质量结论。

## 当前完成情况

### 已完成

- FastAPI 后端 API、JWT 鉴权和基础 RBAC。
- LangGraph 六个业务节点 + Approval Gate 工作流和安全条件路由。
- LangGraph Checkpoint + Durable Execution：本地 SQLite / 生产 PostgreSQL Saver、`interrupt` / `Command(resume)`、`AgentExecution` 状态、数据库恢复租约、启动恢复和主管手动重试。
- Prompt Injection、Jailbreak、PII 脱敏和 Response Filter。
- ToolRegistry、4 个读 Tool 与 1 个高风险 Mock 写 Tool，具备 Schema、RBAC、风险策略和超时边界。
- Tool Governance V2.1：高风险写操作必须经过 `proposed -> pending_approval -> approved/rejected -> executing -> succeeded/failed/unknown` 状态机；提议人不能批准自己的 Action，且 Agent Workflow 不会自动路由该写 Tool。
- Tool 调用已持久化到 `tool_invocation_audits`，只保存 HMAC、字段名、脱敏结果、执行状态、身份与 Request/Trace 关联；Action 迁移以 Append-only Event 保存。
- ChromaDB、知识库版本/类别过滤、Hybrid Retrieval、轻量 rerank 和 citation。
- Mock / OpenAI / Azure OpenAI LLM Provider 适配。
- SQLAlchemy 持久化模型、Redis 可选会话存储与 SQL 降级。
- Human-in-the-Loop 审批与工单状态机。
- OpenTelemetry 统一 Trace / Metrics 采集、OTLP Collector、LangSmith Trace 后端和 Prometheus / Grafana 指标展示。
- Docker Compose、Kubernetes manifests、分层 requirements、Python 3.11 GitHub Actions 全量 CI、两级 Evaluation Quality Gate 与 GHCR CD。
- RAGAS / DeepEval Adapter、本地评测降级和 JSON 报告输出。
- Dataset + Workflow Replay 离线评测，统一输出 RAG / Agent / Security 指标并关联 Trace ID。
- Baseline Workflow Replay V1：固定 100 条 Dataset、完整 Ticket State、六项确定性行为指标、逐 Case 执行结果及 OTel Trace 同源性能报告。
- 真实 LLM Regression 专用入口，支持 12 条 smoke 和 100 条 full 套件，具备 Mock 拒绝、显式确认、调用预算和模型/Token/成本归因。
- Feedback Pipeline 第一阶段：Agent Run 快照、用户评价、人工修正、评测结果关联，以及脱敏后的 SFT / DPO 候选导出。
- LangSmith 前端入口：主管/管理员可分页查看 Agent Run、Trace ID、Workflow Path 和执行快照，并跳转至配置的 LangSmith Project 下钻。
- Prompt Injection 多层检测已覆盖用户输入、Tool 返回和 RAG 文档，命中时从当前信任边界短路到 Escalation。
- Qwen3Guard-Gen-0.6B 已作为独立 OpenAI-compatible 语义安全 Adapter 接入三类信任边界；默认关闭外部服务，启用后将 `Safe / Controversial / Unsafe` 交给 Risk Engine。
- 独立 Risk Engine 已接入 Analyzer、QA、Escalation、AgentState、API、Trace、Metrics 和结构化日志。
- 第一版 Resilience 已覆盖 LLM、Hybrid RAG 和 Tool：统一故障分类、超时、有界 Retry、进程内 Circuit Breaker、可选备用模型/单路 RAG Fallback，并将降级事件关联 AgentState、Risk Engine、Trace 和 Metrics。
- MVP 主链路已实测通过：FastAPI `/health` -> LangGraph Workflow -> Ticket / AgentRun 持久化 -> 用户评价 -> FeedbackEvent 持久化。
- 覆盖 Agent、API、Auth、Guardrails、RAG、Evaluation、Observability、Tool Registry 和工单状态机的 pytest 测试模块。

### 部分完成

- **多轮记忆**：已存储与降级，但尚未将历史注入 Agent Prompt。
- **Tool Governance**：V2.1 已实现持久化审计与高风险 Action 状态机；当前写 Tool 仍是 Mock，尚无跨服务幂等键、Outbox、自动 Reconciliation Worker 和生产 Alembic Migration。
- **Trace**：核心 Span 与 OTLP Collector 已接入，当前 Collector 将 Trace 转发 LangSmith；尚未接入 Jaeger / Tempo。
- **评测**：已具备 Golden Dataset、100 条 Workflow Replay Baseline、真实 LLM 运行入口、统一报告与两级 Quality Gate。2026-08-30 同一固定 Dataset 的 DeepSeek + Qwen 真实复测将 Case Pass Rate 从 `0.54` 提升到 `0.99`，平均耗时约 `1.62s`、P95 约 `3.24s`、平均总 Token `453.29`、LLM Calls `87`。PR Gate 要求 Mock 确定性回放 100% 通过，Release Gate 固化当前真实模型质量和性能阈值；语义回答质量与人工标注仍是后续评测范围。
- **Feedback Pipeline**：第一阶段采集和候选导出已实现，尚未接入标注平台、训练任务、Dataset Registry 和模型发布门禁。
- **部署**：本地 Docker Compose 和 Kubernetes 模板已存在，但不代表已在真实生产环境部署。
- **前端**：React 已拆分用户咨询页与客服员工后台；员工后台仅处理待审批异常工单，并保留 Agent Run / LangSmith 可观测入口。尚未接入 Prometheus 真实趋势指标、内嵌 Span 时间轴和异步消息通知。
- **安全治理**：已有确定性多层检测、Qwen3Guard 语义 Adapter 与可配置 Risk Engine，但 Guard 服务默认未启用，且尚无策略版本、持久化安全事件和真实数据阈值校准。
- **故障治理**：已完成单进程第一版；尚无分布式 Circuit Breaker、Queue / DLQ、跨服务幂等键、写操作结果对账与故障注入压测。
- **Durable Execution**：已覆盖人工审批等待与重启续跑；尚无 Checkpoint TTL/归档清理、多 Workflow 版本兼容执行器、通用后台任务队列和全节点失败的自动续跑策略。

### 已知环境限制

- 项目推荐 Python 3.11。
- 旧的本机 `.venv` 是混装 Evaluation 依赖的 Python 3.13 环境，其 pytest `exit code 139` 与 LangGraph 版本冲突不代表业务断言失败。
- 核心运行时已固定经验证的 LangChain / LangGraph / ChromaDB 版本组合；2026-09-04 当前环境全量测试 200 passed，包含 Checkpoint 跨 Saver 重启恢复、审批续跑幂等与 Feedback 兼容回归；CI / Docker 继续使用 Python 3.11。
- 本地 ChromaDB 使用版本化目录 `.runtime/chromadb-0.5`；其他 ChromaDB 大版本写入的旧 SQLite schema 不应直接复用。

## 下一步规划

按当前优先级推进，未在代码中完成前不得将以下项目表述为已有能力。

### P0：Feedback Dataset 治理与训练准备

- 增加 Dataset Registry、数据版本、Review 状态和训练集快照。
- 建立训练样本人工复核、数据删除、数据保留周期和来源授权策略。
- 增加 SFT / DPO 数据分层、Train / Validation / Test 划分和数据漂移检查。

### P1：扩充 Golden Set 与回归基线

- 继续扩充并人工复核 Synthetic Golden Dataset，将保修、物流和订单取消等尚未入库政策与现有 100 条 Baseline 分开治理。
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
- 为真实写 Tool 增加业务幂等键、Outbox 与 Unknown 结果自动对账。
- 根据部署需要为 Collector 增加 Jaeger、Tempo 或其他 APM exporter，并完善采样与告警策略。

### P2：用户通知与异步处理

- 将同步 `POST /support/requests` 演进为提交后立即返回 `ticket_id` 的后台任务。
- 增加用户身份、工单归属校验以及人工审批完成后的站内通知或推送。

### P2：Prompt 版本管理与灰度

- 对 Analyzer、Resolver 和 QA Prompt 进行版本化。
- 记录 Prompt 版本、QA 分数、审批率、延迟和 token 成本。
- 在有 Golden Set 和回归基线后再引入 A/B 或灰度发布。

## 项目不变约束

后续 AI 和开发者必须遵守以下约束：

1. 不得将 Mock CRM、OMS、Ticketing、Refund 或默认 Mock LLM 写成真实企业接入。
2. 所有业务工具必须经过 ToolRegistry，不得在 Agent 中直接调用 Adapter。
3. 工单状态只能通过 TicketStateMachine 流转，不得直接赋值 `ticket.status`。
4. 不得移除 Analyzer、Tooling 和 Retriever 后的安全短路路由。
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
