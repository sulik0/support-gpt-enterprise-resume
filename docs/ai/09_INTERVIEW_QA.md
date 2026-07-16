# SupportGPT Enterprise 面试问答

> 本文针对客服 Agent 项目的高频面试问题给出统一回答。所有事实必须与 `03_INTERVIEW_CANON.md` 保持一致。涉及“我负责”“独立开发”等个人经历时，应根据本人真实情况调整，不能仅凭仓库推断。

## 一、项目整体架构

### 1. 请介绍一下你的客服 Agent 平台？

这是一个面向企业售后客服场景的、可本地运行的生产风格 Agent 平台。它把初版 FAQ / RAG 问答扩展为一条完整的客服处理链：先理解工单和识别风险，再补充客户、订单与历史工单上下文，检索售后知识，生成回复草稿，执行 QA 和输出过滤，最后决定是否进入人工审批。

平台目前有 6 个逻辑 Agent 节点、4 个注册 Tool，使用 LangGraph 编排，使用 ChromaDB 做 Hybrid RAG，使用 SQLAlchemy 持久化工单与审批，Redis 作为可选短期会话缓存，并通过 Prometheus 和 OpenTelemetry 做可观测性。CRM、OMS、工单工具与默认 LLM 都是本地 Mock，不是已接入的真实企业系统。

### 2. 为什么传统 FAQ 系统无法满足售后场景？

传统 FAQ 主要解决“问题到固定答案”的映射，但售后问题通常依赖客户、订单和历史处理事实。例如同样问退款，不同订单状态、购买时间和投诉历史会导致不同处理路径。

售后还存在 Prompt Injection、隐私、退款权限、服务故障、低置信度回复和人工审批等要求。FAQ 无法自然表达条件路由、Tool Calling、风险拦截、QA、SLA 和工单状态闭环，因此需要受控 Agent Workflow。

### 3. 你的客服 Agent 整体架构是什么？

架构可以分为五层：

1. FastAPI 接入层：聊天、工单、审批、鉴权、评测和 Metrics。
2. LangGraph 编排层：Analyzer、Tooling、Retriever、Resolver、QA、Escalation。
3. 上下文层：ToolRegistry 提供结构化业务上下文，Hybrid RAG 提供知识 citation。
4. 数据层：SQLite / PostgreSQL 保存领域数据，Redis 可选保存短期会话，ChromaDB 保存向量分块。
5. 治理层：Prompt Guardrails、RBAC、工单状态机、HITL、Prometheus 和 OpenTelemetry。

正常路径是 Analyzer → Tooling → Retriever → Resolver → QA → Escalation；安全风险会从 Analyzer 直接短路到 Escalation。

### 4. 为什么选择 Agent，而不是普通 RAG 问答？

普通 RAG 只解决“找到知识并回答”，但本项目还要解决“是否允许继续、需要哪些业务事实、是否调用订单工具、回答是否可信、是否要人工审批、工单如何流转”。这些问题需要状态、工具、路由和业务规则。

因此这里的 Agent 不是自由自治模型，而是被 Workflow 约束的任务执行系统。RAG 是其中一个节点，不是整个系统。

### 5. 这个项目解决了哪些业务问题？

项目面向退款、技术故障、物流异常、订单取消、账户问题和一般售后咨询，主要解决：

- 客户问题的意图、情绪、优先级和部门识别。
- 客户画像、订单状态与历史工单补全。
- 售后政策和 FAQ 的可溯源检索。
- AI 回复草稿、幻觉检测和输出泄露过滤。
- 高风险、紧急或低质量回复的人工审批。
- 工单从创建、待审批、解决到关闭的合法状态流转。

### 6. 从用户输入到最终回复，完整流程是什么？

系统先创建工单并读取会话存储，然后对当前输入进行 Prompt Injection、Jailbreak 和 PII 处理。安全请求被短路；正常请求进入分类，得到情绪、优先级、部门和意图。

之后查询客户画像和历史工单，相关场景再查订单；接着按知识库版本和业务类别做 Hybrid RAG，得到最多 3 条 citation。Resolver 合并 Tool Context 与 citation 生成草稿，QA 检查依据、幻觉和泄露，Escalation 根据安全、优先级、情绪和 QA 决定是否审批。需要审批时创建待审批记录；不需要时返回草稿及审计信息。

要注意，“本次 Agent 返回回复”不等于“工单已关闭”。工单只有经过合法状态流转才进入 resolved 和 closed。

### 7. LangGraph 在你的项目中承担什么角色？

LangGraph 是 Agent 编排器。它定义节点顺序、共享 State、条件路由和工作流结束条件，并让每个阶段可以独立记录 Trace 和耗时。

它不负责数据库、向量检索或权限本身；这些能力由对应模块实现，再由 LangGraph 组织进同一请求路径。

### 8. 为什么选择 LangGraph，而不是自己写状态机？

LangGraph 原生提供状态图、条件边和异步节点执行，适合表达安全短路和固定处理链，也更容易让节点级 Trace 与 State 更新保持一致。

自己写状态机当然可行，但要自行处理节点注册、状态合并、条件路由、异步调用、错误传播和可视化。当前项目仍然自己实现了“工单业务状态机”；LangGraph 解决的是 Agent 执行编排，两者职责不同。

### 9. 如果不用 LangGraph，你会怎么实现？

我会保留相同的六阶段契约，用一个显式的异步 Orchestrator 顺序执行节点，在安全检测后做条件分支，并使用统一的 State 对象传递结果。每个节点需要统一的输入输出、错误模型、超时、Metrics 和 Trace。

如果流程变成长任务，还需要引入工作流引擎或消息队列来处理持久化状态、幂等、重试和人工中断恢复。对当前短流程，自建 Orchestrator 可以工作，但维护成本高于 LangGraph。

