# SupportGPT Enterprise 技术决策记录

> 本文记录项目已经确认的重要技术决策。每项决策均以当前代码与部署配置为准；“暂不采用”不代表永久否定，而是当前阶段的明确边界。

## 决策 1：采用 FastAPI 作为服务入口

### 问题背景

系统需要提供聊天、工单、审批、鉴权、评测和监控接口，并同时处理数据库、Redis、LLM、RAG 等 I/O。

### 候选方案

- FastAPI
- Flask
- Django / Django REST Framework

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| FastAPI | 原生异步、Pydantic Schema、自动 OpenAPI 文档、依赖注入完善 | 复杂后台管理能力不如 Django 完整 |
| Flask | 简单、生态成熟 | 异步与 Schema 需额外组合 |
| Django | ORM、Admin、权限生态完善 | 对当前轻量异步 Agent 服务偏重 |

### 最终方案

采用 FastAPI。

### 为什么选择

Agent 工作流涉及异步数据库访问、可选 Redis、外部 LLM 和检索调用。FastAPI 能以较少框架胶水代码提供异步接口、输入输出校验和 Swagger 文档。

### 工程权衡

选择 FastAPI 降低了 API 层复杂度，但后台运营管理界面和更复杂的企业权限能力需要额外开发，而不是从框架中直接获得。

## 决策 2：采用 LangGraph 编排 Agent Workflow

### 问题背景

客服请求必须依次经过安全检测、业务上下文补全、知识检索、回复生成、质量检查和升级决策，并需要明确的安全短路路径。

### 候选方案

- LangGraph 固定状态图
- 普通 LLM Chain
- ReAct 自主循环
- 自建状态机

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| LangGraph | 节点与条件边显式、便于 Trace、适合状态传递 | 需要维护共享 State 和图定义 |
| 普通 Chain | 开发快 | 条件路由、审计和失败定位不清晰 |
| ReAct | 灵活，可由模型选择步骤 | 工具调用与循环风险高，难以保证 QA 不被绕过 |
| 自建状态机 | 完全可控 | 需要自行实现图执行、状态合并和可视化能力 |

### 最终方案

采用 LangGraph 固定六节点 Workflow。

### 为什么选择

售后流程阶段稳定，安全与审批不可绕过。LangGraph 既比普通 Chain 更适合表达条件路由，也比自由 ReAct 更可控。

### 工程权衡

固定图限制了对开放式复杂任务的自适应能力，但换来稳定、可测试、可审计的执行路径。

## 决策 3：采用逻辑 Multi-Agent 分工，而非自治多智能体协商

### 问题背景

单一 Prompt 同时承担分类、检索、工具、生成和审查职责时，难以定位错误来源，也容易让模型跳过治理环节。

### 候选方案

- 逻辑 Multi-Agent：Analyzer、Tooling、Retriever、Resolver、QA、Escalation
- 单 Agent 大 Prompt
- 多个自治 Agent 互相协商

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 逻辑 Multi-Agent | 职责边界清晰、节点可观测、易于测试 | 有状态传递和节点编排成本 |
| 单 Agent | 链路短、实现简单 | 可解释性差，难以独立治理安全和 QA |
| 自治协商 | 适合开放式复杂研究任务 | 调试困难、成本高、结果不稳定 |

### 最终方案

采用固定职责的逻辑 Multi-Agent Workflow。

### 为什么选择

这里的 Multi-Agent 是工程分层，不是多个模型自由对话。客服业务更需要可预测的职责链，而不是开放式协商。

### 工程权衡

节点边界使系统更清晰，但也导致部分上下文需要在共享 `AgentState` 中显式传递。

## 决策 4：使用单一 AgentState，不引入独立 TaskState

### 问题背景

系统需要在节点间传递工单、分类、工具、检索、生成、质量和升级信息。

### 候选方案

