# 简历加分改造路线图

本文只规划后续可以增强简历竞争力的方向，不代表当前代码已经全部实现。写简历时需要区分“已实现”“可 mock 演示”“后续规划”。

## 优先级总览

| 优先级 | 改造方向 | 简历加分点 | 代码工作量 | 是否可 mock |
|---|---|---|---|---|
| P0 | 真实工具调用协议与权限控制 | Tool Calling / Function Calling 工程化 | 中 | 可以 |
| P0 | RAG 评估集与离线评测报告 | 可量化质量指标 | 中 | 可以 |
| 已完成 | 工单闭环状态机 | 业务闭环能力 | 中 | 可以 |
| 已完成 | OpenTelemetry Trace 串联链路 | 可观测性与排障能力 | 中 | 部分可以 |
| P1 | 多租户知识库隔离 | 企业级 SaaS 架构感 | 中 | 可以 |
| P1 | 生产级检索后端方案 | 搜索与 RAG 深度 | 中高 | 可以先文档化 |
| P2 | 客服工作台前端 | Demo 展示能力 | 中高 | 可以 |
| P2 | A/B Prompt 与版本灰度 | 模型应用运营能力 | 中 | 可以 |

## P0：工具调用协议与权限控制

### 为什么加分

当前项目已经有 CRM、订单和历史工单工具，但更像工具适配器。下一步可以将它升级成明确的 tool calling 协议，体现“Agent 可以按权限调用业务能力”。

### 建议改造

- 为每个工具定义 `name`、`description`、`input_schema`、`output_schema`。
- 增加工具权限配置，例如 `agent` 只能查订单，`manager` 才能审批退款。
- 增加工具调用超时、重试、失败降级和审计日志。
- 在 API 返回中暴露 `tool_calls`，记录工具名、耗时、状态和 mock 标记。

### 简历可写法

> 设计客服 Agent 工具调用协议，为 CRM、订单和工单工具增加 schema、权限校验、超时重试和调用审计，使业务工具可被 Agent 安全编排。

### 可 mock 细节

- CRM / OMS / Ticketing 仍可继续使用本地 mock 数据。
- 权限、超时和审计可以真实实现。
- 外部 API client 可以先保留接口和模拟响应。

### 面试可能追问

问：怎么避免 Agent 乱调用高风险工具？

答：工具调用前先做权限校验和参数校验，退款、补偿、关闭工单这类高风险工具必须走人工审批；工具执行结果写入审计日志，失败时有超时、重试和降级策略。

## P0：RAG 评估集与离线评测报告

### 为什么加分

很多简历只写“做了 RAG”，但没有质量评估。加入评估集和报告后，可以从“能跑”提升到“能衡量”。

### 建议改造

- 构造 30-50 条客服问题 golden set，覆盖退款、保修、物流、账户、技术支持。
- 每条样本包含 `query`、`expected_answer_points`、`expected_sources` 和 `risk_level`。
- 输出 recall、faithfulness、answer relevance、citation hit rate、hallucination rate。
- 生成 JSON 和 Markdown 评估报告。

### 简历可写法

> 构建客服 RAG 离线评测集，覆盖退款、保修、物流和账户问题，设计 citation hit rate、faithfulness、answer relevance 等指标，用于量化知识库问答质量。

### 可 mock 细节

- Golden set 可以使用合成数据，但要标注为 synthetic evaluation dataset。
- 指标可以先用本地规则和文本匹配，后续再接 LLM-as-Judge。

### 面试可能追问

问：如果评估集是自己造的，指标可信么？

答：合成评估集适合验证工程链路和回归测试，但不能代表真实生产效果。生产环境需要从真实历史工单采样，经过人工标注后形成 golden set。

## P0：工单闭环状态机

### 为什么加分

客服系统的核心不是只回答问题，而是推动工单从创建、处理中、待审批到解决。状态机能体现业务闭环。

### 已落地改造

- 新增 `src/tickets/state_machine.py`，统一管理工单状态流转。
- 明确定义 `open`、`in_progress`、`pending_approval`、`resolved`、`closed`。
- AI 回复进入审批后自动变更为 `pending_approval`。
- 审批通过或修改后变更为 `resolved`。
- 审批拒绝后回到 `in_progress`。
- 新增关闭已解决工单的接口，非法流转返回 `409 Conflict`。

### 后续可增强

- 将状态流转历史持久化到数据库。
- 增加 SLA 超时规则和自动升级原因。
- 为不同角色限制不同状态动作。

### 简历可写法

> 设计工单状态机和审批闭环，将 AI 草稿生成、人工审批、状态流转和 SLA 升级串联起来，保证客服 Agent 不只生成回复，还能驱动工单处理流程。

### 可 mock 细节

- 状态机和数据库变更可以真实实现。
- SLA 规则可以使用本地配置。
- 企业工单系统同步可以先 mock。

### 面试可能追问

问：为什么要状态机，而不是直接改 status 字段？

答：状态机可以限制非法流转，例如未审批的 AI 回复不能直接关闭工单；同时方便记录审计、触发 SLA 规则和生成运营指标。

## P1：OpenTelemetry Trace 串联 Agent 全链路

### 为什么加分

LLM 应用出现慢请求或错误时，需要知道耗时花在检索、工具调用、LLM 还是审批。Trace 能体现生产排障能力。

### 已落地改造