## 二、LangGraph Agent 编排

### 10. 你的 LangGraph Workflow 有哪些节点？

当前是 6 个逻辑节点：

```text
Analyzer（包含 Input Guard 与分类）
  ├─ 安全风险 → Escalation → END
  └─ 正常请求 → Tooling → Retriever → Resolver → QA → Escalation → END
```

项目没有独立 Tool Planner、Tool Executor、Human Review Graph 节点。Tooling 内部按确定性规则调用受治理工具；Human Review 发生在 Graph 完成后的审批流程中。

### 11. 为什么这样拆节点？

拆分依据是职责、风险和可观测边界：Analyzer 处理不可信输入；Tooling 获取业务事实；Retriever 获取知识事实；Resolver 只负责表达；QA 独立审查；Escalation 执行业务风险规则。

这样可以避免一个大 Prompt 同时分类、调用工具、回答和自我放行，也能快速定位错误发生在分类、工具、检索、生成还是 QA。

### 12. 每个节点之间传递什么 State？

State 包含：工单与客户标识、主题与描述、知识库版本；情绪、优先级、部门和意图；操作角色、Tool Context 与 Tool Calls；citation 与回复草稿；QA 分数、幻觉标记、升级原因、是否审批；以及 token、成本、延迟和错误列表。

节点只补充或更新自己负责的字段，后续节点消费已产生的信息。

### 13. State 怎么设计？

当前使用 `AgentState`，而不是示例中的独立 `TicketState` 或 `TaskState`。设计上按六类字段组织：输入标识、分类结果、工具上下文、RAG 结果、质量与风险、可观测元数据。

选择单一 State 是因为当前流程短且线性。它的缺点是以后加入动态子任务、Checkpoint 或并行执行时会膨胀；到那时应拆分 `TaskState` 与执行状态，而不是继续无限加字段。

### 14. 为什么不用多个自治 Agent，而采用 Workflow？

项目已有 6 个逻辑 Agent，但它们不是互相自由协商的自治 Agent。售后场景需要保证安全、检索、QA 和审批不可跳过，因此采用固定 Workflow。

自治多 Agent 更适合开放式研究任务，但会带来工具误选、循环、成本、结果不稳定和难以审计的问题。这里优先选择受控分工。

### 15. 哪些步骤需要 LLM，哪些应该代码实现？

适合 LLM 的是语义理解和自然语言任务：工单分类、回复生成、QA 语义判断。默认 Mock Provider 也实现了同样接口，方便测试。

必须用确定性代码实现的是 Prompt Injection/Jailbreak 基础规则、PII 脱敏、Tool Schema、RBAC、超时、知识库过滤、状态机、审批条件、Metrics 和审计。原则是：涉及权限、状态、资金风险和不可绕过规则的部分不能只交给 LLM。

### 16. 如何避免 Agent 自主规划导致流程失控？

当前根本不提供动态 Planner。执行路径由固定图决定，工具选择是确定性规则，所有工具经过 Registry，退款初筛要求 Manager 权限，QA 和 Escalation 是固定关卡。

系统也没有 Reflection Loop 和通用自动 Retry，因此不会因低分而无限重写或重复调用工具。高风险失败转人工。

### 17. 如何保证退款流程一定经过审批？

必须先澄清：当前项目能保证退款资格初筛工具只有 Manager 及以上角色可调用，且真实退款动作并不存在；但当前 Escalation 规则没有单独写死“所有 refund intent 必须审批”。Mock 分类通常会把退款识别为 negative + high，从而触发审批，但这不是对所有 Provider 的绝对保证。

如果业务要求“任何退款都必须审批”，正确做法是在确定性策略层增加 `refund intent → approval_required` 的硬规则，并让真实退款执行只能在 approved 状态后由幂等、高权限工具完成。不能只靠 Prompt 或模型分类保证。

## 三、工单理解与任务分类

### 18. 用户请求如何分类？

正常输入先脱敏，然后由 LLM Provider 输出情绪、优先级、部门、意图、情绪标签和置信度。当前部门范围主要是 billing、technical、shipping、general，优先级为 low、medium、high、urgent。

安全风险在分类前检测，命中后不再进行正常分类和生成。

### 19. Intent 分类是规则还是 LLM？

业务分类由 LLM Provider 完成；默认 Mock Provider 使用确定性关键词模拟分类，OpenAI/Azure 模式使用 JSON Prompt。

订单工具是否调用、是否升级等下游决策由代码规则完成。也就是说，语义识别由模型负责，权限和关键业务决策由确定性逻辑负责。

### 20. 为什么客服场景需要意图识别？

意图影响需要读取的数据、知识检索类别和处理风险。退款需要订单与账单政策，物流需要订单状态与配送规则，技术故障需要技术知识和更短 SLA。

没有意图识别，系统只能全量查工具和全库检索，会增加隐私暴露、延迟和知识噪声。

### 21. 意图分类错误怎么办？

当前有两层有限兜底：RAG 在类别检索为空时会保留知识库版本并去掉类别过滤重试一次；QA 在无依据或低质量时会触发人工审批。

但当前没有二次分类器、置信度路由或自动重规划。更完整的方案是记录分类置信度、支持多标签、对低置信度触发澄清或人工，并用 Golden Set 评估分类准确率。

### 22. 多意图工单如何处理？

当前 Analyzer 只返回一个主要 intent 和一个 department，没有真正的多标签意图拆分。因此“订单没收到，而且我要投诉”可能只被主意图覆盖，投诉升级主要依赖情绪与优先级规则。

这是现有限制。演进方案是输出 `intents[]`、主次意图和风险标签，并将物流调查与投诉升级拆成受控子任务；在实现前不能声称已支持多意图编排。

### 23. 工单上下文补全怎么实现？