- 单一 `AgentState`
- `TaskState + ExecutionState` 双状态模型
- 事件流与事件溯源

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| AgentState | 轻量、与当前固定图匹配、节点输入输出直观 | 长流程下状态会膨胀 |
| TaskState + ExecutionState | 适合子任务、动态计划和恢复 | 需要状态迁移、版本与持久化设计 |
| 事件流 | 可追溯性强 | 基础设施和领域建模复杂度高 |

### 最终方案

当前只使用 `AgentState`，没有独立 `TaskState`。

### 为什么选择

当前工作流短且线性，没有动态子任务、异步长任务或中断恢复需求。

### 工程权衡

方案简单但不适合未来复杂 Planner。若引入长时调查任务，应再拆分 TaskState，而不是直接扩张现有 State。

## 决策 5：不引入独立 Planner，使用固定流程与规则路由

### 问题背景

用户要求可能涉及退款、物流、保修或安全风险，系统需要决定后续处理步骤。

### 候选方案

- 固定 Workflow + Analyzer 分类 + 规则路由
- LLM Planner 生成动态计划
- 人工预配置流程模板

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 固定流程 | 可预测、易审计、不会跳过关卡 | 灵活性有限 |
| LLM Planner | 可处理更多开放式任务 | 计划幻觉、循环、难以验证和恢复 |
| 流程模板 | 业务可配置 | 模板维护成本高，覆盖有限 |

### 最终方案

采用固定流程与分类驱动的轻量规划，不引入独立 Planner。

### 为什么选择

客服处理路径稳定，高风险节点必须固定存在。动态计划的收益不足以覆盖其治理成本。

### 工程权衡

当前只能进行有限的 RAG 类别回退，不能自主重新规划。人工拒绝草稿后由人工重新处理，而不是让模型无限重试。

## 决策 6：不引入独立 Selector，使用确定性选择规则

### 问题背景

系统需要选择安全分支、订单工具、RAG 类别过滤和升级动作。

### 候选方案

- 确定性条件规则
- LLM Selector / Router
- 学习型策略模型

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 确定性规则 | 可解释、可测试、权限风险低 | 覆盖范围受规则限制 |
| LLM Selector | 适应表达变化 | 可能误选高风险工具或错误路径 |
| 学习型模型 | 可根据数据优化 | 需要标注数据、线上反馈和治理机制 |

### 最终方案

采用确定性规则，不设置独立 Selector Agent。

### 为什么选择

工具选择、类别过滤和升级动作直接影响风险与成本，当前应优先保证可审计性。

### 工程权衡

新增业务类型时要扩展规则；未来场景增多后可增加受限 Selector，但不可绕过 Guardrails、RBAC 和状态机。

## 决策 7：采用 Tool Calling 与 ToolRegistry

### 问题背景

回复需要客户等级、订单状态和历史处理结果等结构化业务事实，同时必须防止越权调用和错误参数。

### 候选方案

- ToolRegistry 统一治理
- Agent 直接调用 Adapter
- LLM Function Calling 直接执行
- API 层预取全部上下文

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| ToolRegistry | Schema、RBAC、超时、Mock 标记和审计集中 | 需要维护工具定义 |
| 直接调用 Adapter | 代码少 | 容易绕过权限和审计 |
| LLM Function Calling | 模型可动态选择工具 | 需要额外的调用验证和副作用控制 |
| API 预取 | Agent 逻辑简单 | 可能读取不必要数据，缺少按意图治理 |

### 最终方案

采用 ToolRegistry，所有业务工具必须经由统一入口调用。

### 为什么选择

统一入口能把参数校验、角色权限、超时和审计做成系统约束，而不是依赖每个 Agent 自觉实现。

### 工程权衡

当前 Registry 审计仍在进程内，尚未持久化；工具是本地 Mock Adapter，不能被表述为真实企业系统集成。

## 决策 8：暂不采用 MCP

### 问题背景

MCP 可以为外部工具、资源和 Prompt 提供标准化连接协议，但项目当前需要先完成本地客服闭环。

### 候选方案

