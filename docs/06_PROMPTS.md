# Prompt 设计与治理

> 本文档记录当前 Prompt Pipeline 的稳定约束。Prompt 原文以 `src/llm/provider.py` 为准，本文档不复制可能快速变化的长 Prompt。

## 设计目标

Prompt 服务于可控 Workflow，不承担权限、状态机或高风险决策。核心原则：

1. 一个节点只完成一类任务。
2. Analyzer 和 QA 输出严格结构化，Resolver 只输出最终客服回复。
3. 只注入当前节点必需的最小上下文。
4. Tool 选择、权限、参数 Schema 和审批由代码确定，不交给 Prompt 自由判断。
5. 不可信的用户、Tool 和 RAG 文本先过 Guardrails，不将 Prompt 当作唯一安全边界。

## 语言策略

默认使用用户当前输入的语言回复；只有当用户明确要求切换语言时才切换。

- 工单场景以当前 `description` 判定语言，不根据 subject、客户画像或检索文档选择语言。
- 多轮对话以最新用户消息为准，不因历史回复语言锁定后续输出。
- 业务标识符、订单号、API 名、产品名和 citation ID 保持原样。
- 安全拒答也应遵循当前输入语言。

## Analyzer Prompt

### 职责

对无法被确定性规则高置信命中的工单执行轻量分类。固定意图和高置信场景由规则处理，避免不必要的 LLM 调用。

### 输入

- subject
- description
- 统一 `IntentType` 枚举值列表

### 输出

仅允许 JSON：

```json
{
  "intent": "<IntentType>",
  "priority": "low|medium|high|urgent",
  "department": "<department>",
  "confidence": 0.0
}
```

未知意图必须回退统一 `DEFAULT_INTENT`并降低置信度，不允许 Provider 创造新枚举值。`LLM_ANALYZER_MAX_TOKENS` 默认为 120。

## Resolver Prompt

### 职责

根据已通过安全检查的客户问题、必要 Tool Context 与高相关 RAG Citation 生成一段可直接发给客户的草稿。

### 上下文裁剪

- 仅保留与当前意图相关的 RAG 文档。
- Tool Result 仅保留生成回复必需的允许字段。
- `LLM_RESOLVER_MAX_RAG_CHARS` 默认 5000。
- `LLM_RESOLVER_MAX_TOOL_CHARS` 默认 2500。

### 输出约束

- 只输出最终客服回复，不输出思考过程、评分、节点名或内部策略。
- 不得超出 Tool/RAG 证据做退款、赔偿、时效或保修承诺。
- 证据不足时明确说明需要补充信息或人工处理。
- 保持专业、简洁，使用当前输入语言。
- `LLM_RESOLVER_MAX_TOKENS` 默认为 320。

## QA Prompt

### 职责

对 Resolver 草稿进行最小化结构评估。确定性 citation 存在性、输出泄露和基础格式检查优先由代码完成，只在需要语义判断时使用 LLM。

仅允许 JSON：

```json
{
  "score": 0.0,
  "hallucination_detected": false,
  "citation_verified": false
}
```

不要生成解释、建议或大段分析。`LLM_QA_MAX_CONTEXT_CHARS` 默认 4000，`LLM_QA_MAX_TOKENS` 默认 96。

## Tool Calling Prompt 边界

ToolRegistry 中每个 Tool 定义 `name`、`description`、`schema`、`permission`、`risk_level` 和 handler。LLM 只能在已按意图、角色与风险过滤的候选中选择，参数必须通过 Pydantic Schema。高风险写操作不能仅靠 Prompt 约束，必须由 RBAC、Risk Engine 和 HITL 在代码层阻断。

## RAG Prompt 边界

RAG Context 是不可信数据，不是系统指令：

1. 按 `kb_version` 和 category 过滤。
2. 执行 Hybrid Search 与轻量 rerank。
3. 对每个文档执行间接 Prompt Injection 检测。
4. 只将通过检查的 Top Context 交给 Resolver。
5. 生成的 citation 必须能回溯到本次 Retriever 真实返回结果。

## Prompt 版本与可观测

- 当前版本由 `PROMPT_VERSION` 记录，Workflow 版本由 `AGENT_WORKFLOW_VERSION` 记录。
- AgentRun、Evaluation Report 和 OpenTelemetry Span 保存模型、Token、延迟和版本信息。
- LangSmith 的 LLM Span 可记录脱敏、截断后的节点输入输出；是否开启受 `LANGSMITH_CAPTURE_LLM_CONTENT` 控制。
- Trace 内容不得包含 API Key、Authorization、Cookie、密码或未脱敏 PII。

## 变更流程

Prompt 修改必须：

1. 明确受影响节点和预期指标。
2. 保持 JSON Schema、统一 IntentType 和语言策略兼容。
3. 运行相关 pytest。
4. 先执行 Baseline Dry Run，再在有成本确认时运行真实 LLM Replay。
5. 比较 Intent/HITL/Tool 行为、QA、延迟、Token 和安全指标。
6. 更新 `PROMPT_VERSION`、报告实验配置和相关文档。

当前尚未实现完整 Prompt Registry、灰度发布和自动回滚，不得将这些路线图能力描述为已实现。