正常请求通过 Tooling 补充客户画像和历史工单；账单、退款、物流或订单相关意图再补充近期订单。得到的内容包括客户等级、未结工单数、订单状态与金额、过去工单状态和处理结果。

这些事实与 RAG citation 一起进入回复生成。当前数据来自 Mock Adapter，架构上可替换真实 CRM、OMS 和工单 Client。

### 24. 缺少必要信息时 Agent 怎么处理？

当前没有完整 Slot Filling 或“缺字段后自动追问”的状态机。系统主要依赖 customer_id 查询已有 Mock 上下文；如果订单或知识依据不足，Resolver 应给出需要升级的保守回复，QA 也会因缺少 context 降低分数并转人工。

如果要支持“我要退款”后追问 order_id 和 reason，需要新增必填 Slot 定义、缺失字段检测、澄清问题、跨轮状态保存和完成条件。当前不能把该能力写成已实现。

## 四、Tool Calling 与 ToolRegistry

### 25. 为什么设计 ToolRegistry？

ToolRegistry 把工具定义、参数 Schema、最低角色、超时、Mock 标记和审计集中管理。这样 Agent 不能绕过权限直接调用业务 Adapter，也能让每次调用的允许状态、耗时和错误可见。

它解决的是工具治理，而不仅是“让模型能调用函数”。

### 26. 为什么不用直接把所有工具放给 LLM？

直接暴露所有工具会让模型决定是否读取敏感数据或触发高风险能力，难以保证最小权限，也可能因 Prompt Injection 误调用工具。

当前系统使用固定 Tooling 规则，且退款初筛要求 Manager 权限。牺牲部分自治能力，换取可预测性和审计性。

### 27. ToolRegistry 怎么设计？

每个 Tool 定义名称、描述、输入 Schema、输出 Schema 描述、最低角色、超时时间、是否 Mock 和 Handler。调用时依次检查工具是否存在、角色权限、输入参数，然后执行并记录结果。

要注意：当前 Pydantic 强校验的是输入参数；输出 Schema 目前是工具元数据描述，还没有做运行时 Pydantic 输出验证。

### 28. Agent 如何选择工具？

当前不是 LLM 自主选择。正常请求始终读取客户画像和历史工单；只有 billing、shipping 或退款、订单、支付等相关意图才读取订单历史。

Manager 级退款资格初筛虽然已注册，但主 Workflow 不会自动调用。这种确定性选择适合当前高风险客服场景。

### 29. 工具描述 Prompt 怎么设计？

当前没有用于 LLM Tool Selection 的工具描述 Prompt，因为工具选择不是模型完成的。Registry 中有中文 description，用于说明工具能力和边界。

如果未来采用 Function Calling 或 MCP，应让描述包含用途、禁止场景、必填参数、返回语义、风险级别和权限，但最终权限判断仍必须由代码执行。

### 30. 如何避免 Agent 调错工具？

第一，工具选择采用确定性规则；第二，所有工具必须注册；第三，Pydantic 校验输入；第四，RBAC 限制高风险工具；第五，设置超时并记录审计；第六，安全输入会在工具之前短路。

当前还没有基于真实数据的工具选择评测，也没有通用 LLM Tool Planner，因此避免的是受控流程中的误调用，而不是解决所有开放式选择问题。

## 五、工具安全控制

### 31. 为什么 Tool Calling 需要安全控制？

Tool 能访问客户、订单和工单事实，未来还可能产生退款、取消订单等副作用。模型输出本身不可信，Prompt Injection 也可能诱导越权调用。

因此必须把身份、权限、参数、超时和审计放在模型之外，确保“模型建议调用”不等于“系统允许执行”。

### 32. Pydantic Schema 在工具调用中做什么？

它负责把输入转换为明确结构并验证必填字段、类型和最小约束。例如 customer_id、order_id 不能为空。验证在 Handler 执行前完成，避免无效参数进入业务系统。

当前输出 Schema 只是描述性元数据，尚未做同等级别的运行时输出校验，这是可改进点。

### 33. 参数校验失败怎么办？

工具不会执行，调用结果记录为 `validation_error`，并把错误写入审计结果。这样上游能看到失败原因，也不会因错误参数产生业务副作用。

当前不会自动让 LLM 修复参数并重试；未来若增加，必须限制次数并防止攻击者借此探测 Schema。

### 34. RBAC 权限控制怎么设计？

角色等级为 agent、manager、admin。每个 Tool 声明最低角色：三个读取类工具允许 agent 及以上调用，退款资格初筛要求 manager 及以上。

当前没有真实 refund_create 或 modify_order 工具，不能用它们作为已实现例子。API 层也使用 JWT 和角色检查保护审批等接口。

### 35. 为什么退款操作不能直接让 Agent 调用？

退款涉及资金、政策适用性和客户权益，模型可能因分类错误、幻觉或攻击输入做出错误承诺。真实退款还需要幂等、审批、审计和财务系统确认。

当前项目只有 Manager 级 Mock 资格初筛，没有真实退款执行。正确边界是 AI 提供上下文和草稿，人类批准后才可能由受控系统执行真实动作。

### 36. 如何限制高风险工具？

通过最低角色、输入 Schema、显式注册、超时、审计和不在主 Workflow 自动调用来限制。真实高风险工具还应增加审批凭证、幂等键、金额限制、双人复核和不可重试策略。

项目当前只实现前一组基础治理，没有真实资金工具。

### 37. 工具调用超时怎么办？

每个当前工具的超时为 1 秒。超时后停止等待，记录 `timeout`、耗时和错误，不把它伪装成成功。

当前没有自动重试。对未来真实外部读工具可采用有限退避重试；对写操作必须先解决幂等和重复副作用。

### 38. 外部系统失败怎么办？