- 本地 ToolRegistry + Adapter
- MCP Client + MCP Server
- 直接 REST / gRPC Client

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| ToolRegistry | 本地可复现、依赖少、治理逻辑集中 | 跨宿主工具发现与复用能力有限 |
| MCP | 协议标准化，适合跨应用工具集成 | 需要处理连接、鉴权、资源治理、协议版本和审计边界 |
| 直接 Client | 对接真实服务直接 | 每个服务的权限和异常逻辑容易分散 |

### 最终方案

当前不集成 MCP，使用 ToolRegistry + Mock Adapter。

### 为什么选择

项目没有需要接入的真实外部 MCP Server；先验证工具治理模型比提前引入协议基础设施更重要。

### 工程权衡

未来可将真实 CRM、OMS 或工单服务封装成 MCP Server，但 MCP 调用仍需经过权限、参数、超时和审计治理，不能成为绕过 ToolRegistry 的通道。

## 决策 9：默认采用 Mock LLM，Provider 支持 OpenAI 与 Azure OpenAI

### 问题背景

项目需在无 API Key、无网络和测试环境下稳定运行，同时保留接入真实模型的能力。

### 候选方案

- 默认 Mock LLM + Provider 抽象
- 默认强依赖 OpenAI
- 仅使用本地开源模型

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| Mock + Provider | 可复现、低成本、测试稳定、可切换外部模型 | Mock 质量不代表真实模型表现 |
| 强依赖 OpenAI | 真实生成能力强 | 密钥、成本、网络和测试不稳定 |
| 本地模型 | 数据不出本地 | 部署和推理资源成本高 |

### 最终方案

默认 `LLM_PROVIDER=mock`，通过统一 Provider 接口支持 OpenAI 与 Azure OpenAI。

### 为什么选择

本项目是本地可演示的工程项目，默认可复现优先于默认模型能力。

### 工程权衡

任何基于 Mock 的质量指标都不能当作生产结果；真实模型接入后需重新评估 Prompt、成本、延迟与 QA 阈值。

## 决策 10：采用输入 Guardrails 与输出 Guardrails

### 问题背景

客服输入可能包含 PII、Prompt Injection 和 Jailbreak，生成输出也可能泄露内部指令或工作流信息。

### 候选方案

- 输入安全检测 + PII 脱敏 + 输出过滤
- 只依赖 System Prompt
- 仅人工审核
- 专用安全网关服务

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 双侧 Guardrails | 前后两道防线，可提前短路 | 规则覆盖有限，需维护 |
| 只靠 Prompt | 实现最少 | 对攻击和提示泄露不可靠 |
| 仅人工审核 | 安全高 | 成本和响应延迟高 |
| 安全网关 | 可集中治理 | 引入额外服务和集成复杂度 |

### 最终方案

采用 Prompt Injection、Jailbreak、PII 脱敏和 Response Filter 的分层 Guardrails。

### 为什么选择

输入风险应在调用工具与模型前被拦截；输出风险需要在回复客户前再检查。双侧措施适合当前本地可运行架构。

### 工程权衡

当前检测以轻量规则为主，不能视为完整安全产品；高风险命中采取人工升级而不是尝试自动绕过或重写。

## 决策 11：采用 ChromaDB 作为当前向量数据库，不采用 pgvector

### 问题背景

系统需要保存知识库分块、Embedding 和 metadata，并支持本地开发与类别、版本过滤。

### 候选方案

- ChromaDB
- PostgreSQL + pgvector
- OpenSearch / Elasticsearch
- Milvus / Pinecone

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| ChromaDB | 本地集成简单、持久化目录、开发门槛低 | 大规模检索、运维和混合搜索能力有限 |
| pgvector | 与 PostgreSQL 事务和元数据统一 | 需要扩展配置与索引调优，词法检索仍需额外设计 |
| OpenSearch | 强大的 BM25、过滤与生产搜索能力 | 部署、索引和运维成本较高 |
| Milvus / Pinecone | 专业向量检索能力 | 引入外部服务或托管依赖 |

