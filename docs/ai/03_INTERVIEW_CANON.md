# SupportGPT Enterprise 面试事实口径

> 本文是本项目唯一允许在面试、简历、项目介绍、AI 回答和对外沟通中引用的事实文档。
> 如其他文档、历史聊天或旧版本描述与本文不一致，以本文为准；如本文与当前代码不一致，以当前代码为准，并必须在同一次改动中更新本文。
> 本文不用于包装未实现能力。无法从仓库、已确认项目设定或用户实际经历中证实的事项，必须明确说明“未知”或“不适用”。

## 1. 项目定位

SupportGPT Enterprise 是一个面向企业售后客服场景的、可本地运行的生产风格 AI Agent 项目。它将初版 FAQ / RAG 问答能力扩展为包含工单理解、结构化业务上下文、知识检索、回复生成、质量校验、风险拦截、人工审批和工单状态闭环的客服处理平台。

项目用于展示 Agentic RAG、Tool Calling 治理、Human-in-the-Loop 和可观测性等工程能力。它不是已连接真实企业数据、已在生产客服中心上线的系统。

## 2. 项目背景

项目基于开源客服项目进行改造，目标是将单一客服问答体验升级为更接近企业售后工作流的系统。重点业务场景包括退款、保修、物流异常、订单取消、账户问题和技术支持。

CRM、OMS、历史工单和退款资格初筛当前均通过本地 Mock Adapter 模拟。默认 LLM 也为 Mock Provider，以保证本地无 API Key 环境下可复现。

## 3. 项目目标

- 让客户自然语言问题进入可分析、可路由、可审核的工单流程。
- 在回复生成前补充客户、订单和历史工单等结构化业务事实。
- 使用带版本和类别过滤的 Hybrid RAG 提供知识依据与 citation。
- 在输入、工具、输出和工单状态多个层面设置安全与治理边界。
- 对高风险、低置信度或紧急问题引入人工审批，而不是让模型自动完成业务闭环。
- 提供本地可运行、可观测、可替换真实服务的工程骨架。

## 4. 团队情况

仓库与已确认项目资料**没有记录真实团队人数、成员名单、组织关系、协作方式或个人贡献占比**。

因此，对外不得声称：

- 这是多人团队项目，或具体说明团队人数。
- 自己担任过不存在证据支持的职位，例如 Tech Lead、架构负责人或项目经理。
- 自己独立完成了仓库中的全部代码，除非提问者本人能基于真实经历确认。

可以准确说明：这是一个基于开源项目改造的简历项目，现有仓库展示了客服 Agent、RAG、工具治理、审批和可观测性等能力。

## 5. 我的职责

仓库不能证明具体个人对每个文件的作者归属。因此“我的职责”必须与回答者的真实参与经历一致，不能由本文虚构。

在仅依据仓库可验证事实的情况下，可以描述的**项目改造范围**为：

- 将客服处理流程组织为安全检测、业务上下文补全、RAG、回复生成、QA 和升级决策的显式 Agent Workflow。
- 增加 Tool Calling 的 Schema、RBAC、超时和审计约束。
- 增加 Hybrid RAG、知识库版本/类别过滤和 citation。
- 增加可选 Redis 记忆、SQL 持久化、HITL 审批、工单状态机、Prometheus 与 OpenTelemetry。
- 增加中文项目、架构、Mock 边界和 AI 接手文档。

如需使用第一人称“我负责”，应仅陈述回答者实际参与且能在追问中解释的部分，不得把“项目具备”自动等同于“我独立完成”。

## 6. 系统架构

系统由以下层次组成：

```text
客服端 / API Client
        |
        v
FastAPI API 层（鉴权、工单、聊天、审批、评测、Metrics）
        |
        v
LangGraph Agent Workflow
  Analyzer -> Tooling -> Retriever -> Resolver -> QA -> Escalation
       \-> 安全风险时直接进入 Escalation
        |
        +-- ToolRegistry -> Mock CRM / OMS / Ticketing
        +-- Hybrid RAG -> ChromaDB
        +-- LLM Provider -> Mock / OpenAI / Azure OpenAI
        +-- HITL -> ResponseApproval + 工单状态机
        |
        +-- SQLAlchemy -> SQLite / PostgreSQL
        `-- Redis（可选会话缓存）