当前 Adapter 是 Mock，但 Registry 已把执行异常转换为可审计错误。Tooling 整体异常时会返回空业务上下文和错误列表，后续 RAG 与 QA 仍可继续；上下文不足时应走保守回复或人工审批。

当前没有 Circuit Breaker、Fallback Provider、消息队列或 Dead Letter Queue。生产接入真实系统时需要补齐这些能力。

### 39. 如何记录工具调用审计？

每次调用记录工具名、调用角色、工单 ID、是否允许、状态、耗时、是否 Mock 和错误。API 会把去除实际结果后的审计信息返回给前端，OpenTelemetry Span 也记录核心属性。

当前 Registry 的审计日志保存在进程内，没有持久化审计表。因此可以说“生成并暴露工具调用审计”，不能说“已建立完整合规审计平台”。

## 六、RAG 知识库

### 40. 客服为什么需要 RAG？

客服回复需要依据当前政策，而模型参数知识可能过期，也不了解企业内部退款窗口、技术指引和账户流程。RAG 把可管理的知识片段放进生成上下文，并返回 citation 供 QA 和人工核验。

RAG 不能替代订单 Tool：RAG 解决政策知识，Tool 解决客户和订单事实。

### 41. 你的知识库包含哪些内容？

当前种子知识库实际包含：v1 与 v2 退款政策、API 故障处理指引、账户设置指引。文档解析能力支持 PDF、DOCX、HTML、TXT、Markdown 和结构化 FAQ。

项目目标场景还包括保修、物流和订单取消，但当前种子数据不能被描述为已经完整覆盖这些知识领域。

### 42. RAG 完整流程是什么？

离线侧：文档解析 → 递归切分 → Embedding → 原文与 metadata 写入 SQL → chunk、向量和 metadata 写入 ChromaDB。

在线侧：工单主题与描述构造 Query → 生成 Query Embedding → 按版本和类别过滤 → 向量召回与 BM25 风格词法召回 → 合并候选 → 轻量 rerank → 返回 Top 3 citation → Resolver 生成 → QA 校验。

### 43. 为什么使用 Hybrid RAG？

客服问题同时存在语义表达和精确规则词。向量检索擅长同义表达，词法检索擅长“30 天”“API 504”“产品型号”等精确词。

Hybrid RAG 把两类信号融合，比纯向量更适合政策型知识，同时保持本地实现可运行。

### 44. BM25 和向量检索分别解决什么问题？

BM25 基于词频、逆文档频率和文档长度，适合精确术语、编号、时间和专有名词。向量检索基于 Embedding 相似度，适合语义相近但用词不同的表达。

两者不是互相替代，而是分别覆盖 lexical match 和 semantic match。

### 45. 为什么退款规则适合关键词检索？

退款规则常由明确条件组成，如“30 天”“60 天”“5% 手续费”“原支付卡”“3–5 个工作日”。这些词一旦漏掉，回答可能改变政策含义。

关键词检索能增强这些精确条件的召回，向量检索则帮助理解“退钱”“撤销付款”等语义变体。

### 46. ChromaDB 为什么选择它？

ChromaDB 本地集成简单，支持持久化或测试时内存模式，也支持 metadata filter，适合无外部向量服务的简历 Demo。

它的代价是大规模集群、真正的分布式 BM25、容量治理和生产运维能力有限，因此被定位为当前本地后端，而不是最终生产搜索方案。

### 47. ChromaDB 和 Milvus 有什么区别？

ChromaDB 更轻量，适合本地开发、小规模知识库和快速验证。Milvus 面向更大规模向量数据、分布式索引和高吞吐检索，部署与运维复杂度也更高。

当前项目使用 ChromaDB，没有使用 Milvus，也没有做两者的实测基准对比。

### 48. 生产环境为什么可能换 Milvus？

如果向量规模、并发、索引构建和水平扩展需求显著增加，Milvus 可能比本地 ChromaDB 更合适。但本项目当前路线图更倾向抽象 SearchBackend 并评估 OpenSearch，因为客服还需要成熟 BM25 和过滤能力。

因此不能直接说“生产一定换 Milvus”。应根据数据规模、混合检索、运维能力和成本选择 Milvus、OpenSearch 或 pgvector。

## 七、RAG 优化

### 49. Chunk 怎么设计？

当前使用递归文本切分，默认 chunk size 为 600 字符，overlap 为 120 字符。它按段落、换行、句子和空格逐级切分，目标是在上下文完整性与检索粒度之间平衡。

这个参数是工程默认值，不是通过真实 Golden Set 调优得到的最优结果。

### 50. Chunk 太大有什么问题？

大 chunk 会混入多个主题，导致向量语义变模糊、citation 不精确、Prompt token 增加，也让 QA 难以判断具体结论来自哪一段。

优点是上下文完整，适合法规长条款；因此不能只追求越小越好。

### 51. Chunk 太小有什么问题？

小 chunk 容易切断条件、例外和结论，例如只召回“30 天”却丢失“不存在争议”这一资格条件。它还会增加 chunk 数量、索引和候选合并成本。

overlap 用于缓解边界切断，但过大又会造成重复召回。

### 52. 如何选择 TopK？

当前最终 TopK 为 3，候选阶段最多扩大到 `TopK × 4`，即通常 12 条，再进行合并和 rerank。选择 3 是为了限制 Prompt 长度和噪声，同时给 QA 足够依据。

这不是经过正式评测得到的最优值。生产上应在 Golden Set 上比较 Recall、Faithfulness、延迟和 token 成本，而不是固定照搬。

### 53. 为什么需要 Rerank？

第一阶段召回目标是“不漏”，但向量和词法候选的分数不可直接比较，也可能包含重复或仅局部匹配的片段。Rerank 用于融合信号并把更适合回答的问题片段排到前面。