### 最终方案

当前采用 ChromaDB，未采用 pgvector。

### 为什么选择

ChromaDB 满足本地 Demo、版本过滤、向量召回和持久化的需求，能够在不启动额外数据库扩展的前提下跑通 RAG。

### 工程权衡

选择 ChromaDB 意味着向量数据与业务 SQL 数据分开管理；未来若需更高并发、统一存储或生产检索，可评估 pgvector 或 OpenSearch，但不能声称当前已使用 pgvector。

## 决策 12：采用 Hybrid RAG，而非纯向量检索

### 问题背景

客服政策常包含退款窗口、产品型号、订单词、政策编号等精确词，纯向量检索容易遗漏这些信号。

### 候选方案

- Chroma 向量召回 + BM25 风格词法召回 + 轻量 rerank
- 纯向量检索
- 纯 BM25
- Cross-encoder / LLM Reranker

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| Hybrid RAG | 同时兼顾语义相似与精确匹配 | 需要合并候选和维护评分逻辑 |
| 纯向量 | 架构简单，适合语义表达 | 精确政策词召回不稳定 |
| 纯 BM25 | 精确词强、成本低 | 对同义表达和自然语言变体较弱 |
| Cross-encoder / LLM Reranker | 排序质量潜力高 | 延迟、成本和依赖更高 |

### 最终方案

采用向量召回、进程内 BM25 风格打分和轻量 rerank 的 Hybrid RAG。

### 为什么选择

该方案以较低复杂度解决客服精确规则问题，同时保留向量检索对自然语言表达的鲁棒性。

### 工程权衡

进程内词法搜索适合 Demo 和小规模知识库，不适合大规模索引。未来需抽象 SearchBackend 并考虑 OpenSearch 或训练型 Reranker。

## 决策 13：采用知识库版本与类别过滤，并设置类别回退

### 问题背景

售后政策会迭代，且不同业务部门的知识不应无差别混入回复上下文。

### 候选方案

- `kb_version` + `category` metadata filter，空结果时放宽类别
- 无过滤全库检索
- 仅版本过滤
- 固定业务知识库分库

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 版本 + 类别 + 回退 | 兼顾精度、灰度和召回兜底 | 分类错误时会多一次查询 |
| 全库检索 | 实现简单，召回高 | 容易引入不相关或过期政策 |
| 仅版本 | 控制版本 | 部门噪声较大 |
| 分库 | 隔离清晰 | 运维和跨域查询复杂 |

### 最终方案

先按知识库版本与部门类别过滤，类别为空时保留版本并放宽类别重试一次。

### 为什么选择

版本保证政策可回滚，类别提高相关性；单次回退防止分类误差导致零召回。

### 工程权衡

当前不支持 `tenant_id` 多租户隔离；版本与类别不是完整的数据权限方案。

## 决策 14：采用 SQLAlchemy Async，SQLite 本地默认、PostgreSQL 容器化部署

### 问题背景

系统需要保存工单、用户、会话、知识文档和审批记录，同时兼顾本地启动和生产风格部署。

### 候选方案

- SQLAlchemy Async + SQLite / PostgreSQL
- 仅 SQLite
- 仅 PostgreSQL
- NoSQL 数据库

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| SQLite + PostgreSQL | 本地门槛低，部署时具备事务与并发能力 | 需要兼容两种数据库行为 |
| 仅 SQLite | 零运维 | 并发、锁与生产能力有限 |
| 仅 PostgreSQL | 环境一致性高 | 本地 Demo 必须启动数据库服务 |
| NoSQL | Schema 灵活 | 工单状态与审批事务约束实现成本更高 |

### 最终方案

本地默认 SQLite，Docker Compose 使用 PostgreSQL，访问层统一使用 SQLAlchemy Async。

### 为什么选择

该方案平衡了本地可复现与生产风格架构；PostgreSQL 提供更合理的连接池和并发事务能力。

### 工程权衡

