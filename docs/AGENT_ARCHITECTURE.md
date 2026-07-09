# Agent 架构说明

本文说明 **SupportGPT Enterprise** 中多 Agent 系统的设计、`StateGraph` 状态结构，以及各 Agent 节点的职责。

---

## LangGraph 状态编排器

系统使用 **LangGraph** 构建有状态的多 Agent 工作流。`AgentState` 字典作为共享状态，由各个节点按顺序读取和更新：

```python
class AgentState(TypedDict):
    ticket_id: int
    customer_id: str
    subject: str
    description: str
    kb_version: str
    sentiment: str
    priority: str
    intent: str
    department: str
    context_citations: List[Citation]
    suggested_response: str
    qa_score: float
    hallucination_detected: bool
    escalation_recommended: bool
    escalation_reason: Optional[str]
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_seconds: float
    approval_required: bool
    errors: List[str]
```

---

## 节点 Agent 与职责

### 1. 工单分析 Agent (`analyzer.py`)

- **职责**：对客户输入做 PII 脱敏，检测 prompt injection 和 jailbreak 风险，并分析语气与意图。
- **输出变量**：`sentiment`、`priority`、`department`、`intent`。

### 2. 工具上下文 Agent (`tooling.py`)

- **职责**：调用 CRM、订单、历史工单等工具适配器，为回复生成补充结构化业务上下文。
- **输出变量**：`tool_context`。
- **边界说明**：当前 CRM、订单和工单工具是本地 mock 适配器，用于演示真实企业系统集成路径。

### 3. 知识检索 Agent (`retriever.py`)

- **职责**：基于当前工单和知识库版本，从 ChromaDB 中检索相关政策、FAQ 和操作指引。
- **输出变量**：`context_citations`。

### 4. 回复生成 Agent (`resolver.py`)

- **职责**：结合工单内容、RAG 引用和工具上下文，生成面向客户的客服回复草稿。
- **输出变量**：`suggested_response`。

### 5. 质量校验 Agent (`quality_assurance.py`)

- **职责**：检查回复是否被引用材料支撑，是否存在幻觉风险，是否泄露内部 prompt 或工作流信息。
- **输出变量**：`qa_score`、`hallucination_detected`。

### 6. 升级决策 Agent (`escalation.py`)

- **职责**：计算 SLA 建议，并对高优先级、低质量分、幻觉风险或安全风险工单触发人工升级。
- **输出变量**：`escalation_recommended`、`escalation_reason`、`sla_hours`。

---

## 当前工作流

```text
analyzer
  ├── security threat -> escalation -> END
  └── normal request  -> tooling -> retriever -> resolver -> qa -> escalation -> END
```

该流程适合简历表述为：基于 LangGraph 设计客服 Agent 工作流，将安全检测、工具上下文、RAG 检索、回复生成、QA 校验和人工升级拆分为可观测节点。