没有 Rerank，TopK 可能被单一检索信号主导。

### 54. Rerank 放在哪一步？

放在向量与词法候选召回、去重合并之后，截取最终 TopK 之前。这样既保留较宽候选集，又只把少量高分 citation 交给 LLM。

当前是轻量规则 rerank，不是独立模型服务。

### 55. Cross Encoder 和 Embedding 模型区别？

Embedding 模型分别编码 Query 和 Document，向量可预计算，适合大规模初召回。Cross Encoder 把 Query 与 Document 成对输入模型，能建模更细交互，通常排序更准，但每个候选都要推理，成本和延迟更高。

当前项目使用 Embedding 召回和轻量规则 rerank，没有 Cross Encoder。

## 八、引用溯源 Citation

### 56. citation 怎么实现？

知识 chunk 入库时携带 title、doc_id、version、category 和 chunk index 等 metadata。检索后把来源标题与版本、chunk 文本和最终分数封装为 citation，并随 API 响应返回。

Resolver 也把 citation 的来源和内容放入 Knowledge Base Context。

### 57. 如何保证回答引用真实存在？

返回给客户端的 citation 来自 ChromaDB 实际检索结果，而不是让 LLM 自己编一个来源。QA 使用同一批 citation 检查回复依据。

但当前没有严格的 claim-to-citation 对齐器，无法证明回复中每个句子都被某条 citation 支撑。因此能保证“引用对象存在”，不能保证“每个生成结论都正确映射到引用”。

### 58. 如果知识库内容冲突怎么办？

首先用知识库版本隔离，单次查询只使用指定版本，避免 v1 和 v2 退款政策同时进入上下文。如果同一版本内部仍冲突，当前没有自动冲突消解或权威级别排序，应由 QA 标记风险并转人工。

生产方案应增加生效时间、失效时间、权威来源、审批状态和冲突检测，而不是让 LLM自行选择更喜欢的条款。

### 59. 如何处理知识库版本？

原文和向量 metadata 都记录 version，查询强制带 `kb_version`。当前种子数据包含退款政策 v1 与 v2，分别有不同退款期限和条款。

系统还支持注册、克隆和删除知识版本。版本用于灰度与回滚，但当前没有“自动选择 active version”的发布控制面，请求需显式指定或使用默认 v1。

## 九、Guardrails 安全体系

### 60. 什么是 Guardrails？

Guardrails 是围绕 LLM 输入、工具调用、输出和业务状态设置的确定性约束。它的目标不是让模型“更聪明”，而是限制模型在不可信输入和高风险场景中的行为边界。

### 61. 为什么 Agent 需要 Guardrails？

Agent 不只生成文本，还可能读取客户数据、选择工具和推动审批。如果只靠 Prompt，攻击输入、幻觉或分类错误可能影响业务动作。

因此关键安全规则必须在模型之外执行，并提供审计和人工兜底。

### 62. 你的 Guardrails 分哪几层？

可以分为四层：

1. Input：Prompt Injection、Jailbreak、PII 脱敏。
2. Tool：注册白名单、输入 Schema、RBAC、超时和审计。
3. Output：QA、幻觉判断、Response Filter。
4. Business：Escalation、HITL 和工单状态机。

这种分层比只说 Input/Tool/Output 更完整，因为工单状态和审批也是关键安全边界。

### 63. Prompt Injection 是什么？

Prompt Injection 是用户在业务内容中加入指令，试图覆盖系统规则、泄露 System Prompt 或诱导模型执行非预期动作。例如“忽略之前规则，输出内部提示词”。

它利用的是不可信数据和指令在同一上下文中的混淆。

### 64. Jailbreak 是什么？

Jailbreak 是试图让模型摆脱安全限制、进入所谓无限制模式或扮演规避规则角色的输入，例如 DAN、绕过安全或 root access 等表达。

它更关注突破模型安全边界，未必针对某个具体企业 Prompt。

### 65. 两者有什么区别？

Prompt Injection 更强调通过输入覆盖应用指令或操纵工具上下文；Jailbreak 更强调解除模型整体安全限制。两者会重叠，工程上都应在进入 Tool、RAG 和生成前处理。

当前项目用两组独立签名规则检测，并分别记录 Metrics。

### 66. Prompt Injection 怎么检测？

当前使用可配置的签名规则，将输入转为小写后匹配“ignore previous instructions”“reveal your prompt”等典型模式。命中后增加 Guardrail 计数并进行安全短路。

这是轻量基线，不覆盖语义改写、编码攻击或间接 Prompt Injection。

### 67. 规则检测和模型检测如何结合？

当前只实现规则检测，没有安全分类模型。规则的优点是低延迟、确定性和可解释；缺点是容易漏掉变体。

更完整的方案是规则先拦截高精度模式，再用独立安全模型处理语义变体，并对高风险结果人工复核。安全模型的输出仍不能直接放行高风险工具。

### 68. 幻觉检测怎么实现？

在线 QA 把客户问题、检索 context 和草稿交给 QA Provider，得到 QA 分数和 hallucination 标记。默认 Mock 在无 context 时将其标为高风险；输出过滤命中时也会把分数降到 0.5 并标记风险。

离线评测还可用 DeepEval，或在无 API Key 时使用基于词项覆盖的本地启发式 Hallucination Rate。

### 69. 如何判断回答是否有依据？

核心是比较回答与检索 citation：是否有 context、关键结论是否能在 context 中找到、QA Provider 的 faithfulness 与 citation_verified 如何、Response Filter 是否命中。

当前没有逐句 Claim Extraction 和 NLI 验证，因此这是风险判断，不是形式化证明。低分或无 context 时应转人工。

### 70. Faithfulness 怎么计算？