当前没有数据库迁移工具、读写分离、审计事件表或多租户数据隔离。

## 决策 15：Redis 作为可选短期记忆，SQL 作为持久化兜底

### 问题背景

会话需要保存最近消息，但本地 Demo 不能因 Redis 未部署而不可用。

### 候选方案

- Redis 短期缓存 + SQL 持久化历史
- 仅 Redis
- 仅 SQL
- 向量长期记忆

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| Redis + SQL | 热数据读取快，缓存故障可回退 | 两层数据可能出现短暂不一致 |
| 仅 Redis | 延迟低 | Redis 故障或过期会丢失历史 |
| 仅 SQL | 简单、耐久 | 热会话读取延迟更高 |
| 向量记忆 | 可做语义长期召回 | 需要额外检索、隐私与摘要治理 |

### 最终方案

Redis 保存最近 12 条消息并设置 24 小时 TTL；SQL `SessionMemory` 保存持久化历史；Redis 不可用时自动使用 SQL。

### 为什么选择

缓存不能成为客服主链路的强依赖，SQL 兜底满足可用性和本地运行要求。

### 工程权衡

当前会话历史尚未注入 Agent Prompt，因此这是存储与回退能力，不是完整的多轮推理记忆。

## 决策 16：暂不引入 Checkpoint

### 问题背景

LangGraph Checkpoint 可以保存执行中状态，用于长流程恢复、中断后继续和人工暂停。

### 候选方案

- 无 Checkpoint，单请求内执行完 Workflow
- Redis Checkpoint
- PostgreSQL Checkpoint
- 专用工作流引擎

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 无 Checkpoint | 链路简单、无状态迁移负担 | 请求中断后不能恢复 Graph |
| Redis Checkpoint | 访问快 | 耐久性和清理策略需额外设计 |
| PostgreSQL Checkpoint | 可持久恢复、审计性好 | 状态版本、幂等和迁移复杂 |
| 工作流引擎 | 支持长事务与重试 | 基础设施与学习成本高 |

### 最终方案

当前不采用 Checkpoint。

### 为什么选择

当前流程短、同步完成，人工审批通过领域记录而不是恢复同一 Graph 来处理。

### 工程权衡

系统失去长任务恢复能力；未来若有异步调查、人工中断后继续或跨服务编排，再评估持久化 Checkpoint。

## 决策 17：采用 Review Agent 与 Response Filter，不采用自动 Reflection Loop

### 问题背景

生成回复可能缺乏依据、产生幻觉或泄露内部信息，需要独立检查。

### 候选方案

- QA Review Agent + Response Filter + 人工升级
- Resolver 自检
- 自动 Reflection 后重写
- 人工全量审核

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 独立 Review | 生成与审查分离，结果可观测 | 增加一次模型调用或规则处理 |
| 自检 | 链路短 | 同一模型容易放过自身错误 |
| Reflection Loop | 有机会改善低质量表达 | 容易循环、增加成本，可能反复生成错误事实 |
| 全量人工 | 风险最低 | 效率低，无法体现自动化价值 |

### 最终方案

采用 QA Review Agent 与 Response Filter；低分或幻觉进入 Human-in-the-Loop，不采用自动 Reflection Loop。

### 为什么选择

在客服政策与退款等场景中，遇到质量风险时优先人工接管比让模型反复自改更可靠。

### 工程权衡

自动化覆盖率低于自动重写方案，但风险、成本和行为不确定性更可控。

## 决策 18：采用风险驱动 Human-in-the-Loop 与工单状态机

### 问题背景

高风险回复不能仅由模型决定，且 AI 草稿需要和真实工单生命周期一致。

### 候选方案

- 风险驱动审批 + 显式状态机
- 所有回复自动发送
- 所有回复人工审核
- 直接修改工单状态字段

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 风险审批 + 状态机 | 平衡效率与安全，阻止非法流转 | 需要审批队列和状态规则 |
| 全自动 | 延迟低 | 退款、安全和低置信度风险高 |
| 全量人工 | 风险低 | 人力成本与处理延迟高 |
| 直接改状态 | 实现简单 | 容易产生审批前关闭等非法状态 |

