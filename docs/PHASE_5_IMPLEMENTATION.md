# 阶段 5：实现说明

## 目标

实现异步、模块化、可测试的 Python 后端，覆盖：

- 输入和输出安全 guardrails。
- RAG 文档切分、向量写入和混合检索。
- LangGraph 有状态 Agent 节点。
- 工单、审批、会话和知识库元数据 API。

---

## 设计决策

代码按职责拆分：

- `src/guardrails/`：PII 脱敏、prompt injection 检测、jailbreak 检测和输出过滤。
- `src/agents/`：LangGraph 节点和工作流。
- `src/rag/`：文档解析、切分、向量存储和知识库版本管理。
- `src/tools/`：CRM、订单、历史工单等工具适配器。
- `src/approval/`：人工审批流程。
- `src/observability/`：Prometheus 指标和成本统计。

---

## 代码参考

- PII 脱敏规则：`src/guardrails/pii_detection.py`
- LangGraph 节点映射：`src/agents/graph.py`
- RAG 向量写入与检索：`src/rag/vector_store.py`

---

## 验证步骤

1. 检查各模块位于对应 package 下。
2. 运行 `python -m compileall src tests`。