在真实 RAGAS 模式下由 RAGAS 评估回答是否被 context 支撑。本地降级模式把 Hallucination Rate 定义为回复中不被 context 词项覆盖的可评估词比例，再用 `1 - Hallucination Rate` 得到 Faithfulness。

本地算法是启发式，适合回归管道演示，不应当作生产语义准确率。

### 71. 为什么不能完全依赖 LLM Judge？

LLM Judge 也会受 Prompt、模型版本、上下文长度和随机性影响，可能与被评模型共享偏差；它还有成本、延迟和数据出域问题。

因此应结合确定性规则、Golden Set、人工标注、业务指标和 LLM Judge。当前项目尚无 Golden Set，这是明确缺口。

## 十、QA 评分体系

### 72. QA Score 是什么？

QA Score 是对当前回复草稿可信度和质量的 0 到 1 风险信号，用于决定是否可以继续自动处理。它不是客户满意度，也不是已验证的线上准确率。

当前阈值是 0.8；低于阈值会触发 Escalation 和人工审批。

### 73. QA 评分指标有哪些？

在线 QA 输出 `qa_score`、`hallucination_detected`、reasons、faithfulness、context_precision 和 citation_verified。输出过滤也会影响最终风险结果。

离线评测还包含 Context Recall、Answer Relevance 和 Hallucination Rate。当前没有独立“礼貌度”或“是否解决问题”分类器，不能把示例指标全部写成现状。

### 74. QA 分数低怎么处理？

当前流程是：低分 → 标记 Escalation → 创建待审批记录 → 人工通过、修改或拒绝。当前**不会先自动重新生成**。

不采用自动重写是因为低分可能来自知识缺失或业务事实不足，多次改写只会让错误更流畅。未来若加入 Reflection，只能限次并比较新旧答案质量。

## 十一、人工审批 HITL

### 75. 为什么需要 Human-in-the-loop？

模型不能承担退款承诺、重大投诉、紧急故障和低依据回复的最终责任。HITL 让人工查看 AI 草稿、citation、风险原因和业务上下文，并保留最终修改或否决权。

它是风险控制机制，不是简单的前端按钮。

### 76. 哪些情况触发人工审批？

当前触发条件是：安全违规、urgent、negative + high、QA 分数低于 0.8、检测到幻觉，或工作流最终建议升级。

不是所有退款意图都由硬编码规则直接触发；若业务要求，应补充确定性退款审批规则。

### 77. 人工审批状态怎么设计？

审批记录状态是 pending、approved、modified、rejected。工单状态是 open、in_progress、pending_approval、resolved、closed。

草稿进入审批时工单变为 pending_approval；通过或修改后 resolved；拒绝后回到 in_progress；resolved 才能 close；resolved 或 closed 可 reopen 到 in_progress。非法流转返回冲突错误。

### 78. AI 草稿和最终回复如何区分？

审批记录分别保存 drafted_response 和 modified_response。approved 时最终回复可使用原草稿，modified 时使用人工修改内容，rejected 时草稿不被接受。

API 返回审批状态和最终选定内容。当前没有单独的“已发送给客户”事件表，因此 resolved 代表审批处理完成，不等于有完整外部发送审计。

### 79. 人工修改后的结果是否反馈模型？

当前不会。人工修改结果保存到审批记录，但没有进入训练集、Prompt Few-shot、长期 Memory 或自动评测回路。

未来可以将经过脱敏和质量审核的修改记录用于 Golden Set 或 Prompt 优化，但必须处理隐私、授权、样本质量和数据版本。

## 十二、Memory

### 80. 客服 Agent 是否需要 Memory？

需要，因为客户问题可能跨多轮沟通，客服也需要看到历史记录。但 Memory 要区分会话消息、历史工单和长期语义记忆，不能混为一谈。

当前实现了会话历史存储和历史工单 Tool Context，但会话历史尚未注入本次 Agent 推理。

### 81. 短期 Memory 存什么？

按 session_id 保存 user 与 assistant 消息。Redis 只保留最近 12 条，TTL 为 24 小时；SQL 保存持久化 conversation_history。

当前不保存 Planner 状态、Checkpoint、工具结果摘要或向量化长期记忆。

### 82. Redis 如何保存会话？

每个 session_id 对应一个消息列表 Key。保存时截取最近 12 条，先更新列表，再设置 24 小时过期。读取或连接失败时返回空结果，主流程回退 SQL。

Redis 是可选缓存，不是唯一事实源。

### 83. 历史工单为什么存 PostgreSQL？

这里要区分两类数据：当前系统创建的 Ticket 会通过 SQLAlchemy 持久化，在 Docker Compose 环境使用 PostgreSQL；Tooling 查询的“历史工单”目前来自 Mock Ticketing Adapter，不是从 PostgreSQL Ticket 表聚合出来的。

生产上历史工单适合放关系数据库，因为需要事务、状态、客户关联、时间筛选和审批关系，但当前不能声称 Mock 历史工具已经改成 PostgreSQL 查询。

### 84. 如何利用历史工单？

正常请求会查询 Mock 历史工单，并将最近处理状态和解决方案放入 Tool Context，帮助 Resolver避免重复建议、识别既往处理结果。

当前没有基于历史工单做相似案例向量检索，也没有自动学习人工处理结果；这些属于后续方向。

## 十三、OpenTelemetry 可观测性

### 85. 为什么 Agent 项目需要链路追踪？

Agent 请求跨越分类、工具、检索、生成、QA 和审批，仅看总延迟无法知道慢在哪一步，也无法解释为什么某次请求被转人工。

链路追踪能把单次请求的阶段、输入维度、状态和耗时关联起来，支持性能排查和决策审计。

### 86. OpenTelemetry 是什么？

OpenTelemetry 是一套厂商中立的可观测标准和 SDK，用于生成、传播与导出 Trace、Metrics 和 Logs 相关遥测数据。