### 最终方案

安全违规、紧急工单、负面且高优先级、低 QA 或幻觉风险触发审批；工单状态只能沿合法状态机流转。

### 为什么选择

该方案让自动化优先处理低风险问题，同时保留高风险场景的人类最终裁决权。

### 工程权衡

审批阈值目前固定，未基于真实运营数据动态优化；状态事件尚未单独持久化。

## 决策 19：采用受限 Error Recovery，而非通用自动 Retry

### 问题背景

网络、检索、工具和模型可能失败，但客服和高风险动作不能发生无限重试或重复副作用。

### 候选方案

- 单次 RAG 回退 + 保守降级 + 人工接管
- 通用自动 Retry
- Circuit Breaker + Queue + Dead Letter Queue
- 失败即终止

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| 受限恢复 | 行为可预测，避免重复副作用 | 自动恢复能力有限 |
| 通用 Retry | 对瞬态故障友好 | 可能重复调用工具或反复消耗 LLM 成本 |
| 完整韧性体系 | 适合生产外部依赖 | 引入幂等、队列和运维复杂度 |
| 失败即终止 | 实现最简单 | 客户体验和可用性差 |

### 最终方案

类别过滤无结果时仅进行一次 RAG 回退；Redis 失败回退 SQL；工具和模型失败采用安全降级或人工升级，不做通用自动 Retry。

### 为什么选择

当前工具以读操作和 Mock 为主，系统优先避免不可见的重复行为。

### 工程权衡

对短暂外部服务故障的自动恢复能力有限。未来加入 Retry 时必须同时加入幂等键、次数上限、退避、审计和高风险禁重试规则。

## 决策 20：采用 Prometheus + OpenTelemetry 双层可观测

### 问题背景

需要既能了解整体延迟、成本和风险趋势，也能定位单次请求在 Agent、工具、RAG 或审批环节的耗时。

### 候选方案

- Prometheus Metrics + OpenTelemetry Trace
- 仅日志
- 仅 Prometheus
- 仅 Trace

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| Metrics + Trace | 趋势分析与单请求诊断互补 | 需要维护两类观测数据 |
| 仅日志 | 简单 | 聚合、告警和链路关联困难 |
| 仅 Metrics | 适合趋势 | 无法定位单次调用路径 |
| 仅 Trace | 适合排障 | 不擅长长期聚合和告警 |

### 最终方案

采用 OpenTelemetry 统一采集请求、节点、token、成本、QA、Guardrail 等 Metrics，并串联 API、Workflow、LLM、工具、RAG 和审批 Span；通过 OTLP Collector 分别转发 LangSmith 与 Prometheus。

### 为什么选择

Agent 系统既需要运营指标，也需要排查“哪一步慢、哪一步失败”的请求级证据。

### 工程权衡

统一 Collector 降低应用侧多套 SDK 的维护和脱敏成本，但 Collector 成为需要监控与容量规划的基础设施；工具审计仍尚未持久化。

## 决策 21：采用 Docker Compose、分层依赖和 Python 3.11 CI

### 问题背景

项目要同时支持本地 Demo、测试、评测、负载依赖和容器化验证。

### 候选方案

- Docker Compose + requirements 分层 + Python 3.11 CI
- 单一 requirements 文件 + 本机运行
- 完整 Kubernetes 优先部署

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| Compose + 分层依赖 | 本地组件可复现，运行时依赖更轻 | 维护多个依赖文件 |
| 单文件依赖 | 简单 | 测试、评测依赖污染运行环境 |
| Kubernetes 优先 | 接近生产 | 对当前项目的部署与调试门槛过高 |

### 最终方案

采用 Docker Compose 编排 backend、PostgreSQL、Redis 和 Prometheus；依赖分为 runtime、test、eval、load；CI 固定 Python 3.11 Smoke Test。