Prometheus + OpenTelemetry 覆盖 API、Agent、工具、RAG 和审批过程。
```

正常请求的固定顺序为：Analyzer → Tooling → Retriever → Resolver → QA → Escalation。命中 Prompt Injection 或 Jailbreak 时，系统跳过 Tooling、RAG、Resolver 和 QA，直接进入 Escalation。

## 7. 技术栈

| 领域 | 当前技术 |
|---|---|
| 后端与 API | Python、FastAPI、Pydantic |
| Agent 编排 | LangGraph |
| 数据访问 | SQLAlchemy Async |
| 本地数据库 | SQLite |
| 容器化数据库 | PostgreSQL |
| 短期会话缓存 | Redis（可选） |
| 向量数据库 | ChromaDB |
| 检索 | Embedding、Hybrid RAG、BM25 风格词法打分、轻量 rerank |
| LLM | Mock LLM、OpenAI、Azure OpenAI Provider |
| 安全 | JWT、RBAC、PII 脱敏、Prompt Injection、Jailbreak、Response Filter |
| 审批 | Human-in-the-Loop、工单状态机 |
| 可观测 | Prometheus、OpenTelemetry |
| 部署与验证 | Docker、Docker Compose、Kubernetes manifests、pytest、GitHub Actions |

未使用或未实现的技术包括：MCP、pgvector、独立 TaskState、LangGraph Checkpoint、动态 Planner、自动 Reflection Loop、多租户知识隔离、生产搜索后端、Prompt 版本灰度。

## 8. Agent 数量与职责

当前存在 **6 个逻辑 Agent 节点**。它们是单个 LangGraph Workflow 中职责分离的节点，不代表 6 个独立部署的模型服务。

| Agent | 职责 |
|---|---|
| Analyzer | PII 脱敏、Prompt Injection/Jailbreak 检测、情绪/优先级/部门/意图分类 |
| Tooling | 调用受治理的业务工具，补充客户、订单和历史工单上下文 |
| Retriever | 按知识库版本与类别进行 Hybrid RAG 检索，返回 citation |
| Resolver | 汇总工单、RAG citation 和 Tool Context，生成客服草稿 |
| QA | 评估质量与幻觉风险，并执行输出泄露过滤 |
| Escalation | 计算 SLA，判断升级与人工审批需求 |

当前没有独立 Planner、Selector、Reviewer 以外的 Agent、Validator Agent 或 Reflection Agent。QA 承担 Review 职责；安全、工具和状态验证由分层规则完成。

## 9. Tool 数量与 Tool Calling

当前 ToolRegistry 中注册 **4 个 Tool**：

| Tool | 权限 | 当前用途 |
|---|---|---|
| 客户画像查询 | agent 及以上 | 返回客户等级和未结工单数量 |
| 订单历史查询 | agent 及以上 | 返回近期订单、状态和付款信息 |
| 历史工单查询 | agent 及以上 | 返回过去工单与处理结果 |
| 退款资格初筛 | manager 及以上 | 高风险 Mock 初筛；主 Workflow 不会自动调用 |

前三个为读工具，其中客户画像和历史工单在正常请求中调用；订单工具只在账单、物流或相关订单意图下调用。每次调用经过 Schema 校验、RBAC、超时控制和审计记录，并返回是否允许、状态、耗时、Mock 标记和错误信息。

所有这些 Tool 当前均是本地 Mock Adapter。不得说成已经接入真实 CRM、OMS、工单系统，或能够执行真实退款、改订单、写 CRM 等操作。

## 10. MCP

当前 **MCP 数量为 0**。系统没有 MCP Client、MCP Server、MCP Tool、MCP Resource 或 MCP Prompt 集成。

当前使用本地 ToolRegistry 管理业务工具。未来如对接真实外部系统，可评估 MCP，但在实现前不得声称项目采用了 MCP。

## 11. TaskState 与任务规划

当前没有独立 `TaskState`。LangGraph 使用单一 `AgentState` 传递工单输入、分类结果、工具上下文、citation、回复草稿、QA、升级结论、token、成本和错误信息。

当前也没有独立 Planner 或动态任务分解。系统采用固定 Workflow，并根据安全结果、部门、意图和优先级做有限的规则路由。当前唯一的受限重新规划是：类别检索无结果时，保留知识库版本并放宽类别进行一次回退检索。

不得表述为：系统具备动态 Planner、子任务拆分、自动 Plan Revision、任务队列或自主多 Agent 协商。

## 12. Memory

系统保存会话历史，但当前不具备“将完整多轮历史注入本次 Agent 推理”的能力。

| 层次 | 当前事实 |
|---|---|
| SQL `SessionMemory` | 保存持久化会话消息，是 Redis 不可用时的兜底 |
| Redis | 可选短期缓存，保存最近 12 条消息，TTL 为 24 小时 |
| 当前业务使用 | 聊天流程会读取和写入历史消息 |
| 当前限制 | 历史尚未注入 Analyzer 或 Resolver 的推理上下文 |

可以说“实现会话历史存储与 Redis 降级”；不能说“已实现基于多轮历史的 Agent 推理”或“已实现长期记忆”。

## 13. Prompt

当前 Prompt 分散维护在 LLM Provider 中，没有独立 Prompt Registry、Prompt 版本号、灰度发布或 A/B 实验。

| Prompt 阶段 | 当前约束 |
|---|---|
| Analyzer | 以脱敏后的工单进行分类，要求结构化 JSON 输出 |
| Resolver | 只应依据 Knowledge Base Context 和 Structured Tool Context 生成回复；上下文不足时应升级 |
| QA | 根据问题、citation 和草稿输出 QA 分数、幻觉判断及相关质量字段 |
| 输出过滤 | 删除可能泄露内部角色、指令或工作流的内容 |

OpenAI 与 Azure OpenAI Provider 使用 `temperature=0.0`；默认 Mock Provider 用于离线可复现。不能说 Prompt 已版本化、已灰度或已通过线上实验优化。

## 14. 数据库

系统使用 SQLAlchemy Async 访问数据库。

| 环境 | 数据库 | 用途 |
|---|---|---|
| 本地默认 | SQLite | 降低启动门槛，支持无额外服务运行 |
| Docker Compose | PostgreSQL | 提供更接近生产的并发与连接池环境 |

持久化实体包括用户、工单、会话记忆、知识文档和回复审批记录。当前没有数据库迁移工具、读写分离、分库分表、`ticket_status_events` 审计表或多租户数据隔离。

## 15. Redis

Redis 是可选组件，不是系统启动或处理工单的强依赖。

- Redis 配置可用时，保存会话最近 12 条消息，TTL 为 24 小时。
- Redis 未配置、连接失败、读取失败或保存失败时，主流程继续运行，历史读取回退到 SQL。
- Docker Compose 会启动 Redis；本地默认配置不要求 Redis。

不能说 Redis 是唯一记忆存储、必须依赖 Redis，或 Redis 当前承担分布式锁、队列、Checkpoint、限流等职责。

## 16. Embedding

系统通过 Embedding Provider 生成知识库分块和查询向量。

| Provider 模式 | 当前 Embedding 事实 |
|---|---|
| 默认 Mock 模式 | 使用稳定的 1536 维 Mock 向量，保证本地可复现 |
| OpenAI 或 Azure 模式 | 使用 OpenAI `text-embedding-3-small` |

当前不使用本地训练 Embedding 模型、向量微调、Embedding A/B 评测或多向量检索。

## 17. RAG

当前 RAG 为 ChromaDB 上的 Hybrid RAG：

1. 知识文档被解析、切分并写入 ChromaDB，同时保留知识库版本和类别 metadata。
2. 检索时使用工单主题与描述构造查询，必须限定 `kb_version`。
3. 系统优先按业务类别过滤；没有结果时，保留版本并放宽类别再查询一次。
4. 系统融合向量召回、进程内 BM25 风格关键词打分和轻量 rerank。
5. 最终返回最多 3 条 citation，每条包含来源、文本、分数和版本。

当前默认分块参数为 600 字符、120 字符 overlap。ChromaDB 是当前向量数据库；系统没有使用 pgvector、OpenSearch、Elasticsearch、Milvus、Pinecone、Cross-encoder 或 LLM Reranker。

可以说“实现 Hybrid RAG、版本/类别过滤、citation 与轻量 rerank”；不能说“已实现生产级搜索集群、多租户 RAG 隔离或训练型 Reranker”。

## 18. 评测体系

项目包含两层质量评估：

| 层次 | 当前事实 |
|---|---|
| 在线 QA | 每次正常草稿生成后评估 QA 分数、幻觉风险和输出泄露；低分或幻觉触发审批 |
| 离线评测 | 提供 RAGAS、DeepEval 和本地启发式指标的统一适配入口 |
| 评测指标 | Faithfulness、Context Precision、Context Recall、Answer Relevance、Hallucination Rate、综合质量分数 |
| 当前通过阈值 | 综合质量分数 `>= 0.75` 且 Hallucination Rate `< 0.35` |
| 报告 | 尝试生成 JSON 评测报告 |

当前没有 30–50 条 Golden Set、人工标注的标准答案、citation hit rate 回归报告、稳定质量基线或真实线上评测数据。无 API Key 时的本地评测是确定性启发式降级，不能等同于真实 LLM-as-Judge 结果。

## 19. 性能指标

### 当前已采集的指标

系统通过 Prometheus 采集：

- HTTP 请求数量和请求延迟。
- Agent 节点执行耗时。
- LLM 输入/输出 token、估算成本与部分 LLM 延迟。
- QA 分数分布。
- 情绪分类计数、Guardrail 违规计数和工单升级计数。

OpenTelemetry Span 覆盖 HTTP 请求、Agent Workflow、各 Agent 节点、工具调用、RAG 查询与回退、审批创建和审批处理。

### 当前没有的性能数据

没有可长期引用的 P50、P95、P99 延迟，QPS、并发上限、吞吐量、RAG Recall、工具成功率、缓存命中率或成本预算实测数据。

历史文档中出现过单次 Mock Workflow 的本地示例延迟；该值受机器、数据、Provider 和运行环境影响，不是基准测试结果，不得作为性能指标对外引用。

## 20. 上线指标

当前**没有上线指标**，原因是项目没有已证实的真实生产部署、真实客户流量、真实 SLA、真实工单量、真实审批率或真实业务转化数据。

不得声称：

- 已上线到真实客服中心。
- 已服务真实客户或处理真实订单。
- 提升了首问解决率、客服效率、满意度或人工成本。
- 达到某个真实 SLA、可用性或业务增长指标。

可以说：Docker Compose 和 Kubernetes manifests 提供了本地或生产风格部署基础，但不代表已生产发布。

## 21. 已知问题与解决方案

| 已知问题 | 当前事实 | 当前解决方案 | 不应夸大的内容 |
|---|---|---|---|
| Python 3.13 下 pytest 崩溃 | 当前本机环境可能因 native dependency / plugin 问题以 `exit code 139` 退出 | 推荐 Python 3.11；CI 使用 Python 3.11；可运行编译检查和定向测试 | 不要把该问题解释为业务断言失败或已完全根治 |
| Redis 不可用 | Redis 是可选组件 | 自动回退 SQL 历史 | 不要说 Redis 已高可用或具备集群容灾 |
| 类别检索无结果 | 分类可能不完全匹配知识类别 | 保留版本，放宽类别回退一次 | 不要说已实现通用检索重试或生产级召回保证 |
| 工具、LLM 或 QA 异常 | 外部能力或 Provider 可能失败 | 记录错误、使用安全降级、触发人工审批 | 不要说已实现 Circuit Breaker、消息队列或通用 Retry |
| 会话历史未进入推理 | 历史当前只保存和读取 | 将其作为后续改造项 | 不要说系统已经具备多轮上下文推理 |
| 工具审计不持久化 | 审计记录当前驻留进程内并可随响应返回 | 作为后续审计表改造项 | 不要说已有完整合规审计平台 |
| Trace 仅控制台输出 | 已有 Span，但默认是 Console Exporter | 后续接 OTLP / Jaeger / Tempo | 不要说已有集中式 APM 或全链路生产追踪 |

## 22. 未来规划

以下均为规划，尚未实现：

1. 构建 30–50 条 Synthetic Customer Support Golden Set，输出 citation hit rate、Faithfulness、Answer Relevance 和 Hallucination Risk 的稳定 JSON / Markdown 报告。
2. 为知识文档与检索 metadata 增加 `tenant_id`，强制 `tenant_id + kb_version` 过滤，实现多租户隔离测试。
3. 抽象 `SearchBackend`，保留 Chroma 本地方案并设计 OpenSearch Hybrid Search 方案。
4. 增加 `ticket_status_events` 和持久化 Tool Calling 审计记录。
5. 完成客服工作台，展示工单、AI 草稿、Tool Context、citation、QA、风险原因与审批动作。
6. 将 Prompt 版本化，并在 Golden Set 基础上记录版本、审批率、QA、延迟和 token 成本。
7. 将 OpenTelemetry 从 Console Exporter 演进至 OTLP，并接入 Jaeger、Tempo 或云 APM。
8. 将会话历史按受控方式注入 Agent 推理上下文，并补充隐私、长度控制和回归测试。

## 23. 长期一致性规则

未来任何回答都必须遵守以下规则：

1. 已实现、部分实现、规划中和未知信息必须明确区分。
2. 所有 CRM、OMS、Ticketing、退款初筛和默认 LLM 均为 Mock，除非代码与凭据明确变为真实集成。
3. Agent 数量固定表述为 6 个逻辑节点；Tool 数量固定表述为 4 个注册 Tool，直至代码发生变化。
4. MCP 数量为 0；独立 TaskState、Checkpoint、动态 Planner、自动 Reflection 和 pgvector 均未采用，直至代码发生变化。
5. Redis 是可选短期缓存，SQL 是持久化兜底；会话历史尚未注入 Agent 推理。
6. ChromaDB 是当前向量数据库；Hybrid RAG 是当前检索方案。
7. 项目没有真实生产上线数据、线上 KPI 或真实客户业务数据。
8. 团队人数和个人贡献归属没有仓库事实依据，必须由回答者的真实经历补充，不能推测。
9. 本文中的计数、阈值、组件和边界发生变化时，必须在同一提交中更新本文。