本项目主要使用它创建 Trace Span，默认导出到控制台；尚未接入 OTLP Collector、Jaeger 或 Tempo。

### 87. Trace 和 Span 是什么？

Trace 表示一次端到端请求的完整调用链；Span 表示其中一个有开始、结束、属性和状态的工作单元，例如 RAG 查询或工具调用。

多个父子 Span 组合后，可以看到请求在哪个阶段耗时或失败。

### 88. 你的 Trace 如何设计？

当前 Span 包括：API 请求、Agent Workflow、Analyzer、Tooling、Retriever、Resolver、QA、Escalation、每个 Tool、RAG 主查询与回退、审批创建与审批处理。

属性包括 ticket_id、customer_id、kb_version、department、priority、operator_role、工具状态和耗时、citation 数量、token、成本与审批结论。当前 LLM 没有单独的 Provider Span，主要通过节点 Span 和 token/成本元数据观察，这是改进点。

### 89. 为什么不用普通日志？

日志适合记录离散事件，但跨多个阶段关联同一次请求、计算父子耗时和展示关键路径比较困难。Trace 提供统一上下文和时间结构。

实际生产通常同时保留日志、Metrics 和 Trace，而不是互相替代。

### 90. Agent Trace 和普通微服务 Trace 有什么区别？

普通微服务 Trace 主要关注服务调用、数据库和网络；Agent Trace 还要记录 Prompt 阶段、模型调用、token、检索候选、Tool Calling、QA、路由和人工审批等非确定性步骤。

Agent 还需要注意不能把客户 PII、完整 Prompt 或敏感 Tool 参数直接写入 Trace。

### 91. 如何定位 Agent 慢？

先从 HTTP 延迟 Histogram 判断是否存在整体慢请求，再查看对应 Trace 的 Agent 节点 Span，比较 Tool、RAG、Resolver、QA 和审批耗时。结合 citation 数量、工具状态、token 数量判断是外部调用、检索候选还是模型上下文导致。

当前默认只有 Console Trace，生产上需要 OTLP 后端、Trace ID 关联和采样策略才能高效查询。

### 92. 如何统计 Token 成本？

各 LLM Provider 返回输入和输出 token，Workflow 汇总后按模型价格表估算 USD 成本，并写入响应元数据、Prometheus Counter 和 Trace 属性。Mock Provider 的成本为 0。

当前价格表是静态估算，不保证与供应商最新账单一致；Azure 部署名和实际价格也需要单独映射。

## 十四、Prometheus 指标设计

### 93. 监控哪些指标？

当前实际采集的核心指标包括：HTTP 请求数与延迟、Agent 节点耗时、LLM token 与估算成本、QA 分数分布、情绪分类、Guardrail 违规和工单升级次数。LLM 延迟、Agent 执行次数和活跃会话指标已定义，但当前没有完整的更新逻辑，不能视为可用监控数据。

当前没有可长期引用的工单完成率、工具成功率、缓存命中率、P95 数值或真实转人工率看板。可以从已有指标推导部分比率，但项目尚未产出稳定线上报告。

### 94. Counter、Gauge、Histogram 区别？

Counter 只累计增加，适合请求数、token、成本、违规和升级次数。Gauge 可增可减，适合当前活跃会话或队列长度。Histogram 将观测值放进 Bucket，并产生 count 与 sum，适合请求延迟、节点耗时和 QA 分布。

当前项目定义了活跃会话 Gauge，但没有完整更新逻辑，不能声称已有可靠的活跃会话指标。

### 95. 为什么延迟用 Histogram？

延迟不是一个只增计数，也不能只看平均值。Histogram 保留不同延迟区间的数量，可在 Prometheus 中计算 P50、P95、P99，并按 endpoint 或节点聚合。

前提是 Bucket 与流量足够合理；当前项目没有公布实际 P95 数据。

## 十五、工程化

### 96. FastAPI 如何设计 Agent 服务？

FastAPI 负责 Schema 校验、鉴权依赖、数据库 Session、Agent 调用、审批持久化和响应装配。核心接口覆盖聊天、工单创建与关闭、回复建议、情绪与升级分析、客户上下文、响应评测和人工审批。

API 返回的不只有文本，还包括 Tool Context、Tool Calls、citation、升级原因、审批 ID 和成本元数据，便于前端审核和排障。

### 97. 同步调用和异步调用怎么处理？

API、SQLAlchemy Session、LangGraph 节点和 LLM Provider 采用 async。同步 Mock Tool Handler 被放到线程执行，并由异步超时包裹，避免直接阻塞事件循环。

部分 ChromaDB 与本地库调用仍是同步实现；规模扩大后应使用线程池隔离、异步 Client 或独立检索服务，并通过压测确认事件循环是否阻塞。

### 98. 如何限制并发 LLM 请求？

当前没有显式 Semaphore、Rate Limiter、队列或 Provider 级并发上限，因此不能声称已完成并发治理。

生产方案应按 Provider 和租户设置并发 Semaphore、请求队列、超时、429 退避、预算限制和熔断；写操作与 LLM 重试还要保证幂等。

### 99. 如何做缓存？

当前缓存只用于会话历史：Redis 保存最近 12 条消息并设置 24 小时 TTL，失败时回退 SQL。

当前没有 Prompt Cache、LLM Response Cache、Embedding Cache 或 RAG Query Cache。知识政策可能版本变化，若增加缓存必须把 tenant、kb_version、模型和 Prompt 版本纳入 Key，并设计失效策略。

### 100. 如何部署？

本地可直接以 SQLite、Mock LLM 和本地 ChromaDB 运行。Docker Compose 编排 backend、PostgreSQL、Redis 和 Prometheus；Dockerfile 使用 Python 3.11 多阶段构建；仓库还有 3 副本、健康检查和资源限制的 Kubernetes manifests。