### 为什么选择

该方案能保证主要路径可复现，也规避本机 Python 3.13 下部分 native dependency / pytest 插件崩溃问题。

### 工程权衡

Kubernetes manifests 已存在，但不代表完成生产发布；CI 目前是定向 Smoke Test，尚非完整测试矩阵。

## 决策 22：暂不引入 Prompt Registry、灰度与 A/B 实验

### 问题背景

Analyzer、Resolver 与 QA 都依赖 Prompt，后续需要可追踪地比较 Prompt 变更效果。

### 候选方案

- Provider 内维护 Prompt
- Prompt Registry + 版本化
- 配置中心 + A/B 灰度

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| Provider 内维护 | 简单、当前修改路径短 | 版本和效果难以独立归因 |
| Prompt Registry | 可记录版本与元数据 | 需要存储、发布和回滚机制 |
| A/B 灰度 | 可基于指标优化 | 需要 Golden Set、流量和统计设计 |

### 最终方案

当前 Prompt 直接维护在 Provider 中，不采用 Prompt Registry、灰度或 A/B。

### 为什么选择

在缺少 Golden Set、稳定回归指标和真实流量时，引入灰度体系无法产生可靠结论。

### 工程权衡

Prompt 修改的可追溯性有限。建立 Golden Set 和离线评测报告后，应优先引入版本管理再做灰度。

## 决策 23：采用 RAGAS / DeepEval Adapter 与本地评测降级

### 问题背景

RAG 质量不能只依靠主观体验，需要评估 Faithfulness、Context Precision / Recall、Answer Relevance 和 Hallucination 风险。

### 候选方案

- RAGAS / DeepEval Adapter + 本地启发式降级
- 强依赖云端 LLM Judge
- 仅人工抽查
- 暂不做评测

### 优点与缺点

| 方案 | 优点 | 缺点 |
|---|---|---|
| Adapter + 本地降级 | 无 API Key 也能跑通评测管道 | 本地指标不等价于真实 LLM Judge |
| 强依赖云端 Judge | 指标能力完整 | 成本、密钥与网络依赖高 |
| 人工抽查 | 贴近业务 | 难以自动化回归 |
| 不评测 | 开发快 | 无法量化质量变化 |

### 最终方案

采用 RAGAS / DeepEval Adapter，并在无可用 API Key 时回退到本地确定性指标。

### 为什么选择

项目需要同时具备离线可运行性和后续接入真实评测框架的能力。

### 工程权衡

当前尚无人工标注 Golden Set，RAGAS 的简化 Ground Truth 也不是标准答案。因此不可宣称已有生产级评测结果。

## 决策总览

| 领域 | 最终决策 | 当前边界 |
|---|---|---|
| Agent 编排 | LangGraph 固定六节点图 | 无动态 Planner / 自治协商 |
| 状态 | 单一 AgentState | 无 TaskState / Checkpoint |
| 工具 | ToolRegistry + Mock Adapter | 无 MCP、审计未持久化 |
| 模型 | Mock 默认，OpenAI / Azure 可选 | 无真实生产模型效果承诺 |
| 安全 | 输入 Guardrails + 输出 Filter + QA | 规则覆盖需持续维护 |
| RAG | ChromaDB Hybrid RAG | 无 pgvector、无生产搜索后端 |
| 数据 | SQLite 本地、PostgreSQL Compose | 无迁移、读写分离、多租户 |
| 记忆 | Redis 可选 + SQL 兜底 | 历史未注入生成 Prompt |
| 审批 | 风险驱动 HITL + 状态机 | 阈值固定、状态事件未持久化 |
| 恢复 | 受限回退、人工接管 | 无通用 Retry / Queue / Circuit Breaker |
| 观测 | OpenTelemetry + OTLP Collector + LangSmith / Prometheus | Collector 尚未高可用，未接 Jaeger / Tempo |
| 评测 | Adapter + 本地降级 | 无 Golden Set 和生产基线 |