- 为 HTTP 请求创建 `api.*` span。
- 为 `agent.workflow` 和 analyzer、tooling、retriever、resolver、QA、escalation 节点创建 span。
- 为工具调用创建 `tool.*` span，记录工具名、角色、状态、耗时和 mock 标记。
- 为 RAG 查询创建 `rag.query` 和 `rag.query_fallback` span。
- 为审批创建和审批处理创建 `approval.*` span。
- 将 `ticket_id`、`customer_id`、`kb_version`、`department`、`operator_role`、工具状态和 citation 数量写入 span attributes。

### 后续可增强

- 为 Collector 增加 Jaeger、Tempo 或其他 APM exporter。
- 完善 Trace sampling、Collector 高可用与容量告警。
- 在前端展示响应中的 trace id，方便客服定位单次请求。

### 简历可写法

> 引入 OpenTelemetry Trace，将一次客服请求中的 Agent 节点、工具调用、RAG 检索和 LLM 生成串联为可观测链路，支持慢请求定位和错误排查。

### 可 mock 细节

- 本地可以只输出 console exporter。
- 不一定需要真实 Jaeger / Tempo 集群。

### 面试可能追问

问：已有 Prometheus 为什么还要 Trace？

答：Prometheus 适合看整体指标和趋势，Trace 适合定位单次请求的耗时路径。比如可以看到某个请求是 RAG 慢、LLM 慢还是工具超时。

## P1：多租户知识库隔离

### 为什么加分

企业客服常见多业务线、多品牌、多租户场景。知识库隔离能体现 SaaS 架构意识。

### 建议改造

- 在知识文档 metadata 中增加 `tenant_id`。
- 查询时强制带上 `tenant_id + kb_version` filter。
- API 层从用户或 token 中解析 tenant。
- 测试不同租户不能检索到彼此文档。

### 简历可写法

> 为 RAG 知识库增加租户隔离设计，通过 `tenant_id + kb_version` metadata filter 限定检索范围，避免跨业务线知识污染。

### 可 mock 细节

- 租户和用户可以使用本地 mock 数据。
- 隔离逻辑可以真实实现。

### 面试可能追问

问：只靠 metadata filter 安全么？

答：metadata filter 是应用层隔离，适合 demo 和小规模场景。生产环境还需要数据库权限、索引隔离、审计日志和越权测试。

## P1：生产级检索后端方案

### 为什么加分

当前项目有 ChromaDB 和进程内 BM25 风格 scorer。下一步可以设计搜索后端替换方案，体现 RAG 架构深度。

### 建议改造

- 增加 `SearchBackend` 接口。
- 提供 `ChromaHybridBackend` 和 `OpenSearchHybridBackend` 两种设计。
- 支持向量召回、BM25、metadata filter、rerank 和 citation。
- 文档中说明不同方案的延迟、成本、可维护性取舍。

### 简历可写法

> 抽象 RAG 检索后端接口，设计 Chroma 本地检索与 OpenSearch 生产检索两套方案，支持向量召回、BM25、metadata filter 和 rerank。

### 可 mock 细节

- OpenSearch 可以先只做接口和文档，不必真的部署。
- 本地仍使用 ChromaDB 跑通 demo。

### 面试可能追问

问：为什么不用一个向量库解决所有问题？

答：客服场景有很多精确词，比如订单号、政策编号、产品型号。纯向量检索容易漏掉这些词，混合检索能同时兼顾语义相似和精确匹配。

## P2：客服工作台前端

### 为什么加分

如果投偏应用开发或全栈岗位，一个可演示的工作台能显著提升项目观感。

### 建议改造

- 工单列表和筛选。
- AI 回复草稿展示。
- RAG citation 展示。
- 工具上下文展示。
- 人工审批、修改、拒绝按钮。
- 风险原因和 QA 分数展示。

### 简历可写法

> 设计客服 Agent 工作台，展示 AI 草稿、知识库 citation、工具上下文和风险评分，并支持人工审批与修改。

### 可 mock 细节

- 前端数据可以直接调本地 API。
- 不需要真实企业 UI 权限体系。

## P2：A/B Prompt 与版本灰度

### 为什么加分

体现 LLM 应用不是写死 prompt，而是可运营、可实验、可回滚。

### 建议改造

- 为 analyzer、resolver、QA prompt 增加版本号。
- 支持按请求或租户选择 prompt version。
- 记录每个版本的通过率、审批率、QA 分数和延迟。
- 增加 prompt rollback 文档。

### 简历可写法

> 设计 Prompt 版本管理和灰度机制，记录不同 prompt 版本下的 QA 分数、审批率和延迟指标，支持快速回滚。

### 可 mock 细节

- Prompt 内容和版本配置可以本地维护。
- 指标可以用本地 demo 数据生成。

## 推荐实施顺序

1. **先做 RAG 评估集与报告**：最容易形成量化指标，简历加分明显。
2. **再做工具调用协议与权限控制**：贴合客服 Agent 场景，面试容易展开。
3. **补工单状态机**：强化业务闭环，不只是 Chatbot。
4. **加 OpenTelemetry Trace**：体现生产排障思维。
5. **设计多租户知识库隔离**：提升企业级架构感。

## 简历上如何区分

### 已实现后可以写

- “实现”
- “设计并落地”
- “接入”
- “支持”

### 只有文档或 mock 时建议写

- “设计”
- “规划”
- “模拟”
- “预留接口”
- “可替换为”

### 不建议写

- “生产上线”
- “真实企业客户使用”
- “接入真实 CRM / OMS”
- “通过真实业务压测”

除非这些事实已经真实发生并且有代码、数据或部署记录支撑。