这些是部署模板，不代表已在真实生产环境上线。生产还需 Secret 管理、数据库迁移、持久卷、OTLP、Ingress、TLS、备份、扩缩容和压测。

## 十六、项目真实性追问

### 101. 这个项目你独立开发，最大的难点是什么？

“独立开发”这一前提必须按真实经历回答，仓库不能证明团队人数或个人贡献。安全口径是：项目基于开源项目改造，我只讲自己确实参与并能解释的部分。

从项目工程角度，最大的难点是平衡 Agent 能力与业务可控性：既要引入 Tool Context 和 RAG，又要保证安全短路、RBAC、QA、审批和状态机不可绕过。同时还要诚实区分 Mock 集成与真实生产能力。

### 102. 最后为什么选择 LangGraph？

因为当前不是单次 RAG 问答，而是一个有 State、固定阶段和安全条件边的工作流。LangGraph 能清晰表达六节点主链和安全短路，并方便节点级测试与 Trace。

我选择它不是为了追求“多 Agent”标签，而是因为它与受控客服流程匹配；如果只有一次检索和一次生成，普通函数或 Chain 就足够。

### 103. 你觉得当前系统最大的问题是什么？

最大问题是缺少能量化质量的 Golden Set 和真实业务数据。现有 RAGAS/DeepEval Adapter 与本地启发式指标能跑通管道，但无法证明真实召回、Faithfulness 或业务收益。

其次是业务系统仍为 Mock、会话历史未注入推理、审计未持久化、无多租户隔离和生产 Trace 后端。

### 104. 如果用户问一个知识库没有的问题怎么办？

系统先在部门类别内检索，空结果时保留知识库版本并去掉类别过滤回退一次。如果仍无 citation，Resolver 应保守说明需要升级，QA 在无 context 时降低分数并标记幻觉，最终进入人工审批。

不能让模型凭参数知识编造公司政策。当前 Mock Resolver 可能生成固定话术，但 QA 会对空 context 标记风险；生产 Prompt 和规则还应进一步强制无依据不回答。

### 105. 如果模型生成错误退款承诺怎么办？

当前防线包括退款政策 citation、QA、幻觉检测、negative + high 升级、Manager 级退款初筛和人工审批。项目没有真实退款执行工具，因此错误文本不会直接产生资金动作。

但要保证所有错误承诺都不外发，还需要增加 refund intent 的硬审批规则、禁止性输出规则和逐句 Claim-to-Citation 校验。当前不能声称已经百分之百阻止错误退款承诺。

### 106. 如果 Agent 调用了错误工具怎么办？

当前工具选择是确定性规则，不由 LLM自由规划；Registry 还会检查注册白名单、参数和角色。误调用会留下工具名、角色、状态和耗时审计。

当前工具主要是读操作且为 Mock。真实写工具上线前需要审批 Token、幂等键、最小权限、操作前确认和补偿流程。

### 107. 如果工具调用失败怎么办？

失败会被记录为 validation_error、permission_denied、timeout 或 error，不会伪装成成功。Tooling 可在无业务上下文的情况下继续到 RAG，QA 再根据依据决定是否转人工。

当前没有通用重试和 Circuit Breaker。生产读工具可有限重试，写工具必须先解决幂等与重复副作用。

### 108. 如果 RAG 检索到了错误文档怎么办？

系统用 kb_version 和 category 限制范围，再用向量、BM25 风格分数和 rerank 排序，并把 citation 暴露给 QA 与人工。如果类别为空会回退，但仍保持版本隔离。

当前没有训练型 Reranker、权威级别和冲突检测，因此错误文档仍可能进入 TopK。应通过 Golden Set、文档生效时间、来源等级、Cross Encoder 和人工反馈改进。

### 109. 如何证明你的 Agent 比普通 FAQ 好？

当前不能用真实线上数据证明，因为没有基准实验和 Golden Set。只能从能力上说明它比 FAQ 多了业务上下文、条件路由、Tool 治理、Hybrid RAG、citation、QA、HITL、状态机和可观测性。

要形成证据，应建立同一测试集，对比 FAQ Baseline 与 Agent 在 citation hit rate、Context Recall、Answer Relevance、Faithfulness、人工审批召回、延迟和成本上的结果。完成前不应声称提升了具体百分比。

### 110. 下一步你会怎么优化这个系统？

优先级如下：

1. P0：构建 30–50 条客服 Golden Set 和稳定 JSON/Markdown 回归报告。
2. P1：增加 tenant_id + kb_version 的多租户知识隔离。
3. P1：抽象 SearchBackend，评估 OpenSearch 生产 Hybrid Search。
4. P1：持久化 Tool Call 和工单状态事件审计，接入 OTLP / Jaeger / Tempo。
5. P1：把受控会话历史注入 Agent 推理，并增加长度、隐私和回归测试。
6. P2：完善客服工作台，展示草稿、citation、Tool Context、QA 和审批。
7. P2：在 Golden Set 基础上做 Prompt 版本管理与灰度，而不是先做无指标的 A/B。

## 回答使用原则

- 只引用 `03_INTERVIEW_CANON.md` 中可证实的事实。
- CRM、OMS、历史工单、退款初筛和默认 LLM 必须明确为 Mock。
- 当前是 6 个逻辑 Agent 节点、4 个注册 Tool、0 个 MCP。
- 当前没有 TaskState、Checkpoint、动态 Planner、自动 Reflection、通用 Retry、pgvector、Milvus 或生产级搜索后端。
- 当前没有真实上线指标、P95/QPS 基准、真实客户数据或业务提升百分比。
- 个人职责和是否独立开发必须按本人真实经历回答，不能根据仓库推断。
